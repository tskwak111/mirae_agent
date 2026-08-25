"""Promote one explicitly approved deterministic reference packet to canonical JSONL."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path

from pydantic import TypeAdapter

from finproof.cli.evaluate import _observed_aggregates, _observed_products, _rows, _typed_value
from finproof.data.artifacts.safe_files import read_held_regular_file
from finproof.domain.answers import ClaimKind, VerifiedAnswer
from finproof.domain.evidence import EvidenceSummary
from finproof.domain.execution import ExecutionTrace, TraceValidation
from finproof.domain.query_plan import EntityMention, Intent, ProductType, QueryPlan, ResultGrain
from finproof.evaluation.models import (
    EvaluationCategory,
    ExpectedAggregate,
    ExpectedPlan,
    ExpectedValue,
    GoldenCase,
    ValueType,
    native_result_grain,
)
from finproof.query import FieldRegistry
from finproof.registry.loader import RegistryBundle

_APPROVAL_KEYS = {
    "schema_version",
    "batch_id",
    "review_status",
    "reviewer",
    "reviewed_at",
    "reference_packet_sha256",
}
_REFERENCE_KEYS = {
    "batch_id",
    "question_and_draft_plan_packet_sha256",
    "source_question_packet_sha256",
    "question_review",
    "review_status",
    "artifact_identity",
    "cases",
}
_CASE_KEYS = {"case_id", "category", "question", "plan", "answer", "retrieved_context", "trace"}
_CONTEXT_KEYS = {
    "format",
    "sources",
    "direct_fields",
    "direct",
    "derived_fields",
    "derived",
    "locator_fields",
    "summaries",
    "material_policy_limitations",
}
_ARTIFACT_KEYS = {
    "artifact_set_id",
    "artifact_contract_version",
    "dataset_version",
    "manifest_logical_hash",
}
_APPROVAL_VERSION = "canonical_reference_approval.v1"
_APPROVED_STATUS = "human_approved_canonical_references"
_REFERENCE_STATUS = "pending_human_plan_and_expectation_review"
_APPROVED_CASE_COUNT = 24
_SNAPSHOT_CONCEPT = "2026-07-11 제공 스냅샷 기준"
_VALUE_TYPES = {
    "decimal": ValueType.DECIMAL,
    "integer": ValueType.INTEGER,
    "date": ValueType.DATE,
    "string": ValueType.TEXT,
    "ordinal_rating": ValueType.TEXT,
    "boolean": ValueType.BOOLEAN,
}


def promote_reference_packet(
    reference_path: Path,
    approval_path: Path,
    canonical_dir: Path,
    *,
    repository_root: Path,
) -> None:
    """Validate and atomically replace each affected category file."""
    review_dir = (repository_root / "evaluation/review_batches").resolve()
    expected_canonical = (repository_root / "evaluation/canonical").resolve()
    if (
        reference_path.resolve().parent != review_dir
        or approval_path.resolve().parent != review_dir
    ):
        raise ValueError("reference and approval must be under evaluation/review_batches")
    if canonical_dir.resolve() != expected_canonical:
        raise ValueError("canonical output path differs")

    reference_raw = read_held_regular_file(_absolute(reference_path))
    approval = _load_json(read_held_regular_file(_absolute(approval_path)), "approval")
    _validate_approval(approval, sha256(reference_raw).hexdigest())
    reference = _load_json(reference_raw, "reference packet")
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    cases = _build_cases(reference, approval, reference_path.name, fields)
    existing, existing_ids = _load_existing(canonical_dir)
    incoming_ids = {case.case_id for case in cases}
    duplicates = existing_ids & incoming_ids
    if duplicates:
        raise ValueError(f"duplicate canonical case ID: {min(duplicates)}")

    grouped: dict[str, list[bytes]] = {}
    for case in cases:
        line = (case.model_dump_json() + "\n").encode()
        GoldenCase.model_validate_json(line)
        grouped.setdefault(case.category.value, []).append(line)

    outputs: dict[Path, bytes] = {}
    for category, lines in grouped.items():
        path = canonical_dir / f"{category}.jsonl"
        prior = existing.get(path, b"")
        if prior and not prior.endswith(b"\n"):
            prior += b"\n"
        content = prior + b"".join(lines)
        _validate_canonical_bytes(path, content, expected_category=category)
        outputs[path] = content
    _replace_outputs(outputs)


def _validate_approval(approval: Mapping[str, object], reference_checksum: str) -> None:
    if set(approval) != _APPROVAL_KEYS:
        raise ValueError("approval record has an invalid shape")
    expected = {
        "schema_version": _APPROVAL_VERSION,
        "review_status": _APPROVED_STATUS,
        "reference_packet_sha256": reference_checksum,
    }
    if any(approval[key] != value for key, value in expected.items()):
        raise ValueError("approval status or checksum differs")
    for key in ("batch_id", "reviewer", "reviewed_at"):
        value = approval[key]
        if type(value) is not str or not value or value != value.strip():
            raise ValueError(f"approval {key} is invalid")


def _build_cases(
    reference: Mapping[str, object],
    approval: Mapping[str, object],
    reference_name: str,
    fields: FieldRegistry,
) -> tuple[GoldenCase, ...]:
    if set(reference) != _REFERENCE_KEYS or reference["review_status"] != _REFERENCE_STATUS:
        raise ValueError("reference packet has an invalid root shape or status")
    if reference["batch_id"] != approval["batch_id"]:
        raise ValueError("approval batch differs from reference packet")
    batch_id = str(approval["batch_id"])
    if reference_name != f"batch-{batch_id}-reference-review.json":
        raise ValueError("reference packet filename differs from its approved batch")
    question_review = _mapping(reference["question_review"], "question review")
    if set(question_review) != {"reviewer", "reviewed_at"} or (
        question_review["reviewer"] != approval["reviewer"]
    ):
        raise ValueError("approval reviewer differs from question review")
    for key in ("question_and_draft_plan_packet_sha256", "source_question_packet_sha256"):
        _checksum(reference[key], f"reference packet {key}")
    artifact = _validate_artifact(reference["artifact_identity"])
    raw_cases = reference["cases"]
    if type(raw_cases) is not list or len(raw_cases) != _APPROVED_CASE_COUNT:
        raise ValueError("reference packet must contain exactly 24 approved cases")

    checksum = str(approval["reference_packet_sha256"])
    source = (
        f"{reference_name} sha256:{checksum}; "
        f"artifact_set_id={artifact['artifact_set_id']}; "
        f"artifact_contract_version={artifact['artifact_contract_version']}; "
        f"dataset_version={artifact['dataset_version']}; "
        f"manifest_logical_hash={artifact['manifest_logical_hash']}"
    )
    built: list[GoldenCase] = []
    seen: set[str] = set()
    for raw_case in raw_cases:
        case = _mapping(raw_case, "reference case")
        if set(case) != _CASE_KEYS:
            raise ValueError("reference case has an invalid shape")
        case_id = case["case_id"]
        if type(case_id) is not str or not case_id.strip() or case_id in seen:
            raise ValueError("reference packet contains an invalid or duplicate case ID")
        seen.add(case_id)
        built.append(
            _build_case(
                case,
                artifact=artifact,
                reviewer=str(approval["reviewer"]),
                reviewed_at=str(approval["reviewed_at"]),
                source=source,
                fields=fields,
            )
        )
    return tuple(built)


def _build_case(
    raw: Mapping[str, object],
    *,
    artifact: Mapping[str, str],
    reviewer: str,
    reviewed_at: str,
    source: str,
    fields: FieldRegistry,
) -> GoldenCase:
    raw_plan = _mapping(raw["plan"], "plan")
    trace = ExecutionTrace.model_validate_json(
        json.dumps(raw["trace"], ensure_ascii=False), strict=True
    )
    answer = VerifiedAnswer.model_validate_json(
        json.dumps(raw["answer"], ensure_ascii=False), strict=True
    )
    context = _mapping(raw["retrieved_context"], "retrieved context")
    if set(context) != _CONTEXT_KEYS or context["format"] != "evidence_context.v2":
        raise ValueError("retrieved context has an invalid shape")
    direct = _validated_rows(context, "direct")
    derived = _validated_rows(context, "derived")
    summaries = _validated_summaries(context, artifact["manifest_logical_hash"])
    evidence = (*direct, *derived)

    if set(raw_plan) != set(QueryPlan.model_fields):
        raise ValueError("reference plan has an invalid shape")
    expected_plan_data = {key: value for key, value in raw_plan.items() if key != "entities"}
    if len(trace.product_types) > 1:
        segment_grains = {
            segment.product_type: segment.native_result_grain for segment in trace.segments
        }
        expected_plan_data["native_segments"] = [
            {
                "product_type": product_type,
                "native_result_grain": segment_grains.get(
                    product_type, native_result_grain(product_type)
                ),
            }
            for product_type in trace.product_types
        ]
    expected_plan = ExpectedPlan.model_validate(expected_plan_data)
    entities = TypeAdapter(tuple[EntityMention, ...]).validate_json(
        json.dumps(raw_plan["entities"], ensure_ascii=False), strict=True
    )
    plan = QueryPlan.model_validate(
        {
            **expected_plan.model_dump(exclude={"native_segments"}, exclude_unset=True),
            "entities": entities,
        }
    )
    _validate_trace(plan, trace, artifact)

    products = _observed_products(plan, evidence, summaries)
    values = _expected_values(evidence, fields)
    aggregates = tuple(
        ExpectedAggregate.model_validate(value.model_dump())
        for value in _observed_aggregates((), summaries)
    )
    evidence_ids = tuple(
        str(value[key])
        for values_, key in (
            (direct, "evidence_id"),
            (derived, "evidence_id"),
            (summaries, "summary_id"),
        )
        for value in values_
    )
    if len(set(evidence_ids)) != len(evidence_ids):
        raise ValueError("reference case contains duplicate evidence IDs")
    limitations = context["material_policy_limitations"]
    if type(limitations) is not list or any(
        type(item) is not str or not item for item in limitations
    ):
        raise ValueError("material policy limitations differ")
    executable = plan.intent not in {Intent.CLARIFY, Intent.UNSUPPORTED}
    required_concepts = tuple(limitations) if executable else (plan.clarification_reason,)
    if executable and (
        _SNAPSHOT_CONCEPT not in required_concepts or trace.validation is not TraceValidation.PASSED
    ):
        raise ValueError("executable reference lacks its approved snapshot semantics")
    if not executable and trace.validation not in {
        TraceValidation.CLARIFY,
        TraceValidation.UNSUPPORTED,
    }:
        raise ValueError("terminal reference trace differs")
    if any(concept not in answer.text for concept in required_concepts):
        raise ValueError("answer omits an approved material semantic")
    category = raw["category"]
    if type(category) is not str:
        raise ValueError("reference case category differs")

    return GoldenCase.model_validate(
        {
            "case_id": raw["case_id"],
            "category": EvaluationCategory(category),
            "question": raw["question"],
            "expected_plan": expected_plan,
            "expected_result": {
                "products": products,
                "order_matters": any(summary.get("kind") == "rank" for summary in summaries),
                "values": values,
                "aggregates": aggregates,
                "required_evidence_ids": evidence_ids,
                "required_compatibility_partitions": tuple(
                    dict.fromkeys(segment.partition_key for segment in trace.segments)
                ),
                "assembled_envelope": None
                if not executable
                else (
                    trace.result_grain is ResultGrain.PRODUCT
                    and len({segment.native_result_grain for segment in trace.segments}) > 1
                ),
            },
            "expected_answer": {
                "required_concepts": required_concepts,
                "forbidden_concepts": ("실시간",) if executable else (),
                "expect_limitation": bool(limitations)
                or any(claim.kind is ClaimKind.LIMITATION for claim in answer.claims),
                "expect_clarification": trace.validation is TraceValidation.CLARIFY,
            },
            "review": {"reviewer": reviewer, "reviewed_at": reviewed_at, "source": source},
        }
    )


def _expected_values(
    evidence: Sequence[Mapping[str, object]], fields: FieldRegistry
) -> tuple[ExpectedValue, ...]:
    values: list[ExpectedValue] = []
    for item in evidence:
        if item.get("field_id") == "product_id":
            continue
        product_type = ProductType(str(item.get("product_type")))
        field_id = str(item.get("field_id"))
        raw_value = item.get("normalized_value", item.get("value"))
        value_type = (
            ValueType.NULL
            if raw_value is None
            else _VALUE_TYPES[fields.projection(field_id, product_type).value_type]
        )
        values.append(
            ExpectedValue(
                product_id=None if item.get("product_id") is None else str(item["product_id"]),
                field_id=field_id,
                value_type=value_type,
                value=_typed_value(value_type, raw_value),
            )
        )
    return tuple(values)


def _validate_trace(plan: QueryPlan, trace: ExecutionTrace, artifact: Mapping[str, str]) -> None:
    plan_facts = (
        plan.intent,
        plan.product_types,
        plan.as_of_date,
        plan.result_grain,
        plan.top_k_scope,
    )
    trace_facts = (
        trace.intent,
        trace.product_types,
        trace.as_of_date,
        trace.result_grain,
        trace.top_k_scope,
    )
    if trace_facts != plan_facts:
        raise ValueError("reference plan and trace differ")
    if (
        trace.versions.get("dataset_version") != artifact["dataset_version"]
        or trace.versions.get("artifact_manifest_hash") != artifact["manifest_logical_hash"]
    ):
        raise ValueError("trace artifact identity differs")
    segment_products = tuple(dict.fromkeys(segment.product_type for segment in trace.segments))
    if trace.validation is TraceValidation.PASSED and segment_products != plan.product_types:
        raise ValueError("trace segment assignment differs")
    if any(
        segment.native_result_grain is not native_result_grain(segment.product_type)
        for segment in trace.segments
    ):
        raise ValueError("trace native result grain differs")


def _validate_artifact(value: object) -> dict[str, str]:
    artifact = _mapping(value, "artifact identity")
    if set(artifact) != _ARTIFACT_KEYS or any(
        type(item) is not str or not item for item in artifact.values()
    ):
        raise ValueError("artifact identity differs")
    result = {key: str(item) for key, item in artifact.items()}
    _checksum(result["manifest_logical_hash"], "artifact manifest logical hash")
    if result["dataset_version"] != "2026-07-11":
        raise ValueError("artifact dataset version differs")
    return result


def _validated_rows(context: Mapping[str, object], name: str) -> tuple[dict[str, object], ...]:
    fields = context.get(f"{name}_fields")
    rows = context.get(name)
    if (
        type(fields) is not list
        or type(rows) is not list
        or any(type(field) is not str for field in fields)
    ):
        raise ValueError(f"{name} evidence shape differs")
    if any(type(row) is not list or len(row) != len(fields) for row in rows):
        raise ValueError(f"{name} evidence row differs")
    parsed = _rows(context, name)
    required = {"evidence_id", "product_type", "product_id", "field_id"}
    if not required.issubset(fields):
        raise ValueError(f"{name} evidence identity differs")
    return parsed


def _validated_summaries(
    context: Mapping[str, object], manifest_hash: str
) -> tuple[dict[str, object], ...]:
    raw = context.get("summaries")
    if type(raw) is not list:
        raise ValueError("evidence summaries differ")
    result: list[dict[str, object]] = []
    for item in raw:
        summary = EvidenceSummary.model_validate_json(json.dumps(item, ensure_ascii=False))
        if summary.artifact_manifest_hash != manifest_hash:
            raise ValueError("summary artifact identity differs")
        result.append(summary.model_dump(mode="json"))
    return tuple(result)


def _load_existing(canonical_dir: Path) -> tuple[dict[Path, bytes], set[str]]:
    existing: dict[Path, bytes] = {}
    ids: set[str] = set()
    if not canonical_dir.exists():
        return existing, ids
    for path in sorted(canonical_dir.glob("*.jsonl")):
        raw = read_held_regular_file(_absolute(path))
        cases = _validate_canonical_bytes(path, raw, expected_category=path.stem)
        for case in cases:
            if case.case_id in ids:
                raise ValueError(f"duplicate canonical case ID: {case.case_id}")
            ids.add(case.case_id)
        existing[path] = raw
    return existing, ids


def _validate_canonical_bytes(
    path: Path, raw: bytes, *, expected_category: str
) -> tuple[GoldenCase, ...]:
    cases: list[GoldenCase] = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        payload = _load_json(line, f"canonical {path}:{line_number}")
        case = GoldenCase.model_validate(payload)
        if case.category.value != expected_category:
            raise ValueError(f"canonical category differs at {path}:{line_number}")
        cases.append(case)
    return tuple(cases)


def _replace_outputs(outputs: Mapping[Path, bytes]) -> None:
    temporary: list[tuple[Path, Path]] = []
    try:
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            pending = path.with_name(f".{path.name}.pending.tmp")
            with pending.open("xb") as stream:
                stream.write(content)
            temporary.append((pending, path))
        for pending, path in temporary:
            pending.replace(path)
    finally:
        for pending, _ in temporary:
            pending.unlink(missing_ok=True)


def _load_json(raw: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw, object_pairs_hook=_reject_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{label} JSON is invalid") from exc
    if type(value) is not dict:
        raise ValueError(f"{label} JSON must be one object")
    return value


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON object keys must be unique")
        result[key] = value
    return result


def _mapping(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise ValueError(f"{label} must be one object")
    return value


def _checksum(value: object, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} is invalid")
    return value


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote an approved reference packet.")
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--approval", required=True, type=Path)
    parser.add_argument("--canonical-dir", required=True, type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    promote_reference_packet(
        args.reference,
        args.approval,
        args.canonical_dir,
        repository_root=args.repository_root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
