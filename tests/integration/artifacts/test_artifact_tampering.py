"""CP7A final-inventory and report tampering contracts."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

import pytest


def test_public_manifest_verify_rejects_small_core_against_official_expected(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from tests.helpers.artifacts import write_report_artifact_tree
    from tests.integration.artifacts.test_artifact_equality import _quality_rows

    root = tmp_path / "published"
    manifest = write_report_artifact_tree(root, _quality_rows())

    with pytest.raises(ArtifactContractError) as caught:
        manifest.verify(root)

    assert caught.value.code is ArtifactErrorCode.REPRODUCIBILITY_MISMATCH


def test_build_verified_candidate_stage_invokes_complete_core_before_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.builder import (
        CandidateArtifactSet,
        build_verified_candidate_stage,
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
    candidate = build_verified_candidate_stage(
        settings=settings,
        versions=versions,
        options=ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
    )
    assert type(candidate) is CandidateArtifactSet
    candidate._require_issued()
    assert candidate._core_result.exact_link_evidence_count == 0
    candidate._custody.close()


def test_candidate_core_uses_final_relations_after_stage_owner_transfer(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.builder import _issue_candidate_artifact_set
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.expected_contract import ExpectedPhase1ArtifactContract
    from finproof.data.artifacts.manifest import (
        ArtifactCoreVerificationResult,
        ArtifactManifest,
        verify_declared_inventory,
    )
    from finproof.data.artifacts.parquet_io import (
        ParquetArtifactTableVerifier,
        ParquetBatchWriter,
        StagedParquetSet,
        verify_staged_parquet_table,
    )
    from finproof.data.artifacts.reports import _FinalInventoryRelationVerifier
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.data.artifacts.table_specs import TABLE_SPECS
    from tests.helpers.artifacts import (
        artifact_build_input_identity,
        artifact_staging_settings,
        expected_contract_payload,
        write_database_artifact_tree,
    )
    from tests.integration.artifacts.test_artifact_equality import _quality_rows

    final_root = tmp_path / "final"
    final_manifest = write_database_artifact_tree(final_root, _quality_rows())
    expected = ExpectedPhase1ArtifactContract.model_validate(
        expected_contract_payload(),
        strict=True,
    )
    core = ArtifactCoreVerificationResult.model_validate(
        expected.model_dump(mode="python"),
        strict=True,
    )
    settings = artifact_staging_settings(tmp_path / "repository")
    input_identity = artifact_build_input_identity(settings)
    candidate_manifest = ArtifactManifest.from_build(
        input_identity=input_identity,
        persistence_timestamp=final_manifest.persistence_timestamp,
        versions=final_manifest.versions,
        files=final_manifest.files,
        database_sha256=final_manifest.database_sha256,
        tables=final_manifest.tables,
        logical_hash=final_manifest.logical_hash,
    )
    with (
        verify_declared_inventory(final_manifest, final_root) as inventory,
        ArtifactBuildSession.initialize(
            settings,
            VersionBundle(),
            ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
            input_identity=input_identity,
        ) as owner,
    ):
        staged_verifications = []
        for spec in TABLE_SPECS:
            leaf = owner.claim_parquet_leaf(spec)
            ParquetBatchWriter(spec, leaf).close()
            staged_verifications.append(
                verify_staged_parquet_table(owner=owner, leaf=leaf, spec=spec)
            )
        staged = StagedParquetSet.from_verified(
            owner=owner,
            verifications=tuple(staged_verifications),
        )
        final_tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=final_manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        relation = _FinalInventoryRelationVerifier._from_verified(
            inventory=inventory,
            tables=final_tables,
        )
        transferred = owner.transfer_candidate_stage()
        custody = transferred.issue_candidate_custody()
        candidate = _issue_candidate_artifact_set(
            custody=custody,
            manifest=candidate_manifest,
            core=core,
            input_identity=input_identity,
        )
        try:
            with pytest.raises(ArtifactContractError):
                staged.require_complete()
            candidate._require_issued()
            assert relation.verify_quality_to_bronze().total_issues == 1
        finally:
            custody.close()


def test_report_verifier_rebuilds_source_inputs_and_bronze_counts(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.reports import StrictArtifactReportVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS
    from tests.helpers.artifacts import write_report_artifact_tree
    from tests.integration.artifacts.test_artifact_equality import _quality_rows

    root = tmp_path / "artifacts"
    manifest = write_report_artifact_tree(root, _quality_rows())
    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        result = StrictArtifactReportVerifier().verify_reports(
            manifest=manifest,
            inventory=inventory,
            tables=tables,
        )
        assert tuple(report.report_id for report in result.reports) == (
            "source_audit",
            "quality_summary",
        )


def _rewrite_report(
    root: Path,
    manifest: Any,
    report: Any,
) -> Any:
    from finproof.data.artifacts.expected_contract import (
        ExpectedLogicalInput,
        ExpectedLogicalTable,
        ExpectedSemanticReport,
    )
    from finproof.data.artifacts.hashing import manifest_logical_hash, report_logical_hash
    from finproof.data.artifacts.manifest import ArtifactManifest, _ManifestLogicalProjection
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    path = root / "reports" / f"{report.report_id}.json"
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    payload = manifest.model_dump(mode="python")
    files = [dict(entry) for entry in payload["files"]]
    entry = next(value for value in files if value["report_id"] == report.report_id)
    content = path.read_bytes()
    entry["size_bytes"] = len(content)
    entry["sha256"] = hashlib.sha256(content).hexdigest()
    entry["logical_hash"] = report_logical_hash(report)
    payload["files"] = tuple(files)
    report_hashes = {
        value["report_id"]: value["logical_hash"]
        for value in files
        if value["report_id"] is not None
    }
    reports = tuple(
        ExpectedSemanticReport(
            report_id=cast(Literal["source_audit", "quality_summary"], report_id),
            semantic_hash=report_hashes[report_id],
        )
        for report_id in ("source_audit", "quality_summary")
    )
    tables = tuple(
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
    )
    inputs = tuple(
        ExpectedLogicalInput.model_validate(value.model_dump(mode="python"), strict=True)
        for value in manifest.source_inputs
    )
    payload["logical_hash"] = manifest_logical_hash(
        _ManifestLogicalProjection(
            manifest_version=manifest.manifest_version,
            artifact_contract_version=manifest.artifact_contract_version,
            artifact_set_id=manifest.artifact_set_id,
            dataset_version=manifest.dataset_version,
            logical_inputs=inputs,
            versions=manifest.versions,
            tables=tables,
            reports=reports,
        )
    )
    changed = ArtifactManifest.model_validate(payload, strict=True)
    (root / "manifest.json").write_text(changed.model_dump_json(), encoding="utf-8")
    return changed


def test_report_verifier_rebuilds_silver_and_quarantine_counts(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.reports import (
        ExpectedObservedCount,
        StrictArtifactReportVerifier,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPECS
    from tests.helpers.artifacts import write_report_artifact_tree
    from tests.integration.artifacts.test_artifact_equality import _quality_rows

    for case in ("silver", "quarantine", "excluded"):
        root = tmp_path / case
        manifest = write_report_artifact_tree(root, _quality_rows())
        from finproof.data.artifacts.reports import SourceAuditReport

        source = SourceAuditReport.model_validate_json(
            (root / "reports/source_audit.json").read_bytes(), strict=True
        )
        if case == "silver":
            silver_first = source.silver_tables[0]
            source = source.model_copy(
                update={
                    "silver_tables": (
                        silver_first.model_copy(
                            update={
                                "expected": silver_first.expected + 1,
                                "observed": silver_first.observed + 1,
                            }
                        ),
                        *source.silver_tables[1:],
                    )
                }
            )
        elif case == "quarantine":
            source = source.model_copy(
                update={
                    "quarantine_source_rows": ExpectedObservedCount(
                        expected=source.quarantine_source_rows.expected + 1,
                        observed=source.quarantine_source_rows.observed + 1,
                    )
                }
            )
        if case == "excluded":
            from finproof.data.artifacts.reports import (
                ExcludedSilverCount,
                QualitySummaryReport,
            )

            quality = QualitySummaryReport.model_validate_json(
                (root / "reports/quality_summary.json").read_bytes(), strict=True
            )
            excluded_first = quality.excluded_silver_records[0]
            report: SourceAuditReport | QualitySummaryReport = quality.model_copy(
                update={
                    "excluded_silver_records": (
                        ExcludedSilverCount(
                            grain=excluded_first.grain,
                            count=excluded_first.count + 1,
                        ),
                        *quality.excluded_silver_records[1:],
                    )
                }
            )
        else:
            report = source
        changed = _rewrite_report(root, manifest, report)
        with verify_declared_inventory(changed, root) as inventory:
            tables = ParquetArtifactTableVerifier().verify_tables(
                manifest=changed,
                inventory=inventory,
                specs=TABLE_SPECS,
            )
            with pytest.raises(ValueError, match="rebuilt final relations"):
                StrictArtifactReportVerifier().verify_reports(
                    manifest=changed,
                    inventory=inventory,
                    tables=tables,
                )


def _exact_link_rows(
    *,
    evidence_raw: str | None = None,
    left_id: str = "L1",
    right_id: str = "R1",
) -> dict[str, tuple[dict[str, object], ...]]:
    from finproof.data.artifacts.links import _evidence_from_candidate, _link_from_candidate
    from finproof.data.artifacts.serialization import (
        BronzeSourceCellRecord,
        serialize_table_row,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from finproof.data.source_manifest import OFFICIAL_TABLE_IDS
    from tests.unit.data.artifacts.test_exact_links import _candidate

    candidate = _candidate(left_id=left_id, right_id=right_id)
    link = _link_from_candidate(candidate)
    evidence = _evidence_from_candidate(candidate, link)
    if evidence_raw is not None:
        evidence = tuple(
            row.model_copy(update={"raw_identifier": evidence_raw}) for row in evidence
        )
    cells = tuple(
        BronzeSourceCellRecord(
            source_table_order=OFFICIAL_TABLE_IDS.index(row.source_table),
            source_table=row.source_table,
            source_file=row.source_file,
            source_sheet=row.source_sheet,
            source_row_number=row.source_row_number,
            source_column_name=row.source_column_name,
            source_column_number=row.source_column_number,
            source_column_letter=row.source_column_letter,
            source_checksum=row.source_checksum,
            source_snapshot_date=row.source_snapshot_date,
            source_applicable_date=row.source_applicable_date,
            raw_value=row.raw_identifier,
        )
        for row in evidence
    )
    return {
        "bronze_source_cell": tuple(
            dict(serialize_table_row(TABLE_SPEC_BY_NAME["bronze_source_cell"], row))
            for row in cells
        ),
        "gold_exact_cross_source_link": (
            dict(serialize_table_row(TABLE_SPEC_BY_NAME["gold_exact_cross_source_link"], link)),
        ),
        "gold_exact_cross_source_link_evidence": tuple(
            dict(
                serialize_table_row(
                    TABLE_SPEC_BY_NAME["gold_exact_cross_source_link_evidence"], row
                )
            )
            for row in evidence
        ),
    }


def test_report_verifier_rebuilds_exact_link_and_evidence_semantics(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.reports import StrictArtifactReportVerifier
    from finproof.data.artifacts.table_specs import TABLE_SPECS
    from tests.helpers.artifacts import write_report_artifact_tree
    from tests.integration.artifacts.test_artifact_equality import _quality_rows

    rows = _quality_rows()
    extra = _exact_link_rows(evidence_raw="MUTATED")
    rows["bronze_source_cell"] = (
        *rows["bronze_source_cell"],
        *extra["bronze_source_cell"],
    )
    rows.update({key: value for key, value in extra.items() if key != "bronze_source_cell"})
    root = tmp_path / "artifacts"
    manifest = write_report_artifact_tree(root, rows)
    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        with pytest.raises(ValueError, match="evidence"):
            StrictArtifactReportVerifier().verify_reports(
                manifest=manifest,
                inventory=inventory,
                tables=tables,
            )


@pytest.mark.parametrize("case", ["zero", "missing", "mutated", "extra"])
def test_report_verifier_reopens_every_exact_linked_wide_record(
    tmp_path: Path,
    case: str,
) -> None:
    from finproof.data.artifacts.manifest import (
        ReportVerificationResult,
        verify_declared_inventory,
    )
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.reports import StrictArtifactReportVerifier
    from finproof.data.artifacts.serialization import serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME, TABLE_SPECS
    from tests.helpers.artifacts import write_report_artifact_tree
    from tests.integration.artifacts.test_artifact_equality import (
        _linked_rows,
        _quality_rows,
    )
    from tests.unit.data.artifacts.test_serialization import _domestic_record

    rows = _quality_rows()
    if case != "zero":
        wide, left_id, right_id = _linked_rows()
        exact = (
            _exact_link_rows()
            if case == "mutated"
            else _exact_link_rows(left_id=left_id, right_id=right_id)
        )
        rows["bronze_source_cell"] = (
            *rows["bronze_source_cell"],
            *exact["bronze_source_cell"],
        )
        rows.update({key: value for key, value in exact.items() if key != "bronze_source_cell"})
        rows["silver_domestic_listed_product"] = wide["silver_domestic_listed_product"]
        if case != "missing":
            rows["silver_fund_item"] = wide["silver_fund_item"]
        if case == "extra":
            domestic = _domestic_record()
            extra_product_id = domestic.product_id.model_copy(
                update={"normalized_value": "ZZZ-UNLINKED"}
            )
            extra = domestic.model_copy(update={"product_id": extra_product_id})
            extra_row = dict(
                serialize_table_row(
                    TABLE_SPEC_BY_NAME["silver_domestic_listed_product"],
                    extra,
                )
            )
            rows["silver_domestic_listed_product"] = tuple(
                sorted(
                    (*rows["silver_domestic_listed_product"], extra_row),
                    key=lambda row: cast(str, row["product_id"]),
                )
            )
    root = tmp_path / "artifacts"
    manifest = write_report_artifact_tree(root, rows)
    with verify_declared_inventory(manifest, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=manifest,
            inventory=inventory,
            specs=TABLE_SPECS,
        )

        def operation() -> ReportVerificationResult:
            return StrictArtifactReportVerifier().verify_reports(
                manifest=manifest,
                inventory=inventory,
                tables=tables,
            )

        if case == "zero":
            assert operation().exact_link_evidence_count == 0
        elif case == "extra":
            assert operation().exact_link_evidence_count == 2
        else:
            with pytest.raises(ValueError, match="linked"):
                operation()


def test_report_verifier_rebuilds_quality_groups_and_aggregates(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.reports import (
        QualitySummaryReport,
        RuleCount,
        StrictArtifactReportVerifier,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPECS
    from tests.helpers.artifacts import write_report_artifact_tree
    from tests.integration.artifacts.test_artifact_equality import _quality_rows

    root = tmp_path / "artifacts"
    manifest = write_report_artifact_tree(root, _quality_rows())
    quality = QualitySummaryReport.model_validate_json(
        (root / "reports/quality_summary.json").read_bytes(), strict=True
    )
    first = quality.by_rule[0]
    changed_quality = quality.model_copy(
        update={
            "by_rule": (
                RuleCount(
                    rule_id="tampered.rule",
                    rule_version=first.rule_version,
                    count=first.count,
                ),
            )
        }
    )
    changed = _rewrite_report(root, manifest, changed_quality)
    with verify_declared_inventory(changed, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=changed,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        with pytest.raises(ValueError, match="rebuilt final relations"):
            StrictArtifactReportVerifier().verify_reports(
                manifest=changed,
                inventory=inventory,
                tables=tables,
            )


def test_report_verifier_binds_quality_table_logical_hash(tmp_path: Path) -> None:
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.reports import (
        QualitySummaryReport,
        StrictArtifactReportVerifier,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPECS
    from tests.helpers.artifacts import write_report_artifact_tree
    from tests.integration.artifacts.test_artifact_equality import _quality_rows

    root = tmp_path / "artifacts"
    manifest = write_report_artifact_tree(root, _quality_rows())
    quality = QualitySummaryReport.model_validate_json(
        (root / "reports/quality_summary.json").read_bytes(), strict=True
    ).model_copy(update={"quality_table_logical_hash": "f" * 64})
    changed = _rewrite_report(root, manifest, quality)
    with verify_declared_inventory(changed, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=changed,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        with pytest.raises(ValueError, match="rebuilt final relations"):
            StrictArtifactReportVerifier().verify_reports(
                manifest=changed,
                inventory=inventory,
                tables=tables,
            )


def test_report_verifier_rejects_cross_report_quarantine_mismatch_with_all_outer_hashes_recomputed(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.manifest import verify_declared_inventory
    from finproof.data.artifacts.parquet_io import ParquetArtifactTableVerifier
    from finproof.data.artifacts.reports import (
        ExpectedObservedCount,
        SourceAuditReport,
        StrictArtifactReportVerifier,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPECS
    from tests.helpers.artifacts import write_report_artifact_tree
    from tests.integration.artifacts.test_artifact_equality import _quality_rows

    root = tmp_path / "artifacts"
    manifest = write_report_artifact_tree(root, _quality_rows())
    source = SourceAuditReport.model_validate_json(
        (root / "reports/source_audit.json").read_bytes(), strict=True
    ).model_copy(update={"quarantine_source_rows": ExpectedObservedCount(expected=0, observed=0)})
    changed = _rewrite_report(root, manifest, source)
    with verify_declared_inventory(changed, root) as inventory:
        tables = ParquetArtifactTableVerifier().verify_tables(
            manifest=changed,
            inventory=inventory,
            specs=TABLE_SPECS,
        )
        with pytest.raises(ValueError, match="rebuilt final relations"):
            StrictArtifactReportVerifier().verify_reports(
                manifest=changed,
                inventory=inventory,
                tables=tables,
            )
