"""CP7B publication rollback fault boundaries."""

import shutil
from contextlib import suppress
from pathlib import Path

import pytest

from tests.helpers.artifact_filesystem import SyntheticPublicationAuthorization


def test_real_expected_publication_cleanly_replaces_verified_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime

    from finproof.data.artifacts import database
    from finproof.data.artifacts.builder import _build_evaluation_artifacts_with_outcome
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.manifest import ArtifactManifest
    from tests.integration.artifacts.test_candidate_builder import _install_small_fixture

    settings, versions = _install_small_fixture(tmp_path, monkeypatch)

    def accept_expected(_self: object, *, actual: object) -> None:
        del actual

    monkeypatch.setattr(database.PackagedArtifactExpectedComparator, "compare", accept_expected)
    first_timestamp = datetime(2026, 8, 15, tzinfo=UTC)
    second_timestamp = datetime(2026, 8, 15, 0, 0, 1, tzinfo=UTC)
    _build_evaluation_artifacts_with_outcome(
        settings,
        versions,
        options=ArtifactBuildOptions(persistence_timestamp=first_timestamp),
    )
    first_manifest = ArtifactManifest.load(settings.artifact_dir / "manifest.json")

    second = _build_evaluation_artifacts_with_outcome(
        settings,
        versions,
        options=ArtifactBuildOptions(
            clean=True,
            persistence_timestamp=second_timestamp,
        ),
    )

    assert first_manifest.persistence_timestamp == first_timestamp
    assert second.manifest.persistence_timestamp == second_timestamp
    assert (
        ArtifactManifest.load(settings.artifact_dir / "manifest.json").persistence_timestamp
        == second_timestamp
    )
    assert not tuple(settings.repository_root.glob(".artifacts.finproof-stage-*"))
    assert not tuple(settings.repository_root.glob(".artifacts.finproof-backup-*"))
    assert not tuple(settings.repository_root.glob(".artifacts.finproof-cleanup-*"))


def test_real_clean_blocks_tombstone_substitution_after_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime, timedelta

    from finproof.data.artifacts import database
    from finproof.data.artifacts.builder import _build_evaluation_artifacts_with_outcome
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.manifest import ArtifactManifest
    from finproof.data.artifacts.publication import _PublishedArtifactFilesystem
    from tests.integration.artifacts.test_candidate_builder import _install_small_fixture

    settings, versions = _install_small_fixture(tmp_path, monkeypatch)

    def accept_expected(_self: object, *, actual: object) -> None:
        del actual

    monkeypatch.setattr(database.PackagedArtifactExpectedComparator, "compare", accept_expected)
    timestamp = datetime(2026, 8, 15, tzinfo=UTC)
    _build_evaluation_artifacts_with_outcome(
        settings,
        versions,
        options=ArtifactBuildOptions(persistence_timestamp=timestamp),
    )
    verify_named_artifact = _PublishedArtifactFilesystem._verify_named_artifact
    delete_tombstone = _PublishedArtifactFilesystem.delete_tombstone
    displaced = settings.repository_root / ".verified-tombstone"
    victim: Path | None = None
    deleting = False

    def substitute_after_verification(
        self: _PublishedArtifactFilesystem,
        name: str,
    ) -> ArtifactManifest:
        nonlocal victim
        verified = verify_named_artifact(self, name)
        if deleting:
            original = settings.repository_root / name
            original.rename(displaced)
            shutil.copytree(displaced, original)
            victim = original
        return verified

    def delete_with_substitution(self: _PublishedArtifactFilesystem) -> None:
        nonlocal deleting
        deleting = True
        try:
            delete_tombstone(self)
        finally:
            deleting = False

    monkeypatch.setattr(
        _PublishedArtifactFilesystem,
        "_verify_named_artifact",
        substitute_after_verification,
    )
    monkeypatch.setattr(
        _PublishedArtifactFilesystem,
        "delete_tombstone",
        delete_with_substitution,
    )

    with pytest.raises(ArtifactContractError) as caught:
        _build_evaluation_artifacts_with_outcome(
            settings,
            versions,
            options=ArtifactBuildOptions(
                clean=True,
                persistence_timestamp=timestamp + timedelta(seconds=1),
            ),
        )

    assert caught.value.code is ArtifactErrorCode.BACKUP_CLEANUP_FAILED_AFTER_PUBLISH
    assert settings.artifact_dir.is_dir()
    assert displaced.is_dir()
    assert victim is not None
    assert victim.is_dir()


def test_expected_mismatch_blocks_before_first_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime

    from finproof.data.artifacts.builder import _build_evaluation_artifacts_with_outcome
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from tests.integration.artifacts.test_candidate_builder import _install_small_fixture

    settings, versions = _install_small_fixture(tmp_path, monkeypatch)

    with pytest.raises(ArtifactContractError) as caught:
        _build_evaluation_artifacts_with_outcome(
            settings,
            versions,
            options=ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        )

    assert caught.value.code is ArtifactErrorCode.REPRODUCIBILITY_MISMATCH
    assert not settings.artifact_dir.exists()
    assert not tuple(settings.repository_root.glob(".artifacts.finproof-stage-*"))


def test_expected_publication_transition_and_precommit_rollback_use_transferred_custody(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime

    from finproof.data.artifacts import database
    from finproof.data.artifacts.builder import _build_private_live_candidate
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.publication import (
        authorize_candidate_for_publication,
        publish_verified_stage,
    )
    from tests.integration.artifacts.test_candidate_builder import _install_small_fixture

    settings, versions = _install_small_fixture(tmp_path, monkeypatch)
    carrier = _build_private_live_candidate(
        settings,
        versions,
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
    )
    candidate = object.__getattribute__(carrier, "_issuance").candidate

    def accept_expected(_self: object, *, actual: object) -> None:
        del actual

    monkeypatch.setattr(database.PackagedArtifactExpectedComparator, "compare", accept_expected)

    class FailingTargetVerification:
        observed_target = False

        def target_exists(self) -> bool:
            return False

        def verify_target(self) -> None:
            self.observed_target = settings.artifact_dir.is_dir()
            assert (settings.artifact_dir / "manifest.json").is_file()
            raise ArtifactContractError(
                ArtifactErrorCode.EXACT_TREE_MISMATCH,
                operation_id="injected-target-verification",
            )

        def __getattr__(self, name: str) -> object:
            raise AssertionError(f"unexpected filesystem operation: {name}")

    filesystem = FailingTargetVerification()
    with (
        pytest.raises(ArtifactContractError),
        authorize_candidate_for_publication(candidate) as authorized,
    ):
        publish_verified_stage(
            authorized,
            settings=settings,
            clean=False,
            filesystem=filesystem,  # type: ignore[arg-type]
        )

    assert filesystem.observed_target is True
    assert not settings.artifact_dir.exists()
    assert not tuple(settings.repository_root.glob(".artifacts.finproof-stage-*"))


@pytest.mark.parametrize("case", ["receiver-fault", "early-close", "success"])
def test_expected_publication_cleanup_closes_transferred_custody_exactly_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    import os
    from datetime import UTC, datetime

    from finproof.data.artifacts import database
    from finproof.data.artifacts.builder import _build_private_live_candidate
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.publication import (
        ExpectedAcceptedPublicationStage,
        authorize_candidate_for_publication,
        publish_verified_stage,
    )
    from tests.integration.artifacts.test_candidate_builder import _install_small_fixture

    settings, versions = _install_small_fixture(tmp_path, monkeypatch)
    carrier = _build_private_live_candidate(
        settings,
        versions,
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
    )
    candidate = object.__getattribute__(carrier, "_issuance").candidate
    descriptors = tuple(
        getattr(candidate._custody, name)
        for name in ("_parent_fd", "_stage_fd", "_parquet_fd", "_lock_fd")
    )

    def accept_expected(_self: object, *, actual: object) -> None:
        del actual

    monkeypatch.setattr(database.PackagedArtifactExpectedComparator, "compare", accept_expected)
    if case == "receiver-fault":

        def fail_receiver(_self: object, **kwargs: object) -> None:
            del kwargs
            raise RuntimeError("injected receiver failure")

        monkeypatch.setattr(
            ExpectedAcceptedPublicationStage,
            "preflight_expected_accepted_custody",
            fail_receiver,
        )

    class SuccessfulFilesystem:
        def target_exists(self) -> bool:
            return False

        def verify_target(self) -> None:
            assert (settings.artifact_dir / "manifest.json").is_file()

        def __getattr__(self, name: str) -> object:
            raise AssertionError(f"unexpected filesystem operation: {name}")

    authorized: ExpectedAcceptedPublicationStage | None = None
    try:
        if case == "receiver-fault":
            with (
                pytest.raises(RuntimeError, match="injected receiver failure"),
                authorize_candidate_for_publication(candidate),
            ):
                pytest.fail("receiver fault yielded publication authority")
        else:
            with authorize_candidate_for_publication(candidate) as authorized:
                if case == "early-close":
                    authorized.close()
                else:
                    publish_verified_stage(
                        authorized,
                        settings=settings,
                        clean=False,
                        filesystem=SuccessfulFilesystem(),  # type: ignore[arg-type]
                    )
            authorized.close()
        for descriptor in descriptors:
            with pytest.raises(OSError, match="Bad file descriptor"):
                os.fstat(descriptor)
    finally:
        with suppress(Exception):
            candidate._custody.close()


def _assert_first_publish_fault_rolls_back(
    tmp_path: Path,
    fault: str,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.publication import PublicationState

    authorization = SyntheticPublicationAuthorization(
        tmp_path / "repository",
        expected_accepted=True,
        faults=frozenset({fault}),
    )
    unrelated = authorization.root / "unrelated"
    unrelated.write_bytes(b"keep\n")
    unrelated_before = (unrelated.stat().st_ino, unrelated.stat().st_mode, unrelated.read_bytes())
    machine = authorization.state_machine()
    with pytest.raises(ArtifactContractError) as raised:
        machine.publish(clean=False)
    assert raised.value.published is False
    assert machine.state is PublicationState.STAGE_VERIFIED
    assert authorization.stage.is_dir()
    assert (authorization.stage / "manifest.json").read_bytes() == b"new\n"
    assert authorization.stage_marker.read_bytes() == authorization.marker_payload
    assert not (authorization.root / "artifacts").exists()
    assert not tuple(authorization.root.glob("*.finproof-backup-*"))
    assert not tuple(authorization.root.glob("*.finproof-cleanup-*"))
    assert (
        unrelated.stat().st_ino,
        unrelated.stat().st_mode,
        unrelated.read_bytes(),
    ) == unrelated_before


def test_first_publish_verification_failure_rolls_target_back_to_marked_stage(
    tmp_path: Path,
) -> None:
    _assert_first_publish_fault_rolls_back(tmp_path, "target_verify")


def test_first_publish_stage_marker_unlink_failure_rolls_target_back_to_marked_stage(
    tmp_path: Path,
) -> None:
    _assert_first_publish_fault_rolls_back(tmp_path, "stage_marker_unlink")


def test_first_publish_target_to_stage_rollback_failure_is_typed_and_preserved(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.publication import PublicationState

    authorization = SyntheticPublicationAuthorization(
        tmp_path / "repository",
        expected_accepted=True,
        faults=frozenset({"target_verify", "target_to_stage"}),
    )
    machine = authorization.state_machine()
    with pytest.raises(ArtifactContractError) as raised:
        machine.publish(clean=False)
    assert raised.value.code is ArtifactErrorCode.PUBLICATION_ROLLBACK_FAILED
    assert raised.value.published is False
    assert machine.state is PublicationState.TARGET_RENAMED_UNCOMMITTED
    assert not authorization.stage.exists()
    assert (authorization.root / "artifacts" / "manifest.json").read_bytes() == b"new\n"
    assert authorization.stage_marker.read_bytes() == authorization.marker_payload
    assert raised.value.internal_context["stage_path"] == str(authorization.stage)
    assert raised.value.internal_context["target_path"] == str(authorization.root / "artifacts")
    assert str(authorization.stage) not in raised.value.safe_message
    assert str(authorization.root) not in raised.value.safe_message


@pytest.mark.parametrize(
    "fault",
    ["old_target_to_backup", "stage_to_target", "target_verify", "stage_marker_unlink"],
)
def test_existing_target_precommit_fault_restores_old_generation_byte_identically(
    tmp_path: Path,
    fault: str,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.publication import PublicationState

    authorization = SyntheticPublicationAuthorization(
        tmp_path / "repository",
        expected_accepted=True,
        faults=frozenset({fault}),
    )
    target = authorization.root / "artifacts"
    target.mkdir(mode=0o751)
    manifest = target / "manifest.json"
    manifest.write_bytes(b"old\n")
    old = (
        target.stat().st_ino,
        target.stat().st_mode,
        manifest.stat().st_ino,
        manifest.read_bytes(),
    )
    unrelated = authorization.root / "unrelated"
    unrelated.write_bytes(b"keep\n")
    unrelated_before = (unrelated.stat().st_ino, unrelated.stat().st_mode, unrelated.read_bytes())
    machine = authorization.state_machine()
    with pytest.raises(ArtifactContractError) as raised:
        machine.publish(clean=True)
    assert raised.value.published is False
    assert fault in authorization.fault_hits
    assert machine.state is PublicationState.STAGE_VERIFIED
    assert (
        target.stat().st_ino,
        target.stat().st_mode,
        manifest.stat().st_ino,
        manifest.read_bytes(),
    ) == old
    assert (authorization.stage / "manifest.json").read_bytes() == b"new\n"
    assert authorization.stage_marker.exists()
    assert not tuple(authorization.root.glob("*.finproof-backup-*"))
    assert not tuple(authorization.root.glob("*.finproof-cleanup-*"))
    assert (
        unrelated.stat().st_ino,
        unrelated.stat().st_mode,
        unrelated.read_bytes(),
    ) == unrelated_before


@pytest.mark.parametrize(
    ("faults", "expected_state"),
    [
        (
            frozenset({"stage_to_target", "backup_to_target"}),
            "backup_verified",
        ),
        (
            frozenset({"target_verify", "target_to_stage"}),
            "target_renamed_uncommitted",
        ),
    ],
)
def test_existing_target_failed_restoration_is_typed_and_preserves_recovery_paths(
    tmp_path: Path,
    faults: frozenset[str],
    expected_state: str,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    authorization = SyntheticPublicationAuthorization(
        tmp_path / "repository",
        expected_accepted=True,
        faults=faults,
    )
    target = authorization.root / "artifacts"
    target.mkdir(mode=0o751)
    (target / "manifest.json").write_bytes(b"old\n")
    machine = authorization.state_machine()
    with pytest.raises(ArtifactContractError) as raised:
        machine.publish(clean=True)
    assert raised.value.code is ArtifactErrorCode.PUBLICATION_ROLLBACK_FAILED
    assert raised.value.published is False
    assert machine.state.value == expected_state
    assert authorization.backup_marker.read_bytes() == authorization.marker_payload
    assert (authorization.backup / "manifest.json").read_bytes() == b"old\n"
    assert raised.value.internal_context["backup_path"] == str(authorization.backup)
    assert raised.value.internal_context["target_path"] == str(target)
    assert str(authorization.backup) not in raised.value.safe_message
    assert str(authorization.root) not in raised.value.safe_message
    if expected_state == "backup_verified":
        assert (authorization.stage / "manifest.json").read_bytes() == b"new\n"
        assert not target.exists()
    else:
        assert not authorization.stage.exists()
        assert (target / "manifest.json").read_bytes() == b"new\n"


def test_backup_to_tombstone_rename_failure_preserves_verified_backup_and_new_target(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.publication import PublicationState

    authorization = SyntheticPublicationAuthorization(
        tmp_path / "repository",
        expected_accepted=True,
        faults=frozenset({"backup_to_tombstone"}),
    )
    target = authorization.root / "artifacts"
    target.mkdir(mode=0o751)
    (target / "manifest.json").write_bytes(b"old\n")
    machine = authorization.state_machine()
    with pytest.raises(ArtifactContractError) as raised:
        machine.publish(clean=True)
    assert raised.value.code is ArtifactErrorCode.BACKUP_CLEANUP_FAILED_AFTER_PUBLISH
    assert raised.value.published is True
    assert machine.state is PublicationState.BACKUP_WITH_PREPARED_TOMBSTONE_MARKER
    assert "backup_to_tombstone" in authorization.fault_hits
    assert (target / "manifest.json").read_bytes() == b"new\n"
    assert (authorization.backup / "manifest.json").read_bytes() == b"old\n"
    assert authorization.backup_marker.read_bytes() == authorization.marker_payload
    assert authorization.tombstone_marker.read_bytes() == authorization.marker_payload
    assert not authorization.tombstone.exists()
    assert str(authorization.root) not in raised.value.safe_message


def test_publication_markers_bind_operation_artifact_contract_and_target(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError

    marker_payload = (
        b'{"artifact_contract_version":"1.0.0",'
        b'"artifact_set_id":"finproof-data-artifacts/v1",'
        b'"operation_id":"operation","target_basename":"artifacts"}'
    )
    authorization = SyntheticPublicationAuthorization(
        tmp_path / "repository",
        expected_accepted=True,
        faults=frozenset({"backup_to_tombstone"}),
    )
    target = authorization.root / "artifacts"
    target.mkdir(mode=0o751)
    (target / "manifest.json").write_bytes(b"old\n")
    with pytest.raises(ArtifactContractError):
        authorization.state_machine().publish(clean=True)
    for marker in (authorization.backup_marker, authorization.tombstone_marker):
        assert marker.read_bytes() == marker_payload
        assert marker.stat().st_mode & 0o777 == 0o600


def test_tombstone_delete_failure_never_rolls_back_published_target(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.publication import PublicationState

    authorization = SyntheticPublicationAuthorization(
        tmp_path / "repository",
        expected_accepted=True,
        faults=frozenset({"delete_tombstone"}),
    )
    target = authorization.root / "artifacts"
    target.mkdir(mode=0o751)
    (target / "manifest.json").write_bytes(b"old\n")
    machine = authorization.state_machine()
    with pytest.raises(ArtifactContractError) as raised:
        machine.publish(clean=True)
    assert raised.value.code is ArtifactErrorCode.BACKUP_CLEANUP_FAILED_AFTER_PUBLISH
    assert raised.value.published is True
    assert machine.state is PublicationState.TOMBSTONE_WITH_BOTH_MARKERS
    assert "delete_tombstone" in authorization.fault_hits
    assert (target / "manifest.json").read_bytes() == b"new\n"
    assert not authorization.backup.exists()
    assert (authorization.tombstone / "manifest.json").read_bytes() == b"old\n"
    assert authorization.backup_marker.exists()
    assert authorization.tombstone_marker.exists()


def test_tombstone_marker_unlink_failure_retains_both_marker_only_state(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.publication import PublicationState

    authorization = SyntheticPublicationAuthorization(
        tmp_path / "repository",
        expected_accepted=True,
        faults=frozenset({"unlink_tombstone_marker"}),
    )
    target = authorization.root / "artifacts"
    target.mkdir(mode=0o751)
    (target / "manifest.json").write_bytes(b"old\n")
    machine = authorization.state_machine()
    with pytest.raises(ArtifactContractError) as raised:
        machine.publish(clean=True)
    assert raised.value.code is ArtifactErrorCode.BACKUP_CLEANUP_FAILED_AFTER_PUBLISH
    assert raised.value.published is True
    assert machine.state is PublicationState.BOTH_MARKERS_ONLY
    assert (target / "manifest.json").read_bytes() == b"new\n"
    assert not authorization.backup.exists()
    assert not authorization.tombstone.exists()
    assert authorization.backup_marker.exists()
    assert authorization.tombstone_marker.exists()


def test_obsolete_backup_marker_unlink_failure_retains_backup_marker_only_state(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.publication import PublicationState

    authorization = SyntheticPublicationAuthorization(
        tmp_path / "repository",
        expected_accepted=True,
        faults=frozenset({"unlink_backup_marker"}),
    )
    target = authorization.root / "artifacts"
    target.mkdir(mode=0o751)
    (target / "manifest.json").write_bytes(b"old\n")
    machine = authorization.state_machine()
    with pytest.raises(ArtifactContractError) as raised:
        machine.publish(clean=True)
    assert raised.value.code is ArtifactErrorCode.BACKUP_CLEANUP_FAILED_AFTER_PUBLISH
    assert raised.value.published is True
    assert machine.state is PublicationState.BACKUP_MARKER_ONLY
    assert (target / "manifest.json").read_bytes() == b"new\n"
    assert not authorization.backup.exists()
    assert not authorization.tombstone.exists()
    assert not authorization.tombstone_marker.exists()
    assert authorization.backup_marker.exists()
