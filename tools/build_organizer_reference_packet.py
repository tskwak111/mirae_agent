"""Execute the approved August organizer plans into a reviewable reference packet."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path

from finproof.core.settings import ExecutionMode, Settings
from finproof.data.artifacts.safe_files import read_held_regular_file
from finproof.domain.answers import AnswerRequest
from finproof.domain.query_plan import Intent, QueryPlan
from finproof.evaluation.loader import OrganizerDifficulty
from finproof.evaluation.models import EvaluationCategory
from finproof.runtime.session import open_runtime_artifact_session
from finproof.service.answer_service import AnswerService
from tools.build_canonical_reference_packet import (
    _absolute,
    _reject_duplicate_pairs,
    _write_new_json,
)

_PACKET_KEYS = {
    "schema_version",
    "suite_id",
    "review_status",
    "reviewer",
    "snapshot_date",
    "artifact_manifest_logical_hash",
    "target_distribution",
    "coverage_note",
    "cases",
}
_APPROVAL_KEYS = {
    "schema_version",
    "suite_id",
    "review_status",
    "reviewer",
    "reviewed_at",
    "question_plan_packet_sha256",
}
_CASE_KEYS = {"case_id", "difficulty", "coverage_tags", "category", "question", "plan"}
_DISTRIBUTION = {"easy": 10, "medium": 10, "hard": 10, "unanswerable": 5}


def build_organizer_reference_packet(
    packet_path: Path,
    approval_path: Path,
    output: Path,
    *,
    artifact_dir: Path,
    repository_root: Path,
    code_commit: str,
) -> None:
    review_dir = (repository_root / "evaluation/organizer_20260824/review").resolve()
    if any(path.resolve().parent != review_dir for path in (packet_path, approval_path, output)):
        raise ValueError("organizer review paths differ")
    if output.suffix != ".json" or output.exists():
        raise FileExistsError(output) if output.exists() else ValueError("output must be JSON")
    if len(code_commit) != 40 or any(
        character not in "0123456789abcdef" for character in code_commit
    ):
        raise ValueError("code commit is invalid")

    packet_raw = read_held_regular_file(_absolute(packet_path))
    approval_raw = read_held_regular_file(_absolute(approval_path))
    packet = _load_json(packet_raw, "question-plan packet")
    approval = _load_json(approval_raw, "question-plan approval")
    cases = _validate_inputs(packet, approval, sha256(packet_raw).hexdigest())
    settings = Settings.model_validate(
        {
            "repository_root": repository_root,
            "artifact_dir": artifact_dir,
            "database_path": artifact_dir / "finproof.duckdb",
            "execution_mode": ExecutionMode.EXTENDED_DEMO,
            "hcx_enabled": False,
            "hcx_api_key": None,
        },
        strict=True,
    )

    with open_runtime_artifact_session(settings) as session:
        artifact = session.verified_artifacts
        artifact_identity = {
            "artifact_set_id": artifact.artifact_set_id,
            "artifact_contract_version": artifact.artifact_contract_version,
            "dataset_version": artifact.dataset_version.isoformat(),
            "manifest_logical_hash": artifact.overall_manifest_logical_hash,
        }
        if (
            artifact_identity["dataset_version"] != packet["snapshot_date"]
            or artifact_identity["manifest_logical_hash"]
            != packet["artifact_manifest_logical_hash"]
        ):
            raise ValueError("approved packet and artifact identity differ")
        service = AnswerService(session)
        references = []
        failures: list[str] = []
        for raw, plan in cases:
            try:
                result = service.answer_plan(
                    AnswerRequest(question_id=str(raw["case_id"]), question=str(raw["question"])),
                    plan,
                )
            except Exception as error:
                failures.append(f"{raw['case_id']}:{type(error).__name__}:{error}")
                continue
            context = json.loads(
                result.retrieved_context, object_pairs_hook=_reject_duplicate_pairs
            )
            if type(context) is not dict:
                raise ValueError("retrieved context must be one JSON object")
            trace = result.trace.model_dump(mode="json")
            trace["latency_ms"] = {}
            references.append(
                {
                    **raw,
                    "answer": result.answer.model_dump(mode="json"),
                    "retrieved_context": context,
                    "trace": trace,
                }
            )
        if failures:
            raise RuntimeError("organizer references failed: " + "; ".join(failures))

    _write_new_json(
        output,
        {
            "schema_version": "organizer_expected_reference_review.v1",
            "suite_id": "organizer_20260824",
            "question_plan_packet_sha256": sha256(packet_raw).hexdigest(),
            "question_plan_approval_sha256": sha256(approval_raw).hexdigest(),
            "question_plan_approval": {
                "reviewer": approval["reviewer"],
                "reviewed_at": approval["reviewed_at"],
            },
            "review_status": "pending_human_expected_results_and_answers_review",
            "code_commit": code_commit,
            "artifact_identity": artifact_identity,
            "cases": references,
        },
    )


def _validate_inputs(
    packet: Mapping[str, object], approval: Mapping[str, object], packet_checksum: str
) -> tuple[tuple[dict[str, object], QueryPlan], ...]:
    if set(packet) != _PACKET_KEYS or set(approval) != _APPROVAL_KEYS:
        raise ValueError("organizer packet or approval shape differs")
    if (
        packet["schema_version"] != "organizer_question_plan_review.v1"
        or packet["suite_id"] != "organizer_20260824"
        or packet["review_status"] != "pending_human_question_plan_review"
        or packet["snapshot_date"] != "2026-08-24"
        or packet["target_distribution"] != _DISTRIBUTION
    ):
        raise ValueError("organizer question-plan contract differs")
    if (
        approval["schema_version"] != "organizer_question_plan_approval.v1"
        or approval["suite_id"] != packet["suite_id"]
        or approval["review_status"] != "human_approved_questions_and_draft_plans"
        or approval["reviewer"] != packet["reviewer"]
        or approval["question_plan_packet_sha256"] != packet_checksum
    ):
        raise ValueError("approval status or checksum differs")
    if not _is_text(approval["reviewed_at"]) or not _is_checksum(
        packet["artifact_manifest_logical_hash"]
    ):
        raise ValueError("organizer approval or artifact identity is invalid")
    raw_cases = packet["cases"]
    if type(raw_cases) is not list or len(raw_cases) != 35:
        raise ValueError("organizer packet must contain 35 cases")

    validated: list[tuple[dict[str, object], QueryPlan]] = []
    seen: set[str] = set()
    for raw in raw_cases:
        if type(raw) is not dict or set(raw) != _CASE_KEYS:
            raise ValueError("organizer case shape differs")
        case_id = raw["case_id"]
        tags = raw["coverage_tags"]
        if not _is_text(case_id) or case_id in seen or not _is_text(raw["question"]):
            raise ValueError("organizer case identity differs")
        try:
            difficulty = OrganizerDifficulty(str(raw["difficulty"]))
            EvaluationCategory(str(raw["category"]))
        except ValueError as error:
            raise ValueError("organizer case classification differs") from error
        if type(tags) is not list or not tags or any(not _is_text(tag) for tag in tags):
            raise ValueError("organizer coverage tags differ")
        plan = QueryPlan.model_validate_json(
            json.dumps(raw["plan"], ensure_ascii=False), strict=True
        )
        terminal = plan.intent in {Intent.CLARIFY, Intent.UNSUPPORTED}
        if (difficulty is OrganizerDifficulty.UNANSWERABLE) is not terminal:
            raise ValueError("organizer difficulty and plan differ")
        validated.append((raw, plan))
        seen.add(str(case_id))
    if Counter(str(raw["difficulty"]) for raw in raw_cases) != _DISTRIBUTION:
        raise ValueError("organizer difficulty distribution differs")
    return tuple(validated)


def _load_json(raw: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw, object_pairs_hook=_reject_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} must be valid UTF-8 JSON") from error
    if type(value) is not dict:
        raise ValueError(f"{label} must be one JSON object")
    return value


def _is_text(value: object) -> bool:
    return type(value) is str and bool(value) and value == value.strip()


def _is_checksum(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--approval", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args(argv)
    build_organizer_reference_packet(
        args.input,
        args.approval,
        args.output,
        artifact_dir=args.artifact_dir,
        repository_root=args.repository_root,
        code_commit=args.code_commit,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
