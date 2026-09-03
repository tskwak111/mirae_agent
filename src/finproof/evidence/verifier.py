"""Structured claim verification."""

from collections.abc import Mapping
from decimal import Decimal
from typing import cast

from finproof.answer.safety import require_safe_claim
from finproof.data.holdings import HoldingCoverageState
from finproof.domain.answers import (
    AnswerClaim,
    AnswerDraft,
    ClaimKind,
    PreparedAnswer,
    ProviderWording,
    ValueSign,
    VerifiedAnswer,
)
from finproof.domain.evidence import EvidenceBundle, EvidenceSummaryValue
from finproof.domain.query_plan import ProductType, ResultGrain
from finproof.service.limits import RequestDeadline


class ClaimVerificationError(ValueError):
    """Provider wording differs from the application-issued answer surface."""


_EvidenceValue = tuple[
    tuple[ProductType, ...],
    tuple[ResultGrain, ...],
    str | None,
    str | None,
    str | None,
    object,
    tuple[EvidenceSummaryValue, ...],
]


class ClaimVerifier:
    def verify(self, draft: AnswerDraft, evidence: EvidenceBundle) -> VerifiedAnswer:
        if type(draft) is not AnswerDraft or type(evidence) is not EvidenceBundle:
            raise TypeError("claim verification inputs differ")
        values = cast(
            dict[str, _EvidenceValue],
            {
                item.evidence_id: (
                    (item.product_type,),
                    (),
                    None,
                    item.product_id,
                    item.field_id,
                    item.value.normalized_value,
                    (),
                )
                for item in evidence.direct
            }
            | {
                item.evidence_id: (
                    (item.product_type,),
                    (),
                    None,
                    item.product_id,
                    item.field_id,
                    item.value.value,
                    (),
                )
                for item in evidence.derived
            }
            | {
                item.summary_id: (
                    item.product_types,
                    item.native_result_grains,
                    item.partition_key,
                    item.product_id,
                    item.metric_id,
                    item.value,
                    item.group_values,
                )
                for item in evidence.summaries
            }
            | {
                item.evidence_id: (
                    (item.owner_product_type,),
                    (),
                    None,
                    item.owner_product_id,
                    "holding_constituent",
                    item.constituent_identifier,
                    (),
                )
                for item in evidence.holding_records
            }
            | {
                item.evidence_id: (
                    (item.owner_product_type,),
                    (),
                    None,
                    item.owner_product_id,
                    "holding_coverage",
                    item.coverage_state.value,
                    (),
                )
                for item in evidence.holding_coverage
            },
        )
        known_evidence_ids = set(values) | {item.summary_id for item in evidence.summaries}
        claimed_limitations = {
            claim.value
            for claim in draft.claims
            if claim.kind is ClaimKind.LIMITATION and type(claim.value) is str
        }
        if not set(evidence.material_policy_limitations) <= claimed_limitations:
            raise ValueError("material policy limitation is missing")
        for claim in draft.claims:
            require_safe_claim(claim)
            if claim.text not in draft.text:
                raise ValueError("claim text differs from answer projection")
            if claim.kind is ClaimKind.NUMERIC and not claim.evidence_ids:
                raise ValueError("numeric claim requires evidence")
            if not set(claim.evidence_ids) <= known_evidence_ids:
                raise ValueError("claim differs from evidence")
            if claim.kind is ClaimKind.CANDIDATE and not _matches_candidate_claim(claim, values):
                raise ValueError("claim differs from evidence")
            if claim.kind is ClaimKind.CANDIDATE or any(
                summary.kind.value == "rank" and summary.summary_id in claim.evidence_ids
                for summary in evidence.summaries
            ):
                _require_holding_claim_evidence(claim, evidence)
            if claim.kind is ClaimKind.LIMITATION and type(claim.value) is str:
                required = _required_limitation_evidence(claim.value, evidence)
                if _requires_limitation_evidence(claim.value) and (
                    not required or not set(required) <= set(claim.evidence_ids)
                ):
                    raise ValueError("holding limitation evidence differs")
            if (claim.kind is ClaimKind.NUMERIC or claim.field_id is not None) and not (
                _matches_value_claim(claim, values)
            ):
                raise ValueError("claim differs from evidence")
        return VerifiedAnswer(text=draft.text, claims=draft.claims)

    def verify_wording(
        self,
        wording: ProviderWording,
        prepared: PreparedAnswer,
        deadline: RequestDeadline,
    ) -> VerifiedAnswer:
        if (
            type(wording) is not ProviderWording
            or type(prepared) is not PreparedAnswer
            or type(deadline) is not RequestDeadline
        ):
            raise TypeError("wording verification inputs differ")
        if deadline.remaining_work_seconds() <= 0:
            raise ClaimVerificationError("wording verification deadline exceeded")
        if wording.presentation not in {"조회 결과입니다.", "확인 결과입니다."}:
            raise ClaimVerificationError("provider presentation is not allowlisted")
        pack = prepared.fact_pack
        return VerifiedAnswer(
            text=f"{wording.presentation}\n{pack.surface_parts[0].text}",
            claims=prepared.claims,
        )


def _matches_value_claim(
    claim: AnswerClaim,
    values: Mapping[str, _EvidenceValue],
) -> bool:
    referenced = tuple(values.get(evidence_id) for evidence_id in claim.evidence_ids)
    if any(item is None for item in referenced):
        return False
    match = next(
        (
            item
            for item in referenced
            if item is not None
            and (not claim.product_types or item[0] == claim.product_types)
            and (not item[1] or item[0] == claim.product_types)
            and (not claim.native_result_grains or item[1] == claim.native_result_grains)
            and (not item[1] or item[1] == claim.native_result_grains)
            and (claim.partition_key is None or item[2] == claim.partition_key)
            and (item[2] is None or item[2] == claim.partition_key)
            and (claim.product_type is None or item[0] == (claim.product_type,))
            and item[3] == claim.product_id
            and item[4] == claim.field_id
            and type(item[5]) is type(claim.value)
            and item[5] == claim.value
            and (not claim.group_values or item[6] == claim.group_values)
            and (not item[6] or item[6] == claim.group_values)
        ),
        None,
    )
    if match is None:
        return False
    if claim.sign is None:
        return True
    value = match[5]
    if type(value) not in {int, Decimal}:
        return False
    number = cast(int | Decimal, value)
    expected = ValueSign.ZERO
    if number > 0:
        expected = ValueSign.POSITIVE
    elif number < 0:
        expected = ValueSign.NEGATIVE
    return claim.sign is expected


def _matches_candidate_claim(
    claim: AnswerClaim,
    values: Mapping[str, _EvidenceValue],
) -> bool:
    referenced = tuple(values.get(evidence_id) for evidence_id in claim.evidence_ids)
    return bool(referenced) and all(
        item is not None and item[0] == (claim.product_type,) and item[3] == claim.product_id
        for item in referenced
    )


def _require_holding_claim_evidence(claim: AnswerClaim, evidence: EvidenceBundle) -> None:
    if claim.product_type is None or claim.product_id is None:
        return
    owner = (claim.product_type, claim.product_id)
    holding_ids = {
        item.evidence_id
        for item in evidence.holding_records
        if (item.owner_product_type, item.owner_product_id) == owner
    }
    if not holding_ids:
        return
    coverage_ids = {
        item.evidence_id
        for item in evidence.holding_coverage
        if (item.owner_product_type, item.owner_product_id) == owner
    }
    owner_ids = {
        item.evidence_id
        for item in evidence.direct
        if (item.product_type, item.product_id, item.field_id)
        == (claim.product_type, claim.product_id, "product_id")
    }
    referenced = set(claim.evidence_ids)
    if (
        not owner_ids
        or not coverage_ids
        or not all(referenced & required for required in (owner_ids, holding_ids, coverage_ids))
    ):
        raise ValueError("holding evidence is incomplete")


def _required_limitation_evidence(
    limitation: str,
    evidence: EvidenceBundle,
) -> tuple[str, ...]:
    if limitation.startswith("해외 ETF/ETN의 1년 수익률"):
        return tuple(
            item.summary_id
            for item in evidence.summaries
            if item.partition_key == "limitation:overseas-return-1y"
        )
    if "상위 10개 부분 자료" in limitation:
        return tuple(
            item.evidence_id
            for item in evidence.holding_coverage
            if item.coverage_state is HoldingCoverageState.PARTIAL_TOP_10
        )
    if "구성종목 자료" in limitation:
        state = (
            "unavailable"
            if "제공되지 않아" in limitation
            else "partial_top_10"
            if "부분 범위" in limitation
            else None
        )
        return tuple(
            item.summary_id
            for item in evidence.summaries
            if item.kind.value == "coverage"
            and item.product_types
            and limitation.startswith(item.product_types[0].value)
            and (
                state is None
                or (item.partition_key is not None and item.partition_key.endswith(f":{state}"))
            )
        )
    return ()


def _requires_limitation_evidence(limitation: str) -> bool:
    return (
        limitation.startswith("해외 ETF/ETN의 1년 수익률")
        or "상위 10개 부분 자료" in limitation
        or "구성종목 자료" in limitation
    )
