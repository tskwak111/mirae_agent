# mypy: disable-error-code="attr-defined,no-untyped-call,no-untyped-def"
"""Scale contracts for bounded artifact staging."""

import os
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from finproof.core.settings import Settings
from tests.helpers.xlsx import write_complete_bronze_repository

pytestmark = pytest.mark.performance


def _identity(settings: Settings):
    from finproof.data.artifacts.input_identity import (
        BuildInputIdentity,
        ResolvedBuildInputBundle,
        verify_build_inputs,
    )

    resolved = ResolvedBuildInputBundle.from_settings(settings)
    with verify_build_inputs(settings, resolved) as held:
        seal = held.issue_identity_seal()
    return BuildInputIdentity.from_verified(seal=seal)


def test_external_order_store_spills_and_orders_131073_rows_with_bounded_state(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExternalOrderRelation,
        ExternalOrderStoreTestLimits,
        _open_external_order_store_for_test,
    )

    settings = write_complete_bronze_repository(tmp_path / "repository")
    identity = _identity(settings)
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG, strict=True)
    total = 131_073
    payload = "x" * 512
    consumed = 0

    def unsorted_rows():
        nonlocal consumed
        for ordinal in range(total - 1, -1, -1):
            consumed += 1
            yield f"{ordinal:09d}", f"{ordinal:09d}:{payload}"

    with ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=identity,
    ) as session:
        with _open_external_order_store_for_test(
            owner=session,
            config=config,
            limits=ExternalOrderStoreTestLimits(
                batch_rows=65_536,
                memory_limit_bytes=128 * 1024 * 1024,
            ),
        ) as store:
            store.insert_batch(
                relation=ExternalOrderRelation.BRONZE_SOURCE_ROW,
                rows=unsorted_rows(),
            )
            assert consumed == total
            assert not hasattr(store, "spill_path")
            assert not hasattr(store, "workspace_path")
            assert store._connection.execute("SELECT current_setting('threads')").fetchone() == (1,)
            previous = ""
            observed = 0
            maximum_batch = 0
            spill_observed = bool(os.listdir(store._spill_fd))
            stop_observer = threading.Event()

            def observe_spill() -> None:
                nonlocal spill_observed
                while not stop_observer.is_set():
                    spill_observed = spill_observed or bool(os.listdir(store._spill_fd))
                    time.sleep(0.001)

            observer = threading.Thread(target=observe_spill)
            observer.start()
            try:
                for batch in store.iter_ordered_batches(
                    relation=ExternalOrderRelation.BRONZE_SOURCE_ROW
                ):
                    maximum_batch = max(maximum_batch, len(batch))
                    for key, value in batch:
                        assert key > previous
                        assert value.startswith(f"{key}:")
                        previous = key
                        observed += 1
            finally:
                stop_observer.set()
                observer.join()
            assert observed == total
            assert maximum_batch == 65_536
            assert spill_observed is True

        assert set(os.listdir(session._stage_fd)) == {"parquet"}
