from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
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


def _unsupported_hcx_schema_keywords(document: Any) -> set[str]:
    unsupported: set[str] = set()

    def walk(node: Any, *, properties_mapping: bool = False) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        if properties_mapping:
            for child in node.values():
                walk(child)
            return
        for key, value in node.items():
            if key not in HCX_ALLOWED_SCHEMA_KEYWORDS:
                unsupported.add(key)
            if key == "properties":
                walk(value, properties_mapping=True)
            elif key in {"items", "anyOf"}:
                walk(value)

    walk(document)
    return unsupported


def test_api_response_schema_has_exact_competition_fields() -> None:
    schema = json.loads((ROOT / "schemas/api_response.schema.json").read_text(encoding="utf-8"))

    expected = {"question_id", "question", "retrieved_context", "think_trace", "answer"}

    assert set(schema["required"]) == expected
    assert set(schema["properties"]) == expected
    assert schema["additionalProperties"] is False
    assert all(field_schema["type"] == "string" for field_schema in schema["properties"].values())


def test_query_plan_contract_supports_cross_product_scope() -> None:
    schema = json.loads((ROOT / "schemas/query_plan.schema.json").read_text(encoding="utf-8"))

    assert "top_k_scope" in schema["required"]
    assert set(schema["properties"]["top_k_scope"]["enum"]) == {
        "global",
        "per_product_type",
    }
    assert "product" in schema["properties"]["result_grain"]["enum"]
    assert schema["additionalProperties"] is False


def test_hcx_provider_schema_uses_only_supported_subset() -> None:
    schema = json.loads(
        (ROOT / "schemas/hcx_query_plan.schema.json").read_text(encoding="utf-8")
    )

    assert _unsupported_hcx_schema_keywords(schema) == set()
    assert schema["type"] == "object"
    assert "top_k_scope" in schema["required"]
    assert "product" in schema["properties"]["result_grain"]["enum"]


def test_official_input_manifest_contains_pdf_and_eight_workbooks() -> None:
    manifest = json.loads(
        (ROOT / "source_material/input_manifest.json").read_text(encoding="utf-8")
    )

    paths = {entry["path"] for entry in manifest["files"]}

    assert "competition_task_financial_product_agent.pdf" in paths
    assert len([path for path in paths if path.endswith(".xlsx")]) == 8
    assert len(paths) == 9


def test_golden_seed_file_is_valid_jsonl_with_unique_ids() -> None:
    lines = (ROOT / "tests/golden/seed_cases.jsonl").read_text(encoding="utf-8").splitlines()
    cases = [json.loads(line) for line in lines if line.strip()]

    schema = json.loads((ROOT / "schemas/golden_case.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for case in cases:
        validator.validate(case)

    case_ids = [case["case_id"] for case in cases]

    assert len(cases) >= 10
    assert len(case_ids) == len(set(case_ids))
    assert all(case["review"]["reviewer"] == "AI-handoff-seed" for case in cases)
    assert all(case["expected_plan"]["top_k_scope"] in {"global", "per_product_type"} for case in cases)


def test_cross_product_seed_preserves_native_segments() -> None:
    cases = [
        json.loads(line)
        for line in (ROOT / "tests/golden/seed_cases.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    case = next(item for item in cases if item["case_id"] == "SEED-POLICY-013")

    assert case["expected_plan"]["result_grain"] == "product"
    assert case["expected_plan"]["top_k_scope"] == "per_product_type"
    assert [segment["native_grain"] for segment in case["expected_result"]["segments"]] == [
        "instrument",
        "listed_product",
        "fund_item",
    ]


def test_handoff_tools_are_importable_modules() -> None:
    from tools import audit_source_data, extract_schema_catalog, verify_handoff

    assert callable(audit_source_data.main)
    assert callable(extract_schema_catalog.main)
    assert callable(verify_handoff.main)
