# Risk Register

| ID | Risk | Severity | Detection | Mitigation | Release blocker |
|---|---|---|---|---|---|
| R-01 | public-fund attribute rows treated as products | BLOCKER | duplicate `itm_no` in rank tests | item/attribute split and grain validator | yes |
| R-02 | ETF query includes ETN | BLOCKER | product-type golden tests | explicit `pd_grp_no` filter | yes |
| R-03 | `pd_tr_yn` polarity reversed | BLOCKER | state fixture and frozen counts | typed state rule with regression test | yes |
| R-04 | “current” represented as real time | HIGH | answer/date tests | fixed 2026-08-24 distribution default and explicit coverage note | yes |
| R-05 | matured bond presented as currently eligible | HIGH | 20,497/20,407 state-policy regression | validated issue/maturity/listing rules and limitation wording | yes |
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
| R-25 | July-era counts or policies survive the official August replacement | BLOCKER | source audit, contract and official-artifact integration tests | immutable 2026-08-24 manifest and refreshed expectations | yes |
| R-26 | unavailable internal code tables are guessed or decoded | BLOCKER | organizer unanswerable cases and planner semantic tests | fail closed and state that the supplied data cannot support the code meaning | yes |
| R-27 | absent holdings data is presented as absence of holdings | HIGH | holding-coverage tests | 31,492 explicit `unavailable` coverage rows; no fabricated holdings | yes |
| R-28 | HCX rate limit or network interruption causes cross-request failure | HIGH | fault injection, request-owner tests, load/soak reports | bounded retry, shared deadline, request-owned DuckDB interruption, safe failure | yes |
| R-29 | short clean soak misses long-duration memory or provider faults | HIGH | compare final and diagnostic soak reports | D-041 records only 517.063 seconds; retain OOM/network/drift diagnostics and avoid 24-hour claims | no under D-041; residual |
| R-30 | release metadata verifies working-tree bytes instead of the sealed candidate | BLOCKER | release-manifest contract and clean-room reproduction | hash the covered Git object and bind image/artifact/report hashes | yes |
