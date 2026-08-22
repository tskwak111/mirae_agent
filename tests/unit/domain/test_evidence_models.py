"""Focused Phase 2 evidence-contract tests."""

from datetime import date
from decimal import Decimal
from pathlib import PurePosixPath

import pytest
from pydantic import ValidationError

from finproof.domain.locators import SourceCellLocator
from finproof.domain.quality import QualityStatus
from finproof.domain.query_plan import ProductType
from finproof.domain.values import DerivedValue, NormalizedValue


def _source() -> SourceCellLocator:
    return SourceCellLocator(
        source_table="PREF01N001",
        source_file=PurePosixPath("domestic.xlsx"),
        source_sheet="datarows",
        source_row_number=2,
        source_column_name="buy_yield",
        source_column_number=7,
        source_column_letter="G",
        source_checksum="a" * 64,
        source_snapshot_date=date(2026, 7, 11),
        source_applicable_date=date(2026, 7, 11),
    )


def test_direct_evidence_reuses_complete_source_cell_locator_and_normalized_value() -> None:
    """Direct evidence owns the existing typed Phase 1 value and locator graph."""
    from finproof.domain.evidence import DirectEvidence

    source = _source()
    normalized = NormalizedValue[Decimal](
        raw_value="3.250000",
        normalized_value=Decimal("3.25"),
        quality_status=QualityStatus.VALID,
        rule_id="bond.buy_yield",
        rule_version="1.0.0",
        source=source,
    )
    evidence = DirectEvidence[Decimal](
        evidence_id="direct-1",
        product_type=ProductType.DOMESTIC_BOND,
        product_id="bond-1",
        field_id="buy_yield",
        value=normalized,
    )

    assert evidence.value is normalized
    assert evidence.value.source is source
    assert evidence.value.raw_value == "3.250000"
    assert evidence.value.rule_version == "1.0.0"


def test_derived_evidence_binds_inputs_rule_version_and_derived_as_of() -> None:
    """Derived evidence retains the exact Phase 1 derivation value and inputs."""
    from finproof.domain.evidence import DerivedEvidence

    source = _source()
    derived = DerivedValue[int](
        value=254,
        quality_status=QualityStatus.VALID,
        rule_id="bond.not_matured_count",
        rule_version="1.0.0",
        as_of_date=date(2026, 7, 11),
        inputs=(source,),
    )
    evidence = DerivedEvidence[int](
        evidence_id="derived-1",
        product_type=ProductType.DOMESTIC_BOND,
        product_id=None,
        field_id="not_matured_count",
        value=derived,
    )

    assert evidence.value is derived
    assert evidence.value.inputs == (source,)
    assert evidence.value.rule_version == "1.0.0"
    assert evidence.value.as_of_date == date(2026, 7, 11)


def test_evidence_summary_bounds_counts_policy_versions_and_artifact_hash() -> None:
    """Summary evidence is finite and bound to plan, policy, and artifact identity."""
    from finproof.domain.evidence import EvidenceSummary, EvidenceSummaryKind

    summary = EvidenceSummary(
        summary_id="summary-1",
        kind=EvidenceSummaryKind.COUNT,
        included_count=254,
        excluded_count=71,
        evidence_ids=("direct-1", "derived-1"),
        policy_versions=("bond.eligibility@1.0.0",),
        validated_plan_sha256="b" * 64,
        version_bundle_sha256="c" * 64,
        artifact_manifest_hash="d" * 64,
    )
    assert summary.included_count + summary.excluded_count == 325
    assert summary.policy_versions == ("bond.eligibility@1.0.0",)

    invalid = (
        {"included_count": -1},
        {"excluded_count": -1},
        {"evidence_ids": tuple(f"e{i}" for i in range(101))},
        {"policy_versions": tuple(f"p{i}@1.0.0" for i in range(33))},
        {"policy_versions": ("same@1.0.0", "same@1.0.0")},
        {"validated_plan_sha256": "short"},
        {"version_bundle_sha256": "short"},
        {"artifact_manifest_hash": "short"},
    )
    payload = summary.model_dump()
    for mutation in invalid:
        with pytest.raises(ValidationError):
            EvidenceSummary.model_validate(payload | mutation)
