import hashlib
import warnings
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from tools.admit_official_archive import (
    ArchiveAdmissionError,
    ArchiveMemberSpec,
    ArchiveSpec,
    admit_archive,
    inspect_archive,
)

from tests.helpers.xlsx import write_xlsx

EXPECTED_MEMBERS = (
    "prbd01n001_data.xlsx",
    "prbd01n001_schema.xlsx",
    "pref01n001_data.xlsx",
    "pref01n001_schema.xlsx",
    "pref02n001_data.xlsx",
    "pref02n001_schema.xlsx",
    "prfd01n001_data.xlsx",
    "prfd01n001_schema.xlsx",
)


@dataclass(frozen=True)
class SealedArchiveFixture:
    archive: Path
    spec: ArchiveSpec


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_archive(path: Path, members: dict[str, bytes]) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


def _workbook_payload(tmp_path: Path, member: str) -> bytes:
    workbook = tmp_path / member
    write_xlsx(
        workbook,
        sheet_name="data" if member.endswith("_data.xlsx") else "schema",
        rows=(("ID",), ("1",)),
    )
    return workbook.read_bytes()


def _spec(path: Path, members: dict[str, bytes]) -> ArchiveSpec:
    return ArchiveSpec(
        sha256=_sha256(path),
        members=tuple(
            ArchiveMemberSpec(
                member=name,
                size_bytes=len(payload),
                sha256=hashlib.sha256(payload).hexdigest(),
                sheet_name="data" if name.endswith("_data.xlsx") else "schema",
            )
            for name, payload in members.items()
            if name in EXPECTED_MEMBERS
        ),
    )


@pytest.fixture
def sealed_archive_fixture(tmp_path: Path) -> SealedArchiveFixture:
    members = {name: _workbook_payload(tmp_path, name) for name in EXPECTED_MEMBERS}
    members["__MACOSX/._prbd01n001_data.xlsx"] = b"metadata"
    archive = tmp_path / "official.zip"
    _write_archive(archive, members)
    return SealedArchiveFixture(archive=archive, spec=_spec(archive, members))


def build_archive_fixture(tmp_path: Path, *, mutation: str) -> tuple[Path, ArchiveSpec, str]:
    members = {name: _workbook_payload(tmp_path, name) for name in EXPECTED_MEMBERS}
    archive = tmp_path / f"{mutation}.zip"

    if mutation == "wrong_hash":
        _write_archive(archive, members)
        expected = _spec(archive, members)
        return archive, ArchiveSpec(sha256="0" * 64, members=expected.members), "archive_sha256"
    if mutation == "missing":
        members.pop(EXPECTED_MEMBERS[-1])
        _write_archive(archive, members)
        complete = {
            name: _workbook_payload(tmp_path, f"expected-{name}") for name in EXPECTED_MEMBERS
        }
        return archive, _spec(archive, complete), "missing_member"
    if mutation == "duplicate":
        _write_archive(archive, members)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with ZipFile(archive, "a", compression=ZIP_DEFLATED) as zip_file:
                zip_file.writestr(EXPECTED_MEMBERS[0], members[EXPECTED_MEMBERS[0]])
        return archive, _spec(archive, members), "duplicate_member"
    if mutation == "traversal":
        members["__MACOSX/../escape.xlsx"] = b"escape"
        _write_archive(archive, members)
        return archive, _spec(archive, members), "path_escape"
    if mutation == "extra":
        members["unexpected.xlsx"] = b"extra"
        _write_archive(archive, members)
        return archive, _spec(archive, members), "extra_member"
    raise AssertionError(f"unknown mutation: {mutation}")


def test_archive_admission_keeps_only_the_eight_sealed_root_workbooks(
    sealed_archive_fixture: SealedArchiveFixture,
) -> None:
    admitted = inspect_archive(sealed_archive_fixture.archive, expected=sealed_archive_fixture.spec)

    assert tuple(item.member for item in admitted) == EXPECTED_MEMBERS
    assert all(not item.member.startswith("__MACOSX/") for item in admitted)


def test_admit_archive_replaces_target_with_only_admitted_workbooks(
    sealed_archive_fixture: SealedArchiveFixture,
    tmp_path: Path,
) -> None:
    target = tmp_path / "data"
    target.mkdir()
    (target / "old.xlsx").write_bytes(b"old")

    admitted = admit_archive(
        sealed_archive_fixture.archive,
        target,
        expected=sealed_archive_fixture.spec,
    )

    assert tuple(item.member for item in admitted) == EXPECTED_MEMBERS
    assert tuple(path.name for path in sorted(target.iterdir())) == EXPECTED_MEMBERS


@pytest.mark.parametrize("mutation", ["wrong_hash", "missing", "duplicate", "traversal", "extra"])
def test_archive_admission_fails_closed(tmp_path: Path, mutation: str) -> None:
    archive, expected, error_code = build_archive_fixture(tmp_path, mutation=mutation)

    with pytest.raises(ArchiveAdmissionError) as caught:
        inspect_archive(archive, expected=expected)

    assert caught.value.code == error_code
