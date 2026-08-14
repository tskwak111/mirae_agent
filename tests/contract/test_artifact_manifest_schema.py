"""JSON Schema parity for the strict artifact manifest."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from finproof.data.artifacts.manifest import ArtifactManifest
from tests.helpers.artifacts import manifest_payload

SCHEMA_PATH = Path(__file__).parents[2] / "schemas" / "artifact_manifest.schema.json"


def _schema() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def test_artifact_manifest_schema_accepts_only_exact_model_shape() -> None:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    payload = ArtifactManifest.model_validate(manifest_payload(), strict=True).model_dump(
        mode="json", warnings="none"
    )

    assert list(validator.iter_errors(payload)) == []
    assert tuple(schema["properties"]) == tuple(ArtifactManifest.model_fields)
    assert set(schema["required"]) == set(ArtifactManifest.model_fields)
    assert schema["additionalProperties"] is False

    extra = payload | {"unexpected": True}
    assert list(validator.iter_errors(extra))
    missing = dict(payload)
    missing.pop("files")
    assert list(validator.iter_errors(missing))


def test_artifact_manifest_schema_checks_every_format_error() -> None:
    validator = Draft202012Validator(_schema(), format_checker=FormatChecker())
    baseline = ArtifactManifest.model_validate(manifest_payload(), strict=True).model_dump(
        mode="json", warnings="none"
    )
    mutations: dict[str, tuple[object, ...]] = {
        "dataset-date": ("dataset_version", "2026-99-99"),
        "timestamp-format": ("persistence_timestamp", "not-a-time"),
        "timestamp-offset": ("persistence_timestamp", "2026-08-15T09:00:00+09:00"),
        "database-hash": ("database_sha256", "A" * 64),
        "manifest-hash": ("logical_hash", "short"),
        "input-path": ("source_inputs", 0, "path", "../unsafe"),
        "input-hash": ("source_inputs", 0, "sha256", "A" * 64),
        "input-size": ("source_inputs", 0, "size_bytes", -1),
        "file-path": ("files", 0, "path", "/absolute"),
        "file-hash": ("files", 0, "sha256", "short"),
        "file-size": ("files", 0, "size_bytes", -1),
        "table-path": ("tables", "bronze_source_cell", "parquet_path", "a//b"),
        "table-schema-hash": (
            "tables",
            "bronze_source_cell",
            "schema_sha256",
            "A" * 64,
        ),
        "table-logical-hash": (
            "tables",
            "bronze_source_cell",
            "logical_hash",
            "short",
        ),
        "table-count": ("tables", "bronze_source_cell", "row_count", -1),
    }
    for case, mutation in mutations.items():
        payload = deepcopy(baseline)
        target: Any = payload
        for token in mutation[:-2]:
            target = target[token]
        target[mutation[-2]] = mutation[-1]
        assert list(validator.iter_errors(payload)), case


@pytest.mark.parametrize(
    "case",
    [
        "input-order",
        "input-namespace",
        "input-path",
        "input-kind",
        "input-duplicate",
        "file-order",
        "file-path",
        "file-kind",
        "report-id-duplicate",
        "table-name",
        "table-layer",
        "table-grain",
        "table-path",
    ],
)
def test_artifact_manifest_schema_rejects_every_model_invalid_closed_inventory_literal(
    case: str,
) -> None:
    validator = Draft202012Validator(_schema(), format_checker=FormatChecker())
    payload = ArtifactManifest.model_validate(manifest_payload(), strict=True).model_dump(
        mode="json", warnings="none"
    )
    inputs = payload["source_inputs"]
    files = payload["files"]
    tables = payload["tables"]
    if case == "input-order":
        inputs[0], inputs[1] = inputs[1], inputs[0]
    elif case == "input-namespace":
        inputs[0]["namespace"] = "repository"
    elif case == "input-path":
        inputs[0]["path"] = "other.json"
    elif case == "input-kind":
        inputs[0]["kind"] = "source_schema_catalog"
    elif case == "input-duplicate":
        inputs[1] = deepcopy(inputs[0])
    elif case == "file-order":
        files[0], files[1] = files[1], files[0]
    elif case == "file-path":
        files[0]["path"] = "other.duckdb"
    elif case == "file-kind":
        files[1]["kind"] = "duckdb"
    elif case == "report-id-duplicate":
        report_entries = [entry for entry in files if entry["kind"] == "report"]
        report_entries[0]["report_id"] = report_entries[1]["report_id"]
    else:
        table = tables["bronze_source_cell"]
        if case == "table-name":
            table["table_name"] = "bronze_source_column"
        elif case == "table-layer":
            table["layer"] = "silver"
        elif case == "table-grain":
            table["grain"] = "other"
        else:
            table["parquet_path"] = "parquet/other.parquet"

    with pytest.raises(ValidationError):
        ArtifactManifest.model_validate_json(json.dumps(payload), strict=True)
    assert list(validator.iter_errors(payload)), case
