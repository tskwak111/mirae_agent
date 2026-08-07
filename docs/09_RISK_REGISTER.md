# Risk Register

| ID | Risk | Severity | Detection | Mitigation | Release blocker |
|---|---|---|---|---|---|
| R-01 | public-fund attribute rows treated as products | BLOCKER | duplicate `itm_no` in rank tests | item/attribute split and grain validator | yes |
| R-02 | ETF query includes ETN | BLOCKER | product-type golden tests | explicit `pd_grp_no` filter | yes |
| R-03 | `pd_tr_yn` polarity reversed | BLOCKER | state fixture and frozen counts | typed state rule with regression test | yes |
| R-04 | “current” represented as real time | HIGH | answer/date tests | fixed snapshot default and explicit note | yes |
| R-05 | matured bond with positive quantity presented as current buyable | HIGH | 325/254 dual count test | validated state rule and limitation wording | yes |
| R-06 | missing/Not Rated converted to high rating | BLOCKER | rating regression | explicit ordinal registry; no inference | yes |
| R-07 | suspicious zeroes globally nulled or trusted | HIGH | operation-policy tests | metric-specific display/filter/rank/aggregate policy | yes |
| R-08 | constant zero metric produces fake unique rank | HIGH | tie tests | joint rank and secondary display sort | yes |
| R-09 | cross-currency AUM integrated rank | BLOCKER | comparability tests | currency separation unless fixed FX | yes |
| R-10 | bond yield compared as same concept as period return | HIGH | cross-product tests | comparability groups and split output | yes |
| R-10A | heterogeneous query compiled as one grain or one global top-k | BLOCKER | QueryPlan/segment tests | `product` envelope, explicit `top_k_scope`, native ExecutionBundle segments | yes |
| R-11 | fuzzy entity match merges distinct products | BLOCKER | adversarial entity tests | candidate-only fuzzy matching | yes |
| R-12 | LLM generates SQL or arithmetic | BLOCKER | architecture/dependency/code scan | constrained plan and deterministic compiler | yes |
| R-13 | non-HCX generative model in runtime | DISQUALIFICATION | dependency/network/config scan | single HCX client; CI policy test | yes |
| R-14 | answer number lacks evidence | BLOCKER | claim coverage test | verifier fail-closed | yes |
| R-15 | malformed fund row contaminates results | HIGH | quarantine regression | deterministic quarantine | yes |
| R-16 | external data overwrites official value | DISQUALIFICATION/HIGH | provenance test | separate demo namespace, official priority | yes |
| R-17 | evaluation response has extra/wrong types | BLOCKER | JSON schema/API test | strict response model | yes |
| R-18 | planner malformed output or outage | HIGH | integration fault injection | bounded repair, rule fallback, clarification | yes |
| R-19 | cache returns stale policy/result | HIGH | version-bundle tests | complete versioned cache key | yes |
| R-20 | latency exceeds hidden timeout | HIGH | staged latency/load test | one planner call, prebuilt DB/views, cache, bounded work | yes when limit known |
| R-21 | post-freeze deployment changes behavior | DISQUALIFICATION | digest/manifest comparison | immutable release and operating runbook | yes |
| R-22 | overbuilt architecture delays core correctness | HIGH | phase status and scope review | P0/P1/P2 priorities, no UI-first work | yes |
| R-23 | sample `axis_*` treated as ground truth | MEDIUM/HIGH | mapping review | use only as hints; versioned derived mappings | yes for affected fields |
| R-24 | proposal claims unmeasured superiority | MEDIUM | proposal review | publish actual benchmarks and limitations | yes for submission quality |
