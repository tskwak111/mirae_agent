#!/usr/bin/env python3
"""Verify that the Codex handoff is complete, internally consistent, and unmodified."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any, Final

yaml: ModuleType | None
try:
    import yaml as yaml_module
except ModuleNotFoundError:  # pragma: no cover - bootstrap without dependencies
    yaml = None
else:
    yaml = yaml_module

if __package__:
    from .extract_schema_catalog import build_catalog
    from .xlsx_stream import list_sheet_names
else:
    from extract_schema_catalog import build_catalog
    from xlsx_stream import list_sheet_names

ROOT: Final = Path(__file__).resolve().parents[1]

EXECUTABLE_FENCE_LABELS: Final = {
    "bash",
    "ps1",
    "powershell",
    "pwsh",
    "sh",
    "shell",
    "zsh",
}
INERT_FENCE_LABELS: Final = {
    "json",
    "markdown",
    "md",
    "plaintext",
    "py",
    "python",
    "text",
    "toml",
    "txt",
    "yaml",
    "yml",
}
BROAD_STAGE_TARGETS: Final = {
    "config",
    "docs",
    "prompts",
    "release",
    "schemas",
    "source_material",
    "src",
    "tests",
    "tools",
}
MUTATING_GIT_SUBCOMMANDS: Final = {
    "add",
    "branch",
    "checkout",
    "clean",
    "clone",
    "commit",
    "init",
    "merge",
    "mv",
    "pull",
    "push",
    "rebase",
    "reset",
    "restore",
    "rm",
    "stage",
    "stash",
    "switch",
    "tag",
    "worktree",
}

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
    "docs/implementation/QUALITY_LOOP.md",
    "docs/implementation/PHASE_GATES.md",
    "docs/superpowers/specs/2026-08-07-finproof-design.md",
    "docs/superpowers/specs/2026-08-07-preflight-safety-remediation-design.md",
    "docs/superpowers/plans/2026-08-07-00-roadmap.md",
    "docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md",
    "docs/superpowers/plans/2026-08-07-02-deterministic-query-engine.md",
    "docs/superpowers/plans/2026-08-07-03-hcx-planner-and-api.md",
    "docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md",
    "docs/superpowers/plans/2026-08-07-preflight-safety-remediation.md",
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
    "tests/contract/test_repo_root_guard.py",
    "tools/__init__.py",
    "tools/audit_source_data.py",
    "tools/check_repo_root.py",
    "tools/extract_schema_catalog.py",
    "tools/xlsx_stream.py",
    "prompts/00_INITIAL_KICKOFF.md",
    "prompts/01_DATA_FOUNDATION.md",
    "prompts/02_QUERY_ENGINE.md",
    "prompts/03_HCX_AND_API.md",
    "prompts/04_EVALUATION_AND_RELEASE.md",
    "prompts/99_CODE_REVIEW.md",
)


def _fence_label(info: str) -> str:
    if not info.strip():
        return ""
    first = info.strip().split(maxsplit=1)[0].lower()
    if first.startswith("{."):
        match = re.search(r"\.([A-Za-z0-9_-]+)", first)
        return match.group(1).lower() if match else ""
    return first.removeprefix(".")


def _should_scan_fence(label: str, block: list[tuple[int, str]]) -> bool:
    if label in EXECUTABLE_FENCE_LABELS:
        return True
    if label in INERT_FENCE_LABELS:
        return False
    return any(_contains_git_command(line) for _, line in block)


def _shell_blocks(text: str) -> Iterator[tuple[tuple[int, str], ...]]:
    block: list[tuple[int, str]] = []
    in_fence = False
    fence_length = 0
    fence_character = ""
    label = ""
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not in_fence:
            match = re.fullmatch(
                r" {0,3}(?P<fence>`{3,}|~{3,})(?P<info>[^\r\n]*)",
                line,
            )
            if match:
                in_fence = True
                fence_length = len(match.group("fence"))
                fence_character = match.group("fence")[0]
                label = _fence_label(match.group("info"))
                block = []
            continue
        if re.fullmatch(
            rf" {{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*",
            line,
        ):
            if _should_scan_fence(label, block):
                yield tuple(block)
            in_fence = False
            fence_length = 0
            fence_character = ""
            label = ""
            block = []
            continue
        block.append((line_number, line))
    if in_fence and _should_scan_fence(label, block):
        yield tuple(block)


def _shell_tokens(line: str) -> tuple[str, ...] | None:
    try:
        return tuple(shlex.split(line, comments=True, posix=True))
    except ValueError:
        return None


def _contains_git_command(line: str) -> bool:
    tokens = _shell_tokens(line)
    if tokens is None:
        return bool(re.search(r"(?i)(?:^|[\s;&|])git(?:\.exe)?(?=\s|$)", line))
    if not tokens:
        return False
    return any(token.lower() in {"git", "git.exe"} for token in tokens)


def _contains_git_subcommand(line: str, subcommand: str) -> bool:
    tokens = _shell_tokens(line)
    if not tokens:
        return bool(re.search(rf"(?i)(?:^|\s)git(?:\.exe)?\b.*\b{re.escape(subcommand)}\b", line))
    for index, token in enumerate(tokens):
        if token.lower() not in {"git", "git.exe"}:
            continue
        return any(item.lower() == subcommand for item in tokens[index + 1 :])
    return False


def _literal_stage_path(path: str) -> bool:
    if not path or not path.isascii() or path.casefold() in BROAD_STAGE_TARGETS:
        return False
    if path.startswith(("/", "\\", "~", "-", ":")):
        return False
    if "\\" in path or re.match(r"^[A-Za-z]:", path):
        return False
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", path):
        return False
    parts = path.split("/")
    return all(part not in {"", ".", ".."} for part in parts)


def _is_canonical_stage(line: str) -> bool:
    if any(marker in line for marker in (";", "|", "&", "`", "'", '"')):
        return False
    if line.rstrip().endswith("\\") or "\\" in line:
        return False
    tokens = _shell_tokens(line)
    if tokens is None or len(tokens) < 4 or tokens[:3] != ("git", "add", "--"):
        return False
    return all(_literal_stage_path(path) for path in tokens[3:])


def _is_root_guard(line: str, *, require_clean_index: bool = False) -> bool:
    tokens = _shell_tokens(line)
    if not tokens or tokens[:4] != (
        "python",
        "tools/check_repo_root.py",
        "--expected-root",
        ".",
    ):
        return False
    extras = tokens[4:]
    if any(argument != "--require-clean-index" for argument in extras):
        return False
    return not require_clean_index or "--require-clean-index" in extras


def _is_unsafe_git_invocation(line: str) -> bool:
    tokens = _shell_tokens(line)
    if not tokens:
        return _contains_git_command(line)
    git_indexes = [
        index for index, token in enumerate(tokens) if token.lower() in {"git", "git.exe"}
    ]
    if not git_indexes:
        return False
    if git_indexes[0] != 0 or tokens[0] != "git":
        return True
    if re.search(r"(?i)\bGIT_[A-Z0-9_]+\s*=", line):
        return True
    if any(marker in line for marker in (";", "&&", "||", "`")):
        return True
    return any(
        argument == "-C" or argument.startswith("--git-dir") or argument.startswith("--work-tree")
        for argument in tokens[1:]
    )


def _is_mutating_git_line(line: str) -> bool:
    tokens = _shell_tokens(line)
    if tokens == ("git", "branch", "--show-current"):
        return False
    return any(_contains_git_subcommand(line, command) for command in MUTATING_GIT_SUBCOMMANDS)


def _is_executable_line(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped and not stripped.startswith("#"))


def unsafe_git_stage_lines(text: str) -> tuple[tuple[int, str], ...]:
    """Return noncanonical staging commands from executable Markdown fences."""
    violations: list[tuple[int, str]] = []
    for block in _shell_blocks(text):
        for line_number, line in block:
            if (
                _contains_git_subcommand(line, "add")
                or _contains_git_subcommand(line, "stage")
                or ("alias." in line and _contains_git_command(line))
            ) and not _is_canonical_stage(line):
                violations.append((line_number, line.strip()))
    return tuple(violations)


def unguarded_git_block_lines(text: str) -> tuple[tuple[int, str], ...]:
    """Return Git commands whose shell block lacks a still-valid exact-root guard."""
    violations: list[tuple[int, str]] = []
    directory_change = re.compile(r"(?i)^(?:cd|chdir|set-location|push-location|pop-location)\b")
    for block in _shell_blocks(text):
        git_lines = [item for item in block if _contains_git_command(item[1])]
        if not git_lines:
            continue
        executable = [item for item in block if _is_executable_line(item[1])]
        mutation = any(_is_mutating_git_line(line) for _, line in git_lines)
        first_is_guard = bool(executable and _is_root_guard(executable[0][1].strip()))
        clean_guard = bool(
            executable and _is_root_guard(executable[0][1].strip(), require_clean_index=True)
        )
        context_valid = first_is_guard and (not mutation or clean_guard)
        for line_number, line in block:
            stripped = line.strip()
            if directory_change.search(stripped):
                context_valid = False
                continue
            if not _contains_git_command(stripped):
                continue
            if not context_valid or _is_unsafe_git_invocation(stripped):
                violations.append((line_number, stripped))
    return tuple(violations)


def _is_staged_diff_review(line: str) -> bool:
    tokens = _shell_tokens(line)
    return tokens == ("git", "diff", "--cached", "--name-status", "--")


def _has_auto_stage_option(tokens: tuple[str, ...]) -> bool:
    for token in tokens[2:]:
        if token in {"-a", "--all", "-i", "--include", "-o", "--only"}:
            return True
        if token.startswith(("--include=", "--only=")):
            return True
        if re.fullmatch(r"-[^-]+", token) and "a" in token[1:]:
            return True
    return False


def unsafe_git_commit_lines(text: str) -> tuple[tuple[int, str], ...]:
    """Return commits that can absorb paths outside the declared staging command."""
    violations: list[tuple[int, str]] = []
    for block in _shell_blocks(text):
        clean_guard_seen = False
        safe_stage_after_guard = False
        staged_diff_reviewed = False
        for line_number, line in block:
            stripped = line.strip()
            if _is_root_guard(stripped, require_clean_index=True):
                clean_guard_seen = True
                safe_stage_after_guard = False
                staged_diff_reviewed = False
                continue
            if _contains_git_subcommand(stripped, "add") or _contains_git_subcommand(
                stripped, "stage"
            ):
                safe_stage_after_guard = clean_guard_seen and _is_canonical_stage(stripped)
                staged_diff_reviewed = False
                continue
            if safe_stage_after_guard and _is_staged_diff_review(stripped):
                staged_diff_reviewed = True
                continue
            if not _contains_git_subcommand(stripped, "commit"):
                continue
            tokens = _shell_tokens(stripped)
            canonical_commit = bool(tokens and tokens[:2] == ("git", "commit"))
            unsafe_option = bool(tokens and _has_auto_stage_option(tokens))
            if (
                not clean_guard_seen
                or not safe_stage_after_guard
                or not staged_diff_reviewed
                or not canonical_commit
                or unsafe_option
            ):
                violations.append((line_number, stripped))
    return tuple(violations)


def git_workflow_violations(path: Path) -> tuple[str, ...]:
    """Return actionable Git-workflow contract violations for one Markdown file."""
    text = path.read_text(encoding="utf-8")
    try:
        label = str(path.relative_to(ROOT))
    except ValueError:
        label = str(path)
    violations: list[str] = []
    for kind, lines in (
        ("unsafe stage", unsafe_git_stage_lines(text)),
        ("unguarded Git", unguarded_git_block_lines(text)),
        ("unsafe commit", unsafe_git_commit_lines(text)),
    ):
        violations.extend(f"{label}:{line_number}: {kind}: {line}" for line_number, line in lines)
    return tuple(violations)


def verify_git_workflow_markdown(errors: list[str]) -> None:
    """Verify every repository routing surface and implementation plan."""
    paths = [
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
    for path in paths:
        if path.is_file():
            errors.extend(git_workflow_violations(path))


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
    required = {
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
    if query_path.is_file():
        query = load_json(query_path)
        if set(query.get("required", [])) != required:
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
        if set(provider.get("required", [])) != required:
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
        if yaml is not None:
            try:
                document = yaml.safe_load(text)
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
    verify_git_workflow_markdown(errors)
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
    if yaml is None:
        print(
            "Note: PyYAML unavailable; bootstrap verification performed "
            "non-parser YAML checks only."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
