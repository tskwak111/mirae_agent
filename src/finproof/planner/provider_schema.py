"""Checked-in provider schema loading and adaptation."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError as PydanticValidationError

from finproof.domain.query_plan import QueryPlan

_SCHEMA_PATH = Path(__file__).parents[3] / "schemas/hcx_query_plan.schema.json"
_CANONICAL_SCHEMA_PATH = Path(__file__).parents[3] / "schemas/query_plan.schema.json"


class ProviderPlanError(ValueError):
    """Provider output failed JSON, schema, or canonical plan validation."""


def build_hcx_query_plan_schema() -> dict[str, Any]:
    """Load a fresh copy of the checked-in HCX provider schema."""
    value = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("HCX provider schema root must be an object")
    return cast(dict[str, Any], value)


def unsupported_schema_keywords(schema: dict[str, Any], allowed: set[str]) -> set[str]:
    """Return JSON Schema keywords outside the documented HCX subset."""
    unsupported: set[str] = set()

    def visit(node: object) -> None:
        if not isinstance(node, dict):
            return
        for keyword, value in node.items():
            if keyword not in allowed:
                unsupported.add(keyword)
            if keyword == "properties" and isinstance(value, dict):
                for property_schema in value.values():
                    visit(property_schema)
            elif keyword == "items":
                visit(value)
            elif keyword == "anyOf" and isinstance(value, list):
                for option in value:
                    visit(option)

    visit(schema)
    return unsupported


def parse_provider_plan(content: str) -> QueryPlan:
    """Validate provider JSON and adapt its non-null aggregation sentinel."""
    try:
        payload = json.loads(content, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        raise ProviderPlanError("provider output is not strict JSON") from None
    if not isinstance(payload, dict):
        raise ProviderPlanError("provider plan root must be an object")

    try:
        Draft202012Validator(
            build_hcx_query_plan_schema(), format_checker=FormatChecker()
        ).validate(payload)
        canonical = canonicalize_provider_plan(cast(dict[str, Any], payload))
        canonical_schema = json.loads(_CANONICAL_SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator(canonical_schema, format_checker=FormatChecker()).validate(canonical)
        return QueryPlan.model_validate_json(
            json.dumps(canonical, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        )
    except (JsonSchemaValidationError, PydanticValidationError, TypeError, ValueError) as error:
        if isinstance(error, ProviderPlanError):
            raise
        raise ProviderPlanError("provider plan schema validation failed") from error


def canonicalize_provider_plan(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert the HCX-safe aggregation object into the canonical nullable shape."""
    canonical = deepcopy(payload)
    aggregation = canonical.get("aggregation")
    if not isinstance(aggregation, dict) or set(aggregation) != {
        "function",
        "field",
        "group_by",
    }:
        raise ProviderPlanError("provider aggregation shape differs")
    function = aggregation.get("function")
    field = aggregation.get("field")
    group_by = aggregation.get("group_by")
    if not isinstance(field, str) or not isinstance(group_by, list):
        raise ProviderPlanError("provider aggregation values differ")
    if function == "none":
        if field != "" or group_by:
            raise ProviderPlanError("none aggregation requires empty field and group_by")
        canonical["aggregation"] = None
    elif function == "count":
        if field != "":
            raise ProviderPlanError("count aggregation requires an empty field")
        aggregation["field"] = None
    elif function in {"min", "max", "sum", "avg"}:
        if not field:
            raise ProviderPlanError("value aggregation requires a field")
    else:
        raise ProviderPlanError("provider aggregation function differs")
    return canonical


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")
