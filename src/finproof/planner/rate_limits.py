"""CLOVA Studio rate-limit response metadata."""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field


class HcxRateLimitSnapshot(BaseModel):
    """Optional request and token limits returned by CLOVA Studio."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    limit_requests: int | None = Field(default=None, ge=0)
    remaining_requests: int | None = Field(default=None, ge=0)
    reset_requests_seconds: float | None = Field(default=None, ge=0)
    limit_tokens: int | None = Field(default=None, ge=0)
    remaining_tokens: int | None = Field(default=None, ge=0)
    reset_tokens_seconds: float | None = Field(default=None, ge=0)

    @classmethod
    def from_headers(cls, headers: Mapping[str, str]) -> "HcxRateLimitSnapshot":
        lowered = {name.lower(): value for name, value in headers.items()}
        return cls(
            limit_requests=_nonnegative_int(lowered.get("x-ratelimit-limit-requests")),
            remaining_requests=_nonnegative_int(lowered.get("x-ratelimit-remaining-requests")),
            reset_requests_seconds=_duration_seconds(lowered.get("x-ratelimit-reset-requests")),
            limit_tokens=_nonnegative_int(lowered.get("x-ratelimit-limit-tokens")),
            remaining_tokens=_nonnegative_int(lowered.get("x-ratelimit-remaining-tokens")),
            reset_tokens_seconds=_duration_seconds(lowered.get("x-ratelimit-reset-tokens")),
        )


def _nonnegative_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _duration_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    normalized = value.removesuffix("s")
    try:
        parsed = float(normalized)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None
