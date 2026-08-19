"""Bounded final-inventory verifier regression."""

from pathlib import Path
from typing import Any, cast

import pytest

pytestmark = pytest.mark.performance


def test_final_quality_verifier_streams_official_row_scale_in_bounded_batches(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.reports import _FinalInventoryRelationVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS
    from tests.helpers.artifacts import write_database_artifact_tree
    from tests.integration.artifacts.test_artifact_equality import _quality_rows

    rows = _quality_rows()
    first = rows["bronze_source_row"][0]
    bronze_rows = tuple(
        first if index == 0 else first | {"source_row_number": index + 2}
        for index in range(145_393)
    )
    root = tmp_path / "artifacts"
    manifest = write_database_artifact_tree(
        root,
        rows | {"bronze_source_row": bronze_rows},
    )
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
        observed = verifier.verify_quality_to_bronze()
        assert 0 < verifier.max_batch_rows <= 65_536
    assert observed.total_issues == 1
    assert observed.matched_bronze_rows == 1


def test_final_linked_projection_scans_official_cell_scale_with_closed_live_bounds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import contextmanager

    import pyarrow as pa  # type: ignore[import-untyped]
    import pyarrow.compute as pc  # type: ignore[import-untyped]

    from finproof.data.artifacts import reports
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.reports import (
        ExactLinkedSide,
        _FinalInventoryRelationVerifier,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPECS
    from tests.helpers.artifacts import write_empty_database_artifact_tree
    from tests.integration.artifacts.test_artifact_equality import _linked_rows

    base_rows, domestic_base_id, fund_base_id = _linked_rows()
    domestic_base = base_rows["silver_domestic_listed_product"][0]
    fund_base = base_rows["silver_fund_item"][0]
    domestic_ids = tuple(f"KR7{index:09d}" for index in range(47))
    fund_ids = tuple(f"KR5{index:09d}" for index in range(47))
    selected = {
        "silver_domestic_listed_product": tuple(
            domestic_base
            | {
                "product_id": value,
                "record_json": cast(str, domestic_base["record_json"]).replace(
                    domestic_base_id, value
                ),
            }
            for value in domestic_ids
        ),
        "silver_fund_item": tuple(
            fund_base
            | {
                "fund_item_id": value,
                "ksd_id": value,
                "record_json": cast(str, fund_base["record_json"]).replace(fund_base_id, value),
            }
            for value in fund_ids
        ),
    }
    identifiers = {
        "silver_domestic_listed_product": domestic_ids,
        "silver_fund_item": fund_ids,
    }
    scanned = dict.fromkeys(identifiers, 0)
    parsed = dict.fromkeys(identifiers, 0)
    maximum_live_batches = 0
    live_batches = 0

    class SelectedBatch:
        def __init__(self, table_name: str, rows: tuple[dict[str, object], ...]) -> None:
            self._table_name = table_name
            self._rows = rows

        def to_pylist(self) -> list[dict[str, object]]:
            parsed[self._table_name] += len(self._rows)
            return list(self._rows)

    class ProjectedBatch:
        def __init__(self, table_name: str, num_rows: int, include_exact: bool) -> None:
            nonlocal live_batches, maximum_live_batches
            self._table_name = table_name
            self.num_rows = num_rows
            self._include_exact = include_exact
            live_batches += 1
            maximum_live_batches = max(maximum_live_batches, live_batches)

        def __del__(self) -> None:
            nonlocal live_batches
            live_batches -= 1

        def column(self, _name: str) -> Any:
            values = identifiers[self._table_name] if self._include_exact else ()
            return pa.array((*values, *("FOREIGN" for _ in range(self.num_rows - len(values)))))

        def filter(self, mask: object) -> SelectedBatch:
            scanned[self._table_name] += self.num_rows
            rows = selected[self._table_name] if pc.sum(mask).as_py() else ()
            return SelectedBatch(self._table_name, rows)

        def to_pylist(self) -> object:
            raise AssertionError("official-scale wide batch was materialized before filtering")

    @contextmanager
    def official_scale_batches(**kwargs: object) -> Any:
        spec = kwargs["spec"]
        table_name = cast(Any, spec).table_name
        remaining = 6_401_851

        def batches() -> Any:
            nonlocal remaining
            while remaining:
                size = min(65_536, remaining)
                remaining -= size
                yield ProjectedBatch(table_name, size, remaining == 0)

        yield batches()

    root = tmp_path / "artifacts"
    manifest = write_empty_database_artifact_tree(root)
    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        monkeypatch.setattr(reports, "_open_final_verified_batches", official_scale_batches)
        verifier = _FinalInventoryRelationVerifier._from_verified(
            inventory=inventory,
            tables=tables,
        )
        domestic = tuple(
            row
            for batch in verifier.iter_linked_record_json(
                side=ExactLinkedSide.DOMESTIC,
                exact_ids=domestic_ids,
            )
            for row in batch
        )
        fund = tuple(
            row
            for batch in verifier.iter_linked_record_json(
                side=ExactLinkedSide.FUND,
                exact_ids=fund_ids,
            )
            for row in batch
        )
        max_batch_rows = verifier.max_batch_rows
    assert tuple(row.product_id for row in domestic) == domestic_ids
    assert tuple(row.product_id for row in fund) == fund_ids
    assert scanned == dict.fromkeys(identifiers, 6_401_851)
    assert parsed == dict.fromkeys(identifiers, 47)
    assert maximum_live_batches <= 2
    assert max_batch_rows == 65_536


def test_final_evidence_projection_accepts_exact_47_link_371_locator_bound(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.reports import _FinalInventoryRelationVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS
    from tests.helpers.artifacts import write_database_artifact_tree
    from tests.integration.artifacts.test_artifact_equality import _evidence_rows

    base = _evidence_rows()
    evidence_base = base["gold_exact_cross_source_link_evidence"][0]
    cell_base = base["bronze_source_cell"][0]
    evidence: list[dict[str, object]] = []
    cells: list[dict[str, object]] = []
    locator_index = 0
    for link_index in range(47):
        count = 8 if link_index < 42 else 7
        for ordinal in range(count):
            source_row_number = locator_index + 2
            evidence.append(
                evidence_base
                | {
                    "link_id": f"{link_index:064x}",
                    "evidence_ordinal": ordinal,
                    "source_row_number": source_row_number,
                }
            )
            cells.append(cell_base | {"source_row_number": source_row_number})
            locator_index += 1
    rows = {
        "bronze_source_cell": tuple(cells),
        "gold_exact_cross_source_link_evidence": tuple(evidence),
    }
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
    assert locator_index == 371
    assert observed.matched_bronze_cells == 371
    assert observed.max_batch_rows <= 65_536
