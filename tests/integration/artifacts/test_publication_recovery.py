"""CP7B closed remnant recovery mechanics."""

import os
import stat
from pathlib import Path

import pytest

from tests.helpers.artifact_filesystem import SyntheticPublicationAuthorization


def _snapshot(root: Path) -> tuple[tuple[str, int, int, bytes | str | None], ...]:
    rows: list[tuple[str, int, int, bytes | str | None]] = []
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
            rows.append(
                (path.relative_to(root).as_posix(), metadata.st_ino, metadata.st_mode, payload)
            )
    return tuple(sorted(rows))


def test_normal_target_recognition_requires_reopened_expected_acceptance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.data.artifacts.manifest import (
        ArtifactExpectedVerificationResult,
        ArtifactManifest,
        VerifiedArtifactSet,
    )
    from finproof.data.artifacts.publication import _PublishedArtifactFilesystem
    from finproof.data.artifacts.resources import expected_phase1_contract_bytes
    from tests.helpers.artifacts import artifact_staging_settings, manifest_payload

    settings = artifact_staging_settings(tmp_path / "repository")
    settings.artifact_dir.mkdir()
    manifest_path = settings.artifact_dir / "manifest.json"
    manifest_path.write_bytes(b"reopen-me\n")
    manifest = ArtifactManifest.model_validate(manifest_payload(), strict=True)
    expected = VerifiedArtifactSet._from_expected(
        ArtifactExpectedVerificationResult.model_validate_json(
            expected_phase1_contract_bytes(),
            strict=True,
        )
    )
    reopened: list[Path] = []
    verified: list[Path] = []

    def load(path: Path) -> ArtifactManifest:
        reopened.append(path)
        return manifest

    def verify(self: ArtifactManifest, root: Path) -> VerifiedArtifactSet:
        assert self is manifest
        verified.append(root)
        return expected

    monkeypatch.setattr(ArtifactManifest, "load", load)
    monkeypatch.setattr(ArtifactManifest, "verify", verify)

    filesystem = _PublishedArtifactFilesystem(settings=settings, expected=expected)
    filesystem.recognize_target()

    assert reopened == [manifest_path]
    assert verified == [settings.artifact_dir]


@pytest.mark.parametrize(
    "state",
    [
        "backup_with_marker",
        "backup_with_prepared_tombstone_marker",
        "tombstone_with_both_markers",
        "both_markers_only",
        "backup_marker_only",
        "no_remnant",
    ],
)
def test_verified_target_recovers_every_closed_postcommit_remnant_state(
    tmp_path: Path,
    state: str,
) -> None:
    from finproof.data.artifacts.publication import PublicationState

    authorization = SyntheticPublicationAuthorization(
        tmp_path / "repository",
        expected_accepted=True,
    )
    authorization.seed_recovery_state(state)
    unrelated = authorization.root / "unrelated"
    unrelated.write_bytes(b"keep\n")
    unrelated_before = (unrelated.stat().st_ino, unrelated.stat().st_mode, unrelated.read_bytes())
    machine = authorization.state_machine()
    machine.recover()
    assert machine.state is PublicationState.NO_REMNANT
    assert (authorization.root / "artifacts" / "manifest.json").read_bytes() == b"new\n"
    assert not authorization.backup.exists()
    assert not authorization.backup_marker.exists()
    assert not authorization.tombstone.exists()
    assert not authorization.tombstone_marker.exists()
    assert (
        unrelated.stat().st_ino,
        unrelated.stat().st_mode,
        unrelated.read_bytes(),
    ) == unrelated_before


@pytest.mark.parametrize(
    "state",
    ["backup_with_marker", "backup_with_prepared_tombstone_marker"],
)
def test_absent_target_restores_complete_verified_backup(
    tmp_path: Path,
    state: str,
) -> None:
    from finproof.data.artifacts.publication import PublicationState

    authorization = SyntheticPublicationAuthorization(
        tmp_path / "repository",
        expected_accepted=True,
    )
    authorization.seed_recovery_state(state, target_present=False)
    backup_manifest = authorization.backup / "manifest.json"
    backup_before = (authorization.backup.stat().st_ino, backup_manifest.stat().st_ino)
    machine = authorization.state_machine()
    machine.recover()
    target = authorization.root / "artifacts"
    assert machine.state is PublicationState.NO_REMNANT
    assert (target.stat().st_ino, (target / "manifest.json").stat().st_ino) == backup_before
    assert (target / "manifest.json").read_bytes() == b"old\n"
    assert not authorization.backup.exists()
    assert not authorization.backup_marker.exists()
    assert not authorization.tombstone.exists()
    assert not authorization.tombstone_marker.exists()


@pytest.mark.parametrize(
    "case",
    [
        "tombstone_marker_only",
        "mismatched_marker",
        "unexpected_directory",
        "duplicate_marker",
        "marker_without_target",
        "ambiguous_backup",
        "unverified_target",
        "foreign_operation",
    ],
)
def test_recovery_rejects_ambiguous_or_unverified_remnants_without_mutation(
    tmp_path: Path,
    case: str,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError

    authorization = SyntheticPublicationAuthorization(
        tmp_path / "repository",
        expected_accepted=True,
    )
    target = authorization.root / "artifacts"
    if case not in {"marker_without_target"}:
        target.mkdir(mode=0o751)
        (target / "manifest.json").write_bytes(
            b"invalid\n" if case == "unverified_target" else b"new\n"
        )
    if case == "tombstone_marker_only":
        authorization.tombstone_marker.write_bytes(authorization.marker_payload)
        authorization.tombstone_marker.chmod(0o600)
    elif case == "mismatched_marker":
        authorization.seed_recovery_state("backup_with_marker", target_present=False)
        authorization.backup_marker.write_bytes(b"other-operation\n")
    elif case == "unexpected_directory":
        authorization.backup.mkdir(mode=0o751)
        (authorization.backup / "manifest.json").write_bytes(b"old\n")
    elif case == "duplicate_marker":
        authorization.backup_marker.write_bytes(authorization.marker_payload)
        authorization.backup_marker.chmod(0o600)
        (authorization.root / ".artifacts.finproof-backup-other.marker").write_bytes(b"other\n")
    elif case in {"marker_without_target", "unverified_target"}:
        authorization.backup_marker.write_bytes(authorization.marker_payload)
        authorization.backup_marker.chmod(0o600)
    elif case == "ambiguous_backup":
        authorization.seed_recovery_state("backup_with_marker", target_present=False)
        (authorization.backup / "extra").write_bytes(b"foreign\n")
    elif case == "foreign_operation":
        foreign = authorization.root / ".artifacts.finproof-backup-other"
        foreign.mkdir(mode=0o751)
        (foreign / "manifest.json").write_bytes(b"old\n")
        (authorization.root / f"{foreign.name}.marker").write_bytes(b"other\n")
    before = _snapshot(authorization.root)
    with pytest.raises(ArtifactContractError):
        authorization.state_machine().recover()
    assert _snapshot(authorization.root) == before


def test_tombstone_directory_substitution_is_blocked_without_broad_delete(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.publication import PublicationState

    authorization = SyntheticPublicationAuthorization(
        tmp_path / "repository",
        expected_accepted=True,
        faults=frozenset({"substitute_tombstone_before_delete"}),
    )
    authorization.seed_recovery_state("tombstone_with_both_markers")
    target = authorization.root / "artifacts"
    target_before = _snapshot(target)
    machine = authorization.state_machine()
    with pytest.raises(ArtifactContractError):
        machine.recover()
    assert machine.state is PublicationState.TOMBSTONE_WITH_BOTH_MARKERS
    assert "substitute_tombstone_before_delete" in authorization.fault_hits
    assert _snapshot(target) == target_before
    assert authorization.substituted_tombstone.read_bytes() == b"foreign\n"
    assert authorization.displaced_tombstone.read_bytes() == b"old\n"
