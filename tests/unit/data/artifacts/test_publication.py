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
