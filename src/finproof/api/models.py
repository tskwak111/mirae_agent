"""Frozen organizer-facing HTTP models."""

from collections.abc import Mapping
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from finproof.data.artifacts.hashing import canonical_json_bytes
from finproof.registry.loader import RegistryBundle

_MAX_RESPONSE_BYTES = 96_000


class EvaluationResponse(BaseModel):
    """The exact five-string evaluation response envelope."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    question_id: Annotated[str, Field(min_length=1, max_length=200)]
    question: Annotated[str, Field(min_length=1, max_length=4_000)]
    retrieved_context: Annotated[str, Field(min_length=1)]
    think_trace: Annotated[str, Field(min_length=1)]
    answer: Annotated[str, Field(min_length=1, max_length=12_000)]

    @field_validator("retrieved_context", "think_trace")
    @classmethod
    def _validate_utf8_limits(cls, value: str, info: ValidationInfo) -> str:
        limits = RegistryBundle.from_package().answers.document["limits"]
        assert isinstance(limits, Mapping)
        key = "max_context_bytes" if info.field_name == "retrieved_context" else "max_trace_bytes"
        limit = limits.get(key, 16_000)
        if type(limit) is not int or len(value.encode()) > limit:
            raise ValueError(f"{info.field_name} exceeds configured bound")
        return value

    @model_validator(mode="after")
    def _validate_response_bytes(self) -> Self:
        if (
            len(canonical_json_bytes(self.model_dump(mode="json"), terminal_newline=False))
            > _MAX_RESPONSE_BYTES
        ):
            raise ValueError("response exceeds configured bound")
        return self
