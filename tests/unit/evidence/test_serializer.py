"""Focused evidence-context version contracts."""

import json

import pytest

from finproof.data.holdings import HoldingCoverageState
from finproof.domain.evidence import (
    EvidenceBundle,
    EvidenceSummary,
    EvidenceSummaryKind,
    HoldingCoverageEvidenceRef,
)
from finproof.domain.query_plan import ProductType
from finproof.evidence import serialize_evidence_context


def test_empty_holding_references_preserve_exact_v2_bytes() -> None:
    evidence = EvidenceBundle(
        direct=(),
        derived=(),
        summaries=(),
        material_policy_limitations=(),
    )

    assert serialize_evidence_context(evidence) == (
        '{"derived":[],"derived_fields":["evidence_id","product_type","product_id",'
        '"field_id","value","quality_status","rule_id","rule_version","as_of_date",'
        '"inputs"],"direct":[],"direct_fields":["evidence_id","product_type",'
        '"product_id","field_id","raw_value","normalized_value","quality_status",'
        '"rule_id","rule_version","source","source_row_number","source_column_name",'
        '"source_column_number","source_column_letter","source_applicable_date"],'
        '"format":"evidence_context.v2","locator_fields":["source",'
        '"source_row_number","source_column_name","source_column_number",'
        '"source_column_letter","source_applicable_date"],'
        '"material_policy_limitations":[],"sources":[],"summaries":[]}'
    )


def test_nonempty_holding_reference_emits_explicit_v3_context() -> None:
    coverage = HoldingCoverageEvidenceRef(
        evidence_id="coverage:domestic_etn:ETN-1",
        owner_product_type=ProductType.DOMESTIC_ETN,
        owner_product_id="ETN-1",
        coverage_state=HoldingCoverageState.UNAVAILABLE,
        source_generation_id=None,
        observed_holding_count=0,
        limitation_code="source_unavailable",
        source_kind=None,
        source_as_of_date=None,
    )
    evidence = EvidenceBundle(
        direct=(),
        derived=(),
        summaries=(),
        material_policy_limitations=(),
        holding_coverage=(coverage,),
    )

    serialized = serialize_evidence_context(evidence)

    assert serialized == (
        '{"derived":[],"derived_fields":["evidence_id","product_type","product_id",'
        '"field_id","value","quality_status","rule_id","rule_version","as_of_date",'
        '"inputs"],"direct":[],"direct_fields":["evidence_id","product_type",'
        '"product_id","field_id","raw_value","normalized_value","quality_status",'
        '"rule_id","rule_version","source","source_row_number","source_column_name",'
        '"source_column_number","source_column_letter","source_applicable_date"],'
        '"format":"evidence_context.v3","holding_coverage":[{"coverage_state":'
        '"unavailable","evidence_id":"coverage:domestic_etn:ETN-1",'
        '"limitation_code":"source_unavailable","observed_holding_count":0,'
        '"owner_product_id":"ETN-1","owner_product_type":"domestic_etn",'
        '"source_as_of_date":null,"source_generation_id":null,"source_kind":null}],'
        '"holding_records":[],"locator_fields":["source","source_row_number",'
        '"source_column_name","source_column_number","source_column_letter",'
        '"source_applicable_date"],"material_policy_limitations":[],"sources":[],'
        '"summaries":[]}'
    )


def _summary(index: int) -> EvidenceSummary:
    return EvidenceSummary(
        summary_id=f"summary:rank:{index:02d}",
        kind=EvidenceSummaryKind.RANK,
        included_count=40,
        excluded_count=12,
        evidence_ids=(f"evidence:{index:02d}",),
        policy_versions=("policy:a",) if index < 20 else ("policy:b", "policy:shared"),
        validated_plan_sha256="a" * 64,
        version_bundle_sha256="b" * 64,
        artifact_manifest_hash="c" * 64,
        partition_key="historical_total_return:None:1y:same_period_and_compatible_source_semantics",
        product_id=f"P{index:02d}",
        metric_id="return_1y",
        rank=index + 1,
        tie_count=1,
        value=index,
    )


def _summary_bundle() -> EvidenceBundle:
    return EvidenceBundle(
        direct=(),
        derived=(),
        summaries=tuple(_summary(index) for index in range(40)),
        material_policy_limitations=(),
    )


def test_overflowing_summary_context_uses_deterministic_lossless_v4() -> None:
    evidence = _summary_bundle()

    first = serialize_evidence_context(evidence)
    second = serialize_evidence_context(evidence)
    payload = json.loads(first)

    assert first == second
    assert len(first.encode()) <= 24_000
    assert payload["format"] == "evidence_context.v4"
    assert payload["summary_context_fields"] == [
        "validated_plan_sha256",
        "version_bundle_sha256",
        "artifact_manifest_hash",
    ]
    assert payload["summary_context"] == ["a" * 64, "b" * 64, "c" * 64]
    assert payload["summary_policy_versions"] == [
        ["policy:a"],
        ["policy:b", "policy:shared"],
    ]
    assert payload["summary_fields"] == [
        "summary_id",
        "kind",
        "included_count",
        "excluded_count",
        "evidence_ids",
        "policy",
        "product_types",
        "native_result_grains",
        "partition_key",
        "product_id",
        "metric_id",
        "rank",
        "tie_count",
        "value",
        "group_values",
    ]
    reconstructed = []
    for row in payload["summaries"]:
        compact = dict(zip(payload["summary_fields"], row, strict=True))
        policy_index = compact.pop("policy")
        compact["policy_versions"] = payload["summary_policy_versions"][policy_index]
        compact.update(
            zip(payload["summary_context_fields"], payload["summary_context"], strict=True)
        )
        reconstructed.append(compact)
    assert reconstructed == [item.model_dump(mode="json") for item in evidence.summaries]


def test_overflowing_v4_rejects_mixed_summary_context() -> None:
    evidence = _summary_bundle()
    changed = evidence.summaries[-1].model_copy(update={"version_bundle_sha256": "d" * 64})

    with pytest.raises(ValueError, match="summary context differs"):
        serialize_evidence_context(
            evidence.model_copy(update={"summaries": (*evidence.summaries[:-1], changed)})
        )


def test_v4_still_fails_closed_when_lossless_payload_exceeds_bound() -> None:
    evidence = _summary_bundle().model_copy(update={"material_policy_limitations": ("x" * 24_000,)})

    with pytest.raises(ValueError, match="evidence context exceeds configured bound"):
        serialize_evidence_context(evidence)
