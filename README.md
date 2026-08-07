# FinProof

**FinProof** is an evidence-first financial-product analysis agent for the 2026 Mirae Asset Securities AI Festival.

> HyperCLOVA X plans. Deterministic code executes. Evidence proves. Verification blocks unsupported claims.

This repository is an implementation handoff package. It contains the official task PDF and eight source workbooks, frozen architecture and data policies, machine-readable registries and JSON Schemas, source-audit tools, TDD implementation plans, and Codex kickoff/review prompts.

## Start

```bash
cat START_HERE.md
cat AGENTS.md
cat CODEX_MASTER_PROMPT.md
python tools/verify_handoff.py
python tools/audit_source_data.py --check
```

Then give `CODEX_MASTER_PROMPT.md` to Codex and execute the first incomplete phase in `docs/implementation/STATUS.md`.

## Core constraints

- HyperCLOVA X is the only generative LLM in evaluation/runtime code.
- Official source data remains immutable and has priority over external data.
- Search, filters, ranking, aggregation, calculations, evidence, and verification are deterministic.
- Public-fund default grain is `itm_no`.
- ETF queries exclude ETNs unless explicitly included.
- “Current” means the `2026-07-11` snapshot.
- No direct cross-currency AUM ranking without a fixed FX snapshot.
- Heterogeneous product queries use a `product` envelope, explicit `top_k_scope`, and native execution segments.
- No free-form Text-to-SQL and no fuzzy automatic product merge.
- The evaluation API returns exactly the organizer’s five string fields unless officially changed.

## Repository map

```text
AGENTS.md                       repository-wide engineering contract
CODEX_MASTER_PROMPT.md          first Codex session prompt
CODEX_RESUME_PROMPT.md          later-session continuation prompt
CODEX_REVIEW_PROMPT.md          independent review prompt
docs/                           design, contracts, plans, risks, validation, definition of done
config/                         versioned dataset/metric/state/quality/answer policies
schemas/                        JSON contracts for plans, evidence, trace, API
source_material/                official PDF, workbooks, checksums, schema catalog
tools/                          handoff/source audit and schema extraction utilities
tests/contracts/                immutable source baseline
tests/golden/                   seed evaluation cases and authoring rules
src/finproof/                   production package scaffold
```

## Delivery philosophy

Do not build the whole system in a single uncontrolled run. Complete one phase, run its gate, review the diff, commit, and update status. The phase plans are written so a new agent can resume without relying on chat memory.

## Handoff verification status

See `docs/13_HANDOFF_VALIDATION_REPORT.md` for the exact commands that passed and the implementation/release checks that remain pending. A dependency lock must be generated and committed in the first network-enabled bootstrap.
