"""Authorization-independent guarded publication state mechanics."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode


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
