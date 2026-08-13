"""Secure bounded-memory streaming for manifest-verified XLSX sources."""

import re
from collections.abc import Iterator
from pathlib import PurePosixPath
from typing import Final
from urllib.parse import unquote, urlsplit
from zipfile import BadZipFile, ZipFile

from lxml import etree  # type: ignore[import-untyped]

from finproof.core.errors import SourceContractError, SourceErrorCode
from finproof.data.source_manifest import VerifiedSourceFile
from finproof.domain.source import SourceCell, SourceRow

MAIN_NS: Final = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS: Final = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PACKAGE_REL_NS: Final = "{http://schemas.openxmlformats.org/package/2006/relationships}"

_CELL_REFERENCE = re.compile(r"^([A-Z]+)([1-9][0-9]*)$")
_WORKBOOK_MEMBER: Final = "xl/workbook.xml"
_WORKBOOK_RELS_MEMBER: Final = "xl/_rels/workbook.xml.rels"
_SHARED_STRINGS_MEMBER: Final = "xl/sharedStrings.xml"


def _error(source: VerifiedSourceFile, code: SourceErrorCode, message: str) -> SourceContractError:
    return SourceContractError(
        code,
        message,
        source_file=source.manifest_relative_path,
        table_id=source.table_id,
    )


def _xml_parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        recover=False,
        huge_tree=False,
    )


def _sheet_target(archive: ZipFile, source: VerifiedSourceFile) -> str:
    with archive.open(_WORKBOOK_MEMBER) as workbook_stream:
        workbook = etree.parse(workbook_stream, parser=_xml_parser())
    with archive.open(_WORKBOOK_RELS_MEMBER) as relationship_stream:
        relationships = etree.parse(relationship_stream, parser=_xml_parser())

    relationship_targets: dict[str, tuple[str, str | None]] = {}
    for relationship in relationships.findall(f".//{PACKAGE_REL_NS}Relationship"):
        relationship_id = relationship.get("Id")
        target = relationship.get("Target")
        if not relationship_id or target is None or relationship_id in relationship_targets:
            raise ValueError("invalid workbook relationship")
        relationship_targets[relationship_id] = (target, relationship.get("TargetMode"))

    selected_sheet = None
    for sheet in workbook.findall(f".//{MAIN_NS}sheet"):
        if sheet.get("name") == source.sheet_name:
            selected_sheet = sheet
            break
    if selected_sheet is None:
        raise _error(
            source,
            SourceErrorCode.MISSING_SHEET,
            "declared worksheet is missing from the verified workbook",
        )

    relationship_id = selected_sheet.get(f"{REL_NS}id")
    if not relationship_id or relationship_id not in relationship_targets:
        raise ValueError("worksheet relationship is invalid")

    target, target_mode = relationship_targets[relationship_id]
    if target_mode not in (None, "Internal"):
        raise ValueError("external worksheet relationships are not supported")
    return _canonical_zip_target(target)


def _canonical_zip_target(target: str) -> str:
    """Resolve an internal workbook relationship only within the XLSX package."""
    if "\\" in target or "\x00" in target:
        raise ValueError("worksheet relationship target is not a package path")
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("worksheet relationship target must be an internal package path")

    decoded_path = unquote(parsed.path, errors="strict")
    package_absolute = decoded_path.startswith("/")
    raw_parts = decoded_path.split("/")
    if package_absolute:
        raw_parts = raw_parts[1:]
    if not raw_parts or any(part in {"", ".", ".."} for part in raw_parts):
        raise ValueError("worksheet relationship target is not canonical")

    target_path = PurePosixPath(*raw_parts)
    if package_absolute or target_path.parts[:1] == ("xl",):
        normalized = target_path
    else:
        normalized = PurePosixPath("xl") / target_path
    if normalized.parts[:1] != ("xl",) or len(normalized.parts) < 2:
        raise ValueError("worksheet relationship target is outside xl")
    return normalized.as_posix()


def _shared_strings(archive: ZipFile) -> tuple[str, ...]:
    if _SHARED_STRINGS_MEMBER not in archive.namelist():
        return ()

    strings: list[str] = []
    with archive.open(_SHARED_STRINGS_MEMBER) as stream:
        context = etree.iterparse(
            stream,
            events=("end",),
            tag=f"{MAIN_NS}si",
            resolve_entities=False,
            no_network=True,
            recover=False,
            huge_tree=False,
        )
        for _, element in context:
            strings.append("".join(node.text or "" for node in element.iter(f"{MAIN_NS}t")))
            element.clear()
            parent = element.getparent()
            if parent is not None:
                while element.getprevious() is not None:
                    del parent[0]
    return tuple(strings)


def _column_number(cell_reference: str, row_number: int) -> int:
    match = _CELL_REFERENCE.fullmatch(cell_reference)
    if match is None or int(match.group(2)) != row_number:
        raise ValueError("invalid cell reference")
    number = 0
    for character in match.group(1):
        number = number * 26 + ord(character) - ord("A") + 1
    return number


def _column_letter(number: int) -> str:
    letters: list[str] = []
    remaining = number
    while remaining:
        remaining, remainder = divmod(remaining - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def _cell_raw_value(cell: etree._Element, shared_strings: tuple[str, ...]) -> str:
    if cell.find(f".//{MAIN_NS}f") is not None:
        raise RuntimeError("formula")

    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        inline = cell.find(f"{MAIN_NS}is")
        if inline is None:
            return ""
        return "".join(node.text or "" for node in inline.iter(f"{MAIN_NS}t"))

    value_node = cell.find(f"{MAIN_NS}v")
    value = "" if value_node is None or value_node.text is None else value_node.text
    if cell_type == "s":
        return shared_strings[int(value)]
    return value


def _row_number(element: etree._Element) -> int:
    raw_number = element.get("r")
    if raw_number is None:
        raise ValueError("worksheet row has no number")
    row_number = int(raw_number)
    if row_number <= 0:
        raise ValueError("worksheet row number must be positive")
    return row_number


def _row_values(
    element: etree._Element,
    row_number: int,
    shared_strings: tuple[str, ...],
    source: VerifiedSourceFile,
) -> dict[int, str]:
    cells: dict[int, str] = {}
    for cell in element.findall(f"{MAIN_NS}c"):
        if cell.find(f".//{MAIN_NS}f") is not None:
            raise _error(
                source,
                SourceErrorCode.UNSUPPORTED_FORMULA,
                "formulas are not supported in official source workbooks",
            )
        reference = cell.get("r")
        if reference is None:
            raise ValueError("worksheet cell has no reference")
        column_number = _column_number(reference, row_number)
        if column_number in cells:
            raise _error(
                source,
                SourceErrorCode.DUPLICATE_CELL,
                "worksheet row contains a duplicate cell address",
            )
        cells[column_number] = _cell_raw_value(cell, shared_strings)
    return cells


def _validate_header(values: dict[int, str], row_number: int, source: VerifiedSourceFile) -> None:
    if row_number != 1:
        raise ValueError("header row must be worksheet row 1")
    width = max(max(values, default=0), source.expected_columns)
    headers = tuple(values.get(column, "") for column in range(1, width + 1))
    if any(not header for header in headers):
        raise _error(
            source,
            SourceErrorCode.BLANK_HEADER,
            "worksheet headers must not be blank",
        )
    if len(set(headers)) != len(headers):
        raise _error(
            source,
            SourceErrorCode.DUPLICATE_HEADER,
            "worksheet headers must be unique",
        )
    if headers != source.expected_headers:
        raise _error(
            source,
            SourceErrorCode.HEADER_MISMATCH,
            "worksheet headers do not match the declared ordered headers",
        )


def _source_row(values: dict[int, str], row_number: int, source: VerifiedSourceFile) -> SourceRow:
    if any(
        value != ""
        for column_number, value in values.items()
        if column_number > source.expected_columns
    ):
        raise _error(
            source,
            SourceErrorCode.ROW_WIDER_THAN_HEADER,
            "worksheet row contains data beyond the declared header width",
        )
    payload = tuple(
        values.get(column_number, "") for column_number in range(1, source.expected_columns + 1)
    )
    cells = tuple(
        SourceCell(
            column_name=column_name,
            excel_column_number=column_number,
            excel_column_letter=_column_letter(column_number),
            raw_value=payload[column_number - 1],
            applicable_date=None,
        )
        for column_number, column_name in enumerate(source.expected_headers, start=1)
    )
    return SourceRow(
        source_table=source.table_id,
        source_file=source.manifest_relative_path,
        source_sheet=source.sheet_name,
        source_row_number=row_number,
        source_checksum=source.sha256,
        source_snapshot_date=source.snapshot_date,
        raw_payload=payload,
        cells=cells,
    )


def iter_xlsx_rows(source: VerifiedSourceFile) -> Iterator[SourceRow]:
    """Yield exact source rows from one fully verified XLSX workbook."""
    try:
        with ZipFile(source.verified_absolute_path) as archive:
            sheet_target = _sheet_target(archive, source)
            shared_strings = _shared_strings(archive)
            with archive.open(sheet_target) as worksheet_stream:
                context = etree.iterparse(
                    worksheet_stream,
                    events=("end",),
                    tag=f"{MAIN_NS}row",
                    resolve_entities=False,
                    no_network=True,
                    recover=False,
                    huge_tree=False,
                )
                header_seen = False
                data_row_count = 0
                for _, element in context:
                    row_number = _row_number(element)
                    values = _row_values(element, row_number, shared_strings, source)
                    if not header_seen:
                        _validate_header(values, row_number, source)
                        header_seen = True
                    else:
                        data_row_count += 1
                        yield _source_row(values, row_number, source)
                    element.clear()
                    parent = element.getparent()
                    if parent is not None:
                        while element.getprevious() is not None:
                            del parent[0]

                if not header_seen:
                    raise _error(
                        source,
                        SourceErrorCode.HEADER_MISMATCH,
                        "worksheet does not contain a header row",
                    )
                if data_row_count != source.expected_rows:
                    raise _error(
                        source,
                        SourceErrorCode.ROW_COUNT_MISMATCH,
                        "worksheet data-row count does not match the declared count",
                    )
    except SourceContractError:
        raise
    except (
        BadZipFile,
        IndexError,
        KeyError,
        OSError,
        OverflowError,
        ValueError,
        etree.XMLSyntaxError,
    ):
        raise _error(
            source,
            SourceErrorCode.MALFORMED_WORKBOOK,
            "verified source is not a structurally valid supported XLSX workbook",
        ) from None
