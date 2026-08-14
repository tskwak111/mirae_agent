"""Closed and bounded artifact-build errors."""

import re
from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

_OPERATION_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")


class ArtifactErrorCode(StrEnum):
    INVALID_SETTINGS = "invalid_settings"
    UNSAFE_TARGET = "unsafe_target"
    EXISTING_TARGET = "existing_target"
    UNRECOGNIZED_TARGET = "unrecognized_target"
    UNRECOGNIZED_ORPHAN_STAGE = "unrecognized_orphan_stage"
    MANIFEST_INVALID = "manifest_invalid"
    SCHEMA_INVALID = "schema_invalid"
    CONFIG_INVALID = "config_invalid"
    SERIALIZATION_FAILED = "serialization_failed"
    ROW_COUNT_MISMATCH = "row_count_mismatch"
    TABLE_SCHEMA_MISMATCH = "table_schema_mismatch"
    SORT_KEY_MISMATCH = "sort_key_mismatch"
    UNIQUE_KEY_MISMATCH = "unique_key_mismatch"
    EXACT_LINK_CONFLICT = "exact_link_conflict"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    DATABASE_VALIDATION_FAILED = "database_validation_failed"
    REPRODUCIBILITY_MISMATCH = "reproducibility_mismatch"
    LOGICAL_HASH_MISMATCH = "logical_hash_mismatch"
    REPORT_MISMATCH = "report_mismatch"
    TIMESTAMP_MISMATCH = "timestamp_mismatch"
    EXACT_TREE_MISMATCH = "exact_tree_mismatch"
    VERIFICATION_INCOMPLETE = "verification_incomplete"
    LOCK_HELD = "lock_held"
    STAGING_CLEANUP_FAILED = "staging_cleanup_failed"
    PUBLICATION_ROLLBACK_FAILED = "publication_rollback_failed"
    BACKUP_CLEANUP_FAILED_AFTER_PUBLISH = "backup_cleanup_failed_after_publish"
    BASELINE_MISSING = "baseline_missing"
    BASELINE_ALREADY_EXISTS = "baseline_already_exists"


class ArtifactContractError(Exception):
    """Artifact failure skeleton before public rendering is implemented."""

    def __init__(
        self,
        code: ArtifactErrorCode,
        *,
        operation_id: str,
        target_basename: str | None = None,
        published: bool = False,
        internal_context: Mapping[str, str] | None = None,
    ) -> None:
        if type(operation_id) is not str:
            raise TypeError("operation_id must be a string")
        if _OPERATION_ID_PATTERN.fullmatch(operation_id) is None:
            raise ValueError("operation_id has invalid syntax")
        if target_basename is not None:
            if type(target_basename) is not str:
                raise TypeError("target_basename must be a string or None")
            if (
                not 1 <= len(target_basename) <= 128
                or not target_basename.isprintable()
                or target_basename in {".", ".."}
                or "/" in target_basename
                or "\\" in target_basename
            ):
                raise ValueError("target_basename is unsafe")
        if internal_context is None:
            context: dict[str, str] = {}
        else:
            if not isinstance(internal_context, Mapping):
                raise TypeError("internal_context must be a mapping")
            if any(
                type(key) is not str or type(value) is not str
                for key, value in internal_context.items()
            ):
                raise TypeError("internal_context keys and values must be exact strings")
            context = dict(internal_context)
        self.code = code
        self.operation_id = operation_id
        self.target_basename = target_basename
        self.published = published
        self.internal_context = MappingProxyType(context)
        super().__init__(code.value)

    @property
    def safe_message(self) -> str:
        target = f" for {self.target_basename}" if self.target_basename is not None else ""
        return f"artifact error {self.code.value}{target} ({self.operation_id})"

    def __str__(self) -> str:
        return self.safe_message
