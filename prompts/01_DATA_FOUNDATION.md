# Codex Prompt 01 — Data Foundation Router

Use this prompt only when `docs/implementation/STATUS.md` selects a Phase 1 task. Otherwise stop
and follow the selected task's plan.

Read `AGENTS.md`, `docs/implementation/QUALITY_LOOP.md`, `STATUS.md`, the complete selected Phase 1
task, the frozen data/domain contracts, and the source-audit baseline. Run repository and source
preflight before edits. Freeze one task brief and follow the repository-owned TDD, fan-out, review,
retry, Git, status, and reporting gates.

Preserve raw values and row lineage; never weaken the frozen audit. Keep public-fund `itm_no` grain,
many-valued `prfd_attr_cd`, quarantine, and deterministic versioned artifacts exactly as specified
by `AGENTS.md`. End after the selected task.
