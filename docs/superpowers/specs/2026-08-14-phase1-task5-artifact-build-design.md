# Phase 1 Task 5 Artifact Build Design

**Status:** Approved for implementation planning on 2026-08-14

**Scope:** Reproducible Bronze/Silver/Gold Parquet, self-contained DuckDB, data-artifact
manifest, reports, exact domestic ETF/public-fund links, and guarded publication

**Governing decisions:** D-014, D-017, D-021, D-022, D-023

## 1. Purpose and completion boundary

Task 5 turns the four checksum-verified official data workbooks and the Task 2-4
normalizers into a versioned, source-faithful runtime artifact. The build is offline,
deterministic at the logical-data boundary, and safe to publish into a managed local
artifact directory. The API later opens the resulting DuckDB read-only.

Task 5 is complete only when it proves all of the following:

- all 145,393 official source rows, all 6,401,851 cells, and all 207 catalog columns are
  present in Bronze with D-017 lineage;
- Silver contains 42,394 bonds, 1,733 domestic listed products, 5,646 overseas listed
  products, 11,138 public-fund items, and 95,618 public-fund attributes;
- the two known malformed source rows remain in Bronze, are excluded from their normal
  Silver grains, and have canonical persisted quarantine issues;
- row-level Task 2-4 issues are persisted under D-021 with one injected UTC timestamp;
- exactly 47 raw-identifier, item-grain links and 371 exact source locators are stored;
- two independent builds have equal table and manifest logical hashes when operational
  persistence times differ;
- the self-contained database verifies against the manifest and rejects writes;
- failed builds never replace a prior valid artifact set, and `--clean` never deletes an
  unrecognized directory.

The 6,032 issues currently observed from Task 2-4 row normalization are diagnostic
evidence, not a newly frozen grand-total baseline. Task 5 does not add dataset-level
constant-metric issues. Later metric policy may materialize those only after its own
contract is frozen.

## 2. Inputs, outputs, and non-goals

### 2.1 Verified inputs

The builder accepts no arbitrary workbook paths. It loads the official
`input_manifest.json` and `schema_catalog.json` below `Settings.source_root`, verifies
the complete source set, and passes only `VerifiedSourceFile` descriptors to
`iter_xlsx_rows`.

The manifest contains exactly nine direct logical input entries. Each entry has a
closed namespace, a canonical path relative to that namespace root, kind, byte size,
and SHA-256:

```text
namespace=source_root, path=input_manifest.json, kind=source_manifest
namespace=source_root, path=schema_catalog.json, kind=source_schema_catalog
namespace=repository, path=config/artifact_build.yaml, kind=artifact_build_config
namespace=repository, path=config/datasets.yaml, kind=dataset_registry
namespace=repository, path=config/quality_rules.yaml, kind=quality_rule_registry
namespace=repository, path=config/rating_scale.yaml, kind=rating_scale_registry
namespace=repository, path=config/state_rules.yaml, kind=state_rule_registry
namespace=repository, path=schemas/artifact_manifest.schema.json, kind=artifact_manifest_schema
namespace=repository, path=schemas/quality_issue.schema.json, kind=quality_issue_schema
```

The closed namespace order is `source_root` then `repository`; entries are sorted by
namespace rank and then canonical POSIX path. A `source_root` path is relative to the
verified `Settings.source_root`; a `repository` path is relative to the explicitly
validated `Settings.repository_root`. Neither namespace is inferred from the process
working directory or from an installed package path. Paths may not repeat the namespace
directory name, be absolute, contain empty/`.`/`..` components, backslashes, NUL,
percent-encoded aliases, or resolve through a symlink. No tenth direct input is allowed.

The source-manifest entry commits indirectly to all nine official source-file
checksums, so workbook paths are not duplicated as direct input entries. `VersionBundle`
and `artifact_contract_version` remain separately typed manifest fields rather than
file entries. The manifest records every direct input's exact bytes, size, and hash.
`config/artifact_build.yaml` is the production artifact-count/schema/link baseline; the
production builder never imports or reads `tests/contracts/expected_source_audit.json`.
The existing independent source-audit command and frozen test baseline remain a
separate mandatory gate.

### 2.2 Runtime outputs

The managed artifact root contains:

```text
manifest.json
finproof.duckdb
reports/source_audit.json
reports/quality_summary.json
parquet/bronze_source_column.parquet
parquet/bronze_source_row.parquet
parquet/bronze_source_cell.parquet
parquet/silver_bond_instrument.parquet
parquet/silver_domestic_listed_product.parquet
parquet/silver_overseas_listed_product.parquet
parquet/silver_fund_item.parquet
parquet/silver_fund_item_attribute.parquet
parquet/silver_quality_issue.parquet
parquet/gold_exact_cross_source_link.parquet
parquet/gold_exact_cross_source_link_evidence.parquet
```

DuckDB contains physical, self-contained copies of the same eleven logical tables. It
does not contain views whose definitions point at staging paths, the current working
directory, or external Parquet files.

### 2.3 Explicit non-goals

Task 5 does not create placeholder or inferred tables for:

- bond/listed/fund metric policy;
- public-fund family candidates;
- overseas or public-fund eligibility;
- product aliases, fuzzy candidates, or name-based links;
- state, search, metric, evidence-locator, or answer views;
- QueryPlan, SQL compilation, runtime evidence, API, HCX, or release manifests.

The Task 5 data-artifact manifest is not the Phase 4 immutable release manifest. It
does not contain Git tags, container digests, endpoint identity, or evaluation results.

### 2.4 Legacy plan supersession

The Task 5 section in
`docs/superpowers/plans/2026-08-07-01-repository-and-data-foundation.md` predates D-022
and D-023. Its two-argument builder, undeclared `table_hashes`, generic atomic replace,
and tracked runtime-artifact examples were non-executable legacy text and have been
replaced by an approved-spec/forthcoming-plan pointer plus the eight checkpoint
boundaries. The next planning step must create
`docs/superpowers/plans/2026-08-14-phase1-task5-artifact-build.md`; after review, that
file becomes the sole Task 5 execution authority. No Task 5 production code is written
until the detailed plan is reviewed and approved.

## 3. Typed build interfaces

### 3.1 Settings

Task 5 extends `Settings` with:

```python
repository_root: Path = Path(".")
source_root: Path = Path("source_material")
artifact_build_config_path: Path = Path("config/artifact_build.yaml")
expected_artifact_contract_path: Path = Path("config/expected_phase1_artifacts.json")
```

`repository_root` is the single explicit build anchor. At settings validation, it is
resolved once to an absolute nonsymlink directory; every relative `source_root`,
`data_dir`, `artifact_dir`, `database_path`, artifact-build config, and expected-contract
path is then resolved against that anchor, never against the current working directory.
Absolute overrides are accepted only after the same containment and canonical-identity
checks; an absolute source/config path still serializes as its root-relative
`source_root` or `repository` namespace path, so invocation spelling cannot change a
logical hash. `data_dir` must resolve to `source_root / "data"`. Build validation
requires the resolved database path to be exactly
`artifact_dir / "finproof.duckdb"`. The source root, artifact root, and database path
must be distinct; the artifact root must not be the repository root, filesystem root, a
home directory, or a path inside the resolved `source_root`. No component of the source
or artifact target may be a symlink. The `Path(".")` default is resolved exactly once
when settings load; an invocation outside the checkout supplies
`FINPROOF_REPOSITORY_ROOT`. The CLI passes that resolved value, and the builder performs
no later `cwd` lookup or upward directory discovery.

### 3.2 Options and builder

```python
class ArtifactBuildOptions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    clean: bool = False
    persistence_timestamp: datetime


def build_artifacts(
    settings: Settings,
    versions: VersionBundle,
    *,
    options: ArtifactBuildOptions,
) -> ArtifactManifest: ...
```

The timestamp is required, timezone-aware, and UTC with zero offset. The builder never
calls the clock. The CLI obtains one timestamp once and injects it. The same value is
used for the manifest, Bronze `loaded_at`, and every quality issue
`first_detected_at`. JSON serialization must end in `Z`.

`VersionBundle.dataset_version`, source snapshot, dataset config snapshot, and verified
source snapshot must all equal `2026-07-11`. Config/rule versions used by the build must
equal the corresponding exact `VersionBundle` fields.

### 3.3 Errors

Expected failures use one focused `ArtifactContractError` with a closed error-code
enum covering invalid settings, unsafe target, existing target, unrecognized target,
manifest/schema/config invalidity, serialization, row/count/schema mismatch, exact-link
conflict, checksum mismatch, database validation, reproducibility, and publication
rollback failure. Messages are bounded and do not expose stack traces, arbitrary raw
payloads, or unrestricted absolute paths. Each build has an opaque operation ID.
Absolute stage/backup/recovery paths may appear only in access-controlled structured
internal diagnostics. Exception `safe_message` values and CLI output contain at most
the managed target basename plus the opaque operation ID; they never print parent,
stage, backup, source, or operator-recovery paths.

## 4. Storage type system and naming

### 4.1 Shared physical types

The following mapping is frozen for Parquet and DuckDB:

| Logical value | Arrow/Parquet | DuckDB |
|---|---|---|
| text, enum, canonical JSON, SHA-256 | `utf8` | `VARCHAR` |
| row/column number, count, integer value | `int64` | `BIGINT` |
| decimal value | `decimal128(38,18)` | `DECIMAL(38,18)` |
| date | `date32` | `DATE` |
| source-local date-time | `timestamp[us]` without timezone | `TIMESTAMP` |
| operational UTC date-time | `timestamp[us, UTC]` | `TIMESTAMPTZ` |
| boolean | `bool` | `BOOLEAN` |

Every source Decimal must round-trip exactly through `DECIMAL(38,18)`. Overflow or
scale loss is a build-blocking contract error; the builder never rounds. Empty strings
remain empty only in raw columns/JSON. Missing normalized values use SQL null.

All table and column names are lowercase snake case and come only from frozen table
specifications. The builder never accepts a caller-supplied SQL identifier.

### 4.2 Wide Silver convention

Each Silver product table contains:

```text
grain                         VARCHAR, non-null
<field>                       typed normalized/representative scalar, nullable
<field>__quality_status       VARCHAR, non-null
<derived>                     typed derived scalar, nullable                 # when applicable
<derived>__quality_status     VARCHAR, non-null                               # when applicable
<derived>__as_of_date         DATE, non-null                                  # when applicable
record_json                   VARCHAR, non-null
```

The exact physical column order for the four wide product tables is generated by one
closed algorithm:

1. emit `grain` first;
2. traverse the corresponding exact domain model fields in their declared Pydantic
   order;
3. skip only frozen structural lineage-only fields that are represented inside
   `record_json` rather than query projection (`FundItem.contributing_rows` in the
   current models);
4. for each `NormalizedValue`, immediately emit `<field>` from its
   `normalized_value`, then `<field>__quality_status` from its `quality_status`;
5. for each public-fund `FundItemValue`, immediately emit `<field>` from
   `representative.normalized_value`, then `<field>__quality_status` from
   `representative.quality_status`; its `equivalent_sources` remain only in
   `record_json` and may not create extra wide rows or columns;
6. for each `DerivedValue`, immediately emit `<field>`,
   `<field>__quality_status`, then `<field>__as_of_date`;
7. emit `record_json` last.

No alphabetical or type-group reordering is permitted. The type-group bullets in
sections 5.4 through 5.7 are complete type inventories only; they do not define column
order. A domain-model field addition, removal, or reorder must make the frozen
`TableSpec` contract test fail until an explicit design/schema decision is reviewed.
Neither the table spec nor expected baseline may auto-regenerate to accept model drift.
The fund-attribute, quality, Bronze, and Gold tables retain their explicit listed column
order because they are not governed by this wide-table derivation.

`record_json` is the authoritative fidelity serialization. The builder takes the exact
value returned by the corresponding strict Pydantic model's
`model_dump(mode="json")` and applies only sorted object keys, compact JSON separators,
UTF-8, and JSON escaping. It does not re-normalize leaf values: Pydantic's Decimal
string scale, date/date-time strings, UTC `Z` representation, raw text, list order, and
nulls remain exact. It contains raw values, normalized values, transformation rule
IDs/versions, quality states, complete locators, derived inputs, source applicable
dates, and public-fund equivalent locators.
The wide scalar columns are a query projection. For every row and every field, tests
must parse `record_json` back through the exact model and prove the projection equals
the model value. A projection is never permitted to replace or disagree with
`record_json`.

Canonical record JSON uses UTF-8, sorted object keys, compact separators, and no NaN or
Infinity. Section 8 scalar normalization does not apply inside the already JSON-mode
payload. `record_json` has no added artifact timestamp except the D-021 issue field in
the quality table.

## 5. Exact table contracts

### 5.1 `bronze_source_column`

Grain: one ordered catalog column. Primary key:
`(source_table, source_column_number)`. Sort key:
`(source_table_order, source_column_number)`.

```text
catalog_version               VARCHAR NOT NULL
source_snapshot_date          DATE NOT NULL
source_table_order            BIGINT NOT NULL
source_table                  VARCHAR NOT NULL
source_column_number          BIGINT NOT NULL
source_column_letter          VARCHAR NOT NULL
source_column_name            VARCHAR NOT NULL
source_declared_type          VARCHAR NOT NULL
source_example                VARCHAR NOT NULL
source_key_marker             VARCHAR NOT NULL
source_name_ko                VARCHAR NOT NULL
schema_file                   VARCHAR NOT NULL
schema_excel_row              BIGINT NOT NULL
```

`source_table_order` is the zero-based verified manifest order PRBD01N001, PREF01N001,
PREF02N001, PRFD01N001. There are exactly 207 rows. Column numbers are contiguous within each source table;
letters agree with numbers; names and order agree with the verified schema catalog.

### 5.2 `bronze_source_row`

Grain: one official worksheet data row. Primary key:
`(source_table, source_file, source_sheet, source_row_number)`. Sort key:
`(source_table_order, source_file, source_sheet, source_row_number)`.

```text
source_table_order            BIGINT NOT NULL
source_table                  VARCHAR NOT NULL
source_file                   VARCHAR NOT NULL
source_sheet                  VARCHAR NOT NULL
source_row_number             BIGINT NOT NULL
source_checksum               VARCHAR NOT NULL
source_snapshot_date          DATE NOT NULL
raw_payload_json              VARCHAR NOT NULL
raw_payload_sha256            VARCHAR NOT NULL
loaded_at                     TIMESTAMPTZ NOT NULL
```

`raw_payload_json` is the canonical JSON array of exact strings in header order.
`raw_payload_sha256` is SHA-256 of NUL-joined raw values, exactly matching
`DataQualityIssue.raw_payload_sha256`. `loaded_at` is the single injected persistence
timestamp and is excluded from the logical row projection.

There are exactly 145,393 rows: 42,394, 1,734, 5,646, and 95,619 by official table.

### 5.3 `bronze_source_cell`

Grain: one official raw cell. Primary key:
`(source_table, source_file, source_sheet, source_row_number,
source_column_number)`. Sort key:
`(source_table_order, source_file, source_sheet, source_row_number,
source_column_number)`.

```text
source_table_order            BIGINT NOT NULL
source_table                  VARCHAR NOT NULL
source_file                   VARCHAR NOT NULL
source_sheet                  VARCHAR NOT NULL
source_row_number             BIGINT NOT NULL
source_column_name            VARCHAR NOT NULL
source_column_number          BIGINT NOT NULL
source_column_letter          VARCHAR NOT NULL
source_checksum               VARCHAR NOT NULL
source_snapshot_date          DATE NOT NULL
source_applicable_date        DATE NULL
raw_value                     VARCHAR NOT NULL
```

There are exactly 6,401,851 rows:

```text
42,394 * 40 + 1,734 * 73 + 5,646 * 49 + 95,619 * 45
```

Every cell joins exactly once to its Bronze row and catalog column. Reconstructing each
row's ordered `raw_value` list must equal `raw_payload_json` byte-for-byte after
canonical JSON serialization.

### 5.4 `silver_bond_instrument`

Grain: `instrument`. Sort/unique key: `product_id`.

Normalized scalar fields and types:

- text: `product_id`, `name`, `short_name`, `currency`, `bond_kind_raw`,
  `credit_rating`, `credit_rating_agencies_raw`;
- date: `issue_date`, `maturity_date`, `source_update_date`, `credit_rating_date`;
- decimal: `coupon_rate`, `buy_yield`, `buyable_quantity`, `duration`,
  `evaluation_price`;
- integer: `source_remaining_days`.

Derived fields are `remaining_days_at_as_of` (`BIGINT`) and
`is_matured_at_as_of`, `has_positive_buyable_quantity`,
`is_buyable_validated_at_as_of` (`BOOLEAN`). Each derived field has its own quality and
as-of columns. All 17 normalized fields have a `<field>__quality_status` column.
There are exactly 42,394 rows.

### 5.5 `silver_domestic_listed_product`

Grain: `listed_product`. Sort/unique key: `product_id`.

- text: `product_id`, `market_identifier`, `product_type`, `name`, `short_name`,
  `currency`, `risk_code`, `risk_name`, `base_index`, `manager`, `asset_type`,
  `region`;
- date: `listing_date`, `listing_end_date`, `custom_update_date`,
  `weekly_update_date`;
- timestamp without timezone: `daily_update_at`;
- boolean: `sale_flag`, `suspension_flag`;
- decimal: `aum_primary`, `aum_secondary`, `total_fee`, `tracking_error`,
  `difference_rate`, `return_1d`, `return_1m`, `return_3m`, `return_6m`, `return_1y`,
  `return_ytd`;
- derived boolean: `is_eligible_at_as_of` with quality and as-of columns.

Every normalized field has a quality column. There are exactly 1,733 rows. Excel row
1,155 with raw `pd_itm_no="KR"` remains only in Bronze and quality output.

### 5.6 `silver_overseas_listed_product`

Grain: `listed_product`. Sort/unique key: `product_id`.

- text: `base_index`, `etn_flag_raw`, `manager`, `replication_method`,
  `index_tracking_flag_raw`, `inverse_short_flag_raw`, `strategy`,
  `daily_base_date_match_raw`, `daily_close_source`, `ticker`,
  `source_currency_raw`, `exchange_market_code`, `product_type`, `isin`, `product_id`,
  `market_identifier`, `lipper_id`, `market_code`, `name`, `sale_flag_raw`,
  `trading_currency`, `suspension_flag_raw`, `us_cik`, `core_flag_raw`, `asset_type`,
  `region`;
- date: `custom_update_date`, `close_price_base_date`, `daily_update_date`,
  `listing_date`, `weekly_update_date`;
- timestamp without timezone: `nav_base_at`;
- decimal: `total_fee`, `leverage_factor`, `daily_bid_price`, `close_price`,
  `difference_rate_raw_metric`, `return_1d`, `daily_high_price`, `aum`, `last_nav`,
  `daily_low_price`, `daily_open_price`, `daily_value`, `daily_volume`, `listing_price`,
  `listed_share_count`, `realtime_market_price`, `realtime_market_volume`.

Every one of the 49 normalized fields has a quality column. There is no derived
eligibility, staleness, or dataset-level constant field. There are exactly 5,646 rows.

### 5.7 `silver_fund_item`

Grain: `fund_item`. Sort/unique key: `fund_item_id`.

- text: `benchmark_english_name`, `benchmark_name`, `currency`,
  `exchange_traded_flag_raw`, `establishment_country_code`, `region_description`,
  `establishment_type_code`, `foreign_base_price_flag_raw`, `fss_item_id`,
  `hedge_fund_flag_raw`, `interest_dividend_description`, `short_name`,
  `english_short_name`, `english_name`, `name`, `fund_item_id`,
  `kofia_classification_code`, `ksd_id`, `manager_item_id`, `offshore_fund_flag_raw`,
  `fund_type_raw`, `manager_external_code`, `overseas_fund_description`,
  `investor_type_description`, `professional_sale_control_code`,
  `private_fund_description`, `offering_type_description`, `family_candidate_key`,
  `sale_status_raw`, `standard_item_id`, `mirae_sale_flag_raw`,
  `trustee_external_code`, `risk_code`, `risk_name`;
- decimal: `return_18m`, `return_1m`, `return_3m`, `return_6m`, `net_assets`,
  `return_1w`, `return_1y`, `return_2y`, `return_3y`, `return_5y`.

Each of the 44 representative values has a quality column. `record_json` retains the
complete `FundItem`, including all contributing `SourceRow` values and all equivalent
locators. `family_candidate_key` remains a raw/normalized source field; it does not
create a family. There are exactly 11,138 rows.

### 5.8 `silver_fund_item_attribute`

Grain: `fund_attribute`. Sort/unique key:
`(fund_item_id, attribute_code, attribute_code_raw, source_row_number)`.

```text
grain                         VARCHAR NOT NULL
fund_item_id                  VARCHAR NOT NULL
fund_item_id__quality_status  VARCHAR NOT NULL
attribute_code                VARCHAR NOT NULL
attribute_code__quality_status VARCHAR NOT NULL
attribute_code_raw            VARCHAR NOT NULL
source_row_number             BIGINT NOT NULL
record_json                   VARCHAR NOT NULL
```

The raw attribute column is explicit because normalized trimming must never erase the
official padded code. `record_json` is the canonical `FundItemAttribute` dump. There
are exactly 95,618 rows. Excel row 84,563 remains only in Bronze and quality output.

### 5.9 `silver_quality_issue`

Grain and sort key:
`(source_table, source_file, source_sheet, source_row_number,
source_column_number, rule_id, issue_id)`. `issue_id` is unique.

```text
issue_id                      VARCHAR NOT NULL
rule_id                       VARCHAR NOT NULL
rule_version                  VARCHAR NOT NULL
severity                      VARCHAR NOT NULL
quality_status                VARCHAR NOT NULL
source_table                  VARCHAR NOT NULL
source_file                   VARCHAR NOT NULL
source_sheet                  VARCHAR NOT NULL
source_row_number             BIGINT NOT NULL
source_column_name            VARCHAR NOT NULL
source_column_number          BIGINT NOT NULL
source_column_letter          VARCHAR NOT NULL
source_checksum               VARCHAR NOT NULL
source_snapshot_date          DATE NOT NULL
source_applicable_date        DATE NULL
reason                        VARCHAR NOT NULL
quarantined                   BOOLEAN NOT NULL
raw_payload_sha256            VARCHAR NOT NULL
first_detected_at             TIMESTAMPTZ NOT NULL
record_json                   VARCHAR NOT NULL
```

Pure normalizers must supply `first_detected_at=None`; a non-null incoming value is a
contract error. Persistence reconstructs and validates a new `DataQualityIssue` with
the injected UTC time. `record_json` is exactly its canonical D-021 JSON and must pass
`schemas/quality_issue.schema.json` using `Draft202012Validator` with an explicit
`FormatChecker`.

Every issue joins to exactly one Bronze row/cell and its raw-payload hash must equal the
Bronze row hash. Exactly two distinct source rows have quarantined issues. The current
row-issue count of 6,032 is recorded in build evidence but is not a frozen manifest
acceptance count.

### 5.10 `gold_exact_cross_source_link`

Grain: one exact item-grain link. Sort/unique key:
`(left_product_id, right_product_id, rule_version)`.

```text
link_id                       VARCHAR NOT NULL
left_table                    VARCHAR NOT NULL
left_product_id               VARCHAR NOT NULL
left_identifier_field         VARCHAR NOT NULL
right_table                   VARCHAR NOT NULL
right_product_id              VARCHAR NOT NULL
right_identifier_field        VARCHAR NOT NULL
matched_raw_identifier        VARCHAR NOT NULL
link_type                     VARCHAR NOT NULL
confidence                    DECIMAL(38,18) NOT NULL
rule_id                       VARCHAR NOT NULL
rule_version                  VARCHAR NOT NULL
```

Frozen constants are:

```text
left_table = silver_domestic_listed_product
left_identifier_field = pd_itm_no
right_table = silver_fund_item
right_identifier_field = ksd_itm_no
link_type = exact_identifier
confidence = 1.0
rule_id = cross_source.domestic_etf_public_fund.exact_raw_identifier
rule_version = 1.0.0
```

Only a domestic record whose source product type is exactly ETF participates. The join
uses the exact untrimmed left `product_id.raw_value` and right
`ksd_id.representative.raw_value`. Trimming is measured only as an acceptance check;
it never creates a link. All equivalent fund `ksd_id` raw values must agree.

The official result is 47 one-to-one `(left_product_id, right_fund_item_id)` pairs,
with no conflict and no difference between raw and trimmed pair sets. Sorted canonical
TSV `{left_id}\t{right_item_id}\n` is 1,222 bytes and has SHA-256:

```text
8f1049ae6137dbd2141214248c9871f8c4dcced3fcb81cb7c72c2f0863d3a962
```

`link_id` is SHA-256 of the NUL-separated rule ID, rule version, left table/ID,
right table/ID, and matched raw identifier. A left ID resolving to multiple right item
IDs, a right item resolving to multiple left IDs, or disagreeing equivalent right raw
values blocks the build. Repeated public-fund attribute rows are evidence, not duplicate
links.

### 5.11 `gold_exact_cross_source_link_evidence`

Grain: one exact source locator supporting one link. Sort/unique key:
`(link_id, evidence_role_order, evidence_ordinal)`.

```text
link_id                       VARCHAR NOT NULL
evidence_role                 VARCHAR NOT NULL   # left_identifier | right_identifier
evidence_role_order           BIGINT NOT NULL    # 0 left, 1 right
evidence_ordinal              BIGINT NOT NULL    # zero-based within role
raw_identifier               VARCHAR NOT NULL
source_table                  VARCHAR NOT NULL
source_file                   VARCHAR NOT NULL
source_sheet                  VARCHAR NOT NULL
source_row_number             BIGINT NOT NULL
source_column_name            VARCHAR NOT NULL
source_column_number          BIGINT NOT NULL
source_column_letter          VARCHAR NOT NULL
source_checksum               VARCHAR NOT NULL
source_snapshot_date          DATE NOT NULL
source_applicable_date        DATE NULL
```

Each link has exactly one left `pd_itm_no` locator and every equivalent right
`ksd_itm_no` locator from the fund item. Official acceptance is exactly 371 locators:
47 left plus 324 right.

Every evidence row must join to exactly one `bronze_source_cell` on the complete
locator key. For every row:

```text
evidence.raw_identifier
  == joined bronze_source_cell.raw_value
  == parent link matched_raw_identifier
```

For role `left_identifier`, ordinal is exactly zero, the source field is `pd_itm_no`,
and the locator/value equal the linked domestic record's `product_id` NormalizedValue.
For role `right_identifier`, the source field is `ksd_itm_no`, ordinals are contiguous
from zero, and locator/value order exactly equals the linked FundItem
`ksd_id.equivalent_sources` order. Evidence may not be deduplicated, reordered, or
reconstructed from only Bronze proximity. Conversely, every locator in those two
authoritative wrapper sources must have one and only one evidence row. Tests validate
the full bidirectional relation for all 371 official rows and synthetic missing,
duplicate, swapped-role, noncontiguous-ordinal, wrong-field, wrong-raw-value, and
wrong-parent-link failures.

## 6. Bounded build pipeline

The builder uses a same-filesystem sibling staging directory. It never writes directly
into the published target.

### 6.1 Verify and initialize

1. Validate settings, options, config schemas, versions, and safe paths.
2. Verify all nine official source inputs before opening a data workbook.
3. Validate the quality and artifact JSON schemas with explicit format checkers.
4. Create a private sibling staging directory, fixed table writers, and one temporary
   on-disk DuckDB used only for bounded external ordering.

The staging DuckDB and its spill directory are inside the private build directory and
use fixed settings:

```text
threads = 1
memory_limit = "1GiB"
temp_directory = <private-stage>/duckdb-temp
preserve_insertion_order = false
```

The internal stage/temp paths are constructed by the builder, never accepted from the
CLI, and excluded from every logical/physical runtime inventory. The connection is
closed before cleanup. On pre-publication failure, the published target remains
unchanged and the builder removes only its recognized staging database/temp directory.
If that cleanup fails, it raises a bounded `STAGING_CLEANUP_FAILED` and retains the
recognized private stage for next-run recovery; it never broadens the delete target.

Concurrent/orphan safety uses an advisory exclusive lock on one deterministic sibling
lock file named `.<target-basename>.finproof-build.lock`. A stage basename is
`.<target-basename>.finproof-stage-<opaque-operation-id>`; its sibling marker is the
same basename plus `.marker`. The marker is created exclusively with mode 0600 and
contains the same operation ID, `artifact_set_id`, artifact contract version, and
intended target basename. Backups use the analogous
`.<target-basename>.finproof-backup-<opaque-operation-id>` directory and `.marker`
sidecar. Post-commit cleanup uses the analogous
`.<target-basename>.finproof-cleanup-<opaque-operation-id>` tombstone and `.marker`.
A marker is never placed inside or added to a verified artifact directory, so
renaming the old target to backup does not alter its bytes or inventory. While another
process holds the lock, the builder refuses to build or clean. After acquiring the
lock, a later invocation may remove an orphan stage only when the candidate is a
nonsymlink sibling directory, its basename and sidecar marker agree exactly, its target
basename matches, and its resolved path is neither target, backup, source root,
repository root, nor home.
Missing, malformed, duplicated, or mismatched markers are an
`UNRECOGNIZED_ORPHAN_STAGE` hard stop, not a cleanup invitation. The user-facing error
reports only the opaque operation ID; full recovery paths remain internal diagnostics.

### 6.2 Bronze and non-fund Silver

The source catalog is emitted in catalog order. Each workbook is streamed once in
manifest order. Every `SourceRow` is written to bounded Bronze row/cell batches before
normalization. Because Bronze sort keys begin with the frozen manifest
`source_table_order`, these batches are already in final order.

The official bond, domestic-listed, and overseas product IDs are not source-sorted.
Their normalized wide rows and issues therefore enter bounded batches in the temporary
DuckDB, not final Parquet. After ingestion, DuckDB externally orders each Silver table
by its frozen key and externally orders the combined `silver_quality_issue` relation by
its global frozen key before fixed-size batches are streamed to Parquet. Link and link-
evidence outputs use the same stage/sort/export boundary. No non-source-sorted table may
be sorted by materializing all rows in a Python list or DataFrame.

### 6.3 Bounded public-fund collapse

Official public-fund input is not item-grouped, and the existing complete normalization
acceptance has exceeded 7 GB peak RSS. Artifact building therefore must not call
`normalize_public_funds` over all 95,619 rows and then construct a full DataFrame.

The build stages only canonical `SourceRow` payloads plus a validated item key in the
same temporary DuckDB relation. It orders rows by normalized item key and source row,
reconstructs exact `SourceRow` instances, and gives one complete item group at a time
to the authoritative public-fund normalization/collapse behavior. The official maximum
live group is 16 rows. Item and attribute output is already in the frozen item/attribute
order and enters fixed-size Parquet writers. Fund issues enter the shared temporary
quality relation so the final cross-product quality order is produced by the bounded
external sort. Objects are released before the next batch.

The staging relation is not a runtime artifact, is not hashed, and is removed after
success or failure under the cleanup rule in section 6.1. It may not implement
independent normalization policy in SQL. SQL only stores and orders validated source
values; Python normalizers remain authoritative.
Synthetic duplicate, normalized-collision, and disagreement groups must produce the
same fail-closed behavior as Task 4.

### 6.4 Finalize

Each Parquet file is closed, reopened, and checked against its frozen schema, count,
sort order, uniqueness, and logical hash. Reports are then written. DuckDB tables are
materialized from verified Parquet in explicit order, closed and reopened read-only,
and validated. Only after every file hash and manifest invariant passes may publication
begin.

## 7. Reports and quarantine

### 7.1 Source audit report

`reports/source_audit.json` is an observed artifact-build report. It contains the build
contract version, source snapshot, verified source-manifest/catalog hashes, source row/
cell/column counts by table, emitted Silver counts, quarantine source-row count, exact
link/evidence counts, and the canonical pair hash. Expected values come from
`config/artifact_build.yaml`; the report records expected and observed values and is
written only when they are equal.

It does not copy a file from `tests/`, and it does not replace the independent detailed
`tools/audit_source_data.py --check` gate.

### 7.2 Quality summary

`reports/quality_summary.json` deterministically contains:

- total issues and distinct affected source rows;
- counts by source table, rule ID/version, severity, quality status, and quarantine flag;
- quarantined issue and distinct source-row counts;
- excluded Silver records by native grain;
- SHA-256 of the quality table's logical projection.

Arrays and mapping keys use lexical order. No persistence timestamp enters report
logical content. The two quarantined rows remain recoverable through their complete
Bronze rows and cells.

### 7.3 Report logical identity

Both reports have strict, versioned Pydantic contracts. Their canonical
logical bytes are compact sorted-key JSON plus one terminal newline. They contain no
wall-clock or output-path field. Each report receives a canonical SHA-256 independent
of its pretty on-disk rendering. The report models carry closed semantic IDs:
`source_audit` and `quality_summary` respectively.

The manifest `ArtifactFile.logical_hash` is required and non-null for exactly the two
`kind=report` entries, together with the matching `report_id`. Both fields are null for
`parquet` and `duckdb`, whose logical or physical identity is covered elsewhere. The
ordered `(report_id, report logical_hash)` pairs, in closed ID order `source_audit`,
`quality_summary`, enter the overall manifest logical hash and the tracked expected
Phase 1 artifact contract. A report's output path belongs only to physical inventory
and is excluded from logical identity. Therefore a timestamp-free report semantic
change changes artifact identity, while moving the same verified report does not.

## 8. Canonical hashing and reproducibility

### 8.1 Canonical value encoding

Typed table projections, schemas, reports, and manifests use a dedicated scalar
serializer, never `repr`, Python `hash`, locale, or database file bytes:

- objects: keys sorted by Unicode code point;
- arrays: preserved frozen order;
- strings: UTF-8 JSON with `ensure_ascii=False`;
- null/boolean/integer: normal JSON literals;
- Decimal: non-exponent base-10 form with insignificant trailing fractional zeroes
  removed and every numerical zero rendered as `"0"`;
- date: `YYYY-MM-DD`;
- source-local datetime: ISO-8601 without an invented timezone;
- UTC operational datetime: microsecond-precision terminal-`Z` form;
- `PurePosixPath`: POSIX string;
- enum: its string value;
- NaN and Infinity: prohibited.

Decimal trailing-zero removal and UTC microsecond normalization in this list apply only
to typed scalar/table/hash values. They never rewrite strings or leaf values inside a
strict model's exact JSON-mode payload. A `record_json` column enters a logical row hash
as its exact string. Canonical JSON bytes use compact separators and one `\n` terminator
per row.

### 8.2 Schema and table hashes

Each immutable `TableSpec` declares table name, layer, grain, ordered columns and types,
nullable state, sort key, unique key, logical-row projection, and Parquet path. Its
`schema_sha256` is computed from a narrower canonical schema-identity projection that
contains exactly:

```text
table_name
grain
ordered columns: name, logical type, Arrow type, DuckDB type, nullable
unique_key
sort_key
```

Layer, Parquet/output path, physical file kind, compression settings, row count, and
logical-row data are excluded from `schema_sha256`. Moving an otherwise identical table
to a different output path therefore does not change its schema identity. The table
logical hash still covers this schema hash, its logical row projection, and row count.

The table logical hash stream is:

```text
canonical({
  "schema_sha256": <lowercase SHA-256>,
  "logical_projection": [<ordered logical column names>],
  "row_count": <nonnegative integer>
}) + "\n"
canonical(logical row 1) + "\n"
...
```

That three-key canonical JSON object is the entire table-hash header. Path, layer,
writer options, file kind, and physical metadata are prohibited. Table name, grain,
column contracts, and sort/unique keys are already committed by `schema_sha256` and are
not duplicated in the header. Independent hash-implementation tests must reproduce the
same bytes and prove path/layer invariance.

Rows are in the table's frozen sort order. For `bronze_source_row`, `loaded_at` becomes
null in the logical projection. For `silver_quality_issue`, `first_detected_at` becomes
null and the logical `record_json` is reconstructed with a null timestamp. No other
field is excluded.

### 8.3 Manifest logical hash

The overall logical hash covers:

```text
manifest_version
artifact_contract_version
artifact_set_id
dataset_version
ordered logical input namespace/path/kind/size/SHA-256 entries
exact VersionBundle
ordered table name/grain/schema/count/sort/logical-hash entries
ordered semantic report-ID/logical-hash entries
```

It excludes persistence time, stage/output paths, artifact file sizes, compression
bytes, physical file hashes, and database SHA-256. Verified logical-input paths, sizes,
and hashes remain covered. Changing any logical row, schema, source, rule/config
version, or table count changes it.

### 8.4 Physical integrity

Physical SHA-256 values cover each Parquet file, report, and the closed DuckDB file.
They prove that a published generation has not changed; they are not the cross-time or
cross-platform logical reproducibility claim. Reproduction tests recompute and verify
each generation's declared physical hashes but do not require separate DuckDB files to
have equal bytes.

## 9. Parquet and DuckDB construction

### 9.1 Parquet

Every table is one file, never a partitioned directory. Writers use the exact explicit
schema and these fixed options:

```text
compression = zstd
compression_level = 3
statistics = true
row_group_size = 65,536
data_page_size = 1,048,576
```

Rows reach the writer in final sort order, and the builder does not write multiple
tables concurrently. Physical bytes remain generation-specific integrity data rather
than the logical reproducibility identity. Library versions are pinned by `uv.lock`.
Task 5 moves `jsonschema` and `rfc3339-validator` from dev-only availability into
runtime dependencies because artifact and D-021 validation occur in production build
code.

### 9.2 DuckDB

Construction uses one writer connection with:

```text
threads = 1
preserve_insertion_order = true
TimeZone = UTC
```

Static allowlisted DDL creates all eleven tables with explicit column order/types.
Verified Parquet rows are inserted with an explicit final `ORDER BY`. The builder
checkpoints and closes the database, requires no `.wal`, hashes the closed file, and
reopens it read-only to validate information-schema columns, counts, uniqueness, sort
probes, link evidence, and manifest agreement.

```python
def open_read_only_database(path: Path) -> duckdb.DuckDBPyConnection: ...
```

The function accepts only an existing nonsymlink regular file and calls DuckDB with
`read_only=True` and `enable_external_access=false`. Integration tests require
persistent INSERT, UPDATE, DELETE, and CREATE attempts against the artifact database,
plus external ATTACH and COPY attempts, to fail. DuckDB session-local TEMP objects are
outside this persistence contract; the public FinProof query path never exposes raw SQL
or creates them.

## 10. Artifact manifest

### 10.1 Typed shape

All models are frozen, strict, and forbid extra fields. Mappings are deeply immutable
after validation.

```text
ArtifactManifest
  manifest_version              literal "1.0.0"
  artifact_contract_version     literal "1.0.0"
  artifact_set_id               literal "finproof-data-artifacts/v1"
  dataset_version               date
  persistence_timestamp         UTC datetime
  source_inputs                 ordered tuple[ArtifactInput]
  versions                      exact ArtifactVersions
  files                         ordered tuple[ArtifactFile]
  database_path                 safe relative path
  database_sha256               lowercase SHA-256
  tables                        exact immutable map[str, ArtifactTable]
  logical_hash                  lowercase SHA-256

ArtifactInput
  namespace, path, kind, size_bytes, sha256

ArtifactFile
  path, kind, size_bytes, sha256, report_id, logical_hash

ArtifactTable
  table_name, layer, grain, parquet_path, row_count,
  schema_sha256, sort_key, unique_key, logical_hash
```

`ArtifactVersions` has exactly the seven fields of `VersionBundle`; arbitrary registry
keys are forbidden. `ArtifactInput` uses the exact nine-entry namespace/path inventory
and closed per-path kind literals in section 2.1. Artifact-file paths are safe
artifact-root-relative POSIX
paths with no absolute path, `..`, NUL, symlink interpretation, or duplicate canonical
path. SHA values are lowercase 64-hex. File and table inventories must be complete,
unique, and lexically ordered. `files` contains exactly the eleven Parquet files, two
reports, and `finproof.duckdb`: fourteen entries total. It excludes `manifest.json`,
because the manifest does not hash itself. `database_path` must identify that same sole
DuckDB file entry and `database_sha256` must equal the entry's physical SHA-256.
`ArtifactFile.logical_hash` is required only for the two timestamp-free reports and
prohibited for Parquet/database entries. `ArtifactFile.report_id` follows the same
conditional rule: it is required for reports, must be the exact closed ID declared by
the parsed report, and is prohibited otherwise. Exactly one report entry has
`source_audit` and exactly one has `quality_summary`; report paths do not determine
semantic identity. `ArtifactFile.kind` is the closed literal `parquet`, `report`, or
`duckdb` and must agree with the exact path inventory.

`schemas/artifact_manifest.schema.json` is updated to match this model exactly,
including terminal-`Z` UTC validation. Runtime and contract consumers call
`Draft202012Validator.check_schema`, supply `FormatChecker`, and inspect every error.

### 10.2 Load and verify

```python
@classmethod
def ArtifactManifest.load(path: Path) -> ArtifactManifest: ...

def ArtifactManifest.verify(root: Path) -> VerifiedArtifactSet: ...
```

`load` performs safe JSON/domain/schema validation without trusting paths or opening
artifact files. `verify` resolves each declared path under one root without following
symlinks. Before trusting the root it recursively inventories it without following
links: the exact tree is root `manifest.json`, the fourteen declared nonsymlink regular
files, and only the required `parquet/` and `reports/` nonsymlink directories. Any extra
file/directory, symlink, socket, device/special file, canonical-path duplicate, hardlink
alias (`st_nlink != 1`), DuckDB `.wal`, or missing entry is a hard stop. Operational
stage/backup/tombstone markers are sibling sidecars outside this tree. Verification then
checks each file's type/size/SHA-256, checks the database hash, and independently
recomputes rather than trusting declared logical metadata. It reads each Parquet table,
revalidates the exact schema/count/sort/unique contract, recomputes `schema_sha256` and
the canonical table `logical_hash`, and compares both with the manifest. It parses both
reports through their strict contracts, checks each closed `report_id`, recomputes its
logical hash, and compares both with the report file entry. Finally it reconstructs the complete manifest
logical projection from the strictly validated declared input identities, versions,
table metadata, and report hashes, recomputes `ArtifactManifest.logical_hash`, and
compares it before opening DuckDB
read-only. For every table, DuckDB's exact schema and count must agree, and a
bidirectional typed `EXCEPT ALL` comparison between the verified Parquet relation and
the self-contained DuckDB table must return zero rows. Column lists and table names come
only from `TableSpec`; values are not coerced to text. This proves exact multiset content
equality and rejects a database with the same schema/count but changed values. The
frozen table sort probes separately prove DuckDB can reproduce canonical order.
Verification is all-or-nothing; a physical checksum match never substitutes for
Parquet logical verification, overall logical verification, or database content
equality.

Operational consistency is verified separately from logical reproducibility. The
manifest `persistence_timestamp` must equal every `bronze_source_row.loaded_at`, every
non-null `silver_quality_issue.first_detected_at`, and the corresponding timestamp
inside each quality `record_json`; pure-normalizer null input is not persisted as null.
A timestamp-only file mutation, a mixed row timestamp, or a typed-column/JSON mismatch
is rejected even though the timestamp is removed from logical projections.

DuckDB/Parquet equality verification uses `tempfile.TemporaryDirectory` under the
trusted OS operational temp base, or an optional containment-validated
`FINPROOF_RUNTIME_TMP_ROOT`. It creates one mode-0700 unique marker-owned directory and
private DuckDB spill below it, never under the artifact root or its parent. Verification
uses `threads=1`, `memory_limit="1GiB"`, and no caller-provided SQL or path. It closes
the connection before removing only that exact marker-owned temp. Spill, close, marker,
or cleanup failure is a bounded typed verification error; tests force external spill
and each cleanup failure without permitting a broad delete or unbounded comparison.

`verify(root)` does not pretend that the artifact root contains the original repository
or source workbooks. It recomputes the overall hash from the manifest's strictly
validated nine declared input identities. The offline builder separately re-hashes all
nine direct input files before ingestion, while evaluation/readiness anchors every
declared input identity by exact comparison with the tracked packaged expected
contract. A caller that needs fresh-input verification must use the builder/source-audit
boundary; artifact-only verification cannot silently substitute current checkout files.

The tracked logical baseline has a separate strict interface:

```python
class ExpectedPhase1ArtifactContract(BaseModel): ...

@classmethod
def ExpectedPhase1ArtifactContract.load(path: Path) -> ExpectedPhase1ArtifactContract: ...

def compare_expected_artifact_contract(
    verified: VerifiedArtifactSet,
    expected: ExpectedPhase1ArtifactContract,
) -> None: ...
```

`ExpectedPhase1ArtifactContract` contains artifact-set identity, contract/dataset
versions, exact logical input identities, ordered table names/grains/schema hashes/
counts/sort and unique keys/logical hashes, the two report logical hashes, overall
manifest logical hash, exact link-pair hash, and evidence count. Reports are keyed only
by their closed semantic IDs. It contains no
persistence timestamp, artifact output path, artifact size, or physical hash.
Comparison reports every deterministic field difference and fails closed; it never
updates the expected file.

The initial baseline has one review-only bootstrap boundary outside the installed
package and `finproof` CLI:

```python
def build_candidate_artifacts(
    settings: Settings,
    versions: VersionBundle,
    *,
    options: ArtifactBuildOptions,
) -> ExpectedPhase1ArtifactContract: ...
```

This interface lives only in repository review tooling, is not exported by the package,
has no console entry point, and is unavailable to runtime/readiness. It refuses to run
if either the repository expected-contract file or its packaged resource already
exists. It builds with the exact production transformation into a fresh private
temporary target, performs full manifest/Parquet/report/DuckDB verification, never
calls publication, and omits only the impossible expected-contract comparison. It
returns/prints canonical candidate-contract JSON for review but cannot write, update,
accept, or publish `config/expected_phase1_artifacts.json`; its temporary artifacts are
removed under the guarded marker rules. A second existence check immediately before
candidate output closes the concurrent-bootstrap race.

Humans may create the initial tracked file only in a separate review-only change after
independently checking source identities, counts, table/report/overall hashes, pair
hash, evidence count, and two full official candidate reproductions. Checkpoint 1 may
create only the expected-contract model/loader/comparator, packaging configuration, and
synthetic-fixture bootstrap tests; it must not create placeholder, guessed, or premature
official baseline content. The official `config/expected_phase1_artifacts.json` and its
wheel byte-identity test are created and committed only at Checkpoint 8 after independent
review. Once that file exists, the candidate interface permanently refuses rather than
becoming an update mechanism.

Official Phase 1 acceptance must first call `ArtifactManifest.load(...).verify(root)`
and only then compare the returned verified set with the separately loaded tracked
`config/expected_phase1_artifacts.json`. Evaluation-mode `build_artifacts` performs the
same comparison on the fully verified staged set before publication, and evaluation
runtime/readiness uses the packaged expected contract; neither path has an option to
skip it. Extended-demo tooling may accept an explicitly different expected contract,
but it cannot be used in evaluation mode. Unit tests prove that physical-file,
Parquet-logical, report-logical, overall-logical, DuckDB same-count/different-value, and
expected-contract mismatches fail at distinct boundaries.

The manifest does not hash itself. Its serialized bytes are canonical pretty JSON with
stable key order and one terminal newline for reviewability; its `logical_hash` follows
section 8 rather than hashing those physical bytes.

### 10.3 Runtime schema packaging

Manifest verification is a runtime/readiness capability and may not depend on the
checkout current working directory. The root files
`schemas/artifact_manifest.schema.json` and `schemas/quality_issue.schema.json` remain
the repository contract sources. The wheel build uses explicit Hatch
`force-include` entries to package those exact bytes as:

```text
finproof/resources/schemas/artifact_manifest.schema.json
finproof/resources/schemas/quality_issue.schema.json
```

Runtime loaders use `importlib.resources`, not `Path.cwd()` or a source-tree parent
calculation. A wheel contract test builds the wheel, opens both packaged resources, and
proves byte/SHA equality with the root schema files. Editable-install tests prove the
same public loader works. Installed-wheel artifact verification uses only the caller's
artifact root plus package resources; it neither requires nor synthesizes a
`repository_root`. The explicit repository anchor is an offline-build input boundary.

The separately tracked official logical contract has one repository source of truth,
`config/expected_phase1_artifacts.json`, and is force-included byte-for-byte as
`finproof/resources/contracts/expected_phase1_artifacts.json`. Evaluation readiness
loads it with `importlib.resources`; no production code reads a path below `tests/`.
Wheel tests prove source/resource byte and SHA equality for this contract too. The
production package also declares `jsonschema` and `rfc3339-validator` as runtime
dependencies. Other artifact config and official sources remain offline build inputs
and are not silently copied into the runtime wheel.

## 11. Guarded transactional publication

Portable filesystems cannot atomically replace a non-empty directory with one
`os.replace`. Task 5 therefore promises offline transactional publication with rollback,
not simultaneous-reader atomicity.

1. Build and fully verify a private sibling staging directory on the same filesystem.
2. If target is absent, rename stage to target.
3. If target exists without `clean=True`, fail before changing it.
4. If `clean=True`, refuse a symlink, non-directory, empty/unrecognized directory, or a
   directory whose manifest cannot load and verify as `finproof-data-artifacts/v1`,
   including any extra tree entry, special file, hardlink alias, or canonical duplicate.
   Recognition failure is byte-preserving: clean does not rename, unlink, or chmod any
   target entry.
5. Rename the verified old target to a private sibling backup.
6. Rename the verified stage to target.
7. If step 6 fails, restore the backup; a failed restoration is a distinct high-severity
   typed error that preserves both paths only in internal structured diagnostics for
   operator recovery.
8. After either stage-to-target rename in step 2 or step 6, reopen and verify the new
   target, then remove the now-orphaned stage sidecar marker. If verification or marker
   removal fails, publication has not committed: move the recognized target back to its
   marked stage name and restore a verified backup when one exists; otherwise leave the
   target absent. A failed move or restore is the distinct high-severity recovery error
   from step 7.
9. Successful post-rename verification and stage-marker removal are the publication
   commit point. Before this point the verified backup is never recursively or
   partially deleted.
10. After commit, create the exact cleanup marker and atomically rename the verified
   backup directory to its cleanup-tombstone basename. Only after that rename may the
   publisher recursively remove the marked tombstone, then its marker and obsolete
   backup marker. The tombstone is no longer a rollback dependency.
11. If the atomic rename or recursive tombstone cleanup fails after the commit point,
   do not roll back or delete the newly verified target. Raise
   `BACKUP_CLEANUP_FAILED_AFTER_PUBLISH`, state explicitly that publication succeeded,
   and retain recovery state. A failed backup-to-tombstone rename leaves the complete
   verified backup intact. A failure after that rename may leave only a marker-bound,
   possibly partial tombstone and must not claim that a verified backup remains. The
   safe message contains only target basename and opaque operation ID.

Stage and backup names are unpredictable operational names and never enter hashes.
Failure before publication leaves the prior target byte-identical. Tests inject failures
at both rename boundaries and during post-publication cleanup. A later invocation first
examines sibling remnants created by this exact publisher: if the target verifies, it
may atomically tombstone a separately verified retained backup or resume deletion of
only an exact marker/path-matched cleanup tombstone, even when that tombstone is already
partial. If the target is absent, it restores the verified backup and never consumes a
partial tombstone. Any ambiguous or unverified non-tombstone remnant is a hard stop. No
operation recursively deletes an unresolved path, source root, repository root, home
directory, or unrecognized content.

Post-commit cleanup has this closed remnant state machine for one operation ID:

```text
verified backup dir + backup marker
  -> verified backup dir + backup marker + prepared tombstone marker
  -> tombstone dir + tombstone marker + obsolete backup marker
  -> tombstone marker + obsolete backup marker       # directory deletion succeeded
  -> obsolete backup marker                          # tombstone-marker unlink succeeded
  -> no remnant                                      # backup-marker unlink succeeded
```

The prepared-marker state may retry the atomic backup-to-tombstone rename because the
complete backup has not been recursively touched. The next invocation first verifies
the new target. With that target valid, it may resume tombstone-directory deletion only
when directory basename, tombstone marker,
obsolete backup marker, target basename, and operation ID agree. When the corresponding
backup and tombstone directories are both confirmed absent, it may unlink exact
marker-only remnants in the same order: both markers to backup-marker-only, then none;
backup-marker-only may go directly to none. A tombstone-marker-only state, ambiguous
marker content, mismatched operation ID/basename, unexpected corresponding directory,
duplicate marker, or marker without a verified new target is a hard stop. Each marker
unlink is fault-injected independently; the next-run recovery test must reach `none`
without touching the artifact tree or any unrelated sibling.

## 12. CLI contract

The existing dispatcher adds:

```text
finproof build-data [--clean]
```

The command loads `Settings` and `VersionBundle`, captures one
`datetime.now(timezone.utc)` value, constructs `ArtifactBuildOptions`, and calls the
builder. It accepts no arbitrary SQL, table name, source workbook, output file, timestamp,
or version override.

- success: exit 0 and one compact, sorted JSON line containing only the managed target
  basename, manifest-relative path, database-relative path, and logical hash;
- typed source/artifact failure: exit 2 and one bounded `error: ...` stderr line;
- post-publication backup-cleanup failure: exit 2 with a bounded message that explicitly
  says the new target published and verified while marked old-generation cleanup remains
  incomplete; it does not claim the tombstone is still a complete verified backup;
- argparse usage failure: standard exit 2;
- no stack trace or partial success output.

Without `--clean`, an existing target is never changed. With `--clean`, only the
recognized guarded publication contract in section 11 is authorized.

## 13. Generated-artifact repository policy

All runtime files under `/artifacts/`, including manifest and reports, are generated and
untracked. `.gitignore` excludes the complete directory and the default sibling
transients `/.artifacts.finproof-build.lock`,
`/.artifacts.finproof-stage-*`, `/.artifacts.finproof-backup-*`, and
`/.artifacts.finproof-cleanup-*`. A clean rebuild or recoverable interrupted build must
not dirty the repository.

The repository instead tracks a deterministic
`config/expected_phase1_artifacts.json` containing artifact contract version,
the exact nine logical input identities, table schemas/counts/logical hashes, both
semantic report-ID/logical-hash pairs, overall manifest logical hash, link pair hash, and evidence
count. It excludes persistence time and physical hashes. Status records the observed
official manifest logical hash and physical file hashes for the reviewed build.

The normal builder and verifier expose no `--update`, `--accept`, or write-back option
for this contract. Its initial contents are copied from an independently verified
official candidate into a review-only change, compared against source/count/link
invariants, and committed with review evidence. Every later difference is a failing
acceptance condition, not an automatic baseline refresh.

Only the unexported review-only candidate interface in section 10.2 may omit expected
comparison, and only while the expected file/resource is absent. It cannot publish or
write the baseline. Normal evaluation build, CLI, verifier/readiness, and packaged
runtime expose no skip path.

If organizers later require binary delivery, the exact generated artifact set is stored
outside Git under an immutable link and checksum, or committed only after an explicit
repository-policy decision. Task 5 does not make that release decision.

## 14. TDD and checkpoint sequence

Every production behavior begins with a focused observed RED. Eight independently
reviewable checkpoints are required:

1. **Build foundations:** runtime schema dependencies, safe `source_root`, artifact
   containment, `ArtifactBuildOptions`, artifact config, expected-contract typed
   model/loader/comparator, packaging configuration, synthetic-fixture candidate
   bootstrap boundary, and typed errors; no official baseline content.
2. **Manifest and hashing:** strict schema/model/load/verify, canonical value/table/
   semantic-report/manifest hashes, operational timestamp cross-checks, format checking,
   mutation and path attacks.
3. **Table specs and serializers:** exact Arrow/DuckDB schemas, wide projections,
   canonical model round trips, Decimal/date/time behavior, fixed Parquet settings.
4. **Bronze streaming:** all three Bronze tables, bounded batches, exact row/cell/
   column reconstruction, source audit report, and failed-stage isolation.
5. **Silver and quality:** domestic/overseas wide records, bounded item-group fund
   collapse, attribute relation, two quarantines, D-021 injection/schema/joins, and no
   new metric/family/eligibility behavior.
6. **Exact links:** raw identifier rule v1.0.0, one-to-one conflict rejection, 47-pair
   TSV hash, 371 locators, no trimming/name/fuzzy/family links.
7. **DuckDB, reports, publication, CLI:** self-contained tables, read-only rejection,
   bounded OS-temp equality verification, physical inventory/checksums, guarded
   clean/rollback/tombstone failures, safe exit/output.
8. **Official reproduction and Phase 1 gate:** two different-time logical builds, one
   generation-integrity verification per build, bounded-memory evidence, all
   counts/hashes, independent candidate review, creation/commit of the official expected
   contract and wheel-byte identity test, all mandatory repository/source gates,
   independent whole-branch review, status evidence, and clean tree.

An official acceptance test may reuse a session-scoped artifact build, but no production
behavior is introduced only through an acceptance test that is already green.

## 15. Required test matrix

At minimum, tests prove:

- strict manifest/config/schema versions, extra-field rejection, explicit format
  checking, exact nine-input namespace/path inventory, safe paths, deep immutability,
  and all-or-nothing verification;
- fixture builds started from two different current working directories resolve every
  relative input/output/config path against the same explicit repository root and
  produce the same canonical input identities; absolute spellings produce those same
  identities, while an out-of-root config/input is rejected;
- source/config/version/hash changes alter logical identity while timestamp, output
  directory, and compression bytes do not;
- schema hashes do not change when only Parquet/output paths change and do change for
  table name, grain, ordered column/type/nullability, unique-key, or sort-key changes;
- manifest verification independently detects physical-file, Parquet schema/table
  logical, report logical, and overall manifest logical tampering;
- table logical hashes use the exact three-key header; an independent implementation
  reproduces the bytes and proves output-path/layer invariance;
- operational verification rejects manifest/Bronze/quality typed/quality-JSON timestamp
  mismatches although the common timestamp is excluded from logical projections;
- report logical identity uses closed semantic report IDs, not output paths;
- the separately tracked expected contract detects any source/table/report/overall
  logical baseline drift without consulting an operational timestamp or physical hash;
- initial candidate bootstrap performs full transform/verification without publication
  or write-back, refuses an existing expected file/resource, and is unavailable after
  the reviewed baseline is created;
- every table uses exact schema, type, column order, count, unique/sort key, and model
  round trip;
- each of the bond, domestic-listed, overseas-listed, and fund-item wide tables derives
  its complete ordered columns independently from the exact model declaration and
  asserts the frozen sequence; synthetic field insertion/removal/reorder fails instead
  of regenerating a table spec or expected baseline;
- every fund-item wide value and quality column equals its `FundItemValue`
  representative value/status, while all equivalent locators remain recoverable from
  `record_json` and never multiply the item-grain row;
- all-null columns retain declared physical type;
- Decimal values never round and source-local timestamps gain no invented timezone;
- Bronze reconstructs every D-017 row/cell and retains both malformed rows;
- deliberately unsorted official bond/domestic/overseas IDs and the global quality
  relation are externally sorted under the fixed one-thread/1-GiB/private-temp staging
  settings without table-sized Python materialization;
- public-fund live groups remain bounded to one complete item and fixed writer batches;
- canonical/reverse/interleaved fund input produces identical logical output;
- D-021 uses one UTC `Z` timestamp, rejects pre-timestamped/naive/non-UTC issues, and
  removes the operational field only from the logical projection;
- quarantined issue payload hashes and locators join exactly to Bronze;
- 47 raw pairs, full pair hash, one-to-one behavior, and synthetic duplicate/conflict
  rejection; all 371 evidence rows bidirectionally match one Bronze cell and their
  parent NormalizedValue/FundItemValue role, field, raw value, order, and ordinal;
- link confidence uses the shared `DECIMAL(38,18)` type and exact value `1.0` without a
  field-specific Decimal storage exception;
- DuckDB has only the eleven Task 5 tables, no external paths, exact counts, no WAL,
  and the public reader rejects persistent artifact mutation plus external ATTACH/COPY
  with external access disabled; TEMP session state is explicitly outside the contract;
- stage, validation, first-rename, and second-rename failures preserve or restore the
  old recognized artifact set;
- post-publication cleanup atomically tombstones the old verified backup before recursive
  deletion; partial cleanup retains the new verified target and resumes only that exact
  marked tombstone on the next run;
- injected backup-to-tombstone rename failure preserves the complete verified backup,
  while injected post-rename deletion failure makes no verified-backup claim;
- independent tombstone-marker and obsolete-backup-marker unlink faults produce only
  the closed marker-only states and next-run recovery reaches no remnant;
- verification equality uses one thread, 1-GiB memory, a mode-0700 marker-owned OS temp
  directory, and no artifact-root/parent writes or caller SQL; verification succeeds
  when the artifact root and parent are read-only;
- staging spill/close/removal failures never alter the published target or delete an
  unrecognized path;
- no-clean refuses existing targets and clean refuses symlink/unrecognized targets;
- exact recursive inventory rejects an extra file/directory, symlink, socket/special,
  hardlink alias, canonical duplicate, or WAL; clean refusal leaves every target byte
  unchanged;
- runtime build artifacts are Git-ignored and the expected logical contract is stable;
- built-wheel and editable resource loaders expose byte-identical artifact/quality
  schemas without a checkout-working-directory dependency;
- CLI output/exit codes are deterministic and safe.

## 16. Hard stops

Stop rather than updating baselines or guessing when:

- any official checksum, header, row count, 6,401,851 cell count, or 207-column count
  differs;
- the direct logical-input inventory is not the exact nine ordered namespace/path
  entries, a packaged schema/expected-contract resource differs from its root source,
  or evaluation cannot load the expected contract;
- Silver counts differ from 42,394 / 1,733 / 5,646 / 11,138 / 95,618;
- the two known malformed rows are absent from Bronze or present in normal Silver;
- fund grouping requires more than the complete item group or changes Task 4 collapse
  semantics;
- any Decimal cannot be stored exactly in the frozen type;
- an issue cannot validate as canonical D-021 JSON or cannot join to Bronze;
- raw and trimmed exact-link pair sets differ, exact links are not one-to-one, pair
  count/hash differs, or locator count differs from 371;
- implementation would create metric, family, eligibility, fuzzy, state, search, or
  evidence behavior deferred by D-023;
- DuckDB contains a staging/external path or accepts a write through the read-only API;
- any DuckDB table differs from verified Parquet despite matching schema/count, or any
  Parquet/report/overall logical hash differs from its declaration or expected contract;
- a prior artifact target is unrecognized, unsafe, or cannot be restored after a
  publication failure;
- an artifact root has anything other than `manifest.json`, the declared fourteen
  regular files, and the exact required parent directories, or any entry is a link or
  special file;
- an orphan stage/backup lacks its exact marker/manifest identity, a cleanup tombstone
  lacks its exact marker/path identity, or cleanup would resolve a broad/protected path;
- two builds disagree logically after only operational fields are removed;
- an unexplained Task 1-4 or source-audit regression appears.

The observed 6,032 row-issue count alone is not a frozen stop condition. Any change is
recorded and investigated against rule-specific behavior before acceptance.

## 17. Completion evidence

The completion report records:

- every focused RED and why it failed;
- checkpoint commits and independent review results;
- table schemas/counts/logical hashes and link/evidence evidence;
- physical manifest/file hashes for the reviewed official build;
- bounded-memory measurements and exact build duration;
- two-build logical reproduction and per-generation physical verification results;
- read-only database and guarded rollback results;
- all required format, lint, type, test, source-audit, handoff, schema-catalog,
  pre-commit, diff, source-read-only, ignored-artifact, and clean-tree results;
- unresolved official questions and the exact Phase 2 next task.
