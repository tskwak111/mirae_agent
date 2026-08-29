# Official Data Refresh and Sealed Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Use superpowers:test-driven-development for every behavior change, superpowers:requesting-code-review at each checkpoint, and superpowers:verification-before-completion before any success claim.

**Goal:** Replace the superseded 2026-07-11 official source with the verified 2026-08-24 distribution, migrate the deterministic data/runtime contracts, add sealed holdings evidence, require HyperCLOVA X for both mandated stages, and prove the final candidate against the organizer-shaped evaluation and release gates.

**Architecture:** Keep the existing verified XLSX -> Bronze/Silver/Gold -> read-only DuckDB -> validated QueryPlan -> parameterized SQL -> evidence -> claim-verification pipeline. Add only one bond sale-lot child relation and two holdings relations. Evaluation planning and final wording use HCX; all retrieval, calculation, evidence construction, and verification remain deterministic.

**Tech Stack:** Python 3.12, Pydantic, stdlib `zipfile`/`hashlib`, Polars, PyArrow, DuckDB, FastAPI, httpx, pytest, Ruff, mypy, Docker.

**Spec:** `docs/superpowers/specs/2026-08-28-official-data-refresh-and-sealed-enrichment-design.md`

## Global constraints

- Preserve all existing user changes in `artifacts/evaluation/ablation*.json`, the untracked PDFs, and untracked review packets.
- Work in the current checkout because the user explicitly approved continuing the present state; never run two modifying workers in this worktree.
- The source archive must have SHA-256 `93450657290e09f5f6afd65bdacb229faddca33a9e9bad6d37bbd11f41c492fc` before any member is admitted.
- Preserve historical decisions and old corpus files as history; append overrides and select a new active suite instead of rewriting history.
- Follow one focused RED -> minimum GREEN per behavior. Run a related aggregate only when its bundle closes. Reserve the repository-wide gate for the final candidate.
- Do not hand-edit generated artifact contracts, logical hashes, Parquet, DuckDB, reports, or evaluation observations.
- No live external-data call is permitted at runtime. An external source without exact owner mapping, cutoff-safe provenance, and reuse authority produces `unavailable` coverage.
- No external or derived overseas one-year return is admitted. Never annualize `du_er_1d`.
- Reviews are limited to Critical and Important findings. Allow one correction/re-review wave; later findings are adjudicated under the user's frozen review rule.
- Stage and commit only explicit paths owned by this plan. Never use a broad `git add evaluation`, `git add source_material`, or `git add docs` while user-owned untracked files exist.
- Skip generic provider frameworks, a data lake, a new holdings grain, fuzzy automatic links, and unrelated cleanup.

---

### Task 1: Record official authority and build the archive-admission boundary

**Files:**

- Create: `source_material/official_notices/2026-08-24-data-refresh-and-runtime-rules.md`
- Create: `tests/contract/test_official_data_refresh_contract.py`
- Create: `tools/admit_official_archive.py`
- Create: `tests/contract/test_official_archive_admission.py`
- Modify: `docs/10_DECISION_LOG.md`
- Modify: `docs/superpowers/specs/2026-08-28-official-data-refresh-and-sealed-enrichment-design.md`

**Interfaces:**

- `inspect_archive(archive: Path, *, expected: ArchiveSpec = OFFICIAL_ARCHIVE) -> tuple[AdmittedWorkbook, ...]`
- `admit_archive(archive: Path, target: Path) -> tuple[AdmittedWorkbook, ...]`
- CLI: `python tools/admit_official_archive.py --archive <zip> --check`
- CLI: `python tools/admit_official_archive.py --archive <zip> --target source_material/data --admit`

- [ ] **Step 1: Write the official-override RED**

```python
def test_latest_official_rules_are_versioned_without_rewriting_history() -> None:
    text = (ROOT / "docs/10_DECISION_LOG.md").read_text(encoding="utf-8")
    assert "| D-006 | 2026-08-07 | FROZEN | current = 2026-07-11 snapshot" in text
    assert "2026-08-24 | OFFICIAL_OVERRIDE" in text
    assert "domestic/public=2026-08-22" in text
    assert "overseas=2026-08-23" in text
    assert "du_er_1d" in text and "never annualized" in text
```

Also require explicit rules for unavailable internal code tables, intentional zero/missing display, bond quantity invalidation, delisted/ended exclusion, mandatory HCX intent and wording, and the 295-second outer deadline.

- [ ] **Step 2: Run the focused RED**

```bash
uv run pytest tests/contract/test_official_data_refresh_contract.py -q
```

Expected: fail because the new notice, Q&A, and appended `OFFICIAL_OVERRIDE` rows do not exist.

- [ ] **Step 3: Persist the exact notice/Q&A and append overrides**

Append dated overrides; never edit D-006/D-008/D-012/D-015 or Q-002/Q-003/Q-005 in place. Resolve A-005 with a new dated internal decision: a release manifest is metadata in a child commit, explicitly covers its clean parent candidate commit, and is verified from that Git object; the image/artifact hashes also bind to the covered parent. Correct the approved spec to state:

```text
code-table meanings are not queried or guessed
ended or delisted evidence excludes a bond; absence of both permits the organizer assumption
overseas ETF/ETN 1Y segments are pruned with an explicit limitation
```

Preserve these organizer communications in the notice record as user-transcribed source text, without inventing a URL:

```text
[데이터 관련 공지]
현재 26.07.11 전달드린 데이터는 정합성 및 코드관련 이슈가 있어, 지금 배포드린 데이터 기준으로 활용하시면 됩니다.
(스키마/테이블 정보 X 4개 테이블 총 8개 파일)
(26.08.24일 기준, 영업일 08.22까지 / 해외는 한국시간 23일)

1. 데이터 코드 값 이슈
데이터 내 코드 값에 대해 기본 코드값 정보는 내부 코드관리체계 이슈로 코드 값 테이블을 제공할 수 없으며, 이 부분에 대한 질문은 없을 예정입니다.

2. 데이터 정합성 이슈
데이터 중 0이나 값이 없는 데이터는 의도된 내용이며, 해당 내용을 조회하는 질의에는 값을 빼고 보여주거나 값이 없다고 응답합니다.

3. 추가 데이터 활용 이슈
원하는 데이터를 활용할 수 있으며, 섹터-상품 및 구성종목-상품 등의 지식 구축 데이터 선택은 참가자 자율입니다.

총 35개 질의(상 10 / 중 10 / 하 10 / 답변불가 5)로 평가합니다. 두 개 이상의 상품을 비교/검색하는 교차질의가 있을 수 있습니다. 공시 및 기타 시장데이터는 2026-08-24까지 발행된 자료를 사용할 수 있습니다. BUYABLE_QUANTITY 값은 무효이며, 상장폐지 또는 리스팅 종료를 제외한 종목은 모두 구매가능하다고 가정합니다. 300초 타임아웃은 물리적 미응답 처리이며 300초 미만 응답은 지연에 따라 점수가 차등됩니다. 질의 Intent 분석과 답변 생성에는 NCP HyperCLOVA X가 필수입니다.

[해외 ETF 1년 수익률 Q&A]
해외 ETF는 제공된 du_er_1d만으로 1년 수익률을 산출할 근거가 없으므로, 해외 ETF의 1년 수익률을 묻는 질의는 없을 예정입니다. 구성종목이 포함된 ETF의 1년 수익률 질의가 나오면 해외 ETF를 제외해도 무방합니다.
```

- [ ] **Step 4: Write archive-admission REDs**

```python
def test_archive_admission_keeps_only_the_eight_sealed_root_workbooks(sealed_archive_fixture) -> None:
    admitted = inspect_archive(
        sealed_archive_fixture.archive,
        expected=sealed_archive_fixture.spec,
    )
    assert tuple(item.member for item in admitted) == EXPECTED_MEMBERS
    assert all(not item.member.startswith("__MACOSX/") for item in admitted)


@pytest.mark.parametrize("mutation", ["wrong_hash", "missing", "duplicate", "traversal", "extra"])
def test_archive_admission_fails_closed(tmp_path: Path, mutation: str) -> None:
    archive, expected, error_code = build_archive_fixture(tmp_path, mutation=mutation)
    with pytest.raises(ArchiveAdmissionError) as caught:
        inspect_archive(archive, expected=expected)
    assert caught.value.code == error_code
```

For structural mutations, the fixture specification contains the mutated archive's actual outer SHA but the sealed expected member contract, so the test reaches and proves the intended missing/duplicate/traversal/extra branch. Only `wrong_hash` intentionally fails at the outer hash boundary.

- [ ] **Step 5: Run archive RED and implement the smallest stdlib tool**

```bash
uv run pytest tests/contract/test_official_archive_admission.py -q
```

Use `zipfile`, `hashlib`, `tempfile`, `os.replace`, and existing `tools.xlsx_stream.list_sheet_names`. Unit tests use synthetic archives and an injected sealed fixture specification; CI never depends on the user's Downloads directory. The public CLI is fixed to the official package constants and verifies exact archive hash, member name, size, SHA-256, and `data`/`schema` sheet before staged replacement. The eight sealed workbook facts are:

```text
prbd01n001_data.xlsx    5926563  574ae5d6c1d98704712c256ed5352cbaed065ea9c3a6eb7b2a52adb305fa9001
prbd01n001_schema.xlsx     7863  9965126695066f9dc07951a78054e9e7639b6863d1ad2a9616f7e2d8fcadbc4f
pref01n001_data.xlsx     957630  18c4329d8fc8768d030316816f3e6e48226a3c217db3354245b766a2c6f6c592
pref01n001_schema.xlsx     9022  2135081fd8107760d127915147032987ee1d9e7c2ed039665ae4214b96faec5a
pref02n001_data.xlsx    2102888  ca6a274aeaf3f884f2f7635d7802558bc6dabf408871ecb1f71e5a50d9d34067
pref02n001_schema.xlsx     7294  32ac732f0501f4ab518682175fecc50756ee1eafde9296801f139d62559b5e64
prfd01n001_data.xlsx    9130974  81b3ce3f1d5042b32fd52a76acff094fc5b8dd9fa36289af2fb54c195eb5d94c
prfd01n001_schema.xlsx     8306  cfe7be44cbcd9ce349206776a4eb46996162643acbf3ca5a4f74c2886394862b
```

- [ ] **Step 6: Run GREEN and verify the exact package without cutting over active data**

```bash
uv run pytest tests/contract/test_official_archive_admission.py tests/contract/test_official_data_refresh_contract.py -q
uv run python tools/admit_official_archive.py --archive '/Users/ss020/Downloads/ai-festival2026_금융상품Agent_DtataSet260824.zip' --check
```

Do not replace `source_material/data` in this checkpoint. Cutting over workbooks while the July manifest/catalog remain active would create an unexplained checksum failure. Task 2 performs the workbook, manifest, catalog, and audit cutover in one reviewable transaction.

- [ ] **Step 7: Commit and independent review**

```bash
git add docs/10_DECISION_LOG.md docs/superpowers/specs/2026-08-28-official-data-refresh-and-sealed-enrichment-design.md source_material/official_notices/2026-08-24-data-refresh-and-runtime-rules.md tools/admit_official_archive.py tests/contract/test_official_archive_admission.py tests/contract/test_official_data_refresh_contract.py
git commit -m "chore: record official refresh admission boundary"
```

Review only Task 1's approved authority/admission contract and diff.

---

### Task 2: Atomically migrate workbooks, manifest, catalog, dates, and independent source audit

**Files:**

- Modify: `src/finproof/data/source_manifest.py`
- Replace: `source_material/data/*.xlsx`
- Modify: `src/finproof/core/settings.py`
- Modify: `src/finproof/core/versions.py`
- Modify: `src/finproof/service/orchestrator.py`
- Modify: `config/datasets.yaml`
- Modify: `config/artifact_build.yaml`
- Modify: `config/answer_policy.yaml`
- Modify: `schemas/artifact_manifest.schema.json`
- Modify: `tools/create_input_manifest.py`
- Modify: `tools/extract_schema_catalog.py`
- Modify: `tools/audit_source_data.py`
- Modify: `tools/admit_official_archive.py`
- Modify: `tools/verify_handoff.py`
- Regenerate: `source_material/input_manifest.json`
- Regenerate: `source_material/schema_catalog.json`
- Regenerate: `tests/contracts/expected_source_audit.json`
- Modify: `source_material/README.md`
- Modify: `tests/helpers/source_manifest.py`
- Modify: `tests/helpers/xlsx.py`
- Modify: `tests/helpers/source_rows.py`
- Modify: `tests/source_contract/test_source_manifest.py`
- Modify: `tests/source_contract/test_xlsx_stream.py`
- Modify: `tests/source_contract/test_official_xlsx_lineage.py`
- Modify: `tests/contract/test_handoff_package.py`
- Modify: `tests/contract/test_handoff_commands.py`
- Modify: `tests/unit/core/test_settings.py`
- Modify: `tests/unit/core/test_versions.py`

**Interfaces:**

- `OFFICIAL_DISTRIBUTION_DATE = date(2026, 8, 24)`
- coverage map: domestic bonds/domestic listed/public funds `2026-08-22`; overseas listed `2026-08-23`
- schema sheet columns: `순번`, `컬럼명`, `데이터타입`, `Nullable`, `컬럼코멘트`

- [ ] **Step 1: Write source/date, audit-profile, and rollback REDs**

```python
def test_active_source_contract_is_the_august_distribution() -> None:
    manifest = SourceFileManifest.load(MANIFEST, CATALOG)
    assert manifest.snapshot_date == date(2026, 8, 24)
    assert [(e.table_id, e.expected_rows, e.expected_columns, e.sheet_name) for e in manifest.data_files] == [
        ("PRBD01N001", 21_882, 58, "data"),
        ("PREF01N001", 1_780, 98, "data"),
        ("PREF02N001", 6_037, 49, "data"),
        ("PRFD01N001", 23_676, 75, "data"),
    ]
```

Add settings/version assertions for 2026-08-24 and a lineage assertion that all 53,375 rows retain exact `data` sheet coordinates and source checksums. Before generating any expected audit JSON, hard-code the organizer-package profile in a focused test independently of that JSON. Add a failure-injection test that snapshots every active source/manifest/catalog byte, rejects a bad staged candidate, and proves the active bytes are unchanged.

- [ ] **Step 2: Run focused REDs**

```bash
uv run pytest tests/source_contract/test_source_manifest.py tests/source_contract/test_official_xlsx_lineage.py tests/contract/test_handoff_commands.py tests/unit/core/test_settings.py tests/unit/core/test_versions.py tests/contract/test_official_archive_admission.py -q
```

Expected: old snapshot/date/count/sheet assumptions fail.

- [ ] **Step 3: Build and verify a complete candidate without touching active bytes**

Run the reviewed admission tool against a temporary candidate root, not `source_material/data`. Generate the candidate manifest, catalog, and independent audit from those exact staged bytes; compare each ordered schema column list to the corresponding `data` header and require the hard-coded official profile RED to pass. Keep distribution date separate from coverage/applicable dates. Retire public-fund `attribute_column` and the composite source PK; use `itm_no`.

```bash
finproof_candidate_root="$(mktemp -d /private/tmp/finproof-source-candidate.XXXXXX)"
uv run python tools/admit_official_archive.py --archive '/Users/ss020/Downloads/ai-festival2026_금융상품Agent_DtataSet260824.zip' --target "$finproof_candidate_root/source_material/data" --admit
```

- [ ] **Step 4: Rewrite the independent audit for the replacement schema**

The audit must independently establish at least:

```text
total rows 53,375
bond rows/instruments 21,882 / 20,497; duplicate instruments 1,078
domestic listed rows 1,780; ETF/ETN 1,235 / 545
overseas listed rows 6,037; ETF/ETN 5,972 / 65
public funds rows/unique itm_no 23,676 / 23,676
exact domestic-listed/fund KSD intersection 217 candidates
```

Audit zero/missing distributions without treating them as suspicious and record coverage maxima separately from the package date. `--write-expected` must refuse unless this independent fixed profile passes; it may serialize observed details but cannot define its own acceptance values.

- [ ] **Step 5: Generate all candidate contracts, verify them, then publish once with rollback**

Generate every replaceable source contract under the same candidate root first. Each generator must accept explicit input/output roots and must not fall back to active repository paths in candidate mode:

```bash
uv run python tools/create_input_manifest.py --data-root "$finproof_candidate_root/source_material/data" --output "$finproof_candidate_root/source_material/input_manifest.json"
uv run python tools/extract_schema_catalog.py --schema-root "$finproof_candidate_root/source_material/data" --output "$finproof_candidate_root/source_material/schema_catalog.json"
uv run python tools/audit_source_data.py --source-root "$finproof_candidate_root/source_material" --write-expected "$finproof_candidate_root/tests/contracts/expected_source_audit.json"
uv run python tools/admit_official_archive.py --candidate-root "$finproof_candidate_root" --repo-root . --publish
```

Before `--publish`, validate the candidate archive, ordered schema/header equality, checksums, fixed independent audit profile, candidate manifest/catalog, and handoff-equivalent inventory. `--publish` is the only operation allowed to touch the active `source_material/data`, `source_material/input_manifest.json`, `source_material/schema_catalog.json`, and `tests/contracts/expected_source_audit.json`. Reuse the existing guarded stage/verify/backup/rename/rollback pattern across that exact file set; inject a failure after each publication step and prove every prior active byte is restored. Never publish workbooks and then run a generator against active paths. The Git checkpoint captures this verified publication together with the already prepared code/config/date changes.

Add the explicit rooted generation modes shown above; preserve each tool's existing no-flag and `--check` behavior.

- [ ] **Step 6: Run the focused GREEN bundle**

```bash
uv run pytest tests/source_contract/test_source_manifest.py tests/source_contract/test_xlsx_stream.py tests/source_contract/test_official_xlsx_lineage.py -q
uv run pytest tests/contract/test_handoff_package.py tests/contract/test_handoff_commands.py tests/unit/core/test_settings.py tests/unit/core/test_versions.py -q
uv run python tools/extract_schema_catalog.py --check
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
```

- [ ] **Step 7: Commit and independent review**

```bash
git add src/finproof/core src/finproof/data/source_manifest.py src/finproof/service/orchestrator.py config schemas/artifact_manifest.schema.json tools source_material tests/contracts tests/helpers tests/source_contract tests/contract/test_handoff_package.py tests/contract/test_handoff_commands.py tests/unit/core
git commit -m "feat: migrate official source and date contracts"
```

Do not activate or hand-edit `config/expected_phase1_artifacts.json` in this task.

---

### Task 3: Normalize bond lots and implement the organizer purchaseability rule

**Files:**

- Modify: `src/finproof/domain/bonds.py`
- Modify: `src/finproof/data/normalization/bonds.py`
- Modify: `src/finproof/quality/state.py`
- Modify: `config/state_rules.yaml`
- Modify: `config/field_registry.yaml`
- Modify: `config/metric_registry.yaml`
- Modify: `config/planner_catalog.yaml`
- Modify: `src/finproof/planner/prompts.py`
- Modify: `src/finproof/planner/rule_fallback.py`
- Modify: `src/finproof/query/ast.py`
- Modify: `src/finproof/evidence/builder.py`
- Modify: `tests/helpers/source_rows.py`
- Modify: `tests/unit/data/normalization/test_bonds.py`
- Modify: `tests/unit/quality/test_state_policy.py`
- Modify: `tests/unit/query/test_field_registry.py`
- Create: `tests/unit/query/test_query_ast.py`
- Modify: `tests/unit/query/test_sql_compiler.py`
- Modify: `tests/unit/evidence/test_builder.py`
- Modify: `tests/unit/planner/test_rule_fallback.py`
- Modify: `tests/unit/planner/test_prompts.py`
- Modify: `tests/source_contract/test_official_domestic_normalization.py`

**Interfaces:**

- `BondSaleLot`: exact source-key fields, quote values, raw quantity, and lineage
- `normalize_bond_lot(row: SourceRow) -> NormalizationResult[BondSaleLot]`
- `project_bond_instrument(lots: Sequence[BondSaleLot], *, as_of: date) -> NormalizationResult[BondInstrument]`

- [ ] **Step 1: Write lot/projection REDs**

```python
def test_bond_projection_selects_max_yield_and_same_lot_quote() -> None:
    result = project_bond_instrument((lot(yield_="3.1", price="99"), lot(yield_="4.2", price="97")), as_of=BOUNDARY)
    assert result.record.buy_yield.normalized_value == Decimal("4.2")
    assert result.record.evaluation_price.normalized_value == Decimal("97")


def test_equal_yield_uses_source_key_not_quantity() -> None:
    result = project_bond_instrument((lot(seq="2", quantity="999"), lot(seq="1", quantity="0")), as_of=BOUNDARY)
    assert result.record.selected_lot_key.info_seq == "1"
```

Also cover one parent per `pd_no`, one child per valid source row, equivalent locators, conflicting parent fields, issue-after-boundary, ended/delisted evidence, and missing/sentinel maturity warning.

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/unit/data/normalization/test_bonds.py -q -k 'lot or projection or purchase'
```

- [ ] **Step 3: Implement the minimum grouped projection**

Reuse existing parsers/value/locator models. Preserve `buyable_quantity` only on the lot/raw record; remove it from the parent query projection and every ranking/filter/aggregate/state rule.

- [ ] **Step 4: Write and close registry/state REDs**

```python
def test_buyable_quantity_is_not_queryable(registries) -> None:
    assert "buyable_quantity" not in registries.fields.fields
    assert "bond.buyable_quantity" not in registries.metrics.metrics
```

Add direct REDs proving the validated plan/AST/compiler cannot request or implicitly add quantity, the rule fallback never emits a quantity clause for “구매 가능”, and evidence/state logic never uses raw lot quantity to include, exclude, rank, aggregate, or explain a parent bond. Raw and lot lineage must still preserve the source cell.

```bash
uv run pytest tests/unit/quality/test_state_policy.py tests/unit/query/test_field_registry.py tests/unit/query/test_query_ast.py tests/unit/query/test_sql_compiler.py tests/unit/planner/test_prompts.py tests/unit/planner -q -k 'buyable or purchase or saleable or quantity'
uv run pytest tests/unit/evidence/test_builder.py -q -k 'buyable or purchase or saleable or quantity'
```

- [ ] **Step 5: Run official bond acceptance**

```bash
uv run pytest tests/source_contract/test_official_domestic_normalization.py -q -k bond
```

Assert 21,882 recoverable lots, 20,497 unique parent instruments, 1,078 duplicate groups, and quantity-independent projections.

- [ ] **Step 6: Run bundle aggregate and commit**

```bash
uv run pytest tests/unit/data/normalization/test_bonds.py tests/unit/quality/test_state_policy.py tests/unit/query/test_field_registry.py tests/unit/query/test_query_ast.py tests/unit/query/test_sql_compiler.py tests/unit/planner tests/unit/evidence/test_builder.py tests/source_contract/test_official_domestic_normalization.py -q
git add src/finproof/domain/bonds.py src/finproof/data/normalization/bonds.py src/finproof/quality/state.py src/finproof/planner/prompts.py src/finproof/planner/rule_fallback.py src/finproof/query/ast.py src/finproof/evidence/builder.py config/state_rules.yaml config/field_registry.yaml config/metric_registry.yaml config/planner_catalog.yaml tests/helpers/source_rows.py tests/unit/data/normalization/test_bonds.py tests/unit/quality/test_state_policy.py tests/unit/query/test_field_registry.py tests/unit/query/test_query_ast.py tests/unit/query/test_sql_compiler.py tests/unit/planner tests/unit/evidence/test_builder.py tests/source_contract/test_official_domestic_normalization.py
git commit -m "feat: normalize bond sale lots and purchaseability"
```

- [ ] **Step 7: Independent review and bounded correction if required**

Review selection/tie/source-fidelity/state behavior only.

---

### Task 4: Migrate domestic and overseas listed-product normalization

**Files:**

- Modify: `src/finproof/domain/domestic_listed.py`
- Modify: `src/finproof/domain/overseas_listed.py`
- Modify: `src/finproof/data/normalization/domestic_listed.py`
- Modify: `src/finproof/data/normalization/overseas_listed.py`
- Modify: `config/metric_registry.yaml`
- Modify: `config/quality_rules.yaml`
- Modify: `config/answer_policy.yaml`
- Modify: `src/finproof/quality/metric_policy.py`
- Modify: `src/finproof/quality/pipeline.py`
- Modify: `src/finproof/evidence/builder.py`
- Modify: `src/finproof/answer/renderer.py`
- Modify: `tests/helpers/source_rows.py`
- Modify: `tests/unit/data/normalization/test_domestic_listed.py`
- Modify: `tests/unit/data/normalization/test_overseas_listed.py`
- Modify: `tests/unit/quality/test_metric_operation_policy.py`
- Modify: `tests/unit/quality/test_pipeline_order.py`
- Modify: `tests/unit/evidence/test_builder.py`
- Modify: `tests/unit/answer/test_renderer.py`
- Modify: `tests/source_contract/test_official_domestic_normalization.py`
- Modify: `tests/source_contract/test_official_overseas_public_normalization.py`

- [ ] **Step 1: Write domestic-listed REDs**

Require all mapped wrappers to bind the new 98-column header, preserve differing field dates, treat tracking error and one-year return as ordinary varying metrics, and retain plain ETF/ETN discrimination.

```bash
uv run pytest tests/unit/data/normalization/test_domestic_listed.py -q
```

- [ ] **Step 2: Implement domestic listed mapping and run GREEN**

Reuse the current model/normalizer; add or remove only fields changed by the new catalog. Delete old constant-zero policy branches for refreshed metrics.

- [ ] **Step 3: Write overseas-listed REDs**

Require all 49 columns, varying `du_er_1d`, exact source currency, and separate `du_*`/`cu_*`/`wu_*` applicable dates. Do not add `return_1y`.

```bash
uv run pytest tests/unit/data/normalization/test_overseas_listed.py -q
```

- [ ] **Step 4: Implement overseas mapping and run GREEN**

```bash
uv run pytest tests/unit/data/normalization/test_overseas_listed.py tests/unit/quality/test_metric_operation_policy.py -q
```

- [ ] **Step 5: Write and close intentional zero/missing operation REDs**

For each refreshed metric policy affected by the notice, add focused cases proving: display omits or explicitly labels unavailable; filter and rank exclude missing without converting it to zero; an actual recorded zero follows that metric's declared zero policy; aggregation reports included/excluded counts and never imputes missing as zero; and every material omission/partial comparison universe produces a bound limitation. Remove only old snapshot-specific constant-zero/dual-lens branches invalidated by the new data.

```bash
uv run pytest tests/unit/quality/test_metric_operation_policy.py tests/unit/quality/test_pipeline_order.py tests/unit/evidence/test_builder.py tests/unit/answer/test_renderer.py -q -k 'zero or missing or unavailable or included_count or limitation'
```

- [ ] **Step 6: Run official source acceptance and aggregate**

```bash
uv run pytest tests/source_contract/test_official_domestic_normalization.py -q -k listed
uv run pytest tests/source_contract/test_official_overseas_public_normalization.py -q -k overseas
uv run pytest tests/unit/data/normalization/test_domestic_listed.py tests/unit/data/normalization/test_overseas_listed.py tests/unit/quality/test_metric_operation_policy.py -q
```

- [ ] **Step 7: Commit and independent review**

```bash
git add src/finproof/domain/domestic_listed.py src/finproof/domain/overseas_listed.py src/finproof/data/normalization/domestic_listed.py src/finproof/data/normalization/overseas_listed.py src/finproof/quality/metric_policy.py src/finproof/quality/pipeline.py src/finproof/evidence/builder.py src/finproof/answer/renderer.py config/metric_registry.yaml config/quality_rules.yaml config/answer_policy.yaml tests/helpers/source_rows.py tests/unit/data/normalization/test_domestic_listed.py tests/unit/data/normalization/test_overseas_listed.py tests/unit/quality/test_metric_operation_policy.py tests/unit/quality/test_pipeline_order.py tests/unit/evidence/test_builder.py tests/unit/answer/test_renderer.py tests/source_contract/test_official_domestic_normalization.py tests/source_contract/test_official_overseas_public_normalization.py
git commit -m "feat: migrate refreshed listed-product normalization"
```

---

### Task 5: Replace public-fund attribute rows with item-level attributes

**Files:**

- Modify: `src/finproof/domain/public_funds.py`
- Modify: `src/finproof/data/normalization/public_funds.py`
- Modify: `tests/helpers/source_rows.py`
- Modify: `tests/unit/domain/test_task4_contracts.py`
- Modify: `tests/unit/data/normalization/test_public_funds.py`
- Modify to assert retirement without losing regression coverage: `tests/unit/data/normalization/test_public_fund_collapse.py`
- Modify to assert retirement without losing regression coverage: `tests/unit/data/normalization/test_public_fund_group_adapter.py`
- Modify: `tests/source_contract/test_official_overseas_public_normalization.py`

**Interface:**

- `normalize_public_fund_item(row: SourceRow) -> NormalizationResult[PublicFundItem]`
- `attribute_codes: tuple[str, ...]`, parsed from comma-separated `prfd_attr_cds`
- `attribute_count` cross-checked with `prfd_attr_cnt`
- `attribute_search_text` preserved with lineage

- [ ] **Step 1: Write item-attribute REDs**

```python
def test_public_fund_attributes_are_item_properties() -> None:
    result = normalize_public_fund_item(fund_row(prfd_attr_cds="C101,V101,D102", prfd_attr_cnt="3"))
    assert result.record.attribute_codes == ("C101", "V101", "D102")
    assert result.record.attribute_count.normalized_value == 3


def test_empty_attribute_list_and_zero_count_are_valid() -> None:
    result = normalize_public_fund_item(fund_row(prfd_attr_cds="", prfd_attr_cnt="0"))
    assert result.record.attribute_codes == ()
    assert result.issues == ()
```

Add count-mismatch and no-duplicate-item tests. Preserve token text, order, duplicates, and lineage exactly after comma splitting; duplicate tokens do not become duplicate products. Do not validate an invented token grammar or infer any code meaning. Reject syntax only if the admitted official schema explicitly defines it.

```python
def test_attribute_codes_are_opaque_and_never_inferred() -> None:
    result = normalize_public_fund_item(fund_row(prfd_attr_cds="opaque,opaque,X?", prfd_attr_cnt="3"))
    assert result.record.attribute_codes == ("opaque", "opaque", "X?")
    assert not hasattr(result.record, "attribute_meanings")
```

- [ ] **Step 2: Run RED and implement direct item normalization**

```bash
uv run pytest tests/unit/data/normalization/test_public_funds.py tests/unit/domain/test_task4_contracts.py -q
```

Remove the old group/collapse production path only after the direct item tests are green. Retain the two historical test modules as explicit regressions proving the retired API cannot recreate duplicate product rows.

- [ ] **Step 3: Run official acceptance**

```bash
uv run pytest tests/source_contract/test_official_overseas_public_normalization.py -q -k public
```

Assert 23,676 source rows produce 23,676 unique `itm_no` items and no expanded fund-attribute product rows.

- [ ] **Step 4: Run aggregate, remove only the retired production path, and rerun retained retirement regressions**

```bash
uv run pytest tests/unit/data/normalization/test_public_funds.py tests/unit/data/normalization/test_public_fund_collapse.py tests/unit/data/normalization/test_public_fund_group_adapter.py tests/unit/domain/test_task4_contracts.py tests/source_contract/test_official_overseas_public_normalization.py -q
```

- [ ] **Step 5: Commit and independent review**

```bash
git add src/finproof/domain/public_funds.py src/finproof/data/normalization/public_funds.py tests/helpers/source_rows.py tests/unit/domain/test_task4_contracts.py tests/unit/data/normalization tests/source_contract/test_official_overseas_public_normalization.py
git commit -m "feat: normalize refreshed public-fund items"
```

---

### Task 6: Migrate official artifact tables and exact links without a duplicate full build

**Files:**

- Modify: `config/artifact_build.yaml`
- Modify: `src/finproof/core/versions.py`
- Modify: `src/finproof/data/artifacts/table_specs.py`
- Modify: `src/finproof/data/artifacts/serialization.py`
- Modify: `src/finproof/data/artifacts/silver.py`
- Modify: `src/finproof/data/artifacts/staging.py`
- Modify: `src/finproof/data/artifacts/reports.py`
- Modify: `src/finproof/data/artifacts/config.py`
- Modify: `src/finproof/data/artifacts/builder.py`
- Modify: `src/finproof/data/artifacts/manifest.py`
- Modify: `src/finproof/data/artifacts/expected_contract.py`
- Modify: `src/finproof/data/artifacts/links.py`
- Modify: `schemas/artifact_manifest.schema.json`
- Modify: `tests/helpers/artifacts.py`
- Modify: `tests/unit/core/test_versions.py`
- Leave inactive until Task 7's final relation inventory is ready: `config/expected_phase1_artifacts.json`
- Modify: artifact unit/integration/source-contract tests under their existing paths

**Table delta:** add `silver_bond_sale_lot`; remove `silver_fund_item_attribute`; retain three Bronze tables, four native product tables, quality, and the two exact-link tables.

**Build-config delta:** Task 2 migrated only the admitted source dimensions. Task 6 owns the output half of `artifact_build.yaml` and its frozen in-code mirror. The refreshed native counts are exactly 21,882 bond lots, 20,497 bond instruments, 1,779 domestic listed products, 6,037 overseas listed products, 23,676 fund items, and one quarantined source row. The version bundle and artifact config must use the already admitted registry versions `quality=1.1.0` and `state=1.2.0`; no fixture or loader may retain the prior `1.0.0`/`1.1.0` pair. Replace the old exact-link output golden (`links`, `evidence`, and `pair_sha256`) with one input-side `exact_link_candidate_limit: 217`. This value is the independently audited exact-intersection ceiling, not an expected Gold row count. The immutable evidence ceiling is derived as 434 because each accepted pair has exactly one left and one right direct-cell record; callers cannot widen either ceiling. The exact-only builder must accept any valid result at or below the ceiling and return the observed count/hash. Only Task 7's generated expected artifact contract may turn those observed values into release acceptance values.

- [ ] **Step 1: Write build-config, table, and serialization REDs**

```python
def test_refreshed_build_config_separates_input_ceiling_from_output_goldens() -> None:
    config = load_repository_artifact_build_config()
    assert config.silver_counts.model_dump() == {
        "bond_sale_lot": 21_882,
        "bond_instrument": 20_497,
        "domestic_listed_product": 1_779,
        "overseas_listed_product": 6_037,
        "fund_item": 23_676,
    }
    assert config.quarantine_source_rows == 1
    assert config.exact_link_candidate_limit == 217
    assert not hasattr(config, "exact_links")


def test_version_bundle_matches_admitted_quality_and_state_registries() -> None:
    versions = VersionBundle()
    assert versions.quality_rule_version == "1.1.0"
    assert versions.state_rule_version == "1.2.0"


def test_refreshed_silver_inventory_contains_lots_not_fund_attribute_rows() -> None:
    names = tuple(spec.name for spec in TABLE_SPECS)
    assert "silver_bond_sale_lot" in names
    assert "silver_fund_item_attribute" not in names
```

Prove `record_json` round trips every lot and item field with exact lineage.

- [ ] **Step 2: Run RED and implement table specs/serialization**

```bash
uv run pytest tests/unit/core/test_versions.py tests/unit/data/artifacts/test_foundations.py tests/unit/data/artifacts/test_table_specs.py tests/unit/data/artifacts/test_serialization.py -q -k 'version or artifact_build_config or refreshed or round_trip'
```

- [ ] **Step 3: Write and close staged-emitter REDs**

Stage bond rows by parent ID/source key, emit every lot plus one parent, and emit one fund item per source row. Reuse the existing bounded staging custody instead of creating another storage layer.

```bash
uv run pytest tests/unit/data/artifacts/test_silver.py tests/unit/data/artifacts/test_staging.py tests/integration/artifacts/test_silver_fixture_build.py -q
```

- [ ] **Step 4: Regenerate exact links through the exact-only algorithm**

Use direct fund-item `ksd_itm_no` evidence. Rewrite the official source-profile test as a fast independent exact-untrimmed ETF/fund pair-set scan that proves exactly 217 pairs, zero ETN pairs, and zero one-to-many conflicts; it must not call the artifact builder. Bounded fixtures prove algorithmic conservation: every admitted candidate produces exactly one link and two direct-cell evidence rows, with no drop or duplication. The production builder uses 217 only as a closed upper bound, never an output equality check, returns observed link/evidence counts and the canonical pair hash, and rejects one-to-many conflicts.

Apply the same immutable ceilings to candidate production, reopened relation verification, linked-ID filtering, relation accumulation, and telemetry/report validation. Focused boundary tests must accept 217 links and 434 evidence rows, reject 218 or 435, and prove no caller-controlled widening. Reports must not label observed outputs as predeclared expectations; Task 7 compares the sole official A/B build's emitted pair set to the independently scanned pair set before generating the expected contract.

```bash
uv run pytest tests/unit/data/artifacts/test_exact_links.py tests/source_contract/test_official_exact_link_profile.py tests/integration/artifacts/test_link_evidence_fixture.py -q
```

- [ ] **Step 5: Verify the migrated official inventory with bounded fixture candidates**

Use existing fixture builders to prove the new lot/item/link inventory, logical hashing, Parquet, and DuckDB contracts without running the multi-hour official build. Do not generate or activate `config/expected_phase1_artifacts.json` yet; Task 7 adds the final two relations and owns the single official candidate pair.

- [ ] **Step 6: Run official artifact acceptance**

```bash
uv run pytest tests/integration/artifacts/test_silver_fixture_build.py tests/integration/artifacts/test_artifact_equality.py tests/integration/artifacts/test_artifact_duckdb.py -q
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
```

- [ ] **Step 7: Commit and independent review**

```bash
git add config/artifact_build.yaml src/finproof/core/versions.py src/finproof/data/artifacts schemas/artifact_manifest.schema.json tests/helpers/artifacts.py tests/unit/core/test_versions.py tests/unit/data/artifacts tests/integration/artifacts tests/source_contract/test_official_exact_link_profile.py
git commit -m "feat: migrate refreshed artifact contracts"
```

---

### Task 7: Add sealed holdings and coverage relations

**Files:**

- Create: `src/finproof/data/holdings.py`
- Create: `tests/unit/data/test_holdings.py`
- Create: `source_material/external/README.md`
- Modify: `src/finproof/data/artifacts/expected_contract.py`
- Modify: `src/finproof/data/artifacts/table_specs.py`
- Modify: `src/finproof/data/artifacts/serialization.py`
- Modify: `src/finproof/data/artifacts/silver.py`
- Modify: `src/finproof/data/artifacts/builder.py`
- Modify: `schemas/artifact_manifest.schema.json`
- Modify: artifact tests for the two relations

**Interfaces:**

- `HoldingCoverageState = complete | partial_top_10 | unavailable`
- `HoldingRecord` and `HoldingCoverageRecord` strict models
- `admit_holding_snapshot(...) -> HoldingGeneration`

- [x] **Step 1: Write admission/coverage REDs**

```python
def test_partial_coverage_allows_positive_match_but_not_negative_claim() -> None:
    generation = admitted_generation(state="partial_top_10", holdings=(holding("KR7005930003"),))
    assert generation.can_support_positive("KR7005930003")
    assert not generation.can_support_absence("KR7006600007")
```

Reject nonexact owner links, cutoff-late records, missing URL/hash/reuse basis, contradictory or falsely declared unit metadata, and declared generation count/hash drift. Preserve an unknown unit as unknown with lineage and a quality state; never guess, convert, rank, or aggregate it as a known unit.

- [x] **Step 2: Run RED and implement the two strict records**

```bash
uv run pytest tests/unit/data/test_holdings.py -q
```

For product types without an admitted generation, emit explicit `unavailable` coverage rows. Do not fabricate holdings.

- [x] **Step 3: Add only the two artifact relations**

```bash
uv run pytest tests/unit/data/artifacts/test_table_specs.py tests/unit/data/artifacts/test_serialization.py tests/unit/data/artifacts/test_silver.py tests/unit/data/artifacts/test_manifest.py tests/integration/artifacts/test_artifact_duckdb.py -q -k holding
```

Update the manifest schema and expected-contract validator from Task 6's 11-table intermediate inventory to the final 13-table inventory in this same RED/GREEN slice.

- [x] **Step 4: Build the single official candidate pair, seal the expected contract, and run the official aggregate**

Use the repository's existing candidate builder/publication flow. Candidate A and B use distinct injected UTC timestamps and must produce identical logical contract bytes. Reuse the Task 6 independent source scan without launching another artifact build, and require each candidate's exact emitted pair set to equal that scanned 217-pair set before expected-contract generation. This is the conservation bridge that detects a dropped or substituted candidate while keeping 217 out of the build config's output golden. Generate `config/expected_phase1_artifacts.json` only from the pair-set-checked, verified final 13-table inventory. Any source with unresolved reuse permission remains unavailable; this does not block official-only queries or artifact publication.

```bash
uv run pytest tests/source_contract/test_official_artifact_build.py tests/source_contract/test_official_exact_link_profile.py tests/integration/artifacts/test_artifact_equality.py tests/integration/artifacts/test_artifact_duckdb.py -q
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
```

- [x] **Step 5: Commit and independent review**

```bash
git add src/finproof/data/holdings.py src/finproof/data/artifacts schemas/artifact_manifest.schema.json source_material/external tests/unit/data tests/unit/data/artifacts tests/integration/artifacts config/expected_phase1_artifacts.json
git commit -m "feat: add sealed holdings coverage"
```

---

### Task 8: Add constituent filtering, coverage evidence, and overseas 1Y pruning

**Implementation gate:** This Task changes public validation, execution, evidence, and
dependency-construction contracts. Obtain an independent plan review reporting
`Critical 0 / Important 0` on this corrected Task before writing any RED or modifying
production code.

**Files:**

- Modify: `config/field_registry.yaml`
- Modify: `config/planner_catalog.yaml`
- Modify: `src/finproof/entity/__init__.py`
- Modify: `src/finproof/entity/models.py`
- Create: `src/finproof/entity/holding_resolver.py`
- Modify: `src/finproof/query/fields.py`
- Modify: `src/finproof/query/semantic_validator.py`
- Modify: `src/finproof/query/segmenter.py`
- Modify: `src/finproof/query/ast.py`
- Modify: `src/finproof/query/compiler.py`
- Modify: `src/finproof/domain/execution.py`
- Modify: `src/finproof/domain/evidence.py`
- Modify: `src/finproof/storage/repositories/evidence.py`
- Modify: `src/finproof/quality/pipeline.py`
- Modify: `src/finproof/evidence/builder.py`
- Modify: `src/finproof/evidence/serializer.py`
- Modify: `src/finproof/evidence/verifier.py`
- Modify: `src/finproof/answer/renderer.py`
- Modify: `src/finproof/api/dependencies.py`
- Modify: `src/finproof/planner/service.py`
- Modify: `src/finproof/planner/prompts.py`
- Modify: `src/finproof/service/answer_service.py`
- Modify: `src/finproof/cli/evaluate.py`
- Modify: `src/finproof/evaluation/ablation_experiment.py`
- Create: `tests/unit/entity/test_holding_resolution.py`
- Modify: `tests/unit/query/test_field_registry.py`
- Modify: `tests/unit/query/test_semantic_validator.py`
- Modify: `tests/unit/query/test_execution_bundle.py`
- Modify: `tests/unit/query/test_sql_compiler.py`
- Modify: `tests/security/test_query_injection.py`
- Create: `tests/integration/query/test_holding_executor.py`
- Create: `tests/integration/query/test_cross_product_holding_query.py`
- Modify: `tests/integration/query/test_executor.py`
- Modify: `tests/integration/planner/test_planner_service.py`
- Modify: `tests/integration/service/test_answer_service.py`
- Modify: `tests/integration/api/test_answer_endpoint.py`
- Modify: `tests/contract/test_runtime_registry_resources.py`
- Modify: `tests/unit/cli/test_evaluate.py`
- Modify: `tests/unit/evaluation/test_ablation.py`
- Modify: `tests/unit/planner/test_prompts.py`
- Modify: `tests/unit/quality/test_pipeline_order.py`
- Modify: `tests/unit/registry/test_registry_loader.py`
- Modify: `tests/unit/domain/test_evidence_models.py`
- Modify: `tests/unit/evidence/test_builder.py`
- Create: `tests/unit/evidence/test_serializer.py`
- Modify: `tests/unit/evidence/test_claim_verifier.py`
- Modify: `tests/unit/answer/test_renderer.py`

**Interfaces:**

- `HoldingResolutionCandidate` preserves `constituent_identifier`,
  `constituent_identifier_type`, and `display_name` from the admitted snapshot.
- `HoldingResolutionResult` contains one optional selected candidate and at most five
  deterministic candidates.
- `ResolutionBundle` retains the existing product-entity `results` and adds the separate
  typed field `holding_constituent: HoldingResolutionResult | None = None`. The default
  keeps unrelated existing constructors source-compatible. If a plan contains a
  `holding_constituent` filter, every production construction boundary must supply a
  resolver, and semantic validation rejects `None`, unresolved, multiple, or malformed
  holding resolution. A holding result never enters the product-entity result tuple.
- `HoldingConstituentFilter` is a small strict frozen model containing both
  `constituent_identifier` and `constituent_identifier_type`.
  `ExecutionSegment.holding_constituent_filter: HoldingConstituentFilter | None = None`
  carries it independently from scalar `filters` while preserving unrelated constructors.
- `ExecutionLimitationCode(StrEnum)` is a closed code set containing only
  `OVERSEAS_RETURN_1Y_UNAVAILABLE = "overseas_return_1y_unavailable"` in this Task.
  `ExecutionBundle.limitations: tuple[ExecutionLimitationCode, ...] = ()` passes unchanged
  to `PolicyExecutionResult.limitations: tuple[ExecutionLimitationCode, ...] = ()`.
  `EvidenceBuilder` maps the code to one fixed reviewed answer phrase; the enum contains no
  display text and this Task creates no generic warning or limitation model.
- `EvidenceBundle` adds bounded
  `holding_records: tuple[HoldingRecordEvidenceRef, ...] = ()` and
  `holding_coverage: tuple[HoldingCoverageEvidenceRef, ...] = ()`. Defaults preserve
  unrelated constructors. These references bind already validated canonical holding and
  coverage records; they do not create a generic evidence framework.

**Contract:** The field registry fixes `holding_constituent` product applicability to
exactly `domestic_etf`, `domestic_etn`, `overseas_etf`, `overseas_etn`, and `public_fund`
and declares only the `eq` operator. One plan contains either zero or exactly one
`holding_constituent` filter; semantic validation rejects two or more. If the filter is
present and `product_types` contains `domestic_bond` anywhere, reject the whole plan. Do
not silently prune the bond segment or execute it unfiltered. `FieldRegistry` has one
explicit special case for this relation field and does not create native-table projections
for it; do not add a generic relation registry or compiler framework.

Resolution order is exact admitted constituent identifier, unique normalized exact name,
otherwise bounded clarification. An exact identifier string selects only when it maps to
exactly one distinct `(constituent_identifier, constituent_identifier_type)` pair. The
same identifier string under different identifier types is ambiguous and never selects
automatically. Only repeated rows for the same pair are deduplicated. A normalized exact
name likewise selects only when all matches reduce to one distinct identifier/type pair;
otherwise return deterministic bounded ambiguity with at most five candidates. Fuzzy
similarity never selects a constituent.

Each selected native product segment among the five allowed holding product types compiles
independently to one parameterized correlated
`EXISTS` against `silver_product_holding`. It exactly correlates
`owner_product_type` and the outer native owner product ID and binds both
`constituent_identifier` and `constituent_identifier_type`. It never interpolates values
or unions incompatible product tables. The relation is absent from
`ExecutionSegment.filters`, native projections, and policy scalar filters. ETN segments
retain the predicate and therefore return zero rows under unavailable coverage instead of
silently returning unfiltered products.

Adding the field increments `field_registry.yaml` from the Task 7 issued version to
`1.3.0`. `planner_catalog.yaml` increments to `1.2.0` and adds the exact aliases
`구성종목`, `보유종목`, and `편입종목` for `holding_constituent`. The planner prompt increments
to `phase4-planner-v3` and instructs HCX to emit these phrases as one scalar `eq`
`holding_constituent` filter, never as a product entity, tuple, fuzzy match, sort, or
aggregation. It permits that filter only for the five allowed holding product types,
emits it at most once, and never combines it with `domestic_bond`. Repository,
editable-install, and clean-wheel runtime resources must expose the same reviewed registry
bytes and issued versions.

- [x] **Step 1: Write resolver, registry, semantic, and construction-boundary REDs**

```python
from finproof.domain.query_plan import FilterOperator
from finproof.query.fields import FieldRegistry as QueryFieldRegistry
from finproof.registry.loader import RegistryBundle


def test_holding_constituent_supports_only_eq_without_native_projection() -> None:
    registries = RegistryBundle.from_package()
    field = registries.fields.entries["holding_constituent"]
    assert field.operators == (FilterOperator.EQ,)
    query_fields = QueryFieldRegistry.from_bundle(registries)
    assert all(
        key[0] != "holding_constituent" for key in query_fields.projections
    )
```

Add focused tests proving an exact identifier selects only one distinct identifier/type
pair, repeated rows deduplicate only for that same pair, the same identifier string under
different identifier types remains ambiguous, a normalized exact name selects only one
distinct pair, and every multi-pair ambiguity is deterministic and bounded to five
candidates. Also prove no fuzzy automatic selection and unresolved behavior over the
official zero-row holding relation. Semantic REDs prove exact applicability to the five
allowed holding product types, zero-or-one filter cardinality, rejection of two filters,
and whole-plan rejection whenever a holding filter and `domestic_bond` coexist. They also
prove a holding query rejects missing, unresolved, multiple, and malformed resolution
while unrelated queries remain source-compatible through the `None` default. Caller REDs
prove `api/dependencies.py`, `planner/service.py`,
`service/answer_service.py`, `cli/evaluate.py`, and
`evaluation/ablation_experiment.py` all construct or receive the holding resolver and pass
the separate typed resolution. Registry/prompt REDs prove the `1.3.0` field registry,
`1.2.0` planner catalog, three exact aliases, scalar `eq` relation-filter instruction,
five-type applicability, at-most-one/bond-exclusion prompt rules,
`phase4-planner-v3` identity/checksum, and repository/package resource equality. The
clean-wheel install test is reserved for the single Step 9 aggregate.

Run the REDs separately and record the expected failures: the holding types, resolver,
relation-field special case, typed bundle field, and production wiring do not exist.

```bash
uv run pytest tests/unit/entity/test_holding_resolution.py tests/unit/query/test_field_registry.py tests/unit/query/test_semantic_validator.py -q
uv run pytest tests/unit/registry/test_registry_loader.py tests/unit/planner/test_prompts.py -q -k 'holding or alias or version or checksum'
uv run pytest tests/contract/test_runtime_registry_resources.py::test_repository_and_package_registry_bytes_are_identical -q
uv run pytest tests/integration/planner/test_planner_service.py tests/integration/service/test_answer_service.py tests/integration/api/test_answer_endpoint.py tests/unit/cli/test_evaluate.py tests/unit/evaluation/test_ablation.py -q -k holding
```

- [x] **Step 2: Implement the minimum resolver, registry exception, and caller wiring**

Reuse `normalize_product_text` from `src/finproof/entity/normalization.py`, the
deterministic ordering used by `EntityResolver`, and
the existing runtime-session query pattern. Export the resolver and types through
`entity/__init__.py`. Add only the explicit `holding_constituent` projection exception.
Increment the two registry versions, add only the three reviewed holding aliases, and
update the closed planner rule and prompt identity so HCX emits one scalar `eq` relation
filter rather than a product entity.
Wire one holding resolver through every listed production constructor. Require it only
when the plan contains the relation filter; semantic validation converts the selected
candidate into a strict `HoldingConstituentFilter` and rejects every unresolved shape.

```bash
uv run pytest tests/unit/entity/test_holding_resolution.py tests/unit/query/test_field_registry.py tests/unit/query/test_semantic_validator.py -q
uv run pytest tests/unit/registry/test_registry_loader.py tests/unit/planner/test_prompts.py -q -k 'holding or alias or version or checksum'
uv run pytest tests/contract/test_runtime_registry_resources.py::test_repository_and_package_registry_bytes_are_identical -q
uv run pytest tests/integration/planner/test_planner_service.py tests/integration/service/test_answer_service.py tests/integration/api/test_answer_endpoint.py tests/unit/cli/test_evaluate.py tests/unit/evaluation/test_ablation.py -q -k holding
```

- [x] **Step 3: Write relation-separation and SQL/security REDs**

```python
def test_holding_filter_compiles_parameterized_exists(compiler, segment) -> None:
    compiled = compiler.compile(segment)
    assert "EXISTS" in compiled.sql
    assert "silver_product_holding" in compiled.sql
    assert "삼성전자" not in compiled.sql
    assert compiled.parameters[-2:] == ("KR7005930003", "ISIN")
```

Prove the typed relation is absent from scalar filters and native projections, the policy
engine never reapplies it as a row-value predicate, and the compiler exactly constrains
owner type, outer owner ID, constituent identifier, and identifier type. Prove injected
payloads appear only in parameters, no union is emitted, and ETN retains `EXISTS` and
returns no rows rather than becoming unfiltered.

Run RED and record the expected failures: `ExecutionSegment` has no typed relation and the
compiler emits no four-part holding correlation.

```bash
uv run pytest tests/unit/query/test_execution_bundle.py tests/unit/query/test_sql_compiler.py tests/security/test_query_injection.py tests/integration/query/test_holding_executor.py tests/unit/quality/test_pipeline_order.py -q
```

- [x] **Step 4: Implement the minimum typed relation and correlated `EXISTS`**

Add `HoldingConstituentFilter` and carry it only on `ExecutionSegment`. Exclude the
relation from `QueryAst` native projection collection, ordinary filter compilation,
policy scalar matching, and ordinary evidence field lookup. Reuse closed table specs,
native owner-ID projections, and deterministic parameter ordering; do not introduce a
generic relation abstraction.

```bash
uv run pytest tests/unit/query/test_execution_bundle.py tests/unit/query/test_sql_compiler.py tests/security/test_query_injection.py tests/integration/query/test_holding_executor.py tests/unit/quality/test_pipeline_order.py -q
```

- [x] **Step 5: Write and close overseas 1Y limitation transport RED**

For a domestic ETF + overseas ETF + public-fund `return_1y` plan, preserve the compatible
domestic ETF/public-fund global rank, omit the overseas segment, and create a typed
`ExecutionLimitationCode.OVERSEAS_RETURN_1Y_UNAVAILABLE`. Prove it travels without loss
through `ExecutionBundle`,
`PolicyExecutionResult`, `EvidenceBuilder`, serializer, renderer, and verifier. A single
overseas-only one-year request remains unsupported.

Run RED and record the expected failures: the overseas segment is retained without a
metric, and no typed execution limitation path exists. Implement only
the closed enum value, default-empty pass-through tuples, its fixed reviewed answer-text
mapping, and the pruning rule; do not create a generic warning or limitation model.

```bash
uv run pytest tests/unit/query/test_execution_bundle.py tests/integration/query/test_executor.py tests/unit/quality/test_pipeline_order.py tests/unit/evidence/test_builder.py tests/unit/evidence/test_serializer.py tests/unit/answer/test_renderer.py tests/unit/evidence/test_claim_verifier.py -q -k 'overseas and return_1y'
```

- [x] **Step 6: Write holding/coverage evidence and snapshot REDs**

Add focused REDs proving each positive owner binds official owner evidence, exact owner
crosswalk, one or more canonical holding rows, the exact owner coverage row, displayed
metric evidence, rank/partition facts, and artifact/registry versions. For every positive
owner, reparse canonical `record_json` through the existing `HoldingRecord` and
`HoldingCoverageRecord` models and reject owner, identifier, generation, source, or count
mismatches.

For an unavailable product type that returns no product row, require one bounded coverage
summary containing product type, `unavailable` state, and official owner count. This
summary grounds the material limitation without inventing a negative holding fact. Prove
partial coverage means “rank among evidenced positive matches,” and partial/unavailable
coverage cannot yield a negative or exhaustive claim. Prove serializer exposes the typed
references in `retrieved_context` only as explicit bounded `evidence_context.v3`. For an
evidence bundle with empty holding/coverage references, serialization must remain
byte-identical `evidence_context.v2`. Existing evaluation artifacts and goldens are not
modified. Renderer and verifier require matching evidence or coverage-summary IDs only for
new holding candidate/rank claims and new holding/coverage/overseas-pruning material
limitations; this Task does not retroactively redesign unrelated existing limitations.

Add a focused RED asserting the builder reuses the already issued
`answer_policy.yaml` `snapshot_assumption` value and never owns a new snapshot literal.
Record the expected failures: `EvidenceBundle` lacks the bounded defaulted references,
the serializer has no v3 branch, and the builder still owns the obsolete snapshot string.

```bash
uv run pytest tests/unit/domain/test_evidence_models.py tests/unit/evidence/test_builder.py tests/unit/evidence/test_serializer.py tests/unit/evidence/test_claim_verifier.py tests/unit/answer/test_renderer.py -q -k 'holding or coverage or snapshot'
```

- [x] **Step 7: Implement the minimum typed evidence binding**

Add bounded, default-empty `HoldingRecordEvidenceRef` and
`HoldingCoverageEvidenceRef` tuples to `EvidenceBundle`. Reuse canonical holding models,
existing evidence IDs, summaries, version hashes, and material-limitation enforcement.
Emit v3 only when either new reference tuple is non-empty; otherwise preserve the exact v2
payload bytes. Expose only these fields through the existing serializer and scoped
renderer/verifier paths. Load the snapshot assumption from the issued answer-policy
registry instead of hardcoding a replacement string. Do not introduce a second evidence
graph or duplicate holding schema.

```bash
uv run pytest tests/unit/domain/test_evidence_models.py tests/unit/evidence/test_builder.py tests/unit/evidence/test_serializer.py tests/unit/evidence/test_claim_verifier.py tests/unit/answer/test_renderer.py -q -k 'holding or coverage or snapshot'
```

- [x] **Step 8: Write and close the synthetic cross-product E2E RED**

The official contract remains exactly zero `silver_product_holding` rows and 31,492
`silver_product_holding_coverage` rows. Do not rebuild or modify the official artifacts,
expected counts, evaluation artifacts, or goldens. Use one bounded synthetic runtime
fixture containing a domestic ETF positive partial match, a public-fund positive partial
match, and unavailable domestic ETN coverage.

Run two organizer-shaped requests through that fixture. The constituent request proves
independent domestic ETF, public-fund, and domestic ETN native-grain segments, one
four-part parameterized correlated `EXISTS` per segment, no incompatible union, and
domestic ETN zero-row fail-closed coverage evidence. The mixed `return_1y` request proves
the domestic ETF and public-fund positive partial matches form the actual compatible
global one-year rank while the overseas ETF segment is pruned with
`OVERSEAS_RETURN_1Y_UNAVAILABLE`. Both requests prove partial/unavailable coverage never
becomes an unsupported negative or exhaustive claim and reuse the issued snapshot
assumption.

Run RED and record the expected missing end-to-end contract, implement only bounded
fixture support, then require GREEN.

```bash
uv run pytest tests/integration/query/test_cross_product_holding_query.py -q
```

- [x] **Step 9: Run one Task 8 aggregate and verification bundle**

```bash
uv run pytest tests/unit/entity tests/unit/query tests/unit/registry/test_registry_loader.py tests/unit/planner/test_prompts.py tests/security/test_query_injection.py tests/integration/query tests/integration/planner/test_planner_service.py tests/integration/service/test_answer_service.py tests/integration/api/test_answer_endpoint.py tests/unit/cli/test_evaluate.py tests/unit/evaluation/test_ablation.py tests/unit/quality/test_pipeline_order.py tests/unit/domain/test_evidence_models.py tests/unit/evidence tests/unit/answer/test_renderer.py tests/contract/test_runtime_registry_resources.py -q
uv run ruff format --check src/finproof/entity src/finproof/query src/finproof/domain/execution.py src/finproof/domain/evidence.py src/finproof/storage/repositories/evidence.py src/finproof/quality/pipeline.py src/finproof/evidence src/finproof/answer/renderer.py src/finproof/api/dependencies.py src/finproof/planner/service.py src/finproof/planner/prompts.py src/finproof/service/answer_service.py src/finproof/cli/evaluate.py src/finproof/evaluation/ablation_experiment.py tests/unit/entity tests/unit/query tests/unit/registry/test_registry_loader.py tests/unit/planner/test_prompts.py tests/security/test_query_injection.py tests/integration/query tests/integration/planner/test_planner_service.py tests/integration/service/test_answer_service.py tests/integration/api/test_answer_endpoint.py tests/unit/cli/test_evaluate.py tests/unit/evaluation/test_ablation.py tests/unit/quality/test_pipeline_order.py tests/unit/domain/test_evidence_models.py tests/unit/evidence tests/unit/answer/test_renderer.py tests/contract/test_runtime_registry_resources.py
uv run ruff check src/finproof/entity src/finproof/query src/finproof/domain/execution.py src/finproof/domain/evidence.py src/finproof/storage/repositories/evidence.py src/finproof/quality/pipeline.py src/finproof/evidence src/finproof/answer/renderer.py src/finproof/api/dependencies.py src/finproof/planner/service.py src/finproof/planner/prompts.py src/finproof/service/answer_service.py src/finproof/cli/evaluate.py src/finproof/evaluation/ablation_experiment.py tests/unit/entity tests/unit/query tests/unit/registry/test_registry_loader.py tests/unit/planner/test_prompts.py tests/security/test_query_injection.py tests/integration/query tests/integration/planner/test_planner_service.py tests/integration/service/test_answer_service.py tests/integration/api/test_answer_endpoint.py tests/unit/cli/test_evaluate.py tests/unit/evaluation/test_ablation.py tests/unit/quality/test_pipeline_order.py tests/unit/domain/test_evidence_models.py tests/unit/evidence tests/unit/answer/test_renderer.py tests/contract/test_runtime_registry_resources.py
uv run mypy --no-incremental src/finproof/entity src/finproof/query src/finproof/domain/execution.py src/finproof/domain/evidence.py src/finproof/storage/repositories/evidence.py src/finproof/quality/pipeline.py src/finproof/evidence src/finproof/answer/renderer.py src/finproof/api/dependencies.py src/finproof/planner/service.py src/finproof/planner/prompts.py src/finproof/service/answer_service.py src/finproof/cli/evaluate.py src/finproof/evaluation/ablation_experiment.py tests/unit/entity tests/unit/query tests/unit/registry/test_registry_loader.py tests/unit/planner/test_prompts.py tests/integration/query tests/integration/planner/test_planner_service.py tests/integration/service/test_answer_service.py tests/integration/api/test_answer_endpoint.py tests/unit/cli/test_evaluate.py tests/unit/evaluation/test_ablation.py tests/unit/quality/test_pipeline_order.py tests/unit/domain/test_evidence_models.py tests/unit/evidence tests/unit/answer/test_renderer.py tests/contract/test_runtime_registry_resources.py
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
git diff --check
```

Do not run another official full artifact build in Task 8.
The clean-wheel resource check appears only in the aggregate command above and runs once.

**Acceptance criteria:**

- Every production construction path supplies the separate typed holding resolution for
  holding queries; unrelated `ResolutionBundle` constructors remain compatible through
  the `None` default.
- Registry and prompt resources expose field registry `1.3.0`, planner catalog `1.2.0`,
  the three exact holding aliases, the scalar `eq` relation-filter rule, and
  `phase4-planner-v3`. The field and prompt allow exactly the five holding product types,
  at most one holding filter, and no bond combination. Repository, editable, and
  clean-wheel bytes and issued versions match exactly.
- Resolver selection requires one distinct constituent identifier/type pair for either an
  exact identifier or normalized exact name. Same-string/different-type matches and every
  other multi-pair result remain deterministic bounded ambiguity; only repeated rows for
  the same pair deduplicate.
- Semantic validation rejects missing, unresolved, multiple, malformed, or raw-name
  holding execution inputs, two or more holding filters, and the entire plan whenever a
  holding filter coexists with `domestic_bond`; it never silently prunes or executes an
  unfiltered bond segment.
- The strict execution relation preserves both constituent identifier and identifier
  type and never enters scalar filters, native projections, or policy scalar matching.
- Every selected native segment among `domestic_etf`, `domestic_etn`, `overseas_etf`,
  `overseas_etn`, and `public_fund`, including either ETN type, retains one exact four-part
  parameterized correlated `EXISTS`; no value interpolation or incompatible union exists.
- ETN/unavailable coverage fails closed and is never rendered as unfiltered, negative, or
  complete coverage.
- Mixed overseas `return_1y` preserves the compatible domestic ETF/public-fund global
  rank, prunes overseas, and carries its typed limitation through execution, policy,
  evidence, serialization, rendering, and verification. Overseas-only remains
  unsupported.
- Positive matches bind official owner, exact crosswalk, canonical holding, canonical
  coverage, metric, rank/partition, and version evidence. No-row unavailable types have a
  bounded type/state/count coverage summary grounding their limitation.
- New holding candidate/rank claims and new holding/coverage/overseas-pruning material
  limitations reference matching evidence or coverage summaries and pass fail-closed
  claim verification; unrelated existing limitations retain their current contract.
- Non-holding evidence serialization remains byte-identical `evidence_context.v2`; only
  non-empty holding/coverage references produce bounded, lossless `evidence_context.v3`.
  Task 8 does not modify evaluation artifacts or goldens.
- Builder and rendered output reuse the issued answer-policy `snapshot_assumption` and own
  no replacement snapshot literal.
- Synthetic domestic ETF and public-fund positive partial matches prove the compatible
  global 1Y rank; domestic ETN proves unavailable fail-closed and overseas ETF proves 1Y
  pruning. Official holding count 0 and coverage count 31,492 remain unchanged, and no
  official full build runs.
- Every Step 9 command has fresh observed GREEN output before commit.

**Stop conditions:**

- Stop if the active manifest/checksum or refreshed 13-table counts differ, including
  `silver_product_holding = 0` or `silver_product_holding_coverage = 31,492`.
- Stop if repository, editable-install, or clean-wheel registry resources differ in bytes
  or issued versions.
- Stop if `holding_constituent` applicability differs from the exact five allowed product
  types, if more than one relation filter can pass validation, or if any bond-containing
  holding plan is pruned or executed instead of rejected as a whole.
- Stop if Task 7 changes the reviewed holding/coverage schema or canonical model
  interfaces; correct and independently re-review this plan before implementation.
- Stop if any owner or constituent match requires name-only, fuzzy, or non-admitted
  identifier linkage.
- Stop if one identifier string mapped to multiple identifier types, or one normalized
  name mapped to multiple distinct identifier/type pairs, is selected automatically.
- Stop if positive ETN holdings or non-unavailable ETN coverage appear.
- Stop if coverage is missing, duplicated, inconsistent with its holding generation, or
  insufficient to distinguish evidenced positives from exhaustive coverage.
- Stop if overseas 1Y requires an unapproved source, metric, or comparability rule.
- Stop on any unexplained focused failure, source audit failure, or evidence mismatch.

- [x] **Step 10: Commit the exact Task 8 paths and request independent code review**

```bash
git add config/field_registry.yaml config/planner_catalog.yaml src/finproof/entity/__init__.py src/finproof/entity/models.py src/finproof/entity/holding_resolver.py src/finproof/query src/finproof/domain/execution.py src/finproof/domain/evidence.py src/finproof/storage/repositories/evidence.py src/finproof/quality/pipeline.py src/finproof/evidence src/finproof/answer/renderer.py src/finproof/api/dependencies.py src/finproof/planner/service.py src/finproof/planner/prompts.py src/finproof/service/answer_service.py src/finproof/cli/evaluate.py src/finproof/evaluation/ablation_experiment.py tests/unit/entity/test_holding_resolution.py tests/unit/query tests/unit/registry/test_registry_loader.py tests/unit/planner/test_prompts.py tests/security/test_query_injection.py tests/integration/query tests/integration/planner/test_planner_service.py tests/integration/service/test_answer_service.py tests/integration/api/test_answer_endpoint.py tests/unit/cli/test_evaluate.py tests/unit/evaluation/test_ablation.py tests/unit/quality/test_pipeline_order.py tests/unit/domain/test_evidence_models.py tests/unit/evidence tests/unit/answer/test_renderer.py tests/contract/test_runtime_registry_resources.py
git commit -m "feat: query sealed constituent evidence"
```

Obtain an independent code review before Task 9. Do not broaden the implementation beyond
the files and contracts above.

---

### Task 9: Require HCX planning and verified HCX answer wording within 295 seconds

**2026-08-29 blocker correction (D-036):** The prompt-only strict-JSON live
acceptance reached HCX-007, but both the initial planner output and the one allowed
repair failed local schema validation. NCP's official Chat Completions v3 contract
documents HCX-007 Structured Outputs through `responseFormat` and supports every
keyword used by both checked-in provider schemas. Therefore evaluation activates the
already implemented `HcxRequest.structured` transport for planning and wording while
retaining all stricter local validation, the same two-call ceiling, and fail-closed
publication. `StrictJsonPlanner` remains offline/extended-demo only. This correction
supersedes Task 9 references to evaluation "strict JSON" below; it does not reopen
Steps 1-8 except for the focused provider-mode and replay assertions listed in Step 9.

**Files:**

- Create: `schemas/hcx_answer.schema.json`
- Create: `src/finproof/answer/hcx_verbalizer.py`
- Create: `src/finproof/service/publication.py`
- Create: `tests/unit/answer/test_hcx_verbalizer.py`
- Create: `tests/unit/service/test_publication.py`
- Modify: `src/finproof/answer/__init__.py`
- Modify: `src/finproof/domain/answers.py`
- Modify: `src/finproof/evidence/__init__.py`
- Modify: `src/finproof/evidence/builder.py`
- Modify: `src/finproof/planner/hcx_client.py`
- Modify: `src/finproof/planner/json_planner.py`
- Modify: `src/finproof/planner/models.py`
- Modify: `src/finproof/planner/rule_fallback.py`
- Modify: `src/finproof/planner/structured_planner.py`
- Modify: `src/finproof/api/dependencies.py`
- Modify: `src/finproof/api/app.py`
- Modify: `src/finproof/api/errors.py`
- Modify: `src/finproof/api/models.py`
- Modify: `src/finproof/api/routes/answer.py`
- Modify: `src/finproof/cli/evaluate.py`
- Modify: `src/finproof/planner/service.py`
- Modify: `src/finproof/service/__init__.py`
- Modify: `src/finproof/service/answer_service.py`
- Modify: `src/finproof/service/orchestrator.py`
- Modify: `src/finproof/service/limits.py`
- Modify: `src/finproof/evidence/verifier.py`
- Modify: `src/finproof/evaluation/ablation_experiment.py`
- Modify: `src/finproof/evaluation/runner.py`
- Modify: `tools/build_canonical_reference_packet.py`
- Modify: `tests/golden/test_seed_plans.py`
- Modify: `tests/unit/api/test_response_model.py`
- Modify: `tests/unit/cli/test_evaluate.py`
- Modify: `tests/unit/core/test_hcx_settings.py`
- Modify: `tests/unit/planner/test_hcx_models.py`
- Modify: `tests/unit/planner/test_rule_fallback.py`
- Modify: `tests/unit/evaluation/test_ablation.py`
- Modify: `tests/unit/evaluation/test_build_canonical_reference_packet.py`
- Modify: `tests/unit/evidence/test_claim_verifier.py`
- Modify: `tests/integration/planner/test_hcx_client.py`
- Modify: `tests/integration/planner/test_planner_service.py`
- Modify: `tests/integration/planner/test_live_hcx.py`
- Modify: `tests/integration/query/test_cross_product_holding_query.py`
- Modify: `tests/integration/service/test_answer_service.py`
- Modify: `tests/integration/service/test_orchestrator_fallbacks.py`
- Modify: `tests/integration/api/test_answer_endpoint.py`
- Modify: `tests/integration/evaluation/test_fault_injection.py`
- Modify: `tests/integration/evaluation/test_runner.py`
- Modify: `tests/evaluation/test_adversarial_cases.py`
- Modify: `tests/e2e/test_evaluation_api.py`
- Modify: `tests/security/test_runtime_provider_policy.py`
- Modify: `tests/unit/service/test_limits.py`

**Interfaces:**

- `RequestDeadline.start(*, clock) -> RequestDeadline` freezes
  `started_at=clock()`, `work_cutoff_at=started_at + 293.0`, and
  `outer_at=started_at + 295.0`. `SERIALIZATION_RESERVE_SECONDS` is exactly
  `2.0`; work uses `remaining_work_seconds()`, while envelope/byte publication
  uses `remaining_outer_seconds()`.
- `RequestLimiter.acquire(*, correlation_id: str, deadline: RequestDeadline) ->
  AsyncIterator[RequestContext]`; `RequestContext.deadline is deadline`.
- `PlannerProtocol.plan(request: PlanningRequest, *, deadline: RequestDeadline) ->
  PlannedQuery`; `PlanningRequest.start(..., deadline_seconds=...)` is removed so
  no planner or caller can mint a stage-local deadline.
- One dependency-owned `HcxClient` and one dependency-owned `httpx.AsyncClient`
  lifetime are shared by the evaluation `StructuredOutputPlanner` and
  `HcxVerbalizer`; `StrictJsonPlanner` has no evaluation composition path.
- `HcxClient.generate(request: HcxRequest, request_id: str, *, deadline:
  RequestDeadline) -> HcxResponse` checks the same work cutoff; it remains
  non-retrying and does not own or close the shared HTTP client.
- `AnswerService.prepare_plan(request: AnswerRequest, plan: QueryPlan,
  deadline: RequestDeadline) -> PreparedAnswer` performs validation, query,
  policy, evidence, deterministic draft construction, fact-pack construction,
  and local draft verification synchronously. It never returns publishable
  evaluation prose.
- `EvaluationOrchestrator.answer(request: AnswerRequest, *, deadline:
  RequestDeadline, safe_result: AnswerResult) -> AnswerResult` awaits planning,
  runs `prepare_plan` through one bounded `asyncio.to_thread`, awaits HCX wording
  and at most one wording repair, then calls local wording verification.
- `HcxVerbalizer.verbalize(fact_pack: FactPack, *, request_id: str, deadline:
  RequestDeadline) -> ProviderWording` and `repair(..., invalid_content: str,
  ...) -> ProviderWording` are async and reuse `HcxClient.generate`.
- `ClaimVerifier.verify_wording(wording: ProviderWording, prepared:
  PreparedAnswer, deadline: RequestDeadline) -> VerifiedAnswer` trusts only the
  application-issued fact pack and evidence-derived signatures.
- `build_safe_publication(request: AnswerRequest, *, correlation_id: str,
  snapshot_date: date, deadline: RequestDeadline) -> EvaluationPublication` and
  `publish_result(request: AnswerRequest, result: AnswerResult, *,
  correlation_id: str, deadline: RequestDeadline) -> EvaluationPublication` are
  the sole result/envelope/
  canonical-byte publication functions. `EvaluationPublication` contains the
  `AnswerResult`, exact five-string `EvaluationResponse`, and
  `canonical_json_bytes(..., terminal_newline=False)` body.

**Evaluation composition contract:**

- `ExecutionMode.EVALUATION` in the FastAPI lifespan and canonical/robustness CLI
  composition requires `hcx_enabled=True`, a non-empty key, exact model `HCX-007`, a
  successfully opened shared HTTP client, both checked-in schemas, both prompt
  identities, and an expected-verified runtime artifact session. Absence or
  construction failure raises before evaluation work; it never selects
  `RuleFallbackPlanner` or deterministic substantive wording.
- `ApiDependencies.create_orchestrator` and `run_evaluation(..., service=...)`
  cannot override an evaluation graph. Test doubles use the HCX transport seam,
  or explicitly use `ExecutionMode.EXTENDED_DEMO`.
- API and CLI end-to-end evaluation use the same dependency-owned
  `EvaluationOrchestrator`. CLI `PLAN_ONLY` uses that graph but stops after its
  mandatory HCX plan; CLI `DETERMINISTIC_CORE` is rejected in evaluation mode.
- `RuleFallbackPlanner`, `AnswerService.answer_plan`, deterministic reference
  authoring, and ablation shortcuts remain only in explicitly
  `EXTENDED_DEMO`/offline test/artifact paths and cannot produce organizer-mode
  execution. `Settings(hcx_enabled=False)` remains valid for those non-runtime
  tools; the evaluation composition root, not generic settings construction,
  enforces mandatory HCX.
- `Intent.CLARIFY` and `Intent.UNSUPPORTED` still produce a strict fact pack and
  require HCX wording. Only `"요청을 처리할 수 없습니다."` with empty claims,
  empty context, safe trace, and exact five-string envelope bypasses HCX.
- Evaluation `ReplayVersions` records both mandatory HCX stages. Rename the stale
  `PlannerRuntimeMode.HCX_STRICT_JSON_WITH_FALLBACK` member/value to
  `HCX_STRUCTURED_OUTPUTS_VERIFIED_WORDING =
  "hcx-structured-outputs-verified-wording"`; record
  `execution_mode=EVALUATION`, `hcx_enabled=True`, `fallback_enabled=False`, the
  HCX planner model/provider, `PROMPT_VERSION`, `ANSWER_PROMPT_VERSION`, the
  checked-in answer-schema SHA-256, and
  `wording_verification_mode="exact-application-surface-v1"` in the replay object
  and `configuration_sha256`. `ReplayVersions.from_configuration` rejects any
  evaluation combination that omits those identities, names a model other than exact
  `HCX-007`, sets `structured_outputs_enabled=False`, enables fallback, or disables
  HCX. `FALLBACK_ONLY` metadata remains valid only with
  `ExecutionMode.EXTENDED_DEMO` for explicit offline/demo replay.

**Fact-pack and provider contract:**

`FactPack` is frozen, strict, and bounded. It contains exactly:

```text
format = "finproof.fact-pack.v1"
surface_parts: tuple[SurfacePart, ...]
claim_signatures: tuple[ClaimSignature, ...]
required_claim_ids: tuple[str, ...]
required_limitation_codes: tuple[str, ...]
evidence_context_sha256: 64 lowercase hex characters
```

Task 9 uses the smallest fail-closed surface: exactly one application-issued
`SurfacePart(part_id="surface:answer", text=<deterministic AnswerDraft.text>,
claim_ids=<all required claim IDs>, limitation_codes=<all required codes>)`.
Therefore the application answer is exactly `"".join(part.text for part in
surface_parts)` and covers every byte; there is no unbound prefix, suffix, or
separator.

Each `ClaimSignature` is derived locally from `AnswerClaim`, `EvidenceBundle`, and
the issued registries and contains the exact claim kind and surface text; every
referenced entity's product type, evidence-derived identifier, and evidence-derived
display name; each value's canonical normalized JSON, exact display text, field ID,
and registry unit (including explicit `None` when the registry declares no unit);
rank, tie count, and partition; comparison relation (`gt`, `lt`,
or `eq`) and both evidence-derived operands; evidence IDs; and application-issued
limitation/omission codes. Known codes reuse typed execution/coverage codes;
snapshot, clarification, and unsupported use `snapshot_assumption`,
`clarification_required`, and `unsupported_request`. Any remaining existing policy
limitation receives `policy:<sha256(canonical text plus ordered evidence IDs)>`, so
HCX never chooses a code. A missing applicable entity name, operand, value, rank,
tie, unit declaration, partition, limitation evidence, duplicate ID, or ambiguous
binding fails preparation.

`PreparedAnswer` contains exactly the issued `FactPack`, the locally verified
`AnswerClaim` tuple needed to construct `VerifiedAnswer`, the execution trace, and
`retrieved_context=canonical_json_bytes(fact_pack, terminal_newline=False).decode()`.
The fact pack binds the SHA-256 of the pre-pack evidence context, and the published
fact pack must fit the existing 24,000-byte context bound without truncation; overflow
returns the fixed safe response.

`schemas/hcx_answer.schema.json` is checked in and uses the already tested HCX-safe
JSON-Schema subset. The only provider object is:

```json
{
  "answer": "<exact application surface>",
  "surface_part_ids": ["surface:answer"],
  "claim_ids": ["<every required claim ID in application order>"],
  "limitation_codes": ["<every required code in application order>"]
}
```

`src/finproof/answer/hcx_verbalizer.py` owns the checked-in schema loader, strict
JSON parser, `ANSWER_PROMPT_VERSION`, prompt checksum, and the adapter. Local
verification requires all four fields to equal the application-issued values
exactly. Unknown or duplicate IDs, reordering, partial coverage, missing
limitations, changed entity/number/comparison/rank, extra text, and any answer not
equal to the exact application surface fail even when the provider cites otherwise
valid IDs.

**Closed planner transition table:**

| Initial HCX outcome | Second call | Second outcome | Evaluation result |
|---|---|---|---|
| valid parse, schema, and semantics | none | n/a | execute validated plan |
| parse/schema invalid | one invalid-output repair carrying the invalid content | valid parse/schema/semantics | execute repaired plan |
| parse/schema invalid | one invalid-output repair | parse/schema invalid, semantic invalid, or provider failure | centralized safe response |
| semantic invalid | none | n/a | centralized safe response; never repair or fallback |
| retryable transport (`HcxTransportError`, 429 whose reset fits the work budget, or HTTP 5xx) | one identical-prompt transport retry | valid parse/schema/semantics | execute retried plan |
| retryable transport | one identical-prompt transport retry | any failure or invalid output | centralized safe response |
| non-retryable provider failure, elapsed work cutoff, or 429 reset outside budget | none | n/a | centralized safe response |

The planner ceiling is exactly two HCX calls. Invalid-output repair and transport
retry are mutually exclusive; a retry response never opens a third repair. Exactly
one invalid-output repair is possible. Terminal planner errors are typed and contain
only bounded categories/counters for logging, never provider content, key, path, or
prompt.

- [x] **Step 1: Write request-deadline and publication REDs**

Add fake-clock tests proving `outer_at == start + 295.0`,
`work_cutoff_at == start + 293.0`, object identity through queue admission, queue
expiry at the work cutoff, and exact safe bytes already constructed inside the
two-second reserve. Test the exact five keys, canonical byte equality, and absence of
keys, paths, raw SQL, provider content, prompts, and stack traces.
Before changing middleware, routes, errors, models, or serialization, add API REDs in
`tests/integration/api/test_answer_endpoint.py`, `tests/e2e/test_evaluation_api.py`,
and `tests/unit/api/test_response_model.py`. They must prove the middleware creates
the deadline at ingress, route/error paths reuse the prebuilt safe publication, raw
response content equals canonical bytes, and FastAPI performs no second serialization.

```bash
uv run pytest tests/unit/service/test_limits.py tests/unit/service/test_publication.py tests/unit/api/test_response_model.py tests/integration/api/test_answer_endpoint.py tests/e2e/test_evaluation_api.py -q
```

Expected: fail because the current limiter creates a 15-second deadline at admission
and safe result/envelope/bytes have three independent renderers.

- [x] **Step 2: Implement the one ingress deadline and publication path**

Add `RequestDeadline` and change the limiter to accept it. At HTTP middleware ingress,
create one deadline with the injected clock and store it on `request.state` before
validation/routing. Build the fixed safe publication immediately after valid query
binding and before queue admission. Replace `api.errors.safe_failure`, the private
orchestrator safe renderer, route assembly, and unexpected-exception assembly with
`service.publication`. Normal and safe HTTP responses use the publication's canonical
bytes directly; FastAPI must not perform a second JSON serialization.

```bash
uv run pytest tests/unit/service/test_limits.py tests/unit/service/test_publication.py tests/unit/api/test_response_model.py tests/integration/api/test_answer_endpoint.py tests/e2e/test_evaluation_api.py -q
```

Expected: pass with the exact 293/295 boundaries and byte contract.

- [x] **Step 3: Write mandatory-HCX composition and planner-transition REDs**

Cover API and canonical/robustness CLI construction with disabled HCX, missing key,
invalid readiness, explicit orchestrator/service override, and ready recorded HCX.
Assert the same ready graph owns one HTTP client, one `HcxClient`, one structured-output
planner, and one structured-output verbalizer. Replace the old fallback expectations
with every row in the closed transition table; assert the exact call count, prompt kind
(`repair` versus identical transport retry), and centralized safe terminal category.
Add replay REDs before changing `evaluation/runner.py`: evaluation metadata rejects
`hcx_enabled=False` and `fallback_enabled=True`, uses the renamed HCX-only verified-
wording mode, binds both prompt identities and the answer-schema hash, and keeps
fallback-only metadata exclusive to extended-demo replay. Seed, ablation, reference-
packet, and integration-runner tests must first fail while they still advertise the
stale evaluation fallback contract.

```bash
uv run pytest tests/integration/planner/test_hcx_client.py tests/integration/planner/test_planner_service.py tests/unit/cli/test_evaluate.py tests/golden/test_seed_plans.py tests/unit/evaluation/test_ablation.py tests/unit/evaluation/test_build_canonical_reference_packet.py tests/integration/evaluation/test_runner.py tests/security/test_runtime_provider_policy.py -q
```

Expected: fail because API and CLI currently select `RuleFallbackPlanner`, accept
evaluation overrides, planner failures return rule plans, and replay metadata still
advertises HCX with fallback without a verified-wording identity.

- [x] **Step 4: Implement mandatory evaluation planning and shared ownership**

Remove the evaluation fallback dependency from `PlannerService`, implement the table
with a two-call counter, and pass the same `RequestDeadline` object into structured
plan, repair, retry, and `HcxClient.generate`. In `ApiDependencies.open_orchestrator`, open
one HTTP client, construct one `HcxClient`, inject it into both HCX adapters, and close
the HTTP context only after `EvaluationOrchestrator.aclose()` drains retained DB work.
Make `_open_local_service` reuse this graph. Keep direct rule planning and deterministic
answering only behind explicit non-evaluation checks; update seed, ablation, and
reference-packet tests/tools to declare that offline mode. Update `ReplayVersions` and
the evaluation service metadata exactly as frozen above; no evaluation report may
retain the old `WITH_FALLBACK` name or `fallback_enabled=True`.

```bash
uv run pytest tests/integration/planner/test_hcx_client.py tests/integration/planner/test_planner_service.py tests/unit/cli/test_evaluate.py tests/golden/test_seed_plans.py tests/unit/evaluation/test_ablation.py tests/unit/evaluation/test_build_canonical_reference_packet.py tests/integration/evaluation/test_runner.py tests/security/test_runtime_provider_policy.py -q
```

Expected: pass with no evaluation path to `RuleFallbackPlanner`, no second HTTP
client, and exact HCX-only verified-wording replay metadata.

- [x] **Step 5: Write strict fact-pack, provider-output, and wording-verifier REDs**

First test a valid numeric/rank/comparison/limitation fact pack. Then use the same
valid IDs while changing, one case at a time, the number, entity ID/name, comparison
relation/operand, rank/tie/partition, and display/unit; every case must fail. Also
reject missing entity evidence, unknown IDs, duplicate IDs, reordered/partial surface
parts or claims, missing limitation/omission code, extra prefix/suffix, provider fields
outside the schema, and an answer differing by one byte from the application join.
Add CLARIFY and UNSUPPORTED cases that prove the verbalizer is called, plus the fixed
safe response case that proves it is not.

```python
def test_valid_ids_cannot_cover_a_changed_number(prepared, verifier, deadline) -> None:
    wording = provider_wording(prepared.fact_pack).model_copy(
        update={"answer": prepared.fact_pack.surface_parts[0].text.replace("3.10", "3.11")}
    )
    with pytest.raises(ClaimVerificationError):
        verifier.verify_wording(wording, prepared, deadline)
```

```bash
uv run pytest tests/unit/answer/test_hcx_verbalizer.py tests/unit/evidence/test_claim_verifier.py tests/integration/service/test_answer_service.py tests/integration/query/test_cross_product_holding_query.py -q
```

Expected: fail because no strict answer schema, fact pack, signature binder, or HCX
wording verifier exists.

- [x] **Step 6: Implement deterministic preparation and HCX wording**

Add the frozen contracts in `domain.answers`, build the one-part fact pack from the
existing deterministic `AnswerRenderer` draft and verified evidence, and keep the
existing `ClaimVerifier.verify` checks as the preparation gate. Add the strict parser,
prompt identity, and async adapter in `hcx_verbalizer.py`; do not add another transport
or dependency. `AnswerService.prepare_plan` returns only `PreparedAnswer`.
`AnswerService.answer_plan` rejects evaluation sessions and remains a narrow
offline/demo compatibility method.

```bash
uv run pytest tests/unit/answer/test_hcx_verbalizer.py tests/unit/evidence/test_claim_verifier.py tests/integration/service/test_answer_service.py tests/integration/query/test_cross_product_holding_query.py -q
```

Expected: pass, including CLARIFY/UNSUPPORTED fact packs and exact surface equality.

- [x] **Step 7: Write async orchestration and stage-deadline REDs**

With one identity-recording fake deadline, assert planner, planning repair, retained
DB thread, every deterministic preparation checkpoint, verbalizer, wording repair,
wording verifier, envelope construction, and success/safe serialization see the same
object. Advance the clock at queue, DB, planner repair, wording repair, work cutoff,
and serialization reserve boundaries. Prove no call starts at/after
`work_cutoff_at`; DB timeout/cancellation shields the worker, retains the limiter
permit until completion, and `aclose` drains it before the artifact session/HTTP
client closes. Prove valid CLARIFY and UNSUPPORTED responses each make one wording
call. Prove initial invalid wording gets exactly one repair and any second failure or
transport failure returns the prebuilt safe publication.

```bash
uv run pytest tests/integration/service/test_orchestrator_fallbacks.py tests/integration/evaluation/test_fault_injection.py tests/evaluation/test_adversarial_cases.py tests/integration/api/test_answer_endpoint.py tests/e2e/test_evaluation_api.py tests/unit/cli/test_evaluate.py -q
```

Expected: fail because synchronous `answer_plan` currently publishes deterministic
prose and existing stages consume/reset independent remaining-time values.

- [x] **Step 8: Implement orchestration, API, and CLI publication**

Change the orchestrator to the async planner -> bounded `to_thread(prepare_plan)` ->
async verbalizer -> local verify flow. Word repair is allowed only for strict parse,
schema, or local surface/signature verification failure; it is the final wording call.
Route every terminal typed failure to the supplied safe result. Preserve the existing
shield/permit-retention/drain mechanics. Adapt `/answer` and CLI observations to the
new result and publication contracts; no API exception path may build a second safe
shape.
The route returns the already built safe body when the orchestrator returns the exact
supplied `safe_result`; it does not rebuild or reserialize that failure. Unexpected
post-validation API exceptions reuse `request.state.safe_publication`. The bounded
framework 422 for invalid/missing query parameters remains governed by Q-010 and is
the only path that cannot form a valid five-string evaluation envelope.

```bash
uv run pytest tests/integration/service/test_orchestrator_fallbacks.py tests/integration/api/test_answer_endpoint.py tests/unit/cli/test_evaluate.py tests/evaluation/test_adversarial_cases.py -q
```

Expected: pass with exact five-string canonical bytes and the full HCX graph in
evaluation mode.

- [x] **Step 9: Activate Structured Outputs under focused RED→GREEN, then run live acceptance**

First add focused RED assertions that evaluation planning and wording each emit
`responseFormat={"type":"json","schema":<their exact checked-in provider schema>}`;
that those structured requests set exact `thinking={"effort":"none"}`; that neither path can select prompt-only
`HcxRequest.strict_json`; that both schemas contain only the officially supported HCX
subset; that API and CLI evaluation reject every model except exact `HCX-007`; and that
replay metadata rejects `structured_outputs_enabled=False` and uses only
`hcx-structured-outputs-verified-wording`. Run:

```bash
uv run pytest tests/unit/planner/test_hcx_models.py tests/unit/answer/test_hcx_verbalizer.py tests/integration/planner/test_planner_service.py tests/integration/evaluation/test_runner.py tests/integration/api/test_answer_endpoint.py tests/unit/cli/test_evaluate.py tests/security/test_runtime_provider_policy.py -q
```

Expected RED on the resumed correction: the current structured payload omits the
provider-required explicit non-inference marker.

Implement the smallest activation by reusing `HcxRequest.structured` and the existing
provider-schema loaders. `HcxRequest.to_payload` emits exact
`thinking={"effort":"none"}` for every HCX-007 request; with `responseFormat` this is
the provider's explicit non-inference marker, not enabled Thinking. Give
`StructuredOutputPlanner` the same one invalid-output
repair interface already enforced by `PlannerService`; every initial/retry/repair
planner call uses `hcx_query_plan.schema.json`, and every initial/repair wording call
uses `hcx_answer.schema.json`. Keep strict local parsing, canonical schema/Pydantic and
semantic validation, exact fact-pack verification, call limits, deadline identity, and
safe publication unchanged. Rerun the focused command and require GREEN before any
live call.

The opt-in test constructs the same shared `HcxClient`, runs one planner schema case
and one wording schema case with at least one numeric/entity/rank signature, and passes
the returned wording through local exact-surface verification. It may print only test
node IDs/status, never the environment value, authorization header, prompt, provider
body, or fact pack.

```bash
FINPROOF_RUN_LIVE_HCX=1 uv run pytest tests/integration/planner/test_live_hcx.py -q -k 'planner or verbalizer'
```

Expected: pass when authorized credentials are present. If credentials are absent,
record the skip and do not claim live acceptance. If the selected HCX model cannot
satisfy either structured provider schema plus stricter local validation after its one
allowed invalid-output repair, stop under the repository HCX-model contract; do not
enable deterministic evaluation fallback.

- [x] **Step 10: Run the one Task 9 aggregate and scoped checks**

Run the Task 9 bundle once after all focused GREENs:

```bash
uv run pytest tests/golden/test_seed_plans.py tests/unit/api/test_response_model.py tests/unit/answer/test_hcx_verbalizer.py tests/unit/service/test_limits.py tests/unit/service/test_publication.py tests/unit/cli/test_evaluate.py tests/unit/core/test_hcx_settings.py tests/unit/planner/test_hcx_models.py tests/unit/planner/test_rule_fallback.py tests/unit/evaluation/test_ablation.py tests/unit/evaluation/test_build_canonical_reference_packet.py tests/unit/evidence/test_claim_verifier.py tests/integration/planner/test_hcx_client.py tests/integration/planner/test_planner_service.py tests/integration/planner/test_live_hcx.py tests/integration/query/test_cross_product_holding_query.py tests/integration/service/test_answer_service.py tests/integration/service/test_orchestrator_fallbacks.py tests/integration/api/test_answer_endpoint.py tests/integration/evaluation/test_fault_injection.py tests/integration/evaluation/test_runner.py tests/evaluation/test_adversarial_cases.py tests/e2e/test_evaluation_api.py tests/security/test_runtime_provider_policy.py -q
uv run ruff format --check src/finproof/answer src/finproof/api src/finproof/cli/evaluate.py src/finproof/domain/answers.py src/finproof/evidence src/finproof/planner src/finproof/service src/finproof/evaluation/ablation_experiment.py src/finproof/evaluation/runner.py tools/build_canonical_reference_packet.py tests/golden/test_seed_plans.py tests/unit/api/test_response_model.py tests/unit/answer tests/unit/service tests/unit/cli/test_evaluate.py tests/unit/core/test_hcx_settings.py tests/unit/planner tests/unit/evaluation/test_ablation.py tests/unit/evaluation/test_build_canonical_reference_packet.py tests/unit/evidence/test_claim_verifier.py tests/integration/planner tests/integration/query/test_cross_product_holding_query.py tests/integration/service tests/integration/api/test_answer_endpoint.py tests/integration/evaluation/test_fault_injection.py tests/integration/evaluation/test_runner.py tests/evaluation/test_adversarial_cases.py tests/e2e/test_evaluation_api.py tests/security/test_runtime_provider_policy.py
uv run ruff check src/finproof/answer src/finproof/api src/finproof/cli/evaluate.py src/finproof/domain/answers.py src/finproof/evidence src/finproof/planner src/finproof/service src/finproof/evaluation/ablation_experiment.py src/finproof/evaluation/runner.py tools/build_canonical_reference_packet.py tests/golden/test_seed_plans.py tests/unit/api/test_response_model.py tests/unit/answer tests/unit/service tests/unit/cli/test_evaluate.py tests/unit/core/test_hcx_settings.py tests/unit/planner tests/unit/evaluation/test_ablation.py tests/unit/evaluation/test_build_canonical_reference_packet.py tests/unit/evidence/test_claim_verifier.py tests/integration/planner tests/integration/query/test_cross_product_holding_query.py tests/integration/service tests/integration/api/test_answer_endpoint.py tests/integration/evaluation/test_fault_injection.py tests/integration/evaluation/test_runner.py tests/evaluation/test_adversarial_cases.py tests/e2e/test_evaluation_api.py tests/security/test_runtime_provider_policy.py
uv run mypy src/finproof/answer src/finproof/api src/finproof/cli/evaluate.py src/finproof/domain/answers.py src/finproof/evidence src/finproof/planner src/finproof/service src/finproof/evaluation/ablation_experiment.py src/finproof/evaluation/runner.py tools/build_canonical_reference_packet.py tests/integration/evaluation/test_runner.py
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
git diff --check
```

Do not run the repository-wide pytest/Ruff/mypy gate in Task 9; Task 10 owns the final
candidate gate.

**Acceptance:**

- API and canonical/robustness CLI evaluation cannot start disabled, keyless,
  unready, rule-planned, deterministically worded, or through an injected service
  override. Both use one shared-client HCX graph.
- Planner behavior matches every transition-table row, has at most two calls and one
  repair, and never executes a semantic-invalid or fallback plan.
- Deterministic code alone prepares data/evidence/facts. Every substantive,
  clarification, and unsupported evaluation answer is returned by HCX and then
  accepted only when it equals the entire application-issued surface and all
  evidence-derived signatures/codes.
- All adversarial wording cases fail closed, including valid IDs paired with changed
  entity, number, comparison, rank, tie, partition, unit, or limitation.
- The ingress-created deadline has exact 293/295 cutoffs and identical object identity
  throughout. Queueing, both repairs, DB work, verification, envelope creation, and
  canonical serialization cannot reset or exceed it; safe bytes are available before
  `outer_at`.
- One centralized publisher emits exactly the five string fields and no secret,
  provider payload, prompt, path, SQL, or stack trace on any terminal path.
- The focused live acceptance is observed or explicitly recorded as skipped for absent
  credentials; schema incompatibility is a stop, not a fallback trigger.
- Evaluation replay metadata identifies HCX Structured Outputs planning plus verified HCX
  wording, binds both prompt/schema identities, and always records
  exact model `HCX-007`, `structured_outputs_enabled=True`, `hcx_enabled=True`, and
  `fallback_enabled=False`; fallback-only metadata is
  demonstrably extended-demo/offline.

**Stop conditions:**

- Stop if API and CLI cannot share the same dependency-owned HCX client lifetime, or
  if either evaluation root can select `RuleFallbackPlanner`, `answer_plan`, an
  injected service, or another model/provider.
- Stop if HCX readiness requires printing/probing the key, or if either provider schema
  cannot be represented by the checked-in HCX-safe subset.
- Stop if a material fact lacks an exact evidence-derived entity name/ID, normalized
  and display value/unit, rank/tie/partition, comparison operands/relation, or
  limitation/omission code. Return the fixed safe response; do not weaken equality.
- Stop if any output byte can lie outside the single application-issued surface, or if
  provider-reported IDs are accepted without exact application tuple equality.
- Stop if a third planner or wording call is possible, if transport retry and repair
  can both occur, or if CLARIFY/UNSUPPORTED bypass HCX.
- Stop if an evaluation `ReplayVersions` can carry the stale `WITH_FALLBACK` mode,
  `hcx_enabled=False`, `fallback_enabled=True`, a missing answer prompt/schema/
  verification identity, or fallback-only metadata.
- Stop if any stage constructs a new deadline, if work begins inside the serialization
  reserve, if safe bytes cannot be produced before `outer_at`, or if a detached DB
  worker releases its permit/session early.
- Stop on an unexplained focused/aggregate/check failure or live HCX schema failure.

- [x] **Step 11: Commit the exact Task 9 paths and request independent review**

```bash
git add schemas/hcx_answer.schema.json src/finproof/answer/__init__.py src/finproof/answer/hcx_verbalizer.py src/finproof/domain/answers.py src/finproof/evidence/__init__.py src/finproof/evidence/builder.py src/finproof/evidence/verifier.py src/finproof/planner/hcx_client.py src/finproof/planner/json_planner.py src/finproof/planner/models.py src/finproof/planner/rule_fallback.py src/finproof/planner/structured_planner.py src/finproof/planner/service.py src/finproof/api/app.py src/finproof/api/dependencies.py src/finproof/api/errors.py src/finproof/api/models.py src/finproof/api/routes/answer.py src/finproof/cli/evaluate.py src/finproof/service/__init__.py src/finproof/service/answer_service.py src/finproof/service/limits.py src/finproof/service/orchestrator.py src/finproof/service/publication.py src/finproof/evaluation/ablation_experiment.py src/finproof/evaluation/runner.py tools/build_canonical_reference_packet.py tests/golden/test_seed_plans.py tests/unit/api/test_response_model.py tests/unit/answer/test_hcx_verbalizer.py tests/unit/service/test_limits.py tests/unit/service/test_publication.py tests/unit/cli/test_evaluate.py tests/unit/core/test_hcx_settings.py tests/unit/planner/test_hcx_models.py tests/unit/planner/test_rule_fallback.py tests/unit/evaluation/test_ablation.py tests/unit/evaluation/test_build_canonical_reference_packet.py tests/unit/evidence/test_claim_verifier.py tests/integration/planner/test_hcx_client.py tests/integration/planner/test_planner_service.py tests/integration/planner/test_live_hcx.py tests/integration/query/test_cross_product_holding_query.py tests/integration/service/test_answer_service.py tests/integration/service/test_orchestrator_fallbacks.py tests/integration/api/test_answer_endpoint.py tests/integration/evaluation/test_fault_injection.py tests/integration/evaluation/test_runner.py tests/evaluation/test_adversarial_cases.py tests/e2e/test_evaluation_api.py tests/security/test_runtime_provider_policy.py
git commit -m "feat: require verified HCX answer pipeline"
```

Obtain an independent Critical/Important review before Task 10. The reviewer must map
C1-C4 and I1-I3 to executable tests and confirm the implementation stayed within this
exact path list.

---

### Task 10: Build the 35-case suite and close release verification

**Files:**

- Create: `evaluation/organizer_20260824/*.jsonl`
- Create: `tests/unit/evaluation/test_organizer_case_suite.py`
- Create: `tests/integration/evaluation/test_organizer_runner.py`
- Modify: `src/finproof/evaluation/loader.py`
- Modify: `src/finproof/cli/evaluate.py`
- Modify: `schemas/query_plan.schema.json`
- Modify: `schemas/hcx_query_plan.schema.json`
- Modify: `src/finproof/domain/query_plan.py`
- Modify: `src/finproof/query/semantic_validator.py`
- Modify: `src/finproof/query/segmenter.py`
- Modify: `src/finproof/planner/prompts.py`
- Modify: `src/finproof/evaluation/models.py`
- Modify: `src/finproof/evaluation/scoring.py`
- Modify: `src/finproof/answer/renderer.py`
- Modify: `src/finproof/evidence/serializer.py`
- Modify: `tests/unit/answer/test_renderer.py`
- Modify: `tests/unit/evidence/test_serializer.py`
- Create: versioned August-only expected plans/results/answers and review packets under explicit new paths
- Create: `tools/create_release_manifest.py`
- Create: `tools/verify_release_manifest.py`
- Create: `tools/check_competition_compliance.py`
- Create: `tools/check_claim_evidence_report.py`
- Create: `scripts/clean_room_reproduce.sh`
- Create: `tests/contract/test_release_manifest.py`
- Create: `tests/contract/test_competition_compliance.py`
- Create: `docs/review/INDEPENDENT_REVIEW.md`
- Create: `docs/review/FINDING_CLOSURE.md`
- Create: `docs/submission/SUBMISSION_CHECKLIST.md`
- Create: `docs/submission/API_SCHEMA.md`
- Create: `docs/submission/PROPOSAL_EVIDENCE_INDEX.md`
- Create: `docs/submission/RELEASE_RECORD.md`
- Modify: `docs/09_RISK_REGISTER.md`
- Modify: `docs/10_DECISION_LOG.md`
- Modify: `README.md`
- Generate: `artifacts/evaluation/organizer-20260824.json`
- Generate: `artifacts/evaluation/final-load.json`
- Generate: `artifacts/evaluation/final-soak.json`
- Generate after the covered candidate gate: `release/manifest.json`
- Modify once after 0C/0I review and the covered candidate gate: `docs/implementation/STATUS.md`
- Preserve untouched: the historical 265-case corpus and user-owned `evaluation/review_batches/*`

- [ ] **Step 1: Write suite-shape RED**

```python
def test_organizer_suite_has_exact_announced_shape() -> None:
    cases = load_suite("organizer_20260824")
    assert Counter(case.difficulty for case in cases) == {
        "easy": 10,
        "medium": 10,
        "hard": 10,
        "unanswerable": 5,
    }
    assert len(cases) == 35
```

Require constituent cross-product cases, partial/unavailable coverage cases, code-table unsupported cases, overseas 1Y pruning, intentional missing/zero handling, and no buyable-quantity behavior.

- [ ] **Step 2: Implement suite selection and author reviewed questions/plans**

Do not modify or use the old 265 data-dependent values as active truth. Create a separately selected and versioned August corpus; keep the old corpus byte-preserved as historical language/safety regression material.

- [ ] **Step 3: Generate deterministic expected results from the sealed artifact and obtain human review**

Use the existing reference-packet workflow and bind reviewer, review date, packet SHA-256, code commit, and artifact logical hash. No model output becomes truth without review.

The first approved 35-plan sealed-artifact execution exposed two bounded projection issues
before any expected result became truth. Rank answers must not repeat the same
product/metric/value as a second direct-value claim, and positive partition plus internal
metric-population summaries stay in evidence but are not repeated as answer claims when
rank claims already express the requested result. Preserve empty partitions and every
material limitation. Write focused renderer REDs before the minimum projection change.

The same run proved that valid TOP10 evidence can exceed Q-005 solely because v2 repeats
summary metadata. Apply D-037 under focused serializer RED/GREEN: retain byte-identical
v2/v3 for fitting payloads, use v4 only after canonical overflow, preserve every summary
field through ordered tables and exact common-context/policy references, and fail closed if
the lossless v4 still exceeds the bound. Do not reduce `top_k`, remove evidence, or raise
the 24,000-byte ceiling.

The answer-quality audit also exposed one overlapping-field segmentation error in the
approved H-005/H-009 plans. Apply D-038 under focused RED/GREEN by adding the explicit
`metric_targets` plan member to the canonical/provider schemas and HCX prompt. Require
an empty array unless the question explicitly assigns metrics to product types; otherwise
require exact selected-product coverage and metric-union equality, validate every target
pair against the registry, and route metrics plus same-field sorts exactly as declared.
Keep empty mappings on every shared or ambiguous plan, with the prior all-applicable
distribution unchanged. Update only H-005/H-009 in a v3 plan packet and obtain renewed
human plan approval before regenerating expected answers.

```bash
uv run pytest tests/unit/domain/test_query_plan_models.py tests/contract/test_phase2_schemas.py tests/unit/planner/test_provider_schema.py tests/unit/planner/test_prompts.py tests/unit/query/test_semantic_validator.py tests/unit/query/test_execution_bundle.py tests/unit/evaluation/test_case_schema.py tests/unit/evaluation/test_scoring.py -q -k 'metric_target or provider_schema or query_plan'
```

```bash
uv run pytest tests/unit/answer/test_renderer.py -q -k 'rank and duplicate'
uv run pytest tests/unit/evidence/test_serializer.py -q -k 'v2 or v3 or v4'
```

The serializer REDs prove the complete existing fitting v2 and v3 bytes remain identical;
v4 serialization is byte-identical across repeats; its exact field, first-appearance
policy-table, zero-based index, and original-row ordering reconstruct every original
canonical summary field/value; unequal common hash triples fail closed; and a lossless v4
that still exceeds 24,000 bytes fails closed.

- [ ] **Step 4: Run organizer suite and related regressions**

```bash
uv run finproof evaluate --suite organizer_20260824 --output artifacts/evaluation/organizer-20260824.json
uv run pytest tests/unit/evaluation/test_organizer_case_suite.py tests/integration/evaluation/test_organizer_runner.py tests/evaluation -q
```

- [ ] **Step 5: Run API, fault, load, and container checks**

```bash
uv run pytest tests/e2e tests/integration/api tests/integration/evaluation/test_fault_injection.py tests/performance/test_api_load.py -q
uv run pytest tests/contract/test_competition_compliance.py -q
uv run python tools/check_competition_compliance.py --check
uv run python tools/check_claim_evidence_report.py artifacts/evaluation/organizer-20260824.json
```

Run the configured 24-hour soak once against the final submitted endpoint candidate; retain its immutable report. The 300-second boundary is a no-response limit, while latency remains score-differentiated.

- [ ] **Step 6: Write the release-manifest RED and implement the A-005 resolution**

The manifest tool requires an explicit clean `covered_commit`. It reads and hashes behavior-sensitive files from that Git object, binds the image/artifact/evaluation hashes built from it, and never attempts to include its own future metadata-commit hash. Tests must prove that a manifest created in a child working tree verifies the parent object, that worktree substitution cannot change covered bytes, that an unknown/non-ancestor/dirty covered candidate is rejected, and that changing a covered Git object or bound image/artifact hash fails verification.

```bash
uv run pytest tests/contract/test_release_manifest.py -q
```

- [ ] **Step 7: Commit the exact Task 10 candidate paths**

Stage only the new August suite, its generated/reviewed August packets/results, the exact
Task 10 runtime repairs and tests (including renderer/serializer), the two loader/CLI files,
release/compliance implementation files, and immutable run reports produced by this task.
Do not use directory-wide staging and do not stage `evaluation/review_batches/*` or
historical corpus files.

```bash
git add evaluation/organizer_20260824 src/finproof/evaluation/loader.py src/finproof/cli/evaluate.py src/finproof/answer/renderer.py src/finproof/evidence/serializer.py tests/unit/answer/test_renderer.py tests/unit/evidence/test_serializer.py tests/unit/evaluation/test_organizer_case_suite.py tests/integration/evaluation/test_organizer_runner.py tests/contract/test_release_manifest.py tests/contract/test_competition_compliance.py tools/create_release_manifest.py tools/verify_release_manifest.py tools/check_competition_compliance.py tools/check_claim_evidence_report.py scripts/clean_room_reproduce.sh artifacts/evaluation/organizer-20260824.json artifacts/evaluation/final-load.json artifacts/evaluation/final-soak.json
git commit -m "chore: prepare refreshed FinProof release candidate"
bash scripts/clean_room_reproduce.sh . "$(git rev-parse HEAD)"
```

- [ ] **Step 8: Run final independent review and bounded correction rule**

Review the approved migration contract and the committed candidate diff. Block only on Critical/Important. Allow one focused correction/re-review wave; root-adjudicate any later finding. The exact corrected 0C/0I commit becomes `COVERED_COMMIT`; make no behavior/data/config/prompt/image change after this boundary.

- [ ] **Step 9: Run the mandatory full gate exactly once on clean `COVERED_COMMIT`**

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run pytest -q
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
```

If the review correction changed code before this gate, its focused tests and re-review happen first, so this remains the one final full gate. If any behavior/data/config/prompt/image change is nevertheless made afterward, run affected focused tests first and rerun this full gate exactly once; the previous commit is no longer `COVERED_COMMIT`.

- [ ] **Step 10: Generate metadata against the covered Git object, verify it, update closure docs once, and commit the metadata child**

Generate `release/manifest.json` with `--covered-commit "$COVERED_COMMIT"`; verification must read covered bytes from the Git object, not the current working tree. Batch the review/risk/submission/README closure and update `docs/implementation/STATUS.md` once with focused RED/GREEN evidence, 0C/0I verdict, the observed full-gate output, unresolved external coverage, covered commit/image/artifact hashes, and exact submission action. These are metadata-only changes in a child commit and do not alter the covered runtime candidate.

```bash
uv run python tools/create_release_manifest.py --covered-commit "$COVERED_COMMIT" --output release/manifest.json
uv run python tools/verify_release_manifest.py release/manifest.json
git add release/manifest.json docs/implementation/STATUS.md docs/review/INDEPENDENT_REVIEW.md docs/review/FINDING_CLOSURE.md docs/submission/SUBMISSION_CHECKLIST.md docs/submission/API_SCHEMA.md docs/submission/PROPOSAL_EVIDENCE_INDEX.md docs/submission/RELEASE_RECORD.md docs/09_RISK_REGISTER.md README.md
git commit -m "chore: seal refreshed FinProof release metadata"
```

The release tag points to this metadata child; `release/manifest.json.covered_commit` and every runtime/image/artifact hash continue to point to the verified parent candidate, so the manifest cannot stale itself.
