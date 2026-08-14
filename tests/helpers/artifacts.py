"""Deterministic fixtures for artifact-contract tests."""

from datetime import date
from typing import Any


def expected_contract_payload(*, json_compatible: bool = False) -> dict[str, Any]:
    """Return one complete synthetic Phase 1 logical contract."""
    input_declarations = (
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
    table_names = (
        "bronze_source_column",
        "bronze_source_row",
        "bronze_source_cell",
        "silver_bond_instrument",
        "silver_domestic_listed_product",
        "silver_overseas_listed_product",
        "silver_fund_item",
        "silver_fund_item_attribute",
        "silver_quality_issue",
        "gold_exact_cross_source_link",
        "gold_exact_cross_source_link_evidence",
    )
    logical_inputs: tuple[dict[str, Any], ...] = tuple(
        {
            "namespace": namespace,
            "path": path,
            "kind": kind,
            "size_bytes": index + 1,
            "sha256": f"{index + 1:064x}",
        }
        for index, (namespace, path, kind) in enumerate(input_declarations)
    )
    tables: tuple[dict[str, Any], ...] = tuple(
        {
            "name": name,
            "grain": "synthetic",
            "schema_hash": f"{index + 20:064x}",
            "row_count": index + 10,
            "sort_key": ("id",),
            "unique_key": ("id",),
            "logical_hash": f"{index + 40:064x}",
        }
        for index, name in enumerate(table_names)
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
        "exact_link_pair_sha256": "d" * 64,
        "exact_link_evidence_count": 371,
    }
