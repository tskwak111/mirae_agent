# FinProof Codex Handoff Package Manifest

## Give these to Codex

The preferred delivery is the whole repository. The minimum required set is:

1. `AGENTS.md` — non-negotiable engineering and competition contract.
2. `START_HERE.md` — exact startup order.
3. `docs/implementation/QUALITY_LOOP.md` — normative task, fan-out, TDD, review, and Git contract.
4. `CODEX_MASTER_PROMPT.md` — first-session router.
5. `CODEX_RESUME_PROMPT.md` — later-session continuation router.
6. `CODEX_REVIEW_PROMPT.md` — fresh-context independent audit router.
7. `docs/` — package-content summary only; never a staging operand.
8. `config/` — package-content summary only; never a staging operand.
9. `schemas/` — package-content summary only; never a staging operand.
10. `source_material/` — package-content summary only; never a staging operand.
11. `tools/` and `tests/contracts/` — package-content summary only; never staging operands.
12. `pyproject.toml`, `Makefile`, CI, and environment templates — reproducible engineering environment. Generate and commit `uv.lock` during the first network-enabled bootstrap.
13. `prompts/` — task-routing and independent-review prompts.
14. `tools/check_repo_root.py`, `tests/contract/test_repo_root_guard.py`, and the dated Preflight
    designs/plans — executable repository-boundary protection and its bounded retry record.

Do not give Codex only a prose summary or only the source workbooks. The contracts, registries, tests, and phase plans are what prevent design drift.

## Frozen literal initial import

These commands are duplicated in `START_HERE.md` so a human coordinator can compare them before
the one-time baseline import. They run only after the exact private repository exists and the guard
passes. Directory substitution, globbing, variables, pathspec magic, and worker-agent improvisation
are prohibited.

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

## First command sequence

```bash
cat START_HERE.md
cat AGENTS.md
cat docs/implementation/QUALITY_LOOP.md
```

```bash
python tools/check_repo_root.py --expected-root .
```

```bash
python tools/verify_handoff.py
python tools/audit_source_data.py --check
uv sync --all-groups
uv run pytest -q
```

Then paste `CODEX_MASTER_PROMPT.md` and let Codex execute only the task selected in
`docs/implementation/STATUS.md`.

## Session discipline

- `docs/implementation/QUALITY_LOOP.md` governs task scope, fan-out, role separation, retries,
  staging, verification, and durable handoff.
- Exactly one selected `STATUS.md` task per session; phase prompts cannot select work themselves.
- Use `CODEX_RESUME_PROMPT.md` for continuation and a fresh verifier context for every candidate.
- `STATUS.md` and allowlisted Git commits are the durable record; phase gates remain mandatory.
