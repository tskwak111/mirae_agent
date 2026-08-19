"""CP6 complete source-audit typestate and report contracts."""

# mypy: disable-error-code="func-returns-value,no-untyped-call,no-untyped-def"

from datetime import date
from typing import Literal


def _silver_observations():
    from finproof.data.artifacts.reports import (
        BronzeSourceAuditObservations,
        ExpectedObservedCount,
        NamedExpectedObservedCount,
        SourceTableAudit,
    )

    source_names: tuple[Literal["PRBD01N001", "PREF01N001", "PREF02N001", "PRFD01N001"], ...] = (
        "PRBD01N001",
        "PREF01N001",
        "PREF02N001",
        "PRFD01N001",
    )
    source_tables = tuple(
        SourceTableAudit(
            source_table=name,
            expected_rows=1,
            observed_rows=1,
            expected_columns=1,
            observed_columns=1,
            expected_cells=1,
            observed_cells=1,
        )
        for name in source_names
    )
    bronze = BronzeSourceAuditObservations.from_bronze(
        source_snapshot_date=date(2026, 7, 11),
        source_manifest_sha256="a" * 64,
        schema_catalog_sha256="b" * 64,
        source_tables=source_tables,
    )
    silver_names: tuple[
        Literal[
            "bond_instrument",
            "domestic_listed_product",
            "overseas_listed_product",
            "fund_item",
            "fund_item_attribute",
        ],
        ...,
    ] = (
        "bond_instrument",
        "domestic_listed_product",
        "overseas_listed_product",
        "fund_item",
        "fund_item_attribute",
    )
    return bronze.with_silver(
        tuple(
            NamedExpectedObservedCount(name=name, expected=1, observed=1) for name in silver_names
        ),
        ExpectedObservedCount(expected=0, observed=0),
    )


def _verified_links():
    from finproof.data.artifacts.links import _issue_exact_evidence_observations
    from finproof.data.artifacts.reports import (
        ExpectedObservedCount,
        ExpectedObservedSha256,
    )

    return _issue_exact_evidence_observations(
        owner=object(),
        exact_links=ExpectedObservedCount(expected=1, observed=1),
        exact_link_evidence=ExpectedObservedCount(expected=3, observed=3),
        exact_link_pair_sha256=ExpectedObservedSha256(
            expected="c" * 64,
            observed="c" * 64,
        ),
        matched_bronze_cells=3,
        matched_left_records=1,
        matched_right_records=1,
        max_relation_batch_rows=3,
    )


def test_with_links_preserves_silver_prefix_and_uses_owned_expected_observed_members() -> None:
    from finproof.data.artifacts.reports import CompleteSourceAuditObservations

    silver = _silver_observations()
    verified = _verified_links()

    complete = silver.with_links(verified=verified)

    assert type(complete) is CompleteSourceAuditObservations
    assert complete.source_tables is silver.source_tables
    assert complete.silver_tables is silver.silver_tables
    assert complete.quarantine_source_rows is silver.quarantine_source_rows
    assert complete.exact_links is verified.exact_links
    assert complete.exact_link_evidence is verified.exact_link_evidence
    assert complete.exact_link_pair_sha256 is verified.exact_link_pair_sha256


def test_complete_observations_reject_wrong_phase_copy_forge_reuse_and_unowned_link_facts() -> None:
    from copy import copy

    import pytest

    from finproof.data.artifacts.reports import (
        CompleteSourceAuditObservations,
        require_complete_source_audit_observations,
    )

    silver = _silver_observations()
    verified = _verified_links()
    complete = silver.with_links(verified=verified)

    assert require_complete_source_audit_observations(complete) is None
    with pytest.raises((TypeError, ValueError)):
        require_complete_source_audit_observations(silver)
    with pytest.raises((TypeError, ValueError)):
        silver.with_links(verified=verified)
    with pytest.raises((TypeError, ValueError)):
        require_complete_source_audit_observations(copy(complete))
    forged = object.__new__(CompleteSourceAuditObservations)
    for name in complete.__dataclass_fields__:
        object.__setattr__(forged, name, getattr(complete, name))
    with pytest.raises((TypeError, ValueError)):
        require_complete_source_audit_observations(forged)
    object.__setattr__(verified, "matched_bronze_cells", 2)
    with pytest.raises((TypeError, ValueError)):
        require_complete_source_audit_observations(complete)


def test_source_audit_report_factory_accepts_only_exact_complete_observations() -> None:
    import pytest

    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
    )
    from finproof.data.artifacts.reports import SourceAuditReport

    payload = dict(_EXPECTED_ARTIFACT_CONFIG)
    payload["sources"] = tuple(
        {**source, "rows": 1, "columns": 1, "cells": 1}
        for source in _EXPECTED_ARTIFACT_CONFIG["sources"]
    )
    payload["silver_counts"] = {
        "bond_instrument": 1,
        "domestic_listed_product": 1,
        "overseas_listed_product": 1,
        "fund_item": 1,
        "fund_item_attribute": 1,
    }
    payload["quarantine_source_rows"] = 0
    payload["exact_links"] = {
        "links": 1,
        "evidence": 3,
        "pair_sha256": "c" * 64,
    }
    config = ArtifactBuildConfig.model_validate(payload)
    silver = _silver_observations()
    complete = silver.with_links(verified=_verified_links())

    report = SourceAuditReport.from_complete_observations(
        config=config,
        observations=complete,
    )

    assert report.report_id == "source_audit"
    assert report.source_tables is complete.source_tables
    assert report.silver_tables is complete.silver_tables
    assert report.exact_links is complete.exact_links
    assert report.exact_link_evidence is complete.exact_link_evidence
    assert report.exact_link_pair_sha256 is complete.exact_link_pair_sha256
    with pytest.raises((TypeError, ValueError)):
        SourceAuditReport.from_complete_observations(
            config=config,
            observations=silver,
        )
    object.__setattr__(complete.exact_links, "observed", 2)
    with pytest.raises((TypeError, ValueError)):
        SourceAuditReport.from_complete_observations(
            config=config,
            observations=complete,
        )
