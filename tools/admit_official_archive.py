#!/usr/bin/env python3
"""Fail-closed admission for the organizer's sealed workbook archive."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final
from zipfile import BadZipFile, ZipFile

if TYPE_CHECKING:
    from tools.xlsx_stream import list_sheet_names
elif __package__:
    from .xlsx_stream import list_sheet_names
else:
    from xlsx_stream import list_sheet_names


@dataclass(frozen=True)
class ArchiveMemberSpec:
    member: str
    size_bytes: int
    sha256: str
    sheet_name: str


@dataclass(frozen=True)
class ArchiveSpec:
    sha256: str
    members: tuple[ArchiveMemberSpec, ...]


@dataclass(frozen=True)
class AdmittedWorkbook:
    member: str
    size_bytes: int
    sha256: str


class ArchiveAdmissionError(ValueError):
    """A sealed archive violated an admission boundary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _member(name: str, size_bytes: int, sha256: str) -> ArchiveMemberSpec:
    return ArchiveMemberSpec(
        member=name,
        size_bytes=size_bytes,
        sha256=sha256,
        sheet_name="data" if name.endswith("_data.xlsx") else "schema",
    )


OFFICIAL_ARCHIVE: Final = ArchiveSpec(
    sha256="93450657290e09f5f6afd65bdacb229faddca33a9e9bad6d37bbd11f41c492fc",
    members=(
        _member(
            "prbd01n001_data.xlsx",
            5926563,
            "574ae5d6c1d98704712c256ed5352cbaed065ea9c3a6eb7b2a52adb305fa9001",
        ),
        _member(
            "prbd01n001_schema.xlsx",
            7863,
            "9965126695066f9dc07951a78054e9e7639b6863d1ad2a9616f7e2d8fcadbc4f",
        ),
        _member(
            "pref01n001_data.xlsx",
            957630,
            "18c4329d8fc8768d030316816f3e6e48226a3c217db3354245b766a2c6f6c592",
        ),
        _member(
            "pref01n001_schema.xlsx",
            9022,
            "2135081fd8107760d127915147032987ee1d9e7c2ed039665ae4214b96faec5a",
        ),
        _member(
            "pref02n001_data.xlsx",
            2102888,
            "ca6a274aeaf3f884f2f7635d7802558bc6dabf408871ecb1f71e5a50d9d34067",
        ),
        _member(
            "pref02n001_schema.xlsx",
            7294,
            "32ac732f0501f4ab518682175fecc50756ee1eafde9296801f139d62559b5e64",
        ),
        _member(
            "prfd01n001_data.xlsx",
            9130974,
            "81b3ce3f1d5042b32fd52a76acff094fc5b8dd9fa36289af2fb54c195eb5d94c",
        ),
        _member(
            "prfd01n001_schema.xlsx",
            8306,
            "cfe7be44cbcd9ce349206776a4eb46996162643acbf3ca5a4f74c2886394862b",
        ),
    ),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _is_traversal(name: str) -> bool:
    path = PurePosixPath(name)
    return "\\" in name or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts)


def _verified_payloads(
    archive: Path, *, expected: ArchiveSpec = OFFICIAL_ARCHIVE
) -> tuple[tuple[AdmittedWorkbook, bytes], ...]:
    """Read and validate the exact workbook payloads admitted from one archive."""

    if not archive.is_file():
        raise ArchiveAdmissionError("archive_missing", "archive is not a regular file")
    if _sha256(archive) != expected.sha256:
        raise ArchiveAdmissionError(
            "archive_sha256", "archive SHA-256 does not match the sealed value"
        )

    expected_by_name = {item.member: item for item in expected.members}
    if len(expected_by_name) != len(expected.members):
        raise ValueError("expected archive specification contains duplicate members")
    payloads: dict[str, bytes] = {}
    try:
        with ZipFile(archive) as zip_file:
            for info in zip_file.infolist():
                name = info.filename
                if _is_traversal(name):
                    raise ArchiveAdmissionError("path_escape", f"unsafe archive member: {name!r}")
                if name.startswith("__MACOSX/"):
                    continue
                if name not in expected_by_name:
                    raise ArchiveAdmissionError(
                        "extra_member", f"unexpected archive member: {name!r}"
                    )
                if name in payloads:
                    raise ArchiveAdmissionError(
                        "duplicate_member", f"duplicate archive member: {name!r}"
                    )
                payloads[name] = zip_file.read(info)
    except BadZipFile as error:
        raise ArchiveAdmissionError("invalid_archive", "archive is not a readable ZIP") from error

    missing = tuple(name for name in expected_by_name if name not in payloads)
    if missing:
        raise ArchiveAdmissionError("missing_member", f"missing archive member: {missing[0]!r}")

    admitted: list[tuple[AdmittedWorkbook, bytes]] = []
    with tempfile.TemporaryDirectory(prefix="finproof-archive-check-") as temporary:
        root = Path(temporary)
        for spec in expected.members:
            payload = payloads[spec.member]
            if len(payload) != spec.size_bytes:
                raise ArchiveAdmissionError("member_size", f"size mismatch: {spec.member!r}")
            actual_sha256 = hashlib.sha256(payload).hexdigest()
            if actual_sha256 != spec.sha256:
                raise ArchiveAdmissionError("member_sha256", f"checksum mismatch: {spec.member!r}")
            staged = root / spec.member
            staged.write_bytes(payload)
            try:
                sheets = list_sheet_names(staged)
            except (BadZipFile, KeyError, ValueError) as error:
                raise ArchiveAdmissionError(
                    "invalid_workbook", f"invalid workbook: {spec.member!r}"
                ) from error
            if spec.sheet_name not in sheets:
                raise ArchiveAdmissionError(
                    "missing_sheet", f"missing {spec.sheet_name!r}: {spec.member!r}"
                )
            admitted.append(
                (
                    AdmittedWorkbook(
                        member=spec.member,
                        size_bytes=spec.size_bytes,
                        sha256=spec.sha256,
                    ),
                    payload,
                )
            )
    return tuple(admitted)


def inspect_archive(
    archive: Path, *, expected: ArchiveSpec = OFFICIAL_ARCHIVE
) -> tuple[AdmittedWorkbook, ...]:
    """Verify one archive and return its admitted root workbooks in sealed order."""

    return tuple(workbook for workbook, _ in _verified_payloads(archive, expected=expected))


def admit_archive(
    archive: Path, target: Path, *, expected: ArchiveSpec = OFFICIAL_ARCHIVE
) -> tuple[AdmittedWorkbook, ...]:
    """Verify one archive before atomically replacing a target workbook directory."""

    verified = _verified_payloads(archive, expected=expected)
    parent = target.parent.resolve()
    if not parent.is_dir():
        raise ArchiveAdmissionError("target_parent", "target parent directory is missing")
    with tempfile.TemporaryDirectory(prefix=f".{target.name}.admission-", dir=parent) as temporary:
        staged = Path(temporary) / target.name
        staged.mkdir()
        for workbook, payload in verified:
            (staged / workbook.member).write_bytes(payload)
        backup = parent / f".{target.name}.admission-backup"
        if backup.exists():
            raise ArchiveAdmissionError("target_busy", "admission backup path already exists")
        try:
            if target.exists():
                os.replace(target, backup)
            os.replace(staged, target)
        except OSError as error:
            if backup.exists() and not target.exists():
                os.replace(backup, target)
            raise ArchiveAdmissionError("target_replace", "staged replacement failed") from error
        if backup.exists():
            shutil.rmtree(backup)
    return tuple(workbook for workbook, _ in verified)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--admit", action="store_true")
    parser.add_argument("--target", type=Path, default=Path("source_material/data"))
    args = parser.parse_args(argv)
    try:
        admitted = (
            admit_archive(args.archive, args.target)
            if args.admit
            else inspect_archive(args.archive)
        )
    except ArchiveAdmissionError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"Official archive {'admitted' if args.admit else 'verified'}: {len(admitted)} workbooks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
