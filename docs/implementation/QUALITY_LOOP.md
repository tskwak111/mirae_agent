# FinProof Repository Quality Loop

This file is the single normative orchestration contract for implementation and review. Product,
competition, domain, and safety invariants remain in `AGENTS.md`; `STATUS.md` selects the work;
the selected plan supplies task details. Skills and agent frameworks are execution aids only and
may not enlarge the selected task, its allowed paths, or its retry budget.

## 1. Select and freeze one task

The coordinator selects exactly one incomplete task from `docs/implementation/STATUS.md`. A
session may finish that task or stop it as blocked; it may not begin another task.

Before edits, freeze a task brief in the work log containing:

- task ID and plan section;
- objective, interfaces, non-goals, and acceptance criteria;
- base commit, branch, and the externally selected absolute worktree path;
- exact writable paths and one named writer for every file;
- applicable source/config/schema hashes and official decisions;
- required RED, focused GREEN, regression, adversarial, and handoff commands;
- risk class, oracle author, implementer, spec verifier, and execution verifier.

Hash the canonical brief text with SHA-256. A scope, interface, acceptance, or allowed-path change
creates a new brief and must be recorded before work continues. Shared contracts are frozen before
implementation fan-out. `docs/implementation/STATUS.md` is coordinator-only.

## 2. Repository and staging safety

The absolute worktree is selected outside the repository instructions. From that exact directory,
run `python tools/check_repo_root.py --expected-root .` before every Git inspection or mutation.
The guard proves exact top-level and invoking-directory equality; it does not choose the intended
worktree or branch. A missing repository, ancestor repository, different worktree, unexpected
branch/base commit, or repository-selection environment override is a stop condition.

Before staging, run the guard with `--require-clean-index`. The index must be empty. Staging uses
only the canonical form `git add -- <literal task-owned path>...`, with paths copied from the frozen
allowlist. `git add .`, `git add -A`, `git stage`, Git `-C`, pathspec magic, variables, wildcards,
absolute/parent paths, continuation lines, shell chaining, and bare broad directories are forbidden.
`git commit -a`, `--all`, `--include`, and `--only` are forbidden. Inspect the staged name/status
list and prove every path is allowlisted before committing. Never tag, push, or release with a dirty
worktree or unexplained staged state.

Every staging operand is a literal file declared under the selected task's `Files` allowlist.
Directory operands are prohibited even when a task appears to own the directory. The verifier
compares each plan checkpoint with that declared allowlist. Only the bare `git` executable form is
supported; aliases, wrappers, path-qualified executables, shell continuations, and repository or
index mutations between staged-diff review and commit are stop conditions.

Executable Markdown uses a closed, case-sensitive Git grammar. The complete read-only set is
`git status --short`, `git branch --show-current`, `git log -3 --oneline`, `git diff --check`, and
`git diff --cached --name-status --`. The only index mutation is
`git add -- <one-or-more literal task-owned paths>`; quoted operands, comment markers, pathspecs,
variables, broad directories, and shell metacharacters are rejected. The only history mutation is
`git commit -m <one non-empty non-expanding literal or quoted ASCII message>`, after the clean-index
guard, canonical staging, and staged name/status review. Variables, globs, brace/array/splat syntax,
command substitution, and control operators are rejected in the message expression. Every other
Git or Git-like executable shape fails closed. Tagging is deferred until a separately tested
release gate proves the final commit, manifest identity, and a clean worktree together.

Within one executable fence, the exact-root guard's raw line must be exactly the registered command;
inline comments, operators, quotes, duplicate flags, or suffixes do not arm it. A valid guard
establishes either read-only or clean-index state. After it, only blank lines and commands from the
closed grammar may execute. For this cross-dialect verifier, apparent comment syntax is a
non-empty context line because the same spelling may execute in another supported shell. Any other
non-empty line moves the fence to an absorbing invalid state; a later relative root guard cannot
re-arm it, and every later Git command is unguarded. Comments, validation, and setup commands
therefore belong in separate fences from the guard.
`cmd`, `bat`, and `batch` fences, including interleaved CommonMark list/blockquote containers, are
executable and are checked by the same rule.

The coordinator also verifies that no staged path traverses a symlink or Windows junction. Static
Markdown validation cannot prove future filesystem topology, so a trusted, coordinator-inspected
worktree is an explicit prerequisite.

## 3. Fan-out and ownership

Parallel work is allowed only when dependencies and writable state are independent:

- read-only research, oracle design, domain review, security review, and verification may fan out;
- writers must own disjoint files in isolated worktrees or operate sequentially;
- one writer owns each file for the candidate; shared files are coordinator-owned;
- no agent may edit `STATUS.md`, change the task brief, stage, commit, tag, push, create a PR, or
  alter release state unless the coordinator explicitly grants that action;
- an implementer cannot serve as either final verifier for its own change.

Stop fan-out when work converges on a shared contract. The coordinator resolves findings one at a
time and records why each was accepted, rejected, waived, or deferred.

## 4. Roles

- **Oracle author:** owns focused tests, proves the expected RED against the frozen base, and does
  not disclose an implementation shortcut.
- **Domain/data reviewer:** checks grain, state, eligibility, metric definition, unit, currency,
  period, source fidelity, lineage, missing/zero/tie policy, and official-data limits.
- **Security reviewer:** attacks trust boundaries, repository selection, staging, prompt injection,
  allowlists, SQL construction, secrets, egress, timeouts, retries, concurrency, and resource caps.
- **Implementer:** makes the smallest typed change that satisfies the frozen task and no more.
- **Spec verifier:** receives the brief and an anonymized diff, not the implementer narrative or
  earlier conclusions, and checks every acceptance statement.
- **Execution verifier:** starts from a fresh checkout/worktree, installs from the frozen environment,
  reruns the commands, and adds adversarial or differential probes. Reported results are not evidence.

Small low-risk work may combine oracle, domain/security review, and implementation roles, but the
two final verifiers remain independent of the implementer. High-risk normalization, state,
eligibility, metric, SQL, claim-verification, API, and release changes require both approvals.

## 5. TDD and candidate lifecycle

For each behavior, the oracle writes one focused test and observes the expected failure. The
implementer makes the smallest change, observes focused GREEN, runs the relevant regression set,
and refactors only while green. A pre-existing passing test is not RED evidence, and a dependency,
permission, or timeout failure is infrastructure evidence rather than behavioral RED.

Candidate 1 is reviewed independently by both verifiers. A technically valid finding may produce
Candidate 2; one final targeted correction may produce Candidate 3. Each correction receives a
focused regression test where behavior changes and fresh verification. Only one separately recorded
retry is allowed for a transient infrastructure failure. If a BLOCKER or HIGH remains after
Candidate 3, mark the task `BLOCKED`; never run an unbounded “until impressed” loop.

## 6. Pass gate

A task passes only with current observed evidence for all applicable items:

- zero BLOCKER or HIGH findings;
- zero deterministic contract, evidence, claim-verifier, and API failures;
- exact source-manifest, frozen row-count, snapshot, and schema-catalog matches;
- recorded focused RED and GREEN output;
- relevant regression, adversarial, differential, load, or reproduction checks green;
- sealed-holdout threshold measured only after prompt/model/config/schema/code freeze;
- exact Git root, expected branch/base commit, allowlisted staged paths, and clean worktree;
- each MEDIUM waiver names a human owner, evidence, rationale, expiry date, and removal condition.

“AAA,” reviewer enthusiasm, and visual resemblance are goals, not proof. A comparison against a
real service is accepted only when the benchmark, evaluator independence, denominator, failures,
and artifact hashes are recorded.

## 7. Model and evaluation independence

No non-HyperCLOVA-X model may generate production/evaluation answers, runtime financial claims,
golden truth, or sealed-holdout truth. Development agents may write code, tests, and review reports;
their synthetic examples stay clearly labeled and cannot become evaluation truth without the
defined human review. HyperCLOVA X wording receives only a verified fact pack and must pass claim
verification; deterministic rendering remains the fallback.

## 8. Durable handoff

Before completion, the coordinator updates `STATUS.md` with the brief hash, base/candidate commits,
writers and reviewers, RED/GREEN commands and observed results, accepted findings, waivers, source
checks, unresolved risks, and the exact next task. The completion report states the same evidence.
Do not use “done,” “fixed,” “passing,” or “AAA” without the corresponding fresh command or review
record.
