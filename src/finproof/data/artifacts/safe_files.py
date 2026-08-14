"""Descriptor-relative reads for trusted regular artifact inputs."""

import os
import stat
from pathlib import Path


class SafeFileReadError(Exception):
    """A path could not be proven stable, nonsymlink, and regular."""


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


def read_held_regular_file(path: Path) -> bytes:
    """Read one absolute regular file while retaining its full descriptor chain."""
    if not _HAS_SECURE_DESCRIPTOR_SUPPORT:
        raise SafeFileReadError("secure descriptor-relative reads are unsupported")
    if not path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts[1:]):
        raise SafeFileReadError("file path must be canonical and absolute")

    descriptors: list[int] = []
    child_records: list[tuple[int, str, tuple[int, int, int]]] = []
    close_failure: OSError | None = None
    active_error = False
    try:
        root_descriptor = os.open(
            path.anchor,
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        descriptors.append(root_descriptor)
        root_identity = _identity(os.fstat(root_descriptor))
        parent_descriptor = root_descriptor

        components = path.parts[1:]
        if not components:
            raise SafeFileReadError("file path has no leaf")
        for index, component in enumerate(components):
            is_leaf = index == len(components) - 1
            before = os.stat(
                component,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
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
            child_records.append((parent_descriptor, component, opened_identity))
            parent_descriptor = child_descriptor

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
        return payload
    except (OSError, SafeFileReadError) as exc:
        active_error = True
        if isinstance(exc, SafeFileReadError):
            raise
        raise SafeFileReadError("descriptor-relative read failed") from exc
    finally:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError as exc:
                close_failure = exc
        if close_failure is not None and not active_error:
            raise SafeFileReadError("descriptor close failed") from close_failure
