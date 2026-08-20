"""Official expected-accepted Phase 1 artifact generation."""

from pathlib import Path

import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest

from finproof.data.artifacts.builder import ArtifactBuildOutcome
from tests.helpers.official_artifact_subprocess import OfficialArtifactSession

pytestmark = pytest.mark.source_contract


def _scan_bronze_cells_once(path: Path) -> tuple[int, int, int]:
    columns = (
        "source_table_order",
        "source_file",
        "source_sheet",
        "source_row_number",
        "source_column_number",
    )
    previous: tuple[int, str, str, int, int] | None = None
    active_row: tuple[int, str, str, int] | None = None
    active_cells = 0
    completed_rows = 0
    max_cells = 0
    total_cells = 0
    for batch in pq.ParquetFile(path).iter_batches(batch_size=65_536, columns=columns):
        arrays = tuple(batch.column(index) for index in range(5))
        for index in range(batch.num_rows):
            key = (
                int(arrays[0][index].as_py()),
                str(arrays[1][index].as_py()),
                str(arrays[2][index].as_py()),
                int(arrays[3][index].as_py()),
                int(arrays[4][index].as_py()),
            )
            assert previous is None or key > previous
            row_key = key[:4]
            if row_key != active_row:
                if active_row is not None:
                    completed_rows += 1
                    max_cells = max(max_cells, active_cells)
                active_row = row_key
                active_cells = 0
            active_cells += 1
            total_cells += 1
            previous = key
    if active_row is not None:
        completed_rows += 1
        max_cells = max(max_cells, active_cells)
    return total_cells, completed_rows, max_cells


def test_evaluation_build_accepts_official_expected_and_publishes(
    official_artifact_session: OfficialArtifactSession,
) -> None:
    import duckdb

    from finproof.data.artifacts.database import open_read_only_database
    from finproof.data.artifacts.expected_contract import ExpectedPhase1ArtifactContract
    from finproof.data.artifacts.manifest import ArtifactManifest
    from finproof.data.artifacts.resources import expected_phase1_contract_bytes

    root = official_artifact_session.root
    outcome = official_artifact_session.outcome

    assert type(outcome) is ArtifactBuildOutcome
    assert (
        ArtifactManifest.load(root / "manifest.json").verify(root).logical_contract
        == outcome.logical_contract
    )
    assert outcome.manifest == ArtifactManifest.load(root / "manifest.json")
    assert outcome.telemetry.model_dump(mode="json")["persistence_timestamp"] == (
        "2026-08-14T00:00:02.123456Z"
    )
    expected = ExpectedPhase1ArtifactContract.model_validate_json(
        expected_phase1_contract_bytes(),
        strict=True,
    )
    assert outcome.logical_contract.model_dump(mode="python") == expected.model_dump(mode="python")
    assert len(outcome.manifest.source_inputs) == 9
    assert len(outcome.manifest.files) == 14
    assert {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()} == {
        "manifest.json",
        *(file.path for file in outcome.manifest.files),
    }
    assert {table.name: table.row_count for table in outcome.logical_contract.tables} == {
        "bronze_source_column": 207,
        "bronze_source_row": 145_393,
        "bronze_source_cell": 6_401_851,
        "silver_bond_instrument": 42_394,
        "silver_domestic_listed_product": 1_733,
        "silver_overseas_listed_product": 5_646,
        "silver_fund_item": 11_138,
        "silver_fund_item_attribute": 95_618,
        "silver_quality_issue": 6_032,
        "gold_exact_cross_source_link": 47,
        "gold_exact_cross_source_link_evidence": 371,
    }
    assert _scan_bronze_cells_once(root / "parquet/bronze_source_cell.parquet") == (
        6_401_851,
        145_393,
        73,
    )
    connection = open_read_only_database(root / "finproof.duckdb")
    try:
        assert tuple(
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main' ORDER BY table_name"
            ).fetchall()
        ) == tuple(sorted(table.name for table in outcome.logical_contract.tables))
        assert connection.execute(
            "SELECT rule_id, source_table, source_row_number FROM silver_quality_issue "
            "WHERE quarantined ORDER BY source_table, source_row_number"
        ).fetchall() == [
            ("domestic_listed.product_id", "PREF01N001", 1155),
            ("public_fund.malformed_item", "PRFD01N001", 84563),
        ]
        assert connection.execute(
            "SELECT count(*) FROM gold_exact_cross_source_link "
            "WHERE matched_raw_identifier != trim(matched_raw_identifier)"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM gold_exact_cross_source_link AS link "
            "JOIN silver_domestic_listed_product AS product "
            "ON product.product_id = link.left_product_id "
            "WHERE product.product_type = 'ETN'"
        ).fetchone() == (0,)
        with pytest.raises(duckdb.Error):
            connection.execute("CREATE TABLE forbidden(id BIGINT)")
        with pytest.raises(duckdb.Error):
            connection.execute(f"ATTACH '{root / 'other.duckdb'}' AS other")
        with pytest.raises(duckdb.Error):
            connection.execute(f"COPY bronze_source_row TO '{root / 'rows.csv'}'")
    finally:
        connection.close()
    assert not (root / "other.duckdb").exists()
    assert not (root / "rows.csv").exists()
    assert outcome.logical_contract.exact_link_evidence_count == 371
    assert outcome.logical_contract.exact_link_pair_sha256 == (
        "8f1049ae6137dbd2141214248c9871f8c4dcced3fcb81cb7c72c2f0863d3a962"
    )
    assert not tuple(root.parent.glob(f".{root.name}.finproof-stage-*"))
