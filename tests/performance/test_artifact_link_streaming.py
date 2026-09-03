"""Closed one-pass bounds for exact-link candidate/evidence processing."""

# mypy: disable-error-code="arg-type,attr-defined"

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pytest


def test_exact_link_candidate_and_evidence_pipeline_stays_within_closed_one_pass_bounds(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.links import (
        _build_link_and_evidence_records,
        _consume_candidate_batches,
        canonical_link_pair_tsv,
    )
    from finproof.data.artifacts.quality_persistence import StagedBoundedRelationVerifier
    from finproof.data.artifacts.serialization import canonical_record_json
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExactLinkCandidateJoinRow,
        ExactLinkCandidateStoreCustody,
        ExternalOrderRelation,
        ExternalOrderRow,
        ExternalOrderStoreTestLimits,
        _open_external_order_store_for_test,
    )
    from tests.helpers.artifacts import artifact_build_input_identity, artifact_staging_settings
    from tests.unit.data.artifacts.test_exact_links import _candidate

    class OnePassRows:
        def __init__(self, rows: tuple[ExternalOrderRow, ...]) -> None:
            self._rows = rows
            self.iterations = 0

        def __len__(self) -> int:
            raise AssertionError("candidate relation must not be sized or materialized")

        def __iter__(self) -> Iterator[ExternalOrderRow]:
            self.iterations += 1
            if self.iterations != 1:
                raise AssertionError("candidate relation was iterated twice")
            yield from self._rows

    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
    limits = ExternalOrderStoreTestLimits(batch_rows=7, memory_limit_bytes=1 << 20)

    def run_pipeline(*, reverse: bool) -> bytes:
        matches = tuple(
            _candidate(
                raw=f"MATCH-{index:03d}",
                left_id=f"L-{index:03d}",
                right_id=f"R-{index:03d}",
            )
            for index in range(217)
        )
        irrelevant_left = tuple(
            _candidate(raw=f"LEFT-{index:04d}", left_id=f"IL-{index:04d}").left
            for index in range(1_000)
        )
        irrelevant_right = tuple(
            _candidate(raw=f"RIGHT-{index:04d}", right_id=f"IR-{index:04d}").right
            for index in range(1_000)
        )
        lefts = (*irrelevant_left, *(candidate.left for candidate in matches))
        rights = (*irrelevant_right, *(candidate.right for candidate in matches))
        if reverse:
            lefts = tuple(reversed(lefts))
            rights = tuple(reversed(rights))
        left_rows = OnePassRows(
            tuple(
                ExternalOrderRow(
                    key=(item.identifier.raw_identifier, item.left_product_id),
                    payload_json=canonical_record_json(item),
                )
                for item in lefts
            )
        )
        right_rows = OnePassRows(
            tuple(
                ExternalOrderRow(
                    key=(item.identifiers[0].raw_identifier, item.right_product_id),
                    payload_json=canonical_record_json(item),
                )
                for item in rights
            )
        )
        settings = artifact_staging_settings(tmp_path / ("reverse" if reverse else "forward"))
        with ArtifactBuildSession.initialize(
            settings,
            VersionBundle(),
            ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
            input_identity=artifact_build_input_identity(settings),
        ) as session:
            store_context = _open_external_order_store_for_test(
                owner=session,
                config=config,
                limits=limits,
            )
            store = store_context.__enter__()
            store.insert_batch(
                relation=ExternalOrderRelation.EXACT_LINK_LEFT_CANDIDATE,
                rows=left_rows,
            )
            store.insert_batch(
                relation=ExternalOrderRelation.EXACT_LINK_RIGHT_CANDIDATE,
                rows=right_rows,
            )
            assert left_rows.iterations == right_rows.iterations == 1
            assert store._forced_spill_names[ExternalOrderRelation.EXACT_LINK_LEFT_CANDIDATE]
            assert store._forced_spill_names[ExternalOrderRelation.EXACT_LINK_RIGHT_CANDIDATE]
            custody = ExactLinkCandidateStoreCustody._issue(owner=session, store=store)
            candidates, maximum = _consume_candidate_batches(
                custody.iter_candidate_join_batches(),
                expected_links=217,
            )
            assert len(candidates) == 217
            assert maximum <= limits.batch_rows
            links, evidence = _build_link_and_evidence_records(candidates)
            assert len(links) == 217
            assert len(evidence) == 434
            custody.admit_exact_evidence(iter(evidence))
            verifier = StagedBoundedRelationVerifier.for_candidate_custody(custody)
            admitted = tuple(
                row
                for batch in custody.order_exact_link_evidence(verifier=verifier)
                for row in batch
            )
            assert admitted == evidence
            custody.close()
            return canonical_link_pair_tsv(links, expected_links=217)

    expected = b"".join(f"L-{index:03d}\tR-{index:03d}\n".encode() for index in range(217))
    assert run_pipeline(reverse=False) == run_pipeline(reverse=True) == expected

    conflict_rows: tuple[ExactLinkCandidateJoinRow, ...] = (
        _candidate(raw="A", left_id="L-DUP", right_id="R-1"),
        _candidate(raw="M", left_id="L-MID", right_id="R-MID"),
        _candidate(raw="Z", left_id="L-DUP", right_id="R-2"),
    )
    with pytest.raises(ArtifactContractError):
        _build_link_and_evidence_records(conflict_rows)

    wide_rows = (
        ("R-A", '{"fund_item_id":"R-A"}'),
        ("R-Z", '{"fund_item_id":"R-Z"}'),
        *((f"foreign-{index}", '{"foreign":"' + "x" * 4096 + '"}') for index in range(128)),
    )
    wide_batches = tuple(
        pa.record_batch(
            {
                "fund_item_id": [row[0] for row in wide_rows[offset : offset + 7]],
                "record_json": [row[1] for row in wide_rows[offset : offset + 7]],
            }
        )
        for offset in range(0, len(wide_rows), 7)
    )

    class OnePassBatches:
        def __init__(self) -> None:
            self.iterations = 0

        def __len__(self) -> int:
            raise AssertionError("wide batches must not be sized or retained")

        def __iter__(self) -> Iterator[pa.RecordBatch]:
            self.iterations += 1
            if self.iterations != 1:
                raise AssertionError("wide batches were iterated twice")
            yield from wide_batches

    batches = OnePassBatches()
    wide_limits = ExternalOrderStoreTestLimits(
        batch_rows=limits.batch_rows,
        memory_limit_bytes=16 << 20,
    )

    class Handle:
        @contextlib.contextmanager
        def iter_batches(self, *, batch_size: int) -> Iterator[Iterator[pa.RecordBatch]]:
            assert batch_size == wide_limits.batch_rows
            yield iter(batches)

    class Verification:
        handle = Handle()

    class Tables:
        def verification_for(self, staged_name: str) -> Verification:
            assert staged_name == "silver_fund_item"
            return Verification()

    class ConnectionProxy:
        def __init__(self, inner: Any, registered_rows: list[int] | None = None) -> None:
            self._inner = inner
            self.registered_rows = [] if registered_rows is None else registered_rows

        def __getattr__(self, name: str) -> Any:
            return getattr(self._inner, name)

        def cursor(self) -> ConnectionProxy:
            return ConnectionProxy(self._inner.cursor(), self.registered_rows)

        def register(self, name: str, batch: pa.RecordBatch) -> None:
            assert name == "finproof_staged_join_batch"
            self.registered_rows.append(batch.num_rows)
            self._inner.register(name, batch)

        def close(self) -> None:
            self._inner.close()

    settings = artifact_staging_settings(tmp_path / "wide-filter")
    with (
        ArtifactBuildSession.initialize(
            settings,
            VersionBundle(),
            ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
            input_identity=artifact_build_input_identity(settings),
        ) as session,
        _open_external_order_store_for_test(
            owner=session,
            config=config,
            limits=wide_limits,
        ) as store,
    ):
        connection = ConnectionProxy(store._connection)
        store._connection = connection
        observed = tuple(
            row
            for batch in store._iter_linked_record_json_batches(
                tables=Tables(),
                exact_ids=("R-A", "R-Z"),
                staged_name="silver_fund_item",
                join_table="join_linked_fund",
                id_column="fund_item_id",
                sql="SELECT i.exact_id, r.record_json FROM join_exact_ids AS i "
                "JOIN join_linked_fund AS r ON i.exact_id = r.fund_item_id ORDER BY 1",
            )
            for row in batch
        )
        assert tuple(row.key for row in observed) == (("R-A",), ("R-Z",))
        assert connection.registered_rows == [2]
        assert batches.iterations == 1
