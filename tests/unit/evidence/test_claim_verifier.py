"""Focused structured-claim verification contracts."""

from decimal import Decimal

import pytest


def test_claim_verifier_rejects_numeric_claim_without_evidence() -> None:
    from finproof.domain.answers import AnswerClaim, AnswerDraft, ClaimKind
    from finproof.domain.evidence import EvidenceBundle
    from finproof.evidence import ClaimVerifier

    draft = AnswerDraft(
        text="매수수익률은 2.25%입니다.",
        claims=(
            AnswerClaim(
                claim_id="claim:yield",
                kind=ClaimKind.NUMERIC,
                text="매수수익률은 2.25%입니다.",
                product_id="KR0000000001",
                field_id="buy_yield",
                value=Decimal("2.25"),
                evidence_ids=(),
            ),
        ),
    )

    with pytest.raises(ValueError, match="numeric claim requires evidence"):
        ClaimVerifier().verify(
            draft,
            EvidenceBundle(direct=(), derived=(), summaries=(), material_policy_limitations=()),
        )


@pytest.mark.parametrize(
    "change",
    [
        {"product_id": "KR9999999999"},
        {"value": Decimal("2.26")},
        {"sign": "negative"},
        {"kind": "text", "value": "2.25"},
        {"kind": "text", "evidence_ids": ("evidence:missing",)},
    ],
)
def test_claim_verifier_rejects_wrong_product_changed_decimal_and_false_sign_family(
    change: dict[str, object],
) -> None:
    from tests.unit.evidence.test_builder import _bond_evidence_session

    from finproof.domain.answers import AnswerClaim, AnswerDraft, ClaimKind, ValueSign
    from finproof.domain.evidence import EvidenceBundle
    from finproof.domain.query_plan import ProductType
    from finproof.evidence import ClaimVerifier
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, _ = _bond_evidence_session()
    record = EvidenceRepository(session).fetch_final_record_evidence(
        (
            EvidenceLookup(
                product_type=ProductType.DOMESTIC_BOND,
                product_ids=("KR0000000001",),
                field_ids=("buy_yield",),
            ),
        )
    )[0]
    evidence = EvidenceBundle(
        direct=record.direct,
        derived=(),
        summaries=(),
        material_policy_limitations=(),
    )
    valid = AnswerClaim(
        claim_id="claim:yield",
        kind=ClaimKind.NUMERIC,
        text="매수수익률은 2.25%입니다.",
        product_id="KR0000000001",
        field_id="buy_yield",
        value=Decimal("2.25"),
        evidence_ids=("domestic_bond:KR0000000001:buy_yield",),
        sign=ValueSign.POSITIVE,
    )

    with pytest.raises(ValueError, match="claim differs from evidence"):
        ClaimVerifier().verify(
            AnswerDraft(
                text=valid.text,
                claims=(valid.model_copy(update=change),),
            ),
            evidence,
        )
    session._close()


def test_claim_verifier_rejects_unsupported_recommendation_claim() -> None:
    from finproof.domain.answers import AnswerClaim, AnswerDraft, ClaimKind
    from finproof.domain.evidence import EvidenceBundle
    from finproof.evidence import ClaimVerifier

    draft = AnswerDraft(
        text="이 상품을 반드시 매수하세요.",
        claims=(
            AnswerClaim(
                claim_id="claim:recommendation",
                kind=ClaimKind.RECOMMENDATION,
                text="이 상품을 반드시 매수하세요.",
                product_id="KR0000000001",
            ),
        ),
    )

    with pytest.raises(ValueError, match="recommendation claim is unsupported"):
        ClaimVerifier().verify(
            draft,
            EvidenceBundle(direct=(), derived=(), summaries=(), material_policy_limitations=()),
        )


def test_claim_verifier_rejects_candidate_with_false_native_identity() -> None:
    from tests.unit.evidence.test_builder import _bond_evidence_session

    from finproof.domain.answers import AnswerClaim, AnswerDraft, ClaimKind
    from finproof.domain.evidence import EvidenceBundle
    from finproof.domain.query_plan import ProductType
    from finproof.evidence import ClaimVerifier
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, _ = _bond_evidence_session()
    direct = (
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
        .direct
    )
    text = "조건에 부합하는 후보: domestic_etf KR9999999999"
    draft = AnswerDraft(
        text=text,
        claims=(
            AnswerClaim(
                claim_id="claim:false-candidate",
                kind=ClaimKind.CANDIDATE,
                text=text,
                product_type=ProductType.DOMESTIC_ETF,
                product_id="KR9999999999",
                evidence_ids=(direct[0].evidence_id,),
            ),
        ),
    )

    with pytest.raises(ValueError, match="claim differs from evidence"):
        ClaimVerifier().verify(
            draft,
            EvidenceBundle(
                direct=direct,
                derived=(),
                summaries=(),
                material_policy_limitations=(),
            ),
        )
    session._close()


def test_claim_verifier_rejects_false_aggregate_group_partition_and_native_identity() -> None:
    from finproof.domain.answers import AnswerClaim, AnswerDraft, ClaimKind
    from finproof.domain.evidence import (
        EvidenceBundle,
        EvidenceSummary,
        EvidenceSummaryKind,
        EvidenceSummaryValue,
    )
    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.evidence import ClaimVerifier

    summary = EvidenceSummary(
        summary_id="summary:aggregate:0",
        kind=EvidenceSummaryKind.AGGREGATE,
        included_count=2,
        excluded_count=0,
        evidence_ids=(),
        policy_versions=("buy_yield:avg",),
        validated_plan_sha256="a" * 64,
        version_bundle_sha256="b" * 64,
        artifact_manifest_hash="c" * 64,
        product_types=(ProductType.DOMESTIC_BOND,),
        native_result_grains=(ResultGrain.INSTRUMENT,),
        partition_key="yield:KRW",
        metric_id="buy_yield",
        value=Decimal("2.10"),
        group_values=(EvidenceSummaryValue(field_id="currency", value="KRW"),),
    )
    false_text = "domestic_bond/instrument [yield:USD] currency=USD buy_yield 평균: 2.10"
    false_claim = AnswerClaim(
        claim_id="claim:false-aggregate",
        kind=ClaimKind.NUMERIC,
        text=false_text,
        product_types=(ProductType.DOMESTIC_BOND,),
        native_result_grains=(ResultGrain.INSTRUMENT,),
        partition_key="yield:USD",
        field_id="buy_yield",
        value=Decimal("2.10"),
        group_values=(EvidenceSummaryValue(field_id="currency", value="USD"),),
        evidence_ids=(summary.summary_id,),
    )

    with pytest.raises(ValueError, match="claim differs from evidence"):
        ClaimVerifier().verify(
            AnswerDraft(text=false_text, claims=(false_claim,)),
            EvidenceBundle(
                direct=(),
                derived=(),
                summaries=(summary,),
                material_policy_limitations=(),
            ),
        )

    omitted_text = "buy_yield 평균: 2.10"
    omitted_claim = false_claim.model_copy(
        update={
            "text": omitted_text,
            "product_types": (),
            "native_result_grains": (),
            "partition_key": None,
            "group_values": (),
        }
    )
    with pytest.raises(ValueError, match="claim differs from evidence"):
        ClaimVerifier().verify(
            AnswerDraft(text=omitted_text, claims=(omitted_claim,)),
            EvidenceBundle(
                direct=(),
                derived=(),
                summaries=(summary,),
                material_policy_limitations=(),
            ),
        )


def test_claim_verifier_rejects_claim_not_projected_in_answer_text() -> None:
    from finproof.domain.answers import AnswerClaim, AnswerDraft, ClaimKind
    from finproof.domain.evidence import EvidenceBundle
    from finproof.evidence import ClaimVerifier

    draft = AnswerDraft(
        text="표시된 본문",
        claims=(
            AnswerClaim(
                claim_id="claim:hidden",
                kind=ClaimKind.LIMITATION,
                text="숨은 주장",
                value="숨은 주장",
            ),
        ),
    )

    with pytest.raises(ValueError, match="claim text differs from answer projection"):
        ClaimVerifier().verify(
            draft,
            EvidenceBundle(direct=(), derived=(), summaries=(), material_policy_limitations=()),
        )


def test_claim_verifier_requires_every_material_policy_limitation() -> None:
    from finproof.domain.answers import AnswerClaim, AnswerDraft, ClaimKind
    from finproof.domain.evidence import EvidenceBundle
    from finproof.evidence import ClaimVerifier

    limitations = (
        "2026-07-11 제공 스냅샷 기준",
        "통화별로 결과를 분리했습니다.",
    )
    evidence = EvidenceBundle(
        direct=(),
        derived=(),
        summaries=(),
        material_policy_limitations=limitations,
    )
    claims = tuple(
        AnswerClaim(
            claim_id=f"claim:limitation:{index}",
            kind=ClaimKind.LIMITATION,
            text=limitation,
            value=limitation,
        )
        for index, limitation in enumerate(limitations)
    )

    with pytest.raises(ValueError, match="material policy limitation is missing"):
        ClaimVerifier().verify(AnswerDraft(text=limitations[0], claims=claims[:1]), evidence)

    verified = ClaimVerifier().verify(
        AnswerDraft(text=" ".join(limitations), claims=claims), evidence
    )
    assert verified.claims == claims


def test_holding_candidate_requires_owner_holding_and_exact_coverage_evidence() -> None:
    from datetime import date
    from pathlib import PurePosixPath
    from typing import cast

    from finproof.data.holdings import HoldingCoverageState
    from finproof.domain.answers import AnswerClaim, AnswerDraft, ClaimKind
    from finproof.domain.evidence import (
        DirectEvidence,
        EvidenceBundle,
        HoldingCoverageEvidenceRef,
        HoldingRecordEvidenceRef,
    )
    from finproof.domain.locators import SourceCellLocator
    from finproof.domain.quality import QualityStatus
    from finproof.domain.query_plan import ProductType
    from finproof.domain.values import NormalizedValue
    from finproof.evidence import ClaimVerifier

    owner = cast(
        DirectEvidence[object],
        DirectEvidence[str](
            evidence_id="owner:product-id",
            product_type=ProductType.DOMESTIC_ETF,
            product_id="ETF-1",
            field_id="product_id",
            value=NormalizedValue[str](
                raw_value="ETF-1",
                normalized_value="ETF-1",
                quality_status=QualityStatus.VALID,
                rule_id="product_id",
                rule_version="1.0.0",
                source=SourceCellLocator(
                    source_table="PREF01N001",
                    source_file=PurePosixPath("domestic.xlsx"),
                    source_sheet="datarows",
                    source_row_number=2,
                    source_column_name="product_id",
                    source_column_number=1,
                    source_column_letter="A",
                    source_checksum="a" * 64,
                    source_snapshot_date=date(2026, 8, 24),
                    source_applicable_date=date(2026, 8, 22),
                ),
            ),
        ),
    )
    holding = HoldingRecordEvidenceRef(
        evidence_id="holding:1",
        owner_product_type=ProductType.DOMESTIC_ETF,
        owner_product_id="ETF-1",
        generation_id="generation-1",
        constituent_identifier="KR7005930003",
        constituent_identifier_type="ISIN",
        display_name="삼성전자",
        source_kind="krx_etf_pdf",
        source_as_of_date=date(2026, 8, 22),
        source_row_ordinal=1,
    )
    coverage = HoldingCoverageEvidenceRef(
        evidence_id="coverage:1",
        owner_product_type=ProductType.DOMESTIC_ETF,
        owner_product_id="ETF-1",
        coverage_state=HoldingCoverageState.PARTIAL_TOP_10,
        source_generation_id="generation-1",
        observed_holding_count=1,
        limitation_code="partial_top_10_only",
        source_kind="krx_etf_pdf",
        source_as_of_date=date(2026, 8, 22),
    )
    text = "조건에 부합하는 후보: domestic_etf ETF-1"
    claim = AnswerClaim(
        claim_id="candidate:holding",
        kind=ClaimKind.CANDIDATE,
        text=text,
        product_type=ProductType.DOMESTIC_ETF,
        product_id="ETF-1",
        evidence_ids=(owner.evidence_id, holding.evidence_id, coverage.evidence_id),
    )
    evidence = EvidenceBundle(
        direct=(owner,),
        derived=(),
        summaries=(),
        material_policy_limitations=(),
        holding_records=(holding,),
        holding_coverage=(coverage,),
    )

    assert ClaimVerifier().verify(AnswerDraft(text=text, claims=(claim,)), evidence).claims
    with pytest.raises(ValueError, match="holding evidence"):
        ClaimVerifier().verify(
            AnswerDraft(
                text=text,
                claims=(claim.model_copy(update={"evidence_ids": (owner.evidence_id,)}),),
            ),
            evidence,
        )
