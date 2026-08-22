"""Structured claim verification."""

from collections.abc import Mapping
from decimal import Decimal
from typing import cast

from finproof.answer.safety import require_safe_claim
from finproof.domain.answers import (
    AnswerClaim,
    AnswerDraft,
    ClaimKind,
    ValueSign,
    VerifiedAnswer,
)
from finproof.domain.evidence import EvidenceBundle
from finproof.domain.query_plan import ProductType

_EvidenceValue = tuple[ProductType | None, str | None, str | None, object]


class ClaimVerifier:
    def verify(self, draft: AnswerDraft, evidence: EvidenceBundle) -> VerifiedAnswer:
        if type(draft) is not AnswerDraft or type(evidence) is not EvidenceBundle:
            raise TypeError("claim verification inputs differ")
        values: dict[str, _EvidenceValue] = (
            {
                item.evidence_id: (
                    item.product_type,
                    item.product_id,
                    item.field_id,
                    item.value.normalized_value,
                )
                for item in evidence.direct
            }
            | {
                item.evidence_id: (
                    item.product_type,
                    item.product_id,
                    item.field_id,
                    item.value.value,
                )
                for item in evidence.derived
            }
            | {
                item.summary_id: (
                    item.product_types[0] if len(item.product_types) == 1 else None,
                    item.product_id,
                    item.metric_id,
                    item.value,
                )
                for item in evidence.summaries
            }
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
            if (claim.kind is ClaimKind.NUMERIC or claim.field_id is not None) and not (
                _matches_value_claim(claim, values)
            ):
                raise ValueError("claim differs from evidence")
        return VerifiedAnswer(text=draft.text, claims=draft.claims)


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
            and (claim.product_type is None or item[0] is claim.product_type)
            and item[1] == claim.product_id
            and item[2] == claim.field_id
            and type(item[3]) is type(claim.value)
            and item[3] == claim.value
        ),
        None,
    )
    if match is None:
        return False
    if claim.sign is None:
        return True
    value = match[3]
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
        item is not None and item[0] is claim.product_type and item[1] == claim.product_id
        for item in referenced
    )
