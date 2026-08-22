"""Structured answer contracts for deterministic rendering and verification."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from finproof.domain.execution import ExecutionTrace
from finproof.domain.query_plan import ProductType


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class ClaimKind(StrEnum):
    NUMERIC = "numeric"
    TEXT = "text"
    LIMITATION = "limitation"
    CANDIDATE = "candidate"
    RECOMMENDATION = "recommendation"


class ValueSign(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    ZERO = "zero"


class AnswerRequest(_FrozenModel):
    question_id: Annotated[str, Field(min_length=1, max_length=200)]
    question: Annotated[str, Field(min_length=1, max_length=4_000)]


class AnswerClaim(_FrozenModel):
    claim_id: Annotated[str, Field(min_length=1, max_length=200)]
    kind: ClaimKind
    text: Annotated[str, Field(min_length=1, max_length=2_000)]
    product_type: ProductType | None = None
    product_id: Annotated[str, Field(min_length=1, max_length=300)] | None = None
    field_id: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    value: Decimal | int | str | date | bool | None = None
    evidence_ids: Annotated[tuple[str, ...], Field(max_length=100)] = ()
    sign: ValueSign | None = None


class AnswerDraft(_FrozenModel):
    text: Annotated[str, Field(min_length=1, max_length=12_000)]
    claims: Annotated[tuple[AnswerClaim, ...], Field(max_length=300)]


class VerifiedAnswer(_FrozenModel):
    text: Annotated[str, Field(min_length=1, max_length=12_000)]
    claims: Annotated[tuple[AnswerClaim, ...], Field(max_length=300)]


class AnswerResult(_FrozenModel):
    answer: VerifiedAnswer
    retrieved_context: str
    trace: ExecutionTrace
