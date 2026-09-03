# Submission Checklist

## Sealed candidate

- [x] Covered commit is `b0cf204f27d41811df69c52d02c8791afb69cfa0`.
- [x] Official distribution is 2026-08-24 with 53,375 audited source rows.
- [x] Artifact logical hash is
  `977b34099c246ca0156824a661718d027fba2eb5adee3f1cbbb8945fbd90a9a8`.
- [x] Clean-room image digest is
  `sha256:5ef62fa1e665ec2626b84d5878eb2c084b5ac74c100da162efa80797a7f8a7be`.
- [x] `release/manifest.json` verifies against the covered Git object, image, artifact,
  and evaluation reports.
- [x] Independent review closed at Critical 0 / Important 0.

## Evaluation contract

- [x] Sole public route is `GET /answer`.
- [x] Success and safe publication use exactly five string fields.
- [x] Evaluation mode requires NCP HyperCLOVA X `HCX-007` Structured Outputs for intent
  planning and answer wording.
- [x] Retrieval, filtering, ranking, aggregation, calculations, evidence, and claim
  verification are deterministic.
- [x] Secrets are environment-only and absent from the image and release manifest.
- [x] No external data overwrites official values; unavailable holdings remain explicit.

## Verification evidence

- [x] Ruff format/check passed for all 335 files.
- [x] mypy passed for all 335 source files.
- [x] pytest passed: 2,963 passed, 9 explicitly opted-out skips, 5 warnings.
- [x] Source audit passed: 53,375 rows, distribution 2026-08-24.
- [x] Handoff passed: 61 required files, 9 official inputs, 19,074,953 bytes.
- [x] Clean-room compliance and release-contract suite passed: 12 tests.
- [x] Final live load passed: 35/35, failure 0, p95 11,351.361 ms.
- [x] Final soak passed: 20 cycles, 80 observations, failure 0, drift 0.

## Operator actions before organizer submission

- [ ] Push the metadata child commit and create the final release tag.
- [ ] Deploy the exact image digest; do not rebuild from a moving branch.
- [ ] Mount the verified artifact directory read-only at `/app/artifacts`.
- [ ] Set `FINPROOF_HCX_ENABLED=true`, `FINPROOF_HCX_MODEL_NAME=HCX-007`, and inject
  `FINPROOF_HCX_API_KEY` through the server secret environment.
- [ ] Expose only the required HTTPS `/answer` endpoint and run one non-destructive
  schema smoke request.
- [ ] Submit the final endpoint and freeze code, data, prompts, policies, image, and
  deployment configuration.
