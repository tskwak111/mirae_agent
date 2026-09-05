# Submission Checklist

## Frozen package

- [x] Pre-deadline documentation revision authorized by the owner; team `Agent.종필` reflected. Original `finproof-submission` tag stays at `712f0ba`; only a documentation descendant is published to both main branches.
- [x] Covered package: `5edea2d3fcf39f590013c32a7b0c611ffed177a8`.
- [x] Runtime inputs identical to full-gate / live-image source `ba530fc`.
- [x] Official 2026-08-24 data: 53,375 audited rows.
- [x] Manifest verified against covered Git object, actual deployed image and artifact.
- [x] Exact hashes are recorded in `RELEASE_RECORD.md`.
- [x] Organizer repository is PRIVATE with WRITE permission; initial history preserved.
- [x] Source, Dockerfile, pyproject/lock, README, five Turtle ontologies, PDF/PPTX, API specification, and release metadata included.
- [x] Original metadata child/tag published and verified. For the documentation revision, fast-forward both main branches without changing that tag; verify exact remote refs before reporting publication.

## Verification

- [x] Independent review closed at 0 Critical / 0 Important after one correction.
- [x] Focused ontology RED rejected unsupported StateRules; GREEN aggregate: 10 passed.
- [x] Ruff format/check clean; mypy 340 files clean.
- [x] Final pytest: 3,068 passed, 9 opted-out skips, 5 warnings.
- [x] Source/handoff/compliance passed; exact covered clean-room contracts: 14 passed.
- [x] Reproduction build passed; generated-cache digest difference documented and live-accepted image retained.
- [x] Load: 35/35, failure 0, p95 11,007.570 ms.
- [x] Soak: 20 cycles / 80 observations, failure 0, drift 0, 1,123.638 seconds.
- [x] Historical reports retained separately; no 24-hour claim.

## API and operation

- [x] Endpoint: `https://101-79-30-91.sslip.io/answer`.
- [x] Only GET /answer reaches the app; five-string response contract preserved.
- [x] Valid TLS, missing-parameter 422, disallowed-route/method 404, HTTP redirect 308.
- [x] HCX-007 performs intent planning and wording in evaluation mode.
- [x] Retrieval, calculations, evidence and verification remain deterministic.
- [x] Artifact mount read-only; secret file mode 600; no secret committed.
- [x] Key-only SSH 2222 with approved-IP restriction; 80/443 explicitly approved public.
- [x] Endpoint/proxy restart unless stopped; Docker boot-enabled.

## Proposal

- [x] Revised editable 15-slide PPTX, one native chart and one native table, no package/layout findings.
- [x] Team branding and natural Korean revised throughout; unsupported weighting removed; actual HCX role and workload/accuracy limits clarified.
- [x] All 15 searchable PDF pages rendered and inspected; all 254 native slide text fragments preserved.
- [x] Korean text, numbers, charts, diagrams and page layout checked.
- [x] Korean font export corrected with a task-local render configuration; tagged text PDF replaces the old raster fallback. Original tagged artifacts remain in Git history.
- [x] Holdout failures, nonzero A-E errors, unavailable holdings, distinct workloads and bounded soak duration remain explicit.
- [x] Independent documentation review: Critical 0 / Important 0 / READY. Revised hashes recorded once in `RELEASE_RECORD.md`.

## After publication

Keep the exact service active 2026-09-07 through 2026-09-20 KST. Monitor without extra HCX questions. Do not rebuild or change code, data, prompts, policies, images or results without organizer authorization. Check provider/server availability and NCP credit; only identical-image restart is permitted under the frozen operations scope.
