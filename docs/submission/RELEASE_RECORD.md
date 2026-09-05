# FinProof Release Record

**Runtime freeze:** 2026-09-06 KST. The original metadata child's Git timestamp is the exact freeze time. The owner-confirmed submission cutoff is September 6 end of day, operationally capped at 23:59 KST; the official PDF itself states `09.06`.

**Pre-deadline documentation revision:** 2026-09-06, at the owner's explicit request. The revised proposal and submission guide are a fast-forward descendant of `712f0bacd1def9fe36d16823f882f1bae52c3bc6`. The `finproof-submission` tag remains on that original commit. No runtime, data, prompt, policy, result, image or release-manifest identity changed. See the dated scope resolution in `docs/10_DECISION_LOG.md`.

- Organizer private repository: https://github.com/miraeasset-aifestival-2026-product/fin-211
- Evaluation endpoint: https://101-79-30-91.sslip.io/answer
- Original publication unit: metadata child plus annotated `finproof-submission` tag. Publish the documentation descendant to organizer `main` and personal `origin/main` without moving that tag or rewriting either repository's history.

## Immutable identities

| Item | Identity |
|---|---|
| Covered package / metadata first parent | `5edea2d3fcf39f590013c32a7b0c611ffed177a8` |
| Full-gate / deployed-image source | `ba530fc74bd8b4b823e3e8d9a394cea03b33989d` |
| Deployed linux/amd64 image | `sha256:cf7f56d20c2c6cb565bcc415a43e27c6c8546c582e653797738a70c98e8a1252` |
| Mounted artifact manifest SHA-256 | `31d8a99516a66817a7f8bdcb807e672be5ae8da3bcff28b1c921e84ddbf09259` |
| Artifact logical hash | `977b34099c246ca0156824a661718d027fba2eb5adee3f1cbbb8945fbd90a9a8` |
| Final load report SHA-256 | `8cc38cad40302ee2bfd48f18ea4ce4cbf816e3739e8ae2174415792ce5d472af` |
| Final soak report SHA-256 | `7fed2e7f0e1cbd7abdfb4422c8dee11a97b0f7fa6f5defb4e1476a148dd47641` |
| Current A-E ablation SHA-256 | `b394e7f536b8028b5a3caa94489407210051a62a4765c6d069ed0631ff8ccc0e` |
| API specification SHA-256 | `2d5a9960e4a4490cf0c9bb21fa69da66e2bfb35526578f5600449a93f2f5ad73` |
| Revised proposal PPTX SHA-256 | `04839ace9c14198751a2f965be1c8db0aa6cc4f4f8ba9b3d70c6ce6ce0456108` |
| Revised proposal PDF SHA-256 | `3546e50fd72e852c0d09a32d8b73c40c738587d2c6807cc273cc0f9453f3eb38` |
| Release manifest file SHA-256 | `b6ba2e5ca961bb08f27a4db0ca77d8bfe1cd3f4ce7b1a8a7066d9ef0a52672cd` |
| Release manifest internal checksum | `a5bb6e130e27e92bb1a456c9f2d853c7a65eefac6736439d0275a0532b94a577` |

The manifest covers its parent Git object, not itself or the metadata child. All Docker runtime inputs are byte-identical between `ba530fc` and the covered package.

## Observed verification

- Full gate on `ba530fc`: Ruff format/check clean (340 files), mypy clean (340 files), pytest **3,068 passed / 9 opted-out skips / 5 warnings** in 2,933.74 seconds. Source audit, handoff, competition compliance, and diff check passed.
- Source audit: 53,375 rows, distribution 2026-08-24. Handoff: 61 required files, 9 official inputs, 19,074,953 bytes.
- Exact covered-commit clean-room: frozen dependency installation, source/handoff/compliance passed, compliance/release contracts **14 passed**, linux/amd64 Docker build succeeded. Manifest verification passed against the actual deployed image and mounted artifact manifest.
- Independent review: one bounded ontology correction, then **0 Critical / 0 Important / READY**. Focused RED rejected unsupported StateRule declarations before removal; the ontology aggregate passed 10 tests.
- Load: **35/35**, failure 0, mean 7,268.868 ms, p95 11,007.570 ms. This is the reviewed four-case weighted mix, not 35 unique questions.
- Soak: **20 cycles / 80 observations**, failure 0, drift 0, **1,123.6383504400146 active seconds**. Both runners exited 0. Endpoint logs recorded 115 completions without errors, OOM, or restart. The run stayed within the approved 460-call HCX ceiling.
- HTTPS: valid TLS, missing-parameter 422, disallowed method/path 404, HTTP redirect 308. Schema probes generated no HCX calls.
- Original tagged proposal: 15 slides and three native charts, with the earlier raster PDF fallback. Its PPTX/PDF hashes remain recoverable at `finproof-submission`: `267da08c…bb2` / `b46d95f4…279`. This is historical evidence, not the current proposal format.

## Documentation revision verification

- Team `Agent.종필` is on the cover, page branding, submission guide and author metadata. FinProof remains the system name; 곽태성 remains the named participant. Tool metadata and development history were not falsified or erased.
- Removed the unsupported 20/40/40 weighting and corrected the PDF page/deadline attribution. Clarified the D-039 hybrid wording boundary and evaluation-mode safe failure. Replaced the unsupported holdings success scenario with a labeled supported design example, not a new live result.
- Revised PPTX: 15 slides, one native chart and one native table. Package/layout findings: 0. The chart includes all six reported holdout axes, including plan fields 48.96%; the latency table separates workloads and candidates.
- Revised PDF: 15 pages, searchable Korean, tagging enabled, author `Agent.종필`. All 254 native slide text fragments are preserved. All pages were visually inspected; the final two small edits affected only pages 8 and 12, re-inspected after confirming the other 13 page renders were pixel-identical.
- Bundled LibreOffice export initially lacked the Korean font configuration. A task-local Fontconfig file pointing to available system fonts and a writable temporary cache corrected the export. No project dependency or deployed image changed. PDF producer metadata remains intact.
- Fresh checks: `verify_handoff.py` PASS (61 files, 9 inputs, 19,074,953 bytes), `audit_source_data.py --check` PASS (53,375 rows, 2026-08-24), competition compliance PASS, bound release-manifest verification PASS, and `git diff --check` clean. Full pytest/Ruff/mypy were not repeated for documentation-only edits; the existing full gate remains attributed to `ba530fc` above.
- Fresh service check: HTTPS missing-parameter response 422, TLS verification 0. Both exact-image containers running, OOM false, restart count 0; endpoint memory 1.817 GiB, proxy 52.88 MiB. These probes sent no HCX question.
- Independent `/root/submission_polish_review` inspected all 15 revised PDF pages, official pages 6-7, source/claim consistency and exact promoted hashes: **Critical 0 / Important 0 / READY**. The review closed without a correction loop. Closure records were then updated once.

## Rebuild boundary

The final package rebuild produced `sha256:d8aa8b798d869b02d9e7df01891b2ac49865d4d9bb290d1a179c8a171500a8e8`. It is a reproduction check, **not the deployed image**. Of 228 compared files under the copied runtime-input paths, only 61 generated `.pyc` files differed; all other 167 files matched. With build-path/header metadata removed, all 61 compiled-code hashes matched. All 42 installed package names/versions also matched.

Host validation creates nested `__pycache__` before Docker COPY; rebuilds are not claimed bit-for-bit identical. Recursive cache exclusion is a post-competition packaging backlog item. No runtime/image input changed after live acceptance. Restart the recorded deployed digest, never the reproduction image or a newly rebuilt tag.

## Deployment and continuous operation

- NCP host `101.79.30.91`, container `finproof-task10-ba530fc-candidate`.
- `/opt/finproof/runtime-artifacts-copy` is mounted read-only at `/app/artifacts`.
- Evaluation mode uses HCX-007. Server secret file is mode 600; no secret value is in this record or image.
- HTTPS container `finproof-https`: pinned Caddy `sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648`; config SHA-256 `a46c60734cc9bbe686e01d0af1240372047a8eff8fc2bf0519a0cbddbc74c192`.
- Both containers use `unless-stopped`; Docker is boot-enabled. TCP 80/443 are public under explicit approval. Key-only SSH uses 2222, ACG-restricted to the approved operator IP, and no longer occupies 443.
- Keep this exact service active 2026-09-07 through 2026-09-20 KST. After freeze, only monitoring and identical-image restart are allowed without organizer authorization. Do not send extra HCX questions for health monitoring.

## Residual risks

This is not a 24-hour soak. Earlier OOM, network and drift diagnostics remain separate, as do prior v22 acceptance and v4 ablation reports. Holdout measured 25/48 successes and 23 safe failures; current A-E error counts are 25/11/15/17/16. These are disclosed limitations, not target-level language accuracy or zero-error acceptance. Holdings coverage remains unavailable and organizer latency scoring is undisclosed. Continuous operation depends on NCP credit, networking, DNS/TLS and HCX availability.

The final read-only runtime audit found no demonstrated release-critical defect. A
pre-existing privacy-hardening item remains: default Uvicorn access logs can retain
question/query strings in private Docker logs even though application events are
redacted. The deployed command has no `--no-access-log` flag. Suppression belongs in
an authorized maintenance window with a new image's contract and acceptance checks;
this documentation revision neither changes logging nor claims complete log redaction.
