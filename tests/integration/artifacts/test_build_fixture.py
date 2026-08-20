"""CP7C private core outcome and bounded telemetry contracts."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

import pytest


def _strict_outcome() -> Any:
    from finproof.data.artifacts.builder import (
        ArtifactBuildTelemetry,
        ArtifactCoreBuildOutcome,
        ArtifactManifestIdentity,
        ArtifactPhysicalFileHash,
        ArtifactWorkspaceTelemetry,
    )
    from finproof.data.artifacts.expected_contract import (
        ExpectedLogicalInput,
        ExpectedLogicalTable,
        ExpectedSemanticReport,
    )
    from finproof.data.artifacts.manifest import (
        ArtifactCoreVerificationResult,
        ArtifactManifest,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPECS
    from tests.helpers.artifacts import manifest_payload

    manifest = ArtifactManifest.model_validate(manifest_payload(), strict=True)
    logical = ArtifactCoreVerificationResult(
        artifact_contract_version=manifest.artifact_contract_version,
        artifact_set_id=manifest.artifact_set_id,
        dataset_version=manifest.dataset_version,
        logical_inputs=tuple(
            ExpectedLogicalInput.model_validate(value.model_dump(), strict=True)
            for value in manifest.source_inputs
        ),
        tables=tuple(
            ExpectedLogicalTable(
                name=value.table_name,
                grain=value.grain,
                schema_hash=value.schema_sha256,
                row_count=value.row_count,
                sort_key=value.sort_key,
                unique_key=value.unique_key,
                logical_hash=value.logical_hash,
            )
            for spec in TABLE_SPECS
            for value in (manifest.tables[spec.table_name],)
        ),
        reports=tuple(
            ExpectedSemanticReport(
                report_id=cast(Literal["source_audit", "quality_summary"], report_id),
                semantic_hash=next(
                    value.logical_hash
                    for value in manifest.files
                    if value.report_id == report_id and value.logical_hash is not None
                ),
            )
            for report_id in ("source_audit", "quality_summary")
        ),
        overall_manifest_logical_hash=manifest.logical_hash,
        exact_link_pair_sha256=("8f1049ae6137dbd2141214248c9871f8c4dcced3fcb81cb7c72c2f0863d3a962"),
        exact_link_evidence_count=371,
    )
    workspace = ArtifactWorkspaceTelemetry(
        mode=0o700,
        marker_owned=True,
        containment_verified=True,
        cleanup_completed=True,
        threads=1,
        memory_limit="1GiB",
    )
    telemetry = ArtifactBuildTelemetry(
        persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC),
        max_live_fund_group_rows=16,
        max_writer_batch_rows=65_536,
        max_verifier_batch_rows=65_536,
        max_bronze_reconstruction_cells=73,
        linked_domestic_record_json_parses=47,
        linked_fund_record_json_parses=47,
        max_live_link_keys=47,
        max_live_evidence_keys=371,
        staging_workspace=workspace,
        verifier_workspace=workspace,
        physical_files=tuple(
            ArtifactPhysicalFileHash(
                path=value.path,
                kind=value.kind,
                size_bytes=value.size_bytes,
                sha256=value.sha256,
            )
            for value in manifest.files
        ),
        manifest_identity=ArtifactManifestIdentity(
            manifest_version=manifest.manifest_version,
            artifact_contract_version=manifest.artifact_contract_version,
            artifact_set_id=manifest.artifact_set_id,
            dataset_version=manifest.dataset_version,
            logical_hash=manifest.logical_hash,
        ),
    )
    return ArtifactCoreBuildOutcome(
        manifest=manifest,
        logical_contract=logical,
        telemetry=telemetry,
    )


def test_private_core_outcome_binds_manifest_logical_and_physical_facts() -> None:
    from finproof.data.artifacts.builder import ArtifactCoreBuildOutcome

    outcome = _strict_outcome()
    assert type(outcome) is ArtifactCoreBuildOutcome
    assert outcome.telemetry.persistence_timestamp == outcome.manifest.persistence_timestamp
    assert len(outcome.telemetry.physical_files) == 14
    assert set(outcome.telemetry.staging_workspace.model_dump()) == {
        "mode",
        "marker_owned",
        "containment_verified",
        "cleanup_completed",
        "threads",
        "memory_limit",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mode", 0o755),
        ("marker_owned", False),
        ("containment_verified", False),
        ("cleanup_completed", False),
        ("threads", 2),
        ("memory_limit", "2GiB"),
        ("temp_path", "/private/tmp/leak"),
    ],
)
def test_workspace_telemetry_rejects_unverified_or_path_bearing_facts(
    field: str,
    value: object,
) -> None:
    from pydantic import ValidationError

    from finproof.data.artifacts.builder import ArtifactWorkspaceTelemetry

    payload: dict[str, object] = {
        "mode": 0o700,
        "marker_owned": True,
        "containment_verified": True,
        "cleanup_completed": True,
        "threads": 1,
        "memory_limit": "1GiB",
    }
    payload[field] = value
    with pytest.raises(ValidationError):
        ArtifactWorkspaceTelemetry.model_validate(payload, strict=True)


@pytest.mark.parametrize(
    "mutation",
    ["missing", "duplicate", "reordered", "hash", "timestamp", "logical"],
)
def test_core_outcome_rejects_incomplete_or_cross_generation_facts(mutation: str) -> None:
    from pydantic import ValidationError

    from finproof.data.artifacts.builder import ArtifactCoreBuildOutcome

    outcome = _strict_outcome()
    payload = outcome.model_dump(mode="python")
    if mutation == "missing":
        payload["telemetry"]["physical_files"] = payload["telemetry"]["physical_files"][:-1]
    elif mutation == "duplicate":
        payload["telemetry"]["physical_files"] = (
            payload["telemetry"]["physical_files"][0],
            *payload["telemetry"]["physical_files"],
        )
    elif mutation == "reordered":
        payload["telemetry"]["physical_files"] = tuple(
            reversed(payload["telemetry"]["physical_files"])
        )
    elif mutation == "hash":
        payload["telemetry"]["physical_files"][0]["sha256"] = "f" * 64
    elif mutation == "timestamp":
        payload["telemetry"]["persistence_timestamp"] = datetime(2026, 8, 16, tzinfo=UTC)
    else:
        payload["logical_contract"]["overall_manifest_logical_hash"] = "f" * 64
    with pytest.raises(ValidationError):
        ArtifactCoreBuildOutcome.model_validate(payload, strict=True)


def test_private_transform_returns_verified_outcome_after_exact_candidate_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.builder import (
        ArtifactCoreBuildOutcome,
        _build_private_core_outcome,
    )
    from finproof.data.artifacts.config import ArtifactBuildConfig, ArtifactBuildOptions
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    loaded = ArtifactBuildConfig.load(
        settings.artifact_build_config_path,
        repository_root=settings.repository_root,
        versions=versions,
    )
    payload = loaded.model_dump(mode="python")
    payload["sources"] = tuple(
        {**source, "rows": 1, "cells": source["columns"]} for source in payload["sources"]
    )
    payload["silver_counts"] = {
        "bond_instrument": 1,
        "domestic_listed_product": 1,
        "overseas_listed_product": 1,
        "fund_item": 1,
        "fund_item_attribute": 1,
    }
    payload["quarantine_source_rows"] = 0
    payload["exact_links"] = {
        "links": 0,
        "evidence": 0,
        "pair_sha256": hashlib.sha256(b"").hexdigest(),
    }
    config = ArtifactBuildConfig.model_validate(payload, strict=True)

    def small_config(
        _cls: object,
        _stream: object,
        *,
        versions: VersionBundle,
    ) -> ArtifactBuildConfig:
        assert versions is not None
        return config

    monkeypatch.setattr(
        ArtifactBuildConfig,
        "from_held_stream",
        classmethod(small_config),
    )
    outcome = _build_private_core_outcome(
        settings,
        versions,
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, 1, 2, 3, tzinfo=UTC)),
    )
    assert type(outcome) is ArtifactCoreBuildOutcome
    assert outcome.manifest.logical_hash == outcome.logical_contract.overall_manifest_logical_hash
    assert outcome.telemetry.persistence_timestamp == datetime(2026, 8, 15, 1, 2, 3, tzinfo=UTC)
    assert outcome.telemetry.max_bronze_reconstruction_cells == max(
        value.columns for value in config.sources
    )
    assert outcome.telemetry.linked_domestic_record_json_parses == 0
    assert outcome.telemetry.linked_fund_record_json_parses == 0
    assert not settings.artifact_dir.exists()
    assert not tuple(settings.repository_root.glob(".artifacts.finproof-stage-*"))
