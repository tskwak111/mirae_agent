# Proposal Evidence Index

Only the claims below are release-supported. Hashes are bound in
`release/manifest.json`.

| Claim | Evidence | Observed result |
|---|---|---|
| Official data identity | official artifact manifest | 2026-08-24; 53,375 source rows; 13 tables; logical hash `977b3409…a9a8` |
| Exact cross-source identity | artifact tables | 217 exact links and 434 link-evidence rows |
| Holding coverage honesty | artifact tables | 0 fabricated holdings; 31,492 explicit `unavailable` coverage rows |
| Organizer corpus shape | `evaluation/organizer_20260824/*.jsonl` | 35 cases: easy 10, medium 10, hard 10, unanswerable 5 |
| Human reference approval | `evaluation/organizer_20260824/review/*-v3.json` | reviewer 곽태성; approved 2026-08-29; expected packet SHA-256 `859602d7…f38c` |
| Deterministic correctness | `artifacts/evaluation/organizer-20260824.json` | all nonempty scored axes 1.0; evidence 439/439; answer semantics 280/280 |
| Deterministic-core latency | same organizer report | 35/35; mean 509.743 ms; p95 1,341 ms; fallback-only extended-demo measurement |
| Blind-development deterministic replay | `artifacts/evaluation/blind-development-deterministic.json` | 144/144; all 13 aggregate axes 1.0; mean 179.382 ms; p95 625 ms; reviewed-plan deterministic core only |
| Frozen blind-holdout identity | `artifacts/evaluation/blind-holdout-candidate.json` | commit `b10d2e6…efcdf`; image `sha256:c37aa7…a768`; artifact `977b3409…a9a8`; 48-case sealed suite `900571a8…02ec` |
| Private blind-holdout aggregate | `artifacts/evaluation/blind-holdout-summary.json` | 48 cases; 25 successful and 23 safe failures; plan fields 0.4896, filter slots 0.8704, product set 0.5904, numeric values 0.5217, evidence 0.4298, answer semantics 0.5878; p95 31,610.704 ms |
| Current organizer A–E ablation | `artifacts/evaluation/ablation-organizer-20260824.json` | complete 35-case/two-repeat measurement; A/B/C/D/E error counts 25/10/14/16/15 and p95 75,371/55,660/55,810/55,849/56,048 ms; final E product F1 0.5331, order 0.3228, numeric 0.4348, evidence 0.2187, limitation 0.5714 |
| Final HCX endpoint load | `artifacts/evaluation/final-load.json` | 35/35; failure 0; mean 7,347.939 ms; p95 11,351.361 ms |
| Final HCX endpoint stability | `artifacts/evaluation/final-soak.json` | 20 cycles; 80 observations; 517.063 active seconds; failure 0; drift 0 |
| Repository verification | final clean-clone gate | 2,963 passed, 9 opted-out skips; Ruff and mypy clean; source/handoff PASS |
| Reproducible packaging | clean-room reproduction | compliance/release 12 passed; image `sha256:5ef62f…a7be` |
| Independent review | `docs/review/INDEPENDENT_REVIEW.md` | Critical 0 / Important 0 / READY |

## Claim limits

- Do not describe the 517.063-second run as a 24-hour soak.
- Do not cite organizer `repeat_stability`; that report contains a 0/0 denominator.
- Do not compare deterministic-core latency with the HCX endpoint as an equivalent
  workload.
- Do not present the blind holdout as acceptance: 23/48 requests returned safe failures,
  and its aggregate scores are materially below the reviewed deterministic replay.
- Do not claim monotonic A–E improvement. The current ablation records nonzero errors in
  every variant; `error_count` is the number of cases with any errored repeat and, for
  B–E, includes repaired planner-attempt errors propagated by the measurement harness.
- The ablation report is diagnostic evidence, not a zero-error endpoint acceptance or an
  equivalent workload comparison between variants.
- Do not claim holdings-based answers are available from the sealed official artifact.
- Do not claim real-time prices, forecasts, guaranteed returns, or recommendations.
