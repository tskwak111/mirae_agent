# FinProof — Codex Resume Router

Resume from repository state, not conversational memory.

1. Read `AGENTS.md`, `docs/implementation/QUALITY_LOOP.md`, and
   `docs/implementation/STATUS.md` completely.
2. Read the entire plan section for the single task selected by `STATUS.md`.
3. From the externally selected worktree root, verify repository context:

```powershell
python tools/check_repo_root.py --expected-root .
git status --short
git branch --show-current
git log -3 --oneline
```

4. Run `python tools/verify_handoff.py`; run the source audit before consuming frozen facts.
5. Confirm the recorded task-brief hash, base commit, allowed paths, writers, RED/GREEN evidence,
   candidate number, findings, and retry budget before editing.
6. Continue only that task under `QUALITY_LOOP.md`. Skills and agents may not enlarge scope or
   writable paths. Shared contracts and `STATUS.md` remain coordinator-only.
7. Obtain the required independent reviews, run fresh verification, use canonical exact staging,
   update the durable handoff, and report observed facts plus the exact next task.

If state is inconsistent or a stop condition is unresolved, stop and report it instead of
reconstructing intent from chat.
