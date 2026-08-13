"""Strict immutable credit-rating registry."""

from collections.abc import Hashable, Mapping
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
    field_serializer,
    field_validator,
    model_validator,
)
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

from finproof.core.errors import RatingNotComparableError, RatingRegistryConfigurationError
from finproof.domain.quality import QualityStatus


class _RatingConfig(BaseModel):
    """Strict raw shape accepted at the YAML trust boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    version: Literal["1.0.0"]
    missing_tokens: list[StrictStr]
    ratings: dict[StrictStr, StrictInt]
    aliases: dict[StrictStr, StrictStr]


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """A task-local SafeLoader that rejects duplicate keys at every mapping level."""

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[object, object]:
        self.flatten_mapping(node)
        mapping: dict[object, object] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, Hashable):
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found unhashable key",
                    key_node.start_mark,
                )
            if key in mapping:
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found duplicate key",
                    key_node.start_mark,
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


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

    @model_validator(mode="after")
    def validate_semantics(self) -> Self:
        """Reject invalid registry state at every public construction boundary."""
        category = _semantic_error_category(
            self.missing_tokens,
            self.ratings,
            self.aliases,
        )
        if category is not None:
            raise ValueError(f"invalid rating registry {category}")
        return self

    @field_serializer("ratings")
    def serialize_ratings(self, value: Mapping[str, int]) -> dict[str, int]:
        """Serialize the immutable mapping as an ordinary JSON object."""
        return dict(value)

    @field_serializer("aliases")
    def serialize_aliases(self, value: Mapping[str, str]) -> dict[str, str]:
        """Serialize the immutable mapping as an ordinary JSON object."""
        return dict(value)

    @classmethod
    def from_yaml(cls, path: Path) -> Self:
        """Load and validate one rating registry without leaking unsafe details."""
        try:
            document = _load_unique_key_yaml(path.read_text(encoding="utf-8"))
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
        if first_error["type"] == "missing":
            return "configuration"
        return "rating" if len(location) == 1 or "[key]" in location else "ordinal"
    if field == "aliases":
        return "alias"
    return "configuration"


def _load_unique_key_yaml(raw_yaml: str) -> object:
    """Safely construct YAML while rejecting duplicate keys without global mutation."""
    loader = _UniqueKeySafeLoader(raw_yaml)
    try:
        return loader.get_single_data()
    finally:
        loader.dispose()  # type: ignore[no-untyped-call]  # types-PyYAML omits this signature


def _validate_semantics(config: _RatingConfig) -> None:
    """Validate relationships that cannot be expressed by raw field types alone."""
    category = _semantic_error_category(
        tuple(config.missing_tokens),
        config.ratings,
        config.aliases,
    )
    if category is not None:
        raise RatingRegistryConfigurationError(category)


def _semantic_error_category(
    missing_tokens: tuple[str, ...],
    ratings: Mapping[str, int],
    aliases: Mapping[str, str],
) -> str | None:
    """Return the first fixed semantic-error category, or ``None`` when valid."""
    if (
        not missing_tokens
        or len(set(missing_tokens)) != len(missing_tokens)
        or any(token != token.strip() for token in missing_tokens)
    ):
        return "missing token"
    if (
        not ratings
        or any(not rating or rating != rating.strip() for rating in ratings)
        or any(rating in missing_tokens for rating in ratings)
    ):
        return "rating"
    if any(ordinal <= 0 for ordinal in ratings.values()):
        return "ordinal"
    if any(
        not alias
        or alias != alias.strip()
        or target != target.strip()
        or alias in ratings
        or alias in missing_tokens
        or target not in ratings
        for alias, target in aliases.items()
    ):
        return "alias"
    return None
