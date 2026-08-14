"""Closed runtime access to packaged artifact schemas."""

import os
import stat
from enum import StrEnum
from importlib import metadata as importlib_metadata
from importlib import resources as importlib_resources
from pathlib import Path
from typing import Protocol

from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
from finproof.data.artifacts.safe_files import SafeFileReadError, read_held_regular_file


class RuntimeArtifactResource(StrEnum):
    """Frozen distribution destinations available during Checkpoint 1."""

    ARTIFACT_MANIFEST_SCHEMA = "finproof/resources/schemas/artifact_manifest.schema.json"
    QUALITY_ISSUE_SCHEMA = "finproof/resources/schemas/quality_issue.schema.json"


class CandidateBaselineProbe(Protocol):
    """Read-only baseline-presence boundary for repository candidate tooling."""

    def source_exists(self) -> bool:
        """Return whether the repository expected-contract source exists."""
        ...

    def resource_exists(self) -> bool:
        """Return whether the packaged expected-contract resource exists."""
        ...

    def second_check(self) -> None:
        """Recheck after a future private transform boundary."""
        ...


_EXPECTED_CONTRACT_DESTINATION = "finproof/resources/contracts/expected_phase1_artifacts.json"


def artifact_manifest_schema_bytes() -> bytes:
    """Return the packaged artifact-manifest schema bytes."""
    return _resource_bytes(RuntimeArtifactResource.ARTIFACT_MANIFEST_SCHEMA)


def quality_issue_schema_bytes() -> bytes:
    """Return the packaged quality-issue schema bytes."""
    return _resource_bytes(RuntimeArtifactResource.QUALITY_ISSUE_SCHEMA)


def _resource_bytes(resource: RuntimeArtifactResource) -> bytes:
    try:
        return _primary_read(resource)
    except ArtifactContractError as exc:
        if exc.internal_context != {"reason": "missing_primary_resource"}:
            raise
    return _editable_read(resource)


def _primary_candidate(resource: RuntimeArtifactResource) -> object:
    _require_resource(resource)
    relative = resource.value.removeprefix("finproof/")
    return importlib_resources.files("finproof").joinpath(*relative.split("/"))


def _primary_read(resource: RuntimeArtifactResource) -> bytes:
    candidate = _primary_candidate(resource)
    try:
        if isinstance(candidate, Path):
            payload = _held_path_read(resource, candidate)
            if payload is None:
                raise _schema_invalid("missing_primary_resource")
            return payload
        if candidate.is_dir():  # type: ignore[attr-defined]
            raise _schema_invalid("invalid_primary_resource")
        if not candidate.is_file():  # type: ignore[attr-defined]
            raise _schema_invalid("missing_primary_resource")
        return candidate.read_bytes()  # type: ignore[attr-defined,no-any-return]
    except ArtifactContractError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise _schema_invalid("invalid_primary_resource") from exc


def _primary_exists(resource: RuntimeArtifactResource) -> bool:
    candidate = _primary_candidate(resource)
    try:
        if isinstance(candidate, Path):
            return _held_path_read(resource, candidate) is not None
        return bool(candidate.is_file())  # type: ignore[attr-defined]
    except (OSError, TypeError, ValueError) as exc:
        raise _schema_invalid("invalid_primary_resource") from exc


def _editable_read(resource: RuntimeArtifactResource) -> bytes:
    root, candidate, relative_parts = _editable_candidate(resource)
    try:
        payload = _held_path_read(
            resource,
            candidate,
            root=root,
            relative_parts=relative_parts,
            invalid_reason="invalid_editable_resource",
        )
        if payload is None:
            raise _schema_invalid("missing_editable_resource")
        return payload
    except ArtifactContractError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise _schema_invalid("invalid_editable_resource") from exc


def _editable_exists(resource: RuntimeArtifactResource) -> bool:
    root, candidate, relative_parts = _editable_candidate(resource)
    try:
        return (
            _held_path_read(
                resource,
                candidate,
                root=root,
                relative_parts=relative_parts,
                invalid_reason="invalid_editable_resource",
            )
            is not None
        )
    except ArtifactContractError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise _schema_invalid("invalid_editable_resource") from exc


def _editable_candidate(
    resource: RuntimeArtifactResource,
) -> tuple[Path, Path, list[str]]:
    _require_resource(resource)
    distribution = importlib_metadata.distribution("finproof")
    root = Path(str(distribution.locate_file("")))
    candidate = Path(str(distribution.locate_file(resource.value)))
    relative_parts = resource.value.split("/")
    if candidate != root.joinpath(*relative_parts):
        raise _schema_invalid("invalid_editable_resource")
    return root, candidate, relative_parts


def _require_resource(resource: RuntimeArtifactResource) -> None:
    if type(resource) is not RuntimeArtifactResource:
        raise _schema_invalid("invalid_runtime_resource")


def _expected_contract_resource_exists() -> bool:
    relative_parts = _EXPECTED_CONTRACT_DESTINATION.removeprefix("finproof/").split("/")
    try:
        primary_root = importlib_resources.files("finproof")
        primary = primary_root.joinpath(*relative_parts)
        if isinstance(primary, Path):
            if _closed_entry_exists(Path(str(primary_root)), primary, relative_parts):
                return True
        elif primary.is_file() or primary.is_dir():
            return True
    except (OSError, TypeError, ValueError):
        return True

    try:
        distribution = importlib_metadata.distribution("finproof")
        root = Path(str(distribution.locate_file("")))
        candidate = Path(str(distribution.locate_file(_EXPECTED_CONTRACT_DESTINATION)))
        return _closed_entry_exists(root, candidate, _EXPECTED_CONTRACT_DESTINATION.split("/"))
    except importlib_metadata.PackageNotFoundError:
        return False
    except (OSError, TypeError, ValueError):
        return True


def _closed_entry_exists(root: Path, candidate: Path, relative_parts: list[str]) -> bool:
    if candidate != root.joinpath(*relative_parts):
        return True
    current = root
    try:
        root_stat = current.lstat()
        if current.is_symlink() or not stat.S_ISDIR(root_stat.st_mode):
            return True
        for index, part in enumerate(relative_parts):
            current /= part
            current_stat = current.lstat()
            if current.is_symlink():
                return True
            if index < len(relative_parts) - 1 and not stat.S_ISDIR(current_stat.st_mode):
                return True
        return True
    except FileNotFoundError:
        return False


def _held_path_read(
    resource: RuntimeArtifactResource,
    candidate: Path,
    *,
    root: Path | None = None,
    relative_parts: list[str] | None = None,
    invalid_reason: str = "invalid_primary_resource",
) -> bytes | None:
    if relative_parts is None:
        relative_parts = resource.value.removeprefix("finproof/").split("/")
    if root is None:
        root = candidate
        for _part in relative_parts:
            root = root.parent
    try:
        return read_held_regular_file(candidate)
    except SafeFileReadError as exc:
        if (
            _static_regular_identity(
                candidate,
                root=root,
                relative_parts=relative_parts,
                invalid_reason=invalid_reason,
            )
            is None
        ):
            return None
        raise _schema_invalid(invalid_reason) from exc


def _static_regular_identity(
    candidate: Path,
    *,
    root: Path,
    relative_parts: list[str],
    invalid_reason: str,
) -> os.stat_result | None:
    if candidate != root.joinpath(*relative_parts):
        raise _schema_invalid(invalid_reason)

    current = root
    try:
        root_stat = current.lstat()
        if current.is_symlink() or not stat.S_ISDIR(root_stat.st_mode):
            raise _schema_invalid(invalid_reason)
        for index, part in enumerate(relative_parts):
            current = current / part
            current_stat = current.lstat()
            if current.is_symlink():
                raise _schema_invalid(invalid_reason)
            is_leaf = index == len(relative_parts) - 1
            expected_type = stat.S_ISREG if is_leaf else stat.S_ISDIR
            if not expected_type(current_stat.st_mode):
                raise _schema_invalid(invalid_reason)
        return current_stat
    except FileNotFoundError:
        return None


def _schema_invalid(reason: str) -> ArtifactContractError:
    return ArtifactContractError(
        ArtifactErrorCode.SCHEMA_INVALID,
        operation_id="load-artifact-schema",
        internal_context={"reason": reason},
    )
