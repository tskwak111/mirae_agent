# Codex Prompt 00 — Initial Kickoff

You are starting the FinProof implementation from a deliberately complete handoff. Do not rely on prior chat context.

1. Read `AGENTS.md` and `START_HERE.md` completely.
2. Read the frozen design and contracts listed by `START_HERE.md`.
3. Run `python tools/verify_handoff.py` and `python tools/audit_source_data.py --check` before editing.
4. Open `docs/implementation/STATUS.md` and identify the first incomplete task.
5. Read that task in its phase plan.
6. Execute exactly that one task with strict red-green-refactor TDD.
7. Run the task checks and repository quality checks available at the current phase.
8. Update `docs/implementation/STATUS.md`, commit the change, and leave a clean worktree.

Do not start later tasks, weaken frozen source baselines, add non-HyperCLOVA generative models, use free-form SQL, silently merge fuzzy product matches, or change metric policies without a documented decision. Your final response must include the observed failing test, passing commands, files changed, commit hash, remaining risks, and exact next task.
