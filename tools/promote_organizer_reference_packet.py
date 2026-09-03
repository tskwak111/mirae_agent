"""Promote one approved August organizer reference packet to the 35-case suite."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path

from finproof.data.artifacts.safe_files import read_held_regular_file
from finproof.evaluation.loader import OrganizerCase, OrganizerDifficulty
from finproof.query import FieldRegistry
from finproof.registry.loader import RegistryBundle
from tools.promote_canonical_reference_packet import (
    _absolute,
    _build_case,
    _checksum,
    _load_json,
    _mapping,
    _replace_outputs,
    _validate_artifact,
)

_APPROVAL_KEYS = {
    "schema_version",
    "suite_id",
    "review_status",
    "reviewer",
    "reviewed_at",
    "expected_reference_packet_sha256",
}
_REFERENCE_KEYS = {
    "schema_version",
    "suite_id",
    "question_plan_packet_sha256",
    "question_plan_approval_sha256",
    "question_plan_approval",
    "review_status",
    "code_commit",
    "artifact_identity",
    "cases",
}
_CASE_KEYS = {
    "case_id",
    "difficulty",
    "coverage_tags",
    "category",
    "question",
    "plan",
    "answer",
    "retrieved_context",
    "trace",
}
_GOLDEN_CASE_KEYS = _CASE_KEYS - {"difficulty", "coverage_tags"}
_DISTRIBUTION = {"easy": 10, "medium": 10, "hard": 10, "unanswerable": 5}


def promote_organizer_reference_packet(
    reference_path: Path,
    approval_path: Path,
    output_dir: Path,
    *,
    repository_root: Path,
) -> None:
    """Validate the approval and atomically replace all four organizer files."""
    expected_output = (repository_root / "evaluation/organizer_20260824").resolve()
    review_dir = (expected_output / "review").resolve()
    if any(path.resolve().parent != review_dir for path in (reference_path, approval_path)):
        raise ValueError("organizer reference and approval paths differ")
    if output_dir.resolve() != expected_output:
        raise ValueError("organizer output path differs")

    reference_raw = read_held_regular_file(_absolute(reference_path))
    approval = _load_json(read_held_regular_file(_absolute(approval_path)), "approval")
    reference_checksum = sha256(reference_raw).hexdigest()
    _validate_approval(approval, reference_checksum)
    reference = _load_json(reference_raw, "organizer reference packet")
    cases = _build_cases(
        reference,
        approval,
        reference_name=reference_path.name,
        reference_checksum=reference_checksum,
    )

    grouped: dict[str, list[bytes]] = {difficulty.value: [] for difficulty in OrganizerDifficulty}
    for case in cases:
        line = (case.model_dump_json() + "\n").encode()
        OrganizerCase.model_validate_json(line)
        grouped[case.difficulty.value].append(line)
    _replace_outputs(
        {
            output_dir / f"{difficulty}.jsonl": b"".join(lines)
            for difficulty, lines in grouped.items()
        }
    )


def _validate_approval(approval: Mapping[str, object], reference_checksum: str) -> None:
    if set(approval) != _APPROVAL_KEYS or any(
        approval.get(key) != value
        for key, value in {
            "schema_version": "organizer_expected_reference_approval.v1",
            "suite_id": "organizer_20260824",
            "review_status": "human_approved_expected_results_and_answers",
            "expected_reference_packet_sha256": reference_checksum,
        }.items()
    ):
        raise ValueError("approval status or checksum differs")
    for key in ("reviewer", "reviewed_at"):
        value = approval[key]
        if type(value) is not str or not value or value != value.strip():
            raise ValueError(f"approval {key} is invalid")


def _build_cases(
    reference: Mapping[str, object],
    approval: Mapping[str, object],
    *,
    reference_name: str,
    reference_checksum: str,
) -> tuple[OrganizerCase, ...]:
    if set(reference) != _REFERENCE_KEYS or any(
        reference.get(key) != value
        for key, value in {
            "schema_version": "organizer_expected_reference_review.v1",
            "suite_id": "organizer_20260824",
            "review_status": "pending_human_expected_results_and_answers_review",
        }.items()
    ):
        raise ValueError("organizer reference packet differs")
    _checksum(reference["question_plan_packet_sha256"], "question-plan packet checksum")
    _checksum(reference["question_plan_approval_sha256"], "question-plan approval checksum")
    code_commit = reference["code_commit"]
    if (
        type(code_commit) is not str
        or len(code_commit) != 40
        or any(character not in "0123456789abcdef" for character in code_commit)
    ):
        raise ValueError("organizer reference code commit differs")
    question_approval = _mapping(reference["question_plan_approval"], "question-plan approval")
    if (
        set(question_approval) != {"reviewer", "reviewed_at"}
        or question_approval["reviewer"] != approval["reviewer"]
    ):
        raise ValueError("organizer reference reviewer differs")
    artifact = _validate_artifact(reference["artifact_identity"])
    raw_cases = reference["cases"]
    if type(raw_cases) is not list or len(raw_cases) != 35:
        raise ValueError("organizer reference packet must contain 35 cases")

    source = (
        f"{reference_name} sha256:{reference_checksum}; "
        f"code_commit={code_commit}; "
        f"artifact_set_id={artifact['artifact_set_id']}; "
        f"artifact_contract_version={artifact['artifact_contract_version']}; "
        f"dataset_version={artifact['dataset_version']}; "
        f"manifest_logical_hash={artifact['manifest_logical_hash']}"
    )
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    built: list[OrganizerCase] = []
    seen: set[str] = set()
    for raw_case in raw_cases:
        case = _mapping(raw_case, "organizer reference case")
        if set(case) != _CASE_KEYS:
            raise ValueError("organizer reference case shape differs")
        case_id = case["case_id"]
        if type(case_id) is not str or not case_id.strip() or case_id in seen:
            raise ValueError("organizer reference case identity differs")
        golden = _build_case(
            {key: case[key] for key in _GOLDEN_CASE_KEYS},
            artifact=artifact,
            reviewer=str(approval["reviewer"]),
            reviewed_at=str(approval["reviewed_at"]),
            source=source,
            fields=fields,
        )
        built.append(
            OrganizerCase.model_validate(
                {
                    **golden.model_dump(mode="python"),
                    "difficulty": case["difficulty"],
                    "coverage_tags": case["coverage_tags"],
                }
            )
        )
        seen.add(case_id)
    if Counter(case.difficulty.value for case in built) != _DISTRIBUTION:
        raise ValueError("organizer difficulty distribution differs")
    return tuple(built)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--approval", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    promote_organizer_reference_packet(
        args.reference,
        args.approval,
        args.output_dir,
        repository_root=args.repository_root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
