"""Canonical artifact hashing contracts."""

import hashlib
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
from pathlib import PurePosixPath
from types import SimpleNamespace
from typing import ClassVar, cast

import pytest
from pydantic import BaseModel, ConfigDict

from finproof.data.artifacts.expected_contract import (
    ExpectedLogicalInput,
    ExpectedLogicalTable,
    ExpectedSemanticReport,
)
from finproof.data.artifacts.hashing import (
    TableSpecIdentity,
    canonical_json_bytes,
    manifest_logical_hash,
    report_logical_hash,
    schema_sha256,
    table_logical_hash,
)


class _Kind(StrEnum):
    VALUE = "value"


class _IntSubclass(int):
    pass


class _Iterable:
    def __iter__(self) -> Iterator[int]:
        return iter((1, 2))


class _OneShotRows:
    def __init__(self, rows: tuple[Mapping[str, object], ...]) -> None:
        self._rows = rows
        self.iterations = 0

    def __iter__(self) -> Iterator[Mapping[str, object]]:
        self.iterations += 1
        if self.iterations != 1:
            raise AssertionError("rows were iterated more than once")
        return iter(self._rows)

    def __len__(self) -> int:
        raise AssertionError("rows must not be measured or materialized")


class _DuplicateKeyMapping(Mapping[str, object]):
    def __getitem__(self, key: str) -> object:
        return {"id": 1, "value": "a"}[key]

    def __iter__(self) -> Iterator[str]:
        return iter(("id", "id", "value"))

    def __len__(self) -> int:
        return 3


class _StatefulIterationMapping(Mapping[str, object]):
    def __init__(self) -> None:
        self.iterations = 0
        self.lookups: list[str] = []

    def __getitem__(self, key: str) -> object:
        self.lookups.append(key)
        return {"id": 1, "value": "a", "unchecked": "external"}[key]

    def __iter__(self) -> Iterator[str]:
        self.iterations += 1
        if self.iterations == 1:
            return iter(("id", "value"))
        return iter(("id", "unchecked"))

    def __len__(self) -> int:
        return 2


class _LookupMutationMapping(Mapping[str, object]):
    def __init__(self) -> None:
        self.iterations = 0
        self.lookups: list[str] = []
        self._value_available = True

    def __getitem__(self, key: str) -> object:
        self.lookups.append(key)
        if key == "id":
            self._value_available = False
            return 1
        if key == "value" and self._value_available:
            return "a"
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        self.iterations += 1
        return iter(("id", "value"))

    def __len__(self) -> int:
        return 2


class _LookupErrorMapping(Mapping[str, object]):
    def __init__(self) -> None:
        self.iterations = 0

    def __getitem__(self, key: str) -> object:
        raise RuntimeError(f"lookup failed for {key}")

    def __iter__(self) -> Iterator[str]:
        self.iterations += 1
        return iter(("id", "value"))

    def __len__(self) -> int:
        return 2


class _SyntheticReport(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    projection_mode: ClassVar[str] = "valid"
    report_id: str
    count: int

    @property
    def physical_size(self) -> int:
        return 999

    def semantic_projection(self) -> Mapping[str, object]:
        projection: dict[str, object] = {
            "report_id": self.report_id,
            "count": self.count,
        }
        if self.projection_mode == "missing":
            projection.pop("count")
        elif self.projection_mode == "extra":
            projection["physical_size"] = self.physical_size
        elif self.projection_mode == "reordered":
            projection = {"count": self.count, "report_id": self.report_id}
        return projection


class _MissingProjectionReport(_SyntheticReport):
    projection_mode = "missing"


class _ExtraProjectionReport(_SyntheticReport):
    projection_mode = "extra"


class _ReorderedProjectionReport(_SyntheticReport):
    projection_mode = "reordered"


class _Versions(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    dataset_version: date
    metric_registry_version: str
    state_rule_version: str
    quality_rule_version: str
    rating_rule_version: str
    answer_policy_version: str
    planner_version: str


@dataclass(frozen=True)
class _Manifest:
    manifest_version: str
    artifact_contract_version: str
    artifact_set_id: str
    dataset_version: date
    logical_inputs: tuple[ExpectedLogicalInput, ...]
    versions: object
    tables: tuple[ExpectedLogicalTable, ...]
    reports: tuple[ExpectedSemanticReport, ...]
    persistence_timestamp: datetime
    physical_size: int


def _valid_manifest() -> _Manifest:
    return _Manifest(
        manifest_version="1.0.0",
        artifact_contract_version="1.0.0",
        artifact_set_id="finproof-data-artifacts/v1",
        dataset_version=date(2026, 7, 11),
        logical_inputs=(
            ExpectedLogicalInput(
                namespace="source_root",
                path="input_manifest.json",
                kind="source_manifest",
                size_bytes=1,
                sha256="a" * 64,
            ),
        ),
        versions=_Versions(
            dataset_version=date(2026, 7, 11),
            metric_registry_version="1.0.0",
            state_rule_version="1.0.0",
            quality_rule_version="1.0.0",
            rating_rule_version="1.0.0",
            answer_policy_version="1.0.0",
            planner_version="1.0.0",
        ),
        tables=(
            ExpectedLogicalTable(
                name="example",
                grain="row",
                schema_hash="b" * 64,
                row_count=2,
                sort_key=("id",),
                unique_key=("id",),
                logical_hash="c" * 64,
            ),
        ),
        reports=(ExpectedSemanticReport(report_id="source_audit", semantic_hash="d" * 64),),
        persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC),
        physical_size=999,
    )


@dataclass(frozen=True)
class _Column:
    name: str
    logical_type: str
    arrow_type: str
    duckdb_type: str
    nullable: bool


@dataclass(frozen=True)
class _Table:
    table_name: str
    grain: str
    columns: tuple[_Column, ...]
    unique_key: tuple[str, ...]
    sort_key: tuple[str, ...]
    logical_projection: tuple[str, ...]


def _valid_spec() -> _Table:
    return _Table(
        table_name="example",
        grain="row",
        columns=(
            _Column("id", "integer", "int64", "BIGINT", False),
            _Column("value", "text", "utf8", "VARCHAR", True),
        ),
        unique_key=("id",),
        sort_key=("id",),
        logical_projection=("id", "value"),
    )


def test_canonical_json_bytes_null() -> None:
    assert canonical_json_bytes(None) == b"null\n"
    assert canonical_json_bytes(None, terminal_newline=False) == b"null"


def test_canonical_json_bytes_exact_bool_int_and_text() -> None:
    assert canonical_json_bytes(True) == b"true\n"
    assert canonical_json_bytes(False) == b"false\n"
    assert canonical_json_bytes(42) == b"42\n"
    assert canonical_json_bytes("한글") == '"한글"\n'.encode()


def test_canonical_decimal_zero_trailing_scale_and_decimal_38_18_bounds() -> None:
    expected = {
        Decimal("1.2300"): b'"1.23"\n',
        Decimal("-0"): b'"0"\n',
        Decimal("0E-18"): b'"0"\n',
        Decimal("1E+3"): b'"1000"\n',
        Decimal("12345678901234567890.123456789012345678"): (
            b'"12345678901234567890.123456789012345678"\n'
        ),
    }
    for value, encoded in expected.items():
        assert canonical_json_bytes(value) == encoded

    invalid = (
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("1.1234567890123456789"),
        Decimal("123456789012345678901"),
    )
    for value in invalid:
        with pytest.raises((TypeError, ValueError)):
            canonical_json_bytes(value)


def test_canonical_datetime_date_enum_and_pure_posix_path() -> None:
    assert canonical_json_bytes(datetime(2026, 8, 15, 1, 2, 3, 4)) == (
        b'"2026-08-15T01:02:03.000004"\n'
    )
    assert (
        canonical_json_bytes(datetime(2026, 8, 15, 1, 2, 3, 4, tzinfo=UTC))
        == b'"2026-08-15T01:02:03.000004Z"\n'
    )
    assert canonical_json_bytes(date(2026, 7, 11)) == b'"2026-07-11"\n'
    assert canonical_json_bytes(_Kind.VALUE) == b'"value"\n'
    assert canonical_json_bytes(PurePosixPath("reports/source_audit.json")) == (
        b'"reports/source_audit.json"\n'
    )
    with pytest.raises(ValueError, match="UTC"):
        canonical_json_bytes(datetime(2026, 8, 15, tzinfo=timezone(timedelta(hours=9))))


def test_canonical_mapping_and_array_order_utf8_and_newline() -> None:
    value = {"한": [2, 1], "a": {"z": None, "b": Decimal("2.00")}}
    assert canonical_json_bytes(value) == ('{"a":{"b":"2","z":null},"한":[2,1]}\n'.encode())
    assert canonical_json_bytes(("나", "가"), terminal_newline=False) == ('["나","가"]'.encode())


@pytest.mark.parametrize(
    "value",
    [1.0, _IntSubclass(1), b"bytes", {"set"}, _Iterable(), object()],
)
def test_canonical_scalar_rejects_float_subclasses_and_unsupported_values(
    value: object,
) -> None:
    with pytest.raises(TypeError):
        canonical_json_bytes(value)


@pytest.mark.parametrize(
    "case",
    [
        "table-name",
        "grain",
        "columns-tuple",
        "column-name",
        "nullable-bool",
        "duplicate-columns",
        "unique-tuple",
        "unknown-unique",
        "unknown-sort",
        "empty-projection",
        "duplicate-projection",
        "unknown-projection",
    ],
)
def test_column_and_table_identity_protocols_reject_every_wrong_shape(
    case: str,
) -> None:
    spec: object = _valid_spec()
    if case == "table-name":
        spec = replace(_valid_spec(), table_name=cast(str, 1))
    elif case == "grain":
        spec = replace(_valid_spec(), grain=cast(str, 1))
    elif case == "columns-tuple":
        spec = replace(_valid_spec(), columns=cast(tuple[_Column, ...], []))
    elif case == "column-name":
        spec = replace(
            _valid_spec(),
            columns=cast(
                tuple[_Column, ...],
                (
                    SimpleNamespace(
                        name=1,
                        logical_type="text",
                        arrow_type="utf8",
                        duckdb_type="VARCHAR",
                        nullable=True,
                    ),
                ),
            ),
        )
    elif case == "nullable-bool":
        spec = replace(
            _valid_spec(),
            columns=cast(
                tuple[_Column, ...],
                (
                    SimpleNamespace(
                        name="id",
                        logical_type="integer",
                        arrow_type="int64",
                        duckdb_type="BIGINT",
                        nullable=1,
                    ),
                ),
            ),
        )
    elif case == "duplicate-columns":
        spec = replace(_valid_spec(), columns=(_valid_spec().columns[0],) * 2)
    elif case == "unique-tuple":
        spec = replace(_valid_spec(), unique_key=cast(tuple[str, ...], ["id"]))
    elif case == "unknown-unique":
        spec = replace(_valid_spec(), unique_key=("missing",))
    elif case == "unknown-sort":
        spec = replace(_valid_spec(), sort_key=("missing",))
    elif case == "empty-projection":
        spec = replace(_valid_spec(), logical_projection=())
    elif case == "duplicate-projection":
        spec = replace(_valid_spec(), logical_projection=("id", "id"))
    else:
        spec = replace(_valid_spec(), logical_projection=("missing",))

    with pytest.raises((TypeError, ValueError)):
        schema_sha256(cast(TableSpecIdentity, spec))


def test_schema_hash_uses_exact_identity_projection() -> None:
    expected_projection = (
        b'{"columns":[{"arrow_type":"int64","duckdb_type":"BIGINT",'
        b'"logical_type":"integer","name":"id","nullable":false},'
        b'{"arrow_type":"utf8","duckdb_type":"VARCHAR","logical_type":'
        b'"text","name":"value","nullable":true}],"grain":"row",'
        b'"sort_key":["id"],"table_name":"example","unique_key":["id"]}\n'
    )

    assert schema_sha256(_valid_spec()) == hashlib.sha256(expected_projection).hexdigest()


def test_schema_hash_changes_only_for_identity_fields() -> None:
    baseline = _valid_spec()
    baseline_hash = schema_sha256(baseline)
    nonidentity = SimpleNamespace(
        **(
            baseline.__dict__
            | {
                "logical_projection": ("value",),
                "layer": "silver",
                "relative_path": "tables/example.parquet",
                "compression": "zstd",
            }
        )
    )
    assert schema_sha256(cast(TableSpecIdentity, nonidentity)) == baseline_hash

    identity_mutations = (
        replace(baseline, table_name="changed"),
        replace(baseline, grain="instrument"),
        replace(
            baseline,
            columns=(replace(baseline.columns[0], name="identifier"), baseline.columns[1]),
            unique_key=("identifier",),
            sort_key=("identifier",),
            logical_projection=("identifier", "value"),
        ),
        replace(
            baseline,
            columns=(replace(baseline.columns[0], logical_type="text"), baseline.columns[1]),
        ),
        replace(
            baseline,
            columns=(replace(baseline.columns[0], arrow_type="utf8"), baseline.columns[1]),
        ),
        replace(
            baseline,
            columns=(replace(baseline.columns[0], duckdb_type="VARCHAR"), baseline.columns[1]),
        ),
        replace(
            baseline,
            columns=(replace(baseline.columns[0], nullable=True), baseline.columns[1]),
        ),
        replace(baseline, columns=tuple(reversed(baseline.columns))),
        replace(baseline, unique_key=("value",)),
        replace(baseline, sort_key=("value",)),
    )
    assert all(schema_sha256(spec) != baseline_hash for spec in identity_mutations)


def test_table_hash_writes_exact_header_before_first_row() -> None:
    spec = _valid_spec()
    expected_bytes = (
        canonical_json_bytes(
            {
                "schema_sha256": schema_sha256(spec),
                "logical_projection": ["id", "value"],
                "row_count": 2,
            }
        )
        + canonical_json_bytes({"id": 1, "value": "가"})
        + canonical_json_bytes({"id": 2, "value": "나"})
    )

    observed = table_logical_hash(
        spec,
        row_count=2,
        rows=iter(({"id": 1, "value": "가"}, {"id": 2, "value": "나"})),
    )

    assert observed == hashlib.sha256(expected_bytes).hexdigest()


@pytest.mark.parametrize(
    "row",
    [
        pytest.param({"id": 1}, id="missing-projection-key"),
        pytest.param({"id": 1, "value": "가", "extra": 2}, id="extra-key"),
    ],
)
def test_table_hash_requires_exact_logical_projection_keys(
    row: Mapping[str, object],
) -> None:
    with pytest.raises(ValueError, match="logical projection"):
        table_logical_hash(_valid_spec(), row_count=1, rows=iter((row,)))


@pytest.mark.parametrize(
    "row",
    [
        (("id", 1), ("value", "a")),
        _DuplicateKeyMapping(),
    ],
    ids=["non-mapping-tuple", "duplicate-key-mapping"],
)
def test_table_logical_hash_rejects_non_mapping_and_duplicate_key_mapping_rows(
    row: object,
) -> None:
    rows = cast(Iterable[Mapping[str, object]], (row,))

    with pytest.raises(TypeError, match="table row must be a mapping with unique keys"):
        table_logical_hash(_valid_spec(), row_count=1, rows=rows)


def test_table_logical_hash_snapshots_stateful_mapping_after_one_key_iteration() -> None:
    row = _StatefulIterationMapping()

    observed = table_logical_hash(_valid_spec(), row_count=1, rows=(row,))

    assert row.iterations == 1
    assert row.lookups == ["id", "value"]
    assert observed == "e6d190552db0c8f3ed630fc36f60d5b208fd01d57f2cc0f94b4d852d4a2aee28"


@pytest.mark.parametrize(
    "row",
    [_LookupMutationMapping(), _LookupErrorMapping()],
    ids=["lookup-mutation", "lookup-error"],
)
def test_table_logical_hash_fails_typed_when_mapping_lookup_changes_or_errors(
    row: _LookupMutationMapping | _LookupErrorMapping,
) -> None:
    with pytest.raises(TypeError, match="table row changed during snapshot"):
        table_logical_hash(_valid_spec(), row_count=1, rows=(row,))

    assert row.iterations == 1


@pytest.mark.parametrize(
    ("row_count", "rows"),
    [
        pytest.param(2, ({"id": 1, "value": "가"},), id="declared-too-high"),
        pytest.param(0, ({"id": 1, "value": "가"},), id="declared-too-low"),
        pytest.param(True, (), id="bool-count"),
        pytest.param(-1, (), id="negative-count"),
    ],
)
def test_table_hash_consumes_rows_once_and_requires_exact_final_count(
    row_count: int,
    rows: tuple[Mapping[str, object], ...],
) -> None:
    one_shot = _OneShotRows(rows)
    with pytest.raises((TypeError, ValueError)):
        table_logical_hash(_valid_spec(), row_count=row_count, rows=one_shot)
    assert one_shot.iterations <= 1


@pytest.mark.parametrize(
    ("report_type", "valid"),
    [
        pytest.param(_SyntheticReport, True, id="exact-projection"),
        pytest.param(_MissingProjectionReport, False, id="missing-field"),
        pytest.param(_ExtraProjectionReport, False, id="extra-field"),
        pytest.param(_ReorderedProjectionReport, False, id="reordered-fields"),
    ],
)
def test_report_hash_uses_only_closed_semantic_projection(
    report_type: type[_SyntheticReport], valid: bool
) -> None:
    report = report_type(report_id="source_audit", count=2)
    if not valid:
        with pytest.raises((TypeError, ValueError)):
            report_logical_hash(report)
        return

    expected = hashlib.sha256(
        canonical_json_bytes({"report_id": "source_audit", "count": 2})
    ).hexdigest()
    assert report_logical_hash(report) == expected


@pytest.mark.parametrize(
    "case",
    ["exact-projection", "physical-invariant", "input-not-tuple", "versions-extra"],
)
def test_manifest_hash_uses_only_closed_logical_projection(case: str) -> None:
    manifest: object = _valid_manifest()
    if case == "input-not-tuple":
        manifest = replace(
            _valid_manifest(),
            logical_inputs=cast(tuple[ExpectedLogicalInput, ...], []),
        )
    elif case == "versions-extra":
        versions = _valid_manifest().versions
        assert isinstance(versions, _Versions)
        manifest = replace(
            _valid_manifest(),
            versions=SimpleNamespace(
                **versions.model_dump(mode="python"), unexpected="not-logical"
            ),
        )

    if case in {"input-not-tuple", "versions-extra"}:
        with pytest.raises((TypeError, ValueError)):
            manifest_logical_hash(cast(_Manifest, manifest))
        return

    baseline = _valid_manifest()
    if case == "physical-invariant":
        manifest = replace(
            baseline,
            persistence_timestamp=datetime(2026, 8, 16, tzinfo=UTC),
            physical_size=1,
        )
    assert manifest_logical_hash(cast(_Manifest, manifest)) == manifest_logical_hash(baseline)


def test_manifest_input_mutation_changes_only_overall_logical_hash() -> None:
    baseline = _valid_manifest()
    input_entry = baseline.logical_inputs[0]
    mutated_input = input_entry.model_copy(update={"sha256": "e" * 64})
    mutated = replace(
        baseline,
        logical_inputs=(mutated_input,),
        persistence_timestamp=datetime(2027, 1, 1, tzinfo=UTC),
        physical_size=1,
    )

    assert mutated.tables is baseline.tables
    assert mutated.reports is baseline.reports
    assert mutated.versions is baseline.versions
    assert manifest_logical_hash(mutated) != manifest_logical_hash(baseline)
    assert manifest_logical_hash(mutated) == manifest_logical_hash(
        replace(
            mutated,
            persistence_timestamp=datetime(2030, 1, 1, tzinfo=UTC),
            physical_size=999_999,
        )
    )
