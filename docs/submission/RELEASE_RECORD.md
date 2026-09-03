# FinProof Release Record

**Sealed on:** 2026-09-03

## Immutable identities

| Item | Identity |
|---|---|
| Covered runtime commit | `b0cf204f27d41811df69c52d02c8791afb69cfa0` |
| Clean-room image | `sha256:5ef62fa1e665ec2626b84d5878eb2c084b5ac74c100da162efa80797a7f8a7be` |
| Artifact manifest SHA-256 | `70ccd09344bd0ef9a21f46008f37bdf86ef3937cf92e8024e072d4653f4e4287` |
| Artifact logical hash | `977b34099c246ca0156824a661718d027fba2eb5adee3f1cbbb8945fbd90a9a8` |
| Organizer report SHA-256 | `0467862645b348672eae64b9d220e54a0df0276fc3483318e1706a49182db625` |
| Load report SHA-256 | `d3dd137f0341266bb5a1662a5c8a5230e88f57ff149d71c281d738de2f0bf843` |
| Soak report SHA-256 | `c4ed11afd724a1b06c698671711c6fff02d6fb1702d093427c7e419c9ce7c529` |
| Release manifest SHA-256 | `7342cfbf4169c81a2ac79b1d995041e07dff8e620e811dc51699211df2caea31` |

The metadata commit is the commit containing this record. The release tag must point
to that metadata child; `release/manifest.json` continues to cover its verified parent
runtime commit and therefore does not hash itself.

## Acceptance

- Final clean-clone gate: Ruff format/check PASS, mypy 335 files PASS, pytest 2,963
  passed and 9 opted-out skips, source audit PASS, handoff PASS.
- Clean-room reproduction: exact detached covered commit, compliance/release contract
  12 passed, Docker build PASS.
- Independent bounded re-review: Critical 0 / Important 0 / READY.
- Live acceptance: load 35/35 with zero failures; soak 20 cycles/80 observations with
  zero failures and zero drift.

## Residual risk

The live soak measured 517.063 active seconds, not 24 hours. Earlier OOM, network, and
terminal-drift diagnostics remain diagnostic history and are not represented as final
acceptance. Holding coverage remains unavailable in the sealed artifact, and hidden
organizer latency scoring remains unknown.

Any behavior, data, prompt, policy, dependency, artifact, or image change invalidates
this record and requires a new covered commit, gate, image digest, and manifest.
