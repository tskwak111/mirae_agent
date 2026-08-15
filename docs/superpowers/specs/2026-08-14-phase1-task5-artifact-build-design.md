# Phase 1 Task 5 Artifact Build Design

**Status:** Approved for implementation planning on 2026-08-14

**Scope:** Reproducible Bronze/Silver/Gold Parquet, self-contained DuckDB, data-artifact
manifest, reports, exact domestic ETF/public-fund links, and guarded publication

**Governing decisions:** D-014, D-017, D-021, D-022, D-023, D-024, D-025

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

Checkpoint 2 adds the closed internal-assembly code
`VERIFICATION_INCOMPLETE="verification_incomplete"`. It is emitted only when a private
verification kernel port is missing, before any filesystem work; it never downgrades an
artifact/input failure or becomes a public option to skip a verification stage.

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

CP4 `staging.py` owns every production staging primitive. `ArtifactBuildSession` is a
managed context and the sole production implementation of both
`OwnedStageArtifactOwner` and `OwnedStageDatabaseOwner`; neither a caller path nor a
free-standing leaf/store constructor can create a stage capability. Its state machine
is exactly `LIVE -> CLOSING -> CLOSED`. Only `LIVE` may claim leaves, open a bounded
store, register staged facts, or ingest rows. Context exit first enters `CLOSING`,
closes every registered writer/store, then either removes only the exact recognized
stage on abort or transfers the held parent/stage/parquet descriptors, sidecar-marker
identity, owner registrations, held-nine-input carrier close responsibility, and
advisory lock exactly once into a direct-
construction-disabled `OwnedCandidateStage`. A successful transfer makes the session
`CLOSED` and leaves no second owner. An ambiguous abort retains the recognized bytes
and marker for recovery, never broadens deletion, closes child descriptors, and holds
the advisory lock until the managed exit has completed its last safe action; the lock
is then released exactly once. A close, abort, or transfer fault cannot return the
session to `LIVE`.

The build's direct logical inputs cross checkpoints only through one immutable,
direct-construction-disabled held carrier. A free tuple of caller-created
`ArtifactInput` values is never an issuance input:

```python
@dataclass(frozen=True, init=False)
class ResolvedBuildInputBundle:
    @classmethod
    def from_settings(cls, settings: Settings) -> "ResolvedBuildInputBundle": ...


class HeldVerifiedBuildInputs(AbstractContextManager["HeldVerifiedBuildInputs"]):
    def issue_identity_seal(self) -> object: ...
    def close(self) -> None: ...


def verify_build_inputs(
    settings: Settings,
    resolved: ResolvedBuildInputBundle,
) -> AbstractContextManager[HeldVerifiedBuildInputs]: ...


class BuildInputIdentityView(Protocol):
    @property
    def logical_inputs(self) -> tuple[ArtifactInput, ...]: ...
    @property
    def source_manifest_sha256(self) -> str: ...
    @property
    def schema_catalog_sha256(self) -> str: ...
    def assert_unchanged(self) -> None: ...
    def take_manifest_identity_seal(self) -> object: ...


@dataclass(frozen=True, init=False)
class BuildInputIdentity:
    logical_inputs: tuple[ArtifactInput, ...]
    source_manifest_sha256: str
    schema_catalog_sha256: str

    @classmethod
    def from_verified(cls, *, seal: object) -> "BuildInputIdentity": ...

    def open_verified_input(
        self, *, kind: ArtifactInputKind
    ) -> AbstractContextManager[BinaryIO]: ...
    def assert_unchanged(self) -> None: ...
    def close(self) -> None: ...
```

The tuple is exactly nine strict `ArtifactInput` values in this closed order:
`source_root/input_manifest.json` source manifest,
`source_root/schema_catalog.json` source schema catalog,
`repository/config/artifact_build.yaml`, `repository/config/datasets.yaml`,
`repository/config/quality_rules.yaml`, `repository/config/rating_scale.yaml`,
`repository/config/state_rules.yaml`,
`repository/schemas/artifact_manifest.schema.json`, and
`repository/schemas/quality_issue.schema.json`, each with its exact kind, size, and
lowercase SHA-256. The two named hashes must equal the first and second tuple entries;
they cannot be caller overrides. Copies, subclasses, reordered/equal-looking tuples,
wrong namespace/path/kind, duplicate/missing/extra entries, boolean sizes, and stale
hashes fail before session creation.

`ResolvedBuildInputBundle.from_settings(settings)` is the only resolver entry used by
the build. It calls CP1's closed resolver internally, retains the exact nine member
objects plus one per-instance private owner capability, rejects copy/deepcopy/pickle,
and exposes neither the owner nor a mutable/reconstructable member container. There is
no module-global issuance registry. A copied, equal, subclassed, `object.__new__`-
created, foreign-bundle, or replaced `ResolvedArtifactInput` member cannot satisfy the
bundle's exact owner/member-object checks.

`verify_build_inputs(settings, resolved)` accepts only an exact live
`ResolvedBuildInputBundle` and the trusted frozen `Settings`. It independently derives
the two namespace roots from `settings.repository_root` and `settings.source_root`,
recomputes all nine closed namespace/relative-path/kind/absolute-path declarations,
and requires those facts and exact member identities to match the bundle; it never
trusts a member's stored `absolute_path` or a caller root. It opens every recomputed namespace parent and basename
descriptor-relatively with `O_RDONLY | O_CLOEXEC | O_NOFOLLOW`, requires regular
single-link leaves, computes size/SHA from each held descriptor, and retains the parent/
name/file identities plus root/parent mutation facts in exact order. Before issuing,
it revalidates every root/parent/name/
descriptor and recomputes every held-stream size/SHA. The direct-init-disabled result's
one-use `issue_identity_seal()` atomically transfers those nine held generations into
an opaque seal and invalidates the result; context exit closes all untransferred
descriptors exactly once.

`BuildInputIdentity.from_verified(seal=...)` is the only issuer and consumes that exact
seal once. It derives all `ArtifactInput` fields and the two named hashes
from the held observations and takes sole descriptor custody. The seal and carrier are
instance-owned capabilities; no module-global identity registry exists. It accepts no `logical_inputs`,
path, hash, descriptor, or caller token argument. `open_verified_input` yields a
rewound duplicate of the same retained file generation and revalidates before/after;
`assert_unchanged` rechecks all nine parent/name/descriptor identities and held-stream
size/SHA plus namespace-root and parent mutation facts. A basename replacement, an
A-to-B-to-A basename swap during parsing, same-inode/same-size byte mutation, stale but
well-formed supplied SHA, copied/equal tuple, copied seal/carrier, subclass,
`object.__new__`, or token forgery fails before session/manifest use. The carrier closes
all retained descriptors exactly once only after candidate discard or CP8 publication
custody completes.

`ArtifactBuildSession.initialize(..., input_identity=...)` first revalidates and then
retains that exact carrier;
`BronzeBuildResult`, later Silver/link results, `CandidateArtifactSet`, and the sole
manifest builder pass the same object unchanged. The build-only
`ArtifactManifest.from_build(..., input_identity=...)` stores that object identity in a
private, frozen, nonserialized `_build_input_identity` slot and exposes only
`require_build_input_identity(value) -> None`; JSON `load`/`model_validate` cannot mint
that producer authorization. At concrete carrier issuance `input_identity.py` asks a
manifest-owned module-private issuer to register the exact carrier object and frozen
facts; `take_manifest_identity_seal()` yields that one-use opaque seal.
`ArtifactManifest.from_build` validates/consumes the seal against the same object before
retention, so a structural protocol fake cannot mint build authorization without a
manifest-to-input-identity import. The manifest serializes only the carrier's exact
`logical_inputs` as `source_inputs`, and its source-manifest/catalog hashes in Bronze/
complete report semantics come only from the carrier. Manifest construction requires
`manifest.source_inputs == input_identity.logical_inputs` with exact entry types/order/
values and rechecks the two hash bindings; the candidate requires the same carrier
object from session, results, and manifest. No checkpoint may rebuild the tuple from
paths or separately supplied hashes.

The import direction is one-way: `manifest.py` owns `ArtifactInput` plus the narrow
`BuildInputIdentityView` protocol used by `ArtifactManifest.from_build`, and never
imports `input_identity.py`; `input_identity.py` imports that protocol/model and CP1's
resolver types. The concrete carrier structurally implements the view. This prevents a
manifest/input-identity cycle while preserving exact object-identity admission.

Path-owning parsers cannot reopen these nine files. `config.py` owns
`ArtifactBuildConfig.from_held_stream(stream: BinaryIO, *, versions: VersionBundle)
-> ArtifactBuildConfig` and
`validate_build_registry_versions_from_held_streams(*, datasets: BinaryIO, quality:
BinaryIO, rating: BinaryIO, state: BinaryIO, versions: VersionBundle) -> None`;
`source_manifest.py` owns `SourceFileManifest.from_held_streams(*, manifest_stream:
BinaryIO, schema_catalog_stream: BinaryIO) -> SourceFileManifest`.
Each accepts only a seekable binary stream yielded by
`BuildInputIdentity.open_verified_input`, rewinds and bounded-reads that exact stream,
strictly parses it without closing it, and returns before the surrounding identity
context performs its after-parse digest/root/parent/name revalidation. These entries
accept no `Path`, root, raw descriptor, fallback loader, or caller bytes. Existing path-
based loaders remain compatibility entries for earlier tasks but are absent from Task
5 production assembly. Build config, four registry headers, source manifest, and
schema catalog are therefore parsed from retained generations only; an A-to-B-to-A
basename swap changes the held parent mutation facts and fails before parsed state can
enter the session even if the original leaf inode has been restored.

CP5 extends the owning registry parser, not the input carrier:
`RatingRegistry.from_held_stream(stream: BinaryIO) -> RatingRegistry` bounded-reads,
strict-decodes, and applies the exact same duplicate-key/shape/semantic validation as
`from_yaml` without accepting a path and without closing the stream. Before creating a
Silver emitter, the builder calls only
`input_identity.open_verified_input(kind=ArtifactInputKind.RATING_SCALE_REGISTRY)` on
the retained `BuildInputIdentity`, calls this stream parser inside that context, and
exits through the carrier's after-parse root/parent/name/digest revalidation. It never
calls `RatingRegistry.from_yaml` in Task 5, reopens `config/rating_scale.yaml`, or
retains a stream beyond its context. Held and compatibility-path parsing of identical
bytes must produce equal registries and identical errors.

`CandidateArtifactSet` later retains one exact instance-owned opaque
`CandidateStageCustody` issued by `OwnedCandidateStage`; there is no candidate/stage
module-global registry and the candidate contains no raw descriptor, path, basename,
or independently usable stage object. CP8's `ExpectedAcceptedPublicationStage`
receives that custody only through the atomic transfer below.
The candidate exposes only `open_verification_root()` and package-private
`transfer_expected_accepted_custody(*, expected_acceptance_seal, receiver) -> None`;
both delegate through the exact retained custody instance without exposing or reading
its private state. The latter is the only bridge to staging's one-use transfer
primitive, and only CP8 publication may call it.
CP4 custody supplies only liveness, managed verification-root access, exact staged
discard, and close. CP8 alone wraps that custody in the production transition
capability whose descriptor-relative operations perform active publication and
pre-commit rollback. They never reconstruct a
stage or parent from a returned `Path`, basename, manifest field, or verification
result. Candidate cleanup and publication close the transferred descriptors and lock
exactly once on every exit. A later process has no such live capability: next-run
orphan recovery separately reacquires the advisory lock and applies the strict marker/
basename/inode recognition rules above; it cannot pretend to resume the old candidate.

The held stage-custody capability has no public constructor, path property, rename, or
rollback operation:

```python
@dataclass(frozen=True, init=False)
class OwnedCandidateStage:
    def assert_live(self) -> None: ...
    def issue_candidate_custody(self) -> "CandidateStageCustody": ...
    def close(self) -> None: ...


@dataclass(frozen=True, init=False)
class CandidateStageCustody:
    def open_verification_root(
        self,
    ) -> AbstractContextManager[ManagedArtifactVerificationRoot]: ...
    def transfer_expected_accepted(
        self,
        *,
        expected_acceptance_seal: object,
        receiver: "ExpectedAcceptedCustodyReceiver",
    ) -> None: ...
    def discard_if_exact(self) -> None: ...
    def close(self) -> None: ...


class ExpectedAcceptedCustodyReceiver(Protocol):
    def accept_transferred_custody(
        self, custody: "TransferredCandidateCustody"
    ) -> None: ...
```

CP2 `manifest.py` owns the opaque adoption boundary and concrete managed adapter:

```python
@dataclass(frozen=True, init=False)
class HeldArtifactRootAdoption:
    pass


def adopt_held_artifact_root(
    adoption: HeldArtifactRootAdoption,
) -> AbstractContextManager[ManagedArtifactVerificationRoot]: ...
```

`open_verification_root` duplicates only the already-held parent and stage directory
descriptors, revalidates the same parent/name/root generation, and asks CP2's
module-private issuer for a one-use `HeldArtifactRootAdoption`. It immediately passes
that opaque value to `adopt_held_artifact_root`; no caller sees it. The CP2 factory
requires exact issuance object/token identity, consumes it once, takes ownership of the
duplicates, revalidates parent/name/root before and after adoption, and creates the same
`_HeldArtifactTree` chain used by `verify_declared_inventory`. Adoption or adapter exit
closes every transferred descriptor exactly once; a copied/forged/reused seal,
different descriptor generation, close-then-reuse, basename/inode swap, or failure
during adoption is typed and fail-closed. Neither public API nor the kernel/caller can
receive a descriptor integer, basename, private field, or reconstructed `Path`.

`OwnedCandidateStage.issue_candidate_custody()` is one-use: it transfers its live
ownership slots into one `CandidateStageCustody`, invalidates the bare stage object,
and returns no parallel stage reference. The candidate retains that exact opaque
instance. Copy/deepcopy/pickle/subclass/`object.__new__` are rejected by the custody's
per-instance owner/slot identity; no global registration lookup participates.

`CandidateStageCustody.discard_if_exact` removes only the exact still-staged
recognized generation and is unavailable after a CP8 production transition has
consumed the custody or after close. Copy/forge,
changed marker/inode/parent, closed capability, or a foreign adapter fails before
inventory/open/unlink. CP4 implements only liveness, verification custody, exact
discard, and close. It has no production target/backup/tombstone or publication
transition primitive.

CP7 `publication.py` defines a private `PublicationTransitionPort` for its
authorization-independent state-machine tests; only `tests/helpers/artifact_filesystem.py`
implements the synthetic port in CP7. CP8 alone defines the production transition
capability inside `ExpectedAcceptedPublicationStage` after expected acceptance. That
CP8 capability receives the exact live custody only through the candidate's retained
instance-owned custody and typed atomic acceptance and owns
stage-to-target, optional pre-commit target-to-stage rollback, and commit/close
transitions. `staging.py` never imports `publication.py`; `publication.py` imports only
the narrow `CandidateStageCustody`/`ExpectedAcceptedCustodyReceiver` capability
contracts, never `OwnedCandidateStage` or a custody private field.

```python
class PublicationTransitionPort(Protocol):
    def assert_live(self) -> None: ...
    def rename_stage_to_target(self) -> None: ...
    def rollback_target_to_stage(self) -> None: ...
    def commit_after_stage_marker_removal(self) -> None: ...
    def close(self) -> None: ...
```

The port takes and returns no path, basename, descriptor, manifest, result, or separate
stage value. CP7's state machine receives it only through its sealed synthetic test
authorization. CP8's expected-accepted capability is the only production object that
may implement it, and each transition is one-use and state-checked.

Expected acceptance and custody transfer are bound to that same adopted descriptor
generation. After the expected route's final rescan, the kernel marks the still-live
`ManagedArtifactVerificationRoot` with one CP2-owned opaque expected-acceptance seal;
the candidate route never can. CP8's `authorize_candidate_for_publication` takes the
opaque seal from that exact root, then exits `candidate.open_verification_root()` so
all adopted duplicate descriptors close before any custody move. It then creates one
direct-init-disabled `ExpectedAcceptedPublicationStage` receiver and calls
`candidate.transfer_expected_accepted_custody(...)`, the sole no-private-field
bridge to its exact retained `CandidateStageCustody.transfer_expected_accepted(...)`
method. That staging-owned instance method validates the unconsumed acceptance seal
against the stage/adoption generation and the exact typed receiver, then creates one
opaque `TransferredCandidateCustody`, calls the receiver's non-fallible
`accept_transferred_custody(...)` slot operation, and atomically clears/invalidates the
source custody. The accepted instance is the sole owner of the original parent/stage/
parquet descriptors, leaf identities, advisory lock, and held-input close
responsibility; neither side exchanges raw descriptors or a private field. No duplicate
owner or rollback-to-live path exists. On any
preflight failure ownership remains wholly with
the candidate custody; after the non-fallible move, every old candidate/custody method
fails and only the publication capability can rename,
rollback, commit, or close. Production import/call-site checks permit this transfer only
from `publication.py` after expected success; synthetic CP7 ports never receive real
custody.

Taking the seal transfers its one-use ownership out of the managed root; normal root
exit invalidates only an untaken seal. The detached opaque seal contains no fd/path and
survives only until this exact transfer call. If receiver creation/preflight fails,
authorization explicitly invalidates it while the original stage remains sole owner.

The sole cross-module transfer API is the instance method owned by `staging.py`:

```python
class CandidateStageCustody:
    def transfer_expected_accepted(
        self,
        *,
        expected_acceptance_seal: object,
        receiver: ExpectedAcceptedCustodyReceiver,
    ) -> None: ...


class ExpectedAcceptedCustodyReceiver(Protocol):
    def accept_transferred_custody(
        self,
        custody: TransferredCandidateCustody,
    ) -> None: ...
```

`TransferredCandidateCustody` is direct-init-disabled, noncopyable, nonserializable,
and exposes no raw descriptor/path/basename/token or caller constructor. It is created
inside the source custody's preflight and can be retained only by one typed receiver;
its exact instance supplies the receiver's internal descriptor-relative operations
without disclosing their storage. Receiver acceptance performs no I/O and cannot raise
after preflight; it swaps the one ownership slot, after which source invalidation is the
same atomic state transition. A receiver that is copied, already filled, foreign,
structurally similar, or raises during its preflight is rejected before the source slot
moves.

The exact `CandidateArtifactSet` bridge is the only production caller of the retained
custody method, and CP8 publication is the only production caller of that bridge. The
candidate stores the custody object itself and delegates without a registry lookup;
`ExpectedAcceptedPublicationStage` implements the typed receiver directly and retains
the transferred instance. The method validates exact source-custody identity,
receiver type/state, seal object identity, and generation before its non-fallible slot
move. It returns no descriptor, path, bundle, token, or replacement custody object.
CP4 freezes only this raising method/receiver protocol boundary and retains custody;
CP7 can retain/open/clean an unpublished candidate but has no expected seal or transfer
success. CP8 first implements the successful instance transfer and production receiver,
driven by the real-descriptor selector below. No module-global candidate, stage,
receiver, token, or custody registry exists.

`ExternalOrderStore` disables direct construction. Its only production entry is
`ArtifactBuildSession.open_external_order_store(config=...)`, which accepts the live
owner and strict `ArtifactBuildConfig` implicitly through the session, fixes
`threads=1`, `memory_limit="1GiB"`, `preserve_insertion_order=false`, and a private
owner-created spill workspace, and returns a managed context. It accepts no stage,
database, spill, or temp path and no caller-selected production limit. A module-private
`_open_external_order_store_for_test(*, owner, config, limits)` may lower positive
batch/memory limits only for hermetic tests; production assembly cannot import or call
that factory. All stores are registered with the exact session, close before cleanup,
and are absent before candidate-stage transfer.

CP5 extends that CP4-owned capability rather than creating another database wrapper.
The closed `ExternalOrderRelation` inventory becomes exactly
`BRONZE_SOURCE_ROW`, `SILVER_BOND_INSTRUMENT`,
`SILVER_DOMESTIC_LISTED_PRODUCT`, `SILVER_OVERSEAS_LISTED_PRODUCT`,
`PUBLIC_FUND_SOURCE_ROW`, `SILVER_QUALITY_ISSUE`,
`EXACT_LINK_LEFT_CANDIDATE`, `EXACT_LINK_RIGHT_CANDIDATE`, and
`EXACT_LINK_EVIDENCE`. The last three reserve the same typed boundary for CP6; CP5
does not populate them. Each name maps internally to one frozen key schema. Text keys
are exact strings; numeric keys are exact nonboolean integers stored and ordered as
numeric DuckDB columns, never decimal-padded/string-coerced keys. The mixed fund key is
exactly `(item_key: str, source_row_number: int)` and the quality key is exactly
`(source_table_order: int, source_file: str, source_sheet: str,
source_row_number: int, source_column_number: int, rule_id: str, issue_id: str)`.

```python
@dataclass(frozen=True)
class ExternalOrderRow:
    key: tuple[str | int, ...]
    payload_json: str


class ExternalOrderJoinOperation(StrEnum):
    QUALITY_TO_BRONZE = "quality_to_bronze"
    EXACT_EVIDENCE_TO_BRONZE = "exact_evidence_to_bronze"
    LINKED_DOMESTIC_RECORD_JSON = "linked_domestic_record_json"
    LINKED_FUND_RECORD_JSON = "linked_fund_record_json"


@dataclass(frozen=True)
class ExternalOrderJoinRow:
    key: tuple[str | int, ...]
    values: tuple[str | int, ...]


class ExternalOrderStore:
    def insert_batch(
        self,
        *,
        relation: ExternalOrderRelation,
        rows: Iterable[ExternalOrderRow],
    ) -> None: ...

    def iter_ordered_batches(
        self, *, relation: ExternalOrderRelation
    ) -> Iterator[tuple[ExternalOrderRow, ...]]: ...

    def iter_join_batches(
        self,
        *,
        operation: ExternalOrderJoinOperation,
        tables: StagedParquetSet,
        exact_ids: tuple[str, ...] = (),
    ) -> Iterator[tuple[ExternalOrderJoinRow, ...]]: ...
```

Every entry validates exact relation/operation runtime type, key arity and scalar type,
strict canonical payload JSON, exact same-owner live `StagedParquetSet` when a join is
requested, and batches of at most 65,536. Export uses the frozen explicit key columns
followed by `payload_json` only as a deterministic final tie breaker; duplicates that
violate a relation's declared unique key fail. `iter_join_batches` has only the four
static allowlisted statements above and is called in production only by the closed
bounded verifier. The DuckDB connection, SQL, table spelling, cursor, registration
name, and file/spill identity remain private; there is no `connection`, `execute`,
generic join, caller column, caller SQL, or raw-handle method.

The import/ownership direction is frozen. `manifest.py` owns `ArtifactInput`,
`BuildInputIdentityView`, held-root adoption, and the managed root; it never imports
input identity, staging, or publication. `input_identity.py` imports the manifest view/
model plus CP1 resolver types and owns held-nine verification plus
`BuildInputIdentity`. `staging.py` may import both narrow capabilities plus CP3
protocols and
owns the build advisory lock, build-stage/working markers, held descriptor custody,
Parquet/database leaves, scratch stores, exact abort/discard, candidate custody, and the
sole one-use custody-transfer primitive; it never owns a publication transition.
`bronze.py` consumes staging and input identity; `builder.py` owns the
`CandidateArtifactSet` bridge, which retains the exact instance-owned custody, and
orchestrates without defining filesystem primitives.
`publication.py` defines only a narrow candidate-method protocol and never imports
builder; builder may import publication in CP8. `publication.py` may import only
staging's narrow custody/typed-receiver contracts; it never imports
`OwnedCandidateStage`, and `staging.py` never imports publication.
Publication alone owns target/backup/tombstone markers, target recognition, authorization-bound
transition objects, rename/rollback/commit, and recovery. Manifest/kernel code imports
only `ManagedArtifactVerificationRoot`, never staging/publication implementations.

### 6.2 Bronze and non-fund Silver

The source catalog is emitted in catalog order. Each workbook is streamed once in
manifest order. Every `SourceRow` is written to bounded Bronze row/cell batches before
normalization. Because Bronze sort keys begin with the frozen manifest
`source_table_order`, these batches are already in final order.

`VerifiedSourceFile` carries the manifest's exact nonnegative `size_bytes` in addition
to SHA-256. `iter_xlsx_rows` opens the verified workbook parent as a held no-follow
directory descriptor and opens the exact basename relative to it with
`O_RDONLY | O_NOFOLLOW`. It requires a regular single-link file and exact parent/name/
descriptor identity. Size and SHA-256 are computed from the same held binary stream
that is rewound and passed to `ZipFile`; the parser never reopens
`verified_absolute_path`. Parent/name/descriptor identity is revalidated before ZIP
metadata, before every row yield, after the final worksheet row, and on generator
close. After parsing, that same stream is rewound and independently rechecked for exact
size/SHA before either descriptor closes. A replacement before open, during iteration,
or after the last yielded row, and an in-place same-inode mutation all fail with a
typed source-contract error. No row from a changed generation may be reported as
success, and every descriptor is released exactly once on early consumer failure.

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

### 6.4 Silver finalization, quality relations, and result ownership

`quality_persistence.py` imports the one authoritative
`finproof.domain.quality.DataQualityIssue`; no second `QualityIssue`, alias model, DTO,
persisted-row wrapper, or shape-compatible substitute exists. Its exact persistence
adapter is
`persist_quality_issue(issue: DataQualityIssue, *, persistence_timestamp: datetime)
-> DataQualityIssue`: it reconstructs and returns the authoritative model with the one
accepted build timestamp. `reports.py` owns the immutable observation contracts
consumed by its report model, while `quality_persistence.py` owns the stage-backed
implementation and imports staging only one way:

```python
@dataclass(frozen=True)
class QualityJoinObservations:
    total_issues: int
    distinct_issue_ids: int
    matched_bronze_rows: int
    matched_bronze_cells: int
    distinct_affected_source_rows: int
    quarantined_issue_count: int
    quarantined_source_row_count: int
    persistence_timestamp: datetime
    quality_table_logical_hash: str


class ExactLinkedSide(StrEnum):
    DOMESTIC = "domestic"
    FUND = "fund"


@dataclass(frozen=True)
class LinkedRecordJson:
    product_id: str
    record_json: str


class BoundedRelationVerifier(Protocol):
    def verify_quality_to_bronze(
        self, *, tables: StagedParquetSet
    ) -> QualityJoinObservations: ...

    def verify_exact_evidence_to_bronze(
        self, *, tables: StagedParquetSet
    ) -> None: ...

    def iter_linked_record_json(
        self,
        *,
        tables: StagedParquetSet,
        side: ExactLinkedSide,
        exact_ids: tuple[str, ...],
    ) -> Iterator[tuple[LinkedRecordJson, ...]]: ...
```

All observation integers are exact nonboolean nonnegative values; issue IDs are unique,
`distinct_issue_ids == total_issues == matched_bronze_rows == matched_bronze_cells`,
affected/quarantined bounds hold, the timestamp is aware UTC and equals the owner-bound
set/Bronze/typed-quality/quality-JSON timestamp, and the hash is lowercase SHA-256 for
the reopened staged quality table's timestamp-neutral logical projection.
`StagedBoundedRelationVerifier` receives one live owner-managed `ExternalOrderStore`
and invokes only its closed join operations. Every method first revalidates the exact
set object, owner, timestamp, required ordered names and handle identities. It exposes
no connection, SQL, relation/table string, raw handle tuple, final inventory, path, or
materialized result. The exact-evidence and linked-record methods are frozen now for
CP6 compatibility but cannot succeed until CP6 extends the same set with its two Gold
tables.

The quality report producer is exact and is not a generic aggregation entry:

```python
class QualitySummaryReport:
    @classmethod
    def from_verified_quality(
        cls,
        *,
        issues: Iterable[DataQualityIssue],
        join_observations: QualityJoinObservations,
        excluded_silver_records: tuple[ExcludedSilverCount, ...],
    ) -> "QualitySummaryReport": ...
```

It single-pass strict-validates each exact persisted `DataQualityIssue`, derives all
closed lexical groups, independently recomputes the timestamp-neutral logical hash,
and requires complete equality with the immutable join observations. It accepts no
mapping/DTO, pre-aggregated caller counts, timestamp override, path, or caller hash.

`SilverArtifactEmitter` is direct-construction-disabled and issued for one exact live
`ArtifactBuildSession`, config, version bundle, held-stream-parsed `RatingRegistry`, and
session timestamp. Its exact interface is:

```python
class SilverArtifactEmitter:
    @classmethod
    def for_session(
        cls,
        *,
        session: ArtifactBuildSession,
        config: ArtifactBuildConfig,
        versions: VersionBundle,
        rating_registry: RatingRegistry,
    ) -> "SilverArtifactEmitter": ...

    def consume(self, row: SourceRow) -> None: ...

    def finalize(
        self, *, bronze_result: BronzeBuildResult
    ) -> "SilverBuildResult": ...
```

The call sequence is frozen: (1) builder opens the rating input through the exact
`BuildInputIdentity` and parses it with `RatingRegistry.from_held_stream`; (2) builder
creates the emitter; (3) `session.ingest_bronze(consumer=emitter)` returns one exact
`BronzeBuildResult`; (4) builder calls `emitter.finalize(bronze_result=that_result)`
once; (5) finalization exact-type/object-validates the Bronze result, same input
carrier, same owner, three-table set, Bronze observations, and timestamp before closing
source admission; (6) it drains fund groups, externally orders/exports non-fund and
quality relations, writes/reopens/verifies the six new Silver tables, and atomically
extends the same set in frozen order from three to nine tables; (7) it requires the
nine-table set, runs the bounded quality relation, constructs Silver observations and
the quality report, and only then issues the result. Any failure emits no result and
leaves cleanup with the managed session; finalize is one-use.

```python
@dataclass(frozen=True)
class NamedObservedCount:
    name: str
    observed: int


@dataclass(frozen=True)
class SilverBuildInstrumentation:
    source_rows_consumed: int
    source_consume_counts: tuple[NamedObservedCount, ...]
    normalizer_call_counts: tuple[NamedObservedCount, ...]
    staged_relation_rows: tuple[NamedObservedCount, ...]
    max_live_fund_group_rows: int
    max_writer_batch_rows: int
    max_relation_batch_rows: int


@dataclass(frozen=True, init=False, slots=True)
class SilverBuildResult:
    input_identity: BuildInputIdentity
    staged_tables: StagedParquetSet
    observations: SilverSourceAuditObservations
    quality_join_observations: QualityJoinObservations
    quality_report: QualitySummaryReport
    instrumentation: SilverBuildInstrumentation

    @classmethod
    def _issue_from_finalizer(
        cls,
        *,
        bronze_result: BronzeBuildResult,
        staged_tables: StagedParquetSet,
        observations: SilverSourceAuditObservations,
        quality_join_observations: QualityJoinObservations,
        quality_report: QualitySummaryReport,
        instrumentation: SilverBuildInstrumentation,
    ) -> "SilverBuildResult": ...
```

These contracts are deeply immutable and strict. `SilverBuildResult` can be issued only
by the successful finalizer through the module-private issuer; its issuer derives and
retains the exact `bronze_result.input_identity`, exact
extended set, exact predecessor-derived Silver observations, verified join facts,
factory-produced report, and bounded counters. Direct construction, copy/subclass,
`object.__new__`, equal-field substitution, foreign owner/set/input, incomplete/order-
changed set, timestamp mismatch, independently reconstructed observations/report, or
counter mismatch fails before issuance. CP6 consumes this exact result and extends its
set/observations; it never receives parallel fields.

Every `NamedObservedCount` has an exact nonempty closed name and exact nonboolean
nonnegative count. `source_consume_counts` and `normalizer_call_counts` contain exactly
the four source-table IDs in frozen source order. The former sum to
`source_rows_consumed` and both prove exactly one admission/normalizer decision per
source row. `staged_relation_rows` contains exactly
`SILVER_BOND_INSTRUMENT`, `SILVER_DOMESTIC_LISTED_PRODUCT`,
`SILVER_OVERSEAS_LISTED_PRODUCT`, `PUBLIC_FUND_SOURCE_ROW`, and
`SILVER_QUALITY_ISSUE` in that order. All three maximum counters are exact nonboolean
nonnegative values and do not exceed the configured closed production bounds.

The import graph is one-way: `rating.py` imports no artifact module; `staging.py`
imports no Silver/quality/report implementation; `reports.py` imports only domain and
closed model contracts; `quality_persistence.py` imports staging/parquet/report/domain
contracts but not `silver.py` or builder; `silver.py` imports Bronze, staging, quality,
report, rating, serialization, and authoritative normalizers; builder imports Silver
and orchestrates. No reverse import or runtime local import may hide a cycle.

### 6.5 Candidate finalization

Each Parquet writer is closed, then its exact CP4-owned stage leaf is reopened and
checked by CP3's common bounded checker against frozen schema, count, sort order,
uniqueness, and logical hash. Those verifications/handles enter only one owner-bound
`StagedParquetSet`, which remains live inside the marker-owned build session and feeds CP5/6
relations, reports, and DuckDB construction. Reports/database and then the manifest are
written from those verified observations. Once the complete declared 14-file tree
exists, CP7 opens CP2's distinct final `VerifiedPhysicalInventory` and independently
reruns the same checker to create new manifest-owned `VerifiedParquetTable` handles;
stage handles are never promoted. Only after every final file hash, logical check, and
manifest invariant passes may the session transfer its exact held stage/lock capability
to `CandidateArtifactSet`; publication never receives a stage path or a separate result.

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

The strict declaration order and complete field inventory are:

```text
SourceAuditReport
  report_id                     literal "source_audit"
  report_contract_version       literal "1.0.0"
  artifact_contract_version     literal "1.0.0"
  source_snapshot_date          literal date(2026, 7, 11)
  source_manifest_sha256        lowercase SHA-256
  schema_catalog_sha256         lowercase SHA-256
  source_tables                 tuple[SourceTableAudit, ...]  # exact four-table order
  silver_tables                 tuple[NamedExpectedObservedCount, ...]  # exact five-table order
  quarantine_source_rows        ExpectedObservedCount
  exact_links                   ExpectedObservedCount
  exact_link_evidence           ExpectedObservedCount
  exact_link_pair_sha256        ExpectedObservedSha256

SourceTableAudit
  source_table                  closed table literal
  expected_rows                 nonnegative integer
  observed_rows                 nonnegative integer
  expected_columns              nonnegative integer
  observed_columns              nonnegative integer
  expected_cells                nonnegative integer
  observed_cells                nonnegative integer

NamedExpectedObservedCount
  name                          closed Silver table literal
  expected                      nonnegative integer
  observed                      nonnegative integer

ExpectedObservedCount
  expected                      nonnegative integer
  observed                      nonnegative integer

ExpectedObservedSha256
  expected                      lowercase SHA-256
  observed                      lowercase SHA-256
```

The report is reached through three non-interchangeable strict frozen typestates, not a
phase tag on one permissive transport model:

```text
BronzeSourceAuditObservations
  source_snapshot_date          literal date(2026, 7, 11)
  source_manifest_sha256        lowercase SHA-256
  schema_catalog_sha256         lowercase SHA-256
  source_tables                 tuple[SourceTableAudit, ...]  # exact four-table order

SilverSourceAuditObservations
  source_snapshot_date          literal date(2026, 7, 11)
  source_manifest_sha256        lowercase SHA-256
  schema_catalog_sha256         lowercase SHA-256
  source_tables                 tuple[SourceTableAudit, ...]  # exact four-table order
  silver_tables                 tuple[NamedExpectedObservedCount, ...]  # exact five-table order
  quarantine_source_rows        ExpectedObservedCount

CompleteSourceAuditObservations
  source_snapshot_date          literal date(2026, 7, 11)
  source_manifest_sha256        lowercase SHA-256
  schema_catalog_sha256         lowercase SHA-256
  source_tables                 tuple[SourceTableAudit, ...]  # exact four-table order
  silver_tables                 tuple[NamedExpectedObservedCount, ...]  # exact five-table order
  quarantine_source_rows        ExpectedObservedCount
  exact_links                   ExpectedObservedCount
  exact_link_evidence           ExpectedObservedCount
  exact_link_pair_sha256        ExpectedObservedSha256
```

CP4 implements only `BronzeSourceAuditObservations.from_bronze(...)`, accepting the
exact carrier-bound manifest/catalog hashes and four ordered source-table observations.
It has no `with_silver`, later-phase class, or report-producer factory yet; every CP4
session/result consumer requires the exact Bronze runtime type and rejects a
structurally equal fake, subclass, copied/forged object, or injected suffix field.
CP5 first adds `BronzeSourceAuditObservations.with_silver(...)` and the distinct
`SilverSourceAuditObservations`; that type cannot accept or expose link fields. CP6
first adds `SilverSourceAuditObservations.with_links(...)`, the distinct
`CompleteSourceAuditObservations`, and the report producer. The Complete successor
preserves every earlier object/value/order and adds only the three exact-link fields.
Each implemented class rejects extra/missing/reordered fields, booleans as integers,
unequal expected/observed values, noncanonical hashes, and construction from the wrong
predecessor. The only build-producer factory, added in CP6, is
`SourceAuditReport.from_complete_observations(config=..., observations:
CompleteSourceAuditObservations)`. CP2's strict model parser remains available only to
reparse/verify an existing report payload; parsing bytes is not a build-production
authorization. Bronze or Silver observations cannot be cast, dumped/reparsed,
phase-mutated, or supplied to the producer factory. CP4 creates only Bronze, CP5
creates Silver, and CP6 creates Complete plus the first report.

`source_tables` is exactly `PRBD01N001`, `PREF01N001`, `PREF02N001`,
`PRFD01N001`. `silver_tables` is exactly `bond_instrument`,
`domestic_listed_product`, `overseas_listed_product`, `fund_item`,
`fund_item_attribute`. Every expected/observed pair must be equal before the model can
be constructed. The report does not contain the observed, nonfrozen quality-issue
total; that belongs to the quality summary.

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

The strict declaration order and complete field inventory are:

```text
QualitySummaryReport
  report_id                     literal "quality_summary"
  report_contract_version       literal "1.0.0"
  artifact_contract_version     literal "1.0.0"
  total_issues                  nonnegative integer
  distinct_affected_source_rows nonnegative integer
  by_source_table               tuple[SourceTableCount, ...]
  by_rule                       tuple[RuleCount, ...]
  by_severity                   tuple[SeverityCount, ...]
  by_quality_status             tuple[QualityStatusCount, ...]
  by_quarantine_flag            tuple[BooleanCount, BooleanCount]
  quarantined_issue_count       nonnegative integer
  quarantined_source_row_count  nonnegative integer
  excluded_silver_records       tuple[ExcludedSilverCount, ...]
  quality_table_logical_hash    lowercase SHA-256

SourceTableCount
  source_table                  one of the four closed source-table literals
  count                         positive integer

RuleCount
  rule_id                       nonempty exact string
  rule_version                  nonempty exact string
  count                         positive integer

SeverityCount
  severity                      exact IssueSeverity value
  count                         positive integer

QualityStatusCount
  quality_status                exact QualityStatus value
  count                         positive integer

BooleanCount
  value                         exact boolean
  count                         nonnegative integer

ExcludedSilverCount
  grain                         instrument | listed_product | fund_item | fund_attribute
  count                         positive integer
```

All tuple entries are unique and contain only observed positive groups except the
always-present two quarantine-flag entries. `by_source_table` is sorted by
`source_table`; `by_severity` by `severity`; `by_quality_status` by `quality_status`;
`excluded_silver_records` by `grain`, all in Unicode code-point order; `by_rule` is
sorted by `(rule_id, rule_version)`; and
`by_quarantine_flag` is exactly `False`, then `True`. Aggregate fields must equal their
grouped counts: each of the source-table, rule, severity, quality-status, and quarantine
families independently sums to `total_issues`; the `True` entry equals
`quarantined_issue_count`; affected/quarantined source-row counts cannot exceed their
corresponding issue counts; and `quarantined_source_row_count` must equal the source-audit
quarantine observation. No report model accepts an omitted observed group, duplicate group,
mapping-shaped substitute, float count, or boolean-as-integer.

### 7.3 Report logical identity

Both reports have strict, versioned Pydantic contracts. Their canonical
logical bytes are compact sorted-key JSON plus one terminal newline. They contain no
wall-clock or output-path field. Each report receives a canonical SHA-256 independent
of its pretty on-disk rendering. The report models carry closed semantic IDs:
`source_audit` and `quality_summary` respectively.

Each model exposes `semantic_projection() -> Mapping[str, object]`. That projection is
the exact complete field inventory above in declaration order, including `report_id`
and both contract versions. It excludes only rendering/path/operational metadata,
because none of those fields may exist on either strict model. `report_logical_hash`
accepts only this closed report protocol, requires the projection keys to equal the
model's declared fields exactly, canonicalizes the projection once, and hashes those
bytes. A second ad-hoc report DTO or a caller-supplied projection is prohibited.

```python
class SemanticReportIdentity(Protocol):
    @property
    def report_id(self) -> str: ...
    def semantic_projection(self) -> Mapping[str, object]: ...


def report_logical_hash(report: SemanticReportIdentity) -> str: ...
```

Model validation proves each report's local invariants; concrete verification must also
prove provenance and cross-report meaning. CP7's `StrictArtifactReportVerifier` reparses
both files only through the live inventory, then independently rebuilds their complete
semantic projections from the manifest's strict input identities and the same eleven
live-inventory-owned verified table handles. It bounded-streams/group-counts Bronze and
quality rows and uses verified table counts/hashes plus exact link/evidence relations;
it does not trust report aggregates or a manifest-declared report hash as observations.
The rebuilt source-audit expected values must equal its rebuilt observed values, the
rebuilt quality group/aggregate inventories must equal the parsed quality report, and
`quality_table_logical_hash` must equal the verified quality-table handle. Finally,
`QualitySummaryReport.quarantined_source_row_count` must equal
`SourceAuditReport.quarantine_source_rows.observed`. Parsed-vs-rebuilt model equality
and this cross-report equality are checked before either report logical hash is accepted.
Changing both report payloads and every attacker-controlled outer hash cannot bypass
this relation.

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

Canonical dispatch is closed and ordered: `None`, exact `bool`, exact `int`, exact
`str`, `Decimal`, `datetime`, `date`, `StrEnum`/string-valued `Enum`,
`PurePosixPath`, exact `list`/`tuple`, then `Mapping` with exact-string keys. It does
not coerce subclasses through an earlier branch (`bool` is never an integer count),
and does not accept `float`, bytes, sets, arbitrary iterables, dataclasses, Pydantic
models, or objects with only a useful `repr`. Mapping keys are sorted by Unicode code
point and must be unique exact strings; arrays keep their supplied order.

Decimal canonicalization first rejects nonfinite values, expands exponent notation,
and removes only insignificant trailing fractional zeroes. It then proves exact fit in
`DECIMAL(38,18)`: at most 18 remaining fractional digits and at most 20 integer digits,
with no nonzero digit discarded or rounded. `-0`, `0E-18`, and every other numerical
zero become the JSON string `"0"`.
A naive `datetime` is rendered with exactly six fractional digits and no suffix. An
aware `datetime` is accepted only when its UTC offset is exactly zero and is rendered
with exactly six fractional digits plus `Z`; another offset is rejected rather than
silently converted. `date` dispatch occurs after `datetime`. Enum values must be exact
strings. `canonical_json_bytes` uses `ensure_ascii=False`, `allow_nan=False`, sorted
keys, compact separators, UTF-8, and either exactly one terminal newline or none as
selected by its keyword argument.

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

Checkpoint 2 freezes the narrow structural protocols consumed by those hash
primitives; Checkpoint 3's concrete `ColumnSpec` and `TableSpec` must implement them
without an adapter:

```python
class ColumnSpecIdentity(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def logical_type(self) -> str: ...
    @property
    def arrow_type(self) -> str: ...
    @property
    def duckdb_type(self) -> str: ...
    @property
    def nullable(self) -> bool: ...


class TableSpecIdentity(Protocol):
    @property
    def table_name(self) -> str: ...
    @property
    def grain(self) -> str: ...
    @property
    def columns(self) -> tuple[ColumnSpecIdentity, ...]: ...
    @property
    def unique_key(self) -> tuple[str, ...]: ...
    @property
    def sort_key(self) -> tuple[str, ...]: ...
    @property
    def logical_projection(self) -> tuple[str, ...]: ...
```

Every protocol property is runtime-validated as its exact declared scalar/tuple type.
Column names are unique; unique/sort/logical-projection names must exist in `columns`;
and `logical_projection` itself is ordered, unique, and nonempty. The schema identity
projection is exactly `table_name`, `grain`, the ordered five-field column projections,
`unique_key`, and `sort_key`. `logical_projection` deliberately does not enter the
schema hash, but enters the table header exactly once. Each logical row must be a
mapping whose exact key set equals `logical_projection`; the iterator is consumed once,
its observed count must equal `row_count`, which is an exact non-boolean nonnegative
`int`, and no rows are
materialized. The signatures are:

```python
def schema_sha256(spec: TableSpecIdentity) -> str: ...

def table_logical_hash(
    spec: TableSpecIdentity,
    *,
    row_count: int,
    rows: Iterable[Mapping[str, object]],
) -> str: ...
```

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

`manifest_logical_hash(manifest: ManifestLogicalIdentity) -> str` accepts one internal
structural protocol with exact properties `manifest_version`,
`artifact_contract_version`, `artifact_set_id`, `dataset_version`, ordered
`logical_inputs: tuple[ExpectedLogicalInput, ...]`, exact seven-field
`ArtifactVersions`, ordered `tables: tuple[ExpectedLogicalTable, ...]`, and ordered
`reports: tuple[ExpectedSemanticReport, ...]`. It validates these through their strict
models and hashes exactly the projection listed above. It accepts no arbitrary mapping,
file inventory, physical manifest bytes, output path, or timestamp.

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

Parquet verification has two deliberately non-interchangeable capability domains.
Before reports and the manifest exist, CP4 supplies an exact `OwnedStageParquetLeaf`
for one frozen `TableSpec`. The leaf is bound to the live marker-owned build stage and
its retained parent/`parquet` directory descriptors; creation is relative
`O_CREAT | O_EXCL | O_NOFOLLOW` mode `0600`, and later open/unlink operations accept
only the exact leaf object and recorded `(st_dev, st_ino, file type, st_nlink)`.
Substitution, a foreign/copied leaf, closed owner, existing name, symlink/hardlink, or
owner/marker change fails closed. CP3 defines the protocol and consumes it; CP4 creates
the production implementation and owns stage cleanup.

```python
class OwnedStageParquetLeaf(Protocol):
    @property
    def table_name(self) -> str: ...
    @property
    def relative_path(self) -> PurePosixPath: ...
    def create_exclusive(self) -> AbstractContextManager[BinaryIO]: ...
    def open_verified(self) -> AbstractContextManager[BinaryIO]: ...
    def create_verification_workspace(
        self,
    ) -> AbstractContextManager["OwnedParquetVerificationWorkspace"]: ...
    def assert_unchanged(self) -> None: ...
    def unlink_if_exact_writer_owned(self) -> None: ...


class OwnedStageArtifactOwner(Protocol):
    @property
    def persistence_timestamp(self) -> datetime: ...
    def assert_live(self) -> None: ...
    def require_owned_parquet_leaf(self, leaf: OwnedStageParquetLeaf) -> None: ...
    def _register_staged_verification(
        self,
        value: "StagedParquetVerification",
        handle: "StagedParquetHandle",
    ) -> object: ...
    def _require_registered_staged_verification(
        self,
        value: "StagedParquetVerification",
        handle: "StagedParquetHandle",
        token: object,
    ) -> None: ...
    def _require_registered_staged_handle(
        self, handle: "StagedParquetHandle", token: object
    ) -> None: ...
    def _register_staged_set(self, value: "StagedParquetSet") -> object: ...
    def _replace_registered_staged_set(
        self, previous: "StagedParquetSet", value: "StagedParquetSet"
    ) -> object: ...
    def _require_registered_staged_set(
        self, value: "StagedParquetSet", token: object
    ) -> None: ...
class ManagedUniqueKeyIndex(Protocol):
    def insert_canonical_batch(self, keys: Sequence[bytes]) -> None: ...
    def assert_unique(self) -> None: ...


class OwnedParquetVerificationWorkspace(Protocol):
    def create_unique_key_index(
        self, *, limits: "ParquetVerificationLimits"
    ) -> AbstractContextManager[ManagedUniqueKeyIndex]: ...
    def assert_unchanged(self) -> None: ...


@dataclass(frozen=True, init=False)
class StagedParquetHandle:
    _owner: OwnedStageArtifactOwner
    _leaf: OwnedStageParquetLeaf
    _verified_leaf_identity: object
    _owner_registration_token: object
    table_name: str
    row_count: int
    schema_sha256: str
    logical_hash: str
    physical_size_bytes: int
    physical_sha256: str

    def iter_batches(
        self, *, batch_size: int = 65_536
    ) -> AbstractContextManager[Iterator[pyarrow.RecordBatch]]: ...


@dataclass(frozen=True, init=False)
class StagedParquetVerification:
    _owner: OwnedStageArtifactOwner
    _owner_registration_token: object
    logical: ExpectedLogicalTable
    physical_size_bytes: int
    physical_sha256: str
    handle: StagedParquetHandle


@dataclass(frozen=True, init=False)
class StagedParquetSet:
    _owner: OwnedStageArtifactOwner
    _registration_token: object
    verifications: tuple[StagedParquetVerification, ...]
    handles: tuple[StagedParquetHandle, ...]
    persistence_timestamp: datetime

    @classmethod
    def from_verified(
        cls,
        *,
        owner: OwnedStageArtifactOwner,
        verifications: tuple[StagedParquetVerification, ...],
    ) -> "StagedParquetSet": ...

    def extend_verified(
        self,
        *,
        owner: OwnedStageArtifactOwner,
        verifications: tuple[StagedParquetVerification, ...],
    ) -> "StagedParquetSet": ...

    def require_owned(self, handle: StagedParquetHandle) -> None: ...
    def verification_for(self, table_name: str) -> StagedParquetVerification: ...
    def table_declarations(self) -> tuple[ArtifactTable, ...]: ...
    def require_tables(self, names: tuple[str, ...]) -> None: ...
    def require_complete(self) -> None: ...
    def assert_live(self) -> None: ...

def verify_staged_parquet_table(
    *, owner: OwnedStageArtifactOwner, leaf: OwnedStageParquetLeaf, spec: TableSpec
) -> StagedParquetVerification: ...


class VerifiedParquetTable(VerifiedTableHandle, Protocol):
    @property
    def entry(self) -> VerifiedPhysicalEntry: ...


class ParquetArtifactTableVerifier(ArtifactTableVerifier):
    def verify_tables(
        self,
        *,
        manifest: ArtifactManifest,
        inventory: VerifiedPhysicalInventory,
        specs: tuple[TableSpecIdentity, ...],
    ) -> TableVerificationResult: ...
```

`StagedParquetHandle` retains the exact live stage-leaf owner but deliberately has no
`VerifiedPhysicalEntry` and cannot implement CP2 `VerifiedTableHandle` or enter
`TableVerificationResult`. Its direct constructor is disabled. A bare tuple of handles
is not a cross-stage capability. `StagedParquetSet` also disables direct construction;
each staged verification/handle retains frozen physical size/SHA plus the opaque
verification registration token issued only by the owner after the verified read. No
leaf/public API can mint that token. The common verifier's module-private seal path
constructs the direct-init-disabled verification and handle together, then atomically
registers those exact two object identities with the exact owner and stores the returned
opaque token in both. The set retains
the ordered verification objects, not only their logical handles; `verification_for`
revalidates the registered pair and current leaf bytes before returning facts;
`table_declarations` returns only logical `ArtifactTable` declarations, and CP7 builds
each physical `ArtifactFile` declaration from the corresponding revalidated
`verification_for(name)` size/SHA. Its sole factory and extension method
validate exact frozen table order, exact handle/verification object identities, one
opaque nonserializable CP4 owner token by object identity, the owner's exact UTC
persistence timestamp, every leaf through
`owner.require_owned_parquet_leaf(...)`, and live marker/descriptor state. Every
consumer first calls `assert_live()`, `require_tables(...)`, and `require_owned(...)`;
the CP7 construction boundary additionally calls `require_complete()`. A copied/equal-looking
set, `object.__new__`/equal-field forgery, superseded registered set, mixed-session
tuple, foreign/unissued handle, reordered/duplicate table, closed owner, or owner/
timestamp substitution fails. CP4-7 pass only this owner-bound set within one live build
session. After all eleven Parquets and both
reports/database have been written and the complete manifest/14-file tree exists, CP7's
`ParquetArtifactTableVerifier` independently reopens each manifest-owned entry through
`VerifiedPhysicalInventory.open_verified`, reruns the common checker, compares every
fact to `ArtifactTable`, creates new final `VerifiedParquetTable` handles, and returns
only `TableVerificationResult.from_verified(...)`. It never promotes or trusts staged
verification facts. A final handle has no stage-leaf opener; a staged handle has no
manifest entry. Runtime checks and typing both reject cross-domain substitution.

`from_verified` registers the newly constructed exact set object with the owner and
stores the returned opaque registration token. `extend_verified` requires the currently
registered exact predecessor, constructs the new set, and atomically replaces the
registration; the predecessor is thereafter superseded and rejected. `assert_live`,
`require_owned`, `verification_for`, `table_declarations`, `require_tables`, and
`require_complete` all call the module-private owner registration check before
using any field. Equality, field copying, or an `object.__new__` forged instance cannot
manufacture that object-identity registration.

Both adapters call one private bounded stream checker. `pyarrow.parquet.ParquetFile`
is constructed while the owning `open_verified()` context is live and cannot escape
it. Every physical/logical pass uses
`ParquetFile.iter_batches(batch_size=65_536, use_threads=False)`; an internal limits
object permits a smaller positive batch size only in focused tests and production
assembly fixes `65_536`. Each yielded batch and all retained state are bounded by that
limit. The checker validates exact Arrow schema/metadata, row-group maximum, final
count, canonical sort order, logical header/hash, and exact uniqueness.
For a staged leaf the checker first streams size/SHA from the held descriptor, rewinds
or duplicates at offset zero for `ParquetFile`, and after all batches independently
re-streams size/SHA from that same descriptor before the leaf's name/owner rescan.
`StagedParquetHandle.iter_batches` repeats those pre/post checks against its frozen
staged physical size/SHA, verified leaf identity, and owner registration on every use;
it stores the exact `_owner` and first requires the handle object/token registration
before opening the leaf. The verification likewise stores that exact owner, and set
fact lookup requires `verification._owner is set._owner` plus the registered pair.
`StagedParquetSet.verification_for` and `table_declarations` repeat the same checks.
Same-inode/same-size mutation during or between
reads therefore fails. The final adapter receives the equivalent guarantee from CP2
`inventory.open_verified` and final `assert_unchanged`; neither adapter uses a path
precheck followed by a lexical reopen.

Sort validation retains only the previous complete sort key. Exact uniqueness does
**not** use a Python `set`, a table-sized Arrow/Polars object, or previous-key-only
comparison. For each table it creates a unique mode-`0700`, marker-owned private
workspace outside the artifact inventory and enters only its managed
`create_unique_key_index(...)` context; no database/spill path or generic DuckDB
connection escapes. The context owns exact marker/directory/key-store/spill identities,
creates a mode-`0600` DuckDB key store, fixes `threads=1`,
`memory_limit="1GiB"`, disables external access and extension install/load, and confines
spill below its owned directory. An internal limits seam permits only smaller positive
memory/batch limits in focused tests; production assembly cannot override 1 GiB/65,536.
Static allowlisted DDL stores collision-free canonical typed unique-key bytes in bounded
inserts and an external group/index query rejects any count greater than one, including
equal keys in nonadjacent batches. Connection close precedes exact marker/directory/
leaf/inode-checked cleanup and rejects directory/leaf ABA substitution;
creation, spill, query, close, substitution, marker, or cleanup failure is a typed
pre-publication/verification failure and never broadens deletion. Stage checks use the
stage session's separately marker-owned scratch child; final checks use trusted OS temp.

`ParquetBatchWriter` accepts an `OwnedStageParquetLeaf`, never a caller/raw `Path`.
`close()` flushes and closes exactly once and returns no verification fact or trusted
handle. Only a later `verify_staged_parquet_table` reopen may create staged verification.
`abort()` may unlink only the exact inode this writer exclusively created after leaf/
owner revalidation; a substituted, foreign, already-existing, hardlinked, or ambiguous
leaf is retained and fails closed for CP4 cleanup. Writer output creation and all
reopens therefore use descriptor-relative capabilities rather than lexical path checks.

Serialization has two separate timestamp boundaries:

```python
def serialize_table_row(spec: TableSpec, value: object) -> Mapping[str, object]: ...

def serialize_bronze_source_row(
    spec: TableSpec,
    value: SourceRow,
    *,
    persistence_timestamp: datetime,
) -> Mapping[str, object]: ...
```

Only `serialize_bronze_source_row` accepts/injects the exact UTC persistence timestamp.
`silver_quality_issue` accepts only the already persisted CP5 strict row and proves its
typed/JSON timestamp agreement; every other serializer has no timestamp argument.
Every call revalidates that `spec` is the exact closed registry member for the exact
model/table pair. `derive_wide_columns(model_type)` has no generic `skip_fields` escape:
it skips only `FundItem.contributing_rows` when and only when `model_type is FundItem`.
Forged/equal-looking specs, wrong model/table pairs, subclasses, and attempts to skip
any other field are rejected.

### 9.2 DuckDB

These database-stage capabilities are implemented and owned by CP4 `staging.py`, not
CP3 `parquet_io.py`:

```python
class OwnedStageDatabaseLeaf(Protocol):
    @property
    def relative_path(self) -> PurePosixPath: ...
    def create_exclusive(self) -> AbstractContextManager[BinaryIO]: ...
    def open_verified(self) -> AbstractContextManager[BinaryIO]: ...
    def assert_unchanged(self) -> None: ...
    def unlink_if_exact_writer_owned(self) -> None: ...


class OwnedStageDatabaseOwner(OwnedStageArtifactOwner, Protocol):
    def claim_database_leaf(self) -> OwnedStageDatabaseLeaf: ...
    def create_database_build_workspace(
        self,
    ) -> AbstractContextManager["ManagedStageDatabaseBuild"]: ...
    def require_owned_database_leaf(self, leaf: OwnedStageDatabaseLeaf) -> None: ...
    def _register_sealed_database(
        self, value: "SealedStageDatabase", leaf: OwnedStageDatabaseLeaf
    ) -> tuple[object, object]: ...
    def _require_registered_sealed_database(
        self,
        value: "SealedStageDatabase",
        leaf: OwnedStageDatabaseLeaf,
        owner_token: object,
        leaf_token: object,
    ) -> None: ...


@dataclass(frozen=True, init=False)
class SealedStageDatabase:
    _owner: OwnedStageDatabaseOwner
    _leaf: OwnedStageDatabaseLeaf
    _owner_registration: object
    _leaf_issuance_token: object
    persistence_timestamp: datetime
    physical_size_bytes: int
    physical_sha256: str

    def validate_against(self, owner: OwnedStageDatabaseOwner) -> None: ...


class ManagedStageDatabaseBuild(Protocol):
    def open_writer(self) -> AbstractContextManager[duckdb.DuckDBPyConnection]: ...
    def checkpoint_close_and_seal(
        self, *, leaf: OwnedStageDatabaseLeaf
    ) -> SealedStageDatabase: ...
```

CP7 `database.py` owns this direct-construction-disabled result (it is not a CP3
`parquet_io.py` type):

```python
@dataclass(frozen=True, init=False)
class StagedDatabaseVerification:
    _owner: OwnedStageDatabaseOwner
    _sealed: SealedStageDatabase
    _owner_registration: object
    _leaf_issuance_token: object
    persistence_timestamp: datetime
    physical_size_bytes: int
    physical_sha256: str

    @classmethod
    def from_sealed(
        cls, *, owner: OwnedStageDatabaseOwner, sealed: SealedStageDatabase
    ) -> "StagedDatabaseVerification": ...

    def validate_against(self, owner: OwnedStageDatabaseOwner) -> None: ...
```

CP7's orchestration signature is exact and keeps the owner explicit:

```python
def build_self_contained_database(
    *,
    owner: OwnedStageDatabaseOwner,
    tables: StagedParquetSet,
    database_leaf: OwnedStageDatabaseLeaf,
) -> StagedDatabaseVerification: ...
```

It requires the complete set and leaf against that exact owner, obtains the managed
workspace from that owner, validates the returned seal against that owner, and calls
`StagedDatabaseVerification.from_sealed(owner=owner, sealed=sealed)`. Inferring an
owner from private leaf/set fields, accepting a foreign equal-looking owner, or passing
the leaf without the explicit owner is forbidden.

Database construction is two-stage because DuckDB must create/open its own valid
database, not an empty precreated final file. CP4's owner first enters one pathless
`ManagedStageDatabaseBuild` backed by a unique mode-`0700` marker-owned private scratch
directory. `open_writer()` alone gives CP7 a configured connection to an internally
owned scratch database. CP7 builds/checkpoints/closes it; the managed context then
rejects a WAL, reopens the exact scratch leaf, and verifies identity/type/link/size/SHA.
Only after that succeeds does `checkpoint_close_and_seal(leaf=...)` call the same
owner's `OwnedStageDatabaseLeaf.create_exclusive()` to obtain a binary final-stage fd
with `O_CREAT | O_EXCL | O_NOFOLLOW` mode `0600`, bounded-copy scratch bytes, `fsync`,
close, and independently reopen/hash/rescan the final leaf. Scratch connection close
precedes exact marker/directory/leaf cleanup. Scratch close/checkpoint/WAL/hash,
copy/fsync/final-close, final substitution/reopen/hash, or scratch cleanup ambiguity
blocks and deletes neither an unowned scratch entry nor final leaf. No caller sees or
supplies a scratch/final path.

After the final rescan, the manager constructs `SealedStageDatabase` only through its
private seal path and atomically registers the exact seal/final-leaf object pair with
the exact `OwnedStageDatabaseOwner`, storing the returned opaque owner and leaf tokens.
No leaf or public caller can mint either token.

The managed CP4 operation returns only `SealedStageDatabase`; CP7's sole
`StagedDatabaseVerification.from_sealed(...)` factory first validates that seal, then
stores the exact `_owner` object plus opaque owner-registration/final-leaf issuance
tokens. `validate_against(owner)` requires `owner is self._owner`, a live registered
seal/leaf/token, exact timestamp, inode/type/link, size, and SHA before manifest
construction consumes those facts. A foreign/equal-looking owner or seal, copy,
`object.__new__` forge, or token substitution fails. Abort/cleanup unlinks only the
exact final inode created by `create_exclusive()`.

Construction uses one writer connection with:

```text
threads = 1
preserve_insertion_order = true
TimeZone = UTC
```

Static allowlisted DDL creates all eleven tables with explicit column order/types.
During construction, rows are read only from one live `StagedParquetSet`
and inserted with an explicit final `ORDER BY`; final CP7 equality uses only the newly
created inventory-owned handles. The builder
checkpoints and closes the database, requires no `.wal`, hashes the closed file, and
reopens it read-only to validate information-schema columns, counts, uniqueness, sort
probes, link evidence, and manifest agreement.

```python
def open_read_only_database(path: Path) -> duckdb.DuckDBPyConnection: ...

def verify_database_against_parquet(
    *,
    inventory: VerifiedPhysicalInventory,
    database_entry: VerifiedPhysicalEntry,
    tables: TableVerificationResult,
    runtime_tmp_root: Path | None = None,
) -> None: ...
```

The function accepts only an existing nonsymlink regular file and calls DuckDB with
`read_only=True` and `enable_external_access=false`. Integration tests require
persistent INSERT, UPDATE, DELETE, and CREATE attempts against the artifact database,
plus external ATTACH and COPY attempts, to fail. DuckDB session-local TEMP objects are
outside this persistence contract; the public FinProof query path never exposes raw SQL
or creates them.

The private equality verifier never gives DuckDB a path below the published artifact
root. DuckDB cannot consume the retained file descriptor as its database, so the
verifier first creates one unique mode-`0700`, marker-owned directory below trusted OS
temp (or a containment-validated runtime-temp root), creates a mode-`0600` regular
`database-copy.duckdb` with `O_CREAT | O_EXCL | O_NOFOLLOW`, and bounded-stream-copies
the source only through `inventory.open_verified(database_entry)`. The source context
must complete its leaf/ancestor/tree revalidation. After the destination closes, its
`lstat`/held-`fstat` identity, type, `st_nlink == 1`, byte count, and SHA-256 must still
match both the retained source entry and manifest declaration before DuckDB opens the
private copy. The verifier repeats the copy identity/size/hash checks after closing
DuckDB and before marker-owned cleanup. Source swap during copy, private-copy
substitution, ambiguous marker/identity, close/hash failure, or cleanup failure fails
closed. There is no fallback that reopens `root / database_path` after inventory.

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

Both `report_id` and `logical_hash` are required JSON object members on every
`ArtifactFile`; they are not optional/omittable fields. Their value is non-null on a
`kind="report"` entry and exact JSON `null` on every `parquet` or `duckdb` entry. A
missing key, an omitted-on-serialization default, a non-report string value, or a
report null is schema/model invalid. This explicit-null policy is part of the canonical
manifest shape even though physical file entries are excluded from the overall logical
hash.

`schemas/artifact_manifest.schema.json` is updated to match this model exactly,
including terminal-`Z` UTC validation. Runtime and contract consumers call
`Draft202012Validator.check_schema`, supply `FormatChecker`, and inspect every error.

### 10.2 Load and verify

```python
@classmethod
def ArtifactManifest.load(path: Path) -> ArtifactManifest: ...

def ArtifactManifest.verify(root: Path) -> VerifiedArtifactSet: ...
```

Checkpoint 2 implements only `load`, the descriptor-bound physical inventory, and the
internal orchestration kernel below. Under D-024 the public `verify` method and
`VerifiedArtifactSet` do not exist until Checkpoint 8 installs the independently
approved official expected source/resource. Checkpoint 7 completes the concrete core
ports and packaged-comparator implementation, but the absent resource leaves the
expected route unavailable outside synthetic kernel orchestration.

```python
@dataclass(frozen=True)
class VerifiedPhysicalEntry:
    path: PurePosixPath
    kind: Literal["manifest", "parquet", "report", "duckdb"]
    size_bytes: int
    sha256: str
    st_dev: int
    st_ino: int
    file_type: int
    st_nlink: int


class VerifiedPhysicalInventory(AbstractContextManager["VerifiedPhysicalInventory"]):
    @property
    def manifest_entry(self) -> VerifiedPhysicalEntry: ...
    @property
    def declared_entries(self) -> tuple[VerifiedPhysicalEntry, ...]: ...
    def open_verified(
        self, entry: VerifiedPhysicalEntry
    ) -> AbstractContextManager[BinaryIO]: ...
    def require_owned(self, entry: VerifiedPhysicalEntry) -> None: ...
    def assert_unchanged(self) -> None: ...


def verify_declared_inventory(
    manifest: ArtifactManifest,
    root: Path,
) -> VerifiedPhysicalInventory: ...
```

The inventory is a live, single-owner capability, not a serializable DTO. It retains
the full filesystem-anchor-to-root directory descriptor chain plus the root's
`parquet` and `reports` descriptors and every `(st_dev, st_ino, file type)` identity
until context exit. It has exactly one `manifest_entry` plus the
fourteen `declared_entries` in manifest order. `require_owned` and `open_verified`
accept only the exact entry instance owned by that live inventory (object identity,
not structural equality); both fail after inventory close. `open_verified` opens its leaf relative to the retained
parent descriptor with `O_NOFOLLOW`, requires the new `fstat` identity/type/link count
to equal the recorded values, independently streams exact size/SHA from that held
descriptor before yielding (then resets/duplicates at offset zero), yields the binary
stream, and after consumer close independently re-streams exact size/SHA from the same
held descriptor before revalidating the leaf name, opened descriptor, every retained
ancestor, and exact directory inventory. `assert_unchanged()` reopens every exact-owned
leaf through retained parents, rechecks identity/type/link, re-streams all fourteen
declared size/SHA values, reparses held `manifest.json`, requires equality with the
bound manifest, and repeats the exact tree/ancestor inventory. Same-inode, same-size
in-place mutation therefore fails even if no name or metadata identity changes. It
fails after inventory close. This is the only final-artifact Parquet/report/database
reopen boundary; it becomes usable only after the complete manifest tree exists.
Pre-manifest CP4-6 Parquet access uses the non-interchangeable stage-leaf capability in
section 9.1. Later code never reconstructs an absolute artifact path from a string.

Root-to-manifest binding is mandatory. `verify_declared_inventory` opens the supplied
absolute root through a retained no-follow descriptor chain beginning at the filesystem
anchor; every ancestor and the root must be a nonsymlink directory and is identity-
revalidated through its retained parent. It reads `manifest.json` relative to that held root,
parses it through the same strict schema/model loader, and requires equality with the
passed `manifest` before it trusts any declaration. Thus a model loaded from another
tree or a replaced root cannot authorize this tree. The manifest leaf is identity-
checked like every other file, must be a nonsymlink regular file with `st_nlink == 1`,
and is revalidated after parsing although it is not one of the fourteen self-declared
hashes.

Recursive traversal uses the valid descriptor API `os.scandir(held_directory_fd)`;
there is no nonexistent `follow_symlinks` argument on `os.scandir`. Each returned
`DirEntry` is classified with `entry.stat(follow_symlinks=False)`. Required child
directories are opened relative to the held parent using
`O_DIRECTORY | O_NOFOLLOW`, and their `fstat` identities must match the `DirEntry`
snapshot. Regular leaves require `st_nlink == 1`, are opened with `O_NOFOLLOW`, and are
size/hash checked through that descriptor. After hashing, the implementation repeats
descriptor-relative `os.stat(name, dir_fd=parent_fd, follow_symlinks=False)` and a full
`os.scandir(held_directory_fd)` name/identity inventory before returning. Unsupported
descriptor-relative open/stat/scandir semantics, an unavailable no-follow flag, any
close/revalidation error, or any identity change fails closed; there is no Path-based
precheck-and-reopen fallback.

Checkpoint 2 also freezes the internal port signatures and exact order used by the
eventual public verifier:

```python
class ClosedTableSpecRegistry(Protocol):
    def ordered_specs(self) -> tuple[TableSpecIdentity, ...]: ...


class VerifiedTableHandle(Protocol):
    @property
    def table_name(self) -> str: ...
    @property
    def entry(self) -> VerifiedPhysicalEntry: ...
    @property
    def row_count(self) -> int: ...
    @property
    def schema_sha256(self) -> str: ...
    @property
    def logical_hash(self) -> str: ...


@dataclass(frozen=True, init=False)
class TableVerificationResult:
    tables: tuple[ExpectedLogicalTable, ...]
    handles: tuple[VerifiedTableHandle, ...]

    @classmethod
    def from_verified(
        cls,
        *,
        inventory: VerifiedPhysicalInventory,
        tables: tuple[ExpectedLogicalTable, ...],
        handles: tuple[VerifiedTableHandle, ...],
    ) -> "TableVerificationResult": ...

    def validate_against(self, inventory: VerifiedPhysicalInventory) -> None: ...


class ArtifactTableVerifier(Protocol):
    def verify_tables(
        self,
        *,
        manifest: ArtifactManifest,
        inventory: VerifiedPhysicalInventory,
        specs: tuple[TableSpecIdentity, ...],
    ) -> TableVerificationResult: ...


class ReportVerificationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    reports: tuple[ExpectedSemanticReport, ...]
    exact_link_pair_sha256: str
    exact_link_evidence_count: int


class ArtifactReportVerifier(Protocol):
    def verify_reports(
        self,
        *,
        manifest: ArtifactManifest,
        inventory: VerifiedPhysicalInventory,
        tables: TableVerificationResult,
    ) -> ReportVerificationResult: ...


class ArtifactDatabaseVerifier(Protocol):
    def verify_database(
        self,
        *,
        manifest: ArtifactManifest,
        inventory: VerifiedPhysicalInventory,
        specs: tuple[TableSpecIdentity, ...],
        tables: TableVerificationResult,
        logical: "ArtifactCoreVerificationResult",
    ) -> None: ...


class ArtifactExpectedComparator(Protocol):
    def compare(self, *, actual: ArtifactLogicalContractView) -> None: ...


class ArtifactCoreVerificationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    artifact_contract_version: str
    artifact_set_id: str
    dataset_version: date
    logical_inputs: tuple[ExpectedLogicalInput, ...]
    tables: tuple[ExpectedLogicalTable, ...]
    reports: tuple[ExpectedSemanticReport, ...]
    overall_manifest_logical_hash: str
    exact_link_pair_sha256: str
    exact_link_evidence_count: int


class ArtifactExpectedVerificationResult(ArtifactCoreVerificationResult):
    pass


class ManagedArtifactVerificationRoot(Protocol):
    def open_inventory(
        self, *, manifest: ArtifactManifest
    ) -> AbstractContextManager[VerifiedPhysicalInventory]: ...
    def take_expected_acceptance_seal(self) -> object: ...


class ArtifactVerificationKernel:
    def __init__(
        self,
        *,
        table_registry: ClosedTableSpecRegistry | None,
        table_verifier: ArtifactTableVerifier | None,
        report_verifier: ArtifactReportVerifier | None,
        database_verifier: ArtifactDatabaseVerifier | None,
        expected_comparator: ArtifactExpectedComparator | None,
    ) -> None: ...

    def verify_candidate_core(
        self,
        *,
        manifest: ArtifactManifest,
        root: Path,
    ) -> ArtifactCoreVerificationResult: ...

    def verify_expected(
        self,
        *,
        manifest: ArtifactManifest,
        root: Path,
    ) -> ArtifactExpectedVerificationResult: ...

    def verify_candidate_core_from_root(
        self,
        *,
        manifest: ArtifactManifest,
        root: ManagedArtifactVerificationRoot,
    ) -> ArtifactCoreVerificationResult: ...

    def verify_expected_from_root(
        self,
        *,
        manifest: ArtifactManifest,
        root: ManagedArtifactVerificationRoot,
    ) -> ArtifactExpectedVerificationResult: ...
```

All five ports are private fixed production dependencies, not public/caller-supplied
arguments. CP2's already-approved `verify_candidate_core`/`verify_expected` path-root
entries remain unchanged for their closed synthetic tests and the eventual private
published-root opener. CP7 adds `verify_candidate_core_from_root`; CP8 activates
`verify_expected_from_root`. Every entry shares one private inventory execution path:
candidate routes require the registry/table/report/database ports and expected routes
require all five. A required missing port is an incomplete assembly and raises
`ArtifactContractError(VERIFICATION_INCOMPLETE)` before filesystem work, with
`reason=missing_verification_ports` and the unique sorted missing port names stored as
compact canonical JSON in string-only internal context;
no partial result is returned. The expected entry performs exactly:
descriptor-bound inventory, tables, reports, overall-manifest logical reconstruction,
database, expected-contract comparison, final inventory revalidation, then result.
The candidate entry performs the identical first five stages, skips only expected
comparison, then performs final inventory revalidation and returns the strict core type.
Only after the managed-root expected entry's final inventory revalidation does it
atomically register one one-use opaque expected-acceptance seal on that exact still-live
root. The path-root compatibility entry returns no stage-transfer authorization, and
the candidate entry never registers one. Failure or root close invalidates any
incomplete/untaken seal; a seal already detached by the one-use take operation is
explicitly consumed by transfer or invalidated by CP8 authorization cleanup.
The table result flows to report, overall, and database ports; the report result joins
it to construct the strict logical result at the overall stage; database receives that
same logical result; and expected comparison receives it only after database succeeds.
Any
exception aborts immediately, closes the inventory, calls no later port, and returns
nothing. CP2 uses synthetic stubs only to prove both orders/short-circuit behavior; its
production assembly deliberately has all five ports set to `None`, so it cannot produce
even the internal result. CP3 supplies the table registry, common checker, staged
adapter, and final adapter implementation; CP4-7 carry only D-025's owner-bound staged
set before final inventory, while CP7 is the first checkpoint that can invoke the final
adapter after manifest completion.
CP5/6 produce the report semantics and timestamp/link relation evidence, and CP7 supplies concrete
report/database ports plus the packaged-comparator implementation and performs the
final relation rechecks. CP8 installs the reviewed expected bytes, activates the
expected route, and alone wraps its result as the first public `VerifiedArtifactSet`.

The new managed-root entries never accept a `Path`, descriptor integer, stage basename,
or private capability field. CP4's `OwnedCandidateStage.open_verification_root()`
returns the managed adapter over its already-held stage root. CP7 enters that adapter
for candidate verification; CP8 uses the same entry for expected authorization.
Published-target recognition may enter the retained CP2 private path-root boundary,
which itself opens the descriptor-bound inventory; it never receives or reconstructs a
candidate stage path. Every inventory closes on success or every failure. No caller
reconstructs `/dev/fd`, an absolute stage path, or a root from manifest text/private
fields.

Both result types structurally implement the CP1 `ArtifactLogicalContractView`; they do
not duplicate its entry models and contain no
root, descriptor, artifact path, timestamp, physical hash, database handle, or trust
flag. Both internal result models apply strict types, frozen exact field/order/name/
grain inventories, lowercase hashes, non-boolean nonnegative counts, and their own
cross-field consistency checks; they are not unchecked dataclass transport containers.
The official known row counts, frozen exact-link pair hash/evidence count, and other
baseline-specific values belong only to `ExpectedPhase1ArtifactContract` and its
comparator. Core results may therefore represent a complete hermetic small fixture,
while only expected comparison can accept the official evaluation baseline.

`TableVerificationResult` is the one deliberate internal capability carrier between
stages, not a trusted public result. Its direct constructor is disabled; the sole
`from_verified(...)` factory runtime-validates exact tuples,
eleven-entry frozen order, one-to-one table-name/count/schema/logical-hash equality
between each CP1 logical entry and handle, and calls `inventory.require_owned(...)` for
every handle entry. `validate_against(inventory)` repeats those checks immediately on
receipt by each downstream port, including live owner identity, so a structurally
forged/copied handle or result cannot cross a stage boundary. CP3's final-only
`VerifiedParquetTable` structurally implements
`VerifiedTableHandle`. CP7 report/timestamp/link/database ports receive the same handles
and can reopen typed batches only via `inventory.open_verified(handle.entry)`; no port
reconstructs a path or trusts a second table scan unrelated to CP3's verified identity.
The distinct `StagedParquetHandle` does not have an `entry`, cannot implement this
protocol, and is never accepted by the kernel.

The core route is not an expected-accepted/public result. CP7 exposes it only through
the already guarded, repository-only candidate transform: the CP1 initial/second
baseline probes must both permit the call, no publication occurs, and only a canonical
`ExpectedPhase1ArtifactContract` projection escapes before cleanup. No installed
package, readiness path, `finproof` CLI, or normal builder can call
`verify_candidate_core_from_root`. CP7 publication/recovery state-machine mechanics are tested
below the authorization boundary with synthetic filesystem states; no production
recognition/publisher accepts a core result and the D-022 candidate remains strictly
unpublished/no-write. CP8 wires public/evaluation `ArtifactManifest.verify` only to
the managed-root `verify_expected_from_root` entry; only that route may construct `VerifiedArtifactSet` or authorize
target recognition/publication.
This avoids a no-op expected comparator, an unreviewed generated baseline, and
duplicated verification orchestration.

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
class ArtifactLogicalContractPayload(BaseModel): ...

class ExpectedPhase1ArtifactContract(ArtifactLogicalContractPayload): ...

@classmethod
def ExpectedPhase1ArtifactContract.load(path: Path) -> ExpectedPhase1ArtifactContract: ...

def compare_expected_artifact_contract(
    actual: ArtifactLogicalContractView,
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

`ArtifactLogicalContractPayload` is the private strict structural twin used to
reconstruct the `actual` protocol: exact field types, inventories, declaration order,
names/grains, non-boolean nonnegative integers, and hash shapes, but no official known
count/pair/evidence value assertions. `ExpectedPhase1ArtifactContract` adds those
baseline-specific validators. The comparator strict-reconstructs actual through the
payload type, serializes both payloads canonically, and computes all RFC 6901
differences. Thus a well-shaped wrong official count is reported at its deterministic
path rather than mislabeled `invalid_actual_contract`; only malformed structure/types
use that reason.

Its scalar boundary is also closed before the first official baseline exists:
`artifact_contract_version` is literal `1.0.0`, `artifact_set_id` is literal
`finproof-data-artifacts/v1`, and `dataset_version` is exactly `2026-07-11`; every hash
is lowercase 64-hex; input sizes and counts are exact nonnegative integers (never
booleans); the nine input, eleven table, and two report tuples have their frozen order,
names, kinds, and grains; the known ten non-quality table counts are
207/145,393/6,401,851, 42,394/1,733/5,646/11,138/95,618, and 47/371; the quality-table
count remains a nonnegative reviewed value rather than a pre-baseline `6,032` literal;
the pair hash is the frozen 64-hex value in section 5.10; and evidence count is exactly
371. `ExpectedLogicalInput`, `ExpectedLogicalTable`, and `ExpectedSemanticReport` in
`expected_contract.py` remain the only entry types used by the CP1 protocol and the
later verified result.

The exact expected table `(name, grain)` sequence is:

```text
bronze_source_column                  source_column
bronze_source_row                     source_row
bronze_source_cell                    source_cell
silver_bond_instrument                instrument
silver_domestic_listed_product        listed_product
silver_overseas_listed_product        listed_product
silver_fund_item                      fund_item
silver_fund_item_attribute            fund_attribute
silver_quality_issue                  quality_issue
gold_exact_cross_source_link          exact_cross_source_link
gold_exact_cross_source_link_evidence exact_cross_source_link_evidence
```

On mismatch, `compare_expected_artifact_contract` first reconstructs the actual value
through `ArtifactLogicalContractPayload`, then recursively compares its JSON-mode payload with
the expected payload. It reports the complete sorted tuple of differing RFC 6901 JSON
Pointers. Object tokens escape `~` as `~0` and `/` as `~1`; array positions are decimal
indices; a whole-root scalar mismatch is `""`. The error's string-only internal context
stores `difference_paths` as compact UTF-8 canonical JSON, for example
`["/reports/0/semantic_hash","/tables/3/row_count"]`. Paths are unique and sorted by
Unicode code point; no raw differing value, absolute path, or input payload is exposed.

The initial baseline has one review-only bootstrap boundary outside the installed
package and `finproof` CLI:

```python
def build_candidate_artifacts(
    settings: Settings,
    versions: VersionBundle,
    *,
    options: ArtifactBuildOptions,
) -> ArtifactCoreVerificationResult: ...
```

This interface lives only in repository review tooling, is not exported by the package,
has no console entry point, and is unavailable to runtime/readiness. It refuses to run
if either the repository expected-contract file or its packaged resource already
exists. It builds with the exact production transformation into a fresh private
temporary target, performs full core manifest/Parquet/report/DuckDB verification, never
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

Installed-wheel loaders use `importlib.resources`. Hatch editable installs place
force-included data in the installed distribution while the regular `src/finproof`
package can shadow that data path, so the same public loader has one explicit editable
fallback: `importlib.metadata.distribution("finproof").locate_file(...)` for the exact
closed force-included destination. It accepts only an existing nonsymlink regular file
whose distribution-relative path is the frozen resource path. It never uses
`Path.cwd()`, a source-tree parent calculation, or a caller-supplied resource path. A
wheel contract test builds the wheel, opens both packaged resources through
`importlib.resources`, and proves byte/SHA equality with the root schema files. A real
standard editable-install test proves the distribution-metadata fallback returns the
same bytes while the source package shadows the copied data. Installed-wheel artifact
verification uses only the caller's artifact root plus package resources; it neither
requires nor synthesizes a `repository_root`. The explicit repository anchor is an
offline-build input boundary.

The separately tracked official logical contract has one repository source of truth,
`config/expected_phase1_artifacts.json`, and is force-included byte-for-byte as
`finproof/resources/contracts/expected_phase1_artifacts.json`. Evaluation readiness
loads it through the same wheel/editable resource boundary; no production code reads a
path below `tests/`. Wheel and real editable tests prove source/resource byte and SHA
equality for this contract too. The production package also declares `jsonschema` and
`rfc3339-validator` as runtime dependencies. Other artifact config and official sources
remain offline build inputs and are not silently copied into the runtime wheel.

## 11. Guarded transactional publication

Portable filesystems cannot atomically replace a non-empty directory with one
`os.replace`. Task 5 therefore promises offline transactional publication with rollback,
not simultaneous-reader atomicity.

`CandidateArtifactSet` is a private, live, direct-construction-disabled stage
capability created by the builder. It directly retains one exact instance-owned opaque
`CandidateStageCustody` binding the marker-owned sibling stage
directory `(parent identity, basename, st_dev, st_ino)`, its manifest, and its
`ArtifactCoreVerificationResult`; it is not trusted for publication and the repository
candidate can only clean it. After the reviewed expected resource exists, CP8's sole
`authorize_candidate_for_publication(candidate: CandidateArtifactSet) ->
ExpectedAcceptedPublicationStage` factory reruns the expected route against that exact
held stage, preserves the stage/parent descriptor identity, and binds the resulting
`VerifiedArtifactSet` into one nonserializable context-managed capability. This CP8
capability is the sole production implementation of publication's private transition
port; CP7 has only its test-helper synthetic implementation. The publisher
accepts only that single capability—never separate `verified` and `stage` arguments—so
a result for stage A cannot authorize stage B. It revalidates the bound parent/name/
inode immediately before rename and closes the capability on every exit. Reopened
target recognition independently reruns public expected verification. The CP4 custody
has no rename, rollback, target, backup, or tombstone operation. CP7 contains
only the authorization-independent state-machine mechanics; neither capability has a
CP7 production publication call site. CP8 moves that custody only through typed
instance acceptance; no production registry or raw descriptor handoff exists.

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
2. **Manifest and hashing:** strict schema/model/load, canonical scalar/schema/table/
   semantic-report/manifest hash primitives, exact strict report shapes, descriptor-
   bound recursive physical inventory, exhaustive expected-contract differences, and
   manifest UTC shape plus the internal synthetic-port kernel. It has no concrete
   table/report/database/expected verifier and no public trusted result.
3. **Table specs and serializers:** exact Arrow/DuckDB schemas, wide projections,
   canonical model round trips, Decimal/date/time behavior, fixed Parquet settings,
   the exact Bronze/quality timestamp-neutral logical projections, the common bounded
   stream/unique checker, D-025 owner-bound staged set/verification contracts, and the
   distinct final manifest-inventory adapter implementation. CP4 implements the
   production owner plus Parquet/database stage leaves; CP5/6/7 consume only its live
   set, and CP7 is the first checkpoint able to invoke the final adapter. CP3 still
   cannot expose a complete artifact verifier.
4. **Bronze streaming and owned staging:** held-descriptor same-stream workbook
   verification; all three Bronze tables; bounded batches; exact row/cell/column
   reconstruction; the exact Bronze audit typestate plus rejection of forged later
   phases (CP5 first implements Silver and CP6 first implements Complete/report); the
   trusted-Settings-recomputed instance-owned resolved bundle, held-nine-input verifier/
   seal, descriptor-owning identity, and owning-module held-stream parsers with ABA
   rejection; CP2-owned opaque held-root adoption; the sole managed live/closing/closed stage owner;
   pathless fixed-bound external ordering; CP4-owned Parquet/database leaves,
   workspace, and seal; exact abort/ambiguous retention/lock transfer into an instance-
   owned candidate custody without global registries; and failed-stage
   isolation. It cannot construct a final report or publish.
5. **Silver and quality:** rating parsing only from the retained build-input stream;
   exact Bronze-result-fed one-use finalization; domestic/overseas wide records;
   bounded item-group fund collapse and attribute relation; typed closed external
   order/export/join operations shared forward with CP6; two quarantines; exact
   `DataQualityIssue` D-021 injection/schema/joins and immutable join observations;
   exact nine-table/result/instrumentation custody; the first Silver audit successor;
   quality-summary semantic production; and no new metric/family/eligibility behavior.
6. **Exact links:** raw identifier rule v1.0.0, one-to-one conflict rejection, 47-pair
   TSV hash, 371 locators, no trimming/name/fuzzy/family links, CP6's first Complete
   successor, and the sole source-audit report producer.
7. **DuckDB, reports, pre-baseline publication mechanics, CLI:** write/reparse and
   verify both completed report payloads, perform the complete operational timestamp/
   link rechecks, materialize self-contained tables, enforce read-only rejection, run
   bounded OS-temp equality verification, implement (but do not yet activate) packaged
   expected comparison, exercise authorization-independent guarded clean/rollback/
   tombstone state-machine failures without a publish-capable core token, and provide
   safe absent-baseline exit/output. It has
   no public trusted result while official expected bytes are absent.
8. **Official reproduction and Phase 1 gate:** two different-time logical builds, one
   generation-integrity verification per build, bounded-memory evidence, all
   counts/hashes, independent candidate review, creation/commit of the official expected
   contract and wheel-byte identity test, activation of expected-accepted
   `ArtifactManifest.verify`/`VerifiedArtifactSet` and normal publication recognition,
   all mandatory repository/source gates, independent whole-branch review, status
   evidence, and clean tree.

An official acceptance test may reuse a session-scoped artifact build, but no production
behavior is introduced only through an acceptance test that is already green.

## 15. Required test matrix

At minimum, tests prove:

- strict manifest/config/schema versions, extra-field rejection, explicit format
  checking, exact nine-input namespace/path inventory, safe paths, deep immutability,
  and all-or-nothing verification;
- CP2 inventory reparses and binds the exact held-root `manifest.json`, uses
  `os.scandir(dir_fd)` plus no-follow `DirEntry.stat`, rejects unsupported descriptor
  semantics, and revalidates every directory/name/inode before each CP3+ reopen and
  before close;
- the internal kernel rejects a missing port before filesystem work and, with synthetic
  ports, calls exactly inventory -> tables -> reports -> overall -> database -> expected
  -> final inventory revalidation, short-circuiting without a result after every
  injected failure; CP2 exports neither public `verify` nor `VerifiedArtifactSet`;
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
- expected-contract mismatches expose every unique sorted RFC 6901 path as canonical
  JSON in bounded internal context, including escaped `~`/`/` tokens and array indices,
  without differing values or paths from the host filesystem;
- initial candidate bootstrap performs full transform/verification without publication
  or write-back, refuses an existing expected file/resource, and is unavailable after
  the reviewed baseline is created;
- every table uses exact schema, type, column order, count, unique/sort key, and model
  round trip;
- staged and final Parquet capabilities are nominally and runtime non-interchangeable:
  staged reopen uses only CP4's exact exclusive no-follow leaf owner, while the final
  adapter uses only CP2 inventory entries and independently recomputes every fact;
- `ParquetFile` and its stream remain inside the owning context, batches are at most
  65,536 with threads disabled, and a marker-owned one-thread/1-GiB spillable exact-key
  index catches nonadjacent duplicates without a table-sized Python collection;
- each of the bond, domestic-listed, overseas-listed, and fund-item wide tables derives
  its complete ordered columns independently from the exact model declaration and
  asserts the frozen sequence; synthetic field insertion/removal/reorder fails instead
  of regenerating a table spec or expected baseline;
- every fund-item wide value and quality column equals its `FundItemValue`
  representative value/status, while all equivalent locators remain recoverable from
  `record_json` and never multiply the item-grain row;
- all-null columns retain declared physical type;
- Decimal values never round and source-local timestamps gain no invented timezone;
- verified workbook streaming hashes/parses one held no-follow descriptor stream,
  revalidates its parent/name/identity/size/SHA before, during, and after row yields,
  and rejects replacement or same-inode mutation without a second path open;
- Bronze reconstructs every D-017 row/cell and retains both malformed rows;
- one managed CP4 session enforces `LIVE -> CLOSING -> CLOSED`, transfers its exact
  held descriptors/marker registrations/advisory lock at most once, retains ambiguous
  abort state without victim deletion, and makes pathless fixed-bound order stores plus
  the exact Section 9.2 database capabilities unavailable after close;
- the exact nine build inputs are opened no-follow and retained through a one-use
  verifier seal; replacement/same-inode mutation/stale free SHA fails, while CP2 root
  adoption consumes only same-generation duplicated directory custody and closes it
  exactly once without exposing a path/fd/private field;
- the checkpoint-owned Bronze, Silver, and Complete source-audit observations are
  introduced in CP4, CP5, and CP6 respectively as distinct exact-field/order/hash
  typestates, and only CP6's Complete can construct `SourceAuditReport`;
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
- only a same-generation CP2 expected-acceptance seal can trigger the staging-owned
  one-use custody move into CP8's production transition capability; real descriptor/
  lock/input-close sentinels prove the old stage is invalidated and no duplicate owner
  or CP7 synthetic-port access exists;
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
