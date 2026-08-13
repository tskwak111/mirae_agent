"""Contracts for secure streaming of verified XLSX source rows."""

from collections.abc import Callable
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from finproof.core.errors import SourceContractError, SourceErrorCode
from finproof.data.xlsx_stream import _canonical_zip_target, iter_xlsx_rows
from tests.helpers.xlsx import (
    MAIN_URI,
    PACKAGE_REL_URI,
    REL_URI,
    verified_fixture_source,
    write_xlsx,
)


def _replace_zip_member(path: Path, member: str, payload: bytes) -> None:
    with ZipFile(path) as archive:
        members = {
            info.filename: archive.read(info.filename)
            for info in archive.infolist()
            if info.filename != member
        }
    members[member] = payload
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def _remove_zip_member(path: Path, member: str) -> None:
    with ZipFile(path) as archive:
        members = {
            info.filename: archive.read(info.filename)
            for info in archive.infolist()
            if info.filename != member
        }
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def _worksheet_xml(*rows: str) -> bytes:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{MAIN_URI}">'
        f"<sheetData>{''.join(rows)}</sheetData></worksheet>"
    ).encode()


def _patch_zip_member_flags(
    path: Path,
    member: str,
    *,
    encrypted: bool = False,
    compression_method: int | None = None,
) -> None:
    payload = bytearray(path.read_bytes())
    member_bytes = member.encode()
    matches = 0
    for signature, flag_offset, method_offset, name_length_offset, name_offset in (
        (b"PK\x03\x04", 6, 8, 26, 30),
        (b"PK\x01\x02", 8, 10, 28, 46),
    ):
        offset = 0
        while (header_offset := payload.find(signature, offset)) >= 0:
            name_length = int.from_bytes(
                payload[
                    header_offset + name_length_offset : header_offset + name_length_offset + 2
                ],
                "little",
            )
            name_start = header_offset + name_offset
            if payload[name_start : name_start + name_length] == member_bytes:
                matches += 1
                if encrypted:
                    flags = int.from_bytes(
                        payload[header_offset + flag_offset : header_offset + flag_offset + 2],
                        "little",
                    )
                    payload[header_offset + flag_offset : header_offset + flag_offset + 2] = (
                        flags | 1
                    ).to_bytes(2, "little")
                if compression_method is not None:
                    payload[header_offset + method_offset : header_offset + method_offset + 2] = (
                        compression_method.to_bytes(2, "little")
                    )
            offset = header_offset + len(signature)
    if matches != 2:
        raise AssertionError("test ZIP member must have one local and one central header")
    path.write_bytes(payload)


def test_reader_preserves_omitted_cells_and_exact_raw_lineage(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(
        workbook,
        rows=(("ID", "PADDED", "NULL_TEXT", "TRAILING"), ("00123", None, "NULL", None)),
    )
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID", "PADDED", "NULL_TEXT", "TRAILING"),
        expected_rows=1,
    )

    row = next(iter_xlsx_rows(verified))

    assert row.source_row_number == 2
    assert row.raw_payload == ("00123", "", "NULL", "")
    assert tuple(cell.excel_column_letter for cell in row.cells) == ("A", "B", "C", "D")
    assert all(cell.applicable_date is None for cell in row.cells)
    assert row.source_checksum == verified.sha256


def test_reader_rejects_entity_bearing_cell_text(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("placeholder",)))
    worksheet = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE worksheet [<!ENTITY hidden "must-not-be-expanded">]>
<worksheet xmlns="{MAIN_URI}"><sheetData>
  <row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c></row>
  <row r="2"><c r="A2" t="inlineStr"><is><t>&hidden;</t></is></c></row>
</sheetData></worksheet>'''.encode()
    _replace_zip_member(workbook, "xl/worksheets/sheet1.xml", worksheet)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


@pytest.mark.parametrize(
    "xml_part",
    ["workbook", "relationships", "worksheet", "shared-strings"],
)
def test_reader_rejects_dtd_declaration_before_parsing_every_xml_part(
    tmp_path: Path,
    xml_part: str,
) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("1",)))
    if xml_part == "workbook":
        payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE workbook [<!ENTITY unused "private-workbook-metadata">]>
<workbook xmlns="{MAIN_URI}" xmlns:r="{REL_URI}">
  <sheets><sheet name="datarows" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''.encode()
        _replace_zip_member(workbook, "xl/workbook.xml", payload)
    elif xml_part == "relationships":
        payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE Relationships [<!ENTITY unused "private-relationship-metadata">]>
<Relationships xmlns="{PACKAGE_REL_URI}">
  <Relationship Id="rId1" Type="{REL_URI}/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>'''.encode()
        _replace_zip_member(workbook, "xl/_rels/workbook.xml.rels", payload)
    elif xml_part == "worksheet":
        payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE worksheet [<!ENTITY unused "private-worksheet-metadata">]>
<worksheet xmlns="{MAIN_URI}"><sheetData>
  <row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c></row>
  <row r="2"><c r="A2" t="inlineStr"><is><t>1</t></is></c></row>
</sheetData></worksheet>'''.encode()
        _replace_zip_member(workbook, "xl/worksheets/sheet1.xml", payload)
    else:
        payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE sst [<!ENTITY unused "private-shared-metadata">]>
<sst xmlns="{MAIN_URI}"><si><t>unused</t></si></sst>'''.encode()
        _replace_zip_member(workbook, "xl/sharedStrings.xml", payload)

    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK
    assert "private" not in str(raised.value)


@pytest.mark.parametrize("metadata_part", ["workbook", "relationships"])
def test_reader_rejects_entity_backed_workbook_metadata_attributes(
    tmp_path: Path,
    metadata_part: str,
) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("1",)))
    if metadata_part == "workbook":
        payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE workbook [<!ENTITY declaredSheet "datarows">]>
<workbook xmlns="{MAIN_URI}" xmlns:r="{REL_URI}">
  <sheets><sheet name="&declaredSheet;" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''.encode()
        _replace_zip_member(workbook, "xl/workbook.xml", payload)
    else:
        payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE Relationships [<!ENTITY worksheetTarget "worksheets/sheet1.xml">]>
<Relationships xmlns="{PACKAGE_REL_URI}">
  <Relationship Id="rId1" Type="{REL_URI}/worksheet" Target="&worksheetTarget;"/>
</Relationships>'''.encode()
        _replace_zip_member(workbook, "xl/_rels/workbook.xml.rels", payload)

    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


@pytest.mark.parametrize(
    "workbook_body",
    [
        '<sheet name="datarows" sheetId="1" r:id="rId1"/>',
        ('<sheets><sheet name="datarows" sheetId="1" r:id="rId1"/></sheets><sheets/>'),
        (
            "<bookViews><sheets>"
            '<sheet name="datarows" sheetId="1" r:id="rId1"/>'
            "</sheets></bookViews>"
        ),
        (
            "<sheets>"
            '<sheet name="datarows" sheetId="1" r:id="rId1"/>'
            '<sheet name="datarows" sheetId="2" r:id="rId1"/>'
            "</sheets>"
        ),
    ],
    ids=["missing-container", "duplicate-container", "nested-container", "duplicate-sheet"],
)
def test_reader_rejects_ambiguous_workbook_sheet_metadata(
    tmp_path: Path,
    workbook_body: str,
) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("1",)))
    payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="{MAIN_URI}" xmlns:r="{REL_URI}">{workbook_body}</workbook>'''.encode()
    _replace_zip_member(workbook, "xl/workbook.xml", payload)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


@pytest.mark.parametrize("metadata_part", ["workbook", "relationships", "worksheet", "shared"])
def test_reader_rejects_unexpected_xml_part_roots(
    tmp_path: Path,
    metadata_part: str,
) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("1",)))
    if metadata_part == "workbook":
        payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<wrapper xmlns="{MAIN_URI}" xmlns:r="{REL_URI}">
  <sheets><sheet name="datarows" sheetId="1" r:id="rId1"/></sheets>
</wrapper>'''.encode()
        _replace_zip_member(workbook, "xl/workbook.xml", payload)
    elif metadata_part == "relationships":
        payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<wrapper xmlns="{PACKAGE_REL_URI}">
  <Relationship Id="rId1" Type="{REL_URI}/worksheet" Target="worksheets/sheet1.xml"/>
</wrapper>'''.encode()
        _replace_zip_member(workbook, "xl/_rels/workbook.xml.rels", payload)
    elif metadata_part == "worksheet":
        payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<wrapper><worksheet xmlns="{MAIN_URI}"><sheetData>
  <row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c></row>
  <row r="2"><c r="A2" t="inlineStr"><is><t>1</t></is></c></row>
</sheetData></worksheet></wrapper>'''.encode()
        _replace_zip_member(workbook, "xl/worksheets/sheet1.xml", payload)
    else:
        worksheet = f'''<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="{MAIN_URI}"><sheetData>
  <row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c></row>
  <row r="2"><c r="A2" t="s"><v>0</v></c></row>
</sheetData></worksheet>'''.encode()
        payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<wrapper><sst xmlns="{MAIN_URI}"><si><t>1</t></si></sst></wrapper>'''.encode()
        _replace_zip_member(workbook, "xl/worksheets/sheet1.xml", worksheet)
        _replace_zip_member(workbook, "xl/sharedStrings.xml", payload)

    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


def test_reader_rejects_unexpected_worksheet_root_before_first_value(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("1",)))
    payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<wrapper><worksheet xmlns="{MAIN_URI}"><sheetData>
  <row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c></row>
  <row r="2"><c r="A2" t="inlineStr"><is><t>1</t></is></c></row>
</sheetData></worksheet></wrapper>'''.encode()
    _replace_zip_member(workbook, "xl/worksheets/sheet1.xml", payload)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        next(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


def test_reader_rejects_utf16_dtd_before_first_worksheet_value(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("1",)))
    xml = f'''<?xml version="1.0" encoding="UTF-16"?>
<!DOCTYPE worksheet [<!ENTITY unused "private-utf16-metadata">]>
<worksheet xmlns="{MAIN_URI}"><sheetData>
  <row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c></row>
  <row r="2"><c r="A2" t="inlineStr"><is><t>1</t></is></c></row>
</sheetData></worksheet>'''.encode("utf-16")
    _replace_zip_member(workbook, "xl/worksheets/sheet1.xml", xml)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        next(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK
    assert "private" not in str(raised.value)


@pytest.mark.parametrize("duplicate_sheet_data", [False, True], ids=["missing", "duplicate"])
def test_reader_requires_exactly_one_sheet_data_parent(
    tmp_path: Path, duplicate_sheet_data: bool
) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("placeholder",)))
    rows = (
        '<row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c></row>'
        '<row r="2"><c r="A2" t="inlineStr"><is><t>rogue</t></is></c></row>'
    )
    body = f"<sheetData>{rows}</sheetData><sheetData/>" if duplicate_sheet_data else rows
    worksheet = (
        f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{MAIN_URI}">{body}</worksheet>'
    ).encode()
    _replace_zip_member(workbook, "xl/worksheets/sheet1.xml", worksheet)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


def test_reader_rejects_nested_sheet_data_parent(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("placeholder",)))
    rows = (
        '<row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c></row>'
        '<row r="2"><c r="A2" t="inlineStr"><is><t>nested</t></is></c></row>'
    )
    worksheet = (
        f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{MAIN_URI}">'
        f"<sheetData><sheetData>{rows}</sheetData></sheetData></worksheet>"
    ).encode()
    _replace_zip_member(workbook, "xl/worksheets/sheet1.xml", worksheet)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


def test_reader_rejects_missing_declared_sheet(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, sheet_name="other", rows=(("ID",), ("1",)))
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MISSING_SHEET


def test_reader_rejects_exact_ordered_header_mismatch(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("SECOND", "FIRST"), ("2", "1")))
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("FIRST", "SECOND"),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.HEADER_MISMATCH


def test_reader_rejects_blank_header(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID", ""), ("1", "value")))
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID", "VALUE"),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.BLANK_HEADER


def test_reader_rejects_duplicate_header(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID", "ID"), ("1", "2")))
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID", "VALUE"),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.DUPLICATE_HEADER


def test_reader_rejects_nonblank_cell_beyond_header(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID", "VALUE"), ("1", "2", "unexpected")))
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID", "VALUE"),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.ROW_WIDER_THAN_HEADER


def test_reader_ignores_explicit_blank_cell_beyond_header(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID", "VALUE"), ("1", "2", "")))
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID", "VALUE"),
        expected_rows=1,
    )

    rows = list(iter_xlsx_rows(verified))

    assert rows[0].raw_payload == ("1", "2")


def test_reader_rejects_duplicate_cell_address(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(
        workbook,
        rows=(("ID",), ("1",)),
        duplicate_cells=frozenset({"A2"}),
    )
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.DUPLICATE_CELL


@pytest.mark.parametrize("formula_cell", ["A1", "A2"], ids=["header", "data"])
def test_reader_rejects_formula_in_header_or_data(tmp_path: Path, formula_cell: str) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(
        workbook,
        rows=(("ID",), ("1",)),
        formulas=frozenset({formula_cell}),
    )
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.UNSUPPORTED_FORMULA


def _break_zip(path: Path) -> None:
    path.write_bytes(b"not an XLSX ZIP")


def _break_workbook_xml(path: Path) -> None:
    _replace_zip_member(path, "xl/workbook.xml", b"<workbook")


def _remove_workbook_relationships(path: Path) -> None:
    _remove_zip_member(path, "xl/_rels/workbook.xml.rels")


def _set_relationship_target(
    path: Path,
    target: str,
    *,
    target_mode: str | None = None,
    relationship_type: str = f"{REL_URI}/worksheet",
) -> None:
    target_mode_xml = "" if target_mode is None else f' TargetMode="{target_mode}"'
    relationships = f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="{PACKAGE_REL_URI}">
  <Relationship Id="rId1" Type="{relationship_type}" Target="{target}"{target_mode_xml}/>
</Relationships>""".encode()
    _replace_zip_member(path, "xl/_rels/workbook.xml.rels", relationships)


def _escape_relationship_target(path: Path) -> None:
    _set_relationship_target(path, "../escape.xml")


def test_reader_accepts_package_absolute_internal_relationship_target(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("1",)))
    _set_relationship_target(workbook, "/xl/worksheets/sheet1.xml")
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    rows = list(iter_xlsx_rows(verified))

    assert rows[0].raw_payload == ("1",)


@pytest.mark.parametrize(
    "target",
    [
        "worksheets%5Csheet1.xml",
        "worksheets/sheet%00one.xml",
        "worksheets/sheet%09one.xml",
        "worksheets/sheet%0Aone.xml",
        "worksheets/\tsheet1.xml",
        "worksheets/\nsheet1.xml",
        "worksheets/\rsheet1.xml",
        "worksheets/\x1fsheet1.xml",
        "worksheets/\x7fsheet1.xml",
        "https%3A//example.invalid/sheet.xml",
        "worksheets/%73heet1.xml",
    ],
    ids=[
        "encoded-backslash",
        "encoded-nul",
        "encoded-tab",
        "encoded-newline",
        "raw-tab",
        "raw-newline",
        "raw-carriage-return",
        "raw-unit-separator",
        "raw-delete",
        "encoded-uri-scheme",
        "noncanonical-unreserved-encoding",
    ],
)
def test_relationship_target_canonicalizer_rejects_raw_decoded_and_nonroundtrip_forms(
    target: str,
) -> None:
    with pytest.raises(ValueError, match="worksheet relationship target"):
        _canonical_zip_target(target)


@pytest.mark.parametrize("raw_control", ["\t", "\n"], ids=["tab", "newline"])
def test_reader_rejects_raw_target_controls_before_xml_attribute_normalization(
    tmp_path: Path,
    raw_control: str,
) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("1",)))
    with ZipFile(workbook) as archive:
        worksheet = archive.read("xl/worksheets/sheet1.xml")
    _replace_zip_member(workbook, "xl/worksheets/ sheet1.xml", worksheet)
    _set_relationship_target(workbook, f"worksheets/{raw_control}sheet1.xml")
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


@pytest.mark.parametrize(
    ("target", "zip_member"),
    [
        ("worksheets%5Csheet1.xml", "xl/worksheets\\sheet1.xml"),
        ("worksheets/sheet%09one.xml", "xl/worksheets/sheet\tone.xml"),
        ("worksheets/sheet%0Aone.xml", "xl/worksheets/sheet\none.xml"),
    ],
    ids=["encoded-backslash", "encoded-tab", "encoded-newline"],
)
def test_reader_rejects_post_decoding_target_bypass_even_if_zip_member_exists(
    tmp_path: Path,
    target: str,
    zip_member: str,
) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("1",)))
    with ZipFile(workbook) as archive:
        worksheet = archive.read("xl/worksheets/sheet1.xml")
    _replace_zip_member(workbook, zip_member, worksheet)
    _set_relationship_target(workbook, target)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


def test_reader_rejects_external_relationship_target_mode(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("1",)))
    _set_relationship_target(
        workbook,
        "worksheets/sheet1.xml",
        target_mode="External",
    )
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


def test_reader_rejects_uri_relationship_target_even_if_zip_member_exists(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("1",)))
    with ZipFile(workbook) as archive:
        worksheet = archive.read("xl/worksheets/sheet1.xml")
    _set_relationship_target(workbook, "https://example.invalid/sheet.xml")
    _replace_zip_member(workbook, "xl/https:/example.invalid/sheet.xml", worksheet)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


def test_reader_rejects_nonworksheet_relationship_type(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("1",)))
    _set_relationship_target(
        workbook,
        "worksheets/sheet1.xml",
        relationship_type=f"{REL_URI}/styles",
    )
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


@pytest.mark.parametrize(
    "relationships_body",
    [
        (
            "<group>"
            f'<Relationship Id="rId1" Type="{REL_URI}/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            "</group>"
        ),
        (
            f'<Relationship Id="rId1" Type="{REL_URI}/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            f'<Relationship Id="rId1" Type="{REL_URI}/worksheet" '
            'Target="worksheets/other.xml"/>'
        ),
        "",
    ],
    ids=["nested", "duplicate-id", "missing"],
)
def test_reader_rejects_nested_duplicate_or_missing_workbook_relationships(
    tmp_path: Path,
    relationships_body: str,
) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("1",)))
    payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="{PACKAGE_REL_URI}">{relationships_body}</Relationships>'''.encode()
    _replace_zip_member(workbook, "xl/_rels/workbook.xml.rels", payload)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


def test_reader_resolves_relative_relationship_against_workbook_directory(
    tmp_path: Path,
) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("outer",)))
    nested_worksheet = _worksheet_xml(
        '<row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c></row>',
        '<row r="2"><c r="A2" t="inlineStr"><is><t>nested</t></is></c></row>',
    )
    _replace_zip_member(workbook, "xl/xl/worksheets/sheet1.xml", nested_worksheet)
    _set_relationship_target(workbook, "xl/worksheets/sheet1.xml")
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    rows = list(iter_xlsx_rows(verified))

    assert rows[0].raw_payload == ("nested",)


@pytest.mark.parametrize(
    "corrupt",
    [
        _break_zip,
        _break_workbook_xml,
        _remove_workbook_relationships,
        _escape_relationship_target,
    ],
    ids=["zip", "xml", "missing-relationships", "escaping-relationship"],
)
def test_reader_converts_malformed_workbook_structure_to_safe_error(
    tmp_path: Path, corrupt: Callable[[Path], None]
) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("1",)))
    corrupt(workbook)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK
    assert str(tmp_path) not in str(raised.value)


def test_reader_rejects_duplicate_zip_member_names(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("secret duplicate payload",)))
    with ZipFile(workbook) as archive:
        worksheet = archive.read("xl/worksheets/sheet1.xml")
    with (
        pytest.warns(UserWarning, match="Duplicate name"),
        ZipFile(workbook, "a", compression=ZIP_DEFLATED) as archive,
    ):
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK
    assert str(tmp_path) not in str(raised.value)
    assert "secret duplicate payload" not in str(raised.value)


@pytest.mark.parametrize(
    ("encrypted", "compression_method"),
    [(True, None), (False, 99)],
    ids=["encrypted", "unsupported-compression"],
)
def test_reader_converts_unsupported_zip_member_read_failures(
    tmp_path: Path, encrypted: bool, compression_method: int | None
) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("secret member payload",)))
    _patch_zip_member_flags(
        workbook,
        "xl/worksheets/sheet1.xml",
        encrypted=encrypted,
        compression_method=compression_method,
    )
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK
    assert str(tmp_path) not in str(raised.value)
    assert "secret member payload" not in str(raised.value)


@pytest.mark.parametrize("row_attribute", ["0", "not-a-row"])
def test_reader_rejects_invalid_row_number(tmp_path: Path, row_attribute: str) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("1",)))
    worksheet = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="{MAIN_URI}"><sheetData>
  <row r={row_attribute!r}><c r="A1" t="inlineStr"><is><t>ID</t></is></c></row>
</sheetData></worksheet>""".encode()
    _replace_zip_member(workbook, "xl/worksheets/sheet1.xml", worksheet)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=0,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


def test_reader_rejects_invalid_cell_reference(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",),))
    worksheet = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="{MAIN_URI}"><sheetData>
  <row r="1"><c r="1A" t="inlineStr"><is><t>ID</t></is></c></row>
</sheetData></worksheet>""".encode()
    _replace_zip_member(workbook, "xl/worksheets/sheet1.xml", worksheet)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=0,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


@pytest.mark.parametrize(
    ("data_row_number", "cell_reference"),
    [(2, "XFE2"), (1_048_577, "A1048577")],
    ids=["column-above-xfd", "row-above-1048576"],
)
def test_reader_rejects_cell_references_beyond_excel_bounds(
    tmp_path: Path, data_row_number: int, cell_reference: str
) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",),))
    worksheet = _worksheet_xml(
        '<row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c></row>',
        f'<row r="{data_row_number}"><c r="{cell_reference}" '
        't="inlineStr"><is><t>value</t></is></c></row>',
    )
    _replace_zip_member(workbook, "xl/worksheets/sheet1.xml", worksheet)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


def test_reader_accepts_exact_excel_row_and_column_boundaries(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",),))
    worksheet = _worksheet_xml(
        '<row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c></row>',
        '<row r="1048576"><c r="A1048576" t="inlineStr"><is><t>value</t></is></c>'
        '<c r="XFD1048576" t="inlineStr"><is><t></t></is></c></row>',
    )
    _replace_zip_member(workbook, "xl/worksheets/sheet1.xml", worksheet)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    rows = list(iter_xlsx_rows(verified))

    assert rows[0].source_row_number == 1_048_576
    assert rows[0].raw_payload == ("value",)


@pytest.mark.parametrize(
    "data_rows",
    [
        (
            '<row r="2"><c r="A2" t="inlineStr"><is><t>first</t></is></c></row>',
            '<row r="2"><c r="A2" t="inlineStr"><is><t>again</t></is></c></row>',
        ),
        (
            '<row r="3"><c r="A3" t="inlineStr"><is><t>first</t></is></c></row>',
            '<row r="2"><c r="A2" t="inlineStr"><is><t>backward</t></is></c></row>',
        ),
    ],
    ids=["repeated", "decreasing"],
)
def test_reader_rejects_nonincreasing_worksheet_row_numbers(
    tmp_path: Path, data_rows: tuple[str, str]
) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",),))
    worksheet = _worksheet_xml(
        '<row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c></row>',
        *data_rows,
    )
    _replace_zip_member(workbook, "xl/worksheets/sheet1.xml", worksheet)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=2,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


def test_reader_preserves_shared_plain_and_boolean_raw_strings(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("SHARED", "PLAIN", "BOOLEAN"),))
    worksheet = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="{MAIN_URI}"><sheetData>
  <row r="1">
    <c r="A1" t="inlineStr"><is><t>SHARED</t></is></c>
    <c r="B1" t="inlineStr"><is><t>PLAIN</t></is></c>
    <c r="C1" t="inlineStr"><is><t>BOOLEAN</t></is></c>
  </row>
  <row r="2">
    <c r="A2" t="s"><v>0</v></c>
    <c r="B2"><v>00123</v></c>
    <c r="C2" t="b"><v>1</v></c>
  </row>
</sheetData></worksheet>""".encode()
    shared_strings = f"""<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="{MAIN_URI}"><si><t xml:space="preserve"> shared </t></si></sst>""".encode()
    _replace_zip_member(workbook, "xl/worksheets/sheet1.xml", worksheet)
    _replace_zip_member(workbook, "xl/sharedStrings.xml", shared_strings)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("SHARED", "PLAIN", "BOOLEAN"),
        expected_rows=1,
    )

    rows = list(iter_xlsx_rows(verified))

    assert rows[0].raw_payload == (" shared ", "00123", "1")


def test_reader_rejects_entity_bearing_shared_string(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",),))
    worksheet = f'''<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="{MAIN_URI}"><sheetData>
  <row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c></row>
  <row r="2"><c r="A2" t="s"><v>0</v></c></row>
</sheetData></worksheet>'''.encode()
    shared_strings = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE sst [<!ENTITY hidden "must-not-be-expanded">]>
<sst xmlns="{MAIN_URI}"><si><t>&hidden;</t></si></sst>'''.encode()
    _replace_zip_member(workbook, "xl/worksheets/sheet1.xml", worksheet)
    _replace_zip_member(workbook, "xl/sharedStrings.xml", shared_strings)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


def test_reader_rejects_invalid_shared_string_index(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",),))
    worksheet = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="{MAIN_URI}"><sheetData>
  <row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c></row>
  <row r="2"><c r="A2" t="s"><v>99</v></c></row>
</sheetData></worksheet>""".encode()
    _replace_zip_member(workbook, "xl/worksheets/sheet1.xml", worksheet)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


def test_reader_rejects_negative_shared_string_index(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",),))
    worksheet = _worksheet_xml(
        '<row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c></row>',
        '<row r="2"><c r="A2" t="s"><v>-1</v></c></row>',
    )
    shared_strings = f"""<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="{MAIN_URI}"><si><t>wrong value</t></si></sst>""".encode()
    _replace_zip_member(workbook, "xl/worksheets/sheet1.xml", worksheet)
    _replace_zip_member(workbook, "xl/sharedStrings.xml", shared_strings)
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=1,
    )

    with pytest.raises(SourceContractError) as raised:
        list(iter_xlsx_rows(verified))

    assert raised.value.code is SourceErrorCode.MALFORMED_WORKBOOK


def test_reader_checks_row_count_only_after_normal_exhaustion(tmp_path: Path) -> None:
    workbook = tmp_path / "fixture.xlsx"
    write_xlsx(workbook, rows=(("ID",), ("1",)))
    verified = verified_fixture_source(
        tmp_path,
        table_id="PRBD01N001",
        workbook=workbook,
        expected_headers=("ID",),
        expected_rows=2,
    )
    rows = iter_xlsx_rows(verified)

    first = next(rows)

    assert first.raw_payload == ("1",)
    with pytest.raises(SourceContractError) as raised:
        next(rows)
    assert raised.value.code is SourceErrorCode.ROW_COUNT_MISMATCH
