# mypy: disable-error-code="arg-type,assignment,attr-defined,misc,no-untyped-def"
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
from finproof.data.artifacts.staging import ExternalOrderRow


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


def test_external_order_store_cp5_relation_inventory_is_exact_and_closed() -> None:
    from finproof.data.artifacts.staging import (
        ExternalOrderJoinOperation,
        ExternalOrderJoinRow,
        ExternalOrderRelation,
        ExternalOrderRow,
    )

    assert tuple(ExternalOrderRelation) == (
        ExternalOrderRelation.BRONZE_SOURCE_ROW,
        ExternalOrderRelation.SILVER_BOND_INSTRUMENT,
        ExternalOrderRelation.SILVER_DOMESTIC_LISTED_PRODUCT,
        ExternalOrderRelation.SILVER_OVERSEAS_LISTED_PRODUCT,
        ExternalOrderRelation.PUBLIC_FUND_SOURCE_ROW,
        ExternalOrderRelation.SILVER_QUALITY_ISSUE,
        ExternalOrderRelation.EXACT_LINK_LEFT_CANDIDATE,
        ExternalOrderRelation.EXACT_LINK_RIGHT_CANDIDATE,
        ExternalOrderRelation.EXACT_LINK_EVIDENCE,
    )
    assert tuple(ExternalOrderJoinOperation) == (
        ExternalOrderJoinOperation.QUALITY_TO_BRONZE,
        ExternalOrderJoinOperation.EXACT_EVIDENCE_TO_BRONZE,
        ExternalOrderJoinOperation.LINKED_DOMESTIC_RECORD_JSON,
        ExternalOrderJoinOperation.LINKED_FUND_RECORD_JSON,
    )
    row = ExternalOrderRow(key=(1, "x"), payload_json='{"x":1}')
    join_row = ExternalOrderJoinRow(key=(1, "x"), values=("v", 2))
    assert row.key == (1, "x")
    assert join_row.values == ("v", 2)
    with pytest.raises((AttributeError, TypeError)):
        row.key = (2,)


def test_external_order_store_typed_batch_insert_and_export_are_bounded(tmp_path: Path) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExternalOrderRelation,
        ExternalOrderRow,
        ExternalOrderStoreTestLimits,
        _open_external_order_store_for_test,
    )

    settings = _staging_settings(tmp_path / "repository")
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
    rows = tuple(
        ExternalOrderRow(key=(key,), payload_json=f'{{"key":"{key}"}}')
        for key in ("k7", "k2", "k5", "k1", "k6", "k3", "k4")
    )
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
            limits=ExternalOrderStoreTestLimits(batch_rows=3, memory_limit_bytes=1 << 20),
        ) as store,
    ):
        store.insert_batch(relation=ExternalOrderRelation.SILVER_BOND_INSTRUMENT, rows=iter(rows))
        batches = tuple(
            store.iter_ordered_batches(relation=ExternalOrderRelation.SILVER_BOND_INSTRUMENT)
        )

    assert all(1 <= len(batch) <= 3 for batch in batches)
    assert tuple(row.key for batch in batches for row in batch) == tuple(
        (key,) for key in ("k1", "k2", "k3", "k4", "k5", "k6", "k7")
    )
    assert all(type(row) is ExternalOrderRow for batch in batches for row in batch)


def test_external_order_store_preserves_numeric_and_string_key_order(tmp_path: Path) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExternalOrderRelation,
        ExternalOrderRow,
    )

    settings = _staging_settings(tmp_path / "repository")
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
    rows = tuple(
        ExternalOrderRow(key=key, payload_json=f'{{"id":"{index}"}}')
        for index, key in enumerate((("z", 10), ("z", 2), ("a", 2), ("A", 10)))
    )
    with (
        ArtifactBuildSession.initialize(
            settings,
            VersionBundle(),
            ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
            input_identity=_input_identity(settings),
        ) as session,
        session.open_external_order_store(config=config) as store,
    ):
        store.insert_batch(relation=ExternalOrderRelation.PUBLIC_FUND_SOURCE_ROW, rows=rows)
        ordered = tuple(
            row
            for batch in store.iter_ordered_batches(
                relation=ExternalOrderRelation.PUBLIC_FUND_SOURCE_ROW
            )
            for row in batch
        )

    assert tuple(row.key for row in ordered) == (("A", 10), ("a", 2), ("z", 2), ("z", 10))


def test_external_order_store_ordered_stream_survives_nested_candidate_insert(
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
        ExternalOrderRow,
        ExternalOrderStoreTestLimits,
        _open_external_order_store_for_test,
    )

    settings = _staging_settings(tmp_path / "repository")
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
    source_rows = tuple(
        ExternalOrderRow(key=(f"fund-{index}", index), payload_json=f'{{"id":{index}}}')
        for index in range(5)
    )
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
            limits=ExternalOrderStoreTestLimits(
                batch_rows=2,
                memory_limit_bytes=1 << 30,
            ),
        ) as store,
    ):
        store.insert_batch(
            relation=ExternalOrderRelation.PUBLIC_FUND_SOURCE_ROW,
            rows=source_rows,
        )
        batches = store.iter_ordered_batches(relation=ExternalOrderRelation.PUBLIC_FUND_SOURCE_ROW)
        first = next(batches)
        store.insert_batch(
            relation=ExternalOrderRelation.EXACT_LINK_RIGHT_CANDIDATE,
            rows=(
                ExternalOrderRow(
                    key=("raw-id", "right-id"),
                    payload_json='{"candidate":"right"}',
                ),
            ),
        )
        observed = (*first, *(row for batch in batches for row in batch))

    assert observed == source_rows


def test_staged_join_projection_bulk_ingests_bounded_arrow_batches_without_python_rows(
    tmp_path: Path,
) -> None:
    import pyarrow as pa  # type: ignore[import-untyped]

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

    batches = (
        pa.record_batch({"source_table": ["A", "B"], "source_row_number": [1, 2]}),
        pa.record_batch({"source_table": ["C"], "source_row_number": [3]}),
    )

    class Handle:
        @contextlib.contextmanager
        def iter_batches(self, *, batch_size: int):
            assert batch_size == 2
            yield iter(batches)

    class Verification:
        handle = Handle()

    class Tables:
        def verification_for(self, staged_name: str) -> Verification:
            assert staged_name == "bronze_source_cell"
            return Verification()

    class ConnectionProxy:
        def __init__(self, inner: Any) -> None:
            self.inner = inner
            self.registered_rows: list[int] = []

        def execute(self, statement: str, parameters: Any = None) -> Any:
            if parameters is None:
                return self.inner.execute(statement)
            return self.inner.execute(statement, parameters)

        def executemany(self, statement: str, parameters: Any) -> None:
            del statement, parameters
            raise AssertionError("staged Arrow projection must not materialize Python rows")

        def register(self, name: str, batch: Any) -> None:
            assert name == "finproof_staged_join_batch"
            self.registered_rows.append(batch.num_rows)
            self.inner.register(name, batch)

        def unregister(self, name: str) -> None:
            self.inner.unregister(name)

        def close(self) -> None:
            self.inner.close()

    settings = _staging_settings(tmp_path / "repository")
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
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
            limits=ExternalOrderStoreTestLimits(
                batch_rows=2,
                memory_limit_bytes=1 << 30,
            ),
        ) as store,
    ):
        connection = ConnectionProxy(store._connection)
        store._connection = connection
        store._load_staged_join_projection(
            connection=connection,
            tables=Tables(),
            table_name="join_bronze_cell",
            staged_name="bronze_source_cell",
            columns=(("source_table", "VARCHAR"), ("source_row_number", "BIGINT")),
        )
        observed = connection.execute(
            "SELECT source_table, source_row_number FROM join_bronze_cell "
            "ORDER BY source_row_number"
        ).fetchall()

        assert observed == [("A", 1), ("B", 2), ("C", 3)]
        assert connection.registered_rows == [2, 1]


def test_large_exact_evidence_join_releases_operation_scope_before_low_memory_fund_join(
    tmp_path: Path,
) -> None:
    from datetime import date

    import pyarrow as pa

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

    source_date = date(2026, 7, 11)
    bronze_batches = tuple(
        pa.record_batch(
            {
                "source_table": ["PREF01N001"] * 32,
                "source_file": ["data/domestic.xlsx"] * 32,
                "source_sheet": ["Sheet1"] * 32,
                "source_row_number": list(range(offset + 2, offset + 34)),
                "source_column_name": ["pd_itm_no"] * 32,
                "source_column_number": [1] * 32,
                "source_column_letter": ["A"] * 32,
                "source_checksum": ["a" * 64] * 32,
                "source_snapshot_date": [source_date] * 32,
                "source_applicable_date": [None] * 32,
                "raw_value": [f"ID-{offset + index:04d}-" + "x" * 4096 for index in range(32)],
            }
        )
        for offset in range(0, 512, 32)
    )
    matched = bronze_batches[0].column("raw_value")[0].as_py()
    exact_evidence = pa.record_batch(
        {
            "link_id": ["b" * 64],
            "evidence_role_order": [0],
            "evidence_ordinal": [0],
            "raw_identifier": [matched],
            "source_table": ["PREF01N001"],
            "source_file": ["data/domestic.xlsx"],
            "source_sheet": ["Sheet1"],
            "source_row_number": [2],
            "source_column_name": ["pd_itm_no"],
            "source_column_number": [1],
            "source_column_letter": ["A"],
            "source_checksum": ["a" * 64],
            "source_snapshot_date": [source_date],
            "source_applicable_date": [None],
        }
    )
    fund = pa.record_batch(
        {
            "fund_item_id": ["fund-1"],
            "record_json": ['{"fund_item_id":"fund-1"}'],
        }
    )
    batches_by_name = {
        "gold_exact_cross_source_link_evidence": (exact_evidence,),
        "bronze_source_cell": bronze_batches,
        "silver_fund_item": (fund,),
    }

    class Handle:
        def __init__(self, batches: Any) -> None:
            self._batches = batches

        @contextlib.contextmanager
        def iter_batches(self, *, batch_size: int):
            assert batch_size == 32
            yield iter(self._batches)

    class Verification:
        def __init__(self, batches: Any) -> None:
            self.handle = Handle(batches)

    class Tables:
        def verification_for(self, staged_name: str) -> Verification:
            return Verification(batches_by_name[staged_name])

    class TrackedCursor:
        def __init__(self, inner: Any, owner: Any) -> None:
            self._inner = inner
            self._owner = owner

        def __getattr__(self, name: str) -> Any:
            return getattr(self._inner, name)

        def close(self) -> None:
            self._inner.close()
            self._owner.closed += 1

    class TrackedConnection:
        def __init__(self, inner: Any) -> None:
            self._inner = inner
            self.opened = 0
            self.closed = 0

        def __getattr__(self, name: str) -> Any:
            return getattr(self._inner, name)

        def cursor(self) -> TrackedCursor:
            self.opened += 1
            return TrackedCursor(self._inner.cursor(), self)

        def close(self) -> None:
            self._inner.close()

    settings = _staging_settings(tmp_path / "repository")
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
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
            limits=ExternalOrderStoreTestLimits(
                batch_rows=32,
                memory_limit_bytes=16 << 20,
            ),
        ) as store,
    ):
        connection = TrackedConnection(store._connection)
        store._connection = connection
        evidence_rows = tuple(store._iter_exact_evidence_to_bronze_batches(Tables()))
        fund_rows = tuple(
            store._iter_linked_record_json_batches(
                tables=Tables(),
                exact_ids=("fund-1",),
                staged_name="silver_fund_item",
                join_table="join_linked_fund",
                id_column="fund_item_id",
                sql="SELECT i.exact_id, r.record_json FROM join_exact_ids AS i "
                "JOIN join_linked_fund AS r ON i.exact_id = r.fund_item_id ORDER BY 1",
            )
        )
        remaining = connection.execute(
            "SELECT table_name FROM duckdb_tables() WHERE table_name LIKE 'join_%'"
        ).fetchall()

        assert evidence_rows[0][0].values == (matched, 1)
        assert fund_rows[0][0].key == ("fund-1",)
        assert connection.opened == connection.closed == 2
        assert remaining == []


def test_linked_record_join_filters_exact_ids_before_wide_batch_admission(
    tmp_path: Path,
) -> None:
    import pyarrow as pa

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

    batches = tuple(
        pa.record_batch(
            {
                "fund_item_id": [
                    "fund-match" if offset == 0 and index == 0 else f"foreign-{offset + index}"
                    for index in range(32)
                ],
                "record_json": [
                    '{"fund_item_id":"fund-match"}'
                    if offset == 0 and index == 0
                    else '{"foreign":"' + "x" * 4096 + '"}'
                    for index in range(32)
                ],
            }
        )
        for offset in range(0, 512, 32)
    )

    class Handle:
        @contextlib.contextmanager
        def iter_batches(self, *, batch_size: int):
            assert batch_size == 32
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

        def register(self, name: str, batch: Any) -> None:
            assert name == "finproof_staged_join_batch"
            self.registered_rows.append(batch.num_rows)
            self._inner.register(name, batch)

        def close(self) -> None:
            self._inner.close()

    settings = _staging_settings(tmp_path / "repository")
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
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
            limits=ExternalOrderStoreTestLimits(
                batch_rows=32,
                memory_limit_bytes=16 << 20,
            ),
        ) as store,
    ):
        connection = ConnectionProxy(store._connection)
        store._connection = connection
        observed = tuple(
            store._iter_linked_record_json_batches(
                tables=Tables(),
                exact_ids=("fund-match", "fund-missing"),
                staged_name="silver_fund_item",
                join_table="join_linked_fund",
                id_column="fund_item_id",
                sql="SELECT i.exact_id, r.record_json FROM join_exact_ids AS i "
                "JOIN join_linked_fund AS r ON i.exact_id = r.fund_item_id ORDER BY 1",
            )
        )

        assert observed[0][0].key == ("fund-match",)
        assert connection.registered_rows == [1]


@pytest.mark.parametrize(
    "rows",
    [
        pytest.param(
            (ExternalOrderRow(key=("item", 2, "extra"), payload_json='{"id":1}'),),
            id="wrong-arity",
        ),
        pytest.param(
            (ExternalOrderRow(key=("item", True), payload_json='{"id":1}'),),
            id="bool-numeric-key",
        ),
        pytest.param(
            (ExternalOrderRow(key=("item", "2"), payload_json='{"id":1}'),),
            id="numeric-string-key",
        ),
        pytest.param(
            (ExternalOrderRow(key=("item", 2), payload_json='{"b":2, "a":1}'),),
            id="noncanonical-payload",
        ),
        pytest.param(
            (
                ExternalOrderRow(key=("item", 2), payload_json='{"id":1}'),
                ExternalOrderRow(key=("item", 2), payload_json='{"id":2}'),
            ),
            id="duplicate-key",
        ),
    ],
)
def test_external_order_store_rejects_wrong_arity_bool_coercion_noncanonical_payload_and_duplicate_key(  # noqa: E501
    tmp_path: Path,
    rows: tuple[object, ...],
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
        ExternalOrderRelation,
        ExternalOrderStore,
        ExternalOrderStoreTestLimits,
        _open_external_order_store_for_test,
    )

    settings = _staging_settings(tmp_path / "repository")
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)

    def insert_and_read(store: ExternalOrderStore) -> None:
        store.insert_batch(
            relation=ExternalOrderRelation.PUBLIC_FUND_SOURCE_ROW,
            rows=rows,
        )
        tuple(store.iter_ordered_batches(relation=ExternalOrderRelation.PUBLIC_FUND_SOURCE_ROW))

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
            limits=ExternalOrderStoreTestLimits(batch_rows=2, memory_limit_bytes=1 << 20),
        ) as store,
        pytest.raises(ArtifactContractError),
    ):
        insert_and_read(store)


def test_external_order_store_exposes_no_public_connection_sql_table_cursor_or_path_surface() -> (
    None
):
    from finproof.data.artifacts.staging import ExternalOrderStore

    public_names = {name for name in dir(ExternalOrderStore) if not name.startswith("_")}
    assert public_names <= {
        "close_and_remove_working_state",
        "insert_batch",
        "iter_join_batches",
        "iter_ordered_batches",
    }
    assert {
        "close_and_remove_working_state",
        "insert_batch",
        "iter_ordered_batches",
    } <= public_names
    for forbidden in (
        "connection",
        "execute",
        "sql",
        "table",
        "cursor",
        "path",
        "join",
        "register",
    ):
        assert forbidden not in public_names
    assert tuple(inspect.signature(ExternalOrderStore.insert_batch).parameters) == (
        "self",
        "relation",
        "rows",
    )


def test_bounded_relation_verifier_has_exact_cp5_cp6_closed_signatures() -> None:
    from finproof.data.artifacts.reports import BoundedRelationVerifier

    assert tuple(
        inspect.signature(BoundedRelationVerifier.verify_quality_to_bronze).parameters
    ) == ("self", "tables")
    assert tuple(
        inspect.signature(BoundedRelationVerifier.verify_exact_evidence_to_bronze).parameters
    ) == ("self", "tables")
    assert tuple(inspect.signature(BoundedRelationVerifier.iter_linked_record_json).parameters) == (
        "self",
        "tables",
        "side",
        "exact_ids",
    )


def test_external_order_store_closed_quality_join_revalidates_exact_live_staged_set(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.parquet_io import (
        ParquetBatchWriter,
        StagedParquetSet,
        verify_staged_parquet_table,
    )
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExternalOrderJoinOperation,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPECS

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
        verifications = []
        for spec in TABLE_SPECS[:9]:
            leaf = session.claim_parquet_leaf(spec)
            ParquetBatchWriter(spec, leaf).close()
            verifications.append(verify_staged_parquet_table(owner=session, leaf=leaf, spec=spec))
        tables = StagedParquetSet.from_verified(
            owner=session,
            verifications=tuple(verifications),
        )

        assert (
            tuple(
                store.iter_join_batches(
                    operation=ExternalOrderJoinOperation.QUALITY_TO_BRONZE,
                    tables=tables,
                )
            )
            == ()
        )


def test_external_order_store_cp6_forward_routes_stream_static_typed_rows(
    tmp_path: Path,
) -> None:
    from datetime import date
    from decimal import Decimal

    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.parquet_io import (
        ParquetBatchWriter,
        StagedParquetSet,
        verify_staged_parquet_table,
    )
    from finproof.data.artifacts.serialization import (
        BronzeSourceCellRecord,
        ExactCrossSourceLinkEvidenceRecord,
        ExactCrossSourceLinkRecord,
        canonical_record_json,
        serialize_table_row,
    )
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExternalOrderJoinOperation,
        ExternalOrderJoinRow,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPECS
    from finproof.data.normalization.domestic_listed import normalize_domestic_listed
    from finproof.data.normalization.public_funds import (
        collapse_fund_items,
        normalize_fund_attribute,
    )
    from tests.helpers.source_rows import source_row

    domestic_source = source_row("PREF01N001")
    domestic_result = normalize_domestic_listed(domestic_source, date(2026, 7, 11))
    assert domestic_result.record is not None
    domestic = domestic_result.record
    fund_result = normalize_fund_attribute(source_row("PRFD01N001"))
    assert fund_result.record is not None
    fund = collapse_fund_items((fund_result.record,)).items[0]
    cell = domestic_source.cell("pd_itm_no")
    bronze_cell = BronzeSourceCellRecord(
        source_table_order=1,
        source_table=domestic_source.source_table,
        source_file=domestic_source.source_file,
        source_sheet=domestic_source.source_sheet,
        source_row_number=domestic_source.source_row_number,
        source_column_name=cell.column_name,
        source_column_number=cell.excel_column_number,
        source_column_letter=cell.excel_column_letter,
        source_checksum=domestic_source.source_checksum,
        source_snapshot_date=domestic_source.source_snapshot_date,
        source_applicable_date=cell.applicable_date,
        raw_value=cell.raw_value,
    )
    link = ExactCrossSourceLinkRecord(
        link_id="b" * 64,
        left_table="silver_domestic_listed_product",
        left_product_id=str(domestic.product_id.normalized_value),
        left_identifier_field="pd_itm_no",
        right_table="silver_fund_item",
        right_product_id=str(fund.fund_item_id.representative.normalized_value),
        right_identifier_field="ksd_itm_no",
        matched_raw_identifier=cell.raw_value,
        link_type="exact_identifier",
        confidence=Decimal("1.0"),
        rule_id="cross_source.domestic_etf_public_fund.exact_raw_identifier",
        rule_version="1.0.0",
    )
    evidence = ExactCrossSourceLinkEvidenceRecord(
        link_id=link.link_id,
        evidence_role="left_identifier",
        evidence_role_order=0,
        evidence_ordinal=0,
        raw_identifier=cell.raw_value,
        source_table=bronze_cell.source_table,
        source_file=bronze_cell.source_file,
        source_sheet=bronze_cell.source_sheet,
        source_row_number=bronze_cell.source_row_number,
        source_column_name=bronze_cell.source_column_name,
        source_column_number=bronze_cell.source_column_number,
        source_column_letter=bronze_cell.source_column_letter,
        source_checksum=bronze_cell.source_checksum,
        source_snapshot_date=bronze_cell.source_snapshot_date,
        source_applicable_date=bronze_cell.source_applicable_date,
    )
    rows_by_table = {
        "bronze_source_cell": (serialize_table_row(TABLE_SPECS[2], bronze_cell),),
        "silver_domestic_listed_product": (serialize_table_row(TABLE_SPECS[4], domestic),),
        "silver_fund_item": (serialize_table_row(TABLE_SPECS[6], fund),),
        "gold_exact_cross_source_link": (serialize_table_row(TABLE_SPECS[9], link),),
        "gold_exact_cross_source_link_evidence": (serialize_table_row(TABLE_SPECS[10], evidence),),
    }
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
        verifications = []
        for spec in TABLE_SPECS:
            leaf = session.claim_parquet_leaf(spec)
            writer = ParquetBatchWriter(spec, leaf)
            if rows := rows_by_table.get(spec.table_name):
                writer.write_batch(rows)
            writer.close()
            verifications.append(verify_staged_parquet_table(owner=session, leaf=leaf, spec=spec))
        tables = StagedParquetSet.from_verified(
            owner=session,
            verifications=tuple(verifications),
        )

        evidence_rows = tuple(
            row
            for batch in store.iter_join_batches(
                operation=ExternalOrderJoinOperation.EXACT_EVIDENCE_TO_BRONZE,
                tables=tables,
            )
            for row in batch
        )
        domestic_rows = tuple(
            row
            for batch in store.iter_join_batches(
                operation=ExternalOrderJoinOperation.LINKED_DOMESTIC_RECORD_JSON,
                tables=tables,
                exact_ids=(str(domestic.product_id.normalized_value),),
            )
            for row in batch
        )
        fund_rows = tuple(
            row
            for batch in store.iter_join_batches(
                operation=ExternalOrderJoinOperation.LINKED_FUND_RECORD_JSON,
                tables=tables,
                exact_ids=(str(fund.fund_item_id.representative.normalized_value),),
            )
            for row in batch
        )

        assert evidence_rows == (
            ExternalOrderJoinRow(
                key=(link.link_id, 0, 0),
                values=(cell.raw_value, 1),
            ),
        )
        assert domestic_rows == (
            ExternalOrderJoinRow(
                key=(str(domestic.product_id.normalized_value),),
                values=(canonical_record_json(domestic),),
            ),
        )
        assert fund_rows == (
            ExternalOrderJoinRow(
                key=(str(fund.fund_item_id.representative.normalized_value),),
                values=(canonical_record_json(fund),),
            ),
        )


def test_exact_link_candidate_custody_is_factory_only_live_generation_bound_noncopyable_and_nonserializable(  # noqa: E501
    tmp_path: Path,
) -> None:
    import copy
    import pickle

    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExactLinkCandidateStoreCustody,
    )

    settings = _staging_settings(tmp_path / "repository")
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
    with ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ) as session:
        store_context = session.open_external_order_store(config=config)
        store = store_context.__enter__()
        custody = ExactLinkCandidateStoreCustody._issue(owner=session, store=store)

        assert type(custody) is ExactLinkCandidateStoreCustody
        assert not hasattr(custody, "__dict__")
        with pytest.raises(TypeError):
            ExactLinkCandidateStoreCustody()
        with pytest.raises(TypeError):
            copy.copy(custody)
        with pytest.raises(TypeError):
            copy.deepcopy(custody)
        with pytest.raises(TypeError):
            pickle.dumps(custody)

    with pytest.raises(ArtifactContractError):
        custody.iter_candidate_join_batches()


@pytest.mark.parametrize(
    "case",
    [
        "domestic-empty-id",
        "domestic-wrong-role",
        "domestic-wrong-table",
        "domestic-wrong-column",
        "domestic-dict-source",
        "fund-empty-id",
        "fund-no-sources",
        "fund-list-sources",
        "fund-wrong-table",
        "fund-wrong-column",
        "fund-duplicate-sources",
        "fund-reordered-sources",
        "fund-disagreeing-raw",
        "fund-dict-source",
    ],
)
def test_exact_link_candidate_schemas_require_exact_role_locator_and_ordered_fund_sources(
    case: str,
) -> None:
    from datetime import date
    from pathlib import PurePosixPath

    from pydantic import ValidationError

    from finproof.data.artifacts.staging import (
        DomesticExactLinkCandidate,
        ExactLinkIdentifierSource,
        FundExactLinkCandidate,
    )
    from finproof.domain.locators import SourceCellLocator

    def locator(*, table: str, column: str, row: int) -> SourceCellLocator:
        return SourceCellLocator(
            source_table=table,
            source_file=PurePosixPath(f"data/{table}.xlsx"),
            source_sheet="Sheet1",
            source_row_number=row,
            source_column_name=column,
            source_column_number=1,
            source_column_letter="A",
            source_checksum="a" * 64,
            source_snapshot_date=date(2026, 7, 11),
            source_applicable_date=None,
        )

    left_locator = locator(table="PREF01N001", column="pd_itm_no", row=2)
    right_first = locator(table="PRFD01N001", column="ksd_itm_no", row=2)
    right_second = locator(table="PRFD01N001", column="ksd_itm_no", row=3)
    left_source = ExactLinkIdentifierSource(
        raw_identifier="KR7000000001",
        locator=left_locator,
    )
    right_source = ExactLinkIdentifierSource(
        raw_identifier="KR7000000001",
        locator=right_first,
    )
    right_source_second = ExactLinkIdentifierSource(
        raw_identifier="KR7000000001",
        locator=right_second,
    )

    assert (
        DomesticExactLinkCandidate(
            left_product_id="KR7000000001",
            source_product_type="ETF",
            identifier=left_source,
        ).identifier
        is left_source
    )
    assert FundExactLinkCandidate(
        right_product_id="F0001",
        identifiers=(right_source, right_source_second),
    ).identifiers == (right_source, right_source_second)

    with pytest.raises((TypeError, ValidationError, ValueError)):  # noqa: PT012
        if case == "domestic-empty-id":
            DomesticExactLinkCandidate(
                left_product_id="", source_product_type="ETF", identifier=left_source
            )
        elif case == "domestic-wrong-role":
            DomesticExactLinkCandidate(
                left_product_id="KR7000000001",
                source_product_type="ETN",
                identifier=left_source,
            )
        elif case == "domestic-wrong-table":
            DomesticExactLinkCandidate(
                left_product_id="KR7000000001",
                source_product_type="ETF",
                identifier=ExactLinkIdentifierSource(
                    raw_identifier="KR7000000001",
                    locator=locator(table="PREF02N001", column="pd_itm_no", row=2),
                ),
            )
        elif case == "domestic-wrong-column":
            DomesticExactLinkCandidate(
                left_product_id="KR7000000001",
                source_product_type="ETF",
                identifier=ExactLinkIdentifierSource(
                    raw_identifier="KR7000000001",
                    locator=locator(table="PREF01N001", column="std_pd_cd", row=2),
                ),
            )
        elif case == "domestic-dict-source":
            DomesticExactLinkCandidate(
                left_product_id="KR7000000001",
                source_product_type="ETF",
                identifier=left_source.model_dump(),
            )
        elif case == "fund-empty-id":
            FundExactLinkCandidate(right_product_id="", identifiers=(right_source,))
        elif case == "fund-no-sources":
            FundExactLinkCandidate(right_product_id="F0001", identifiers=())
        elif case == "fund-list-sources":
            FundExactLinkCandidate(right_product_id="F0001", identifiers=[right_source])
        elif case == "fund-wrong-table":
            FundExactLinkCandidate(
                right_product_id="F0001",
                identifiers=(
                    ExactLinkIdentifierSource(
                        raw_identifier="KR7000000001",
                        locator=locator(table="PREF01N001", column="ksd_itm_no", row=2),
                    ),
                ),
            )
        elif case == "fund-wrong-column":
            FundExactLinkCandidate(
                right_product_id="F0001",
                identifiers=(
                    ExactLinkIdentifierSource(
                        raw_identifier="KR7000000001",
                        locator=locator(table="PRFD01N001", column="itm_no", row=2),
                    ),
                ),
            )
        elif case == "fund-duplicate-sources":
            FundExactLinkCandidate(
                right_product_id="F0001", identifiers=(right_source, right_source)
            )
        elif case == "fund-reordered-sources":
            FundExactLinkCandidate(
                right_product_id="F0001",
                identifiers=(right_source_second, right_source),
            )
        elif case == "fund-disagreeing-raw":
            FundExactLinkCandidate(
                right_product_id="F0001",
                identifiers=(
                    right_source,
                    ExactLinkIdentifierSource(raw_identifier="KR7000000002", locator=right_second),
                ),
            )
        else:
            FundExactLinkCandidate(
                right_product_id="F0001",
                identifiers=(right_source.model_dump(),),
            )


def test_candidate_custody_streams_only_bounded_typed_exact_join_rows_without_generic_surface(
    tmp_path: Path,
) -> None:
    from datetime import date
    from pathlib import PurePosixPath

    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.serialization import canonical_record_json
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        DomesticExactLinkCandidate,
        ExactLinkCandidateJoinRow,
        ExactLinkCandidateStoreCustody,
        ExactLinkIdentifierSource,
        ExternalOrderRelation,
        ExternalOrderRow,
        ExternalOrderStoreTestLimits,
        FundExactLinkCandidate,
        _open_external_order_store_for_test,
    )
    from finproof.domain.locators import SourceCellLocator

    def source(*, table: str, column: str, row: int, raw: str) -> ExactLinkIdentifierSource:
        return ExactLinkIdentifierSource(
            raw_identifier=raw,
            locator=SourceCellLocator(
                source_table=table,
                source_file=PurePosixPath(f"data/{table}.xlsx"),
                source_sheet="Sheet1",
                source_row_number=row,
                source_column_name=column,
                source_column_number=1,
                source_column_letter="A",
                source_checksum="a" * 64,
                source_snapshot_date=date(2026, 7, 11),
                source_applicable_date=None,
            ),
        )

    lefts = tuple(
        DomesticExactLinkCandidate(
            left_product_id=product_id,
            source_product_type="ETF",
            identifier=source(table="PREF01N001", column="pd_itm_no", row=row, raw=raw),
        )
        for product_id, raw, row in (
            ("L2", "RAW-B", 3),
            ("L1", "RAW-A", 2),
        )
    )
    rights = tuple(
        FundExactLinkCandidate(
            right_product_id=product_id,
            identifiers=(source(table="PRFD01N001", column="ksd_itm_no", row=row, raw=raw),),
        )
        for product_id, raw, row in (
            ("R2", "RAW-B", 3),
            ("R1", "RAW-A", 2),
        )
    )
    settings = _staging_settings(tmp_path / "repository")
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
    with ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ) as session:
        store_context = _open_external_order_store_for_test(
            owner=session,
            config=config,
            limits=ExternalOrderStoreTestLimits(batch_rows=1, memory_limit_bytes=1 << 30),
        )
        store = store_context.__enter__()
        store.insert_batch(
            relation=ExternalOrderRelation.EXACT_LINK_LEFT_CANDIDATE,
            rows=(
                ExternalOrderRow(
                    key=(item.identifier.raw_identifier, item.left_product_id),
                    payload_json=canonical_record_json(item),
                )
                for item in lefts
            ),
        )
        store.insert_batch(
            relation=ExternalOrderRelation.EXACT_LINK_RIGHT_CANDIDATE,
            rows=(
                ExternalOrderRow(
                    key=(item.identifiers[0].raw_identifier, item.right_product_id),
                    payload_json=canonical_record_json(item),
                )
                for item in rights
            ),
        )
        custody = ExactLinkCandidateStoreCustody._issue(owner=session, store=store)

        public_surface = {name for name in dir(custody) if not name.startswith("_")}
        assert public_surface == {
            "admit_exact_evidence",
            "close",
            "iter_candidate_join_batches",
        }
        batches = custody.iter_candidate_join_batches()
        first = next(batches)
        assert len(first) == 1
        assert type(first[0]) is ExactLinkCandidateJoinRow
        with pytest.raises(ArtifactContractError):
            custody.iter_candidate_join_batches()
        remaining = tuple(batches)
        assert all(0 < len(batch) <= 1 for batch in remaining)
        rows = first + tuple(row for batch in remaining for row in batch)
        assert tuple(
            (row.matched_raw_identifier, row.left.left_product_id, row.right.right_product_id)
            for row in rows
        ) == (("RAW-A", "L1", "R1"), ("RAW-B", "L2", "R2"))
        with pytest.raises(ArtifactContractError):
            custody.iter_candidate_join_batches()


def test_candidate_custody_close_closes_and_deregisters_store_exactly_once(
    tmp_path: Path,
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
        ExactLinkCandidateStoreCustody,
    )

    settings = _staging_settings(tmp_path / "repository")
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
    with ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ) as session:
        store_context = session.open_external_order_store(config=config)
        store = store_context.__enter__()
        custody = ExactLinkCandidateStoreCustody._issue(owner=session, store=store)

        custody.close()

        assert session._live_external_order_stores == {}
        assert store._closed is True
        assert store._cleanup_state == "CLEANED"
        with pytest.raises(ArtifactContractError):
            custody.close()
        assert store._cleanup_state == "CLEANED"


@pytest.mark.parametrize("case", ["custody-close", "managed-abort"])
def test_candidate_custody_close_abort_and_cleanup_faults_are_typed_and_never_retry(
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
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExactLinkCandidateStoreCustody,
        ExternalOrderStore,
    )

    settings = _staging_settings(tmp_path / "repository")
    config = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG)
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ).__enter__()
    store_context = session.open_external_order_store(config=config)
    store = store_context.__enter__()
    custody = ExactLinkCandidateStoreCustody._issue(owner=session, store=store)
    original_close = ExternalOrderStore.close_and_remove_working_state
    attempts = 0

    def fail_close(value: ExternalOrderStore) -> None:
        nonlocal attempts
        assert value is store
        attempts += 1
        raise OSError("injected exact-link candidate cleanup fault")

    monkeypatch.setattr(ExternalOrderStore, "close_and_remove_working_state", fail_close)
    if case == "custody-close":
        with pytest.raises(ArtifactContractError) as captured:
            custody.close()
        assert captured.value.code is ArtifactErrorCode.STAGING_CLEANUP_FAILED
        assert captured.value.operation_id == "build-session"
        assert captured.value.internal_context == {
            "reason": "exact_link_candidate_store_close_failed"
        }
        with pytest.raises(ArtifactContractError):
            custody.close()
        assert attempts == 1
        monkeypatch.setattr(
            ExternalOrderStore,
            "close_and_remove_working_state",
            original_close,
        )
        store.close_and_remove_working_state()
        session.abort()
    else:
        with pytest.raises(ArtifactContractError) as captured:
            session.abort()
        assert captured.value.code is ArtifactErrorCode.STAGING_CLEANUP_FAILED
        assert captured.value.operation_id == "build-session"
        assert captured.value.internal_context == {
            "reason": "exact_link_candidate_store_abort_cleanup_failed"
        }
        assert attempts == 1


def test_candidate_custody_admits_exact_evidence_once_with_numeric_key_payload_order_and_bounded_batches(  # noqa: E501
    tmp_path: Path,
) -> None:
    from datetime import date
    from pathlib import PurePosixPath

    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import (
        _EXPECTED_ARTIFACT_CONFIG,
        ArtifactBuildConfig,
        ArtifactBuildOptions,
    )
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.serialization import (
        ExactCrossSourceLinkEvidenceRecord,
        canonical_record_json,
    )
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExactLinkCandidateStoreCustody,
        ExternalOrderRelation,
        ExternalOrderStoreTestLimits,
        _open_external_order_store_for_test,
    )

    payload = ArtifactBuildConfig.model_validate(_EXPECTED_ARTIFACT_CONFIG).model_dump(
        mode="python"
    )
    payload["exact_links"]["evidence"] = 2
    config = ArtifactBuildConfig.model_validate(payload, strict=True)
    evidence = tuple(
        ExactCrossSourceLinkEvidenceRecord(
            link_id="a" * 64,
            evidence_role="left_identifier" if role_order == 0 else "right_identifier",
            evidence_role_order=role_order,
            evidence_ordinal=0,
            raw_identifier="KR7000000001",
            source_table="PREF01N001" if role_order == 0 else "PRFD01N001",
            source_file=PurePosixPath("data/source.xlsx"),
            source_sheet="Sheet1",
            source_row_number=role_order + 2,
            source_column_name="pd_itm_no" if role_order == 0 else "ksd_itm_no",
            source_column_number=1,
            source_column_letter="A",
            source_checksum="a" * 64,
            source_snapshot_date=date(2026, 7, 11),
            source_applicable_date=None,
        )
        for role_order in (0, 1)
    )
    settings = _staging_settings(tmp_path / "repository")
    with ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ) as session:
        store_context = _open_external_order_store_for_test(
            owner=session,
            config=config,
            limits=ExternalOrderStoreTestLimits(batch_rows=1, memory_limit_bytes=1 << 30),
        )
        store = store_context.__enter__()
        custody = ExactLinkCandidateStoreCustody._issue(owner=session, store=store)
        assert tuple(custody.iter_candidate_join_batches()) == ()

        custody.admit_exact_evidence(iter(evidence))

        stored_batches = tuple(
            store.iter_ordered_batches(relation=ExternalOrderRelation.EXACT_LINK_EVIDENCE)
        )
        assert tuple(len(batch) for batch in stored_batches) == (1, 1)
        stored = tuple(row for batch in stored_batches for row in batch)
        assert tuple(row.key for row in stored) == (("a" * 64, 0, 0), ("a" * 64, 1, 0))
        assert tuple(row.payload_json for row in stored) == tuple(
            canonical_record_json(row) for row in evidence
        )
        with pytest.raises(ArtifactContractError):
            custody.admit_exact_evidence(())


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
        ExternalOrderRow,
        ExternalOrderStoreTestLimits,
        _open_external_order_store_for_test,
    )

    class OnePassRows:
        def __init__(self) -> None:
            self.iterations = 0

        def __len__(self) -> int:
            raise AssertionError("the source must never be materialized for sizing")

        def __iter__(self) -> Iterator[ExternalOrderRow]:
            if self.iterations:
                raise AssertionError("the source must be consumed exactly once")
            self.iterations += 1
            for key in ("k7", "k2", "k5", "k1", "k6", "k3", "k4"):
                yield ExternalOrderRow(key=(key,), payload_json=f'{{"key":"{key}"}}')

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
            relation=ExternalOrderRelation.SILVER_BOND_INSTRUMENT,
            rows=rows,
        )
        batches = tuple(
            store.iter_ordered_batches(relation=ExternalOrderRelation.SILVER_BOND_INSTRUMENT)
        )
        assert all(1 <= len(batch) <= limits.batch_rows for batch in batches)
        assert tuple(row.key for batch in batches for row in batch) == tuple(
            (key,) for key in ("k1", "k2", "k3", "k4", "k5", "k6", "k7")
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
