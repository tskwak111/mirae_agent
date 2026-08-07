# Codex Prompt 01 — Data Foundation

Implement the first incomplete task in `docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md` only.

Before editing, read `AGENTS.md`, `docs/02_FINAL_FROZEN_DESIGN.md`, `docs/03_DATA_AUDIT_BASELINE.md`, `docs/04_DATA_AND_DOMAIN_CONTRACTS.md`, `docs/implementation/STATUS.md`, and the entire Phase 1 plan. Run the handoff and source-audit checks.

Use strict TDD. Preserve all raw source values and row lineage. Never change the expected source audit to accommodate implementation errors. Public-fund normalization must keep `itm_no` as the default product grain and `prfd_attr_cd` as a many-valued attribute. The malformed source row must be preserved in Bronze lineage and explicitly quarantined from normal results. Build deterministic, versioned artifacts only.

End after one independently reviewable task. Run its focused tests plus required quality checks, update status with actual command results, commit, and report the exact next task.
