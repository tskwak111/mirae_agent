"""JSON Schema parity for the strict artifact manifest."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker

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
