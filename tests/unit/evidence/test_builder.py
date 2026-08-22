"""Focused evidence construction contracts."""

from datetime import date
from pathlib import Path
from typing import Self

import pytest
from tests.helpers.source_rows import source_row
from tests.integration.query.test_executor import _session

from finproof.data.artifacts.serialization import canonical_record_json
from finproof.data.normalization.bonds import normalize_bond
from finproof.domain.bonds import BondInstrument
from finproof.registry.rating import RatingRegistry
from finproof.runtime.session import RuntimeArtifactSession


def test_evidence_and_answer_skeleton_exposes_exact_interfaces() -> None:
    from finproof.answer import AnswerRenderer
    from finproof.evidence import ClaimVerifier, EvidenceBuilder
    from finproof.service import AnswerService
    from finproof.storage.repositories.evidence import EvidenceRepository

    assert all(
        isinstance(value, type)
        for value in (
            EvidenceRepository,
            EvidenceBuilder,
            ClaimVerifier,
            AnswerRenderer,
            AnswerService,
        )
    )


def test_final_product_claims_use_complete_source_cell_lineage() -> None:
    from finproof.domain.query_plan import ProductType
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, record = _bond_evidence_session()
    evidence = (
        EvidenceRepository(session)
        .fetch_final_record_evidence(
            (
                EvidenceLookup(
                    product_type=ProductType.DOMESTIC_BOND,
                    product_ids=("KR0000000001",),
                    field_ids=("buy_yield",),
                ),
            )
        )[0]
        .direct[0]
    )

    assert evidence.value == record.buy_yield
    assert evidence.value.source.source_table == "PRBD01N001"
    assert evidence.value.source.source_row_number == 77
    assert evidence.value.source.source_column_name == "BUY_YIELD"
    assert evidence.value.source.source_column_letter
    assert evidence.value.source.source_checksum
    assert evidence.value.source.source_snapshot_date == date(2026, 7, 11)
    session._close()


def test_derived_claims_bind_formula_inputs_rule_and_as_of() -> None:
    from finproof.domain.query_plan import ProductType
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, record = _bond_evidence_session()
    evidence = (
        EvidenceRepository(session)
        .fetch_final_record_evidence(
            (
                EvidenceLookup(
                    product_type=ProductType.DOMESTIC_BOND,
                    product_ids=("KR0000000001",),
                    field_ids=("remaining_days_at_as_of",),
                ),
            )
        )[0]
        .derived[0]
    )

    assert evidence.value == record.remaining_days_at_as_of
    assert evidence.value.rule_id == "bond.remaining_days_at_as_of"
    assert evidence.value.rule_version
    assert evidence.value.as_of_date == date(2026, 7, 11)
    assert tuple(item.source_column_name for item in evidence.value.inputs) == ("MAT_DT",)
    session._close()


def test_count_exclusion_rank_tie_partition_and_aggregate_summaries_are_bounded() -> None:
    from pydantic import ValidationError

    from finproof.domain.evidence import EvidenceSummary, EvidenceSummaryKind

    summaries = tuple(
        EvidenceSummary(
            summary_id=f"summary:{kind.value}",
            kind=kind,
            included_count=254,
            excluded_count=71,
            evidence_ids=("evidence:1",),
            policy_versions=("policy:1.0.0",),
            validated_plan_sha256="a" * 64,
            version_bundle_sha256="b" * 64,
            artifact_manifest_hash="c" * 64,
        )
        for kind in EvidenceSummaryKind
    )

    assert tuple(summary.kind for summary in summaries) == tuple(EvidenceSummaryKind)
    assert all(summary.included_count + summary.excluded_count == 325 for summary in summaries)
    with pytest.raises(ValidationError):
        EvidenceSummary.model_validate(
            {
                **summaries[0].model_dump(),
                "evidence_ids": tuple(f"evidence:{index}" for index in range(101)),
            }
        )


def test_context_serialization_is_stable_json_safe_size_bounded_and_contains_no_local_runtime_path() -> (  # noqa: E501
    None
):
    import json

    from finproof.domain.evidence import EvidenceBundle
    from finproof.domain.query_plan import ProductType
    from finproof.evidence.serializer import serialize_evidence_context
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, _ = _bond_evidence_session()
    record = EvidenceRepository(session).fetch_final_record_evidence(
        (
            EvidenceLookup(
                product_type=ProductType.DOMESTIC_BOND,
                product_ids=("KR0000000001",),
                field_ids=("buy_yield", "remaining_days_at_as_of"),
            ),
        )
    )[0]
    bundle = EvidenceBundle(
        direct=record.direct,
        derived=record.derived,
        summaries=(),
        material_policy_limitations=("2026-07-11 제공 스냅샷 기준",),
    )

    first = serialize_evidence_context(bundle)
    second = serialize_evidence_context(bundle)

    assert first == second
    assert json.loads(first)["direct"][0]["value"]["normalized_value"] == "2.25"
    assert len(first.encode()) <= 24_000
    assert "/Users/example/runtime/artifacts.duckdb" not in first
    with pytest.raises(ValueError, match="local path"):
        serialize_evidence_context(
            bundle.model_copy(
                update={"material_policy_limitations": ("/Users/example/runtime/artifacts.duckdb",)}
            )
        )
    session._close()


def _bond_evidence_session() -> tuple[RuntimeArtifactSession, BondInstrument]:
    record = normalize_bond(
        source_row(
            "PRBD01N001",
            {
                "PD_NO": "KR0000000001",
                "BUY_YIELD": "2.25",
                "BUYABLE_QUANTITY": "10",
                "MAT_DT": "20270711",
            },
            excel_row=77,
        ),
        date(2026, 7, 11),
        RatingRegistry.from_yaml(Path(__file__).resolve().parents[3] / "config/rating_scale.yaml"),
    ).record
    assert isinstance(record, BondInstrument)
    bond = record

    class Connection:
        def execute(self, _sql: str, _parameters: object) -> Self:
            return self

        def fetchall(self) -> tuple[tuple[object, ...], ...]:
            return (("KR0000000001", canonical_record_json(bond)),)

        def close(self) -> None: ...

    return _session(Connection()), bond  # type: ignore[arg-type]
