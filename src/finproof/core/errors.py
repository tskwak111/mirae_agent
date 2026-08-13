"""Transport-independent FinProof errors."""

from enum import StrEnum
from pathlib import PurePosixPath


class FinProofError(Exception):
    """Base FinProof application error."""


class NormalizationContractError(FinProofError):
    """A normalizer received a row from a table outside its contract."""

    def __init__(self, expected_table: str, actual_table: str) -> None:
        self.expected_table = expected_table
        self.actual_table = actual_table
        super().__init__(
            f"normalization table mismatch: expected {expected_table}, got {actual_table}"
        )


class RatingRegistryConfigurationError(FinProofError):
    """The rating registry configuration failed its strict trust boundary."""

    def __init__(self, category: str, *, source_name: str | None = None) -> None:
        self.category = category
        self.source_name = source_name
        source_context = f" ({source_name})" if source_name is not None else ""
        super().__init__(f"rating registry configuration error: {category}{source_context}")


class RatingNotComparableError(FinProofError):
    """At least one rating operand has no registered comparison ordinal."""

    def __init__(self) -> None:
        super().__init__("rating operands are not comparable")


class SourceErrorCode(StrEnum):
    """Stable categories for fail-closed official-source contract failures."""

    MANIFEST_INVALID = "manifest_invalid"
    CATALOG_INVALID = "catalog_invalid"
    PATH_ESCAPE = "path_escape"
    FILE_MISSING = "file_missing"
    FILE_TYPE_INVALID = "file_type_invalid"
    SIZE_MISMATCH = "size_mismatch"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    SNAPSHOT_MISMATCH = "snapshot_mismatch"
    DUPLICATE_TABLE = "duplicate_table"
    MISSING_SHEET = "missing_sheet"
    COLUMN_COUNT_MISMATCH = "column_count_mismatch"
    HEADER_MISMATCH = "header_mismatch"
    BLANK_HEADER = "blank_header"
    DUPLICATE_HEADER = "duplicate_header"
    DUPLICATE_CELL = "duplicate_cell"
    ROW_WIDER_THAN_HEADER = "row_wider_than_header"
    ROW_COUNT_MISMATCH = "row_count_mismatch"
    UNSUPPORTED_FORMULA = "unsupported_formula"
    MALFORMED_WORKBOOK = "malformed_workbook"


class SourceContractError(FinProofError):
    """Official source data violated a frozen contract."""

    def __init__(
        self,
        code: SourceErrorCode,
        message: str,
        *,
        source_file: PurePosixPath | None = None,
        table_id: str | None = None,
    ) -> None:
        if source_file is not None and type(source_file) is not PurePosixPath:
            raise TypeError("source_file error context must be a PurePosixPath")
        if source_file is not None and source_file.is_absolute():
            raise ValueError("source_file error context must be manifest-relative")
        self.code = code
        self.source_file = source_file
        self.table_id = table_id
        context = ""
        if source_file is not None:
            context += f": {source_file.as_posix()}"
        if table_id is not None:
            context += f" [{table_id}]"
        super().__init__(f"{code.value}{context}: {message}")
