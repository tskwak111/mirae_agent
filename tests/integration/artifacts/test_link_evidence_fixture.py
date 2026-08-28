# mypy: disable-error-code="arg-type,attr-defined,no-untyped-def"
"""Gold exact-link persistence and verified-set extension integration contracts."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath

import pytest


@contextmanager
def _empty_link_stage(
    tmp_path: Path,
    *,
    build: bool = True,
) -> Iterator[tuple[object, ...]]:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildConfig, ArtifactBuildOptions
    from finproof.data.artifacts.links import build_exact_links
    from finproof.data.artifacts.silver import (
        SilverArtifactEmitter,
        take_exact_link_candidate_store,
    )
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
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
        {**source, "rows": 1, "columns": source["columns"], "cells": source["columns"]}
        for source in payload["sources"]
    )
    payload["silver_counts"] = {
        "bond_sale_lot": 1,
        "bond_instrument": 1,
        "domestic_listed_product": 1,
        "overseas_listed_product": 1,
        "fund_item": 1,
    }
    payload["quarantine_source_rows"] = 0
    config = ArtifactBuildConfig.model_validate(payload, strict=True)
    with ArtifactBuildSession.initialize(
        settings,
        versions,
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=artifact_build_input_identity(settings),
    ) as session:
        emitter = SilverArtifactEmitter.for_session(
            session=session,
            config=config,
            versions=versions,
            rating_registry=RatingRegistry.from_yaml(
                settings.repository_root / "config/rating_scale.yaml"
            ),
        )
        bronze_result = session.ingest_bronze(consumer=emitter)
        emitter._order_store._connection.execute("DELETE FROM order_exact_link_left_candidate")
        emitter._order_store._connection.execute("DELETE FROM order_exact_link_right_candidate")
        silver_result = emitter.finalize(bronze_result=bronze_result)
        custody = take_exact_link_candidate_store(silver_result=silver_result)
        build_result = (
            build_exact_links(
                silver_result=silver_result,
                custody=custody,
                config=config,
            )
            if build
            else None
        )
        yield session, config, silver_result, custody, build_result


def test_exact_gold_writers_use_only_registered_link_and_evidence_specs(
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildConfig, ArtifactBuildOptions
    from finproof.data.artifacts.links import (
        _write_exact_gold_verifications,
        build_exact_links,
    )
    from finproof.data.artifacts.serialization import canonical_record_json
    from finproof.data.artifacts.silver import (
        SilverArtifactEmitter,
        take_exact_link_candidate_store,
    )
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        DomesticExactLinkCandidate,
        ExactLinkCandidateJoinRow,
        ExactLinkIdentifierSource,
        ExternalOrderRelation,
        ExternalOrderRow,
        FundExactLinkCandidate,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from finproof.domain.locators import SourceCellLocator
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    loaded = ArtifactBuildConfig.load(
        settings.artifact_build_config_path,
        repository_root=settings.repository_root,
        versions=versions,
    )
    payload = loaded.model_dump(mode="python")
    payload["silver_counts"] = {
        "bond_sale_lot": 1,
        "bond_instrument": 1,
        "domestic_listed_product": 1,
        "overseas_listed_product": 1,
        "fund_item": 1,
    }
    payload["quarantine_source_rows"] = 0
    config = ArtifactBuildConfig.model_validate(payload, strict=True)
    locator = ExactLinkIdentifierSource(
        raw_identifier="MATCH",
        locator=SourceCellLocator(
            source_table="PREF01N001",
            source_file=PurePosixPath("data/domestic.xlsx"),
            source_sheet="Sheet1",
            source_row_number=2,
            source_column_name="pd_itm_no",
            source_column_number=1,
            source_column_letter="A",
            source_checksum="a" * 64,
            source_snapshot_date=date(2026, 8, 24),
            source_applicable_date=None,
        ),
    )
    right_locator = ExactLinkIdentifierSource(
        raw_identifier="MATCH",
        locator=SourceCellLocator(
            source_table="PRFD01N001",
            source_file=PurePosixPath("data/fund.xlsx"),
            source_sheet="Sheet1",
            source_row_number=2,
            source_column_name="ksd_itm_no",
            source_column_number=1,
            source_column_letter="A",
            source_checksum="b" * 64,
            source_snapshot_date=date(2026, 8, 24),
            source_applicable_date=None,
        ),
    )
    candidate = ExactLinkCandidateJoinRow(
        matched_raw_identifier="MATCH",
        left=DomesticExactLinkCandidate(
            left_product_id="L1",
            source_product_type="ETF",
            identifier=locator,
        ),
        right=FundExactLinkCandidate(
            right_product_id="R1",
            identifiers=(right_locator,),
        ),
    )

    with ArtifactBuildSession.initialize(
        settings,
        versions,
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=artifact_build_input_identity(settings),
    ) as session:
        emitter = SilverArtifactEmitter.for_session(
            session=session,
            config=config,
            versions=versions,
            rating_registry=RatingRegistry.from_yaml(
                settings.repository_root / "config/rating_scale.yaml"
            ),
        )
        bronze_result = session.ingest_bronze(consumer=emitter)
        emitter._order_store._connection.execute("DELETE FROM order_exact_link_left_candidate")
        emitter._order_store._connection.execute("DELETE FROM order_exact_link_right_candidate")
        emitter._order_store.insert_batch(
            relation=ExternalOrderRelation.EXACT_LINK_LEFT_CANDIDATE,
            rows=(
                ExternalOrderRow(
                    key=(candidate.matched_raw_identifier, candidate.left.left_product_id),
                    payload_json=canonical_record_json(candidate.left),
                ),
            ),
        )
        emitter._order_store.insert_batch(
            relation=ExternalOrderRelation.EXACT_LINK_RIGHT_CANDIDATE,
            rows=(
                ExternalOrderRow(
                    key=(candidate.matched_raw_identifier, candidate.right.right_product_id),
                    payload_json=canonical_record_json(candidate.right),
                ),
            ),
        )
        silver_result = emitter.finalize(bronze_result=bronze_result)
        custody = take_exact_link_candidate_store(silver_result=silver_result)
        build_result = build_exact_links(
            silver_result=silver_result,
            custody=custody,
            config=config,
        )

        verifications = _write_exact_gold_verifications(
            owner=session,
            build_result=build_result,
        )

        assert tuple(item.logical.name for item in verifications) == (
            "gold_exact_cross_source_link",
            "gold_exact_cross_source_link_evidence",
        )
        assert tuple(item.handle._spec for item in verifications) == (
            TABLE_SPEC_BY_NAME["gold_exact_cross_source_link"],
            TABLE_SPEC_BY_NAME["gold_exact_cross_source_link_evidence"],
        )
        assert tuple(item.logical.row_count for item in verifications) == (1, 2)
        custody.close()


def test_exact_gold_verification_extends_same_set_atomically_from_eleven_to_thirteen_and_preserves_prefix_identity(  # noqa: E501
    tmp_path: Path,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildConfig, ArtifactBuildOptions
    from finproof.data.artifacts.links import (
        _extend_silver_with_exact_links,
        _write_exact_gold_verifications,
        build_exact_links,
    )
    from finproof.data.artifacts.serialization import canonical_record_json
    from finproof.data.artifacts.silver import (
        SilverArtifactEmitter,
        take_exact_link_candidate_store,
    )
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExternalOrderRelation,
        ExternalOrderRow,
    )
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.xlsx import write_complete_bronze_repository
    from tests.unit.data.artifacts.test_exact_links import _candidate

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    loaded = ArtifactBuildConfig.load(
        settings.artifact_build_config_path,
        repository_root=settings.repository_root,
        versions=versions,
    )
    payload = loaded.model_dump(mode="python")
    payload["silver_counts"] = {
        "bond_sale_lot": 1,
        "bond_instrument": 1,
        "domestic_listed_product": 1,
        "overseas_listed_product": 1,
        "fund_item": 1,
    }
    payload["quarantine_source_rows"] = 0
    config = ArtifactBuildConfig.model_validate(payload, strict=True)
    candidate = _candidate(raw="MATCH", left_id="L1", right_id="R1")
    with ArtifactBuildSession.initialize(
        settings,
        versions,
        ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC)),
        input_identity=artifact_build_input_identity(settings),
    ) as session:
        emitter = SilverArtifactEmitter.for_session(
            session=session,
            config=config,
            versions=versions,
            rating_registry=RatingRegistry.from_yaml(
                settings.repository_root / "config/rating_scale.yaml"
            ),
        )
        bronze_result = session.ingest_bronze(consumer=emitter)
        emitter._order_store._connection.execute("DELETE FROM order_exact_link_left_candidate")
        emitter._order_store._connection.execute("DELETE FROM order_exact_link_right_candidate")
        emitter._order_store.insert_batch(
            relation=ExternalOrderRelation.EXACT_LINK_LEFT_CANDIDATE,
            rows=(
                ExternalOrderRow(
                    key=(candidate.matched_raw_identifier, candidate.left.left_product_id),
                    payload_json=canonical_record_json(candidate.left),
                ),
            ),
        )
        emitter._order_store.insert_batch(
            relation=ExternalOrderRelation.EXACT_LINK_RIGHT_CANDIDATE,
            rows=(
                ExternalOrderRow(
                    key=(candidate.matched_raw_identifier, candidate.right.right_product_id),
                    payload_json=canonical_record_json(candidate.right),
                ),
            ),
        )
        silver_result = emitter.finalize(bronze_result=bronze_result)
        prefix_verifications = silver_result.staged_tables.verifications
        prefix_handles = silver_result.staged_tables.handles
        custody = take_exact_link_candidate_store(silver_result=silver_result)
        build_result = build_exact_links(
            silver_result=silver_result,
            custody=custody,
            config=config,
        )
        gold = _write_exact_gold_verifications(owner=session, build_result=build_result)

        successor = _extend_silver_with_exact_links(
            silver_result=silver_result,
            owner=session,
            verifications=gold,
        )

        assert len(successor.verifications) == 13
        assert successor.verifications[:11] == prefix_verifications
        assert all(
            left is right
            for left, right in zip(successor.verifications[:11], prefix_verifications, strict=True)
        )
        assert all(
            left is right
            for left, right in zip(successor.handles[:11], prefix_handles, strict=True)
        )
        assert successor.persistence_timestamp == silver_result.staged_tables.persistence_timestamp
        custody.close()


@pytest.mark.parametrize(
    "fault",
    ["evidence-admission", "claim", "open-write", "close", "reopen", "extension"],
)
def test_preadmission_and_preextension_faults_leave_no_successor_or_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    from finproof.data.artifacts import links
    from finproof.data.artifacts.links import _build_and_extend_exact_links
    from finproof.data.artifacts.parquet_io import ParquetBatchWriter, StagedParquetSet
    from finproof.data.artifacts.staging import (
        ArtifactBuildSession,
        ExactLinkCandidateStoreCustody,
    )

    def fail(*_args: object, **_kwargs: object) -> None:
        raise OSError(fault)

    with _empty_link_stage(tmp_path, build=False) as values:
        session, config, silver_result, custody, _missing = values
        prefix = silver_result.staged_tables
        if fault == "evidence-admission":
            monkeypatch.setattr(ExactLinkCandidateStoreCustody, "admit_exact_evidence", fail)
        elif fault == "claim":
            monkeypatch.setattr(ArtifactBuildSession, "claim_parquet_leaf", fail)
        elif fault == "open-write":
            monkeypatch.setattr(links, "ParquetBatchWriter", fail)
        elif fault == "close":
            monkeypatch.setattr(ParquetBatchWriter, "close", fail)
        elif fault == "reopen":
            monkeypatch.setattr(links, "verify_staged_parquet_table", fail)
        else:
            monkeypatch.setattr(StagedParquetSet, "extend_verified", fail)

        with pytest.raises((OSError, TypeError, ValueError)):
            _build_and_extend_exact_links(
                silver_result=silver_result,
                custody=custody,
                config=config,
                owner=session,
            )
        assert session._staged_sets.get(id(prefix), (None,))[0] is prefix
        assert all(len(item[0].verifications) == 9 for item in session._staged_sets.values())


def test_complete_builder_follows_exact_order_closes_custody_then_issues_exact_six_field_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.data.artifacts import builder
    from finproof.data.artifacts.builder import (
        CompleteArtifactBuildResult,
        build_complete_for_session,
    )

    with _empty_link_stage(tmp_path, build=False) as values:
        session, config, silver_result, custody, _missing = values
        monkeypatch.setattr(
            builder,
            "build_silver_for_session",
            lambda **_kwargs: silver_result,
        )
        monkeypatch.setattr(
            builder,
            "take_exact_link_candidate_store",
            lambda **_kwargs: custody,
            raising=False,
        )

        result = build_complete_for_session(
            session=session,
            config=config,
            versions=session._versions,
        )

        assert type(result) is CompleteArtifactBuildResult
        assert tuple(result.__dataclass_fields__) == (
            "silver_result",
            "staged_tables",
            "exact_link_build_result",
            "exact_evidence_verification_observations",
            "observations",
            "source_audit_report",
        )
        assert result.silver_result is silver_result
        assert len(result.staged_tables.verifications) == 13
        assert custody._candidate_state == "CLOSED"


@pytest.mark.parametrize("fault", ["link-build", "relation", "report", "custody-close"])
def test_complete_builder_closes_exact_custody_once_across_link_and_postextension_faults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    from finproof.data.artifacts import builder
    from finproof.data.artifacts.builder import build_complete_for_session
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.reports import SourceAuditReport
    from finproof.data.artifacts.staging import ExactLinkCandidateStoreCustody

    def fail(*_args: object, **_kwargs: object) -> None:
        raise OSError(fault)

    with _empty_link_stage(tmp_path, build=False) as values:
        session, config, silver_result, custody, _missing = values
        monkeypatch.setattr(builder, "build_silver_for_session", lambda **_kwargs: silver_result)
        monkeypatch.setattr(
            builder,
            "take_exact_link_candidate_store",
            lambda **_kwargs: custody,
        )
        original_close = ExactLinkCandidateStoreCustody.close
        close_calls = 0

        def close_once(self: ExactLinkCandidateStoreCustody) -> None:
            nonlocal close_calls
            close_calls += 1
            if fault == "custody-close":
                fail()
            original_close(self)

        monkeypatch.setattr(ExactLinkCandidateStoreCustody, "close", close_once)
        if fault == "link-build":
            monkeypatch.setattr(builder, "_build_and_extend_exact_links", fail)
        elif fault == "relation":
            monkeypatch.setattr(builder, "verify_exact_link_evidence", fail)
        elif fault == "report":
            monkeypatch.setattr(SourceAuditReport, "from_complete_observations", fail)

        with pytest.raises(ArtifactContractError):
            build_complete_for_session(
                session=session,
                config=config,
                versions=session._versions,
            )
        assert close_calls == 1
        if fault != "custody-close":
            assert custody._candidate_state == "CLOSED"
        registered = tuple(item[0] for item in session._staged_sets.values())
        assert len(registered) == 1
        assert len(registered[0].verifications) == (9 if fault == "link-build" else 11)


def test_complete_result_validator_rejects_copy_forge_mutation_open_custody_and_nonlive_successor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from copy import copy

    from finproof.data.artifacts import builder
    from finproof.data.artifacts.builder import (
        CompleteArtifactBuildResult,
        build_complete_for_session,
        require_complete_artifact_build_result,
    )
    from finproof.data.artifacts.errors import ArtifactContractError

    with _empty_link_stage(tmp_path, build=False) as values:
        session, config, silver_result, custody, _missing = values
        monkeypatch.setattr(builder, "build_silver_for_session", lambda **_kwargs: silver_result)
        monkeypatch.setattr(
            builder,
            "take_exact_link_candidate_store",
            lambda **_kwargs: custody,
        )
        result = build_complete_for_session(
            session=session,
            config=config,
            versions=session._versions,
        )

        assert require_complete_artifact_build_result(result) is result
        exact_links = result.observations.exact_links
        object.__setattr__(exact_links, "expected", 1)
        object.__setattr__(exact_links, "observed", 1)
        with pytest.raises((TypeError, ValueError)):
            require_complete_artifact_build_result(result)
        object.__setattr__(exact_links, "expected", 0)
        object.__setattr__(exact_links, "observed", 0)
        pair_hash = result.observations.exact_link_pair_sha256
        original_hash = pair_hash.expected
        object.__setattr__(pair_hash, "expected", "a" * 64)
        object.__setattr__(pair_hash, "observed", "a" * 64)
        with pytest.raises((TypeError, ValueError)):
            require_complete_artifact_build_result(result)
        object.__setattr__(pair_hash, "expected", original_hash)
        object.__setattr__(pair_hash, "observed", original_hash)
        with pytest.raises((TypeError, ValueError)):
            require_complete_artifact_build_result(copy(result))
        forged = object.__new__(CompleteArtifactBuildResult)
        for name in result.__dataclass_fields__:
            object.__setattr__(forged, name, getattr(result, name))
        object.__setattr__(forged, "_issuance", result._issuance)
        with pytest.raises((TypeError, ValueError)):
            require_complete_artifact_build_result(forged)
        original_report = result.source_audit_report
        object.__setattr__(result, "source_audit_report", original_report.model_copy())
        with pytest.raises((TypeError, ValueError)):
            require_complete_artifact_build_result(result)
        object.__setattr__(result, "source_audit_report", original_report)
        custody._candidate_state = "EXHAUSTED"
        with pytest.raises((TypeError, ValueError)):
            require_complete_artifact_build_result(result)
        custody._candidate_state = "CLOSED"

    with pytest.raises((ArtifactContractError, TypeError, ValueError)):
        require_complete_artifact_build_result(result)
