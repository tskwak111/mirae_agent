#!/usr/bin/env python3
"""Verify that the Codex handoff is complete, internally consistent, and unmodified."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

YamlSafeLoad = Callable[[str], object]
yaml_safe_load: YamlSafeLoad | None
try:
    yaml_safe_load = cast(YamlSafeLoad, import_module("yaml").safe_load)
except ModuleNotFoundError:  # pragma: no cover - bootstrap without dependencies
    yaml_safe_load = None

if TYPE_CHECKING:
    from tools.extract_schema_catalog import build_catalog
    from tools.xlsx_stream import list_sheet_names
elif __package__:
    from .extract_schema_catalog import build_catalog
    from .xlsx_stream import list_sheet_names
else:
    from extract_schema_catalog import build_catalog
    from xlsx_stream import list_sheet_names

ROOT: Final = Path(__file__).resolve().parents[1]

REQUIRED_FILES: Final = (
    "AGENTS.md",
    "START_HERE.md",
    "README.md",
    "CODEX_MASTER_PROMPT.md",
    "CODEX_RESUME_PROMPT.md",
    "CODEX_REVIEW_PROMPT.md",
    "HANDOFF_PACKAGE_MANIFEST.md",
    "pyproject.toml",
    "docs/02_FINAL_FROZEN_DESIGN.md",
    "docs/03_DATA_AUDIT_BASELINE.md",
    "docs/04_DATA_AND_DOMAIN_CONTRACTS.md",
    "docs/05_QUERYPLAN_AND_API_CONTRACT.md",
    "docs/06_METRIC_REGISTRY_POLICY.md",
    "docs/07_TESTING_AND_EVALUATION.md",
    "docs/08_SECURITY_OPERATIONS_AND_RELEASE.md",
    "docs/10_DECISION_LOG.md",
    "docs/11_DEFINITION_OF_DONE.md",
    "docs/12_CODE_REVIEW_CHECKLIST.md",
    "docs/13_HANDOFF_VALIDATION_REPORT.md",
    "docs/implementation/STATUS.md",
    "docs/implementation/PHASE_GATES.md",
    "docs/superpowers/specs/2026-08-07-finproof-design.md",
    "docs/superpowers/plans/2026-08-07-00-roadmap.md",
    "docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md",
    "docs/superpowers/plans/2026-08-07-02-deterministic-query-engine.md",
    "docs/superpowers/plans/2026-08-07-03-hcx-planner-and-api.md",
    "docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md",
    "config/datasets.yaml",
    "config/metric_registry.yaml",
    "config/field_registry.yaml",
    "config/state_rules.yaml",
    "config/quality_rules.yaml",
    "config/rating_scale.yaml",
    "config/answer_policy.yaml",
    "config/planner_catalog.yaml",
    "schemas/query_plan.schema.json",
    "schemas/hcx_query_plan.schema.json",
    "schemas/evidence_record.schema.json",
    "schemas/api_response.schema.json",
    "schemas/execution_trace.schema.json",
    "schemas/quality_issue.schema.json",
    "schemas/artifact_manifest.schema.json",
    "schemas/golden_case.schema.json",
    "source_material/competition_task_financial_product_agent.pdf",
    "source_material/input_manifest.json",
    "source_material/schema_catalog.json",
    "tests/contracts/README.md",
    "tests/contracts/expected_source_audit.json",
    "tests/golden/README.md",
    "tests/golden/seed_cases.jsonl",
    "tests/contract/test_handoff_package.py",
    "tools/__init__.py",
    "tools/audit_source_data.py",
    "tools/extract_schema_catalog.py",
    "tools/xlsx_stream.py",
    "prompts/00_INITIAL_KICKOFF.md",
    "prompts/01_DATA_FOUNDATION.md",
    "prompts/02_QUERY_ENGINE.md",
    "prompts/03_HCX_AND_API.md",
    "prompts/04_EVALUATION_AND_RELEASE.md",
    "prompts/99_CODE_REVIEW.md",
)

PLAN_FORBIDDEN_PATTERNS: Final = (
    re.compile(r"\bTBD\b", re.IGNORECASE),
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"implement later", re.IGNORECASE),
    re.compile(r"fill in details", re.IGNORECASE),
    re.compile(r"similar to task", re.IGNORECASE),
)

HCX_ALLOWED_SCHEMA_KEYWORDS: Final = {
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

NATIVE_GRAIN_BY_PRODUCT_TYPE: Final = {
    "domestic_bond": "instrument",
    "domestic_etf": "listed_product",
    "domestic_etn": "listed_product",
    "overseas_etf": "listed_product",
    "overseas_etn": "listed_product",
    "public_fund": "fund_item",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def unsupported_hcx_schema_keywords(document: Any) -> set[str]:
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


def verify_required(errors: list[str]) -> None:
    for relative in REQUIRED_FILES:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing required file: {relative}")
        elif path.stat().st_size == 0 and relative != "src/finproof/py.typed":
            errors.append(f"empty required file: {relative}")


def verify_manifest(errors: list[str]) -> None:
    manifest_path = ROOT / "source_material/input_manifest.json"
    if not manifest_path.is_file():
        return
    manifest = load_json(manifest_path)
    if manifest.get("snapshot_date") != "2026-07-11":
        errors.append("input manifest snapshot_date must be 2026-07-11")
    entries = manifest.get("files", [])
    if len(entries) != 9:
        errors.append(f"input manifest must contain 9 files, found {len(entries)}")
    seen: set[str] = set()
    for entry in entries:
        relative = entry.get("path")
        if not isinstance(relative, str):
            errors.append("manifest entry has invalid path")
            continue
        if relative in seen:
            errors.append(f"duplicate manifest path: {relative}")
        seen.add(relative)
        path = (ROOT / "source_material" / relative).resolve()
        source_root = (ROOT / "source_material").resolve()
        if source_root not in path.parents and path != source_root:
            errors.append(f"manifest path escapes source_material: {relative}")
            continue
        if not path.is_file():
            errors.append(f"manifest file missing: {relative}")
            continue
        if path.stat().st_size != entry.get("size_bytes"):
            errors.append(f"size mismatch: {relative}")
        if sha256(path) != entry.get("sha256"):
            errors.append(f"sha256 mismatch: {relative}")
        if entry.get("kind") == "data":
            expected_sheet = entry.get("sheet_name")
            if expected_sheet not in list_sheet_names(path):
                errors.append(f"missing expected sheet {expected_sheet!r}: {relative}")
        if entry.get("kind") == "schema":
            expected_sheets = tuple(entry.get("sheet_names", []))
            actual_sheets = list_sheet_names(path)
            if actual_sheets != expected_sheets:
                errors.append(f"schema sheet mismatch {relative}: {actual_sheets!r}")


def verify_json_and_schema_contracts(errors: list[str]) -> None:
    provider_schema_name = "hcx_query_plan.schema.json"
    for path in sorted((ROOT / "schemas").glob("*.json")):
        try:
            document = load_json(path)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            errors.append(f"invalid JSON {path.relative_to(ROOT)}: {exc}")
            continue
        if (
            path.name != provider_schema_name
            and document.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        ):
            errors.append(f"unexpected JSON Schema draft: {path.relative_to(ROOT)}")

    api_path = ROOT / "schemas/api_response.schema.json"
    if api_path.is_file():
        api = load_json(api_path)
        exact = {"question_id", "question", "retrieved_context", "think_trace", "answer"}
        if set(api.get("required", [])) != exact or set(api.get("properties", {})) != exact:
            errors.append("api_response schema must contain exactly the official five fields")
        if api.get("additionalProperties") is not False:
            errors.append("api_response schema must forbid extra fields")
        for name in exact:
            if api.get("properties", {}).get(name, {}).get("type") != "string":
                errors.append(f"api_response field must be string: {name}")

    query_path = ROOT / "schemas/query_plan.schema.json"
    provider_path = ROOT / "schemas/hcx_query_plan.schema.json"
    provider_required = {
        "intent",
        "product_types",
        "entities",
        "as_of_date",
        "result_grain",
        "filters",
        "metrics",
        "sort",
        "top_k",
        "top_k_scope",
        "needs_clarification",
        "clarification_reason",
    }
    query_required = provider_required | {"aggregation"}
    if query_path.is_file():
        query = load_json(query_path)
        if set(query.get("required", [])) != query_required:
            errors.append("query_plan schema required fields differ from frozen contract")
        grains = set(query.get("properties", {}).get("result_grain", {}).get("enum", []))
        if "product" not in grains:
            errors.append("query_plan schema must include heterogeneous product result grain")
        scopes = set(query.get("properties", {}).get("top_k_scope", {}).get("enum", []))
        if scopes != {"global", "per_product_type"}:
            errors.append("query_plan schema top_k_scope enum differs from frozen contract")
    if provider_path.is_file():
        provider = load_json(provider_path)
        unsupported = unsupported_hcx_schema_keywords(provider)
        if unsupported:
            errors.append(
                f"HCX provider schema contains unsupported keywords: {sorted(unsupported)!r}"
            )
        if set(provider.get("required", [])) != provider_required:
            errors.append("HCX provider schema required fields differ from canonical contract")
        if provider.get("type") != "object":
            errors.append("HCX provider schema root type must be object")
        grains = set(provider.get("properties", {}).get("result_grain", {}).get("enum", []))
        if "product" not in grains:
            errors.append("HCX provider schema must include heterogeneous product result grain")
        scopes = set(provider.get("properties", {}).get("top_k_scope", {}).get("enum", []))
        if scopes != {"global", "per_product_type"}:
            errors.append("HCX provider schema top_k_scope enum differs from frozen contract")

    expected_path = ROOT / "tests/contracts/expected_source_audit.json"
    if expected_path.is_file():
        expected = load_json(expected_path)
        if expected.get("total_source_rows") != 145393:
            errors.append("expected source audit total must be 145393")


def verify_yaml(errors: list[str]) -> None:
    for path in sorted((ROOT / "config").glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        if "\t" in text:
            errors.append(f"tab character in YAML: {path.relative_to(ROOT)}")
        if yaml_safe_load is not None:
            try:
                document = yaml_safe_load(text)
            except Exception as exc:
                errors.append(f"invalid YAML {path.relative_to(ROOT)}: {exc}")
                continue
            if not isinstance(document, dict) or "version" not in document:
                errors.append(f"YAML must be a versioned mapping: {path.relative_to(ROOT)}")


def verify_schema_catalog(errors: list[str]) -> None:
    catalog_path = ROOT / "source_material/schema_catalog.json"
    if not catalog_path.is_file():
        return
    expected = load_json(catalog_path)
    actual = build_catalog()
    if expected != actual:
        errors.append("schema_catalog.json does not match the schema workbooks")
    expected_counts = {"PRBD01N001": 40, "PREF01N001": 73, "PREF02N001": 49, "PRFD01N001": 45}
    actual_counts = {key: value["column_count"] for key, value in actual["tables"].items()}
    if actual_counts != expected_counts:
        errors.append(f"schema column counts differ: {actual_counts!r}")


def verify_golden_seeds(errors: list[str]) -> None:
    path = ROOT / "tests/golden/seed_cases.jsonl"
    if not path.is_file():
        return
    required = {
        "case_id",
        "category",
        "question",
        "expected_plan",
        "expected_result",
        "expected_answer",
        "review",
    }
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid golden JSONL line {line_number}: {exc}")
            continue
        if not isinstance(case, dict) or set(case) != required:
            errors.append(f"golden seed line {line_number} has unexpected top-level fields")
            continue
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"golden seed line {line_number} has invalid case_id")
        elif case_id in seen:
            errors.append(f"duplicate golden seed case_id: {case_id}")
        else:
            seen.add(case_id)
        plan = case.get("expected_plan")
        if not isinstance(plan, dict):
            errors.append(f"golden seed line {line_number} has invalid expected_plan")
        else:
            if plan.get("top_k_scope") not in {"global", "per_product_type"}:
                errors.append(f"golden seed line {line_number} has invalid top_k_scope")
            top_k = plan.get("top_k")
            if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 50:
                errors.append(f"golden seed line {line_number} has invalid top_k")
            product_types = plan.get("product_types", [])
            native_grains = {
                NATIVE_GRAIN_BY_PRODUCT_TYPE[item]
                for item in product_types
                if item in NATIVE_GRAIN_BY_PRODUCT_TYPE
            }
            if len(native_grains) > 1 and plan.get("result_grain") != "product":
                errors.append(
                    f"golden seed line {line_number} spans heterogeneous native grains "
                    "without product envelope"
                )
        review = case.get("review")
        if not isinstance(review, dict) or set(review) != {"reviewer", "reviewed_at", "source"}:
            errors.append(f"golden seed line {line_number} has invalid review block")
    if len(seen) < 10:
        errors.append(f"golden seed file must contain at least 10 unique cases, found {len(seen)}")


def verify_plans(errors: list[str]) -> None:
    for path in sorted((ROOT / "docs/superpowers/plans").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for pattern in PLAN_FORBIDDEN_PATTERNS:
            if pattern.search(text):
                errors.append(
                    f"plan placeholder pattern {pattern.pattern!r}: {path.relative_to(ROOT)}"
                )
        if "- [ ]" not in text:
            errors.append(f"plan has no trackable checkbox: {path.relative_to(ROOT)}")
        if (
            "**Goal:**" not in text
            or "**Architecture:**" not in text
            or "**Tech Stack:**" not in text
        ):
            errors.append(f"plan header incomplete: {path.relative_to(ROOT)}")


def verify_runtime_dependency_policy(errors: list[str]) -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    forbidden = ('"openai', '"anthropic', "google-generativeai", '"cohere', '"groq')
    for token in forbidden:
        if token in pyproject:
            errors.append(f"forbidden generative runtime dependency in pyproject: {token}")
    if '"pytest>=9.1.1,<10"' not in pyproject:
        errors.append("pyproject pytest range differs from verified handoff constraint")
    if '"pytest-asyncio>=1.4,<2"' not in pyproject:
        errors.append("pyproject pytest-asyncio range must support pytest 9")


def main() -> int:
    errors: list[str] = []
    verify_required(errors)
    verify_manifest(errors)
    verify_json_and_schema_contracts(errors)
    verify_yaml(errors)
    verify_schema_catalog(errors)
    verify_golden_seeds(errors)
    verify_plans(errors)
    verify_runtime_dependency_policy(errors)

    if errors:
        print("FinProof handoff verification FAILED:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    manifest = load_json(ROOT / "source_material/input_manifest.json")
    total_bytes = sum(item["size_bytes"] for item in manifest["files"])
    print(
        "FinProof handoff PASS: "
        f"{len(REQUIRED_FILES)} required files, {len(manifest['files'])} official inputs, "
        f"{total_bytes:,} source bytes"
    )
    if yaml_safe_load is None:
        print(
            "Note: PyYAML unavailable; bootstrap verification performed non-parser YAML "
            "checks only."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
