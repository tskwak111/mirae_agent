import json
from pathlib import Path

from finproof.planner.provider_schema import (
    build_hcx_query_plan_schema,
    unsupported_schema_keywords,
)

HCX_ALLOWED_SCHEMA_KEYWORDS = {
    "type",
    "properties",
    "required",
    "enum",
    "format",
    "minimum",
    "maximum",
    "minItems",
    "maxItems",
    "items",
    "anyOf",
}


def test_provider_schema_uses_only_supported_subset() -> None:
    schema = build_hcx_query_plan_schema()

    assert schema == json.loads(
        Path("schemas/hcx_query_plan.schema.json").read_text(encoding="utf-8")
    )
    assert unsupported_schema_keywords(schema, HCX_ALLOWED_SCHEMA_KEYWORDS) == set()
    assert schema["type"] == "object"
    assert set(schema["required"]) == {
        "intent",
        "product_types",
        "entities",
        "as_of_date",
        "result_grain",
        "filters",
        "metrics",
        "sort",
        "aggregation",
        "top_k",
        "top_k_scope",
        "needs_clarification",
        "clarification_reason",
    }
    aggregation = schema["properties"]["aggregation"]
    assert aggregation["type"] == "object"
    assert set(aggregation["required"]) == {"function", "field", "group_by"}
    assert aggregation["properties"]["function"]["enum"] == [
        "none",
        "count",
        "min",
        "max",
        "sum",
        "avg",
    ]
    assert aggregation["properties"]["group_by"]["maxItems"] == 2
    assert "product" in schema["properties"]["result_grain"]["enum"]
