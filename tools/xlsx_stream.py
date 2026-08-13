#!/usr/bin/env python3
"""Small stdlib-only streaming XLSX reader used by handoff verification tools.

This module intentionally does not depend on production FinProof code. It lets a
fresh checkout verify the official workbooks before the project environment is
fully bootstrapped.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Final
from xml.etree import ElementTree as ET
from zipfile import ZipFile

_MAIN: Final = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_DOC_REL: Final = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


@dataclass(frozen=True, slots=True)
class WorkbookRow:
    excel_row_number: int
    values: tuple[str, ...]


def _column_index(cell_reference: str) -> int:
    match = re.match(r"[A-Z]+", cell_reference)
    if match is None:
        raise ValueError(f"Invalid Excel cell reference: {cell_reference!r}")
    value = 0
    for character in match.group(0):
        value = value * 26 + ord(character) - ord("A") + 1
    return value - 1


def _sheet_target(archive: ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    target_by_id = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}

    for sheet in workbook.findall(f".//{_MAIN}sheet"):
        if sheet.attrib.get("name") != sheet_name:
            continue
        relationship_id = sheet.attrib[f"{_DOC_REL}id"]
        target = target_by_id[relationship_id]
        if target.startswith("/"):
            return target.lstrip("/")
        if target.startswith("xl/"):
            return target
        return f"xl/{target.lstrip('/')}"
    raise KeyError(f"Sheet {sheet_name!r} does not exist")


def list_sheet_names(path: Path) -> tuple[str, ...]:
    with ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    return tuple(sheet.attrib["name"] for sheet in workbook.findall(f".//{_MAIN}sheet"))


def _shared_strings(archive: ZipFile) -> tuple[str, ...]:
    member = "xl/sharedStrings.xml"
    if member not in archive.namelist():
        return ()

    values: list[str] = []
    with archive.open(member) as stream:
        for _, element in ET.iterparse(stream, events=("end",)):
            if element.tag == f"{_MAIN}si":
                values.append("".join(node.text or "" for node in element.iter(f"{_MAIN}t")))
                element.clear()
    return tuple(values)


def _cell_value(cell: ET.Element, shared_strings: tuple[str, ...]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        inline = cell.find(f"{_MAIN}is")
        if inline is None:
            return ""
        return "".join(node.text or "" for node in inline.iter(f"{_MAIN}t"))

    value_node = cell.find(f"{_MAIN}v")
    if value_node is None or value_node.text is None:
        return ""
    if cell_type == "s":
        return shared_strings[int(value_node.text)]
    if cell_type == "b":
        return "1" if value_node.text == "1" else "0"
    return value_node.text


def iter_sheet_rows(path: Path, sheet_name: str) -> Iterator[WorkbookRow]:
    """Yield every populated worksheet row while bounding worksheet memory."""

    with ZipFile(path) as archive:
        target = _sheet_target(archive, sheet_name)
        shared_strings = _shared_strings(archive)
        with archive.open(target) as stream:
            for _, element in ET.iterparse(stream, events=("end",)):
                if element.tag != f"{_MAIN}row":
                    continue
                cells: dict[int, str] = {}
                for cell in element.findall(f"{_MAIN}c"):
                    reference = cell.attrib.get("r")
                    if reference is None:
                        raise ValueError(f"Cell without reference in {path.name}")
                    cells[_column_index(reference)] = _cell_value(cell, shared_strings)
                width = max(cells, default=-1) + 1
                row_number = int(element.attrib.get("r", "0"))
                yield WorkbookRow(row_number, tuple(cells.get(index, "") for index in range(width)))
                element.clear()


def iter_table_dicts(path: Path, sheet_name: str = "datarows") -> Iterator[tuple[int, dict[str, str]]]:
    rows = iter_sheet_rows(path, sheet_name)
    try:
        header_row = next(rows)
    except StopIteration as exc:
        raise ValueError(f"Workbook {path.name} has no rows") from exc

    headers = tuple(value.strip() for value in header_row.values)
    if not headers or any(not header for header in headers):
        raise ValueError(f"Workbook {path.name} has blank header cells")
    if len(headers) != len(set(headers)):
        raise ValueError(f"Workbook {path.name} has duplicate headers")

    for row in rows:
        if len(row.values) > len(headers):
            extra = row.values[len(headers) :]
            if any(value != "" for value in extra):
                raise ValueError(f"Row {row.excel_row_number} is wider than the header in {path.name}")
        padded = row.values + ("",) * max(0, len(headers) - len(row.values))
        yield row.excel_row_number, dict(zip(headers, padded, strict=True))
