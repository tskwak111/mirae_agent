# mypy: disable-error-code="attr-defined,has-type,no-any-return,override,var-annotated"
"""Descriptor-owned direct build-input identity capabilities.

Private slot-only identities are allocated through guarded exact-identity factories;
public interfaces remain explicitly typed.
"""

import hashlib
import os
import stat
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import BinaryIO, Self

from finproof.core.settings import Settings
from finproof.data.artifacts.config import (
    ArtifactInputKind,
    ArtifactInputNamespace,
    ResolvedArtifactInput,
    resolve_logical_inputs,
)
from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
from finproof.data.artifacts.manifest import (
    ArtifactInput,
    _issue_build_input_manifest_seal,
    _register_build_input_identity,
)

_DECLARATIONS = (
    (ArtifactInputNamespace.SOURCE_ROOT, "input_manifest.json", ArtifactInputKind.SOURCE_MANIFEST),
    (
        ArtifactInputNamespace.SOURCE_ROOT,
        "schema_catalog.json",
        ArtifactInputKind.SOURCE_SCHEMA_CATALOG,
    ),
    (
        ArtifactInputNamespace.REPOSITORY,
        "config/artifact_build.yaml",
        ArtifactInputKind.ARTIFACT_BUILD_CONFIG,
    ),
    (
        ArtifactInputNamespace.REPOSITORY,
        "config/datasets.yaml",
        ArtifactInputKind.DATASET_REGISTRY,
    ),
    (
        ArtifactInputNamespace.REPOSITORY,
        "config/quality_rules.yaml",
        ArtifactInputKind.QUALITY_RULE_REGISTRY,
    ),
    (
        ArtifactInputNamespace.REPOSITORY,
        "config/rating_scale.yaml",
        ArtifactInputKind.RATING_SCALE_REGISTRY,
    ),
    (
        ArtifactInputNamespace.REPOSITORY,
        "config/state_rules.yaml",
        ArtifactInputKind.STATE_RULE_REGISTRY,
    ),
    (
        ArtifactInputNamespace.REPOSITORY,
        "schemas/artifact_manifest.schema.json",
        ArtifactInputKind.ARTIFACT_MANIFEST_SCHEMA,
    ),
    (
        ArtifactInputNamespace.REPOSITORY,
        "schemas/quality_issue.schema.json",
        ArtifactInputKind.QUALITY_ISSUE_SCHEMA,
    ),
)

_ResolvedFact = tuple[ArtifactInputNamespace, str, ArtifactInputKind, Path]


class _BundleOwner:
    __slots__ = ("bundle", "members")

    def __init__(self) -> None:
        self.bundle: ResolvedBuildInputBundle | None = None
        self.members: tuple[ResolvedArtifactInput, ...] | None = None


class ResolvedBuildInputBundle:
    """Instance-owned result of the closed CP1 logical-input resolver."""

    __slots__ = ("_facts", "_members", "_owner")

    def __new__(cls) -> "ResolvedBuildInputBundle":
        raise TypeError("ResolvedBuildInputBundle is factory-owned")

    @classmethod
    def from_settings(cls, settings: Settings) -> "ResolvedBuildInputBundle":
        members = resolve_logical_inputs(settings)
        facts = _resolved_facts(members)
        if facts != _expected_facts(settings):
            raise _invalid_resolved_bundle()
        value = object.__new__(cls)
        owner = _BundleOwner()
        object.__setattr__(value, "_members", members)
        object.__setattr__(value, "_facts", facts)
        object.__setattr__(value, "_owner", owner)
        owner.bundle = value
        owner.members = members
        return value

    def __copy__(self) -> "ResolvedBuildInputBundle":
        raise TypeError("ResolvedBuildInputBundle cannot be copied")

    def __deepcopy__(self, memo: dict[int, object]) -> "ResolvedBuildInputBundle":
        del memo
        raise TypeError("ResolvedBuildInputBundle cannot be copied")

    def __reduce__(self) -> object:
        raise TypeError("ResolvedBuildInputBundle cannot be copied")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("ResolvedBuildInputBundle cannot be subclassed")


class HeldVerifiedBuildInputs(AbstractContextManager["HeldVerifiedBuildInputs"]):
    """Live held-nine verification result before one-use ownership transfer."""

    __slots__ = ("_closed", "_records")

    def __new__(cls) -> "HeldVerifiedBuildInputs":
        raise TypeError("HeldVerifiedBuildInputs is verifier-owned")

    @classmethod
    def _from_records(cls, records: tuple["_HeldInput", ...]) -> Self:
        value = object.__new__(cls)
        value._records = records
        value._closed = False
        return value

    def __enter__(self) -> Self:
        if self._closed:
            raise _invalid_input_generation()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        self.close()

    def issue_identity_seal(self) -> object:
        if self._closed:
            raise _invalid_input_generation()
        try:
            for record in self._records:
                _revalidate_held_input(record)
        except (OSError, TypeError, ValueError) as exc:
            raise _invalid_input_generation() from exc
        owner = _HeldIdentitySealOwner(self._records)
        seal = _HeldIdentitySeal._issue(owner)
        self._records = ()
        self._closed = True
        return seal

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for record in reversed(self._records):
            _close_held_input(record)


class _HeldIdentitySealOwner:
    __slots__ = ("records", "seal")

    def __init__(self, records: tuple["_HeldInput", ...]) -> None:
        self.records = records
        self.seal: _HeldIdentitySeal | None = None


class _HeldIdentitySeal:
    __slots__ = ("_consumed", "_owner")

    def __new__(cls) -> "_HeldIdentitySeal":
        raise TypeError("held identity seals are verifier-owned")

    @classmethod
    def _issue(cls, owner: _HeldIdentitySealOwner) -> "_HeldIdentitySeal":
        value = object.__new__(cls)
        value._owner = owner
        value._consumed = False
        owner.seal = value
        return value

    def __copy__(self) -> "_HeldIdentitySeal":
        raise TypeError("held identity seals cannot be copied")

    def __deepcopy__(self, memo: dict[int, object]) -> "_HeldIdentitySeal":
        del memo
        raise TypeError("held identity seals cannot be copied")

    def __reduce__(self) -> object:
        raise TypeError("held identity seals cannot be copied")


class _IdentityOwner:
    __slots__ = ("identity", "records")

    def __init__(self, records: tuple["_HeldInput", ...]) -> None:
        self.identity: BuildInputIdentity | None = None
        self.records = records


class BuildInputIdentity:
    """Sole descriptor owner for the exact direct build-input generation."""

    __slots__ = (
        "_closed",
        "_logical_inputs",
        "_manifest_issuer",
        "_owner",
        "_records",
    )

    def __new__(cls) -> "BuildInputIdentity":
        raise TypeError("BuildInputIdentity is verifier-owned")

    @classmethod
    def from_verified(cls, *, seal: object) -> "BuildInputIdentity":
        records = _consume_held_identity_seal(seal)
        value = object.__new__(cls)
        owner = _IdentityOwner(records)
        logical_inputs = tuple(_artifact_input(record) for record in records)
        value._records = records
        value._logical_inputs = logical_inputs
        value._closed = False
        value._owner = owner
        owner.identity = value
        value._manifest_issuer = _register_build_input_identity(value, logical_inputs)
        return value

    @property
    def logical_inputs(self) -> tuple[ArtifactInput, ...]:
        self._require_live()
        return self._logical_inputs

    @property
    def source_manifest_sha256(self) -> str:
        return self.logical_inputs[0].sha256

    @property
    def schema_catalog_sha256(self) -> str:
        return self.logical_inputs[1].sha256

    def open_verified_input(self, *, kind: ArtifactInputKind) -> AbstractContextManager[BinaryIO]:
        self._require_live()
        if type(kind) is not ArtifactInputKind:
            raise _invalid_input_generation()
        matches = tuple(record for record in self._records if record.member.kind is kind)
        if len(matches) != 1:
            raise _invalid_input_generation()
        return self._open_record(matches[0])

    @contextmanager
    def _open_record(self, record: "_HeldInput") -> Iterator[BinaryIO]:
        self.assert_unchanged()
        try:
            descriptor = os.dup(record.leaf_fd)
            os.lseek(descriptor, 0, os.SEEK_SET)
        except OSError as exc:
            raise _invalid_input_generation() from exc
        try:
            with os.fdopen(descriptor, "rb", closefd=True) as stream:
                yield stream
        finally:
            self.assert_unchanged()

    def assert_unchanged(self) -> None:
        self._require_live()
        try:
            for record in self._records:
                _revalidate_held_input(record)
        except (OSError, TypeError, ValueError) as exc:
            raise _invalid_input_generation() from exc

    def take_manifest_identity_seal(self) -> object:
        self.assert_unchanged()
        return _issue_build_input_manifest_seal(
            self._manifest_issuer,
            self,
            self._logical_inputs,
        )

    def close(self) -> None:
        try:
            if self._closed:
                return
            owner = self._owner
            if owner.identity is not self or owner.records is not self._records:
                raise ValueError("build identity ownership changed")
        except (AttributeError, TypeError, ValueError) as exc:
            raise _invalid_input_generation() from exc
        self._closed = True
        for record in reversed(self._records):
            _close_held_input(record)

    def _require_live(self) -> None:
        try:
            if (
                self._closed
                or type(self) is not BuildInputIdentity
                or type(self._owner) is not _IdentityOwner
                or self._owner.identity is not self
                or self._owner.records is not self._records
            ):
                raise ValueError("build identity is not live")
        except (AttributeError, TypeError, ValueError) as exc:
            raise _invalid_input_generation() from exc

    def __copy__(self) -> "BuildInputIdentity":
        raise TypeError("BuildInputIdentity cannot be copied")

    def __deepcopy__(self, memo: dict[int, object]) -> "BuildInputIdentity":
        del memo
        raise TypeError("BuildInputIdentity cannot be copied")

    def __reduce__(self) -> object:
        raise TypeError("BuildInputIdentity cannot be copied")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("BuildInputIdentity cannot be subclassed")


def verify_build_inputs(
    settings: Settings,
    resolved: ResolvedBuildInputBundle,
) -> AbstractContextManager[HeldVerifiedBuildInputs]:
    """Verify and retain the exact nine recomputed input generations."""
    members = _require_resolved_bundle(settings, resolved)
    records: list[_HeldInput] = []
    try:
        for member in members:
            root = (
                settings.source_root
                if member.namespace is ArtifactInputNamespace.SOURCE_ROOT
                else settings.repository_root
            )
            records.append(_open_held_input(root, member))
        return HeldVerifiedBuildInputs._from_records(tuple(records))
    except (OSError, TypeError, ValueError) as exc:
        for record in reversed(records):
            _close_held_input(record)
        raise _invalid_input_generation() from exc


@dataclass(frozen=True)
class _HeldInput:
    member: ResolvedArtifactInput
    directory_fds: tuple[int, ...]
    directory_identities: tuple[tuple[int, int, int, int, int], ...]
    leaf_name: str
    leaf_fd: int
    leaf_identity: tuple[int, int, int, int]
    size_bytes: int
    sha256: str


def _open_held_input(root: Path, member: ResolvedArtifactInput) -> _HeldInput:
    directory_fds: list[int] = []
    leaf_fd = -1
    try:
        directory_flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        root_fd = os.open(root, directory_flags)
        directory_fds.append(root_fd)
        components = member.path.split("/")
        for component in components[:-1]:
            child_fd = os.open(component, directory_flags, dir_fd=directory_fds[-1])
            directory_fds.append(child_fd)
        leaf_name = components[-1]
        before = os.stat(leaf_name, dir_fd=directory_fds[-1], follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError("build input must be a single-link regular file")
        leaf_fd = os.open(
            leaf_name,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_fds[-1],
        )
        opened = os.fstat(leaf_fd)
        if _file_identity(opened) != _file_identity(before):
            raise ValueError("build input changed during descriptor open")
        size_bytes, sha256 = _hash_descriptor(leaf_fd)
        return _HeldInput(
            member=member,
            directory_fds=tuple(directory_fds),
            directory_identities=tuple(
                _directory_identity(
                    os.fstat(descriptor),
                    track_mutation=index == len(directory_fds) - 1,
                )
                for index, descriptor in enumerate(directory_fds)
            ),
            leaf_name=leaf_name,
            leaf_fd=leaf_fd,
            leaf_identity=_file_identity(opened),
            size_bytes=size_bytes,
            sha256=sha256,
        )
    except BaseException:
        if leaf_fd >= 0:
            with suppress(OSError):
                os.close(leaf_fd)
        for descriptor in reversed(directory_fds):
            with suppress(OSError):
                os.close(descriptor)
        raise


def _hash_descriptor(descriptor: int) -> tuple[int, str]:
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = os.read(descriptor, 64 * 1024)
        if not chunk:
            break
        size += len(chunk)
        digest.update(chunk)
    os.lseek(descriptor, 0, os.SEEK_SET)
    return size, digest.hexdigest()


def _revalidate_held_input(record: _HeldInput) -> None:
    if (
        tuple(
            _directory_identity(
                os.fstat(descriptor),
                track_mutation=expected[3] >= 0,
            )
            for descriptor, expected in zip(
                record.directory_fds,
                record.directory_identities,
                strict=True,
            )
        )
        != record.directory_identities
    ):
        raise ValueError("build input parent identity changed")
    opened = os.fstat(record.leaf_fd)
    if (
        _file_identity(opened) != record.leaf_identity
        or not stat.S_ISREG(opened.st_mode)
        or opened.st_nlink != 1
    ):
        raise ValueError("held build input identity changed")
    named = os.stat(
        record.leaf_name,
        dir_fd=record.directory_fds[-1],
        follow_symlinks=False,
    )
    if _file_identity(named) != record.leaf_identity:
        raise ValueError("build input name generation changed")
    if _hash_descriptor(record.leaf_fd) != (record.size_bytes, record.sha256):
        raise ValueError("build input bytes changed")


def _consume_held_identity_seal(seal: object) -> tuple[_HeldInput, ...]:
    try:
        if type(seal) is not _HeldIdentitySeal:
            raise TypeError("wrong held identity seal type")
        owner = seal._owner
        if (
            type(owner) is not _HeldIdentitySealOwner
            or owner.seal is not seal
            or seal._consumed
            or type(owner.records) is not tuple
            or len(owner.records) != len(_DECLARATIONS)
        ):
            raise ValueError("invalid held identity seal")
        seal._consumed = True
        return owner.records
    except (AttributeError, TypeError, ValueError) as exc:
        raise _invalid_input_generation() from exc


def _artifact_input(record: _HeldInput) -> ArtifactInput:
    return ArtifactInput(
        namespace=record.member.namespace.value,
        path=record.member.path,
        kind=record.member.kind.value,
        size_bytes=record.size_bytes,
        sha256=record.sha256,
    )


def _directory_identity(
    value: os.stat_result,
    *,
    track_mutation: bool = True,
) -> tuple[int, int, int, int, int]:
    if not stat.S_ISDIR(value.st_mode):
        raise ValueError("build input parent is not a directory")
    return (
        value.st_dev,
        value.st_ino,
        stat.S_IFMT(value.st_mode),
        value.st_mtime_ns if track_mutation else -1,
        value.st_ctime_ns if track_mutation else -1,
    )


def _file_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return value.st_dev, value.st_ino, stat.S_IFMT(value.st_mode), value.st_nlink


def _close_held_input(record: _HeldInput) -> None:
    with suppress(OSError):
        os.close(record.leaf_fd)
    for descriptor in reversed(record.directory_fds):
        with suppress(OSError):
            os.close(descriptor)


def _expected_facts(settings: Settings) -> tuple[_ResolvedFact, ...]:
    return tuple(
        (
            namespace,
            path,
            kind,
            (
                settings.source_root
                if namespace is ArtifactInputNamespace.SOURCE_ROOT
                else settings.repository_root
            )
            / path,
        )
        for namespace, path, kind in _DECLARATIONS
    )


def _resolved_facts(
    members: tuple[ResolvedArtifactInput, ...],
) -> tuple[_ResolvedFact, ...]:
    return tuple(
        (member.namespace, member.path, member.kind, member.absolute_path) for member in members
    )


def _require_resolved_bundle(
    settings: Settings,
    resolved: ResolvedBuildInputBundle,
) -> tuple[ResolvedArtifactInput, ...]:
    try:
        if type(resolved) is not ResolvedBuildInputBundle:
            raise TypeError("resolved bundle has the wrong runtime type")
        owner = resolved._owner
        members = resolved._members
        facts = resolved._facts
        if (
            type(owner) is not _BundleOwner
            or owner.bundle is not resolved
            or owner.members is not members
            or type(members) is not tuple
            or len(members) != len(_DECLARATIONS)
            or any(type(member) is not ResolvedArtifactInput for member in members)
            or _resolved_facts(members) != facts
            or facts != _expected_facts(settings)
        ):
            raise ValueError("resolved bundle ownership or declarations changed")
        return members
    except (AttributeError, TypeError, ValueError) as exc:
        raise _invalid_resolved_bundle() from exc


def _invalid_resolved_bundle() -> ArtifactContractError:
    return ArtifactContractError(
        ArtifactErrorCode.CONFIG_INVALID,
        operation_id="verify-build-inputs",
        internal_context={"reason": "invalid_resolved_bundle"},
    )


def _invalid_input_generation() -> ArtifactContractError:
    return ArtifactContractError(
        ArtifactErrorCode.CHECKSUM_MISMATCH,
        operation_id="verify-build-inputs",
        internal_context={"reason": "invalid_input_generation"},
    )
