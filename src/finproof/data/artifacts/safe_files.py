"""Descriptor-relative reads for trusted regular artifact inputs."""

import os
import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class SafeFileReadError(Exception):
    """A path could not be proven stable, nonsymlink, and regular."""


class SafeFileReadState(StrEnum):
    """Closed descriptor-relative result states."""

    PRESENT = "present"
    MISSING = "missing"
    INVALID = "invalid"


@dataclass(frozen=True)
class SafeFileReadResult:
    """One closed read result; only PRESENT carries bytes."""

    state: SafeFileReadState
    payload: bytes | None = None


@dataclass(frozen=True)
class ExpectedDirectoryIdentity:
    """Identity captured for one required directory anchor before a held read."""

    path: Path
    identity: tuple[int, int, int]

    @classmethod
    def from_stat(cls, path: Path, value: os.stat_result) -> "ExpectedDirectoryIdentity":
        """Capture an exact directory identity for a later descriptor open."""
        identity = _identity(value)
        if identity[2] != stat.S_IFDIR:
            raise SafeFileReadError("expected anchor is not a directory")
        return cls(path=path, identity=identity)


_HAS_SECURE_DESCRIPTOR_SUPPORT = (
    hasattr(os, "O_CLOEXEC")
    and hasattr(os, "O_DIRECTORY")
    and hasattr(os, "O_NOFOLLOW")
    and os.open in os.supports_dir_fd
    and os.stat in os.supports_dir_fd
    and os.stat in os.supports_follow_symlinks
)


def _identity(value: os.stat_result) -> tuple[int, int, int]:
    return (value.st_dev, value.st_ino, stat.S_IFMT(value.st_mode))


def _read_all(file_descriptor: int) -> bytes:
    chunks: list[bytes] = []
    while chunk := os.read(file_descriptor, 1024 * 1024):
        chunks.append(chunk)
    return b"".join(chunks)


def read_held_regular_file(
    path: Path,
    *,
    expected_directory: ExpectedDirectoryIdentity | None = None,
) -> bytes:
    """Read one absolute regular file while retaining its full descriptor chain."""
    result = inspect_held_regular_file(path, expected_directory=expected_directory)
    if result.state is not SafeFileReadState.PRESENT or result.payload is None:
        raise SafeFileReadError(f"descriptor-relative read was {result.state.value}")
    return result.payload


def inspect_held_regular_file(
    path: Path,
    *,
    expected_directory: ExpectedDirectoryIdentity | None = None,
) -> SafeFileReadResult:
    """Classify and read a file without rechecking its mutable absolute path."""
    if not _HAS_SECURE_DESCRIPTOR_SUPPORT:
        return SafeFileReadResult(SafeFileReadState.INVALID)
    if not path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts[1:]):
        return SafeFileReadResult(SafeFileReadState.INVALID)
    if expected_directory is not None and (
        not expected_directory.path.is_absolute()
        or not path.is_relative_to(expected_directory.path)
    ):
        return SafeFileReadResult(SafeFileReadState.INVALID)

    descriptors: list[int] = []
    child_records: list[tuple[int, str, tuple[int, int, int]]] = []
    result = SafeFileReadResult(SafeFileReadState.INVALID)
    expected_directory_seen = expected_directory is None
    try:
        root_descriptor = os.open(
            path.anchor,
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        descriptors.append(root_descriptor)
        root_identity = _identity(os.fstat(root_descriptor))
        current_path = Path(path.anchor)
        if expected_directory is not None and current_path == expected_directory.path:
            expected_directory_seen = True
            if root_identity != expected_directory.identity:
                raise SafeFileReadError("expected directory identity changed")
        parent_descriptor = root_descriptor

        components = path.parts[1:]
        if not components:
            raise SafeFileReadError("file path has no leaf")
        for index, component in enumerate(components):
            is_leaf = index == len(components) - 1
            try:
                before = os.stat(
                    component,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                if is_leaf:
                    result = SafeFileReadResult(SafeFileReadState.MISSING)
                    break
                raise
            expected_type = stat.S_IFREG if is_leaf else stat.S_IFDIR
            if stat.S_IFMT(before.st_mode) != expected_type:
                raise SafeFileReadError("path component has an unsafe type")
            flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
            if not is_leaf:
                flags |= os.O_DIRECTORY
            child_descriptor = os.open(
                component,
                flags,
                dir_fd=parent_descriptor,
            )
            descriptors.append(child_descriptor)
            opened_identity = _identity(os.fstat(child_descriptor))
            if opened_identity != _identity(before):
                raise SafeFileReadError("path component identity changed while opening")
            current_path /= component
            if expected_directory is not None and current_path == expected_directory.path:
                expected_directory_seen = True
                if opened_identity != expected_directory.identity:
                    raise SafeFileReadError("expected directory identity changed")
            child_records.append((parent_descriptor, component, opened_identity))
            parent_descriptor = child_descriptor
        else:
            if not expected_directory_seen:
                raise SafeFileReadError("expected directory was not opened")
            payload = _read_all(descriptors[-1])

            if _identity(os.fstat(root_descriptor)) != root_identity:
                raise SafeFileReadError("filesystem root identity changed during read")
            for descriptor, (parent, component, expected) in zip(
                descriptors[1:], child_records, strict=True
            ):
                if _identity(os.fstat(descriptor)) != expected:
                    raise SafeFileReadError("opened path component identity changed")
                after = os.stat(component, dir_fd=parent, follow_symlinks=False)
                if _identity(after) != expected:
                    raise SafeFileReadError("path component changed during read")
            result = SafeFileReadResult(SafeFileReadState.PRESENT, payload)
    except (OSError, SafeFileReadError):
        result = SafeFileReadResult(SafeFileReadState.INVALID)
    finally:
        close_failed = False
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                close_failed = True
        if close_failed:
            result = SafeFileReadResult(SafeFileReadState.INVALID)
    return result
