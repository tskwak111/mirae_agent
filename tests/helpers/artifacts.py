"""Complete synthetic Task 5 artifact fixtures."""

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Final

TABLES: Final[tuple[tuple[str, str, int], ...]] = (
    ("bronze_source_column", "source_column", 207),
    ("bronze_source_row", "source_row", 145_393),
    ("bronze_source_cell", "source_cell", 6_401_851),
    ("silver_bond_instrument", "instrument", 42_394),
    ("silver_domestic_listed_product", "listed_product", 1_733),
    ("silver_overseas_listed_product", "listed_product", 5_646),
    ("silver_fund_item", "fund_item", 11_138),
    ("silver_fund_item_attribute", "fund_attribute", 95_618),
    ("silver_quality_issue", "quality_issue", 4),
    ("gold_exact_cross_source_link", "exact_cross_source_link", 47),
    (
        "gold_exact_cross_source_link_evidence",
        "exact_cross_source_link_evidence",
        371,
    ),
)

INPUTS: Final[tuple[tuple[str, str, str], ...]] = (
    ("source_root", "input_manifest.json", "source_manifest"),
    ("source_root", "schema_catalog.json", "source_schema_catalog"),
    ("repository", "config/artifact_build.yaml", "artifact_build_config"),
    ("repository", "config/datasets.yaml", "dataset_registry"),
    ("repository", "config/quality_rules.yaml", "quality_rule_registry"),
    ("repository", "config/rating_scale.yaml", "rating_scale_registry"),
    ("repository", "config/state_rules.yaml", "state_rule_registry"),
    (
        "repository",
        "schemas/artifact_manifest.schema.json",
        "artifact_manifest_schema",
    ),
    ("repository", "schemas/quality_issue.schema.json", "quality_issue_schema"),
)


def expected_contract_payload(*, json_compatible: bool = False) -> dict[str, Any]:
    """Return one complete official-shaped Phase 1 logical contract fixture."""
    logical_inputs: tuple[dict[str, Any], ...] = tuple(
        {
            "namespace": namespace,
            "path": path,
            "kind": kind,
            "size_bytes": index + 1,
            "sha256": f"{index + 1:064x}",
        }
        for index, (namespace, path, kind) in enumerate(INPUTS)
    )
    tables: tuple[dict[str, Any], ...] = tuple(
        {
            "name": name,
            "grain": grain,
            "schema_hash": f"{index + 20:064x}",
            "row_count": row_count,
            "sort_key": ("id",),
            "unique_key": ("id",),
            "logical_hash": f"{index + 40:064x}",
        }
        for index, (name, grain, row_count) in enumerate(TABLES)
    )
    reports: tuple[dict[str, Any], ...] = (
        {"report_id": "source_audit", "semantic_hash": "a" * 64},
        {"report_id": "quality_summary", "semantic_hash": "b" * 64},
    )
    logical_inputs_output: object = logical_inputs
    tables_output: object = tables
    reports_output: object = reports
    dataset_version: object = date(2026, 7, 11)
    if json_compatible:
        logical_inputs_output = list(logical_inputs)
        tables_output = [
            {
                **table,
                "sort_key": list(table["sort_key"]),
                "unique_key": list(table["unique_key"]),
            }
            for table in tables
        ]
        reports_output = list(reports)
        dataset_version = "2026-07-11"
    return {
        "artifact_contract_version": "1.0.0",
        "artifact_set_id": "finproof-data-artifacts/v1",
        "dataset_version": dataset_version,
        "logical_inputs": logical_inputs_output,
        "tables": tables_output,
        "reports": reports_output,
        "overall_manifest_logical_hash": "c" * 64,
        "exact_link_pair_sha256": (
            "8f1049ae6137dbd2141214248c9871f8c4dcced3fcb81cb7c72c2f0863d3a962"
        ),
        "exact_link_evidence_count": 371,
    }


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def manifest_payload() -> dict[str, Any]:
    """Return one complete strict manifest payload with synthetic identities."""
    table_payloads: dict[str, Any] = {}
    for name, grain, row_count in sorted(TABLES):
        layer = name.split("_", maxsplit=1)[0]
        table_payloads[name] = {
            "table_name": name,
            "layer": layer,
            "grain": grain,
            "parquet_path": f"parquet/{name}.parquet",
            "row_count": row_count,
            "schema_sha256": _digest(f"schema:{name}"),
            "sort_key": ("id",),
            "unique_key": ("id",),
            "logical_hash": _digest(f"logical:{name}"),
        }

    files: list[dict[str, object]] = [
        {
            "path": "finproof.duckdb",
            "kind": "duckdb",
            "size_bytes": 8,
            "sha256": _digest("file:finproof.duckdb"),
            "report_id": None,
            "logical_hash": None,
        }
    ]
    for name, _, _ in TABLES:
        path = f"parquet/{name}.parquet"
        files.append(
            {
                "path": path,
                "kind": "parquet",
                "size_bytes": len(path.encode()),
                "sha256": _digest(f"file:{path}"),
                "report_id": None,
                "logical_hash": None,
            }
        )
    for report_id in ("source_audit", "quality_summary"):
        path = f"reports/{report_id}.json"
        files.append(
            {
                "path": path,
                "kind": "report",
                "size_bytes": len(path.encode()),
                "sha256": _digest(f"file:{path}"),
                "report_id": report_id,
                "logical_hash": _digest(f"report:{report_id}"),
            }
        )
    files.sort(key=lambda item: str(item["path"]))
    return {
        "manifest_version": "1.0.0",
        "artifact_contract_version": "1.0.0",
        "artifact_set_id": "finproof-data-artifacts/v1",
        "dataset_version": date(2026, 7, 11),
        "persistence_timestamp": datetime(2026, 8, 15, tzinfo=UTC),
        "source_inputs": tuple(
            {
                "namespace": namespace,
                "path": path,
                "kind": kind,
                "size_bytes": len(path.encode()),
                "sha256": _digest(f"input:{namespace}:{path}"),
            }
            for namespace, path, kind in INPUTS
        ),
        "versions": {
            "dataset_version": date(2026, 7, 11),
            "metric_registry_version": "1.0.0",
            "state_rule_version": "1.0.0",
            "quality_rule_version": "1.0.0",
            "rating_rule_version": "1.0.0",
            "answer_policy_version": "1.0.0",
            "planner_version": "1.0.0",
        },
        "files": tuple(files),
        "database_path": "finproof.duckdb",
        "database_sha256": _digest("file:finproof.duckdb"),
        "tables": table_payloads,
        "logical_hash": _digest("manifest:logical"),
    }


def write_artifact_tree(root: Path) -> Any:
    """Write one complete synthetic physical tree and return its strict manifest."""
    from finproof.data.artifacts.manifest import ArtifactManifest

    payload = manifest_payload()
    files = list(payload["files"])
    root.mkdir()
    (root / "parquet").mkdir()
    (root / "reports").mkdir()
    for entry in files:
        path = root / entry["path"]
        content = f"synthetic:{entry['path']}\n".encode()
        path.write_bytes(content)
        entry["size_bytes"] = len(content)
        entry["sha256"] = hashlib.sha256(content).hexdigest()
    database = next(entry for entry in files if entry["kind"] == "duckdb")
    payload["database_sha256"] = database["sha256"]
    payload["files"] = tuple(files)
    manifest = ArtifactManifest.model_validate(payload, strict=True)
    (root / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    return manifest
