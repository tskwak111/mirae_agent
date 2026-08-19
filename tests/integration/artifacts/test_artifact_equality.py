"""CP7A concrete artifact equality and managed-root contracts."""

from collections.abc import Iterator
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

import pytest

from tests.helpers.artifacts import (
    artifact_build_input_identity,
    artifact_staging_settings,
    manifest_payload,
    write_artifact_tree,
    write_database_artifact_tree,
    write_empty_database_artifact_tree,
)


def test_candidate_core_verifier_consumes_managed_stage_root_without_path_or_private_field_access(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.manifest import ArtifactVerificationKernel

    manifest = write_artifact_tree(tmp_path / "artifacts")
    inventory = object()
    events: list[str] = []

    class InventoryContext(AbstractContextManager[object]):
        def __enter__(self) -> object:
            events.append("enter")
            return inventory

        def __exit__(self, *args: object) -> None:
            del args
            events.append("close")

    class Root:
        def open_inventory(self, *, manifest: object) -> InventoryContext:
            assert manifest is not None
            events.append("open")
            return InventoryContext()

    class Registry:
        def ordered_specs(self) -> tuple[()]:
            return ()

    class Tables:
        def verify_tables(self, **kwargs: Any) -> None:
            assert kwargs["inventory"] is inventory
            events.append("tables")
            raise RuntimeError("managed-root-stop")

    kernel = ArtifactVerificationKernel(
        table_registry=Registry(),
        table_verifier=cast(Any, Tables()),
        report_verifier=object(),  # type: ignore[arg-type]
        database_verifier=object(),  # type: ignore[arg-type]
        expected_comparator=None,
    )
    with pytest.raises(RuntimeError, match="managed-root-stop"):
        kernel.verify_candidate_core_from_root(
            manifest=manifest,
            root=Root(),  # type: ignore[arg-type]
        )
    assert events == ["open", "enter", "tables", "close"]


def test_candidate_manifest_retains_exact_build_input_identity_and_bound_source_hashes(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.manifest import (
        ArtifactFile,
        ArtifactManifest,
        ArtifactTable,
        ArtifactVersions,
    )

    settings = artifact_staging_settings(tmp_path / "repository")
    identity = artifact_build_input_identity(settings)
    other_settings = artifact_staging_settings(tmp_path / "other-repository")
    other_identity = artifact_build_input_identity(other_settings)
    payload = manifest_payload()
    try:
        manifest = ArtifactManifest.from_build(
            input_identity=identity,
            persistence_timestamp=payload["persistence_timestamp"],
            versions=ArtifactVersions.model_validate(payload["versions"], strict=True),
            files=tuple(
                ArtifactFile.model_validate(value, strict=True) for value in payload["files"]
            ),
            database_sha256=payload["database_sha256"],
            tables={
                name: ArtifactTable.model_validate(value, strict=True)
                for name, value in payload["tables"].items()
            },
            logical_hash=payload["logical_hash"],
        )
        assert manifest.source_inputs is identity.logical_inputs
        assert manifest.source_inputs[0].sha256 == identity.source_manifest_sha256
        assert manifest.source_inputs[1].sha256 == identity.schema_catalog_sha256
        manifest.require_build_input_identity(identity)
        with pytest.raises(ValueError, match="build input identity"):
            manifest.require_build_input_identity(other_identity)
        loaded = ArtifactManifest.model_validate_json(manifest.model_dump_json(), strict=True)
        with pytest.raises(ValueError, match="build input identity"):
            loaded.require_build_input_identity(identity)
    finally:
        identity.close()
        other_identity.close()


def test_database_equality_accepts_exact_tables_and_rejects_count_drift(
    tmp_path: Path,
) -> None:
    import duckdb

    from finproof.data.artifacts.database import verify_database_against_parquet
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    root = tmp_path / "artifacts"
    manifest = write_empty_database_artifact_tree(root)
    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        database_entry = inventory.declared_entries[0]
        verify_database_against_parquet(
            inventory=inventory,
            database_entry=database_entry,
            tables=tables,
        )

    connection = duckdb.connect(str(root / "finproof.duckdb"))
    try:
        connection.execute(
            "INSERT INTO bronze_source_column VALUES "
            "('1.0.0', DATE '2026-07-11', 0, 'PRBD01N001', 1, 'A', "
            "'field', 'string', 'x', 'Y', '이름', 'schema.xlsx', 1)"
        )
    finally:
        connection.close()
    payload = manifest.model_dump(mode="python")
    database_bytes = (root / "finproof.duckdb").read_bytes()
    import hashlib

    digest = hashlib.sha256(database_bytes).hexdigest()
    files = [dict(entry) for entry in payload["files"]]
    files[0]["size_bytes"] = len(database_bytes)
    files[0]["sha256"] = digest
    payload["files"] = tuple(files)
    payload["database_sha256"] = digest
    from finproof.data.artifacts.manifest import ArtifactManifest

    changed = ArtifactManifest.model_validate(payload, strict=True)
    (root / "manifest.json").write_text(changed.model_dump_json(), encoding="utf-8")
    with verify_declared_inventory(changed, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=changed,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        with pytest.raises(ValueError, match="DuckDB differs from Parquet"):
            verify_database_against_parquet(
                inventory=inventory,
                database_entry=inventory.declared_entries[0],
                tables=tables,
            )


def test_database_port_requires_exact_manifest_inventory_tables_and_logical_result(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.database import DuckDBArtifactDatabaseVerifier
    from finproof.data.artifacts.expected_contract import (
        ExpectedLogicalInput,
        ExpectedSemanticReport,
    )
    from finproof.data.artifacts.manifest import (
        ArtifactCoreVerificationResult,
        verify_declared_inventory,
    )
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    root = tmp_path / "artifacts"
    manifest = write_empty_database_artifact_tree(root)
    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        logical = ArtifactCoreVerificationResult(
            artifact_contract_version=manifest.artifact_contract_version,
            artifact_set_id=manifest.artifact_set_id,
            dataset_version=manifest.dataset_version,
            logical_inputs=tuple(
                ExpectedLogicalInput.model_validate(entry.model_dump(mode="python"), strict=True)
                for entry in manifest.source_inputs
            ),
            tables=tables.tables,
            reports=tuple(
                ExpectedSemanticReport(
                    report_id=cast(Literal["source_audit", "quality_summary"], report_id),
                    semantic_hash=next(
                        file.logical_hash for file in manifest.files if file.report_id == report_id
                    ),
                )
                for report_id in ("source_audit", "quality_summary")
            ),
            overall_manifest_logical_hash=manifest.logical_hash,
            exact_link_pair_sha256="8f1049ae6137dbd2141214248c9871f8c4dcced3fcb81cb7c72c2f0863d3a962",
            exact_link_evidence_count=371,
        )
        verifier = DuckDBArtifactDatabaseVerifier()
        verifier.verify_database(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
            tables=tables,
            logical=logical,
        )
        forged = ArtifactCoreVerificationResult.model_validate(
            logical.model_dump(mode="python")
            | {
                "tables": (
                    logical.tables[0].model_copy(
                        update={"row_count": logical.tables[0].row_count + 1}
                    ),
                    *logical.tables[1:],
                )
            },
            strict=True,
        )
        with pytest.raises((TypeError, ValueError)):
            verifier.verify_database(
                manifest=manifest,
                inventory=inventory,
                specs=TABLE_SPECS,
                tables=tables,
                logical=forged,
            )


def test_database_equality_rejects_same_count_cell_substitution(tmp_path: Path) -> None:
    import hashlib

    import duckdb

    from finproof.data.artifacts.database import verify_database_against_parquet
    from finproof.data.artifacts.manifest import (
        ArtifactManifest,
        verify_declared_inventory,
    )
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    root = tmp_path / "artifacts"
    manifest = write_database_artifact_tree(root, _quality_rows())
    connection = duckdb.connect(str(root / "finproof.duckdb"))
    try:
        connection.execute("UPDATE silver_quality_issue SET record_json = '{}' ")
    finally:
        connection.close()
    payload = manifest.model_dump(mode="python")
    database_bytes = (root / "finproof.duckdb").read_bytes()
    digest = hashlib.sha256(database_bytes).hexdigest()
    files = [dict(entry) for entry in payload["files"]]
    files[0]["size_bytes"] = len(database_bytes)
    files[0]["sha256"] = digest
    payload["files"] = tuple(files)
    payload["database_sha256"] = digest
    changed = ArtifactManifest.model_validate(payload, strict=True)
    (root / "manifest.json").write_text(changed.model_dump_json(), encoding="utf-8")
    with verify_declared_inventory(changed, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=changed,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        with pytest.raises(ValueError, match="DuckDB differs from Parquet"):
            verify_database_against_parquet(
                inventory=inventory,
                database_entry=inventory.declared_entries[0],
                tables=tables,
            )


def test_final_relation_verifier_accepts_only_exact_live_inventory_and_table_result(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.reports import _FinalInventoryRelationVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    with pytest.raises(TypeError, match="final inventory verifier"):
        _FinalInventoryRelationVerifier()
    root = tmp_path / "artifacts"
    manifest = write_empty_database_artifact_tree(root)
    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        verifier = _FinalInventoryRelationVerifier._from_verified(
            inventory=inventory,
            tables=tables,
        )
        assert type(verifier) is _FinalInventoryRelationVerifier
        with pytest.raises(TypeError, match="final inventory"):
            _FinalInventoryRelationVerifier._from_verified(
                inventory=inventory,
                tables=object(),  # type: ignore[arg-type]
            )


def _quality_rows() -> dict[str, tuple[dict[str, object], ...]]:
    from finproof.data.artifacts.quality_persistence import persist_quality_issue
    from finproof.data.artifacts.serialization import (
        BronzeSourceCellRecord,
        serialize_bronze_source_row,
        serialize_table_row,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from tests.helpers.source_rows import source_row
    from tests.unit.data.artifacts.test_quality_persistence import _issue

    timestamp = datetime(2026, 8, 15, tzinfo=UTC)
    source = source_row("PRBD01N001", excel_row=2)
    cell = source.cell("PD_NM")
    persisted = persist_quality_issue(_issue(), persistence_timestamp=timestamp)
    bronze_cell = BronzeSourceCellRecord(
        source_table_order=0,
        source_table=source.source_table,
        source_file=source.source_file,
        source_sheet=source.source_sheet,
        source_row_number=source.source_row_number,
        source_column_name=cell.column_name,
        source_column_number=cell.excel_column_number,
        source_column_letter=cell.excel_column_letter,
        source_checksum=source.source_checksum,
        source_snapshot_date=source.source_snapshot_date,
        source_applicable_date=cell.applicable_date,
        raw_value=cell.raw_value,
    )
    return {
        "bronze_source_row": (
            dict(
                serialize_bronze_source_row(
                    TABLE_SPEC_BY_NAME["bronze_source_row"],
                    source,
                    persistence_timestamp=timestamp,
                )
            ),
        ),
        "bronze_source_cell": (
            dict(
                serialize_table_row(
                    TABLE_SPEC_BY_NAME["bronze_source_cell"],
                    bronze_cell,
                )
            ),
        ),
        "silver_quality_issue": (
            dict(
                serialize_table_row(
                    TABLE_SPEC_BY_NAME["silver_quality_issue"],
                    persisted,
                )
            ),
        ),
    }


def test_final_relation_verifier_rebuilds_quality_join_from_reopened_final_handles(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.reports import _FinalInventoryRelationVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    root = tmp_path / "artifacts"
    manifest = write_database_artifact_tree(root, _quality_rows())
    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        verifier = _FinalInventoryRelationVerifier._from_verified(
            inventory=inventory,
            tables=tables,
        )
        observations = verifier.verify_quality_to_bronze()
        assert observations.total_issues == 1
        assert observations.matched_bronze_rows == 1
        assert observations.matched_bronze_cells == 1
        assert observations.quarantined_issue_count == 1
        assert observations.quarantined_source_row_count == 1
        assert observations.persistence_timestamp == manifest.persistence_timestamp
        assert (
            observations.quality_table_logical_hash
            == manifest.tables["silver_quality_issue"].logical_hash
        )


def _evidence_rows() -> dict[str, tuple[dict[str, object], ...]]:
    from finproof.data.artifacts.serialization import (
        BronzeSourceCellRecord,
        serialize_table_row,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from finproof.data.source_manifest import OFFICIAL_TABLE_IDS
    from tests.unit.data.artifacts.test_quality_persistence import _exact_evidence_rows

    evidence = _exact_evidence_rows()
    cells = tuple(
        BronzeSourceCellRecord(
            source_table_order=OFFICIAL_TABLE_IDS.index(row.source_table),
            source_table=row.source_table,
            source_file=row.source_file,
            source_sheet=row.source_sheet,
            source_row_number=row.source_row_number,
            source_column_name=row.source_column_name,
            source_column_number=row.source_column_number,
            source_column_letter=row.source_column_letter,
            source_checksum=row.source_checksum,
            source_snapshot_date=row.source_snapshot_date,
            source_applicable_date=row.source_applicable_date,
            raw_value=row.raw_identifier,
        )
        for row in evidence
    )
    return {
        "bronze_source_cell": tuple(
            dict(
                serialize_table_row(
                    TABLE_SPEC_BY_NAME["bronze_source_cell"],
                    row,
                )
            )
            for row in cells
        ),
        "gold_exact_cross_source_link_evidence": tuple(
            dict(
                serialize_table_row(
                    TABLE_SPEC_BY_NAME["gold_exact_cross_source_link_evidence"],
                    row,
                )
            )
            for row in evidence
        ),
    }


def test_final_relation_verifier_rebuilds_exact_evidence_join_from_reopened_final_handles(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.reports import _FinalInventoryRelationVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    root = tmp_path / "artifacts"
    manifest = write_database_artifact_tree(root, _evidence_rows())
    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        verifier = _FinalInventoryRelationVerifier._from_verified(
            inventory=inventory,
            tables=tables,
        )
        observations = verifier.verify_exact_evidence_to_bronze()
        assert observations.matched_bronze_cells == 2
        assert 0 < observations.max_batch_rows <= 65_536


def test_final_evidence_join_handles_link_order_independent_of_bronze_locator_order(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.reports import _FinalInventoryRelationVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    rows = _evidence_rows()
    evidence = rows["gold_exact_cross_source_link_evidence"]
    rows["gold_exact_cross_source_link_evidence"] = tuple(
        row | {"link_id": link_id} for link_id in ("0" * 64, "f" * 64) for row in evidence
    )
    root = tmp_path / "artifacts"
    manifest = write_database_artifact_tree(root, rows)
    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        observed = _FinalInventoryRelationVerifier._from_verified(
            inventory=inventory,
            tables=tables,
        ).verify_exact_evidence_to_bronze()
    assert observed.matched_bronze_cells == 4


def _linked_rows() -> tuple[
    dict[str, tuple[dict[str, object], ...]],
    str,
    str,
]:
    from finproof.data.artifacts.serialization import serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from tests.unit.data.artifacts.test_serialization import (
        _domestic_record,
        _fund_record,
    )

    domestic = _domestic_record()
    fund = _fund_record()
    domestic_id = str(domestic.product_id.normalized_value)
    fund_id = str(fund.fund_item_id.representative.normalized_value)
    return (
        {
            "silver_domestic_listed_product": (
                dict(
                    serialize_table_row(
                        TABLE_SPEC_BY_NAME["silver_domestic_listed_product"],
                        domestic,
                    )
                ),
            ),
            "silver_fund_item": (
                dict(
                    serialize_table_row(
                        TABLE_SPEC_BY_NAME["silver_fund_item"],
                        fund,
                    )
                ),
            ),
        },
        domestic_id,
        fund_id,
    )


def test_final_relation_verifier_filters_exact_linked_records_from_reopened_final_handles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.reports import (
        ExactLinkedSide,
        _FinalInventoryRelationVerifier,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    rows, domestic_id, fund_id = _linked_rows()
    root = tmp_path / "artifacts"
    manifest = write_database_artifact_tree(root, rows)
    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        verifier = _FinalInventoryRelationVerifier._from_verified(
            inventory=inventory,
            tables=tables,
        )
        domestic = tuple(
            row
            for batch in verifier.iter_linked_record_json(
                side=ExactLinkedSide.DOMESTIC,
                exact_ids=(domestic_id,),
            )
            for row in batch
        )
        fund = tuple(
            row
            for batch in verifier.iter_linked_record_json(
                side=ExactLinkedSide.FUND,
                exact_ids=(fund_id,),
            )
            for row in batch
        )
        assert tuple(row.product_id for row in domestic) == (domestic_id,)
        assert tuple(row.product_id for row in fund) == (fund_id,)
        with pytest.raises(ValueError, match="linked IDs"):
            tuple(
                verifier.iter_linked_record_json(
                    side=ExactLinkedSide.DOMESTIC,
                    exact_ids=("missing",),
                )
            )

        def reject_scan(*_args: object, **_kwargs: object) -> object:
            raise AssertionError("more than 47 linked IDs must fail before a table scan")

        monkeypatch.setattr(
            _FinalInventoryRelationVerifier,
            "_iter_exact_id_rows",
            reject_scan,
        )
        with pytest.raises(ValueError, match="linked IDs"):
            tuple(
                verifier.iter_linked_record_json(
                    side=ExactLinkedSide.DOMESTIC,
                    exact_ids=tuple(f"id-{index:02d}" for index in range(48)),
                )
            )


def test_final_linked_filter_does_not_materialize_irrelevant_wide_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import contextmanager

    import pyarrow as pa  # type: ignore[import-untyped]

    from finproof.data.artifacts import parquet_io, reports
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.reports import (
        ExactLinkedSide,
        _FinalInventoryRelationVerifier,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME, TABLE_SPECS

    rows, domestic_id, _ = _linked_rows()
    exact = rows["silver_domestic_listed_product"][0]
    irrelevant = exact | {"product_id": "FOREIGN", "record_json": "not-json"}
    batch = pa.RecordBatch.from_pylist(
        [irrelevant, exact],
        schema=parquet_io._arrow_schema(TABLE_SPEC_BY_NAME["silver_domestic_listed_product"]),
    )

    class GuardedBatch:
        num_rows = batch.num_rows

        def column(self, name: str) -> Any:
            return batch.column(name)

        def filter(self, mask: object) -> Any:
            return batch.filter(mask)

        def to_pylist(self) -> object:
            raise AssertionError("unfiltered wide batch materialized")

    @contextmanager
    def guarded_batches(**kwargs: object) -> Iterator[Iterator[GuardedBatch]]:
        del kwargs
        yield iter((GuardedBatch(),))

    root = tmp_path / "artifacts"
    manifest = write_empty_database_artifact_tree(root)
    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        monkeypatch.setattr(reports, "_open_final_verified_batches", guarded_batches)
        verifier = _FinalInventoryRelationVerifier._from_verified(
            inventory=inventory,
            tables=tables,
        )
        observed = tuple(
            row
            for selected in verifier.iter_linked_record_json(
                side=ExactLinkedSide.DOMESTIC,
                exact_ids=(domestic_id,),
            )
            for row in selected
        )
    assert tuple(row.product_id for row in observed) == (domestic_id,)
