"""CP7B authorization-independent publication state mechanics."""

import os
import stat
from pathlib import Path

import pytest

from tests.helpers.artifact_filesystem import SyntheticPublicationAuthorization


def _snapshot(root: Path) -> tuple[tuple[str, int, int, bytes | str | None], ...]:
    observed: list[tuple[str, int, int, bytes | str | None]] = []
    pending = [root]
    while pending:
        parent = pending.pop()
        for path in sorted(parent.iterdir(), key=lambda value: value.name):
            metadata = path.lstat()
            payload: bytes | str | None = None
            if stat.S_ISREG(metadata.st_mode):
                payload = path.read_bytes()
            elif stat.S_ISLNK(metadata.st_mode):
                payload = os.readlink(path)
            elif stat.S_ISDIR(metadata.st_mode):
                pending.append(path)
            observed.append(
                (path.relative_to(root).as_posix(), metadata.st_ino, metadata.st_mode, payload)
            )
    return tuple(sorted(observed))


def test_publisher_rejects_core_result_substitution_before_filesystem_work(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.builder import ArtifactCoreBuildOutcome
    from finproof.data.artifacts.publication import publish_verified_stage
    from tests.helpers.artifacts import artifact_staging_settings

    class UntouchedFilesystem:
        def target_exists(self) -> bool:
            raise AssertionError("filesystem touched before trusted-stage admission")

    core = ArtifactCoreBuildOutcome.model_construct()

    with pytest.raises(TypeError, match="expected-accepted publication stage"):
        publish_verified_stage(
            core,  # type: ignore[arg-type]
            settings=artifact_staging_settings(tmp_path / "repository"),
            clean=False,
            filesystem=UntouchedFilesystem(),  # type: ignore[arg-type]
        )


def test_expected_receiver_admission_issues_exact_one_use_slot_with_source_unchanged(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime

    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        _ExpectedAcceptedReceiverAdmission,
    )
    from tests.unit.data.artifacts.test_staging import _input_identity, _staging_settings

    class Receiver:
        admission: _ExpectedAcceptedReceiverAdmission | None = None

        def preflight_expected_accepted_custody(
            self,
            *,
            admission: _ExpectedAcceptedReceiverAdmission,
        ) -> None:
            self.admission = admission

    settings = _staging_settings(tmp_path / "repository")
    session = ArtifactBuildSession.initialize(
        settings,
        VersionBundle(),
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=_input_identity(settings),
    ).__enter__()
    custody = session.transfer_candidate_stage().issue_candidate_custody()
    before = (custody._parent_fd, custody._stage_fd, custody._parquet_fd, custody._lock_fd)
    receiver = Receiver()
    try:
        with pytest.raises(TypeError, match="issuer-owned"):
            _ExpectedAcceptedReceiverAdmission()
        admission = custody.issue_expected_accepted_receiver_admission(receiver=receiver)
        assert receiver.admission is admission
        assert object.__getattribute__(admission, "_issuance").custody is None
        assert (
            custody._parent_fd,
            custody._stage_fd,
            custody._parquet_fd,
            custody._lock_fd,
        ) == before
        custody.assert_live()
    finally:
        custody.close()


@pytest.mark.parametrize("case", ["copied", "foreign", "prefilled", "throwing"])
def test_expected_receiver_admission_rejects_foreign_prefilled_copied_and_throwing_before_custody_move(  # noqa: E501
    tmp_path: Path,
    case: str,
) -> None:
    from copy import copy
    from datetime import UTC, datetime

    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        CandidateStageCustody,
        _ExpectedAcceptedReceiverAdmission,
    )
    from tests.unit.data.artifacts.test_staging import _input_identity, _staging_settings

    def new_custody(name: str) -> CandidateStageCustody:
        settings = _staging_settings(tmp_path / name)
        session = ArtifactBuildSession.initialize(
            settings,
            VersionBundle(),
            ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
            input_identity=_input_identity(settings),
        ).__enter__()
        return session.transfer_candidate_stage().issue_candidate_custody()

    foreign_custody = new_custody("foreign")

    class AcceptingReceiver:
        def preflight_expected_accepted_custody(
            self,
            *,
            admission: _ExpectedAcceptedReceiverAdmission,
        ) -> None:
            del admission

    foreign_admission = foreign_custody.issue_expected_accepted_receiver_admission(
        receiver=AcceptingReceiver()
    )
    custody = new_custody("source")
    before = (custody._parent_fd, custody._stage_fd, custody._parquet_fd, custody._lock_fd)

    class RejectingReceiver:
        def preflight_expected_accepted_custody(
            self,
            *,
            admission: _ExpectedAcceptedReceiverAdmission,
        ) -> object:
            if case == "copied":
                return copy(admission)
            if case == "foreign":
                return foreign_admission
            if case == "prefilled":
                object.__getattribute__(admission, "_issuance").custody = object()
                return None
            raise RuntimeError("injected preflight failure")

    try:
        with pytest.raises((TypeError, ValueError, RuntimeError)):
            custody.issue_expected_accepted_receiver_admission(
                receiver=RejectingReceiver()  # type: ignore[arg-type]
            )
        assert (
            custody._parent_fd,
            custody._stage_fd,
            custody._parquet_fd,
            custody._lock_fd,
        ) == before
        custody.assert_live()
    finally:
        custody.close()
        foreign_custody.close()


def test_publication_requires_synthetic_expected_acceptance_before_first_rename(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.publication import PublicationState

    authorization = SyntheticPublicationAuthorization(
        tmp_path / "repository",
        expected_accepted=False,
    )
    machine = authorization.state_machine()
    with pytest.raises(ArtifactContractError):
        machine.publish(clean=False)
    assert authorization.rename_attempts == 0
    assert authorization.stage.is_dir()
    assert machine.state is PublicationState.STAGE_VERIFIED


def test_first_publication_renames_only_authorized_stage_and_commits(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.publication import PublicationState

    authorization = SyntheticPublicationAuthorization(
        tmp_path / "repository",
        expected_accepted=True,
    )
    machine = authorization.state_machine()
    machine.publish(clean=False)
    assert authorization.rename_attempts == 1
    assert not authorization.stage.exists()
    assert not authorization.stage_marker.exists()
    assert (authorization.root / "artifacts" / "manifest.json").read_bytes() == b"new\n"
    assert machine.state is PublicationState.NO_REMNANT


def test_existing_target_without_clean_is_byte_identical_existing_target_error(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    authorization = SyntheticPublicationAuthorization(
        tmp_path / "repository",
        expected_accepted=True,
    )
    target = authorization.root / "artifacts"
    target.mkdir(mode=0o751)
    old = target / "manifest.json"
    old.write_bytes(b"old\n")
    before = (target.stat().st_ino, target.stat().st_mode, old.stat().st_ino, old.read_bytes())
    machine = authorization.state_machine()
    with pytest.raises(ArtifactContractError) as raised:
        machine.publish(clean=False)
    assert raised.value.code is ArtifactErrorCode.EXISTING_TARGET
    assert raised.value.published is False
    assert (
        target.stat().st_ino,
        target.stat().st_mode,
        old.stat().st_ino,
        old.read_bytes(),
    ) == before
    assert authorization.rename_attempts == 0


@pytest.mark.parametrize(
    "case",
    ["symlink", "file", "empty", "extra", "special", "hardlink", "wal", "invalid"],
)
def test_clean_refuses_unrecognized_target_without_mutation(
    tmp_path: Path,
    case: str,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    authorization = SyntheticPublicationAuthorization(
        tmp_path / "repository",
        expected_accepted=True,
    )
    target = authorization.root / "artifacts"
    if case == "symlink":
        target.symlink_to(authorization.stage, target_is_directory=True)
    elif case == "file":
        target.write_bytes(b"foreign\n")
    else:
        target.mkdir(mode=0o751)
        if case != "empty":
            manifest = target / "manifest.json"
            manifest.write_bytes(b"invalid\n" if case == "invalid" else b"old\n")
        if case == "extra":
            (target / "extra").write_bytes(b"foreign\n")
        elif case == "special":
            os.mkfifo(target / "pipe", mode=0o600)
        elif case == "hardlink":
            os.link(target / "manifest.json", target / "alias")
        elif case == "wal":
            (target / "finproof.duckdb.wal").write_bytes(b"wal\n")
    unrelated = authorization.root / "unrelated"
    unrelated.write_bytes(b"keep\n")
    before = _snapshot(authorization.root)
    with pytest.raises(ArtifactContractError) as raised:
        authorization.state_machine().publish(clean=True)
    assert raised.value.code is ArtifactErrorCode.UNRECOGNIZED_TARGET
    assert authorization.rename_attempts == 0
    assert _snapshot(authorization.root) == before


def test_clean_publication_tombstones_old_target_and_reaches_no_remnant(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.publication import PublicationState

    authorization = SyntheticPublicationAuthorization(
        tmp_path / "repository",
        expected_accepted=True,
    )
    target = authorization.root / "artifacts"
    target.mkdir(mode=0o751)
    (target / "manifest.json").write_bytes(b"old\n")
    machine = authorization.state_machine()
    machine.publish(clean=True)
    assert machine.state is PublicationState.NO_REMNANT
    assert (target / "manifest.json").read_bytes() == b"new\n"
    assert not authorization.stage.exists()
    assert not authorization.stage_marker.exists()
    assert not authorization.backup.exists()
    assert not authorization.backup_marker.exists()
    assert not authorization.tombstone.exists()
    assert not authorization.tombstone_marker.exists()
