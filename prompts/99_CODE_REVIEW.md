# Codex Prompt 99 — Independent Adversarial Review

Act as an independent senior reviewer. Do not assume prior implementation claims are true. Read `AGENTS.md`, the frozen design, requirement traceability, current phase gate, risk register, definition of done, and `docs/12_CODE_REVIEW_CHECKLIST.md`.

First inspect the diff and repository history. Then run the applicable verification, source-audit, format, lint, type, unit, integration, contract, differential, adversarial, performance, or reproduction commands. Review for:

- official-requirement drift and unauthorized LLM providers;
- source mutation, lineage loss, fund-grain mistakes, ETF/ETN leakage, time/state errors;
- zero/tie/currency/period policy errors;
- SQL injection, free-form SQL, fuzzy auto-merge, prompt injection, secret leakage;
- unsupported numeric or recommendation claims;
- missing evidence or verifier bypass;
- API schema drift, unbounded retries/timeouts/concurrency, and brittle deployment;
- tests that pass without proving behavior or baselines weakened to hide defects.

Report findings first, ordered BLOCKER, HIGH, MEDIUM, LOW, with exact file/line references, reproduction steps, and the violated contract. Do not modify code until findings are recorded. If authorized to fix, fix one finding at a time with a failing regression test first, rerun the full relevant gate, update status, and commit separately.
