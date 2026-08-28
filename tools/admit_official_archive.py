#!/usr/bin/env python3
"""Fail-closed admission for the organizer's sealed workbook archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final
from zipfile import BadZipFile, ZipFile

if TYPE_CHECKING:
    from tools.audit_source_data import calculate, differences, require_official_profile
    from tools.extract_schema_catalog import build_catalog
    from tools.xlsx_stream import iter_sheet_rows, list_sheet_names
elif __package__:
    from .audit_source_data import calculate, differences, require_official_profile
    from .extract_schema_catalog import build_catalog
    from .xlsx_stream import iter_sheet_rows, list_sheet_names
else:
    from audit_source_data import calculate, differences, require_official_profile
    from extract_schema_catalog import build_catalog
    from xlsx_stream import iter_sheet_rows, list_sheet_names

from finproof.data.source_manifest import SourceFileManifest


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


def validate_candidate(candidate_root: Path) -> None:
    """Validate every candidate contract before any active path can move."""

    source_root = candidate_root / "source_material"
    data_root = source_root / "data"
    manifest_path = source_root / "input_manifest.json"
    catalog_path = source_root / "schema_catalog.json"
    audit_path = candidate_root / "tests/contracts/expected_source_audit.json"
    required = (data_root, manifest_path, catalog_path, audit_path)
    if not candidate_root.is_dir() or any(not path.exists() for path in required):
        raise ArchiveAdmissionError("candidate_missing", "candidate inventory is incomplete")

    actual_names = tuple(path.name for path in sorted(data_root.glob("*.xlsx")))
    expected_names = tuple(sorted(item.member for item in OFFICIAL_ARCHIVE.members))
    if actual_names != expected_names:
        raise ArchiveAdmissionError("candidate_inventory", "candidate workbook inventory differs")
    for spec in OFFICIAL_ARCHIVE.members:
        path = data_root / spec.member
        if path.stat().st_size != spec.size_bytes or _sha256(path) != spec.sha256:
            raise ArchiveAdmissionError(
                "candidate_workbook", f"candidate workbook differs: {spec.member!r}"
            )
        if spec.sheet_name not in list_sheet_names(path):
            raise ArchiveAdmissionError(
                "candidate_workbook", f"candidate workbook sheet differs: {spec.member!r}"
            )

    from finproof.core.errors import SourceContractError

    try:
        canonical_catalog = (
            json.dumps(
                build_catalog(schema_root=data_root),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode()
        if catalog_path.read_bytes() != canonical_catalog:
            raise ArchiveAdmissionError(
                "candidate_catalog", "candidate catalog is not generated from source schemas"
            )
        manifest = SourceFileManifest.load(manifest_path, catalog_path)
        observed_profile = tuple(
            (entry.table_id, entry.expected_rows, entry.expected_columns, entry.sheet_name)
            for entry in manifest.data_files
        )
        if observed_profile != (
            ("PRBD01N001", 21_882, 58, "data"),
            ("PREF01N001", 1_780, 98, "data"),
            ("PREF02N001", 6_037, 49, "data"),
            ("PRFD01N001", 23_676, 75, "data"),
        ):
            raise ArchiveAdmissionError("candidate_manifest", "candidate manifest profile differs")
        verified = manifest.verify(source_root)
        for source in verified.data_files:
            header = next(
                iter(iter_sheet_rows(source.verified_absolute_path, source.sheet_name))
            ).values
            if header != source.expected_headers:
                raise ArchiveAdmissionError(
                    "candidate_header",
                    f"schema and data headers differ: {source.table_id}",
                )
        actual_audit = calculate(source_root=source_root)
        require_official_profile(actual_audit)
        expected_audit = json.loads(audit_path.read_text(encoding="utf-8"))
        if differences(expected_audit, actual_audit):
            raise ArchiveAdmissionError("candidate_audit", "candidate audit contract differs")
    except ArchiveAdmissionError:
        raise
    except (
        OSError,
        ValueError,
        KeyError,
        StopIteration,
        json.JSONDecodeError,
        SourceContractError,
    ) as error:
        raise ArchiveAdmissionError("candidate_invalid", "candidate validation failed") from error


def _publication_checkpoint(step: int) -> None:
    """No-op checkpoint used by rollback failure-injection tests."""

    del step


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def publish_candidate(candidate_root: Path, repository_root: Path) -> None:
    """Publish the four active source groups as one rollback-guarded operation."""

    validate_candidate(candidate_root)
    repository_root = repository_root.resolve(strict=True)
    groups = (
        Path("source_material/data"),
        Path("source_material/input_manifest.json"),
        Path("source_material/schema_catalog.json"),
        Path("tests/contracts/expected_source_audit.json"),
    )
    states: list[tuple[Path, Path, bool]] = []
    source_material = repository_root / "source_material"
    active_data = source_material / "data"
    source_material_mode = stat.S_IMODE(source_material.stat().st_mode)
    active_data_mode = stat.S_IMODE(active_data.stat().st_mode) if active_data.exists() else None
    with tempfile.TemporaryDirectory(prefix=".source-publication-", dir=repository_root) as tmp:
        try:
            staging = Path(tmp) / "candidate"
            shutil.copytree(candidate_root, staging)
            validate_candidate(staging)
            staged_data = staging / "source_material/data"
            staged_data.chmod(stat.S_IMODE(staged_data.stat().st_mode) | 0o700)
            source_material.chmod(source_material_mode | 0o700)
            if active_data_mode is not None:
                active_data.chmod(active_data_mode | 0o700)
            backup_root = Path(tmp) / "backup"
            backup_root.mkdir()
            for step, relative in enumerate(groups, start=1):
                source = staging / relative
                target = repository_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                backup = backup_root / str(step)
                had_target = target.exists()
                if had_target:
                    os.replace(target, backup)
                states.append((target, backup, had_target))
                os.replace(source, target)
                _publication_checkpoint(step)
            for workbook in active_data.glob("*.xlsx"):
                workbook.chmod(0o444)
            (source_material / "input_manifest.json").chmod(0o444)
            (source_material / "schema_catalog.json").chmod(0o444)
            (repository_root / "tests/contracts/expected_source_audit.json").chmod(0o644)
            active_data.chmod(0o555)
            source_material.chmod(0o555)
        except Exception as error:
            rollback_error: OSError | None = None
            for target, backup, had_target in reversed(states):
                try:
                    _remove_path(target)
                    if had_target and backup.exists():
                        os.replace(backup, target)
                except OSError as caught:
                    rollback_error = caught
            try:
                if active_data_mode is not None and active_data.exists():
                    active_data.chmod(active_data_mode)
                source_material.chmod(source_material_mode)
            except OSError as caught:
                rollback_error = caught
            if rollback_error is not None:
                raise ArchiveAdmissionError(
                    "candidate_rollback", "candidate publication rollback failed"
                ) from rollback_error
            raise ArchiveAdmissionError(
                "candidate_publish", "candidate publication failed"
            ) from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--admit", action="store_true")
    action.add_argument("--publish", action="store_true")
    parser.add_argument("--target", type=Path, default=Path("source_material/data"))
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    try:
        if args.publish:
            if args.candidate_root is None:
                parser.error("--publish requires --candidate-root")
            publish_candidate(args.candidate_root, args.repo_root)
            print("Official source candidate published: 4 active groups")
            return 0
        if args.archive is None:
            parser.error("--check and --admit require --archive")
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
