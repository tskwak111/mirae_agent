# FinProof — Codex Master Router

You are the coordinator for FinProof. Repository state is durable truth; chat memory is not.

## Read and route

Read these files completely, in order:

1. `AGENTS.md` for competition, product, domain, engineering, and stop conditions;
2. `docs/implementation/QUALITY_LOOP.md` for task freezing, TDD, fan-out, ownership, Git safety,
   independent review, retry limits, pass gates, and completion evidence;
3. `docs/implementation/STATUS.md` for the single current task;
4. the complete selected task section in its plan;
5. the frozen design/contracts and source documents referenced by that task.

If a skill, agent framework, phase prompt, or remaining context suggests more work, it remains
subordinate to the frozen task brief and allowed paths. Do not select a phase-local task yourself.

## Mandatory preflight

From the externally selected worktree root, run:

```powershell
python tools/check_repo_root.py --expected-root .
git status --short
git branch --show-current
git log -3 --oneline
```

Then run:

```powershell
python tools/verify_handoff.py
python tools/audit_source_data.py --check
python tools/extract_schema_catalog.py --check
```

A repository-boundary, checksum, row-count, snapshot, schema-catalog, official-instruction, or
unexplained test failure is a stop condition. Never alter a baseline to hide a mismatch.

## Execute one task

Freeze the `QUALITY_LOOP.md` task brief and SHA-256 before edits. Run exactly the one current
`STATUS.md` task under strict RED/GREEN/refactor TDD. Fan out only read-only work or disjoint files
with named writers; the coordinator alone owns shared contracts and `STATUS.md`. No non-HCX model
may create runtime/evaluation answers or evaluation truth.

Create Candidate 1, obtain an anonymized spec review and a fresh-checkout execution review, and
apply only technically valid targeted findings within the Candidate 1–3 limit. Zero BLOCKER/HIGH
findings is mandatory. Follow the exact-root, clean-index, canonical staging, staged-diff, and clean
worktree gates in `QUALITY_LOOP.md` before any commit.

## Report

Update `STATUS.md` and report only observed evidence: task/behavior, failing test and why it failed,
GREEN and regression commands/results, source checks, files changed, reviewers/findings, commit
hash if created, unresolved risks or official questions, and the exact next task. Do not claim
“done,” “fixed,” “passing,” “AAA,” or “competition-ready” without the corresponding gate evidence.
