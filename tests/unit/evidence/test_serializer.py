"""Focused evidence-context version contracts."""

from finproof.data.holdings import HoldingCoverageState
from finproof.domain.evidence import EvidenceBundle, HoldingCoverageEvidenceRef
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

    assert '"format":"evidence_context.v3"' in serialized
    assert '"holding_coverage"' in serialized
    assert coverage.evidence_id in serialized
