# mypy: disable-error-code="assignment,attr-defined,misc,no-untyped-def"
"""Descriptor-owned artifact staging contracts."""

from __future__ import annotations

import contextlib
import inspect
import json
import os
import re
import stat
from collections.abc import Iterator
from copy import copy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from finproof.core.settings import Settings


def _staging_settings(repository_root: Path):
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
        (config_root / name).write_text("version: 1.0.0\n", encoding="utf-8")
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


def _input_identity(settings: Settings):
    from finproof.data.artifacts.input_identity import (
        BuildInputIdentity,
        ResolvedBuildInputBundle,
        verify_build_inputs,
    )

    resolved = ResolvedBuildInputBundle.from_settings(settings)
    with verify_build_inputs(settings, resolved) as held:
        seal = held.issue_identity_seal()
    return BuildInputIdentity.from_verified(seal=seal)


def test_staging_module_skeleton_rejects_valid_session_fixture(tmp_path: Path) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        CandidateStageCustody,
        ExternalOrderStore,
        OwnedCandidateStage,
    )

    for constructor in (
        ArtifactBuildSession,
        CandidateStageCustody,
        ExternalOrderStore,
        OwnedCandidateStage,
    ):
        with pytest.raises(TypeError):
            constructor()
    settings = _staging_settings(tmp_path / "repository")
    identity = _input_identity(settings)
    options = ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC))
    try:
        with ArtifactBuildSession.initialize(
            settings,
            VersionBundle(),
            options,
            input_identity=identity,
        ) as session:
            session.assert_live()
    finally:
        identity.close()


def test_artifact_module_ownership_excludes_identity_cycle_and_publication_transition_from_staging() -> (  # noqa: E501
    None
):
    from finproof.data.artifacts import builder, input_identity, manifest, staging
    from finproof.data.artifacts.builder import CandidateArtifactSet
    from finproof.data.artifacts.staging import (
        ExpectedAcceptedCustodyReceiver,
        TransferredCandidateCustody,
    )

    sources = {
        "manifest": inspect.getsource(manifest),
        "input_identity": inspect.getsource(input_identity),
        "staging": inspect.getsource(staging),
        "builder": inspect.getsource(builder),
    }
    assert "from finproof.data.artifacts.input_identity" not in sources["manifest"]
    assert "from finproof.data.artifacts.staging" not in sources["manifest"]
    assert "from finproof.data.artifacts.publication" not in sources["manifest"]
    assert "from finproof.data.artifacts.publication" not in sources["staging"]
    assert "from finproof.data.artifacts.manifest" in sources["input_identity"]
    assert "pathlib" not in sources["builder"]
    assert "import os" not in sources["builder"]
    assert "shutil" not in sources["builder"]
    assert "tempfile" not in sources["builder"]
    for source in sources.values():
        assert "_GLOBAL_REGISTRY" not in source
        assert "module_global_registry" not in source

    with pytest.raises(TypeError):
        CandidateArtifactSet()
    with pytest.raises(TypeError):
        TransferredCandidateCustody()
    assert inspect.isclass(ExpectedAcceptedCustodyReceiver)
    assert tuple(
        inspect.signature(CandidateArtifactSet.transfer_expected_accepted_custody).parameters
    ) == ("self", "expected_acceptance_seal", "receiver")


def test_build_session_initializes_exact_lock_marker_and_descriptor_owned_stage(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = _staging_settings(tmp_path / "repository")
    identity = _input_identity(settings)
    timestamp = datetime(2026, 8, 15, tzinfo=UTC)
    options = ArtifactBuildOptions(persistence_timestamp=timestamp)
    with ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        options,
        input_identity=identity,
    ) as session:
        assert session.persistence_timestamp is timestamp
        siblings = tuple(settings.repository_root.iterdir())
        lock = next(path for path in siblings if path.name == ".artifacts.finproof-build.lock")
        stage = next(
            path
            for path in siblings
            if re.fullmatch(r"\.artifacts\.finproof-stage-[0-9a-f]{32}", path.name)
        )
        marker = stage.with_name(f"{stage.name}.marker")
        assert lock.is_file()
        assert stage.is_dir()
        assert (stage / "parquet").is_dir()
        assert stat.S_IMODE(marker.stat().st_mode) == 0o600
        payload = json.loads(marker.read_text(encoding="utf-8"))
        assert payload == {
            "artifact_contract_version": "1.0.0",
            "artifact_set_id": "finproof-data-artifacts/v1",
            "operation_id": stage.name.rsplit("-", 1)[1],
            "target_basename": "artifacts",
        }
        assert not hasattr(session, "stage_root")
        assert not hasattr(session, "parent_descriptor")

    assert not stage.exists()
    assert not marker.exists()


@pytest.mark.parametrize(
    "case",
    [
        "concurrent-lock",
        "orphan-missing-marker",
        "orphan-malformed-marker",
        "orphan-mismatched-marker",
        "orphan-symlink",
    ],
)
def test_build_session_rejects_concurrent_lock_and_ambiguous_orphan_without_mutation(
    tmp_path: Path,
    case: str,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = _staging_settings(tmp_path / "repository")
    options = ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC))
    identity = _input_identity(settings)
    if case == "concurrent-lock":
        second_identity = _input_identity(settings)
        try:
            with ArtifactBuildSession.initialize(
                settings,
                VersionBundle(),
                options,
                input_identity=identity,
            ):
                before = tuple(
                    (path.name, path.lstat().st_ino) for path in settings.repository_root.iterdir()
                )
                with pytest.raises(ArtifactContractError) as caught:
                    ArtifactBuildSession.initialize(
                        settings,
                        VersionBundle(),
                        options,
                        input_identity=second_identity,
                    )
                assert caught.value.code is ArtifactErrorCode.LOCK_HELD
                assert (
                    tuple(
                        (path.name, path.lstat().st_ino)
                        for path in settings.repository_root.iterdir()
                    )
                    == before
                )
                second_identity.assert_unchanged()
        finally:
            second_identity.close()
        return

    stage = settings.repository_root / ".artifacts.finproof-stage-orphan123"
    marker = stage.with_name(f"{stage.name}.marker")
    if case == "orphan-symlink":
        external = tmp_path / "external"
        external.mkdir()
        stage.symlink_to(external, target_is_directory=True)
    else:
        stage.mkdir()
        if case == "orphan-malformed-marker":
            marker.write_bytes(b"not-json")
        elif case == "orphan-mismatched-marker":
            marker.write_text(
                json.dumps(
                    {
                        "artifact_contract_version": "1.0.0",
                        "artifact_set_id": "finproof-data-artifacts/v1",
                        "operation_id": "different",
                        "target_basename": "artifacts",
                    }
                ),
                encoding="utf-8",
            )
    before = (
        stage.lstat().st_ino,
        marker.lstat().st_ino if marker.exists() else None,
        marker.read_bytes() if marker.exists() else None,
    )
    try:
        with (
            pytest.raises(ArtifactContractError) as caught,
            ArtifactBuildSession.initialize(
                settings,
                VersionBundle(),
                options,
                input_identity=identity,
            ),
        ):
            pass
        assert caught.value.code is ArtifactErrorCode.UNRECOGNIZED_ORPHAN_STAGE
        assert (
            stage.lstat().st_ino,
            marker.lstat().st_ino if marker.exists() else None,
            marker.read_bytes() if marker.exists() else None,
        ) == before
    finally:
        identity.close()


def test_build_session_enforces_live_closing_closed_state(tmp_path: Path) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = _staging_settings(tmp_path / "repository")
    identity = _input_identity(settings)
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=identity,
    )
    session.assert_live()
    session.abort()
    with pytest.raises(ArtifactContractError):
        session.assert_live()
    with pytest.raises(ArtifactContractError):
        session.abort()
    session.__exit__(None, None, None)


def test_build_session_abort_removes_only_exact_recognized_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts import staging
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = _staging_settings(tmp_path / "repository")
    unrelated = settings.repository_root / "unrelated"
    unrelated.write_bytes(b"preserve")
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    )
    stage = next(
        path
        for path in settings.repository_root.iterdir()
        if path.name.startswith(".artifacts.finproof-stage-") and path.is_dir()
    )
    parquet_inode = (stage / "parquet").stat().st_ino
    stage_inode = stage.stat().st_ino
    events: list[str] = []
    real_close = staging.os.close
    real_rmdir = staging.os.rmdir
    real_unlink = staging.os.unlink
    real_flock = staging.fcntl.flock

    def close_spy(descriptor: int) -> None:
        try:
            inode = staging.os.fstat(descriptor).st_ino
        except OSError:
            inode = -1
        if inode == parquet_inode:
            events.append("close-parquet")
        elif inode == stage_inode:
            events.append("close-stage")
        real_close(descriptor)

    def rmdir_spy(path: Any, *args: Any, **kwargs: Any) -> None:
        events.append(f"rmdir-{path}")
        real_rmdir(path, *args, **kwargs)

    def unlink_spy(path: Any, *args: Any, **kwargs: Any) -> None:
        if str(path).endswith(".marker"):
            events.append("unlink-marker")
        real_unlink(path, *args, **kwargs)

    def flock_spy(descriptor: int, operation: int) -> None:
        if operation == staging.fcntl.LOCK_UN:
            events.append("unlock")
        real_flock(descriptor, operation)

    monkeypatch.setattr(staging.os, "close", close_spy)
    monkeypatch.setattr(staging.os, "rmdir", rmdir_spy)
    monkeypatch.setattr(staging.os, "unlink", unlink_spy)
    monkeypatch.setattr(staging.fcntl, "flock", flock_spy)
    session.abort()

    assert unrelated.read_bytes() == b"preserve"
    assert not stage.exists()
    assert events.index("close-parquet") < events.index("rmdir-parquet")
    assert events.index("rmdir-parquet") < events.index("close-stage")
    assert events.index("close-stage") < events.index(f"rmdir-{stage.name}")
    assert events.index(f"rmdir-{stage.name}") < events.index("unlink-marker")
    assert events.index("unlink-marker") < events.index("unlock")


@pytest.mark.parametrize("case", ["marker-bytes", "unexpected-root-child"])
def test_build_session_ambiguous_abort_retains_stage_until_safe_lock_release(
    tmp_path: Path,
    case: str,
) -> None:
    import fcntl

    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = _staging_settings(tmp_path / "repository")
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    )
    stage = next(
        path
        for path in settings.repository_root.iterdir()
        if path.name.startswith(".artifacts.finproof-stage-") and path.is_dir()
    )
    marker = stage.with_name(f"{stage.name}.marker")
    if case == "marker-bytes":
        payload = bytearray(marker.read_bytes())
        payload[-2] = ord("X") if payload[-2] != ord("X") else ord("Y")
        marker.write_bytes(payload)
    else:
        (stage / "unexpected").write_bytes(b"preserve")

    with pytest.raises(ArtifactContractError) as caught:
        session.abort()
    assert caught.value.code is ArtifactErrorCode.STAGING_CLEANUP_FAILED
    assert stage.is_dir()
    assert marker.is_file()
    assert (stage / "parquet").is_dir()
    if case == "unexpected-root-child":
        assert (stage / "unexpected").read_bytes() == b"preserve"

    lock_fd = os.open(
        settings.repository_root / ".artifacts.finproof-build.lock",
        os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)


def test_build_session_candidate_transfer_moves_descriptors_marker_registrations_input_custody_and_lock_once(  # noqa: E501
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = _staging_settings(tmp_path / "repository")
    identity = _input_identity(settings)
    with ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=identity,
    ) as session:
        stage_path = next(
            path
            for path in settings.repository_root.iterdir()
            if path.name.startswith(".artifacts.finproof-stage-") and path.is_dir()
        )
        marker = stage_path.with_name(f"{stage_path.name}.marker")
        owned = session.transfer_candidate_stage()
        owned.assert_live()
        assert stage_path.is_dir()
        assert marker.is_file()
        identity.assert_unchanged()
        with pytest.raises(ArtifactContractError):
            session.assert_live()
        with pytest.raises(ArtifactContractError):
            session.transfer_candidate_stage()

    owned.assert_live()
    owned.close()
    assert not stage_path.exists()
    assert not marker.exists()
    with pytest.raises(ArtifactContractError):
        identity.assert_unchanged()
    with pytest.raises(ArtifactContractError):
        owned.assert_live()


@pytest.mark.parametrize("kind", ["external-order", "database"])
def test_candidate_transfer_rejects_every_live_registered_workspace(
    tmp_path: Path,
    kind: str,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = _staging_settings(tmp_path / "repository")
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ).__enter__()
    workspace = (
        session.open_external_order_store(
            config=ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG, strict=True)
        )
        if kind == "external-order"
        else session.create_database_build_workspace()
    )
    live = workspace.__enter__()
    try:
        with pytest.raises(ArtifactContractError):
            session.transfer_candidate_stage()
        session.assert_live()
    finally:
        workspace.__exit__(None, None, None)
    owned = session.transfer_candidate_stage()
    owned.close()
    del live


def test_session_abort_removes_exact_registered_children_in_fixed_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.data.artifacts.table_specs import table_spec

    settings = _staging_settings(tmp_path / "repository")
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ).__enter__()
    for name in ("bronze_source_row", "bronze_source_cell"):
        with session.claim_parquet_leaf(table_spec(name)).create_exclusive() as stream:
            stream.write(name.encode())
    with session.claim_database_leaf().create_exclusive() as stream:
        stream.write(b"database")
    stage_path = settings.repository_root / session._stage_name
    unlinked: list[str] = []
    real_unlink = os.unlink

    def unlink_spy(path: str, *, dir_fd: int | None = None) -> None:
        unlinked.append(path)
        real_unlink(path, dir_fd=dir_fd)

    monkeypatch.setattr(os, "unlink", unlink_spy)
    session.abort()

    assert unlinked[:3] == [
        "bronze_source_cell.parquet",
        "bronze_source_row.parquet",
        "finproof.duckdb",
    ]
    assert not stage_path.exists()


@pytest.mark.parametrize("case", ["recognized", "failed-preflight-retry"])
def test_candidate_discard_removes_recognized_nonempty_stage_and_preserves_live_retry(
    tmp_path: Path,
    case: str,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.data.artifacts.table_specs import table_spec

    settings = _staging_settings(tmp_path / "repository")
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ).__enter__()
    with session.claim_parquet_leaf(table_spec("bronze_source_row")).create_exclusive() as stream:
        stream.write(b"row")
    stage_path = settings.repository_root / session._stage_name
    owned = session.transfer_candidate_stage()
    custody = owned.issue_candidate_custody()
    if case == "failed-preflight-retry":
        unexpected = stage_path / "unexpected"
        unexpected.write_bytes(b"foreign")
        with pytest.raises(ArtifactContractError):
            custody.discard_if_exact()
        unexpected.unlink()
        custody.assert_live()
    custody.discard_if_exact()
    assert not stage_path.exists()


@pytest.mark.parametrize("kind", ["parquet-writer", "external-order", "database"])
def test_session_registers_exact_live_working_object_and_transfers_only_after_close(
    tmp_path: Path,
    kind: str,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.parquet_io import ParquetBatchWriter
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.data.artifacts.table_specs import table_spec

    settings = _staging_settings(tmp_path / "repository")
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ).__enter__()
    context: Any | None = None
    if kind == "parquet-writer":
        spec = table_spec("bronze_source_column")
        resource = ParquetBatchWriter(spec, session.claim_parquet_leaf(spec))
        registry_name = "_live_parquet_writers"
    elif kind == "external-order":
        context = session.open_external_order_store(
            config=ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG, strict=True)
        )
        resource = context.__enter__()
        registry_name = "_live_external_order_stores"
    else:
        context = session.create_database_build_workspace()
        resource = context.__enter__()
        registry_name = "_live_database_workspaces"

    registry = getattr(session, registry_name, {})
    assert tuple(registry.values()) == (resource,)
    with pytest.raises(ArtifactContractError):
        session.transfer_candidate_stage()
    session.assert_live()

    if kind == "parquet-writer":
        resource.close()
    else:
        assert context is not None
        context.__exit__(None, None, None)
    assert not registry
    session.transfer_candidate_stage().close()


def test_session_abort_closes_all_exact_live_working_objects_in_fixed_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.parquet_io import ParquetBatchWriter
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.data.artifacts.table_specs import table_spec

    settings = _staging_settings(tmp_path / "repository")
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ).__enter__()
    spec = table_spec("bronze_source_column")
    writer = ParquetBatchWriter(spec, session.claim_parquet_leaf(spec))
    store_context = session.open_external_order_store(
        config=ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG, strict=True)
    )
    store = store_context.__enter__()
    database_context = session.create_database_build_workspace()
    database = database_context.__enter__()
    events: list[tuple[str, object]] = []
    writer_abort = ParquetBatchWriter.abort
    store_close = type(store).close_and_remove_working_state
    database_discard = type(database)._discard

    def abort_writer(value: ParquetBatchWriter) -> None:
        events.append(("parquet-writer", value))
        writer_abort(value)

    def close_store(value: Any) -> None:
        events.append(("external-order", value))
        store_close(value)

    def discard_database(value: Any) -> None:
        events.append(("database", value))
        database_discard(value)

    monkeypatch.setattr(ParquetBatchWriter, "abort", abort_writer)
    monkeypatch.setattr(type(store), "close_and_remove_working_state", close_store)
    monkeypatch.setattr(type(database), "_discard", discard_database)

    session.abort()

    assert events == [
        ("parquet-writer", writer),
        ("external-order", store),
        ("database", database),
    ]
    assert not next(
        (
            path
            for path in settings.repository_root.iterdir()
            if path.name.startswith(".artifacts.finproof-stage-")
        ),
        None,
    )
    with pytest.raises(ArtifactContractError):
        session.assert_live()


def test_production_external_order_store_does_not_call_test_only_factory() -> None:
    from finproof.data.artifacts.staging import ArtifactBuildSession

    source = inspect.getsource(ArtifactBuildSession.open_external_order_store)
    assert "_open_external_order_store_for_test" not in source
    assert "ExternalOrderStoreTestLimits" not in source


@pytest.mark.parametrize(
    "case",
    ["valid-root", "copy", "issue-reuse", "forged", "close-reuse"],
)
def test_candidate_stage_custody_is_instance_owned_and_opens_only_capability_bound_managed_verification_root(  # noqa: E501
    tmp_path: Path,
    case: str,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.manifest import ManagedArtifactVerificationRoot
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        CandidateStageCustody,
    )

    settings = _staging_settings(tmp_path / "repository")
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    )
    owned = session.transfer_candidate_stage()
    custody = owned.issue_candidate_custody()
    try:
        with pytest.raises(ArtifactContractError):
            owned.assert_live()
        assert not hasattr(custody, "path")
        assert not hasattr(custody, "basename")
        assert not hasattr(custody, "descriptor")
        if case == "valid-root":
            with custody.open_verification_root() as root:
                assert isinstance(root, ManagedArtifactVerificationRoot)
                with pytest.raises(ArtifactContractError):
                    root.take_expected_acceptance_seal()
            return
        if case == "copy":
            with pytest.raises(TypeError, match="cannot be copied"):
                copy(custody)
            return
        if case == "issue-reuse":
            with pytest.raises(ArtifactContractError):
                owned.issue_candidate_custody()
            return
        if case == "forged":
            forged = object.__new__(CandidateStageCustody)
            with pytest.raises(ArtifactContractError), forged.open_verification_root():
                pass
            return
        custody.close()
        with pytest.raises(ArtifactContractError), custody.open_verification_root():
            pass
    finally:
        with contextlib.suppress(ArtifactContractError):
            custody.close()


def test_candidate_verification_root_second_dup_failure_closes_first_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts import staging as staging_module
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = _staging_settings(tmp_path / "repository")
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    )
    custody = session.transfer_candidate_stage().issue_candidate_custody()
    real_dup = os.dup
    acquired: list[int] = []

    def fail_second_dup(descriptor: int) -> int:
        if acquired:
            raise OSError("second duplicate failed")
        duplicate = real_dup(descriptor)
        acquired.append(duplicate)
        return duplicate

    monkeypatch.setattr(staging_module.os, "dup", fail_second_dup)
    try:
        with pytest.raises(ArtifactContractError), custody.open_verification_root():
            pass
        assert acquired
        with pytest.raises(OSError, match="Bad file descriptor"):
            os.fstat(acquired[0])
        custody.assert_live()
    finally:
        custody.close()


@pytest.mark.parametrize("case", ["valid", "duplicate", "foreign-spec"])
def test_build_session_claims_exact_registry_parquet_leaf_exclusively(
    tmp_path: Path,
    case: str,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.data.artifacts.table_specs import TableSpec, table_spec

    settings = _staging_settings(tmp_path / "repository")
    with ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ) as session:
        spec = table_spec("bronze_source_row")
        if case == "foreign-spec":
            supplied = object.__new__(TableSpec)
            with pytest.raises((ArtifactContractError, ValueError)):
                session.claim_parquet_leaf(supplied)
            return
        leaf = session.claim_parquet_leaf(spec)
        assert leaf.table_name == spec.table_name
        assert leaf.relative_path.as_posix() == spec.parquet_path
        if case == "duplicate":
            with pytest.raises(ArtifactContractError):
                session.claim_parquet_leaf(spec)
            return
        with leaf.create_exclusive() as stream:
            stream.write(b"parquet-generation")
        leaf.assert_unchanged()
        with leaf.open_verified() as stream:
            assert stream.read() == b"parquet-generation"
        leaf.unlink_if_exact_writer_owned()


@pytest.mark.parametrize("case", ["copy", "foreign-forge", "closed-owner", "aba"])
def test_owned_parquet_leaf_rejects_foreign_copy_closed_owner_and_inode_substitution(
    tmp_path: Path,
    case: str,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.data.artifacts.table_specs import table_spec

    settings = _staging_settings(tmp_path / "repository")
    options = ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC))
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        options,
        input_identity=_input_identity(settings),
    )
    leaf = session.claim_parquet_leaf(table_spec("bronze_source_row"))
    if case == "copy":
        with pytest.raises(TypeError, match="cannot be copied"):
            copy(leaf)
        session.abort()
        return
    if case == "foreign-forge":
        second_settings = _staging_settings(tmp_path / "second-repository")
        second = ArtifactBuildSession.initialize(
            second_settings,
            VersionBundle(),
            options,
            input_identity=_input_identity(second_settings),
        )
        second.claim_parquet_leaf(table_spec("bronze_source_row"))
        object.__setattr__(leaf, "_owner", second)
        second._leaf_objects["bronze_source_row"] = leaf
        with pytest.raises(ArtifactContractError):
            second.require_owned_parquet_leaf(leaf)
        second.abort()
        session.abort()
        return
    if case == "closed-owner":
        session.abort()
        with pytest.raises(ArtifactContractError):
            _ = leaf.table_name
        return

    with leaf.create_exclusive() as stream:
        stream.write(b"original")
    stage = next(
        path
        for path in settings.repository_root.iterdir()
        if path.name.startswith(".artifacts.finproof-stage-") and path.is_dir()
    )
    target = stage / leaf.relative_path
    parked = target.with_suffix(".parked")
    os.replace(target, parked)
    target.write_bytes(b"replaced")
    target.unlink()
    os.replace(parked, target)
    with pytest.raises(ArtifactContractError):
        leaf.assert_unchanged()


def test_external_order_store_production_entry_is_pathless_owner_config_only(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.staging import ArtifactBuildSession

    signature = inspect.signature(ArtifactBuildSession.open_external_order_store)
    assert tuple(signature.parameters) == ("self", "config")
    assert not any(
        forbidden in signature.parameters
        for forbidden in (
            "path",
            "stage_root",
            "temp_directory",
            "memory_limit",
            "threads",
            "connection",
            "sql",
        )
    )
    settings = _staging_settings(tmp_path / "repository")
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
    with (
        ArtifactBuildSession.initialize(
            settings,
            VersionBundle(),
            ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
            input_identity=_input_identity(settings),
        ) as session,
        session.open_external_order_store(config=config) as store,
    ):
        assert type(store).__name__ == "ExternalOrderStore"


def test_external_order_store_fixes_production_settings_and_isolates_private_test_limits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts import staging
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExternalOrderStoreTestLimits,
        _open_external_order_store_for_test,
    )

    captured: list[tuple[int, str, bool, str]] = []
    configure = staging._configure_external_order_connection

    def configure_spy(connection: Any, *, temp_directory: str) -> None:
        configure(connection, temp_directory=temp_directory)
        row = connection.execute(
            "SELECT current_setting('threads'), current_setting('memory_limit'), "
            "current_setting('preserve_insertion_order')"
        ).fetchone()
        assert row is not None
        captured.append((int(row[0]), str(row[1]), bool(row[2]), temp_directory))

    monkeypatch.setattr(staging, "_configure_external_order_connection", configure_spy)
    assert tuple(inspect.signature(_open_external_order_store_for_test).parameters) == (
        "owner",
        "config",
        "limits",
    )
    limits = ExternalOrderStoreTestLimits(batch_rows=3, memory_limit_bytes=1 << 20)
    assert limits.batch_rows == 3
    settings = _staging_settings(tmp_path / "repository")
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
    with (
        ArtifactBuildSession.initialize(
            settings,
            VersionBundle(),
            ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
            input_identity=_input_identity(settings),
        ) as session,
        session.open_external_order_store(config=config) as store,
    ):
        assert not hasattr(store, "path")
        assert not hasattr(store, "temp_directory")
        assert not hasattr(store, "connection")
    assert len(captured) == 1
    assert captured[0][:3] == (1, "1.0 GiB", False)
    assert ".artifacts.finproof-stage-" in captured[0][3]


def test_external_order_store_orders_bounded_single_pass_batches_without_materialization(
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

    class OnePassRows:
        def __init__(self) -> None:
            self.iterations = 0

        def __len__(self) -> int:
            raise AssertionError("the source must never be materialized for sizing")

        def __iter__(self) -> Iterator[tuple[str, str]]:
            if self.iterations:
                raise AssertionError("the source must be consumed exactly once")
            self.iterations += 1
            for key in ("k7", "k2", "k5", "k1", "k6", "k3", "k4"):
                yield key, f'{{"key":"{key}"}}'

    settings = _staging_settings(tmp_path / "repository")
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
    limits = ExternalOrderStoreTestLimits(batch_rows=3, memory_limit_bytes=1 << 20)
    rows = OnePassRows()
    with (
        ArtifactBuildSession.initialize(
            settings,
            VersionBundle(),
            ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
            input_identity=_input_identity(settings),
        ) as session,
        _open_external_order_store_for_test(
            owner=session,
            config=config,
            limits=limits,
        ) as store,
    ):
        store.insert_batch(
            relation=ExternalOrderRelation.BRONZE_SOURCE_ROW,
            rows=rows,
        )
        batches = tuple(
            store.iter_ordered_batches(relation=ExternalOrderRelation.BRONZE_SOURCE_ROW)
        )
        assert all(1 <= len(batch) <= limits.batch_rows for batch in batches)
        assert tuple(row for batch in batches for row in batch) == tuple(
            (key, f'{{"key":"{key}"}}') for key in ("k1", "k2", "k3", "k4", "k5", "k6", "k7")
        )
    assert rows.iterations == 1


def test_external_order_store_closes_before_exact_marker_last_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import duckdb

    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExternalOrderStoreTestLimits,
        _open_external_order_store_for_test,
    )

    settings = _staging_settings(tmp_path / "repository")
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
    removed: list[tuple[str, bool]] = []
    unlink = os.unlink
    with ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ) as session:
        store = _open_external_order_store_for_test(
            owner=session,
            config=config,
            limits=ExternalOrderStoreTestLimits(
                batch_rows=3,
                memory_limit_bytes=1 << 20,
            ),
        )
        workspace_fd = store._workspace_fd

        def unlink_spy(
            path: str,
            *,
            dir_fd: int | None = None,
        ) -> None:
            if dir_fd == workspace_fd:
                connection_open = True
                try:
                    store._connection.execute("SELECT 1")
                except duckdb.Error:
                    connection_open = False
                removed.append((path, connection_open))
            unlink(path, dir_fd=dir_fd)

        monkeypatch.setattr(os, "unlink", unlink_spy)
        store.close_and_remove_working_state()
        store.close_and_remove_working_state()
        assert removed
        assert all(not connection_open for _, connection_open in removed)
        assert removed[-1][0] == ".marker"
        assert set(removed[:-1]).issuperset({("store.duckdb", False)})
        os.stat(session._marker_name, dir_fd=session._parent_fd, follow_symlinks=False)
        with os.scandir(session._stage_fd) as entries:
            assert {entry.name for entry in entries} == {"parquet"}


@pytest.mark.parametrize(
    "case",
    [
        "connection-close",
        "database-unlink",
        "spill-rmdir",
        "marker-unlink",
        "foreign-child",
        "wrong-marker-bytes",
        "marker-inode",
        "workspace-inode",
        "database-symlink",
    ],
)
def test_external_order_store_faults_retain_ambiguous_owned_state_and_preserve_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExternalOrderStoreTestLimits,
        _open_external_order_store_for_test,
    )

    settings = _staging_settings(tmp_path / "repository")
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ).__enter__()
    store = _open_external_order_store_for_test(
        owner=session,
        config=config,
        limits=ExternalOrderStoreTestLimits(
            batch_rows=3,
            memory_limit_bytes=1 << 20,
        ),
    )
    settings.artifact_dir.mkdir()
    published = settings.artifact_dir / "published.bin"
    published.write_bytes(b"already-published")
    restore_connection = None
    unlink = os.unlink
    rmdir = os.rmdir
    if case == "connection-close":
        connection = store._connection

        class CloseFault:
            def close(self) -> None:
                raise OSError("injected close failure")

            def __getattr__(self, name: str) -> Any:
                return getattr(connection, name)

        store._connection = CloseFault()
        restore_connection = connection
    elif case == "database-unlink":

        def unlink_database(path: str, *, dir_fd: int | None = None) -> None:
            if path == "store.duckdb" and dir_fd == store._workspace_fd:
                raise OSError("injected database unlink failure")
            unlink(path, dir_fd=dir_fd)

        monkeypatch.setattr(os, "unlink", unlink_database)
    elif case == "spill-rmdir":

        def rmdir_spill(path: str, *, dir_fd: int | None = None) -> None:
            if path == "spill" and dir_fd == store._workspace_fd:
                raise OSError("injected spill removal failure")
            rmdir(path, dir_fd=dir_fd)

        monkeypatch.setattr(os, "rmdir", rmdir_spill)
    elif case == "marker-unlink":

        def unlink_marker(path: str, *, dir_fd: int | None = None) -> None:
            if path == ".marker" and dir_fd == store._workspace_fd:
                raise OSError("injected marker unlink failure")
            unlink(path, dir_fd=dir_fd)

        monkeypatch.setattr(os, "unlink", unlink_marker)
    elif case == "foreign-child":
        child = os.open(
            "foreign",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=store._workspace_fd,
        )
        os.close(child)
    elif case == "wrong-marker-bytes":
        marker = os.open(".marker", os.O_WRONLY | os.O_TRUNC, dir_fd=store._workspace_fd)
        os.write(marker, b"wrong")
        os.close(marker)
    elif case == "marker-inode":
        os.rename(
            ".marker", ".marker.old", src_dir_fd=store._workspace_fd, dst_dir_fd=store._workspace_fd
        )
        marker = os.open(
            ".marker",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=store._workspace_fd,
        )
        os.write(marker, store._marker_payload)
        os.close(marker)
    elif case == "workspace-inode":
        parked = f"{store._workspace_name}.old"
        os.rename(
            store._workspace_name,
            parked,
            src_dir_fd=session._stage_fd,
            dst_dir_fd=session._stage_fd,
        )
        os.mkdir(store._workspace_name, 0o700, dir_fd=session._stage_fd)
    else:
        victim = tmp_path / "external-victim"
        victim.write_bytes(b"victim")
        os.unlink("store.duckdb", dir_fd=store._workspace_fd)
        os.symlink(victim, "store.duckdb", dir_fd=store._workspace_fd)

    try:
        with pytest.raises(ArtifactContractError):
            store.close_and_remove_working_state()
        monkeypatch.undo()
        if restore_connection is not None:
            store._connection = restore_connection
        assert published.read_bytes() == b"already-published"
        with pytest.raises(ArtifactContractError):
            store.close_and_remove_working_state()
    finally:
        monkeypatch.undo()
        with pytest.raises(ArtifactContractError):
            session.abort()


def test_database_stage_skeleton_rejects_valid_owner_fixture(tmp_path: Path) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ManagedStageDatabaseBuild,
        OwnedStageDatabaseLeaf,
        OwnedStageDatabaseOwner,
        SealedStageDatabase,
    )

    for constructor in (
        ManagedStageDatabaseBuild,
        OwnedStageDatabaseLeaf,
        OwnedStageDatabaseOwner,
        SealedStageDatabase,
    ):
        with pytest.raises(TypeError):
            constructor()
    settings = _staging_settings(tmp_path / "repository")
    with ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ) as session:
        assert session.claim_database_leaf().relative_path.as_posix() == "finproof.duckdb"
        assert tuple(inspect.signature(session.create_database_build_workspace).parameters) == ()


@pytest.mark.parametrize("case", ["exact", "duplicate", "copy", "foreign-owner"])
def test_database_stage_claims_one_same_owner_final_leaf(
    tmp_path: Path,
    case: str,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = _staging_settings(tmp_path / "repository")
    with ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ) as session:
        leaf = session.claim_database_leaf()
        if case == "exact":
            assert leaf.relative_path.as_posix() == "finproof.duckdb"
            session.require_owned_database_leaf(leaf)
        elif case == "duplicate":
            with pytest.raises(ArtifactContractError):
                session.claim_database_leaf()
        elif case == "copy":
            with pytest.raises(TypeError):
                copy(leaf)
        else:
            other_settings = _staging_settings(tmp_path / "other-repository")
            with (
                ArtifactBuildSession.initialize(
                    other_settings,
                    VersionBundle(),
                    ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
                    input_identity=_input_identity(other_settings),
                ) as other,
                pytest.raises(ArtifactContractError),
            ):
                other.require_owned_database_leaf(leaf)


def test_database_stage_build_uses_pathless_owned_scratch_and_fixed_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts import staging
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        _configure_stage_database_connection,
    )

    captured: list[tuple[int, bool, str, str]] = []
    configure = _configure_stage_database_connection

    def configure_spy(connection: Any, *, temp_directory: str) -> None:
        configure(connection, temp_directory=temp_directory)
        row = connection.execute(
            "SELECT current_setting('threads'), "
            "current_setting('preserve_insertion_order'), "
            "current_setting('TimeZone')"
        ).fetchone()
        assert row is not None
        captured.append((int(row[0]), bool(row[1]), str(row[2]), temp_directory))

    monkeypatch.setattr(staging, "_configure_stage_database_connection", configure_spy)
    assert tuple(
        inspect.signature(ArtifactBuildSession.create_database_build_workspace).parameters
    ) == ("self",)
    settings = _staging_settings(tmp_path / "repository")
    with (
        ArtifactBuildSession.initialize(
            settings,
            VersionBundle(),
            ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
            input_identity=_input_identity(settings),
        ) as session,
        session.create_database_build_workspace() as build,
    ):
        assert not hasattr(build, "path")
        assert not hasattr(build, "connection")
        assert not hasattr(build, "temp_directory")
        with build.open_writer() as connection:
            connection.execute("CREATE TABLE fixture(value INTEGER NOT NULL)")
            connection.execute("INSERT INTO fixture VALUES (1)")
    assert len(captured) == 1
    assert captured[0][:3] == (1, True, "UTC")
    assert ".artifacts.finproof-stage-" in captured[0][3]


@pytest.mark.parametrize("case", ["checkpoint-close", "wal-after-close"])
def test_database_stage_checkpoints_closes_and_rejects_wal_before_seal(
    tmp_path: Path,
    case: str,
) -> None:
    import duckdb

    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = _staging_settings(tmp_path / "repository")
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ).__enter__()
    leaf = session.claim_database_leaf()
    build = session.create_database_build_workspace().__enter__()
    with build.open_writer() as connection:
        connection.execute("CREATE TABLE fixture(value INTEGER NOT NULL)")
        connection.execute("INSERT INTO fixture VALUES (1)")
    if case == "wal-after-close":
        real_connection = build._connection

        class CloseWithWal:
            def execute(self, statement: str):
                return real_connection.execute(statement)

            def close(self) -> None:
                real_connection.close()
                descriptor = os.open(
                    "scratch.duckdb.wal",
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=build._workspace_fd,
                )
                os.close(descriptor)

        build._connection = CloseWithWal()
    try:
        if case == "checkpoint-close":
            sealed = build.checkpoint_close_and_seal(leaf=leaf)
            sealed.validate_against(session)
        else:
            with pytest.raises(ArtifactContractError) as raised:
                build.checkpoint_close_and_seal(leaf=leaf)
            assert raised.value.internal_context["reason"] == "database_wal_present"
        with pytest.raises(duckdb.Error):
            connection.execute("SELECT 1")
        if case == "checkpoint-close":
            os.stat("finproof.duckdb", dir_fd=session._stage_fd, follow_symlinks=False)
        else:
            with pytest.raises(FileNotFoundError):
                os.stat(
                    "finproof.duckdb",
                    dir_fd=session._stage_fd,
                    follow_symlinks=False,
                )
    finally:
        if case == "checkpoint-close":
            build.__exit__(None, None, None)
            leaf.unlink_if_exact_writer_owned()
            session.abort()
        else:
            with pytest.raises(ArtifactContractError):
                build.__exit__(None, None, None)
            with pytest.raises(ArtifactContractError):
                session.abort()


@pytest.mark.parametrize("case", ["exact-copy", "existing-file", "symlink"])
def test_database_stage_exclusively_nofollow_copies_fsyncs_and_closes_final_leaf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = _staging_settings(tmp_path / "repository")
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ).__enter__()
    leaf = session.claim_database_leaf()
    build = session.create_database_build_workspace().__enter__()
    with build.open_writer() as connection:
        connection.execute("CREATE TABLE fixture(value INTEGER NOT NULL)")
        connection.execute("INSERT INTO fixture VALUES (7), (3)")
    victim = tmp_path / "external-victim"
    if case == "existing-file":
        descriptor = os.open(
            "finproof.duckdb",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=session._stage_fd,
        )
        os.write(descriptor, b"existing")
        os.close(descriptor)
    elif case == "symlink":
        victim.write_bytes(b"victim")
        os.symlink(victim, "finproof.duckdb", dir_fd=session._stage_fd)
    fsync = os.fsync
    fsynced: list[int] = []

    def fsync_spy(descriptor: int) -> None:
        fsynced.append(descriptor)
        fsync(descriptor)

    monkeypatch.setattr(os, "fsync", fsync_spy)
    try:
        if case == "exact-copy":
            sealed = build.checkpoint_close_and_seal(leaf=leaf)
            sealed.validate_against(session)
        else:
            with pytest.raises(ArtifactContractError) as raised:
                build.checkpoint_close_and_seal(leaf=leaf)
        if case == "exact-copy":
            final_stat = os.stat(
                "finproof.duckdb",
                dir_fd=session._stage_fd,
                follow_symlinks=False,
            )
            assert stat.S_IMODE(final_stat.st_mode) == 0o600
            assert fsynced
            for descriptor in fsynced:
                with pytest.raises(OSError, match="Bad file descriptor"):
                    os.fstat(descriptor)
        else:
            assert raised.value.internal_context["reason"] == ("database_final_copy_failed")
            if case == "existing-file":
                descriptor = os.open("finproof.duckdb", os.O_RDONLY, dir_fd=session._stage_fd)
                try:
                    assert os.read(descriptor, 32) == b"existing"
                finally:
                    os.close(descriptor)
            else:
                assert victim.read_bytes() == b"victim"
    finally:
        monkeypatch.undo()
        if case == "exact-copy":
            build.__exit__(None, None, None)
            leaf.unlink_if_exact_writer_owned()
            session.abort()
        else:
            with pytest.raises(ArtifactContractError):
                build.__exit__(None, None, None)
            with pytest.raises(ArtifactContractError):
                session.abort()


def test_database_stage_reopens_hashes_and_rescans_final_leaf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts import staging
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = _staging_settings(tmp_path / "repository")
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ).__enter__()
    leaf = session.claim_database_leaf()
    build = session.create_database_build_workspace().__enter__()
    with build.open_writer() as connection:
        connection.execute("CREATE TABLE fixture(value INTEGER NOT NULL)")
        connection.execute("INSERT INTO fixture VALUES (7), (3)")
    connect = staging.duckdb.connect
    read_only_calls: list[str] = []

    def connect_spy(database: str, *args: Any, **kwargs: Any) -> Any:
        if kwargs.get("read_only") is True:
            read_only_calls.append(database)
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(staging.duckdb, "connect", connect_spy)
    try:
        sealed = build.checkpoint_close_and_seal(leaf=leaf)
        sealed.validate_against(session)
        assert len(read_only_calls) == 1
        assert build._physical_size_bytes > 0
        assert re.fullmatch(r"[0-9a-f]{64}", build._physical_sha256)
        assert build._rescanned_tables == (("fixture", 2),)
        with leaf.open_verified() as stream:
            assert len(stream.read()) == build._physical_size_bytes
        leaf.assert_unchanged()
    finally:
        monkeypatch.undo()
        build.__exit__(None, None, None)
        leaf.unlink_if_exact_writer_owned()
        session.abort()


@pytest.mark.parametrize(
    "case",
    [
        "connection-close",
        "marker-bytes",
        "workspace-inode",
        "spill-inode",
        "scratch-symlink",
        "final-leaf-substitution",
    ],
)
def test_database_stage_closes_before_cleanup_and_rejects_abort_or_substitution_ambiguity(
    tmp_path: Path,
    case: str,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = _staging_settings(tmp_path / "repository")
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ).__enter__()
    build = session.create_database_build_workspace().__enter__()
    with build.open_writer() as connection:
        connection.execute("CREATE TABLE fixture(value INTEGER NOT NULL)")
        connection.execute("INSERT INTO fixture VALUES (1)")
    settings.artifact_dir.mkdir()
    published = settings.artifact_dir / "published.bin"
    published.write_bytes(b"published")
    restore_connection = None
    if case == "connection-close":
        real_connection = build._connection

        class CloseFault:
            def close(self) -> None:
                raise OSError("injected close failure")

            def __getattr__(self, name: str) -> Any:
                return getattr(real_connection, name)

        build._connection = CloseFault()
        restore_connection = real_connection
    elif case == "marker-bytes":
        marker = os.open(".marker", os.O_WRONLY | os.O_TRUNC, dir_fd=build._workspace_fd)
        os.write(marker, b"wrong")
        os.close(marker)
    elif case == "workspace-inode":
        os.rename(
            build._workspace_name,
            f"{build._workspace_name}.old",
            src_dir_fd=session._stage_fd,
            dst_dir_fd=session._stage_fd,
        )
        os.mkdir(build._workspace_name, 0o700, dir_fd=session._stage_fd)
    elif case == "spill-inode":
        os.rename(
            "spill", "spill.old", src_dir_fd=build._workspace_fd, dst_dir_fd=build._workspace_fd
        )
        os.mkdir("spill", 0o700, dir_fd=build._workspace_fd)
    elif case == "scratch-symlink":
        victim = tmp_path / "scratch-victim"
        victim.write_bytes(b"victim")
        os.unlink("scratch.duckdb", dir_fd=build._workspace_fd)
        os.symlink(victim, "scratch.duckdb", dir_fd=build._workspace_fd)
    else:
        leaf = session.claim_database_leaf()
        sealed = build.checkpoint_close_and_seal(leaf=leaf)
        sealed.validate_against(session)
        os.rename(
            "finproof.duckdb",
            "finproof.duckdb.old",
            src_dir_fd=session._stage_fd,
            dst_dir_fd=session._stage_fd,
        )
        victim = tmp_path / "final-victim"
        victim.write_bytes(b"victim")
        os.symlink(victim, "finproof.duckdb", dir_fd=session._stage_fd)
    try:
        with pytest.raises(ArtifactContractError):
            build.__exit__(None, None, None)
        if restore_connection is not None:
            build._connection = restore_connection
            with pytest.raises(ArtifactContractError):
                build.__exit__(None, None, None)
        assert published.read_bytes() == b"published"
        os.stat(
            build._workspace_name,
            dir_fd=session._stage_fd,
            follow_symlinks=False,
        )
    finally:
        with pytest.raises(ArtifactContractError):
            session.abort()


@pytest.mark.parametrize("case", ["exact-owner", "foreign-owner"])
def test_sealed_stage_database_requires_same_owner_registration_and_exact_leaf(
    tmp_path: Path,
    case: str,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.staging import ArtifactBuildSession

    settings = _staging_settings(tmp_path / "repository")
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ).__enter__()
    leaf = session.claim_database_leaf()
    try:
        with session.create_database_build_workspace() as build:
            with build.open_writer() as connection:
                connection.execute("CREATE TABLE fixture(value INTEGER NOT NULL)")
                connection.execute("INSERT INTO fixture VALUES (1), (2)")
            sealed = build.checkpoint_close_and_seal(leaf=leaf)
        assert sealed.persistence_timestamp == session.persistence_timestamp
        assert sealed.physical_size_bytes > 0
        assert re.fullmatch(r"[0-9a-f]{64}", sealed.physical_sha256)
        if case == "exact-owner":
            sealed.validate_against(session)
        else:
            other_settings = _staging_settings(tmp_path / "other-repository")
            with (
                ArtifactBuildSession.initialize(
                    other_settings,
                    VersionBundle(),
                    ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
                    input_identity=_input_identity(other_settings),
                ) as other,
                pytest.raises(ArtifactContractError),
            ):
                sealed.validate_against(other)
    finally:
        leaf.unlink_if_exact_writer_owned()
        session.abort()


@pytest.mark.parametrize(
    "case",
    ["copy", "equal-object-new", "owner-token-forge", "leaf-token-forge"],
)
def test_sealed_stage_database_rejects_copy_equal_object_new_and_token_forge(
    tmp_path: Path,
    case: str,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.staging import ArtifactBuildSession, SealedStageDatabase

    settings = _staging_settings(tmp_path / "repository")
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ).__enter__()
    leaf = session.claim_database_leaf()
    try:
        with session.create_database_build_workspace() as build:
            with build.open_writer() as connection:
                connection.execute("CREATE TABLE fixture(value INTEGER NOT NULL)")
                connection.execute("INSERT INTO fixture VALUES (1)")
            sealed = build.checkpoint_close_and_seal(leaf=leaf)
        if case == "copy":
            with pytest.raises(TypeError):
                copy(sealed)
        elif case == "equal-object-new":
            forged = object.__new__(SealedStageDatabase)
            for name in (
                "_owner",
                "_leaf",
                "_owner_registration",
                "_leaf_issuance_token",
                "persistence_timestamp",
                "physical_size_bytes",
                "physical_sha256",
            ):
                object.__setattr__(forged, name, getattr(sealed, name))
            object.__setattr__(session, "_sealed_database", forged)
            with pytest.raises(ArtifactContractError):
                forged.validate_against(session)
        elif case == "owner-token-forge":
            token = object()
            object.__setattr__(sealed, "_owner_registration", token)
            object.__setattr__(session, "_sealed_owner_token", token)
            with pytest.raises(ArtifactContractError):
                sealed.validate_against(session)
        else:
            token = object()
            object.__setattr__(sealed, "_leaf_issuance_token", token)
            object.__setattr__(session, "_sealed_leaf_token", token)
            with pytest.raises(ArtifactContractError):
                sealed.validate_against(session)
    finally:
        leaf.unlink_if_exact_writer_owned()
        session.abort()
