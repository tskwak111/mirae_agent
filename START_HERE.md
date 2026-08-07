# Start Here — Codex Handoff

## 1. Do not start by coding

Read, in order:

1. `AGENTS.md`
2. `docs/implementation/QUALITY_LOOP.md`
3. `docs/00_PROJECT_CHARTER.md`
4. `docs/01_OFFICIAL_REQUIREMENTS_TRACEABILITY.md`
5. `docs/02_FINAL_FROZEN_DESIGN.md`
6. `docs/03_DATA_AUDIT_BASELINE.md`
7. `docs/04_DATA_AND_DOMAIN_CONTRACTS.md`
8. `docs/05_QUERYPLAN_AND_API_CONTRACT.md`
9. `docs/06_METRIC_REGISTRY_POLICY.md`
10. `docs/07_TESTING_AND_EVALUATION.md`
11. `docs/implementation/STATUS.md`
12. the complete plan section for the one task selected by `STATUS.md`

## 2. Verify the package

```bash
python tools/check_repo_root.py --expected-root .
```

```bash
python tools/verify_handoff.py
python tools/audit_source_data.py --check
```

Both must pass before source-derived implementation work begins. A checksum or audit mismatch is a stop condition, not an invitation to update expected numbers.

## 3. Verify the repository boundary

This package must already be an exact project repository before an agent works in it:

```powershell
python tools/check_repo_root.py --expected-root .
git status --short
git branch --show-current
git log -3 --oneline
```

If the guard reports a missing repository, an ancestor repository, another worktree, or a
repository-selection environment variable, stop. Do not run `git init` or stage from that state.
A human/coordinator must first establish the empty private project repository at the exact
directory. After the exact-root and clean-index guard passes, the coordinator may use only the
frozen literal baseline import below. A worker agent is never authorized to improvise an initial
import or replace these paths with a directory operand.

<!-- INITIAL_IMPORT_START -->

```powershell
python tools/check_repo_root.py --expected-root . --require-clean-index
git add -- .gitattributes .editorconfig .env.example .github/workflows/ci.yml .gitignore .pre-commit-config.yaml .python-version AGENTS.md CODEX_MASTER_PROMPT.md CODEX_RESUME_PROMPT.md CODEX_REVIEW_PROMPT.md HANDOFF_PACKAGE_MANIFEST.md Makefile README.md START_HERE.md pyproject.toml
git add -- config/answer_policy.yaml config/datasets.yaml config/field_registry.yaml config/metric_registry.yaml config/planner_catalog.yaml config/quality_rules.yaml config/rating_scale.yaml config/state_rules.yaml
git add -- docs/00_PROJECT_CHARTER.md docs/01_OFFICIAL_REQUIREMENTS_TRACEABILITY.md docs/02_FINAL_FROZEN_DESIGN.md docs/03_DATA_AUDIT_BASELINE.md docs/04_DATA_AND_DOMAIN_CONTRACTS.md docs/05_QUERYPLAN_AND_API_CONTRACT.md docs/06_METRIC_REGISTRY_POLICY.md docs/07_TESTING_AND_EVALUATION.md docs/08_SECURITY_OPERATIONS_AND_RELEASE.md docs/09_RISK_REGISTER.md docs/10_DECISION_LOG.md docs/11_DEFINITION_OF_DONE.md docs/12_CODE_REVIEW_CHECKLIST.md docs/13_HANDOFF_VALIDATION_REPORT.md docs/implementation/PHASE_GATES.md docs/implementation/QUALITY_LOOP.md docs/implementation/STATUS.md docs/superpowers/plans/2026-08-07-00-roadmap.md docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md docs/superpowers/plans/2026-08-07-02-deterministic-query-engine.md docs/superpowers/plans/2026-08-07-03-hcx-planner-and-api.md docs/superpowers/plans/2026-08-07-04-evaluation-and-release.md docs/superpowers/plans/2026-08-07-preflight-safety-remediation.md docs/superpowers/plans/2026-08-07-preflight-task1-retry.md docs/superpowers/specs/2026-08-07-finproof-design.md docs/superpowers/specs/2026-08-07-preflight-safety-remediation-design.md docs/superpowers/specs/2026-08-07-preflight-task1-retry-design.md
git add -- docs/superpowers/plans/2026-08-08-preflight-task1-quote-retry.md docs/superpowers/specs/2026-08-08-preflight-task1-quote-retry-design.md
git add -- prompts/00_INITIAL_KICKOFF.md prompts/01_DATA_FOUNDATION.md prompts/02_QUERY_ENGINE.md prompts/03_HCX_AND_API.md prompts/04_EVALUATION_AND_RELEASE.md prompts/99_CODE_REVIEW.md
git add -- schemas/api_response.schema.json schemas/artifact_manifest.schema.json schemas/evidence_record.schema.json schemas/execution_trace.schema.json schemas/golden_case.schema.json schemas/hcx_query_plan.schema.json schemas/quality_issue.schema.json schemas/query_plan.schema.json
git add -- source_material/README.md source_material/competition_task_financial_product_agent.pdf source_material/data/PRBD01N001_domestic_bonds_20260711_datarows.xlsx source_material/data/PRBD01N001_schema.xlsx source_material/data/PREF01N001_domestic_etf_20260711_datarows.xlsx source_material/data/PREF01N001_schema.xlsx source_material/data/PREF02N001_overseas_etf_20260711_datarows.xlsx source_material/data/PREF02N001_schema.xlsx source_material/data/PRFD01N001_public_funds_20260711_datarows.xlsx source_material/data/PRFD01N001_schema.xlsx source_material/input_manifest.json source_material/schema_catalog.json
git add -- src/finproof/__init__.py src/finproof/py.typed
git add -- tests/__init__.py tests/contract/__init__.py tests/contract/test_handoff_package.py tests/contract/test_repo_root_guard.py tests/contracts/README.md tests/contracts/expected_source_audit.json tests/golden/README.md tests/golden/seed_cases.jsonl
git add -- tools/__init__.py tools/audit_source_data.py tools/check_repo_root.py tools/create_input_manifest.py tools/extract_schema_catalog.py tools/verify_handoff.py tools/xlsx_stream.py
git diff --cached --name-status --
git commit -m "chore: import FinProof handoff baseline"
```

<!-- INITIAL_IMPORT_END -->

After the baseline commit, use an isolated `codex/` branch or linked worktree for each selected
task.

## 4. Bootstrap dependencies

```bash
uv sync --all-groups
uv run pre-commit install
```

The handoff intentionally does not fabricate a lock file: its creation environment had no registry access. Generate and commit `uv.lock` in the first network-enabled bootstrap, change CI to `uv sync --frozen --all-groups`, and use frozen sync afterward.

## 5. Start Codex

Paste the full contents of `CODEX_MASTER_PROMPT.md` into the first Codex session. Do not replace it with “build this project.” The prompt intentionally forces source verification, phase boundaries, TDD, review gates, and status updates.

For later sessions, use `CODEX_RESUME_PROMPT.md`. For an independent final audit, use `CODEX_REVIEW_PROMPT.md` in a fresh context.

## 6. Phase order

1. Repository and data foundation
2. Deterministic query/evidence engine
3. HyperCLOVA X planner and evaluation API
4. Evaluation, hardening, and release freeze

Do not start UI, GraphDB, runtime/product multi-agent architecture, live external data, portfolio
optimization, or personalized recommendations before all P0 phase gates pass. Safe development
fan-out is governed separately by `QUALITY_LOOP.md`.

## 7. Human review gates

A human should inspect after every phase:

- source fidelity and data policy changes
- public-fund grain behavior
- state/eligibility semantics
- metric zero/tie/currency behavior
- generated SQL allowlists
- evidence coverage
- exact API schema
- competition compliance and LLM dependencies

## 8. Current task

The single task named under `Current next task` in `docs/implementation/STATUS.md` is authoritative.
Do not infer a phase-local task from a prompt, plan filename, or remaining context.
