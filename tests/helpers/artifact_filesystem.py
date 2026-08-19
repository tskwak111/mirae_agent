"""Sealed synthetic CP7B publication authority and filesystem."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any


class SyntheticPublicationAuthorization:
    """Test-only issuer for the authorization-independent state machine."""

    def __init__(
        self,
        root: Path,
        *,
        expected_accepted: bool,
        faults: frozenset[str] = frozenset(),
    ) -> None:
        self.root = root
        self.root.mkdir(mode=0o700)
        self.stage = root / ".artifacts.finproof-stage-operation"
        self.stage.mkdir(mode=0o700)
        (self.stage / "manifest.json").write_bytes(b"new\n")
        self.marker_payload = (
            b'{"artifact_contract_version":"1.0.0",'
            b'"artifact_set_id":"finproof-data-artifacts/v1",'
            b'"operation_id":"operation","target_basename":"artifacts"}'
        )
        self.stage_marker = root / f"{self.stage.name}.marker"
        self.stage_marker.write_bytes(self.marker_payload)
        self.stage_marker.chmod(0o600)
        self.backup = root / ".artifacts.finproof-backup-operation"
        self.backup_marker = root / f"{self.backup.name}.marker"
        self.tombstone = root / ".artifacts.finproof-cleanup-operation"
        self.tombstone_marker = root / f"{self.tombstone.name}.marker"
        self._displaced_tombstone = root / f"{self.tombstone.name}.displaced"
        self.displaced_tombstone = self._displaced_tombstone / "manifest.json"
        self.substituted_tombstone = self.tombstone / "manifest.json"
        self.rename_attempts = 0
        self.fault_hits: set[str] = set()
        self._expected_accepted = expected_accepted
        self._faults = faults
        self._closed = False

    def state_machine(self) -> Any:
        from finproof.data.artifacts.publication import _PublicationStateMachine

        return _PublicationStateMachine._from_test_ports(
            transition=self,
            filesystem=self,
            operation_id="operation",
            target_basename="artifacts",
        )

    def assert_live(self) -> None:
        from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

        if self._closed or not self._expected_accepted:
            raise ArtifactContractError(
                ArtifactErrorCode.VERIFICATION_INCOMPLETE,
                operation_id="synthetic-publication",
                target_basename="artifacts",
                internal_context={"reason": "synthetic_expected_acceptance_missing"},
            )

    def rename_stage_to_target(self) -> None:
        self.rename_attempts += 1
        if "stage_to_target" in self._faults:
            self.fault_hits.add("stage_to_target")
            self._fault("synthetic-stage-to-target", "injected_stage_to_target_failure")
        self.stage.rename(self.root / "artifacts")

    def rollback_target_to_stage(self) -> None:
        if "target_to_stage" in self._faults:
            self.fault_hits.add("target_to_stage")
            from finproof.data.artifacts.errors import (
                ArtifactContractError,
                ArtifactErrorCode,
            )

            raise ArtifactContractError(
                ArtifactErrorCode.PUBLICATION_ROLLBACK_FAILED,
                operation_id="synthetic-target-to-stage",
                target_basename="artifacts",
                internal_context={
                    "backup_path": str(self.backup),
                    "stage_path": str(self.stage),
                    "target_path": str(self.root / "artifacts"),
                },
            )
        (self.root / "artifacts").rename(self.stage)

    def commit_after_stage_marker_removal(self) -> None:
        if "stage_marker_unlink" in self._faults:
            self.fault_hits.add("stage_marker_unlink")
            from finproof.data.artifacts.errors import (
                ArtifactContractError,
                ArtifactErrorCode,
            )

            raise ArtifactContractError(
                ArtifactErrorCode.EXACT_TREE_MISMATCH,
                operation_id="synthetic-stage-marker-unlink",
                target_basename="artifacts",
                internal_context={"reason": "injected_stage_marker_unlink_failure"},
            )
        self.stage_marker.unlink()

    def close(self) -> None:
        self._closed = True

    def target_exists(self) -> bool:
        try:
            os.lstat(self.root / "artifacts")
        except FileNotFoundError:
            return False
        return True

    def recognize_target(self) -> None:
        from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

        target = self.root / "artifacts"
        try:
            target_stat = os.lstat(target)
            names = tuple(sorted(path.name for path in target.iterdir()))
            manifest = target / "manifest.json"
            manifest_stat = os.lstat(manifest)
            if (
                not stat.S_ISDIR(target_stat.st_mode)
                or stat.S_ISLNK(target_stat.st_mode)
                or names != ("manifest.json",)
                or not stat.S_ISREG(manifest_stat.st_mode)
                or manifest_stat.st_nlink != 1
                or manifest.read_bytes() != b"old\n"
            ):
                raise ValueError("synthetic target is not recognized")
        except (FileNotFoundError, NotADirectoryError, OSError, ValueError) as exc:
            raise ArtifactContractError(
                ArtifactErrorCode.UNRECOGNIZED_TARGET,
                operation_id="synthetic-target-recognition",
                target_basename="artifacts",
                internal_context={"reason": "synthetic_target_unrecognized"},
            ) from exc

    def rename_target_to_backup(self) -> None:
        self.recognize_target()
        if "old_target_to_backup" in self._faults:
            self.fault_hits.add("old_target_to_backup")
            self._fault(
                "synthetic-old-target-to-backup",
                "injected_old_target_to_backup_failure",
            )
        descriptor = os.open(
            self.backup_marker,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        try:
            os.write(descriptor, self.marker_payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.rename(self.root / "artifacts", self.backup)

    def verify_backup(self) -> None:
        try:
            backup_stat = os.lstat(self.backup)
            manifest = self.backup / "manifest.json"
            manifest_stat = os.lstat(manifest)
            if (
                not stat.S_ISDIR(backup_stat.st_mode)
                or stat.S_ISLNK(backup_stat.st_mode)
                or tuple(path.name for path in self.backup.iterdir()) != ("manifest.json",)
                or not stat.S_ISREG(manifest_stat.st_mode)
                or manifest_stat.st_nlink != 1
                or manifest.read_bytes() != b"old\n"
                or self.backup_marker.read_bytes() != self.marker_payload
            ):
                raise ValueError("synthetic backup changed")
        except (FileNotFoundError, NotADirectoryError, OSError, ValueError) as exc:
            from finproof.data.artifacts.errors import (
                ArtifactContractError,
                ArtifactErrorCode,
            )

            raise ArtifactContractError(
                ArtifactErrorCode.EXACT_TREE_MISMATCH,
                operation_id="synthetic-backup-verification",
                target_basename="artifacts",
                internal_context={"reason": "synthetic_backup_verification_failed"},
            ) from exc

    def restore_backup_to_target(self) -> None:
        if "backup_to_target" in self._faults:
            self.fault_hits.add("backup_to_target")
            from finproof.data.artifacts.errors import (
                ArtifactContractError,
                ArtifactErrorCode,
            )

            raise ArtifactContractError(
                ArtifactErrorCode.PUBLICATION_ROLLBACK_FAILED,
                operation_id="synthetic-backup-to-target",
                target_basename="artifacts",
                internal_context={
                    "backup_path": str(self.backup),
                    "target_path": str(self.root / "artifacts"),
                },
            )
        self.verify_backup()
        os.rename(self.backup, self.root / "artifacts")
        self.backup_marker.unlink()

    def prepare_tombstone_marker(self) -> None:
        descriptor = os.open(
            self.tombstone_marker,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        try:
            os.write(descriptor, self.marker_payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def rename_backup_to_tombstone(self) -> None:
        self.verify_backup()
        if "backup_to_tombstone" in self._faults:
            self.fault_hits.add("backup_to_tombstone")
            self._fault(
                "synthetic-backup-to-tombstone",
                "injected_backup_to_tombstone_failure",
            )
        os.rename(self.backup, self.tombstone)

    def delete_tombstone(self) -> None:
        try:
            tombstone_stat = os.lstat(self.tombstone)
            manifest = self.tombstone / "manifest.json"
            manifest_stat = os.lstat(manifest)
            if (
                not stat.S_ISDIR(tombstone_stat.st_mode)
                or stat.S_ISLNK(tombstone_stat.st_mode)
                or tuple(path.name for path in self.tombstone.iterdir()) != ("manifest.json",)
                or not stat.S_ISREG(manifest_stat.st_mode)
                or manifest_stat.st_nlink != 1
                or manifest.read_bytes() != b"old\n"
                or self.tombstone_marker.read_bytes() != self.marker_payload
                or self.backup_marker.read_bytes() != self.marker_payload
            ):
                raise ValueError("synthetic tombstone changed")
            if "delete_tombstone" in self._faults:
                self.fault_hits.add("delete_tombstone")
                self._fault(
                    "synthetic-delete-tombstone",
                    "injected_tombstone_delete_failure",
                )
            if "substitute_tombstone_before_delete" in self._faults:
                self.fault_hits.add("substitute_tombstone_before_delete")
                os.rename(self.tombstone, self._displaced_tombstone)
                self.tombstone.mkdir(mode=0o751)
                self.substituted_tombstone.write_bytes(b"foreign\n")
            current = os.lstat(self.tombstone)
            if (current.st_dev, current.st_ino) != (
                tombstone_stat.st_dev,
                tombstone_stat.st_ino,
            ):
                raise ValueError("synthetic tombstone identity changed")
            manifest.unlink()
            self.tombstone.rmdir()
        except (FileNotFoundError, NotADirectoryError, OSError, ValueError) as exc:
            from finproof.data.artifacts.errors import ArtifactContractError

            if isinstance(exc, ArtifactContractError):
                raise
            self._fault("synthetic-delete-tombstone", "synthetic_tombstone_changed")

    def unlink_tombstone_marker(self) -> None:
        if "unlink_tombstone_marker" in self._faults:
            self.fault_hits.add("unlink_tombstone_marker")
            self._fault(
                "synthetic-unlink-tombstone-marker",
                "injected_tombstone_marker_unlink_failure",
            )
        if self.tombstone_marker.read_bytes() != self.marker_payload:
            self._fault(
                "synthetic-unlink-tombstone-marker",
                "synthetic_tombstone_marker_changed",
            )
        self.tombstone_marker.unlink()

    def unlink_backup_marker(self) -> None:
        if "unlink_backup_marker" in self._faults:
            self.fault_hits.add("unlink_backup_marker")
            self._fault(
                "synthetic-unlink-backup-marker",
                "injected_backup_marker_unlink_failure",
            )
        if self.backup_marker.read_bytes() != self.marker_payload:
            self._fault(
                "synthetic-unlink-backup-marker",
                "synthetic_backup_marker_changed",
            )
        self.backup_marker.unlink()

    def seed_recovery_state(self, state: str, *, target_present: bool = True) -> None:
        if target_present:
            target = self.root / "artifacts"
            target.mkdir(mode=0o751)
            (target / "manifest.json").write_bytes(b"new\n")
        if state in {
            "backup_with_marker",
            "backup_with_prepared_tombstone_marker",
        }:
            self.backup.mkdir(mode=0o751)
            (self.backup / "manifest.json").write_bytes(b"old\n")
            self.backup_marker.write_bytes(self.marker_payload)
            self.backup_marker.chmod(0o600)
        if state == "backup_with_prepared_tombstone_marker":
            self.tombstone_marker.write_bytes(self.marker_payload)
            self.tombstone_marker.chmod(0o600)
        elif state == "tombstone_with_both_markers":
            self.tombstone.mkdir(mode=0o751)
            (self.tombstone / "manifest.json").write_bytes(b"old\n")
            self.backup_marker.write_bytes(self.marker_payload)
            self.backup_marker.chmod(0o600)
            self.tombstone_marker.write_bytes(self.marker_payload)
            self.tombstone_marker.chmod(0o600)
        elif state == "both_markers_only":
            self.backup_marker.write_bytes(self.marker_payload)
            self.backup_marker.chmod(0o600)
            self.tombstone_marker.write_bytes(self.marker_payload)
            self.tombstone_marker.chmod(0o600)
        elif state == "backup_marker_only":
            self.backup_marker.write_bytes(self.marker_payload)
            self.backup_marker.chmod(0o600)

    def remnant_state(self) -> Any:
        from finproof.data.artifacts.publication import PublicationState

        allowed = {
            self.backup.name,
            self.backup_marker.name,
            self.tombstone.name,
            self.tombstone_marker.name,
        }
        for entry in self.root.iterdir():
            if (
                entry.name.startswith(".artifacts.finproof-backup-")
                or entry.name.startswith(".artifacts.finproof-cleanup-")
            ) and entry.name not in allowed:
                self._fault(
                    "synthetic-remnant-classification",
                    "foreign_publication_remnant",
                )
        backup = self._lstat_exists(self.backup)
        tombstone = self._lstat_exists(self.tombstone)
        backup_marker = self._lstat_exists(self.backup_marker)
        tombstone_marker = self._lstat_exists(self.tombstone_marker)
        if backup:
            self._verify_remnant_tree(self.backup)
        if tombstone:
            self._verify_remnant_tree(self.tombstone)
        if backup_marker:
            self._verify_marker(self.backup_marker)
        if tombstone_marker:
            self._verify_marker(self.tombstone_marker)
        observed = (backup, tombstone, backup_marker, tombstone_marker)
        states = {
            (True, False, True, False): PublicationState.BACKUP_WITH_MARKER,
            (True, False, True, True): (PublicationState.BACKUP_WITH_PREPARED_TOMBSTONE_MARKER),
            (False, True, True, True): PublicationState.TOMBSTONE_WITH_BOTH_MARKERS,
            (False, False, True, True): PublicationState.BOTH_MARKERS_ONLY,
            (False, False, True, False): PublicationState.BACKUP_MARKER_ONLY,
            (False, False, False, False): PublicationState.NO_REMNANT,
        }
        try:
            return states[observed]
        except KeyError as exc:
            self._fault(
                "synthetic-remnant-classification",
                "ambiguous_publication_remnant",
            )
            raise AssertionError("unreachable") from exc

    @staticmethod
    def _lstat_exists(path: Path) -> bool:
        try:
            os.lstat(path)
        except FileNotFoundError:
            return False
        return True

    def _verify_marker(self, marker: Path) -> None:
        try:
            metadata = os.lstat(marker)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_ISLNK(metadata.st_mode)
                or metadata.st_nlink != 1
                or stat.S_IMODE(metadata.st_mode) != 0o600
                or marker.read_bytes() != self.marker_payload
            ):
                raise ValueError("synthetic marker changed")
        except (FileNotFoundError, NotADirectoryError, OSError, ValueError) as exc:
            self._fault(
                "synthetic-remnant-classification",
                "publication_marker_changed",
            )
            raise AssertionError("unreachable") from exc

    def _verify_remnant_tree(self, directory: Path) -> None:
        try:
            metadata = os.lstat(directory)
            manifest = directory / "manifest.json"
            manifest_metadata = os.lstat(manifest)
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or stat.S_ISLNK(metadata.st_mode)
                or tuple(path.name for path in directory.iterdir()) != ("manifest.json",)
                or not stat.S_ISREG(manifest_metadata.st_mode)
                or manifest_metadata.st_nlink != 1
                or manifest.read_bytes() != b"old\n"
            ):
                raise ValueError("synthetic remnant changed")
        except (FileNotFoundError, NotADirectoryError, OSError, ValueError) as exc:
            self._fault(
                "synthetic-remnant-classification",
                "publication_remnant_changed",
            )
            raise AssertionError("unreachable") from exc

    @staticmethod
    def _fault(operation_id: str, reason: str) -> None:
        from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

        raise ArtifactContractError(
            ArtifactErrorCode.EXACT_TREE_MISMATCH,
            operation_id=operation_id,
            target_basename="artifacts",
            internal_context={"reason": reason},
        )

    def verify_target(self) -> None:
        from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

        target = self.root / "artifacts"
        try:
            if "target_verify" in self._faults:
                self.fault_hits.add("target_verify")
                raise ValueError("injected target verification failure")
            target_stat = os.lstat(target)
            manifest = target / "manifest.json"
            manifest_stat = os.lstat(manifest)
            if (
                not stat.S_ISDIR(target_stat.st_mode)
                or stat.S_ISLNK(target_stat.st_mode)
                or tuple(path.name for path in target.iterdir()) != ("manifest.json",)
                or not stat.S_ISREG(manifest_stat.st_mode)
                or manifest_stat.st_nlink != 1
                or manifest.read_bytes() != b"new\n"
            ):
                raise ValueError("synthetic published target changed")
        except (FileNotFoundError, NotADirectoryError, OSError, ValueError) as exc:
            raise ArtifactContractError(
                ArtifactErrorCode.EXACT_TREE_MISMATCH,
                operation_id="synthetic-target-verification",
                target_basename="artifacts",
                internal_context={"reason": "synthetic_target_verification_failed"},
            ) from exc
