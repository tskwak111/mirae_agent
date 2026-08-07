from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from tools.verify_handoff import (
    git_workflow_violations,
    unguarded_git_block_lines,
    unsafe_git_commit_lines,
    unsafe_git_stage_lines,
)

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
    schema = json.loads((ROOT / "schemas/hcx_query_plan.schema.json").read_text(encoding="utf-8"))

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
    assert all(
        case["expected_plan"]["top_k_scope"] in {"global", "per_product_type"} for case in cases
    )


def test_cross_product_seed_preserves_native_segments() -> None:
    cases = [
        json.loads(line)
        for line in (ROOT / "tests/golden/seed_cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
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


def test_unsafe_git_stage_lines_rejects_noncanonical_staging() -> None:
    text = """```powershell
git add .
git add tests
git add -A
git stage -- README.md
git -C .. add -- README.md
git add -- ../outside.md
git add -- ':(glob)**'
git add -- $paths
git add -- README.md; git commit -m unsafe
git add -- `
  README.md
```
```python
example = "git add ."
```
"""

    assert unsafe_git_stage_lines(text) == (
        (2, "git add ."),
        (3, "git add tests"),
        (4, "git add -A"),
        (5, "git stage -- README.md"),
        (6, "git -C .. add -- README.md"),
        (7, "git add -- ../outside.md"),
        (8, "git add -- ':(glob)**'"),
        (9, "git add -- $paths"),
        (10, "git add -- README.md; git commit -m unsafe"),
        (11, "git add -- `"),
    )


@pytest.mark.parametrize(
    "command",
    [
        "git add -u",
        "git add --update",
        "git --git-dir=../repo/.git --work-tree=.. add -- README.md",
        "git add -- ./tests/unit/test_guard.py",
        "git add -- tests/",
        r"git add -- .\tests\unit\test_guard.py",
        "git add -- TESTS",
        "git add -- C:/outside.txt",
        "git add -- :/",
        "git add -- ':(exclude)README.md'",
        "git add -- docs/**/*.md",
        "git add -- ${paths}",
        'git add -- "README.md"',
        "git add -- README.md && git commit -m unsafe",
        "git add -- README.md \\",
    ],
)
def test_unsafe_git_stage_lines_rejects_bypass_variants(command: str) -> None:
    text = f"```sh\n{command}\n```\n"

    assert unsafe_git_stage_lines(text) == ((2, command),)


def test_unsafe_git_stage_lines_accepts_exact_owned_paths() -> None:
    text = """```powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- tools/check_repo_root.py tests/contract/test_repo_root_guard.py
git add -- src/finproof/query tests/unit/query
```
"""

    assert unsafe_git_stage_lines(text) == ()


def test_nested_shell_example_inside_python_fence_is_inert() -> None:
    text = """````python
```powershell
git add .
```
````
"""

    assert unsafe_git_stage_lines(text) == ()
    assert unguarded_git_block_lines(text) == ()


@pytest.mark.parametrize(
    ("opener", "closer"),
    [
        ("```shell title=guard", "```"),
        ("~~~ZSH {.task}", "~~~"),
        ("```pwsh", "````"),
        ("```ps1", "```"),
        ("```{.bash}", "```"),
        ("```", "```"),
        ("```unknown", "```"),
    ],
)
def test_shell_and_unknown_git_fences_fail_closed(opener: str, closer: str) -> None:
    text = f"   {opener}\ngit status --short\n   {closer}\n"

    assert unguarded_git_block_lines(text) == ((2, "git status --short"),)


def test_unclosed_shell_fence_is_checked_through_eof() -> None:
    text = "```bash\ngit status --short\n"

    assert unguarded_git_block_lines(text) == ((2, "git status --short"),)


def test_unknown_fence_with_unparseable_git_line_fails_closed() -> None:
    text = '```unknown\ngit status "unterminated\n```\n'

    assert unguarded_git_block_lines(text) == ((2, 'git status "unterminated'),)


def test_unguarded_git_block_lines_requires_guard_before_git() -> None:
    text = """```powershell
git status --short
```
```bash
python tools/check_repo_root.py --expected-root .
git status --short
```
```powershell
python tools/check_repo_root.py --expected-root .
Set-Location ..
git status --short
```
"""

    assert unguarded_git_block_lines(text) == (
        (2, "git status --short"),
        (11, "git status --short"),
    )


@pytest.mark.parametrize(
    ("block", "expected_line"),
    [
        (
            "Get-Location\npython tools/check_repo_root.py --expected-root .\ngit status --short",
            4,
        ),
        (
            "python tools/check_repo_root.py --expected-root .\ngit -C .. status --short",
            3,
        ),
        (
            "python tools/check_repo_root.py --expected-root .\nGIT_DIR=../repo/.git git status",
            3,
        ),
        (
            "python tools/check_repo_root.py --expected-root .\ngit tag candidate",
            3,
        ),
    ],
)
def test_git_blocks_reject_context_switches_and_weak_mutation_guards(
    block: str, expected_line: int
) -> None:
    text = f"```powershell\n{block}\n```\n"

    assert unguarded_git_block_lines(text) == (
        (expected_line, block.splitlines()[expected_line - 2]),
    )


def test_unsafe_git_commit_lines_requires_clean_index_and_exact_stage() -> None:
    text = """```powershell
python tools/check_repo_root.py --expected-root .
git add -- README.md
git commit -m missing-clean-index
```
```bash
python tools/check_repo_root.py --expected-root . --require-clean-index
git commit -a -m unsafe
```
```powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git commit -m missing-stage
```
```powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- README.md
git diff --cached --name-status --
git commit -m safe
```
"""

    assert unsafe_git_commit_lines(text) == (
        (4, "git commit -m missing-clean-index"),
        (8, "git commit -a -m unsafe"),
        (12, "git commit -m missing-stage"),
    )


@pytest.mark.parametrize("option", ["-a", "-am", "-ma", "--all", "--include=README.md"])
def test_unsafe_git_commit_lines_rejects_auto_staging_options(option: str) -> None:
    text = f"""```bash
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- README.md
git diff --cached --name-status --
git commit {option} -m unsafe
```
"""

    assert unsafe_git_commit_lines(text) == ((5, f"git commit {option} -m unsafe"),)


def test_unsafe_git_commit_lines_requires_observed_staged_diff() -> None:
    text = """```bash
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- README.md
git commit -m unreviewed-index
```
"""

    assert unsafe_git_commit_lines(text) == ((4, "git commit -m unreviewed-index"),)


def test_repository_git_workflow_markdown_is_safe() -> None:
    routing_files = [
        ROOT / "AGENTS.md",
        ROOT / "START_HERE.md",
        ROOT / "README.md",
        ROOT / "CODEX_MASTER_PROMPT.md",
        ROOT / "CODEX_RESUME_PROMPT.md",
        ROOT / "CODEX_REVIEW_PROMPT.md",
        ROOT / "HANDOFF_PACKAGE_MANIFEST.md",
        ROOT / "docs/implementation/QUALITY_LOOP.md",
        *sorted((ROOT / "prompts").glob("*.md")),
        *sorted((ROOT / "docs/superpowers/plans").glob("*.md")),
    ]
    errors: list[str] = []
    for path in routing_files:
        if not path.is_file():
            errors.append(f"missing routing file: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for label, violations in (
            ("unsafe stage", unsafe_git_stage_lines(text)),
            ("unguarded Git", unguarded_git_block_lines(text)),
            ("unsafe commit", unsafe_git_commit_lines(text)),
        ):
            errors.extend(
                f"{path.relative_to(ROOT)}:{line_number}: {label}: {line}"
                for line_number, line in violations
            )

    assert errors == []


def test_git_workflow_violations_reports_file_and_line(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.md"
    path.write_text("```bash\ngit add .\ngit commit -am unsafe\n```\n", encoding="utf-8")

    violations = git_workflow_violations(path)
    label = path.relative_to(ROOT)

    assert any(f"{label}:2: unsafe stage: git add ." == item for item in violations)
    assert any(f"{label}:2: unguarded Git: git add ." == item for item in violations)
    assert any(f"{label}:3: unsafe commit: git commit -am unsafe" == item for item in violations)
