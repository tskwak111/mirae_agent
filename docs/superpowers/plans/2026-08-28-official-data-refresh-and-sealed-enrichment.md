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
- Leave inactive until Task 7's final relation inventory is ready: `config/expected_phase1_artifacts.json`
- Modify: artifact unit/integration/source-contract tests under their existing paths

**Table delta:** add `silver_bond_sale_lot`; remove `silver_fund_item_attribute`; retain three Bronze tables, four native product tables, quality, and the two exact-link tables.

- [ ] **Step 1: Write table/serialization REDs**

```python
def test_refreshed_silver_inventory_contains_lots_not_fund_attribute_rows() -> None:
    names = tuple(spec.name for spec in TABLE_SPECS)
    assert "silver_bond_sale_lot" in names
    assert "silver_fund_item_attribute" not in names
```

Prove `record_json` round trips every lot and item field with exact lineage.

- [ ] **Step 2: Run RED and implement table specs/serialization**

```bash
uv run pytest tests/unit/data/artifacts/test_table_specs.py tests/unit/data/artifacts/test_serialization.py -q
```

- [ ] **Step 3: Write and close staged-emitter REDs**

Stage bond rows by parent ID/source key, emit every lot plus one parent, and emit one fund item per source row. Reuse the existing bounded staging custody instead of creating another storage layer.

```bash
uv run pytest tests/unit/data/artifacts/test_silver.py tests/unit/data/artifacts/test_staging.py tests/integration/artifacts/test_silver_fixture_build.py -q
```

- [ ] **Step 4: Regenerate exact links through the exact-only algorithm**

Use direct fund-item `ksd_itm_no` evidence. Candidate count 217 is audited input, not a hardcoded published output; the builder seals final link/evidence count and hashes.

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
git add src/finproof/data/artifacts schemas/artifact_manifest.schema.json tests/unit/data/artifacts tests/integration/artifacts tests/source_contract/test_official_exact_link_profile.py
git commit -m "feat: migrate refreshed artifact contracts"
```

---

### Task 7: Add sealed holdings and coverage relations

**Files:**

- Create: `src/finproof/data/holdings.py`
- Create: `tests/unit/data/test_holdings.py`
- Create: `source_material/external/README.md`
- Modify: `src/finproof/data/artifacts/table_specs.py`
- Modify: `src/finproof/data/artifacts/serialization.py`
- Modify: `src/finproof/data/artifacts/silver.py`
- Modify: `src/finproof/data/artifacts/builder.py`
- Modify: artifact tests for the two relations

**Interfaces:**

- `HoldingCoverageState = complete | partial_top_10 | unavailable`
- `HoldingRecord` and `HoldingCoverageRecord` strict models
- `admit_holding_snapshot(...) -> HoldingGeneration`

- [ ] **Step 1: Write admission/coverage REDs**

```python
def test_partial_coverage_allows_positive_match_but_not_negative_claim() -> None:
    generation = admitted_generation(state="partial_top_10", holdings=(holding("KR7005930003"),))
    assert generation.can_support_positive("KR7005930003")
    assert not generation.can_support_absence("KR7006600007")
```

Reject nonexact owner links, cutoff-late records, missing URL/hash/reuse basis, contradictory or falsely declared unit metadata, and declared generation count/hash drift. Preserve an unknown unit as unknown with lineage and a quality state; never guess, convert, rank, or aggregate it as a known unit.

- [ ] **Step 2: Run RED and implement the two strict records**

```bash
uv run pytest tests/unit/data/test_holdings.py -q
```

For product types without an admitted generation, emit explicit `unavailable` coverage rows. Do not fabricate holdings.

- [ ] **Step 3: Add only the two artifact relations**

```bash
uv run pytest tests/unit/data/artifacts/test_table_specs.py tests/unit/data/artifacts/test_serialization.py tests/unit/data/artifacts/test_silver.py tests/integration/artifacts/test_artifact_duckdb.py -q -k holding
```

- [ ] **Step 4: Build the single official candidate pair, seal the expected contract, and run the official aggregate**

Use the repository's existing candidate builder/publication flow. Candidate A and B use distinct injected UTC timestamps and must produce identical logical contract bytes. Generate `config/expected_phase1_artifacts.json` only from the verified final inventory. Any source with unresolved reuse permission remains unavailable; this does not block official-only queries or artifact publication.

```bash
uv run pytest tests/source_contract/test_official_artifact_build.py tests/source_contract/test_official_exact_link_profile.py tests/integration/artifacts/test_artifact_equality.py tests/integration/artifacts/test_artifact_duckdb.py -q
uv run python tools/audit_source_data.py --check
uv run python tools/verify_handoff.py
```

- [ ] **Step 5: Commit and independent review**

```bash
git add src/finproof/data/holdings.py src/finproof/data/artifacts source_material/external tests/unit/data tests/unit/data/artifacts tests/integration/artifacts config/expected_phase1_artifacts.json
git commit -m "feat: add sealed holdings coverage"
```

---

### Task 8: Add constituent filtering, coverage evidence, and overseas 1Y pruning

**Files:**

- Modify: `config/field_registry.yaml`
- Modify: `src/finproof/entity/models.py`
- Create: `src/finproof/entity/holding_resolver.py`
- Modify: `src/finproof/query/fields.py`
- Modify: `src/finproof/query/semantic_validator.py`
- Modify: `src/finproof/query/segmenter.py`
- Modify: `src/finproof/query/ast.py`
- Modify: `src/finproof/query/compiler.py`
- Modify: `src/finproof/domain/execution.py`
- Modify: `src/finproof/storage/repositories/evidence.py`
- Modify: `src/finproof/evidence/builder.py`
- Create: `tests/integration/query/test_cross_product_holding_query.py`
- Add/modify focused entity/query/evidence/security tests

**Contract:** `holding_constituent` supports only `eq` with one resolved constituent ID. SQL is one parameterized correlated `EXISTS` per native segment.

- [ ] **Step 1: Write resolver/registry REDs**

```python
def test_holding_constituent_supports_only_eq(field_registry) -> None:
    field = field_registry.require("holding_constituent")
    assert field.operators == (FilterOperator.EQ,)
```

Resolution order is exact admitted ID, unique normalized exact name, otherwise bounded clarification.

- [ ] **Step 2: Run RED and implement resolver/segment contract**

```bash
uv run pytest tests/unit/entity/test_holding_resolution.py tests/unit/query/test_field_registry.py tests/unit/query/test_semantic_validator.py tests/unit/query/test_execution_bundle.py -q
```

- [ ] **Step 3: Write SQL/security REDs and implement `EXISTS`**

```python
def test_holding_filter_compiles_parameterized_exists(compiler, segment) -> None:
    compiled = compiler.compile(segment)
    assert "EXISTS" in compiled.sql
    assert "silver_product_holding" in compiled.sql
    assert "삼성전자" not in compiled.sql
    assert compiled.parameters[-1] == "KR7005930003"
```

```bash
uv run pytest tests/unit/query/test_sql_compiler.py tests/security/test_query_injection.py tests/integration/query/test_holding_executor.py -q
```

- [ ] **Step 4: Write and close overseas 1Y segment-pruning RED**

For a domestic ETF + overseas ETF + public fund one-year-return plan, preserve domestic/public segments, omit overseas, and attach an explicit limitation. A single overseas one-year request remains unsupported.

```bash
uv run pytest tests/unit/query/test_execution_bundle.py tests/integration/query/test_executor.py -q -k 'overseas and return_1y'
```

- [ ] **Step 5: Bind coverage/evidence limitations**

Prove positive holdings evidence contains owner, exact crosswalk, holding, coverage, metric, rank/partition, and version facts; partial/unavailable coverage cannot yield a negative/exhaustive claim.

```bash
uv run pytest tests/unit/evidence/test_builder.py tests/unit/evidence/test_claim_verifier.py -q -k holding
```

- [ ] **Step 6: Write and close the cross-product end-to-end RED**

One organizer-shaped domestic ETF + overseas ETF + public-fund constituent query must produce independent native-grain segments, one parameterized correlated `EXISTS` per supported segment, the declared `top_k_scope`, no union over incompatible schemas, and coverage-qualified results. The test must include a positive partial-coverage match and an unavailable product type, and prove neither becomes an unsupported negative or exhaustive claim.

```bash
uv run pytest tests/integration/query/test_cross_product_holding_query.py -q
```

- [ ] **Step 7: Run bundle aggregate, commit, and review**

```bash
uv run pytest tests/unit/entity tests/unit/query tests/security/test_query_injection.py tests/integration/query tests/unit/evidence -q
git add config/field_registry.yaml src/finproof/entity/models.py src/finproof/entity/holding_resolver.py src/finproof/query src/finproof/domain/execution.py src/finproof/storage/repositories/evidence.py src/finproof/evidence tests/unit/entity tests/unit/query tests/security/test_query_injection.py tests/integration/query tests/unit/evidence
git commit -m "feat: query sealed constituent evidence"
```

---

### Task 9: Require HCX planning and verified HCX answer wording within 295 seconds

**Files:**

- Create: `src/finproof/answer/hcx_verbalizer.py`
- Create: `tests/unit/answer/test_hcx_verbalizer.py`
- Modify: `src/finproof/domain/answers.py`
- Modify: `src/finproof/api/dependencies.py`
- Modify: `src/finproof/planner/service.py`
- Modify: `src/finproof/service/answer_service.py`
- Modify: `src/finproof/service/orchestrator.py`
- Modify: `src/finproof/service/limits.py`
- Modify: `src/finproof/evidence/verifier.py`
- Modify: `tests/integration/planner/test_live_hcx.py`
- Modify: planner/service/API/security tests

**Interfaces:**

- `HcxVerbalizer.verbalize(fact_pack, *, deadline) -> VerifiedWording`
- strict provider result: ordered `WordingSpan` objects; each span carries text plus its exact claim/limitation bindings, and application code alone joins verified spans into `answer`
- the fact pack declares `required_claim_ids` and `required_limitation_ids`; publication requires complete material coverage, not an arbitrary valid subset
- one planning repair, one wording repair, then the existing fixed non-substantive safe response
- one monotonic outer deadline: request start + 295 seconds, shared by planner, execution, verbalizer, both repairs, and reserved safe-response serialization

- [ ] **Step 1: Write planner-composition REDs**

Evaluation composition without HCX credentials/readiness must fail closed; it may not instantiate `RuleFallbackPlanner`. One invalid HCX plan receives one repair and a second invalid response becomes a safe evaluation response.

```bash
uv run pytest tests/integration/planner/test_planner_service.py tests/security/test_runtime_provider_policy.py -q
```

- [ ] **Step 2: Implement mandatory evaluation planning**

Retain rule parsing only in an explicitly non-evaluation composition if existing tests require it. Never use another model.

- [ ] **Step 3: Write verbalizer/claim REDs**

```python
def test_unlisted_claim_id_is_rejected(verifier, fact_pack) -> None:
    wording = VerifiedWording(spans=(wording_span("...", claim_ids=("unknown",)),))
    with pytest.raises(ClaimVerificationError):
        verifier.verify_wording(wording, fact_pack)
```

Add executable REDs in which a span cites a valid claim ID but changes its numeric value, invents a product/entity, reverses a comparison or rank, or omits a required limitation. Each must fail. Also reject unbound prefix/suffix text and any final answer not equal to the exact ordered join of verified spans. Bind each span deterministically to the cited fact-pack claim signatures—entity IDs/names, exact normalized/display values and units, rank/tie/partition, comparison relation and operands, and required omission/warning codes—rather than trusting HCX's self-reported IDs.

- [ ] **Step 4: Implement HCX fact-pack wording and one repair**

Use the existing HCX transport/schema parsing. Keep deterministic rendering only as internal fact-pack/claim construction and material-span verification, not as a substantive fallback answer. The verifier is conservative: any material token or relation that cannot be bound to the cited claim fails and triggers the one wording repair.

```bash
uv run pytest tests/unit/answer/test_hcx_verbalizer.py tests/unit/evidence/test_claim_verifier.py tests/integration/service/test_answer_service.py -q
```

- [ ] **Step 5: Write fake-clock deadline/safe-response REDs and implement 295 seconds**

With an injected monotonic fake clock, prove the same exact request-start + 295-second deadline reaches planning, planning repair, deterministic execution, wording, and wording repair; no stage resets the budget. Prove a configured serialization reserve prevents another provider call and still returns the centralized safe response before the outer deadline.

```bash
uv run pytest tests/unit/service/test_limits.py tests/integration/service/test_orchestrator_fallbacks.py tests/integration/api/test_answer_endpoint.py -q
```

- [ ] **Step 6: Run live-HCX focused acceptance without printing the key**

```bash
uv run pytest tests/integration/planner/test_live_hcx.py -q -k 'planner or verbalizer'
```

The live acceptance must exercise both planner and wording schemas, including one verified material binding, without printing the key. If the selected HCX model cannot satisfy either strict schema after its allowed repair, stop under the repository contract.

- [ ] **Step 7: Commit and independent review**

```bash
git add src/finproof/answer src/finproof/domain/answers.py src/finproof/api/dependencies.py src/finproof/planner/service.py src/finproof/service src/finproof/evidence/verifier.py tests/unit/answer tests/unit/evidence/test_claim_verifier.py tests/integration/planner tests/integration/service tests/integration/api tests/security/test_runtime_provider_policy.py
git commit -m "feat: require verified HCX answer pipeline"
```

---

### Task 10: Build the 35-case suite and close release verification

**Files:**

- Create: `evaluation/organizer_20260824/*.jsonl`
- Create: `tests/unit/evaluation/test_organizer_case_suite.py`
- Create: `tests/integration/evaluation/test_organizer_runner.py`
- Modify: `src/finproof/evaluation/loader.py`
- Modify: `src/finproof/cli/evaluate.py`
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

Stage only the new August suite, its generated/reviewed August packets/results, the two loader/CLI files, exact Task 10 tests, release/compliance implementation files, and immutable run reports produced by this task. Do not use directory-wide staging and do not stage `evaluation/review_batches/*` or historical corpus files.

```bash
git add evaluation/organizer_20260824 src/finproof/evaluation/loader.py src/finproof/cli/evaluate.py tests/unit/evaluation/test_organizer_case_suite.py tests/integration/evaluation/test_organizer_runner.py tests/contract/test_release_manifest.py tests/contract/test_competition_compliance.py tools/create_release_manifest.py tools/verify_release_manifest.py tools/check_competition_compliance.py tools/check_claim_evidence_report.py scripts/clean_room_reproduce.sh artifacts/evaluation/organizer-20260824.json artifacts/evaluation/final-load.json artifacts/evaluation/final-soak.json
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
