# Metric Registry and Operation Policy

## 1. Why the registry exists

A column name is not enough to compare financial metrics safely. Each metric needs operation-specific rules for display, literal filtering, ranking, aggregation, ties, dates, periods, units, currency, availability, and evidence.

The canonical seed is `config/metric_registry.yaml`. Code loads it into typed models and rejects invalid or incomplete entries.

## 2. Required fields

Each metric definition contains:

```text
id
label_ko
product_types
source_table/source_column or derived_rule
value_type
unit
currency_source or fixed_currency
period
as_of_source
missing_policy
zero_policy
display_policy
literal_filter_policy
ranking_policy
aggregation_policy
tie_policy
comparability_group
cross_product_policy
quality_rules
evidence_rule
version
queryable or explicit non_queryable_reason
```

Every metric intended for Phase 2 execution is reachable through exactly one canonical field entry for each supported product type. A metric that is deliberately not executable declares `queryable: false` and one stable reason code; omission is not an implicit policy. Every planner field alias resolves to one canonical field or fails closed. The field registry maps canonical fields to the frozen `silver_*` table projections and their canonical `record_json` lineage, never directly from a caller-provided source-table or column string.

## 3. Operation-specific policies

### Display

Return the recorded value and quality warning when a user asks for a specific product value, unless the value is malformed and cannot be represented safely.

### Literal filter

A condition such as `fee = 0` uses recorded official zeroes and labels them. It must not quietly convert the condition to `fee > 0`.

### Rank

A rank may provide two views when suspect values materially dominate:

- recorded-value rank
- comparison-valid rank based on the registered policy

The answer says exactly which view produced which rows.

### Aggregate

Averages/sums exclude or separate values only according to the registered policy and report counts included/excluded. Never silently drop a value.

### Tie

If all primary values tie, report a joint rank. A secondary sort may control display order only if named explicitly. It does not break the primary tie semantically.

## 4. Critical metric policies

### Domestic bond buy yield

- valid only when numeric
- source buyability and validated buyability are distinct filters
- date warning required when individual quote date is unknown
- not comparable to historical ETF/fund period return as a shared “return” rank

### Remaining days

- derive from valid `MAT_DT - as_of_date`
- preserve source `REMAINING_DAYS` separately
- `0`, `99991231`, blank, and invalid dates have separate quality states

### Credit rating

- ordinal comparison uses `config/rating_scale.yaml`
- only explicit normalized grades enter an `AA- or above` filter
- Not Rated/missing is not converted to AAA
- agency disagreement creates a warning

### Domestic ETF AUM

- primary `pd_net_tamt`, KRW
- secondary `du_last_aum` for diagnostics only unless policy changes

### Domestic tracking error/difference rate

- recorded values are queryable
- current nonblank values are all zero
- ranking results are joint rank; declared AUM sort may order display

### Overseas ETF total fee

- raw zero remains `recorded_zero_unverified`
- specific-value display returns zero with warning
- literal zero filter includes it
- ranking may show recorded-zero joint rank and a positive/comparison-valid view
- external values never overwrite official values in evaluation mode

### Overseas one-day return

- recorded values are all zero among available rows
- lookup returns recorded value
- rank reports a joint tie and does not pretend to identify winners

### Public-fund AUM

- source `fd_nast_suma`
- currency comes from `curr_cd`
- group/rank separately by currency in evaluation mode
- fixed FX conversion requires explicit versioned snapshot and is not enabled by default

### Public-fund returns

- period is mandatory for ranking/comparison when not uniquely implied
- below -100 values receive out-of-domain quality status and are excluded from comparison-valid rank, while raw evidence remains visible
- item grain prevents repeated attribute rows

## 5. Cross-product compatibility

A comparison is valid only when all relevant dimensions match:

```text
metric definition
value type
unit
currency or FX basis
measurement period
as-of semantics
return/yield concept
state eligibility
```

Examples:

- bond buy yield vs ETF one-year historical return: not a single comparable ranking
- KRW domestic ETF AUM vs USD overseas ETF AUM: separate by currency without FX
- one-year domestic ETF return vs one-year public-fund return: potentially comparable with source/date caveats and active/valid rules
- risk grades across sources: show source systems and treat as reference unless official equivalence is established

## 6. Versioning

A metric policy change that changes results increments `metric_registry_version`, invalidates affected caches, updates golden expectations, and requires a decision-log entry. Do not edit registry meaning after submission freeze.

Phase 2 packages the exact registry source files into the wheel through build mappings rather than maintaining copied YAML files. Tests require repository/resource byte identity, bounded duplicate-key-safe parsing, deep immutability, complete field/metric/alias cross references, and application-issued versions bound to the expected artifact logical hash.
