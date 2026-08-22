"""Complete synthetic Task 5 artifact fixtures."""

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Final, Literal, cast

from finproof.data.artifacts.parquet_io import (
    StagedParquetHandle,
    StagedParquetSet,
    StagedParquetVerification,
)

TABLES: Final[tuple[tuple[str, str, int], ...]] = (
    ("bronze_source_column", "source_column", 207),
    ("bronze_source_row", "source_row", 145_393),
    ("bronze_source_cell", "source_cell", 6_401_851),
    ("silver_bond_instrument", "instrument", 42_394),
    ("silver_domestic_listed_product", "listed_product", 1_733),
    ("silver_overseas_listed_product", "listed_product", 5_646),
    ("silver_fund_item", "fund_item", 11_138),
    ("silver_fund_item_attribute", "fund_attribute", 95_618),
    ("silver_quality_issue", "quality_issue", 4),
    ("gold_exact_cross_source_link", "exact_cross_source_link", 47),
    (
        "gold_exact_cross_source_link_evidence",
        "exact_cross_source_link_evidence",
        371,
    ),
)

INPUTS: Final[tuple[tuple[str, str, str], ...]] = (
    ("source_root", "input_manifest.json", "source_manifest"),
    ("source_root", "schema_catalog.json", "source_schema_catalog"),
    ("repository", "config/artifact_build.yaml", "artifact_build_config"),
    ("repository", "config/datasets.yaml", "dataset_registry"),
    ("repository", "config/quality_rules.yaml", "quality_rule_registry"),
    ("repository", "config/rating_scale.yaml", "rating_scale_registry"),
    ("repository", "config/state_rules.yaml", "state_rule_registry"),
    (
        "repository",
        "schemas/artifact_manifest.schema.json",
        "artifact_manifest_schema",
    ),
    ("repository", "schemas/quality_issue.schema.json", "quality_issue_schema"),
)


def artifact_staging_settings(repository_root: Path) -> Any:
    """Create one complete synthetic repository Settings boundary."""
    from finproof.core.settings import Settings

    source_root = repository_root / "source_material"
    (source_root / "data").mkdir(parents=True)
    (source_root / "input_manifest.json").write_bytes(b"{}")
    (source_root / "schema_catalog.json").write_bytes(b"{}")
    config_root = repository_root / "config"
    config_root.mkdir()
    for name in (
        "artifact_build.yaml",
        "datasets.yaml",
        "quality_rules.yaml",
        "rating_scale.yaml",
        "state_rules.yaml",
    ):
        version = "1.1.0" if name == "state_rules.yaml" else "1.0.0"
        (config_root / name).write_text(f"version: {version}\n", encoding="utf-8")
    schema_root = repository_root / "schemas"
    schema_root.mkdir()
    for name in ("artifact_manifest.schema.json", "quality_issue.schema.json"):
        (schema_root / name).write_bytes(b"{}")
    return Settings(
        repository_root=repository_root,
        source_root=source_root,
        data_dir=source_root / "data",
        artifact_dir=repository_root / "artifacts",
        database_path=repository_root / "artifacts/finproof.duckdb",
        artifact_build_config_path=config_root / "artifact_build.yaml",
        expected_artifact_contract_path=config_root / "expected_phase1_artifacts.json",
    )


def artifact_build_input_identity(settings: Any) -> Any:
    """Issue one exact synthetic build-input identity."""
    from finproof.data.artifacts.input_identity import (
        BuildInputIdentity,
        ResolvedBuildInputBundle,
        verify_build_inputs,
    )

    resolved = ResolvedBuildInputBundle.from_settings(settings)
    with verify_build_inputs(settings, resolved) as held:
        seal = held.issue_identity_seal()
    return BuildInputIdentity.from_verified(seal=seal)


def expected_contract_payload(*, json_compatible: bool = False) -> dict[str, Any]:
    """Return one complete official-shaped Phase 1 logical contract fixture."""
    logical_inputs: tuple[dict[str, Any], ...] = tuple(
        {
            "namespace": namespace,
            "path": path,
            "kind": kind,
            "size_bytes": index + 1,
            "sha256": f"{index + 1:064x}",
        }
        for index, (namespace, path, kind) in enumerate(INPUTS)
    )
    tables: tuple[dict[str, Any], ...] = tuple(
        {
            "name": name,
            "grain": grain,
            "schema_hash": f"{index + 20:064x}",
            "row_count": row_count,
            "sort_key": ("id",),
            "unique_key": ("id",),
            "logical_hash": f"{index + 40:064x}",
        }
        for index, (name, grain, row_count) in enumerate(TABLES)
    )
    reports: tuple[dict[str, Any], ...] = (
        {"report_id": "source_audit", "semantic_hash": "a" * 64},
        {"report_id": "quality_summary", "semantic_hash": "b" * 64},
    )
    logical_inputs_output: object = logical_inputs
    tables_output: object = tables
    reports_output: object = reports
    dataset_version: object = date(2026, 7, 11)
    if json_compatible:
        logical_inputs_output = list(logical_inputs)
        tables_output = [
            {
                **table,
                "sort_key": list(table["sort_key"]),
                "unique_key": list(table["unique_key"]),
            }
            for table in tables
        ]
        reports_output = list(reports)
        dataset_version = "2026-07-11"
    return {
        "artifact_contract_version": "1.0.0",
        "artifact_set_id": "finproof-data-artifacts/v1",
        "dataset_version": dataset_version,
        "logical_inputs": logical_inputs_output,
        "tables": tables_output,
        "reports": reports_output,
        "overall_manifest_logical_hash": "c" * 64,
        "exact_link_pair_sha256": (
            "8f1049ae6137dbd2141214248c9871f8c4dcced3fcb81cb7c72c2f0863d3a962"
        ),
        "exact_link_evidence_count": 371,
    }


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def manifest_payload() -> dict[str, Any]:
    """Return one complete strict manifest payload with synthetic identities."""
    table_payloads: dict[str, Any] = {}
    for name, grain, row_count in sorted(TABLES):
        layer = name.split("_", maxsplit=1)[0]
        table_payloads[name] = {
            "table_name": name,
            "layer": layer,
            "grain": grain,
            "parquet_path": f"parquet/{name}.parquet",
            "row_count": row_count,
            "schema_sha256": _digest(f"schema:{name}"),
            "sort_key": ("id",),
            "unique_key": ("id",),
            "logical_hash": _digest(f"logical:{name}"),
        }

    files: list[dict[str, object]] = [
        {
            "path": "finproof.duckdb",
            "kind": "duckdb",
            "size_bytes": 8,
            "sha256": _digest("file:finproof.duckdb"),
            "report_id": None,
            "logical_hash": None,
        }
    ]
    for name, _, _ in TABLES:
        path = f"parquet/{name}.parquet"
        files.append(
            {
                "path": path,
                "kind": "parquet",
                "size_bytes": len(path.encode()),
                "sha256": _digest(f"file:{path}"),
                "report_id": None,
                "logical_hash": None,
            }
        )
    for report_id in ("source_audit", "quality_summary"):
        path = f"reports/{report_id}.json"
        files.append(
            {
                "path": path,
                "kind": "report",
                "size_bytes": len(path.encode()),
                "sha256": _digest(f"file:{path}"),
                "report_id": report_id,
                "logical_hash": _digest(f"report:{report_id}"),
            }
        )
    files.sort(key=lambda item: str(item["path"]))
    return {
        "manifest_version": "1.0.0",
        "artifact_contract_version": "1.0.0",
        "artifact_set_id": "finproof-data-artifacts/v1",
        "dataset_version": date(2026, 7, 11),
        "persistence_timestamp": datetime(2026, 8, 15, tzinfo=UTC),
        "source_inputs": tuple(
            {
                "namespace": namespace,
                "path": path,
                "kind": kind,
                "size_bytes": len(path.encode()),
                "sha256": _digest(f"input:{namespace}:{path}"),
            }
            for namespace, path, kind in INPUTS
        ),
        "versions": {
            "dataset_version": date(2026, 7, 11),
            "metric_registry_version": "1.0.0",
            "state_rule_version": "1.1.0",
            "quality_rule_version": "1.0.0",
            "rating_rule_version": "1.0.0",
            "answer_policy_version": "1.0.0",
            "planner_version": "1.0.0",
        },
        "files": tuple(files),
        "database_path": "finproof.duckdb",
        "database_sha256": _digest("file:finproof.duckdb"),
        "tables": table_payloads,
        "logical_hash": _digest("manifest:logical"),
    }


def write_artifact_tree(root: Path) -> Any:
    """Write one complete synthetic physical tree and return its strict manifest."""
    from finproof.data.artifacts.manifest import ArtifactManifest

    payload = manifest_payload()
    files = list(payload["files"])
    root.mkdir()
    (root / "parquet").mkdir()
    (root / "reports").mkdir()
    for entry in files:
        path = root / entry["path"]
        content = f"synthetic:{entry['path']}\n".encode()
        path.write_bytes(content)
        entry["size_bytes"] = len(content)
        entry["sha256"] = hashlib.sha256(content).hexdigest()
    database = next(entry for entry in files if entry["kind"] == "duckdb")
    payload["database_sha256"] = database["sha256"]
    payload["files"] = tuple(files)
    manifest = ArtifactManifest.model_validate(payload, strict=True)
    (root / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    return manifest


def write_empty_parquet_artifact_tree(root: Path) -> Any:
    """Write a complete CP2-valid tree with eleven empty real Parquet files."""
    import pyarrow as pa  # type: ignore[import-untyped]
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    from finproof.data.artifacts.hashing import schema_sha256, table_logical_hash
    from finproof.data.artifacts.manifest import ArtifactManifest
    from finproof.data.artifacts.parquet_io import _arrow_schema
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    payload = manifest_payload()
    files = [dict(entry) for entry in payload["files"]]
    root.mkdir()
    (root / "parquet").mkdir()
    (root / "reports").mkdir()

    tables: dict[str, object] = {}
    for spec in TABLE_SPECS:
        path = root / spec.parquet_path
        pq.write_table(
            pa.Table.from_pylist([], schema=_arrow_schema(spec)),
            path,
            compression="zstd",
            compression_level=3,
            write_statistics=True,
            data_page_size=1_048_576,
            row_group_size=65_536,
        )
        logical_hash = table_logical_hash(spec, row_count=0, rows=())
        tables[spec.table_name] = {
            "table_name": spec.table_name,
            "layer": spec.layer,
            "grain": spec.grain,
            "parquet_path": spec.parquet_path,
            "row_count": 0,
            "schema_sha256": schema_sha256(spec),
            "sort_key": spec.sort_key,
            "unique_key": spec.unique_key,
            "logical_hash": logical_hash,
        }

    for entry in files:
        path = root / str(entry["path"])
        if entry["kind"] != "parquet":
            path.write_bytes(f"synthetic:{entry['path']}\n".encode())
        content = path.read_bytes()
        entry["size_bytes"] = len(content)
        entry["sha256"] = hashlib.sha256(content).hexdigest()
    database = next(entry for entry in files if entry["kind"] == "duckdb")
    payload["database_sha256"] = database["sha256"]
    payload["files"] = tuple(files)
    payload["tables"] = {name: tables[name] for name in sorted(tables)}
    manifest = ArtifactManifest.model_validate(payload, strict=True)
    (root / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    return manifest


def write_empty_database_artifact_tree(root: Path) -> Any:
    """Write one complete tree whose DuckDB exactly matches eleven empty Parquets."""
    import duckdb

    from finproof.data.artifacts.manifest import ArtifactManifest
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    manifest = write_empty_parquet_artifact_tree(root)
    database_path = root / "finproof.duckdb"
    database_path.unlink()
    connection = duckdb.connect(str(database_path))
    try:
        for spec in TABLE_SPECS:
            columns = ", ".join(
                f'"{column.name}" {column.duckdb_type}' + ("" if column.nullable else " NOT NULL")
                for column in spec.columns
            )
            connection.execute(f'CREATE TABLE "{spec.table_name}" ({columns})')
    finally:
        connection.close()
    payload = manifest.model_dump(mode="python")
    content = database_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    files = [dict(entry) for entry in payload["files"]]
    files[0]["size_bytes"] = len(content)
    files[0]["sha256"] = digest
    payload["files"] = tuple(files)
    payload["database_sha256"] = digest
    updated = ArtifactManifest.model_validate(payload, strict=True)
    (root / "manifest.json").write_text(updated.model_dump_json(), encoding="utf-8")
    return updated


def write_database_artifact_tree(
    root: Path,
    rows_by_table: dict[str, tuple[dict[str, object], ...]],
) -> Any:
    """Write one small complete Parquet/DuckDB-equivalent CP7 fixture tree."""
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq

    from finproof.data.artifacts.hashing import schema_sha256, table_logical_hash
    from finproof.data.artifacts.manifest import ArtifactManifest
    from finproof.data.artifacts.parquet_io import _arrow_schema
    from finproof.data.artifacts.serialization import logical_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    payload = manifest_payload()
    files = [dict(entry) for entry in payload["files"]]
    root.mkdir()
    (root / "parquet").mkdir()
    (root / "reports").mkdir()
    tables: dict[str, object] = {}
    arrow_tables: dict[str, pa.Table] = {}
    for spec in TABLE_SPECS:
        rows = rows_by_table.get(spec.table_name, ())
        table = pa.Table.from_pylist(list(rows), schema=_arrow_schema(spec))
        arrow_tables[spec.table_name] = table
        pq.write_table(
            table,
            root / spec.parquet_path,
            compression="zstd",
            compression_level=3,
            write_statistics=True,
            data_page_size=1_048_576,
            row_group_size=65_536,
        )
        tables[spec.table_name] = {
            "table_name": spec.table_name,
            "layer": spec.layer,
            "grain": spec.grain,
            "parquet_path": spec.parquet_path,
            "row_count": len(rows),
            "schema_sha256": schema_sha256(spec),
            "sort_key": spec.sort_key,
            "unique_key": spec.unique_key,
            "logical_hash": table_logical_hash(
                spec,
                row_count=len(rows),
                rows=(logical_table_row(spec, row) for row in rows),
            ),
        }
    database_path = root / "finproof.duckdb"
    connection = duckdb.connect(str(database_path))
    try:
        for index, spec in enumerate(TABLE_SPECS):
            columns = ", ".join(
                f'"{column.name}" {column.duckdb_type}' + ("" if column.nullable else " NOT NULL")
                for column in spec.columns
            )
            connection.execute(f'CREATE TABLE "{spec.table_name}" ({columns})')
            table = arrow_tables[spec.table_name]
            if table.num_rows:
                name = f"_fixture_{index}"
                connection.register(name, table)
                try:
                    connection.execute(
                        f'INSERT INTO "{spec.table_name}" SELECT * FROM "{name}"'  # noqa: S608 -- test-only closed spec identifiers
                    )
                finally:
                    connection.unregister(name)
    finally:
        connection.close()
    for entry in files:
        path = root / str(entry["path"])
        if entry["kind"] == "report":
            path.write_bytes(f"synthetic:{entry['path']}\n".encode())
        content = path.read_bytes()
        entry["size_bytes"] = len(content)
        entry["sha256"] = hashlib.sha256(content).hexdigest()
    database = files[0]
    payload["database_sha256"] = database["sha256"]
    payload["files"] = tuple(files)
    payload["tables"] = {name: tables[name] for name in sorted(tables)}
    manifest = ArtifactManifest.model_validate(payload, strict=True)
    (root / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    return manifest


def write_report_artifact_tree(
    root: Path,
    rows_by_table: dict[str, tuple[dict[str, object], ...]],
) -> Any:
    """Write one small complete tree with strict internally consistent reports."""
    from finproof.data.artifacts.expected_contract import (
        ExpectedLogicalInput,
        ExpectedLogicalTable,
        ExpectedSemanticReport,
    )
    from finproof.data.artifacts.hashing import manifest_logical_hash, report_logical_hash
    from finproof.data.artifacts.links import (
        canonical_link_pair_tsv,
        exact_link_pair_sha256,
    )
    from finproof.data.artifacts.manifest import ArtifactManifest, _ManifestLogicalProjection
    from finproof.data.artifacts.reports import (
        ExcludedSilverCount,
        ExpectedObservedCount,
        ExpectedObservedSha256,
        NamedExpectedObservedCount,
        QualityJoinObservations,
        QualitySummaryReport,
        SourceAuditReport,
        SourceTableAudit,
    )
    from finproof.data.artifacts.serialization import ExactCrossSourceLinkRecord
    from finproof.data.source_manifest import OFFICIAL_TABLE_IDS
    from finproof.domain.quality import DataQualityIssue

    manifest = write_database_artifact_tree(root, rows_by_table)
    source_tables = tuple(
        SourceTableAudit(
            source_table=cast(
                Literal["PRBD01N001", "PREF01N001", "PREF02N001", "PRFD01N001"],
                table,
            ),
            expected_rows=sum(
                row["source_table"] == table for row in rows_by_table.get("bronze_source_row", ())
            ),
            observed_rows=sum(
                row["source_table"] == table for row in rows_by_table.get("bronze_source_row", ())
            ),
            expected_columns=sum(
                row["source_table"] == table
                for row in rows_by_table.get("bronze_source_column", ())
            ),
            observed_columns=sum(
                row["source_table"] == table
                for row in rows_by_table.get("bronze_source_column", ())
            ),
            expected_cells=sum(
                row["source_table"] == table for row in rows_by_table.get("bronze_source_cell", ())
            ),
            observed_cells=sum(
                row["source_table"] == table for row in rows_by_table.get("bronze_source_cell", ())
            ),
        )
        for table in OFFICIAL_TABLE_IDS
    )
    silver_names = (
        ("bond_instrument", "silver_bond_instrument"),
        ("domestic_listed_product", "silver_domestic_listed_product"),
        ("overseas_listed_product", "silver_overseas_listed_product"),
        ("fund_item", "silver_fund_item"),
        ("fund_item_attribute", "silver_fund_item_attribute"),
    )
    silver_tables = tuple(
        NamedExpectedObservedCount(
            name=cast(
                Literal[
                    "bond_instrument",
                    "domestic_listed_product",
                    "overseas_listed_product",
                    "fund_item",
                    "fund_item_attribute",
                ],
                name,
            ),
            expected=len(rows_by_table.get(table_name, ())),
            observed=len(rows_by_table.get(table_name, ())),
        )
        for name, table_name in silver_names
    )
    quality_issues = tuple(
        DataQualityIssue.model_validate_json(str(row["record_json"]), strict=True)
        for row in rows_by_table.get("silver_quality_issue", ())
    )
    quarantined_rows = len(
        {
            (
                issue.source.source_table,
                issue.source.source_file,
                issue.source.source_sheet,
                issue.source.source_row_number,
            )
            for issue in quality_issues
            if issue.quarantined
        }
    )
    link_count = len(rows_by_table.get("gold_exact_cross_source_link", ()))
    evidence_count = len(rows_by_table.get("gold_exact_cross_source_link_evidence", ()))
    link_models = tuple(
        ExactCrossSourceLinkRecord.model_validate(row, strict=True)
        for row in rows_by_table.get("gold_exact_cross_source_link", ())
    )
    pair_hash = exact_link_pair_sha256(
        canonical_link_pair_tsv(link_models, expected_links=link_count)
    )
    source_report = SourceAuditReport(
        report_id="source_audit",
        report_contract_version="1.0.0",
        artifact_contract_version="1.0.0",
        source_snapshot_date=manifest.dataset_version,
        source_manifest_sha256=manifest.source_inputs[0].sha256,
        schema_catalog_sha256=manifest.source_inputs[1].sha256,
        source_tables=source_tables,
        silver_tables=silver_tables,
        quarantine_source_rows=ExpectedObservedCount(
            expected=quarantined_rows,
            observed=quarantined_rows,
        ),
        exact_links=ExpectedObservedCount(expected=link_count, observed=link_count),
        exact_link_evidence=ExpectedObservedCount(
            expected=evidence_count,
            observed=evidence_count,
        ),
        exact_link_pair_sha256=ExpectedObservedSha256(
            expected=pair_hash,
            observed=pair_hash,
        ),
    )
    quality_hash = manifest.tables["silver_quality_issue"].logical_hash
    total = len(quality_issues)
    observations = QualityJoinObservations(
        total_issues=total,
        distinct_issue_ids=total,
        matched_bronze_rows=total,
        matched_bronze_cells=total,
        distinct_affected_source_rows=len(
            {
                (
                    issue.source.source_table,
                    issue.source.source_file,
                    issue.source.source_sheet,
                    issue.source.source_row_number,
                )
                for issue in quality_issues
            }
        ),
        quarantined_issue_count=sum(issue.quarantined for issue in quality_issues),
        quarantined_source_row_count=quarantined_rows,
        persistence_timestamp=manifest.persistence_timestamp,
        quality_table_logical_hash=quality_hash,
    )
    quality_report = QualitySummaryReport.from_verified_quality(
        issues=quality_issues,
        join_observations=observations,
        excluded_silver_records=tuple(
            ExcludedSilverCount(
                grain=cast(
                    Literal["instrument", "listed_product", "fund_item", "fund_attribute"],
                    grain,
                ),
                count=count,
            )
            for grain, count in (
                (
                    "fund_attribute",
                    source_tables[3].observed_rows
                    - len(rows_by_table.get("silver_fund_item_attribute", ())),
                ),
                (
                    "instrument",
                    source_tables[0].observed_rows
                    - len(rows_by_table.get("silver_bond_instrument", ())),
                ),
                (
                    "listed_product",
                    source_tables[1].observed_rows
                    + source_tables[2].observed_rows
                    - len(rows_by_table.get("silver_domestic_listed_product", ()))
                    - len(rows_by_table.get("silver_overseas_listed_product", ())),
                ),
            )
            if count > 0
        ),
    )
    reports = (source_report, quality_report)
    files = [dict(entry) for entry in manifest.model_dump(mode="python")["files"]]
    for report in reports:
        path = root / "reports" / f"{report.report_id}.json"
        path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        content = path.read_bytes()
        entry = next(value for value in files if value["report_id"] == report.report_id)
        entry["size_bytes"] = len(content)
        entry["sha256"] = hashlib.sha256(content).hexdigest()
        entry["logical_hash"] = report_logical_hash(report)
    report_entries = tuple(
        ExpectedSemanticReport(
            report_id=report.report_id,
            semantic_hash=report_logical_hash(report),
        )
        for report in reports
    )
    logical_tables = tuple(
        ExpectedLogicalTable(
            name=manifest.tables[spec_name].table_name,
            grain=manifest.tables[spec_name].grain,
            schema_hash=manifest.tables[spec_name].schema_sha256,
            row_count=manifest.tables[spec_name].row_count,
            sort_key=manifest.tables[spec_name].sort_key,
            unique_key=manifest.tables[spec_name].unique_key,
            logical_hash=manifest.tables[spec_name].logical_hash,
        )
        for spec_name, _, _ in TABLES
    )
    inputs = tuple(
        ExpectedLogicalInput.model_validate(item.model_dump(mode="python"), strict=True)
        for item in manifest.source_inputs
    )
    logical_hash = manifest_logical_hash(
        _ManifestLogicalProjection(
            manifest_version=manifest.manifest_version,
            artifact_contract_version=manifest.artifact_contract_version,
            artifact_set_id=manifest.artifact_set_id,
            dataset_version=manifest.dataset_version,
            logical_inputs=inputs,
            versions=manifest.versions,
            tables=logical_tables,
            reports=report_entries,
        )
    )
    payload = manifest.model_dump(mode="python")
    payload["files"] = tuple(files)
    payload["logical_hash"] = logical_hash
    updated = ArtifactManifest.model_validate(payload, strict=True)
    (root / "manifest.json").write_text(updated.model_dump_json(), encoding="utf-8")
    return updated


class TestUniqueKeyIndex:
    """Bounded test double for the owner-managed unique index capability."""

    __test__ = False

    def __init__(self) -> None:
        self._keys: list[bytes] = []

    def insert_canonical_batch(self, keys: tuple[bytes, ...]) -> None:
        self._keys.extend(keys)

    def assert_unique(self) -> None:
        if len(self._keys) != len(set(self._keys)):
            raise ValueError("duplicate unique key")


class TestVerificationWorkspace:
    """Owner-issued pathless verification-workspace test double."""

    __test__ = False

    def __init__(self) -> None:
        self.unchanged = True

    def create_unique_key_index(self, *, limits: Any) -> Any:
        from contextlib import contextmanager

        @contextmanager
        def opened() -> Any:
            assert limits.batch_rows > 0
            yield TestUniqueKeyIndex()

        return opened()

    def assert_unchanged(self) -> None:
        if not self.unchanged:
            raise ValueError("verification workspace changed")


class TestStageParquetLeaf:
    """Filesystem-backed exact-leaf test capability."""

    __test__ = False

    def __init__(self, root: Path, table_name: str) -> None:
        from pathlib import PurePosixPath

        self._root = root
        self.table_name = table_name
        self.relative_path = PurePosixPath(f"parquet/{table_name}.parquet")
        self._identity: tuple[int, int, int, int, int] | None = None

    def _path(self) -> Path:
        return self._root.joinpath(*self.relative_path.parts)

    def create_exclusive(self) -> Any:
        from contextlib import contextmanager

        @contextmanager
        def opened() -> Any:
            import os
            import stat

            path = self._path()
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(path, flags, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                yield stream
            observed = path.stat(follow_symlinks=False)
            if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
                raise ValueError("stage leaf must be one exact regular inode")
            self._identity = (
                observed.st_dev,
                observed.st_ino,
                observed.st_size,
                stat.S_IFMT(observed.st_mode),
                observed.st_nlink,
            )

        return opened()

    def open_verified(self) -> Any:
        from contextlib import contextmanager

        @contextmanager
        def opened() -> Any:
            import os

            self.assert_unchanged()
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self._path(), flags)
            with os.fdopen(descriptor, "rb") as stream:
                yield stream
            self.assert_unchanged()

        return opened()

    def create_verification_workspace(self) -> Any:
        from contextlib import contextmanager

        @contextmanager
        def opened() -> Any:
            yield TestVerificationWorkspace()

        return opened()

    def assert_unchanged(self) -> None:
        import stat

        observed = self._path().stat(follow_symlinks=False)
        if self._identity != (
            observed.st_dev,
            observed.st_ino,
            observed.st_size,
            stat.S_IFMT(observed.st_mode),
            observed.st_nlink,
        ):
            raise ValueError("stage leaf changed")

    def unlink_if_exact_writer_owned(self) -> None:
        self.assert_unchanged()
        self._path().unlink()


class TestStageArtifactOwner:
    """Exact object-identity registry test owner for CP3 staged capabilities."""

    __test__ = False

    def __init__(self, root: Path, persistence_timestamp: datetime) -> None:
        self._root = root
        self.persistence_timestamp = persistence_timestamp
        self._live = True
        self._leaves: list[TestStageParquetLeaf] = []
        self._pairs: dict[int, tuple[object, object, object, tuple[object, ...]]] = {}
        self._sets: dict[int, tuple[object, object]] = {}

    def claim_parquet_leaf(self, table_name: str) -> TestStageParquetLeaf:
        leaf = TestStageParquetLeaf(self._root, table_name)
        self._leaves.append(leaf)
        return leaf

    def assert_live(self) -> None:
        if not self._live:
            raise ValueError("stage owner closed")

    def close(self) -> None:
        self._live = False

    def require_owned_parquet_leaf(self, leaf: Any) -> None:
        self.assert_live()
        if not any(item is leaf for item in self._leaves):
            raise ValueError("foreign stage leaf")
        leaf.assert_unchanged()

    def _register_staged_verification(
        self,
        value: "StagedParquetVerification",
        handle: "StagedParquetHandle",
    ) -> object:
        token = object()
        self._pairs[id(value)] = (
            value,
            handle,
            token,
            self._staged_pair_fingerprint(value, handle),
        )
        return token

    @staticmethod
    def _staged_pair_fingerprint(value: Any, handle: Any) -> tuple[object, ...]:
        try:
            return (
                value.logical.model_dump_json(),
                id(value._leaf),
                value._relative_path,
                value._leaf_identity,
                value.physical_size_bytes,
                value.physical_sha256,
                handle.table_name,
                id(handle._leaf),
                handle._relative_path,
                handle._leaf_identity,
                handle.row_count,
                handle.schema_sha256,
                handle.logical_hash,
                handle.physical_size_bytes,
                handle.physical_sha256,
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("unregistered staged verification") from exc

    def _require_registered_staged_verification(
        self,
        value: "StagedParquetVerification",
        handle: "StagedParquetHandle",
        token: object,
    ) -> None:
        pair = self._pairs.get(id(value))
        if (
            pair is None
            or pair[0] is not value
            or pair[1] is not handle
            or pair[2] is not token
            or pair[3] != self._staged_pair_fingerprint(value, handle)
        ):
            raise ValueError("unregistered staged verification")

    def _require_registered_staged_handle(
        self,
        handle: "StagedParquetHandle",
        token: object,
    ) -> None:
        if not any(
            pair[1] is handle
            and pair[2] is token
            and pair[3] == self._staged_pair_fingerprint(pair[0], handle)
            for pair in self._pairs.values()
        ):
            raise ValueError("unregistered staged handle")

    def _register_staged_set(self, value: "StagedParquetSet") -> object:
        token = object()
        self._sets[id(value)] = (value, token)
        return token

    def _replace_registered_staged_set(
        self,
        previous: "StagedParquetSet",
        value: "StagedParquetSet",
    ) -> object:
        pair = self._sets.get(id(previous))
        if pair is None or pair[0] is not previous:
            raise ValueError("superseded staged set")
        token = self._register_staged_set(value)
        del self._sets[id(previous)]
        return token

    def _require_registered_staged_set(
        self,
        value: "StagedParquetSet",
        token: object,
    ) -> None:
        pair = self._sets.get(id(value))
        if pair is None or pair[0] is not value or pair[1] is not token:
            raise ValueError("unregistered staged set")
