# FinProof — Codex Resume Prompt

Resume FinProof from repository state, not from conversational memory.

1. Read `AGENTS.md`, `docs/implementation/STATUS.md`, and the current phase plan.
2. Inspect `git status`, recent commits, and the last recorded commands/results.
3. Run `python tools/verify_handoff.py`.
4. If the next task consumes source data, run `python tools/audit_source_data.py --check`.
5. Execute exactly the next incomplete task with strict red-green-refactor TDD.
6. Do not alter frozen domain policies or expected source counts without an official override in `docs/10_DECISION_LOG.md`.
7. Run the task’s gate, review the diff, update status, commit, and leave the worktree clean.

At the end, report verified commands/results, the commit hash, unresolved risks, and the next exact task. Never claim completion from code inspection alone.
