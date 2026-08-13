from collections.abc import Mapping
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from finproof.core.errors import RatingNotComparableError, RatingRegistryConfigurationError
from finproof.domain.quality import QualityStatus
from finproof.registry.rating import RatingRegistry, RatingResolution

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def registry() -> RatingRegistry:
    return RatingRegistry.from_yaml(ROOT / "config/rating_scale.yaml")


def test_official_rating_registry_resolves_canonical_alias_and_same_ordinal(
    registry: RatingRegistry,
) -> None:
    assert registry.resolve(" AAA ").normalized_value == "AAA"
    alias = registry.resolve(" AA０ ")  # noqa: RUF001 - official full-width alias
    assert alias.normalized_value == "AA0"
    assert alias.ordinal == 3
    assert alias.quality_status is QualityStatus.VALID
    assert registry.compare("AAA", "AA-") == -1
    assert registry.compare("AA-", "AAA") == 1
    assert registry.compare("AA", "AA0") == 0


def test_public_rating_models_are_explicitly_frozen_forbid_and_strict() -> None:
    for model in (RatingResolution, RatingRegistry):
        assert model.model_config["frozen"] is True
        assert model.model_config["extra"] == "forbid"
        assert model.model_config["strict"] is True


@pytest.mark.parametrize("raw", ["", "  ", "NULL", "N/A", "NR", "Not Rated", "무등급"])
def test_missing_or_unrated_grades_never_compare(registry: RatingRegistry, raw: str) -> None:
    resolution = registry.resolve(raw)
    expected = (
        QualityStatus.MISSING_BLANK if raw.strip() == "" else QualityStatus.MISSING_LITERAL_NULL
    )
    assert resolution.normalized_value is None
    assert resolution.ordinal is None
    assert resolution.quality_status is expected
    with pytest.raises(RatingNotComparableError, match="not comparable"):
        registry.compare(raw, "AA-")


@pytest.mark.parametrize("raw", ["C0", "CC0", "AA1", "aaa"])
def test_unregistered_grades_stay_out_of_domain_and_noncomparable(
    registry: RatingRegistry, raw: str
) -> None:
    resolution = registry.resolve(raw)
    assert resolution.raw_value == raw
    assert resolution.normalized_value is None
    assert resolution.ordinal is None
    assert resolution.quality_status is QualityStatus.OUT_OF_DOMAIN
    with pytest.raises(RatingNotComparableError, match="not comparable"):
        registry.compare(raw, "AA-")


def test_agency_tokens_are_resolved_independently_in_source_order(
    registry: RatingRegistry,
) -> None:
    resolutions = registry.resolve_agencies(" AA, AA0 , C0, NR ")
    assert tuple(item.normalized_value for item in resolutions) == (
        "AA",
        "AA0",
        None,
        None,
    )
    assert tuple(item.quality_status for item in resolutions) == (
        QualityStatus.VALID,
        QualityStatus.VALID,
        QualityStatus.OUT_OF_DOMAIN,
        QualityStatus.MISSING_LITERAL_NULL,
    )


def _write_rating_yaml(path: Path, document: Mapping[str, object]) -> None:
    path.write_text(yaml.safe_dump(dict(document), allow_unicode=True), encoding="utf-8")


def test_registry_state_is_deeply_immutable(registry: RatingRegistry) -> None:
    with pytest.raises(TypeError):
        registry.ratings["AAA"] = 99  # type: ignore[index]
    with pytest.raises(TypeError):
        registry.aliases["AA０"] = "AAA"  # type: ignore[index]  # noqa: RUF001
    with pytest.raises(AttributeError):
        registry.missing_tokens.append("UNKNOWN")  # type: ignore[attr-defined]


def test_registry_json_round_trip_uses_plain_objects_and_restores_immutability(
    registry: RatingRegistry,
) -> None:
    dumped = registry.model_dump(mode="json")
    assert type(dumped["ratings"]) is dict
    assert type(dumped["aliases"]) is dict
    assert dumped["ratings"] == dict(registry.ratings)
    assert dumped["aliases"] == dict(registry.aliases)

    encoded = registry.model_dump_json()
    restored = RatingRegistry.model_validate_json(encoded)
    assert restored == registry
    with pytest.raises(TypeError):
        restored.ratings["AAA"] = 99  # type: ignore[index]
    with pytest.raises(TypeError):
        restored.aliases["ALT"] = "AAA"  # type: ignore[index]


@pytest.mark.parametrize(
    ("missing_tokens", "ratings", "aliases"),
    [
        ((), {"AAA": 1}, {}),
        (("", ""), {"AAA": 1}, {}),
        (("", " NR "), {"AAA": 1}, {}),
        (("",), {}, {}),
        (("",), {"": 1}, {}),
        (("",), {" AAA": 1}, {}),
        (("",), {"AAA": 0}, {}),
        (("",), {"AAA": 1}, {"ALT": "AA0"}),
        (("",), {"AAA": 1}, {"AAA": "AAA"}),
        (("", "NR"), {"AAA": 1}, {"NR": "AAA"}),
        (("",), {"AAA": 1}, {" ALT": "AAA"}),
        (("",), {"AAA": 1}, {"ALT": " AAA"}),
    ],
)
def test_direct_registry_construction_rejects_semantically_invalid_state(
    missing_tokens: tuple[str, ...],
    ratings: Mapping[str, int],
    aliases: Mapping[str, str],
) -> None:
    with pytest.raises(ValidationError):
        RatingRegistry(
            version="1.0.0",
            missing_tokens=missing_tokens,
            ratings=ratings,
            aliases=aliases,
        )


@pytest.mark.parametrize(
    ("document", "category"),
    [
        (
            {
                "version": "2.0.0",
                "missing_tokens": [""],
                "ratings": {"AAA": 1},
                "aliases": {},
            },
            "version",
        ),
        (
            {
                "version": "1.0.0",
                "missing_tokens": [],
                "ratings": {"AAA": 1},
                "aliases": {},
            },
            "missing token",
        ),
        (
            {
                "version": "1.0.0",
                "missing_tokens": ["", ""],
                "ratings": {"AAA": 1},
                "aliases": {},
            },
            "missing token",
        ),
        (
            {
                "version": "1.0.0",
                "missing_tokens": [""],
                "ratings": {"AAA": 0},
                "aliases": {},
            },
            "ordinal",
        ),
        (
            {
                "version": "1.0.0",
                "missing_tokens": [""],
                "ratings": {"AAA": True},
                "aliases": {},
            },
            "ordinal",
        ),
        (
            {
                "version": "1.0.0",
                "missing_tokens": [""],
                "ratings": {"AAA": "1"},
                "aliases": {},
            },
            "ordinal",
        ),
        (
            {
                "version": "1.0.0",
                "missing_tokens": [""],
                "ratings": {"": 1},
                "aliases": {},
            },
            "rating",
        ),
        (
            {
                "version": "1.0.0",
                "missing_tokens": [""],
                "ratings": {"AAA": 1},
                "aliases": {"AA０": "AA0"},  # noqa: RUF001 - alias contract
            },
            "alias",
        ),
        (
            {
                "version": "1.0.0",
                "missing_tokens": [""],
                "ratings": {"AAA": 1},
                "aliases": {"AAA": "AAA"},
            },
            "alias",
        ),
        (
            {
                "version": "1.0.0",
                "missing_tokens": [""],
                "ratings": {"AAA": 1},
                "aliases": {"": "AAA"},
            },
            "alias",
        ),
        (
            {
                "version": "1.0.0",
                "missing_tokens": [""],
                "ratings": {"AAA": 1},
                "aliases": {},
                "extra": 1,
            },
            "configuration",
        ),
        (
            {
                "version": "1.0.0",
                "missing_tokens": [""],
                "aliases": {},
            },
            "configuration",
        ),
        (
            {
                "version": "1.0.0",
                "missing_tokens": [""],
                "ratings": [],
                "aliases": {},
            },
            "rating",
        ),
    ],
)
def test_registry_rejects_wrong_version_and_malformed_contracts(
    tmp_path: Path, document: Mapping[str, object], category: str
) -> None:
    path = tmp_path / "rating.yaml"
    _write_rating_yaml(path, document)
    with pytest.raises(RatingRegistryConfigurationError, match=category) as captured:
        RatingRegistry.from_yaml(path)
    assert captured.value.category == category
    assert str(tmp_path) not in str(captured.value)


@pytest.mark.parametrize(
    ("document", "category"),
    [
        (
            {
                "version": "1.0.0",
                "missing_tokens": ["", " NR "],
                "ratings": {"AAA": 1},
                "aliases": {},
            },
            "missing",
        ),
        (
            {
                "version": "1.0.0",
                "missing_tokens": [""],
                "ratings": {"AAA": 1, " AAA ": 2},
                "aliases": {},
            },
            "rating",
        ),
        (
            {
                "version": "1.0.0",
                "missing_tokens": [""],
                "ratings": {"AAA": 1},
                "aliases": {" ALT ": "AAA"},
            },
            "alias",
        ),
        (
            {
                "version": "1.0.0",
                "missing_tokens": [""],
                "ratings": {"AAA": 1},
                "aliases": {"ALT": " AAA "},
            },
            "alias",
        ),
    ],
)
def test_registry_rejects_padded_and_normalization_colliding_config_tokens(
    tmp_path: Path,
    document: Mapping[str, object],
    category: str,
) -> None:
    path = tmp_path / "rating.yaml"
    _write_rating_yaml(path, document)
    with pytest.raises(RatingRegistryConfigurationError, match=category):
        RatingRegistry.from_yaml(path)


@pytest.mark.parametrize(
    ("raw_yaml", "hidden_content"),
    [
        (
            """version: "2.0.0"
version: "1.0.0"
missing_tokens: [""]
ratings: {AAA: 1}
aliases: {}
""",
            "2.0.0",
        ),
        (
            """version: "1.0.0"
missing_tokens: [""]
ratings:
  UNSUPPORTED_POLICY: 0
ratings:
  AAA: 1
aliases: {}
""",
            "UNSUPPORTED_POLICY",
        ),
        (
            """version: "1.0.0"
missing_tokens: [""]
ratings:
  AAA: 0
  AAA: 1
aliases: {}
""",
            "AAA",
        ),
        (
            """version: "1.0.0"
missing_tokens: [""]
ratings:
  AAA: 1
  AA0: 3
aliases:
  ALT: AAA
  ALT: AA0
""",
            "ALT",
        ),
    ],
)
def test_registry_rejects_duplicate_yaml_keys_without_leaking_hidden_content(
    tmp_path: Path,
    raw_yaml: str,
    hidden_content: str,
) -> None:
    path = tmp_path / "rating.yaml"
    path.write_text(raw_yaml, encoding="utf-8")
    with pytest.raises(
        RatingRegistryConfigurationError,
        match=r"^rating registry configuration error: configuration$",
    ) as captured:
        RatingRegistry.from_yaml(path)
    assert hidden_content not in str(captured.value)
    assert str(tmp_path) not in str(captured.value)


def test_registry_wraps_yaml_syntax_error_without_file_content(tmp_path: Path) -> None:
    path = tmp_path / "rating.yaml"
    path.write_text("ratings: [unclosed", encoding="utf-8")
    with pytest.raises(RatingRegistryConfigurationError, match="configuration") as captured:
        RatingRegistry.from_yaml(path)
    assert "unclosed" not in str(captured.value)
    assert str(tmp_path) not in str(captured.value)


def test_registry_wraps_missing_file_os_error_without_absolute_path(
    tmp_path: Path,
) -> None:
    path = tmp_path / "missing-rating.yaml"
    with pytest.raises(RatingRegistryConfigurationError, match="configuration") as captured:
        RatingRegistry.from_yaml(path)
    assert path.name in str(captured.value)
    assert str(tmp_path) not in str(captured.value)
