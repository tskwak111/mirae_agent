# FinProof evaluation authoring

Canonical cases belong in `evaluation/canonical/*.jsonl`, with one category per file.
Every line must satisfy `GoldenCase`, preserve a unique `case_id`, and contain truthful
human review metadata. The loader computes a stable suite checksum from canonicalized
case content; file order does not change that checksum.

`expected_plan` is a typed expectation subset, not an executable partial `QueryPlan`.
It always records intent, product types, snapshot date, result grain, and top-k scope.
Multi-product expectations also record one native segment per product type. A
heterogeneous native-grain case uses the `product` response envelope. Filters, metrics,
sort, top-k, and clarification behavior are included only when they were actually
reviewed.

Expected numeric and date values declare their type. Matching is exact by default;
`display_tolerance` is allowed only for an explicitly reviewed display-rounding rule.
Result order, compatibility partitions, envelope assembly, evidence IDs, limitation
behavior, and clarification behavior are scored independently.

The 13 files in `tests/golden/seed_cases.jsonl` remain `AI-handoff-seed` semantic
examples. They are not canonical cases, are not loaded from this directory, and must
not be copied or renamed as human-reviewed ground truth.

After deterministic reference execution, source/evidence inspection, and human review,
run:

```bash
uv run finproof evaluate \
  --suite canonical \
  --output artifacts/evaluation/canonical.json
```

No canonical report is committed until reviewed cases exist and the recorded metadata
truthfully identifies their reference source and reviewer.
