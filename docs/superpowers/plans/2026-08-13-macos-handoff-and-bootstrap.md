# macOS Handoff and Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to execute this workstation-only plan step-by-step. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify the Windows-transferred FinProof handoff, establish a reproducible Apple Silicon macOS development environment, and preserve a clean Git baseline without starting product implementation.

**Architecture:** Treat official source files and frozen contracts as immutable inputs. Install the repository-declared Python toolchain, isolate dependencies in `.venv`, generate the required `uv.lock`, ignore transfer/build detritus, and prove the resulting workstation with the repository's full bootstrap checks.

**Tech Stack:** macOS 26 on Apple Silicon, Homebrew, Python 3.12, uv, Git, Ruff, mypy, pytest.

## Global Constraints

- Do not modify files under `source_material/` or frozen audit values.
- Do not begin Phase 1 production implementation during workstation bootstrap.
- Run `python tools/verify_handoff.py` and `python tools/audit_source_data.py --check` before relying on the transfer.
- Use Python `3.12`; the project rejects Python `3.14` through `requires-python = ">=3.12,<3.14"`.
- Keep generated virtual environments, caches, macOS metadata, and runtime artifacts out of Git.
- Record commands and observed results before claiming the workstation is ready.

---

### Task 1: Audit the transferred package

**Files:**
- Read: every repository file, including structured and binary source containers
- Verify: `source_material/input_manifest.json`
- Verify: `tests/contracts/expected_source_audit.json`

**Interfaces:**
- Consumes: the transferred repository tree
- Produces: an evidence-backed inventory, integrity result, and implementation-status assessment

- [x] **Step 1: Inventory tracked candidates and hidden transfer artifacts**

Run:

```bash
rg --files -uu -g '!.git/**'
find . -maxdepth 3 -name '.*' -print
```

Expected: all handoff files are visible; `.DS_Store`, Python bytecode, and temporary pytest directories are classified as generated transfer artifacts.

- [x] **Step 2: Verify the handoff contract and frozen source audit**

Run:

```bash
python3 tools/verify_handoff.py
python3 tools/audit_source_data.py --check
```

Expected: 61 required files, 9 official inputs, and 145,393 source rows at snapshot `2026-07-11`.

- [x] **Step 3: Compare documented progress with implementation contents**

Inspect `docs/implementation/STATUS.md`, the current Phase 1 plan, `src/`, `tests/`, `tools/`, `config/`, and `schemas/`. Confirm whether any production behavior exists beyond the handoff/audit scaffold.

---

### Task 2: Install and pin the macOS toolchain

**Files:**
- Create: `.python-version`
- Create: `uv.lock`
- Create: `.venv/` (ignored local environment)

**Interfaces:**
- Produces: `uv run python` at Python 3.12
- Produces: a resolver-generated, reproducible dependency lock

- [x] **Step 1: Install native Apple Silicon tools**

Run:

```bash
brew install uv python@3.12
```

Expected: `uv` and `/opt/homebrew/bin/python3.12` are available as arm64 binaries.

- [x] **Step 2: Pin Python and synchronize every dependency group**

Run:

```bash
uv python pin 3.12
uv sync --python /opt/homebrew/bin/python3.12 --all-groups
```

Expected: `.python-version`, `.venv`, and a resolver-generated `uv.lock` are created; `uv run python --version` reports Python 3.12.

---

### Task 3: Establish repository hygiene and Git baseline

**Files:**
- Create: `.gitignore`
- Create: `.git/` repository metadata
- Modify: `docs/implementation/STATUS.md`

**Interfaces:**
- Produces: an initial independently reviewable handoff/bootstrap commit
- Preserves: all official inputs and frozen contracts byte-for-byte

- [x] **Step 1: Add ignore rules for local and generated state**

Cover `.DS_Store`, `.venv`, Python/test/type/lint caches, coverage output, editor state, local secrets, temporary transfer directories, and generated DuckDB/Parquet data while permitting checked-in artifact manifests and reports when later required.

- [x] **Step 2: Verify ignore behavior before staging**

Run after Git initialization:

```bash
git check-ignore .DS_Store .venv pytest-cache-files-0o_6lfm9 tmp
git status --short
```

Expected: local artifacts are ignored and official inputs remain visible for the baseline commit.

- [x] **Step 3: Initialize and commit the verified baseline**

Run:

```bash
git init
git add .
git diff --cached --check
git commit -m "chore: bootstrap FinProof handoff on macOS"
```

Expected: one baseline commit with no ignored caches or local environment files.

---

### Task 4: Verify the bootstrapped workstation

**Files:**
- Modify: `docs/implementation/STATUS.md` with observed commands, results, risks, and the exact next task

**Interfaces:**
- Produces: current-session evidence for every mandatory bootstrap check

- [x] **Step 1: Run the project checks in the pinned environment**

Run:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run pytest -q
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
uv run python tools/extract_schema_catalog.py --check
```

Expected: all checks succeed on Python 3.12; any unexplained failure is a stop condition.

- [x] **Step 2: Inspect hook availability and final state**

Run:

```bash
test -f .pre-commit-config.yaml
git status --short --branch
git log -1 --oneline
```

Observed: the transferred handoff has no `.pre-commit-config.yaml`, despite its manifest claiming environment templates are included. A hook was therefore not installed or invented during migration. The missing configuration is recorded for Phase 1 Task 1; after the final audit commit, the working tree must be clean and the exact next product task remains Phase 1, Task 1.
