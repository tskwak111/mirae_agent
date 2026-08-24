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

Expected products use the full `(product_type, native_result_grain, product_id)`
identity, so identical raw IDs from different datasets remain distinct. Rank order is
read from verified rank summaries; non-ranked products come only from selected direct
or derived evidence. Expected numeric and date values declare their type. Matching is
exact by default; `display_tolerance` is allowed only for an explicitly reviewed
display-rounding rule.

Aggregate expectations declare function, optional target field, product type, native
grain, compatibility partition, ordered typed group values, and an exact typed result.
Result order, aggregate values, compatibility partitions, envelope assembly, evidence
IDs, limitation behavior, and clarification behavior are scored independently. Replay
metadata distinguishes fallback-only planning from HCX strict-JSON planning with rule
fallback and hashes the effective planner configuration.

The 13 cases in `tests/golden/seed_cases.jsonl` remain `AI-handoff-seed` semantic
examples. They are not canonical cases, are not loaded from this directory, and must
not be copied or renamed as human-reviewed ground truth. The canonical loader rejects
that reviewer sentinel explicitly.

After deterministic reference execution, source/evidence inspection, and human review,
run:

```bash
uv run finproof evaluate \
  --suite canonical \
  --output artifacts/evaluation/canonical.json
```

No canonical report is committed until reviewed cases exist and the recorded metadata
truthfully identifies their reference source and reviewer.
