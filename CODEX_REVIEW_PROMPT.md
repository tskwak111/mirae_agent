# FinProof — Independent Review Prompt

Act as an adversarial senior reviewer. Do not implement new features during the first pass.

Read `AGENTS.md`, the frozen design, contracts, decision log, phase gates, and current status. Then inspect the implementation and tests. Verify behavior by running the required commands; do not rely on claims in documentation.

Review in this order:

1. competition compliance and prohibited LLM/dependency scan
2. source fidelity, checksums, row lineage, quarantine, and audit reproducibility
3. fund `itm_no` grain and attribute handling
4. ETF/ETN separation and state semantics, especially `pd_tr_yn = 0`
5. time/as-of semantics and bond maturity recalculation
6. metric zero/missing/tie/currency/period policies
7. QueryPlan schema, semantic validator, and SQL injection boundaries
8. entity resolution and prohibition on fuzzy automatic merges
9. evidence coverage and claim-verifier failure behavior
10. deterministic answer stability and exact API schema
11. error handling, redaction, timeout/retry/cache behavior
12. golden, differential, metamorphic, adversarial, load, and soak evidence
13. Docker/reproducibility/release-freeze readiness

Classify every finding as BLOCKER, HIGH, MEDIUM, or LOW. For each, cite exact file/line, demonstrate the failure with a command or test when possible, explain competition impact, and propose the smallest safe fix. Explicitly state which gates were run and their observed results.
