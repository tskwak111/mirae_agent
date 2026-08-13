# Phase 1 Task 1 Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the typed FinProof settings/version/error core, deterministic bootstrap CLI, and the missing environment, pre-commit, and Linux CI contracts without starting source ingestion.

**Architecture:** Pydantic owns external and cross-module settings/version contracts; `argparse` dispatches directly to the existing importable verification tools. Repository automation consumes the checked-in uv lock on Python 3.12 and runs the same deterministic gates used locally.

**Tech Stack:** Python 3.12, Pydantic 2, pydantic-settings, argparse, pytest, Ruff 0.15.22, mypy, pre-commit 4, uv 0.12.3, GitHub Actions.

## Global Constraints

- Execute only Phase 1 Task 1; do not implement data ingestion or product behavior.
- Official source files and frozen audit values remain byte-identical.
- Dataset snapshot date is exactly `2026-07-11`.
- Evaluation mode is the default; no external model credential is needed.
- Every production behavior is implemented after its focused test fails for the expected reason.
- Use `uv sync --frozen --all-groups`; never regenerate the lock in this task.
- The CLI invokes Python functions in-process and never shells out.
- `.env.example` contains names and safe defaults only.

---

### Task 1: Typed settings and domain errors

**Files:**
- Create: `src/finproof/core/__init__.py`
- Create: `src/finproof/core/settings.py`
- Create: `src/finproof/core/errors.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/core/__init__.py`
- Create: `tests/unit/core/test_settings.py`

**Interfaces:**
- Produces: `ExecutionMode(StrEnum)` with `EVALUATION` and `EXTENDED_DEMO`
- Produces: `Settings(BaseSettings)` with frozen snapshot/path/top-k defaults
- Produces: `FinProofError` and `SourceContractError`

- [x] **Step 1: Write failing settings tests**

Create tests for the real settings boundary:

```python
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from finproof.core.settings import ExecutionMode, Settings


def test_settings_use_frozen_evaluation_defaults(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "source",
        artifact_dir=tmp_path / "artifacts",
        database_path=tmp_path / "artifacts/finproof.duckdb",
        _env_file=None,
    )
    assert settings.dataset_snapshot_date == date(2026, 7, 11)
    assert settings.execution_mode is ExecutionMode.EVALUATION
    assert settings.default_top_k == 5
    assert settings.max_top_k == 50


def test_settings_reject_default_top_k_above_maximum() -> None:
    with pytest.raises(ValidationError, match="default_top_k"):
        Settings(default_top_k=51, max_top_k=50, _env_file=None)


def test_settings_parse_prefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FINPROOF_EXECUTION_MODE", "extended_demo")
    monkeypatch.setenv("FINPROOF_DEFAULT_TOP_K", "7")
    settings = Settings(_env_file=None)
    assert settings.execution_mode is ExecutionMode.EXTENDED_DEMO
    assert settings.default_top_k == 7
```

- [x] **Step 2: Run the focused tests and confirm RED**

Run: `uv run pytest tests/unit/core/test_settings.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'finproof.core'`.

- [x] **Step 3: Implement the minimum typed settings and errors**

Use `SettingsConfigDict(env_prefix="FINPROOF_", env_file=".env", extra="ignore")`, typed `Path` fields, Pydantic `Field` bounds, and an `after` model validator that rejects `default_top_k > max_top_k`. Do not create directories during model construction.

```python
class FinProofError(Exception):
    """Base FinProof application error."""


class SourceContractError(FinProofError):
    """Official source data violated a frozen contract."""
```

- [x] **Step 4: Run GREEN and static checks**

Run:

```bash
uv run pytest tests/unit/core/test_settings.py -q
uv run ruff check src/finproof/core tests/unit/core
uv run mypy src/finproof/core tests/unit/core
```

Expected: 3 tests pass and both static checks exit zero.

- [x] **Step 5: Commit the settings checkpoint**

```bash
git add src/finproof/core tests/unit
git commit -m "feat: add typed FinProof settings"
```

---

### Task 2: Immutable version bundle

**Files:**
- Create: `src/finproof/core/versions.py`
- Create: `tests/unit/core/test_versions.py`

**Interfaces:**
- Produces: `VersionBundle(BaseModel)` with `dataset_version: date`
- Produces version strings: `metric_registry_version`, `state_rule_version`, `quality_rule_version`, `rating_rule_version`, `answer_policy_version`, and `planner_version`

- [x] **Step 1: Write failing version tests**

```python
from datetime import date

import pytest
from pydantic import ValidationError

from finproof.core.versions import VersionBundle


def test_version_bundle_defaults_match_checked_in_contracts() -> None:
    bundle = VersionBundle()
    assert bundle.model_dump(mode="json") == {
        "answer_policy_version": "1.0.0",
        "dataset_version": "2026-07-11",
        "metric_registry_version": "1.0.0",
        "planner_version": "1.0.0",
        "quality_rule_version": "1.0.0",
        "rating_rule_version": "1.0.0",
        "state_rule_version": "1.0.0",
    }


def test_version_bundle_is_immutable() -> None:
    bundle = VersionBundle()
    with pytest.raises(ValidationError):
        bundle.dataset_version = date(2026, 7, 12)  # type: ignore[misc]
```

- [x] **Step 2: Run the focused tests and confirm RED**

Run: `uv run pytest tests/unit/core/test_versions.py -q`

Expected: collection fails because `finproof.core.versions` is missing.

- [x] **Step 3: Implement the frozen model**

Use `ConfigDict(frozen=True, extra="forbid")`, `date(2026, 7, 11)`, and literal default version strings of `1.0.0` matching the eight checked-in versioned configurations. Registry loading remains Phase 2 Task 1.

- [x] **Step 4: Run GREEN and relevant suite**

Run: `uv run pytest tests/unit/core -q`

Expected: 5 tests pass.

- [x] **Step 5: Commit the version checkpoint**

```bash
git add src/finproof/core/versions.py tests/unit/core/test_versions.py
git commit -m "feat: add immutable FinProof versions"
```

---

### Task 3: Deterministic CLI dispatch

**Files:**
- Create: `src/finproof/cli/__init__.py`
- Create: `src/finproof/cli/main.py`
- Create: `tests/contract/test_handoff_commands.py`

**Interfaces:**
- Consumes: `tools.verify_handoff.main() -> int`
- Consumes: `tools.audit_source_data.main(argv: list[str] | None = None) -> int`
- Consumes: `VersionBundle().model_dump(mode="json")`
- Produces: `main(argv: Sequence[str] | None = None) -> int`

- [x] **Step 1: Write the failing CLI tests**

```python
import json

from finproof.cli.main import main


def test_show_versions_emits_deterministic_json(capsys) -> None:
    assert main(["show-versions"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dataset_version"] == "2026-07-11"
    assert payload["planner_version"] == "1.0.0"


def test_verify_handoff_runs_real_verifier(capsys) -> None:
    assert main(["verify-handoff"]) == 0
    assert "FinProof handoff PASS" in capsys.readouterr().out


def test_audit_source_runs_frozen_check(capsys) -> None:
    assert main(["audit-source"]) == 0
    assert "145,393 rows" in capsys.readouterr().out
```

- [x] **Step 2: Run the focused tests and confirm RED**

Run: `uv run pytest tests/contract/test_handoff_commands.py -q`

Expected: collection fails because `finproof.cli.main` is missing.

- [x] **Step 3: Implement minimal argparse dispatch**

Build a parser with required subcommands. Render versions using `json.dumps(..., ensure_ascii=False, sort_keys=True)` and a trailing newline. Call `verify_handoff.main()` and `audit_source_data.main(["--check"])` directly. Catch only `FinProofError`, print `error: <message>` to stderr, and return `2`; do not catch unexpected exceptions.

- [x] **Step 4: Run GREEN through both interfaces**

Run:

```bash
uv run pytest tests/contract/test_handoff_commands.py -q
uv run finproof show-versions
uv run finproof verify-handoff
uv run finproof audit-source
```

Expected: 3 tests pass, versions contain `2026-07-11`, and both official checks exit zero.

- [x] **Step 5: Commit the CLI checkpoint**

```bash
git add src/finproof/cli tests/contract/test_handoff_commands.py
git commit -m "feat: add FinProof bootstrap CLI"
```

---

### Task 4: Environment, pre-commit, and Linux CI contracts

**Files:**
- Create: `.env.example`
- Create: `.pre-commit-config.yaml`
- Create: `.github/workflows/ci.yml`
- Create: `tests/contract/test_repository_automation.py`
- Modify: `docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md`

**Interfaces:**
- Consumes: `Settings(_env_file=Path(".env.example"))`
- Produces: a valid pre-commit configuration using Ruff `v0.15.22`
- Produces: GitHub Actions on Ubuntu/Python 3.12 with frozen uv installation and all mandatory checks

- [x] **Step 1: Amend the original Task 1 file scope before behavior depends on it**

Add `.env.example`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, and `tests/contract/test_repository_automation.py` to the Task 1 file list. Add the automation contract test and `uv run pre-commit run --all-files` to its task checks. Do not mark Task 1 complete yet.

- [x] **Step 2: Write failing executable automation tests**

Test these observable contracts:

```python
from pathlib import Path

import yaml

from finproof.core.settings import ExecutionMode, Settings

ROOT = Path(__file__).resolve().parents[2]


def test_environment_example_loads_without_secrets() -> None:
    settings = Settings(_env_file=ROOT / ".env.example")
    assert settings.execution_mode is ExecutionMode.EVALUATION
    assert settings.dataset_snapshot_date.isoformat() == "2026-07-11"


def test_ci_runs_the_required_frozen_checks() -> None:
    workflow = yaml.load(
        (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    steps = workflow["jobs"]["quality"]["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)
    assert "uv sync --frozen --all-groups" in commands
    assert "uv run pytest -q" in commands
    assert "tools/audit_source_data.py --check" in commands
    assert "tools/verify_handoff.py" in commands
```

The production/configuration changes that make these tests pass are the three missing files; the tests fail if those files are missing or if CI drops a mandatory source gate.

- [x] **Step 3: Run the focused tests and confirm RED**

Run: `uv run pytest tests/contract/test_repository_automation.py -q`

Expected: failures report missing `.env.example` and `.github/workflows/ci.yml`.

- [x] **Step 4: Add the minimal safe environment template**

Use only these non-secret variables:

```dotenv
FINPROOF_EXECUTION_MODE=evaluation
FINPROOF_DATASET_SNAPSHOT_DATE=2026-07-11
FINPROOF_DATA_DIR=source_material/data
FINPROOF_ARTIFACT_DIR=artifacts
FINPROOF_DATABASE_PATH=artifacts/finproof.duckdb
FINPROOF_DEFAULT_TOP_K=5
FINPROOF_MAX_TOP_K=50
```

- [x] **Step 5: Add pre-commit and CI**

Pin `astral-sh/ruff-pre-commit` at `v0.15.22` with `ruff-check` and `ruff-format --check`. CI uses `actions/checkout@v6`, `actions/setup-python@v6` with `3.12`, and `astral-sh/setup-uv` at the official v9.0.0 commit `c771a70e6277c0a99b617c7a806ffedaca235ff9`, installing uv `0.12.3`. Set `permissions: contents: read`, disable credential persistence on checkout, and run every acceptance command from the design.

- [x] **Step 6: Run GREEN and validate hooks**

Run:

```bash
uv run pytest tests/contract/test_repository_automation.py -q
uv run pre-commit validate-config
uv run pre-commit run --all-files
```

Expected: 2 tests pass, configuration validates, and hooks exit zero without modifying files.

- [x] **Step 7: Commit the automation checkpoint**

```bash
git add .env.example .pre-commit-config.yaml .github/workflows/ci.yml tests/contract/test_repository_automation.py docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md
git commit -m "ci: add frozen FinProof quality gates"
```

---

### Task 5: Final status, independent verification, and handoff

**Files:**
- Modify: `docs/implementation/STATUS.md`
- Modify: this plan's checkboxes

**Interfaces:**
- Produces: durable RED/GREEN evidence, exact commit hashes, unresolved risks, and `Phase 1 Task 2` as the next task

- [x] **Step 1: Run the complete Task 1 and repository gates**

Run:

```bash
uv sync --frozen --all-groups
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run pytest -q
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
uv run python tools/extract_schema_catalog.py --check
uv run finproof show-versions
uv run finproof verify-handoff
uv run finproof audit-source
uv run pre-commit run --all-files
git diff --check
```

Expected: every command exits zero; source audit remains 145,393 rows at `2026-07-11`, handoff remains 9 official inputs and 41,384,928 bytes, and the schema catalog remains 207 columns.

- [x] **Step 2: Update status without advancing the Phase 1 gate**

Mark only Phase 1 Task 1 complete. Record every focused RED reason, GREEN result, final command output, commits, the local/CI validation distinction, and exact next task `Phase 1 Task 2: implement source manifest and streaming workbook reader with row lineage`.

- [x] **Step 3: Run documentation and worktree checks**

Run:

```bash
git diff --check
git status --short
```

Expected: only intentional status/plan changes remain before the final documentation commit.

- [x] **Step 4: Commit the final Task 1 record**

```bash
git add docs/implementation/STATUS.md docs/superpowers/plans/2026-08-13-phase1-task1-bootstrap.md
git commit -m "docs: record Phase 1 Task 1 completion"
```

- [x] **Step 5: Verify the committed tree and report**

Rerun the complete gate from Step 1, confirm `git status --porcelain=v1` is empty, and report exact outputs and commit hashes. Do not mark the Phase 1 gate complete.
