"""Authorization-independent guarded publication state mechanics."""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Never, Protocol, cast

from finproof.core.settings import Settings
from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
from finproof.data.artifacts.manifest import (
    ArtifactExpectedVerificationResult,
    ArtifactManifest,
    VerifiedArtifactSet,
)
from finproof.data.artifacts.staging import (
    TransferredCandidateCustody,
    _ExpectedAcceptedReceiverAdmission,
)


class PublicationState(StrEnum):
    """Closed publication and recovery states."""

    STAGE_VERIFIED = "stage_verified"
    BACKUP_VERIFIED = "backup_verified"
    TARGET_RENAMED_UNCOMMITTED = "target_renamed_uncommitted"
    PUBLISHED = "published"
    BACKUP_WITH_MARKER = "backup_with_marker"
    BACKUP_WITH_PREPARED_TOMBSTONE_MARKER = "backup_with_prepared_tombstone_marker"
    TOMBSTONE_WITH_BOTH_MARKERS = "tombstone_with_both_markers"
    BOTH_MARKERS_ONLY = "both_markers_only"
    BACKUP_MARKER_ONLY = "backup_marker_only"
    NO_REMNANT = "no_remnant"


class PublicationTransitionPort(Protocol):
    """Narrow stage transition capability supplied only after authorization."""

    def assert_live(self) -> None: ...

    def rename_stage_to_target(self) -> None: ...

    def rollback_target_to_stage(self) -> None: ...

    def commit_after_stage_marker_removal(self) -> None: ...

    def close(self) -> None: ...


class ArtifactFilesystem(Protocol):
    """Closed target/remnant operations used by publication mechanics."""

    def target_exists(self) -> bool: ...

    def recognize_target(self) -> None: ...

    def verify_target(self) -> None: ...

    def rename_target_to_backup(self) -> None: ...

    def verify_backup(self) -> None: ...

    def restore_backup_to_target(self) -> None: ...

    def prepare_tombstone_marker(self) -> None: ...

    def rename_backup_to_tombstone(self) -> None: ...

    def delete_tombstone(self) -> None: ...

    def unlink_tombstone_marker(self) -> None: ...

    def unlink_backup_marker(self) -> None: ...

    def remnant_state(self) -> PublicationState: ...


class _PublishedArtifactFilesystem:
    """Closed filesystem verifier for one expected published generation."""

    __slots__ = ("_closed", "_expected", "_marker_payload", "_operation_id", "_settings")

    _expected: VerifiedArtifactSet | None

    def __init__(
        self,
        *,
        settings: Settings,
        expected: VerifiedArtifactSet,
    ) -> None:
        if type(settings) is not Settings or type(expected) is not VerifiedArtifactSet:
            raise TypeError("published artifact filesystem requires exact inputs")
        self._settings = settings
        self._expected = expected
        self._closed = False
        self._operation_id: str | None = None
        self._marker_payload: bytes | None = None

    @classmethod
    def _for_recovery(cls, settings: Settings) -> _PublishedArtifactFilesystem:
        if type(settings) is not Settings:
            raise TypeError("published artifact recovery requires exact settings")
        value = object.__new__(cls)
        value._settings = settings
        value._expected = None
        value._closed = False
        value._operation_id = value._remnant_operation_id()
        value._marker_payload = (
            value._publication_marker_payload() if value._operation_id is not None else None
        )
        return value

    @property
    def _target_name(self) -> str:
        return self._settings.artifact_dir.name

    @property
    def _stage_name(self) -> str:
        return f".{self._target_name}.finproof-stage-{self._require_operation_id()}"

    @property
    def _stage_marker_name(self) -> str:
        return f"{self._stage_name}.marker"

    @property
    def _backup_name(self) -> str:
        return f".{self._target_name}.finproof-backup-{self._require_operation_id()}"

    @property
    def _backup_marker_name(self) -> str:
        return f"{self._backup_name}.marker"

    @property
    def _tombstone_name(self) -> str:
        return f".{self._target_name}.finproof-cleanup-{self._require_operation_id()}"

    @property
    def _tombstone_marker_name(self) -> str:
        return f"{self._tombstone_name}.marker"

    @contextmanager
    def _open_parent(self) -> Iterator[int]:
        descriptor = os.open(
            self._settings.artifact_dir.parent,
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        try:
            yield descriptor
        finally:
            os.close(descriptor)

    def _active_operation_id(self) -> str:
        prefix = f".{self._settings.artifact_dir.name}.finproof-stage-"
        with self._open_parent() as parent_fd, os.scandir(parent_fd) as entries:
            names = {entry.name for entry in entries}
        operations = {
            name.removeprefix(prefix).removesuffix(".marker")
            for name in names
            if name.startswith(prefix) and name.endswith(".marker")
        }
        valid = {
            operation
            for operation in operations
            if len(operation) == 32
            and all(character in "0123456789abcdef" for character in operation)
            and f"{prefix}{operation}" in names
        }
        if len(valid) != 1 or valid != operations:
            raise ArtifactContractError(
                ArtifactErrorCode.EXACT_TREE_MISMATCH,
                operation_id="publish-artifacts",
                target_basename=self._settings.artifact_dir.name,
                internal_context={"reason": "active_stage_operation_is_ambiguous"},
            )
        return next(iter(valid))

    def _remnant_operation_id(self) -> str | None:
        prefixes = (
            f".{self._settings.artifact_dir.name}.finproof-backup-",
            f".{self._settings.artifact_dir.name}.finproof-cleanup-",
        )
        with self._open_parent() as parent_fd, os.scandir(parent_fd) as entries:
            names = {entry.name for entry in entries}
        matching = {name for name in names if any(name.startswith(prefix) for prefix in prefixes)}
        operations: set[str] = set()
        for name in matching:
            prefix = next(prefix for prefix in prefixes if name.startswith(prefix))
            operation = name.removeprefix(prefix).removesuffix(".marker")
            if (
                len(operation) != 32
                or any(character not in "0123456789abcdef" for character in operation)
                or name not in {f"{prefix}{operation}", f"{prefix}{operation}.marker"}
            ):
                self._remnant_error("foreign_publication_remnant")
            operations.add(operation)
        if not operations:
            return None
        if len(operations) != 1:
            self._remnant_error("ambiguous_publication_remnant")
        operation_id = next(iter(operations))
        allowed = {
            f"{prefix}{operation_id}{suffix}" for prefix in prefixes for suffix in ("", ".marker")
        }
        if not matching <= allowed:
            self._remnant_error("foreign_publication_remnant")
        return operation_id

    def _require_operation_id(self) -> str:
        if self._operation_id is None:
            self._operation_id = self._active_operation_id()
            self._marker_payload = self._publication_marker_payload()
            self._verify_marker(self._stage_marker_name)
        return self._operation_id

    def _publication_marker_payload(self) -> bytes:
        operation_id = self._operation_id
        if operation_id is None:
            raise TypeError("publication operation is unavailable")
        return json.dumps(
            {
                "artifact_contract_version": "1.0.0",
                "artifact_set_id": "finproof-data-artifacts/v1",
                "operation_id": operation_id,
                "target_basename": self._target_name,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def _verify_marker(self, name: str) -> None:
        marker_payload = self._marker_payload
        if marker_payload is None:
            raise TypeError("publication marker payload is unavailable")
        descriptor = -1
        try:
            with self._open_parent() as parent_fd:
                descriptor = os.open(
                    name,
                    os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=parent_fd,
                )
                metadata = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(metadata.st_mode)
                    or metadata.st_nlink != 1
                    or stat.S_IMODE(metadata.st_mode) != 0o600
                    or os.pread(descriptor, 4097, 0) != marker_payload
                ):
                    raise ValueError("publication marker changed")
        except (OSError, TypeError, ValueError) as exc:
            raise ArtifactContractError(
                ArtifactErrorCode.EXACT_TREE_MISMATCH,
                operation_id="publish-artifacts",
                target_basename=self._target_name,
                internal_context={"reason": "publication_marker_changed"},
            ) from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def _create_marker(self, name: str) -> None:
        marker_payload = self._marker_payload
        if marker_payload is None:
            raise TypeError("publication marker payload is unavailable")
        descriptor = -1
        created = False
        try:
            with self._open_parent() as parent_fd:
                descriptor = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=parent_fd,
                )
                created = True
                remaining = marker_payload
                while remaining:
                    written = os.write(descriptor, remaining)
                    if written <= 0:
                        raise OSError("publication marker write made no progress")
                    remaining = remaining[written:]
                os.fsync(descriptor)
        except (OSError, TypeError, ValueError) as exc:
            if created:
                try:
                    with self._open_parent() as parent_fd:
                        os.unlink(name, dir_fd=parent_fd)
                except OSError:
                    pass
            raise ArtifactContractError(
                ArtifactErrorCode.EXACT_TREE_MISMATCH,
                operation_id="publish-artifacts",
                target_basename=self._target_name,
                internal_context={"reason": "publication_marker_create_failed"},
            ) from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def _verify_named_artifact(self, name: str) -> ArtifactManifest:
        root = self._settings.artifact_dir.parent / name
        manifest = ArtifactManifest.load(root / "manifest.json")
        verified = manifest.verify(root)
        if self._expected is None:
            self._expected = verified
        elif verified != self._expected:
            raise ArtifactContractError(
                ArtifactErrorCode.REPRODUCIBILITY_MISMATCH,
                operation_id="verify-published-artifacts",
                target_basename=self._target_name,
            )
        return manifest

    def target_exists(self) -> bool:
        try:
            with self._open_parent() as parent_fd:
                os.stat(self._target_name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return False
        return True

    def verify_target(self) -> None:
        self._verify_named_artifact(self._target_name)

    def recognize_target(self) -> None:
        try:
            self.verify_target()
        except ArtifactContractError as exc:
            raise ArtifactContractError(
                ArtifactErrorCode.UNRECOGNIZED_TARGET,
                operation_id="publish-artifacts",
                target_basename=self._target_name,
                internal_context={"reason": "existing_target_is_not_expected"},
            ) from exc

    def rename_target_to_backup(self) -> None:
        self.recognize_target()
        self._create_marker(self._backup_marker_name)
        try:
            with self._open_parent() as parent_fd:
                os.rename(
                    self._target_name,
                    self._backup_name,
                    src_dir_fd=parent_fd,
                    dst_dir_fd=parent_fd,
                )
        except OSError as exc:
            self._verify_marker(self._backup_marker_name)
            with self._open_parent() as parent_fd:
                os.unlink(self._backup_marker_name, dir_fd=parent_fd)
            raise ArtifactContractError(
                ArtifactErrorCode.EXACT_TREE_MISMATCH,
                operation_id="publish-artifacts",
                target_basename=self._target_name,
                internal_context={"reason": "target_to_backup_rename_failed"},
            ) from exc

    def verify_backup(self) -> None:
        self._verify_marker(self._backup_marker_name)
        self._verify_named_artifact(self._backup_name)

    def restore_backup_to_target(self) -> None:
        self.verify_backup()
        with self._open_parent() as parent_fd:
            try:
                os.stat(self._target_name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ArtifactContractError(
                    ArtifactErrorCode.PUBLICATION_ROLLBACK_FAILED,
                    operation_id="publish-artifacts",
                    target_basename=self._target_name,
                    internal_context={"reason": "target_exists_before_backup_restore"},
                )
            os.rename(
                self._backup_name,
                self._target_name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
        self.verify_target()
        self._verify_marker(self._backup_marker_name)
        with self._open_parent() as parent_fd:
            os.unlink(self._backup_marker_name, dir_fd=parent_fd)

    def prepare_tombstone_marker(self) -> None:
        self._create_marker(self._tombstone_marker_name)

    def rename_backup_to_tombstone(self) -> None:
        self.verify_backup()
        self._verify_marker(self._tombstone_marker_name)
        with self._open_parent() as parent_fd:
            os.rename(
                self._backup_name,
                self._tombstone_name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )

    def delete_tombstone(self) -> None:
        directory_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
        with self._open_parent() as parent_fd:
            tombstone_fd = os.open(self._tombstone_name, directory_flags, dir_fd=parent_fd)
            held = os.fstat(tombstone_fd)
            held_identity = (held.st_dev, held.st_ino)

            def require_held_tombstone() -> None:
                descriptor = os.fstat(tombstone_fd)
                named = os.stat(
                    self._tombstone_name,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                if (descriptor.st_dev, descriptor.st_ino) != held_identity or (
                    named.st_dev,
                    named.st_ino,
                ) != held_identity:
                    raise ValueError("tombstone identity changed")

            try:
                manifest = self._verify_named_artifact(self._tombstone_name)
                self._verify_marker(self._backup_marker_name)
                self._verify_marker(self._tombstone_marker_name)
                require_held_tombstone()
                nested: dict[str, set[str]] = {}
                root_leaves = {"manifest.json"}
                for entry in manifest.files:
                    parts = PurePosixPath(entry.path).parts
                    if len(parts) == 1:
                        root_leaves.add(parts[0])
                    elif len(parts) == 2:
                        nested.setdefault(parts[0], set()).add(parts[1])
                    else:
                        raise ValueError("unsupported tombstone depth")
                with os.scandir(tombstone_fd) as entries:
                    observed = {entry.name for entry in entries}
                if observed != root_leaves | set(nested):
                    raise ValueError("tombstone inventory changed")
                for directory_name, leaves in sorted(nested.items()):
                    require_held_tombstone()
                    directory_fd = os.open(directory_name, directory_flags, dir_fd=tombstone_fd)
                    try:
                        with os.scandir(directory_fd) as entries:
                            if {entry.name for entry in entries} != leaves:
                                raise ValueError("tombstone directory inventory changed")
                        for leaf in sorted(leaves):
                            metadata = os.stat(leaf, dir_fd=directory_fd, follow_symlinks=False)
                            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                                raise ValueError("tombstone leaf changed")
                            require_held_tombstone()
                            os.unlink(leaf, dir_fd=directory_fd)
                    finally:
                        os.close(directory_fd)
                    require_held_tombstone()
                    os.rmdir(directory_name, dir_fd=tombstone_fd)
                for leaf in sorted(root_leaves):
                    metadata = os.stat(leaf, dir_fd=tombstone_fd, follow_symlinks=False)
                    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                        raise ValueError("tombstone root leaf changed")
                    require_held_tombstone()
                    os.unlink(leaf, dir_fd=tombstone_fd)
                require_held_tombstone()
                os.rmdir(self._tombstone_name, dir_fd=parent_fd)
            except (OSError, TypeError, ValueError) as exc:
                raise ArtifactContractError(
                    ArtifactErrorCode.EXACT_TREE_MISMATCH,
                    operation_id="publish-artifacts",
                    target_basename=self._target_name,
                    internal_context={"reason": "tombstone_delete_failed"},
                ) from exc
            finally:
                os.close(tombstone_fd)

    def unlink_tombstone_marker(self) -> None:
        self._verify_marker(self._tombstone_marker_name)
        with self._open_parent() as parent_fd:
            os.unlink(self._tombstone_marker_name, dir_fd=parent_fd)

    def unlink_backup_marker(self) -> None:
        self._verify_marker(self._backup_marker_name)
        with self._open_parent() as parent_fd:
            os.unlink(self._backup_marker_name, dir_fd=parent_fd)

    def _named_exists(self, name: str) -> bool:
        try:
            with self._open_parent() as parent_fd:
                os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return False
        return True

    def assert_live(self) -> None:
        if self._closed:
            raise ArtifactContractError(
                ArtifactErrorCode.VERIFICATION_INCOMPLETE,
                operation_id="recover-published-artifacts",
                target_basename=self._target_name,
                internal_context={"reason": "publication_recovery_is_closed"},
            )

    def close(self) -> None:
        self._closed = True

    def _remnant_error(self, reason: str) -> Never:
        raise ArtifactContractError(
            ArtifactErrorCode.EXACT_TREE_MISMATCH,
            operation_id="recover-published-artifacts",
            target_basename=self._target_name,
            internal_context={"reason": reason},
        )

    def _unsupported(self) -> None:
        raise ArtifactContractError(
            ArtifactErrorCode.UNRECOGNIZED_TARGET,
            operation_id="publish-artifacts",
            target_basename=self._settings.artifact_dir.name,
        )

    def remnant_state(self) -> PublicationState:
        if self._operation_id is None:
            self._operation_id = self._remnant_operation_id()
            if self._operation_id is None:
                return PublicationState.NO_REMNANT
            self._marker_payload = self._publication_marker_payload()
        backup = self._named_exists(self._backup_name)
        tombstone = self._named_exists(self._tombstone_name)
        backup_marker = self._named_exists(self._backup_marker_name)
        tombstone_marker = self._named_exists(self._tombstone_marker_name)
        observed = (backup, tombstone, backup_marker, tombstone_marker)
        states = {
            (True, False, True, False): PublicationState.BACKUP_WITH_MARKER,
            (True, False, True, True): (PublicationState.BACKUP_WITH_PREPARED_TOMBSTONE_MARKER),
            (False, True, True, True): PublicationState.TOMBSTONE_WITH_BOTH_MARKERS,
            (False, False, True, True): PublicationState.BOTH_MARKERS_ONLY,
            (False, False, True, False): PublicationState.BACKUP_MARKER_ONLY,
        }
        try:
            state = states[observed]
        except KeyError:
            self._remnant_error("ambiguous_publication_remnant")
        if backup_marker:
            self._verify_marker(self._backup_marker_name)
        if tombstone_marker:
            self._verify_marker(self._tombstone_marker_name)
        if backup:
            self._verify_named_artifact(self._backup_name)
        if tombstone:
            self._verify_named_artifact(self._tombstone_name)
        return state


class ExpectedAcceptedPublicationStage:
    """Opaque publication authority issued only after expected acceptance."""

    __slots__ = ("_admission", "_closed", "_result")

    _admission: _ExpectedAcceptedReceiverAdmission | None
    _closed: bool
    _result: VerifiedArtifactSet

    def __new__(cls) -> ExpectedAcceptedPublicationStage:
        raise TypeError("expected-accepted publication stage is issuer-owned")

    @classmethod
    def _issue(
        cls,
        result: VerifiedArtifactSet,
    ) -> ExpectedAcceptedPublicationStage:
        if type(result) is not VerifiedArtifactSet:
            raise TypeError("expected-accepted publication stage requires exact result")
        value = object.__new__(cls)
        value._result = result
        value._admission = None
        value._closed = False
        return value

    @property
    def expected_result(self) -> VerifiedArtifactSet:
        return self._result

    def preflight_expected_accepted_custody(
        self,
        *,
        admission: _ExpectedAcceptedReceiverAdmission,
    ) -> None:
        if self._closed or self._admission is not None:
            raise ValueError("expected-accepted publication receiver is unavailable")
        self._admission = admission

    def assert_live(self) -> None:
        self._custody().assert_live()

    def rename_stage_to_target(self) -> None:
        self._custody().rename_stage_to_target()

    def rollback_target_to_stage(self) -> None:
        self._custody().rollback_target_to_stage()

    def commit_after_stage_marker_removal(self) -> None:
        self._custody().commit_after_stage_marker_removal()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._admission is None:
            return
        issuance = object.__getattribute__(self._admission, "_issuance")
        custody = issuance.custody
        if type(custody) is TransferredCandidateCustody:
            custody.close()

    def _custody(self) -> TransferredCandidateCustody:
        if self._closed or self._admission is None:
            raise ValueError("expected-accepted publication stage is closed")
        issuance = object.__getattribute__(self._admission, "_issuance")
        custody = issuance.custody
        if (
            issuance.receiver is not self
            or issuance.state != "TRANSFERRED"
            or type(custody) is not TransferredCandidateCustody
        ):
            raise ValueError("expected-accepted publication custody changed")
        return custody


@contextmanager
def authorize_candidate_for_publication(
    candidate: object,
) -> Iterator[ExpectedAcceptedPublicationStage]:
    """Consume expected verification into one publication receiver."""
    from finproof.data.artifacts.builder import CandidateArtifactSet
    from finproof.data.artifacts.database import artifact_verification_kernel

    if type(candidate) is not CandidateArtifactSet:
        raise TypeError("publication authorization requires exact candidate")
    candidate._require_issued()
    with candidate.open_verification_root() as root:
        result = artifact_verification_kernel().verify_expected_from_root(
            manifest=candidate._manifest,
            root=root,
        )
        seal = root.take_expected_acceptance_seal()
    authorized = ExpectedAcceptedPublicationStage._issue(VerifiedArtifactSet._from_expected(result))
    try:
        admission = candidate.issue_expected_accepted_receiver_admission(receiver=authorized)
        candidate.transfer_expected_accepted_custody(
            expected_acceptance_seal=seal,
            admission=admission,
        )
    except BaseException:
        authorized.close()
        candidate._custody.discard_if_exact()
        raise
    try:
        yield authorized
    finally:
        authorized.close()


def publish_verified_stage(
    authorized: ExpectedAcceptedPublicationStage,
    *,
    settings: Settings,
    clean: bool,
    filesystem: ArtifactFilesystem,
) -> ArtifactExpectedVerificationResult:
    """Publish only one exact expected-accepted stage capability."""
    if type(authorized) is not ExpectedAcceptedPublicationStage:
        raise TypeError("publisher requires expected-accepted publication stage")
    if type(settings) is not Settings or type(clean) is not bool:
        raise TypeError("publisher requires exact settings and clean flag")
    machine = _PublicationStateMachine._from_test_ports(
        transition=authorized,
        filesystem=filesystem,
        operation_id="publish-artifacts",
        target_basename=settings.artifact_dir.name,
    )
    machine.publish(clean=clean)
    return authorized.expected_result.logical_contract


def recover_owned_remnants(
    settings: Settings,
    *,
    filesystem: ArtifactFilesystem,
) -> None:
    """Resume only one exact marker-owned publication cleanup chain."""
    if type(settings) is not Settings:
        raise TypeError("publication recovery requires exact settings")
    transition = cast(PublicationTransitionPort, filesystem)
    if filesystem.remnant_state() is PublicationState.NO_REMNANT:
        transition.close()
        return
    machine = _PublicationStateMachine._from_test_ports(
        transition=transition,
        filesystem=filesystem,
        operation_id="recover-published-artifacts",
        target_basename=settings.artifact_dir.name,
    )
    machine.recover()


class _PublicationStateMachine:
    """One-use mechanics with no production publication authority."""

    _filesystem: ArtifactFilesystem
    _operation_id: str
    _state: PublicationState
    _target_basename: str
    _transition: PublicationTransitionPort

    __slots__ = ("_filesystem", "_operation_id", "_state", "_target_basename", "_transition")

    def __new__(cls) -> _PublicationStateMachine:
        raise TypeError("publication state machine requires sealed ports")

    @classmethod
    def _from_test_ports(
        cls,
        *,
        transition: PublicationTransitionPort,
        filesystem: ArtifactFilesystem,
        operation_id: str,
        target_basename: str,
    ) -> _PublicationStateMachine:
        value = object.__new__(cls)
        value._transition = transition
        value._filesystem = filesystem
        value._operation_id = operation_id
        value._target_basename = target_basename
        value._state = PublicationState.STAGE_VERIFIED
        return value

    @property
    def state(self) -> PublicationState:
        return self._state

    def publish(self, *, clean: bool) -> None:
        try:
            self._transition.assert_live()
            had_target = self._filesystem.target_exists()
            if had_target:
                if not clean:
                    raise ArtifactContractError(
                        ArtifactErrorCode.EXISTING_TARGET,
                        operation_id=self._operation_id,
                        target_basename=self._target_basename,
                    )
                self._filesystem.recognize_target()
                try:
                    self._filesystem.rename_target_to_backup()
                    self._state = PublicationState.BACKUP_VERIFIED
                    self._filesystem.verify_backup()
                except (ArtifactContractError, OSError, TypeError, ValueError) as cause:
                    if self._state is PublicationState.BACKUP_VERIFIED:
                        self._restore_backup_or_raise(cause)
                    raise
            try:
                self._transition.rename_stage_to_target()
            except (ArtifactContractError, OSError, TypeError, ValueError) as cause:
                if had_target:
                    self._restore_backup_or_raise(cause)
                raise
            self._state = PublicationState.TARGET_RENAMED_UNCOMMITTED
            try:
                self._filesystem.verify_target()
                self._transition.commit_after_stage_marker_removal()
            except (ArtifactContractError, OSError, TypeError, ValueError) as cause:
                try:
                    self._transition.rollback_target_to_stage()
                except (ArtifactContractError, OSError, TypeError, ValueError) as rollback:
                    self._raise_rollback(rollback)
                if had_target:
                    self._restore_backup_or_raise(cause)
                self._state = PublicationState.STAGE_VERIFIED
                raise
            if not had_target:
                self._state = PublicationState.NO_REMNANT
                return
            self._state = PublicationState.PUBLISHED
            try:
                self._state = PublicationState.BACKUP_WITH_MARKER
                self._filesystem.prepare_tombstone_marker()
                self._state = PublicationState.BACKUP_WITH_PREPARED_TOMBSTONE_MARKER
                self._filesystem.rename_backup_to_tombstone()
                self._state = PublicationState.TOMBSTONE_WITH_BOTH_MARKERS
                self._filesystem.delete_tombstone()
                self._state = PublicationState.BOTH_MARKERS_ONLY
                self._filesystem.unlink_tombstone_marker()
                self._state = PublicationState.BACKUP_MARKER_ONLY
                self._filesystem.unlink_backup_marker()
                self._state = PublicationState.NO_REMNANT
            except (ArtifactContractError, OSError, TypeError, ValueError) as cleanup:
                raise ArtifactContractError(
                    ArtifactErrorCode.BACKUP_CLEANUP_FAILED_AFTER_PUBLISH,
                    operation_id=self._operation_id,
                    target_basename=self._target_basename,
                    published=True,
                    internal_context={"state": self._state.value},
                ) from cleanup
        finally:
            self._transition.close()

    def _restore_backup_or_raise(self, cause: BaseException) -> None:
        try:
            self._filesystem.restore_backup_to_target()
        except (ArtifactContractError, OSError, TypeError, ValueError) as rollback:
            self._raise_rollback(rollback)
        self._state = PublicationState.STAGE_VERIFIED
        raise cause

    def recover(self) -> None:
        try:
            self._transition.assert_live()
            self._state = self._filesystem.remnant_state()
            if not self._filesystem.target_exists():
                if self._state in {
                    PublicationState.BACKUP_WITH_MARKER,
                    PublicationState.BACKUP_WITH_PREPARED_TOMBSTONE_MARKER,
                }:
                    self._filesystem.verify_backup()
                    if self._state is PublicationState.BACKUP_WITH_PREPARED_TOMBSTONE_MARKER:
                        self._filesystem.unlink_tombstone_marker()
                    self._filesystem.restore_backup_to_target()
                    self._state = PublicationState.NO_REMNANT
                    return
                raise ArtifactContractError(
                    ArtifactErrorCode.UNRECOGNIZED_TARGET,
                    operation_id=self._operation_id,
                    target_basename=self._target_basename,
                    internal_context={"reason": "absent_target_has_no_complete_backup"},
                )
            self._filesystem.verify_target()
            if self._state is PublicationState.BACKUP_WITH_MARKER:
                self._filesystem.prepare_tombstone_marker()
                self._state = PublicationState.BACKUP_WITH_PREPARED_TOMBSTONE_MARKER
            if self._state is PublicationState.BACKUP_WITH_PREPARED_TOMBSTONE_MARKER:
                self._filesystem.rename_backup_to_tombstone()
                self._state = PublicationState.TOMBSTONE_WITH_BOTH_MARKERS
            if self._state is PublicationState.TOMBSTONE_WITH_BOTH_MARKERS:
                self._filesystem.delete_tombstone()
                self._state = PublicationState.BOTH_MARKERS_ONLY
            if self._state is PublicationState.BOTH_MARKERS_ONLY:
                self._filesystem.unlink_tombstone_marker()
                self._state = PublicationState.BACKUP_MARKER_ONLY
            if self._state is PublicationState.BACKUP_MARKER_ONLY:
                self._filesystem.unlink_backup_marker()
                self._state = PublicationState.NO_REMNANT
        finally:
            self._transition.close()

    def _raise_rollback(self, rollback: BaseException) -> None:
        context = dict(getattr(rollback, "internal_context", {}))
        context["state"] = self._state.value
        raise ArtifactContractError(
            ArtifactErrorCode.PUBLICATION_ROLLBACK_FAILED,
            operation_id=self._operation_id,
            target_basename=self._target_basename,
            internal_context=context,
        ) from rollback
