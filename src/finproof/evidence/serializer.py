"""Stable, lossless, bounded serialization for answer evidence context."""

from collections.abc import Mapping
from pathlib import PurePosixPath, PureWindowsPath

from finproof.data.artifacts.hashing import canonical_json_bytes
from finproof.domain.evidence import EvidenceBundle
from finproof.registry.loader import RegistryBundle

_DIRECT_FIELDS = (
    "evidence_id",
    "product_type",
    "product_id",
    "field_id",
    "raw_value",
    "normalized_value",
    "quality_status",
    "rule_id",
    "rule_version",
    "source",
    "source_row_number",
    "source_column_name",
    "source_column_number",
    "source_column_letter",
    "source_applicable_date",
)
_DERIVED_FIELDS = (
    "evidence_id",
    "product_type",
    "product_id",
    "field_id",
    "value",
    "quality_status",
    "rule_id",
    "rule_version",
    "as_of_date",
    "inputs",
)
_LOCATOR_FIELDS = (
    "source",
    "source_row_number",
    "source_column_name",
    "source_column_number",
    "source_column_letter",
    "source_applicable_date",
)


def context_limit_bytes() -> int:
    """Load the frozen answer-policy bound instead of owning a duplicate."""
    limits = RegistryBundle.from_package().answers.document["limits"]
    if not isinstance(limits, Mapping):
        raise ValueError("answer policy limits differ")
    limit = limits.get("max_context_bytes")
    if type(limit) is not int or limit < 1:
        raise ValueError("answer policy context bound differs")
    return limit


def serialize_evidence_context(evidence: EvidenceBundle) -> str:
    if type(evidence) is not EvidenceBundle:
        raise TypeError("evidence context differs")
    payload = _compact(evidence)
    if _contains_local_path(payload):
        raise ValueError("evidence context contains a local path")
    encoded = canonical_json_bytes(payload, terminal_newline=False)
    if len(encoded) > context_limit_bytes():
        raise ValueError("evidence context exceeds configured bound")
    return encoded.decode()


def _compact(evidence: EvidenceBundle) -> dict[str, object]:
    direct = tuple(item.model_dump(mode="json") for item in evidence.direct)
    derived = tuple(item.model_dump(mode="json") for item in evidence.derived)
    locators = tuple(item["value"]["source"] for item in direct) + tuple(
        locator for item in derived for locator in item["value"]["inputs"]
    )
    source_keys = tuple(sorted({_source_key(locator) for locator in locators}))
    source_index = {key: index for index, key in enumerate(source_keys)}
    return {
        "format": "evidence_context.v2",
        "sources": [_source_value(key) for key in source_keys],
        "direct_fields": _DIRECT_FIELDS,
        "direct": [_direct_value(item, source_index) for item in direct],
        "derived_fields": _DERIVED_FIELDS,
        "derived": [_derived_value(item, source_index) for item in derived],
        "locator_fields": _LOCATOR_FIELDS,
        "summaries": [item.model_dump(mode="json") for item in evidence.summaries],
        "material_policy_limitations": list(evidence.material_policy_limitations),
    }


def _source_key(locator: Mapping[str, object]) -> tuple[str, str, str, str, str]:
    return (
        _text(locator, "source_table"),
        _text(locator, "source_file"),
        _text(locator, "source_sheet"),
        _text(locator, "source_checksum"),
        _text(locator, "source_snapshot_date"),
    )


def _source_value(key: tuple[str, str, str, str, str]) -> dict[str, str]:
    fields = (
        "source_table",
        "source_file",
        "source_sheet",
        "source_checksum",
        "source_snapshot_date",
    )
    return dict(zip(fields, key, strict=True))


def _direct_value(
    item: Mapping[str, object], source_index: Mapping[tuple[str, str, str, str, str], int]
) -> list[object]:
    value = _mapping(item, "value")
    return [
        item["evidence_id"],
        item["product_type"],
        item["product_id"],
        item["field_id"],
        value["raw_value"],
        value["normalized_value"],
        value["quality_status"],
        value["rule_id"],
        value["rule_version"],
        *_locator_value(_mapping(value, "source"), source_index),
    ]


def _derived_value(
    item: Mapping[str, object], source_index: Mapping[tuple[str, str, str, str, str], int]
) -> list[object]:
    value = _mapping(item, "value")
    return [
        item["evidence_id"],
        item["product_type"],
        item["product_id"],
        item["field_id"],
        value["value"],
        value["quality_status"],
        value["rule_id"],
        value["rule_version"],
        value["as_of_date"],
        [_locator_value(_mapping(locator), source_index) for locator in _sequence(value["inputs"])],
    ]


def _locator_value(
    locator: Mapping[str, object], source_index: Mapping[tuple[str, str, str, str, str], int]
) -> list[object]:
    return [
        source_index[_source_key(locator)],
        locator["source_row_number"],
        locator["source_column_name"],
        locator["source_column_number"],
        locator["source_column_letter"],
        locator["source_applicable_date"],
    ]


def _mapping(value: object, key: str | None = None) -> Mapping[str, object]:
    candidate = value if key is None else _mapping(value)[key]
    if not isinstance(candidate, Mapping):
        raise TypeError("evidence serialization shape differs")
    return candidate


def _sequence(value: object) -> tuple[object, ...]:
    if type(value) is not list:
        raise TypeError("evidence serialization sequence differs")
    return tuple(value)


def _text(value: Mapping[str, object], key: str) -> str:
    result = value[key]
    if type(result) is not str:
        raise TypeError("evidence source text differs")
    return result


def _contains_local_path(value: object) -> bool:
    if type(value) is str:
        return PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()
    if type(value) is list or type(value) is tuple:
        return any(_contains_local_path(item) for item in value)
    if type(value) is dict:
        return any(_contains_local_path(item) for item in value.values())
    return False
