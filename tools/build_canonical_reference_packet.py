"""Build deterministic references for approved questions and draft plans."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import date
from hashlib import sha256
from pathlib import Path

from finproof.core.settings import Settings
from finproof.data.artifacts.safe_files import read_held_regular_file
from finproof.domain.answers import AnswerRequest
from finproof.domain.query_plan import QueryPlan
from finproof.evaluation.models import EvaluationCategory
from finproof.runtime.session import open_runtime_artifact_session
from finproof.service.answer_service import AnswerService

_INPUT_KEYS = {
    "batch_id",
    "review_status",
    "reviewer",
    "reviewed_at",
    "source_question_packet_sha256",
    "cases",
}
_CASE_KEYS = {"case_id", "category", "question", "plan"}
_APPROVED_STATUS = "human_approved_questions"
_PENDING_STATUS = "pending_human_plan_and_expectation_review"


def build_reference_packet(
    input_path: Path,
    output: Path,
    *,
    artifact_dir: Path,
    repository_root: Path,
) -> None:
    """Execute every draft plan for a human-approved question in one session."""
    _validate_noncanonical_path(input_path, repository_root=repository_root, label="input")
    _validate_output_path(output, repository_root=repository_root)
    raw_input = read_held_regular_file(_absolute(input_path))
    source, approved_cases = _load_approved_packet(raw_input)
    settings = Settings.model_validate(
        {
            "repository_root": repository_root,
            "artifact_dir": artifact_dir,
            "database_path": artifact_dir / "finproof.duckdb",
            "hcx_enabled": False,
            "hcx_api_key": None,
        },
        strict=True,
    )

    with open_runtime_artifact_session(settings) as session:
        service = AnswerService(session)
        artifact = session.verified_artifacts
        cases = []
        for case_id, category, question, plan in approved_cases:
            result = service.answer_plan(
                AnswerRequest(question_id=case_id, question=question),
                plan,
            )
            retrieved_context = json.loads(
                result.retrieved_context,
                object_pairs_hook=_reject_duplicate_pairs,
            )
            if type(retrieved_context) is not dict:
                raise ValueError("retrieved context must be one JSON object")
            trace = result.trace.model_dump(mode="json")
            trace["latency_ms"] = {}
            cases.append(
                {
                    "case_id": case_id,
                    "category": category,
                    "question": question,
                    "plan": plan.model_dump(mode="json"),
                    "answer": result.answer.model_dump(mode="json"),
                    "retrieved_context": retrieved_context,
                    "trace": trace,
                }
            )
        artifact_identity = {
            "artifact_set_id": artifact.artifact_set_id,
            "artifact_contract_version": artifact.artifact_contract_version,
            "dataset_version": artifact.dataset_version.isoformat(),
            "manifest_logical_hash": artifact.overall_manifest_logical_hash,
        }

    packet = {
        "batch_id": source["batch_id"],
        "question_and_draft_plan_packet_sha256": sha256(raw_input).hexdigest(),
        "source_question_packet_sha256": source["source_question_packet_sha256"],
        "question_review": {
            "reviewer": source["reviewer"],
            "reviewed_at": source["reviewed_at"],
        },
        "review_status": _PENDING_STATUS,
        "artifact_identity": artifact_identity,
        "cases": cases,
    }
    _write_new_json(output, packet)


def _load_approved_packet(
    raw: bytes,
) -> tuple[dict[str, object], tuple[tuple[str, str, str, QueryPlan], ...]]:
    try:
        payload = json.loads(raw, object_pairs_hook=_reject_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("question-and-draft-plan packet must be valid UTF-8 JSON") from exc
    if type(payload) is not dict or set(payload) != _INPUT_KEYS:
        raise ValueError("question-and-draft-plan packet has an invalid root shape")
    for key in ("batch_id", "reviewer"):
        value = payload[key]
        if (
            type(value) is not str
            or value != value.strip()
            or not value
            or (key == "reviewer" and len(value) > 200)
        ):
            raise ValueError(f"question-and-draft-plan packet {key} is invalid")
    if payload["review_status"] != _APPROVED_STATUS:
        raise ValueError("approved question packet lacks explicit human approval")
    reviewed_at = payload["reviewed_at"]
    if type(reviewed_at) is not str:
        raise ValueError("question-and-draft-plan packet reviewed_at is invalid")
    try:
        date.fromisoformat(reviewed_at)
    except ValueError as exc:
        raise ValueError("question-and-draft-plan packet reviewed_at is invalid") from exc
    checksum = payload["source_question_packet_sha256"]
    if (
        type(checksum) is not str
        or len(checksum) != 64
        or any(character not in "0123456789abcdef" for character in checksum)
    ):
        raise ValueError("question-and-draft-plan packet source checksum is invalid")
    raw_cases = payload["cases"]
    if type(raw_cases) is not list or not raw_cases:
        raise ValueError("question-and-draft-plan packet cases must be a nonempty list")

    approved_cases: list[tuple[str, str, str, QueryPlan]] = []
    seen_ids: set[str] = set()
    for raw_case in raw_cases:
        if type(raw_case) is not dict or set(raw_case) != _CASE_KEYS:
            raise ValueError("draft-plan case has an invalid shape")
        case_id = raw_case["case_id"]
        category = raw_case["category"]
        question = raw_case["question"]
        if (
            type(case_id) is not str
            or case_id != case_id.strip()
            or not 1 <= len(case_id) <= 200
            or case_id in seen_ids
        ):
            raise ValueError("draft-plan case ID is invalid or duplicate")
        if (
            type(question) is not str
            or question != question.strip()
            or not 1 <= len(question) <= 4_000
        ):
            raise ValueError("draft-plan case question is invalid")
        try:
            EvaluationCategory(category)
        except (TypeError, ValueError) as exc:
            raise ValueError("draft-plan case category is invalid") from exc
        raw_plan = raw_case["plan"]
        if type(raw_plan) is not dict:
            raise ValueError("draft-plan case plan must be one JSON object")
        plan = QueryPlan.model_validate_json(
            json.dumps(raw_plan, ensure_ascii=False),
            strict=True,
        )
        approved_cases.append((case_id, category, question, plan))
        seen_ids.add(case_id)
    return payload, tuple(approved_cases)


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON object keys must be unique")
        result[key] = value
    return result


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def _validate_noncanonical_path(path: Path, *, repository_root: Path, label: str) -> None:
    canonical_root = (repository_root / "evaluation" / "canonical").resolve()
    if path.resolve().is_relative_to(canonical_root):
        raise ValueError(f"reference packet {label} must not be under canonical data")


def _validate_output_path(output: Path, *, repository_root: Path) -> None:
    _validate_noncanonical_path(output, repository_root=repository_root, label="output")
    if output.suffix != ".json":
        raise ValueError("reference packet output must use a .json suffix")
    if output.exists():
        raise FileExistsError(output)


def _write_new_json(output: Path, packet: dict[str, object]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.pending.tmp"
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(packet, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        output.hardlink_to(temporary)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build noncanonical references for approved questions and draft plans."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    build_reference_packet(
        args.input,
        args.output,
        artifact_dir=args.artifact_dir,
        repository_root=args.repository_root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
