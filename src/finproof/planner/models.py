"""Typed CLOVA Studio transport models."""

from __future__ import annotations

import json
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from finproof.planner.rate_limits import HcxRateLimitSnapshot

_MAX_CONTEXT_BUDGET = 128_000


class HcxMessage(BaseModel):
    """One chat-completions message."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class HcxRequest(BaseModel):
    """Validated request for CLOVA Studio Chat Completions v3."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    model_name: str
    messages: tuple[HcxMessage, ...] = Field(min_length=1)
    max_completion_tokens: int = Field(ge=1, le=32_768)
    temperature: float = Field(ge=0.0, le=1.0)
    seed: int
    response_schema_json: str | None = None

    @classmethod
    def structured(
        cls,
        *,
        model_name: str,
        messages: tuple[HcxMessage, ...],
        schema: dict[str, Any],
        max_completion_tokens: int,
        temperature: float,
        seed: int,
    ) -> Self:
        """Build an HCX-007 Structured Outputs request."""
        return cls(
            model_name=model_name,
            messages=messages,
            max_completion_tokens=max_completion_tokens,
            temperature=temperature,
            seed=seed,
            response_schema_json=_canonical_json(schema).decode("utf-8"),
        )

    @classmethod
    def strict_json(
        cls,
        *,
        model_name: str,
        messages: tuple[HcxMessage, ...],
        max_completion_tokens: int,
        temperature: float,
        seed: int,
    ) -> Self:
        """Build a strict-JSON prompting request without Structured Outputs."""
        return cls(
            model_name=model_name,
            messages=messages,
            max_completion_tokens=max_completion_tokens,
            temperature=temperature,
            seed=seed,
        )

    @model_validator(mode="after")
    def validate_provider_contract(self) -> Self:
        if not self.model_name.startswith("HCX-"):
            raise ValueError("model_name must start with HCX-")
        if self.response_schema_json is not None:
            if self.model_name != "HCX-007":
                raise ValueError("Structured Outputs requires HCX-007")
            try:
                schema = json.loads(self.response_schema_json)
            except json.JSONDecodeError:
                raise ValueError("response_schema_json must contain JSON") from None
            if not isinstance(schema, dict):
                raise ValueError("response_schema_json must contain an object schema")
        if sum(message.role == "system" for message in self.messages) > 1:
            raise ValueError("messages may contain at most one system message")
        request_bytes = len(_canonical_json(self.to_payload()))
        if request_bytes + self.max_completion_tokens > _MAX_CONTEXT_BUDGET:
            raise ValueError("request exceeds conservative 128000 context budget")
        return self

    def to_payload(self) -> dict[str, Any]:
        """Return the provider's camel-case request payload."""
        payload: dict[str, Any] = {
            "messages": [message.model_dump() for message in self.messages],
            "maxCompletionTokens": self.max_completion_tokens,
            "temperature": self.temperature,
            "seed": self.seed,
        }
        if self.response_schema_json is not None:
            payload["responseFormat"] = {
                "type": "json",
                "schema": json.loads(self.response_schema_json),
            }
        return payload


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


class HcxUsage(BaseModel):
    """Provider-reported token usage."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class HcxResponse(BaseModel):
    """Validated subset of a successful provider response."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    status_code: str
    status_message: str
    message_content: str
    usage: HcxUsage
    rate_limits: HcxRateLimitSnapshot
    created: int | None = None
    seed: int | None = None
    finish_reason: str | None = None
