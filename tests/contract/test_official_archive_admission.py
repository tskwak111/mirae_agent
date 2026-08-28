import hashlib
import os
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
from tools.xlsx_stream import list_sheet_names

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


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    [
        ("member_size", "member_size"),
        ("member_sha256", "member_sha256"),
        ("missing_sheet", "missing_sheet"),
    ],
)
def test_archive_admission_rejects_exact_member_contract_failures(
    tmp_path: Path,
    mutation: str,
    error_code: str,
) -> None:
    members = {name: _workbook_payload(tmp_path, name) for name in EXPECTED_MEMBERS}
    archive = tmp_path / f"{mutation}.zip"
    expected_members = dict(members)
    if mutation == "member_size":
        members[EXPECTED_MEMBERS[0]] += b"size"
    elif mutation == "member_sha256":
        payload = bytearray(members[EXPECTED_MEMBERS[0]])
        payload[-1] ^= 1
        members[EXPECTED_MEMBERS[0]] = bytes(payload)
    else:
        wrong_sheet = tmp_path / "wrong-sheet.xlsx"
        write_xlsx(wrong_sheet, sheet_name="schema", rows=(("ID",), ("1",)))
        members[EXPECTED_MEMBERS[0]] = wrong_sheet.read_bytes()
        expected_members[EXPECTED_MEMBERS[0]] = members[EXPECTED_MEMBERS[0]]
    _write_archive(archive, members)
    expected = _spec(archive, expected_members)

    with pytest.raises(ArchiveAdmissionError) as caught:
        inspect_archive(archive, expected=expected)

    assert caught.value.code == error_code


def test_admit_archive_restores_target_bytes_when_staged_replacement_fails(
    sealed_archive_fixture: SealedArchiveFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "data"
    target.mkdir()
    (target / "old.xlsx").write_bytes(b"old")
    original = {path.name: path.read_bytes() for path in target.iterdir()}
    real_replace = os.replace

    def fail_staged_replace(source: str | Path, destination: str | Path) -> None:
        if Path(destination) == target and Path(source).name == target.name:
            raise OSError("injected replacement failure")
        real_replace(source, destination)

    monkeypatch.setattr("tools.admit_official_archive.os.replace", fail_staged_replace)

    with pytest.raises(ArchiveAdmissionError) as caught:
        admit_archive(sealed_archive_fixture.archive, target, expected=sealed_archive_fixture.spec)

    assert caught.value.code == "target_replace"
    assert {path.name: path.read_bytes() for path in target.iterdir()} == original


def test_admit_archive_stages_the_payload_validated_before_archive_path_mutates(
    sealed_archive_fixture: SealedArchiveFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "data"
    validated_payload = ZipFile(sealed_archive_fixture.archive).read(EXPECTED_MEMBERS[0])
    calls = 0

    def mutate_archive_after_validation(path: Path) -> tuple[str, ...]:
        nonlocal calls
        sheets = list_sheet_names(path)
        calls += 1
        if calls == len(EXPECTED_MEMBERS):
            _write_archive(
                sealed_archive_fixture.archive,
                dict.fromkeys(EXPECTED_MEMBERS, b"unverified"),
            )
        return sheets

    monkeypatch.setattr(
        "tools.admit_official_archive.list_sheet_names", mutate_archive_after_validation
    )

    admit_archive(sealed_archive_fixture.archive, target, expected=sealed_archive_fixture.spec)

    assert (target / EXPECTED_MEMBERS[0]).read_bytes() == validated_payload


@pytest.mark.parametrize("mutation", ["wrong_hash", "missing", "duplicate", "traversal", "extra"])
def test_archive_admission_fails_closed(tmp_path: Path, mutation: str) -> None:
    archive, expected, error_code = build_archive_fixture(tmp_path, mutation=mutation)

    with pytest.raises(ArchiveAdmissionError) as caught:
        inspect_archive(archive, expected=expected)

    assert caught.value.code == error_code
