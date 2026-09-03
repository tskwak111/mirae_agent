"""Checked-in provider schema loading and adaptation."""

import json
from collections.abc import Iterable
from copy import deepcopy
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError as PydanticValidationError

from finproof.domain.query_plan import QueryPlan

_SCHEMA_PATH = Path(__file__).parents[3] / "schemas/hcx_query_plan.schema.json"
_CANONICAL_SCHEMA_PATH = Path(__file__).parents[3] / "schemas/query_plan.schema.json"


class ProviderPlanValidationStage(StrEnum):
    """Non-content stage at which provider plan validation failed."""

    INVALID_JSON = "invalid_json"
    PROVIDER_SCHEMA = "provider_schema"
    CANONICAL_SCHEMA = "canonical_schema"
    PYDANTIC = "pydantic"


class ProviderPlanError(ValueError):
    """Provider output failed JSON, schema, or canonical plan validation."""

    def __init__(
        self,
        stage: ProviderPlanValidationStage,
        message: str,
        *,
        canonical_substage: str | None = None,
        canonical_path: str | None = None,
        canonical_keyword: str | None = None,
        filter_shape_category: str | None = None,
    ) -> None:
        self.stage = stage
        self.canonical_substage = canonical_substage
        self.canonical_path = canonical_path
        self.canonical_keyword = canonical_keyword
        self.filter_shape_category = filter_shape_category
        super().__init__(message)


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
        raise ProviderPlanError(
            ProviderPlanValidationStage.INVALID_JSON,
            "provider output is not strict JSON",
        ) from None
    if not isinstance(payload, dict):
        raise ProviderPlanError(
            ProviderPlanValidationStage.INVALID_JSON,
            "provider plan root must be an object",
        )

    try:
        Draft202012Validator(
            build_hcx_query_plan_schema(), format_checker=FormatChecker()
        ).validate(payload)
    except (JsonSchemaValidationError, TypeError, ValueError):
        raise ProviderPlanError(
            ProviderPlanValidationStage.PROVIDER_SCHEMA,
            "provider plan schema validation failed",
        ) from None

    canonical = canonicalize_provider_plan(cast(dict[str, Any], payload))
    try:
        canonical_schema = json.loads(_CANONICAL_SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator(canonical_schema, format_checker=FormatChecker()).validate(canonical)
    except JsonSchemaValidationError as error:
        raise ProviderPlanError(
            ProviderPlanValidationStage.CANONICAL_SCHEMA,
            "canonical plan schema validation failed",
            canonical_substage="schema",
            canonical_path=_json_pointer(error.absolute_path),
            canonical_keyword=error.validator if isinstance(error.validator, str) else None,
            filter_shape_category=_filter_shape_category(canonical, error),
        ) from None
    except (TypeError, ValueError):
        raise ProviderPlanError(
            ProviderPlanValidationStage.CANONICAL_SCHEMA,
            "canonical plan schema validation failed",
        ) from None

    try:
        return QueryPlan.model_validate_json(
            json.dumps(
                canonical,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
    except (PydanticValidationError, TypeError, ValueError):
        raise ProviderPlanError(
            ProviderPlanValidationStage.PYDANTIC,
            "canonical plan model validation failed",
        ) from None


def canonicalize_provider_plan(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert the HCX-safe aggregation object into the canonical nullable shape."""
    canonical = deepcopy(payload)
    intent = canonical.get("intent")
    if intent in {"clarify", "unsupported"}:
        canonical.update(
            {
                "product_types": [],
                "entities": [],
                "result_grain": "product",
                "filters": [],
                "metrics": [],
                "metric_targets": [],
                "sort": [],
                "aggregation": {"function": "none", "field": "", "group_by": []},
                "top_k_scope": "per_product_type",
                "needs_clarification": intent == "clarify",
            }
        )
    aggregation = canonical.get("aggregation")
    if not isinstance(aggregation, dict) or set(aggregation) != {
        "function",
        "field",
        "group_by",
    }:
        raise ProviderPlanError(
            ProviderPlanValidationStage.CANONICAL_SCHEMA,
            "provider aggregation shape differs",
            canonical_substage="adaptation",
            canonical_path="/aggregation",
        )
    function = aggregation.get("function")
    field = aggregation.get("field")
    group_by = aggregation.get("group_by")
    if not isinstance(field, str) or not isinstance(group_by, list):
        raise ProviderPlanError(
            ProviderPlanValidationStage.CANONICAL_SCHEMA,
            "provider aggregation values differ",
            canonical_substage="adaptation",
            canonical_path="/aggregation",
        )
    if function == "none":
        if field != "" or group_by:
            raise ProviderPlanError(
                ProviderPlanValidationStage.CANONICAL_SCHEMA,
                "none aggregation requires empty field and group_by",
                canonical_substage="adaptation",
                canonical_path="/aggregation",
            )
        canonical["aggregation"] = None
    elif function == "count":
        if field != "":
            raise ProviderPlanError(
                ProviderPlanValidationStage.CANONICAL_SCHEMA,
                "count aggregation requires an empty field",
                canonical_substage="adaptation",
                canonical_path="/aggregation",
            )
        aggregation["field"] = None
    elif function in {"min", "max", "sum", "avg"}:
        if not field:
            raise ProviderPlanError(
                ProviderPlanValidationStage.CANONICAL_SCHEMA,
                "value aggregation requires a field",
                canonical_substage="adaptation",
                canonical_path="/aggregation",
            )
    else:
        raise ProviderPlanError(
            ProviderPlanValidationStage.CANONICAL_SCHEMA,
            "provider aggregation function differs",
            canonical_substage="adaptation",
            canonical_path="/aggregation",
        )
    return canonical


def _json_pointer(parts: Iterable[str | int]) -> str:
    return "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in parts)


def _filter_shape_category(
    canonical: dict[str, Any], error: JsonSchemaValidationError
) -> str | None:
    path = list(error.absolute_path)
    if error.validator != "oneOf" or len(path) != 2 or path[0] != "filters":
        return None
    filters = canonical.get("filters")
    if not isinstance(filters, list) or not isinstance(path[1], int):
        return None
    clause = filters[path[1]]
    if not isinstance(clause, dict):
        return "unknown"
    operator = clause.get("operator")
    value = clause.get("value")
    if operator in {"eq", "ne", "gt", "gte", "lt", "lte", "contains", "starts_with"}:
        return "scalar_operator_with_array" if isinstance(value, list) else "unknown"
    if operator in {"in", "not_in"}:
        return "unknown" if isinstance(value, list) else "set_operator_with_scalar"
    if operator == "between":
        return "range_arity"
    if operator in {"is_missing", "is_not_missing"}:
        return "missing_operator_with_value"
    return "unknown"


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")
