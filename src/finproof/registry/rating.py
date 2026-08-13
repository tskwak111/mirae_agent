"""Strict immutable credit-rating registry."""

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Self

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    StrictInt,
    StrictStr,
    ValidationError,
    field_validator,
)

from finproof.core.errors import RatingNotComparableError, RatingRegistryConfigurationError
from finproof.domain.quality import QualityStatus


class _RatingConfig(BaseModel):
    """Strict raw shape accepted at the YAML trust boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    version: Literal["1.0.0"]
    missing_tokens: list[StrictStr]
    ratings: dict[StrictStr, StrictInt]
    aliases: dict[StrictStr, StrictStr]


class RatingResolution(BaseModel):
    """One raw grade resolved against an immutable registry snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    raw_value: str
    normalized_value: str | None
    ordinal: int | None
    quality_status: QualityStatus


class RatingRegistry(BaseModel):
    """Versioned canonical credit ratings and exact aliases."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    version: Literal["1.0.0"]
    missing_tokens: tuple[str, ...]
    ratings: Mapping[str, int]
    aliases: Mapping[str, str]

    @field_validator("ratings", mode="after")
    @classmethod
    def freeze_ratings(cls, value: Mapping[str, int]) -> Mapping[str, int]:
        """Copy and freeze canonical ratings even for direct construction."""
        return MappingProxyType(dict(value))

    @field_validator("aliases", mode="after")
    @classmethod
    def freeze_aliases(cls, value: Mapping[str, str]) -> Mapping[str, str]:
        """Copy and freeze aliases even for direct construction."""
        return MappingProxyType(dict(value))

    @classmethod
    def from_yaml(cls, path: Path) -> Self:
        """Load and validate one rating registry without leaking unsafe details."""
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise RatingRegistryConfigurationError("configuration", source_name=path.name) from exc
        except (UnicodeError, yaml.YAMLError) as exc:
            raise RatingRegistryConfigurationError("configuration") from exc

        try:
            raw_config = _RatingConfig.model_validate(document, strict=True)
        except ValidationError as exc:
            raise RatingRegistryConfigurationError(_validation_error_category(exc)) from exc

        _validate_semantics(raw_config)
        return cls(
            version=raw_config.version,
            missing_tokens=tuple(raw_config.missing_tokens),
            ratings=MappingProxyType(dict(raw_config.ratings)),
            aliases=MappingProxyType(dict(raw_config.aliases)),
        )

    def resolve(self, value: str) -> RatingResolution:
        """Resolve one exact grade after stripping only surrounding whitespace."""
        token = value.strip()
        if token == "":
            return RatingResolution(
                raw_value=value,
                normalized_value=None,
                ordinal=None,
                quality_status=QualityStatus.MISSING_BLANK,
            )
        if token in self.missing_tokens:
            return RatingResolution(
                raw_value=value,
                normalized_value=None,
                ordinal=None,
                quality_status=QualityStatus.MISSING_LITERAL_NULL,
            )

        canonical = self.aliases.get(token, token)
        ordinal = self.ratings.get(canonical)
        if ordinal is None:
            return RatingResolution(
                raw_value=value,
                normalized_value=None,
                ordinal=None,
                quality_status=QualityStatus.OUT_OF_DOMAIN,
            )
        return RatingResolution(
            raw_value=value,
            normalized_value=canonical,
            ordinal=ordinal,
            quality_status=QualityStatus.VALID,
        )

    def resolve_agencies(self, value: str) -> tuple[RatingResolution, ...]:
        """Resolve comma-separated agency grades independently in source order."""
        return tuple(self.resolve(token) for token in value.split(","))

    def compare(self, left: str, right: str) -> int:
        """Compare configured ratings, with smaller ordinals representing strength."""
        left_ordinal = self.resolve(left).ordinal
        right_ordinal = self.resolve(right).ordinal
        if left_ordinal is None or right_ordinal is None:
            raise RatingNotComparableError
        return (left_ordinal > right_ordinal) - (left_ordinal < right_ordinal)


def _validation_error_category(error: ValidationError) -> str:
    """Map validation structure to fixed categories without echoing raw input."""
    first_error = error.errors(include_url=False, include_context=False, include_input=False)[0]
    location = first_error["loc"]
    if not location:
        return "configuration"
    field = location[0]
    if field == "version":
        return "version"
    if field == "missing_tokens":
        return "missing token"
    if field == "ratings":
        return "rating" if "[key]" in location else "ordinal"
    if field == "aliases":
        return "alias"
    return "configuration"


def _validate_semantics(config: _RatingConfig) -> None:
    """Validate relationships that cannot be expressed by raw field types alone."""
    if not config.missing_tokens or len(set(config.missing_tokens)) != len(config.missing_tokens):
        raise RatingRegistryConfigurationError("missing token")
    if not config.ratings:
        raise RatingRegistryConfigurationError("rating")
    if any(not rating for rating in config.ratings):
        raise RatingRegistryConfigurationError("rating")
    if any(ordinal <= 0 for ordinal in config.ratings.values()):
        raise RatingRegistryConfigurationError("ordinal")
    if any(rating in config.missing_tokens for rating in config.ratings):
        raise RatingRegistryConfigurationError("rating")
    if any(
        not alias
        or alias in config.ratings
        or alias in config.missing_tokens
        or target not in config.ratings
        for alias, target in config.aliases.items()
    ):
        raise RatingRegistryConfigurationError("alias")
