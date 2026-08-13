# Code Review Checklist

## Competition compliance

- [ ] Only HyperCLOVA X is used as a generative model in runtime/evaluation.
- [ ] Official raw data is not overwritten by external values.
- [ ] No unsupported forecast or categorical recommendation is generated.
- [ ] Exact evaluation API shape remains intact.

## Data and contracts

- [ ] Source checksum/row lineage is preserved.
- [ ] Raw, normalized, and quality values are separate.
- [ ] Public-fund default grain remains `itm_no`.
- [ ] ETF excludes ETN unless explicit.
- [ ] Dates and current/snapshot wording are correct.
- [ ] State rules are product specific and tested.
- [ ] `pd_tr_yn` polarity is correct.
- [ ] Currency, period, unit, and metric definitions are compatible.
- [ ] Heterogeneous queries use the `product` envelope and preserve native grains.
- [ ] `top_k_scope` and compatibility partitions match the user request; no incompatible global rank is created.
- [ ] Suspicious zero/tie behavior follows the operation policy.
- [ ] Quarantined data cannot enter normal results.

## Query and security

- [ ] No user/model SQL or identifier interpolation.
- [ ] All product types/grains/top-k scopes/fields/operators/sorts/aggregations are allowlisted.
- [ ] Limits and timeouts are enforced.
- [ ] Fuzzy matches remain candidates, not automatic merges.
- [ ] Product text cannot instruct the planner/tool layer.
- [ ] No secrets/internal paths/stack traces leak.

## Evidence and answer

- [ ] Every material numeric/comparative claim has evidence.
- [ ] Counts/exclusions have traceable support.
- [ ] Verifier fails closed.
- [ ] Answer states snapshot/assumptions/limitations when material.
- [ ] Primary ties are not falsely broken by display sort.
- [ ] Recommendation wording is converted to condition-matching candidates.

## Tests and operations

- [ ] Test was observed failing before implementation.
- [ ] Critical regression coverage remains.
- [ ] Deterministic reference and production results agree.
- [ ] Formatting, lint, type, tests, audit, and handoff verification pass.
- [ ] Status and decision log are updated.
- [ ] Logs are structured and redacted.
- [ ] Cache key includes complete version bundle.
- [ ] Release/freeze impact is assessed.
