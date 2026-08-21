"""Structured answer contracts for deterministic rendering and verification."""

from pydantic import BaseModel, ConfigDict


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class AnswerRequest(_FrozenModel):
    pass


class AnswerClaim(_FrozenModel):
    pass


class AnswerDraft(_FrozenModel):
    pass


class VerifiedAnswer(_FrozenModel):
    pass


class AnswerResult(_FrozenModel):
    pass
