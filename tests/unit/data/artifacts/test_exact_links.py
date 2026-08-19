"""Exact raw-identifier link construction and evidence contracts."""

# mypy: disable-error-code="arg-type,attr-defined,func-returns-value"

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from finproof.data.artifacts.serialization import ExactCrossSourceLinkRecord
from finproof.data.artifacts.staging import (
    DomesticExactLinkCandidate,
    ExactLinkCandidateJoinRow,
    ExactLinkIdentifierSource,
    FundExactLinkCandidate,
)
from finproof.domain.locators import SourceCellLocator


def _source(*, table: str, column: str, row: int, raw: str) -> ExactLinkIdentifierSource:
    return ExactLinkIdentifierSource(
        raw_identifier=raw,
        locator=SourceCellLocator(
            source_table=table,
            source_file=PurePosixPath(f"data/{table}.xlsx"),
            source_sheet="Sheet1",
            source_row_number=row,
            source_column_name=column,
            source_column_number=1,
            source_column_letter="A",
            source_checksum="a" * 64,
            source_snapshot_date=date(2026, 7, 11),
            source_applicable_date=None,
        ),
    )


def _candidate(
    *,
    raw: str = "KR7000000001",
    left_id: str = "L1",
    right_id: str = "R1",
    right_rows: tuple[int, ...] = (2,),
) -> ExactLinkCandidateJoinRow:
    return ExactLinkCandidateJoinRow(
        matched_raw_identifier=raw,
        left=DomesticExactLinkCandidate(
            left_product_id=left_id,
            source_product_type="ETF",
            identifier=_source(
                table="PREF01N001",
                column="pd_itm_no",
                row=2,
                raw=raw,
            ),
        ),
        right=FundExactLinkCandidate(
            right_product_id=right_id,
            identifiers=tuple(
                _source(
                    table="PRFD01N001",
                    column="ksd_itm_no",
                    row=row,
                    raw=raw,
                )
                for row in right_rows
            ),
        ),
    )


def test_exact_untrimmed_candidate_match_builds_exact_cp3_link_record() -> None:
    from finproof.data.artifacts.links import _link_from_candidate
    from finproof.data.artifacts.serialization import ExactCrossSourceLinkRecord

    candidate = _candidate(raw=" KR7000000001 ")
    link = _link_from_candidate(candidate)
    expected_link_id = hashlib.sha256(
        b"\0".join(
            value.encode("utf-8")
            for value in (
                "cross_source.domestic_etf_public_fund.exact_raw_identifier",
                "1.0.0",
                "silver_domestic_listed_product",
                "L1",
                "silver_fund_item",
                "R1",
                " KR7000000001 ",
            )
        )
    ).hexdigest()

    assert type(link) is ExactCrossSourceLinkRecord
    assert link == ExactCrossSourceLinkRecord(
        link_id=expected_link_id,
        left_table="silver_domestic_listed_product",
        left_product_id="L1",
        left_identifier_field="pd_itm_no",
        right_table="silver_fund_item",
        right_product_id="R1",
        right_identifier_field="ksd_itm_no",
        matched_raw_identifier=" KR7000000001 ",
        link_type="exact_identifier",
        confidence=Decimal("1.0"),
        rule_id="cross_source.domestic_etf_public_fund.exact_raw_identifier",
        rule_version="1.0.0",
    )


def test_exact_link_builder_rejects_one_left_to_multiple_rights_before_output() -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.links import _reject_left_conflicts

    candidates = (
        _candidate(left_id="L1", right_id="R1"),
        _candidate(left_id="L1", right_id="R2"),
    )

    with pytest.raises(ArtifactContractError) as captured:
        _reject_left_conflicts(candidates)

    assert captured.value.code is ArtifactErrorCode.EXACT_LINK_CONFLICT
    assert captured.value.internal_context == {"reason": "left_identifier_conflict"}


@pytest.mark.parametrize("case", ["right-conflict", "duplicate-candidate-key"])
def test_exact_link_builder_rejects_one_right_to_multiple_lefts_before_output(
    case: str,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.links import _reject_right_and_duplicate_conflicts

    candidates = (
        (_candidate(left_id="L1", right_id="R1"), _candidate(left_id="L2", right_id="R1"))
        if case == "right-conflict"
        else (_candidate(left_id="L1", right_id="R1"),) * 2
    )

    with pytest.raises(ArtifactContractError) as captured:
        _reject_right_and_duplicate_conflicts(candidates)

    assert captured.value.code is ArtifactErrorCode.EXACT_LINK_CONFLICT
    assert captured.value.internal_context == {
        "reason": (
            "right_identifier_conflict" if case == "right-conflict" else "duplicate_candidate_key"
        )
    }


def test_exact_evidence_emits_one_left_and_all_contiguous_ordered_right_locators() -> None:
    from finproof.data.artifacts.links import _evidence_from_candidate, _link_from_candidate
    from finproof.data.artifacts.serialization import ExactCrossSourceLinkEvidenceRecord

    candidate = _candidate(right_rows=(2, 5, 9))
    link = _link_from_candidate(candidate)
    evidence = _evidence_from_candidate(candidate, link)

    assert len(evidence) == 4
    assert all(type(row) is ExactCrossSourceLinkEvidenceRecord for row in evidence)
    assert tuple(
        (row.evidence_role, row.evidence_role_order, row.evidence_ordinal) for row in evidence
    ) == (
        ("left_identifier", 0, 0),
        ("right_identifier", 1, 0),
        ("right_identifier", 1, 1),
        ("right_identifier", 1, 2),
    )
    assert tuple(row.link_id for row in evidence) == (link.link_id,) * 4
    assert tuple(row.raw_identifier for row in evidence) == (candidate.matched_raw_identifier,) * 4
    assert evidence[0].source_column_name == "pd_itm_no"
    assert tuple(row.source_row_number for row in evidence[1:]) == (2, 5, 9)
    assert tuple(row.source_column_name for row in evidence[1:]) == ("ksd_itm_no",) * 3


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "duplicate",
        "reordered",
        "role",
        "ordinal",
        "field",
        "raw",
        "parent",
        "extra-locator",
    ],
)
def test_exact_evidence_rejects_missing_duplicate_reordered_role_ordinal_field_raw_parent_and_extra_locator(  # noqa: E501
    case: str,
) -> None:
    from finproof.data.artifacts.links import (
        _evidence_from_candidate,
        _link_from_candidate,
        _require_candidate_evidence,
    )

    candidate = _candidate(right_rows=(2, 5))
    link = _link_from_candidate(candidate)
    valid = _evidence_from_candidate(candidate, link)
    if case == "missing":
        invalid = valid[:-1]
    elif case == "duplicate":
        invalid = (*valid, valid[-1])
    elif case == "reordered":
        invalid = (valid[1], valid[0], valid[2])
    elif case == "role":
        invalid = (
            valid[0],
            valid[1].model_copy(update={"evidence_role": "left_identifier"}),
            valid[2],
        )
    elif case == "ordinal":
        invalid = (valid[0], valid[1].model_copy(update={"evidence_ordinal": 7}), valid[2])
    elif case == "field":
        invalid = (
            valid[0],
            valid[1].model_copy(update={"source_column_name": "itm_no"}),
            valid[2],
        )
    elif case == "raw":
        invalid = (valid[0].model_copy(update={"raw_identifier": "DIFFERENT"}), *valid[1:])
    elif case == "parent":
        invalid = (valid[0].model_copy(update={"link_id": "b" * 64}), *valid[1:])
    else:
        invalid = (
            *valid,
            valid[-1].model_copy(update={"evidence_ordinal": 2, "source_row_number": 99}),
        )

    with pytest.raises(ValueError, match="evidence"):
        _require_candidate_evidence(candidate, link, invalid)


def test_reversed_candidates_produce_identical_order_ids_records_and_evidence() -> None:
    from finproof.data.artifacts.links import _build_link_and_evidence_records

    candidates = (
        _candidate(raw="RAW-B", left_id="L2", right_id="R2", right_rows=(4, 7)),
        _candidate(raw="RAW-A", left_id="L1", right_id="R1", right_rows=(2, 3)),
    )

    forward = _build_link_and_evidence_records(candidates)
    reverse = _build_link_and_evidence_records(tuple(reversed(candidates)))

    assert forward == reverse
    links, evidence = forward
    assert tuple((link.left_product_id, link.right_product_id) for link in links) == (
        ("L1", "R1"),
        ("L2", "R2"),
    )
    assert tuple(
        (row.link_id, row.evidence_role_order, row.evidence_ordinal) for row in evidence
    ) == tuple(
        sorted((row.link_id, row.evidence_role_order, row.evidence_ordinal) for row in evidence)
    )


def test_link_module_defines_no_parallel_gold_record_model_or_dto() -> None:
    import inspect

    from finproof.data.artifacts import links
    from finproof.data.artifacts.serialization import (
        ExactCrossSourceLinkEvidenceRecord,
        ExactCrossSourceLinkRecord,
    )

    source = inspect.getsource(links)
    assert links.ExactCrossSourceLinkRecord is ExactCrossSourceLinkRecord
    assert links.ExactCrossSourceLinkEvidenceRecord is ExactCrossSourceLinkEvidenceRecord
    assert "class ExactCrossSourceLink:" not in source
    assert "class ExactCrossSourceLinkEvidence:" not in source
    assert "TypedDict" not in source


@pytest.mark.parametrize(
    "case",
    [
        "expected-bool",
        "expected-negative",
        "expected-over-bound",
        "foreign-row",
        "constant",
        "order",
        "duplicate",
        "empty-id",
        "nul",
        "tab",
        "cr",
        "lf",
        "surrogate",
        "too-long",
        "short",
        "long",
    ],
)
def test_canonical_pair_tsv_rejects_wrong_type_constants_order_duplicates_utf8_controls_and_count(
    case: str,
) -> None:
    from finproof.data.artifacts.links import (
        _build_link_and_evidence_records,
        canonical_link_pair_tsv,
    )

    links, _evidence = _build_link_and_evidence_records(
        (
            _candidate(raw="RAW-A", left_id="L1", right_id="R1"),
            _candidate(raw="RAW-B", left_id="L2", right_id="R2"),
        )
    )
    rows: object = links
    expected: object = 2
    if case == "expected-bool":
        expected = True
    elif case == "expected-negative":
        expected = -1
    elif case == "expected-over-bound":
        expected = 65_537
    elif case == "foreign-row":
        rows = (object(),)
        expected = 1
    elif case == "constant":
        rows = (links[0].model_copy(update={"rule_version": "2.0.0"}), links[1])
    elif case == "order":
        rows = tuple(reversed(links))
    elif case == "duplicate":
        rows = (links[0], links[0])
    elif case in {"empty-id", "nul", "tab", "cr", "lf", "surrogate", "too-long"}:
        replacement = {
            "empty-id": "",
            "nul": "L\0",
            "tab": "L\t",
            "cr": "L\r",
            "lf": "L\n",
            "surrogate": "L\ud800",
            "too-long": "가" * 1_366,
        }[case]
        rows = (links[0].model_copy(update={"left_product_id": replacement}), links[1])
    elif case == "short":
        rows = links[:1]
    else:
        rows = (*links, links[-1].model_copy(update={"left_product_id": "L3"}))

    with pytest.raises((TypeError, UnicodeError, ValueError)):
        canonical_link_pair_tsv(rows, expected_links=expected)


def test_canonical_pair_tsv_is_one_pass_buffer_bounded_and_hashes_exact_bytes() -> None:
    from finproof.data.artifacts.links import (
        _build_link_and_evidence_records,
        canonical_link_pair_tsv,
        exact_link_pair_sha256,
    )

    links, _evidence = _build_link_and_evidence_records(
        tuple(
            _candidate(
                raw=f"RAW-{index:03d}",
                left_id=f"L{index:03d}",
                right_id=f"R{index:03d}",
            )
            for index in range(128)
        )
    )

    class OnePassRows:
        def __init__(self) -> None:
            self.iterations = 0

        def __iter__(self) -> Iterator[ExactCrossSourceLinkRecord]:
            self.iterations += 1
            if self.iterations != 1:
                raise AssertionError("pair rows were iterated more than once")
            yield from links

    rows = OnePassRows()
    payload = canonical_link_pair_tsv(rows, expected_links=len(links))

    assert rows.iterations == 1
    assert payload == b"".join(
        f"{row.left_product_id}\t{row.right_product_id}\n".encode() for row in links
    )
    assert len(payload) <= len(links) * 8_194
    assert exact_link_pair_sha256(payload) == hashlib.sha256(payload).hexdigest()
    with pytest.raises(TypeError):
        exact_link_pair_sha256(bytearray(payload))


def test_exact_link_build_result_is_factory_only_provenance_bound_and_count_and_batch_bounded(
    tmp_path: Path,
) -> None:
    from copy import copy
    from datetime import UTC, datetime

    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.config import ArtifactBuildConfig, ArtifactBuildOptions
    from finproof.data.artifacts.links import ExactLinkBuildResult, build_exact_links
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

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / "repository")
    loaded = ArtifactBuildConfig.load(
        settings.artifact_build_config_path,
        repository_root=settings.repository_root,
        versions=versions,
    )
    config_payload = loaded.model_dump(mode="python")
    config_payload["silver_counts"] = {
        "bond_instrument": 1,
        "domestic_listed_product": 1,
        "overseas_listed_product": 1,
        "fund_item": 1,
        "fund_item_attribute": 1,
    }
    config_payload["quarantine_source_rows"] = 0
    config_payload["exact_links"] = {
        "links": 1,
        "evidence": 2,
        "pair_sha256": hashlib.sha256(b"L1\tR1\n").hexdigest(),
    }
    config = ArtifactBuildConfig.model_validate(config_payload, strict=True)
    candidate = _candidate(left_id="L1", right_id="R1")

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

        result = build_exact_links(
            silver_result=silver_result,
            custody=custody,
            config=config,
        )

        assert type(result) is ExactLinkBuildResult
        assert tuple(result.__dataclass_fields__) == (
            "links",
            "evidence",
            "canonical_pair_tsv",
            "pair_sha256",
            "max_candidate_batch_rows",
        )
        assert len(result.links) == 1
        assert len(result.evidence) == 2
        assert result.canonical_pair_tsv == b"L1\tR1\n"
        assert result.pair_sha256 == config.exact_links.pair_sha256
        assert result.max_candidate_batch_rows == 1
        assert result._issuance.silver_result is silver_result
        assert result._issuance.custody is custody
        with pytest.raises(TypeError):
            ExactLinkBuildResult()
        with pytest.raises(TypeError):
            copy(result)


@pytest.mark.parametrize("case", ["valid", "missing", "parent", "raw", "bronze-count"])
def test_evidence_relation_is_bidirectionally_equal_to_bronze_cells_and_parent_links(
    case: str,
) -> None:
    from finproof.data.artifacts.links import (
        _build_link_and_evidence_records,
        _verify_evidence_relationships,
    )
    from finproof.data.artifacts.reports import ExactEvidenceBronzeJoinObservations

    candidate = _candidate(right_rows=(2, 3))
    links, evidence = _build_link_and_evidence_records((candidate,))
    observed = ExactEvidenceBronzeJoinObservations(
        matched_bronze_cells=3,
        max_batch_rows=3,
    )
    if case == "missing":
        evidence = evidence[:-1]
    elif case == "parent":
        evidence = (
            evidence[0].model_copy(update={"link_id": "f" * 64}),
            *evidence[1:],
        )
    elif case == "raw":
        evidence = (
            evidence[0].model_copy(update={"raw_identifier": "changed"}),
            *evidence[1:],
        )
    elif case == "bronze-count":
        observed = ExactEvidenceBronzeJoinObservations(
            matched_bronze_cells=2,
            max_batch_rows=2,
        )
    if case == "valid":
        assert (
            _verify_evidence_relationships(
                links=links,
                evidence=evidence,
                bronze=observed,
            )
            is None
        )
    else:
        with pytest.raises(ValueError, match=r"evidence|incomplete|changed"):
            _verify_evidence_relationships(
                links=links,
                evidence=evidence,
                bronze=observed,
            )


def test_linked_record_verification_filters_exact_ids_before_strict_json_parse() -> None:
    from pydantic import BaseModel, ConfigDict

    from finproof.data.artifacts.links import _strict_parse_filtered_linked_records
    from finproof.data.artifacts.reports import LinkedRecordJson

    class Record(BaseModel):
        model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

        product_id: str

    batches = (
        (
            LinkedRecordJson(product_id="ignore", record_json="not-json"),
            LinkedRecordJson(
                product_id="keep",
                record_json='{"product_id":"keep"}',
            ),
        ),
    )

    assert _strict_parse_filtered_linked_records(
        batches=batches,
        exact_ids=("keep",),
        model_type=Record,
    ) == (Record(product_id="keep"),)


def test_linked_fund_verifier_reuses_canonical_json_transport_and_physical_agreement() -> None:
    from finproof.data.artifacts.links import _verify_linked_side
    from finproof.data.artifacts.reports import LinkedRecordJson
    from finproof.data.artifacts.serialization import (
        canonical_record_json,
        logical_table_row,
        serialize_table_row,
    )
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from finproof.data.normalization.public_funds import (
        collapse_fund_items,
        normalize_fund_attribute,
    )
    from finproof.domain.public_funds import FundItem
    from tests.helpers.source_rows import source_row

    normalized = normalize_fund_attribute(source_row("PRFD01N001"))
    assert normalized.record is not None
    fund = collapse_fund_items((normalized.record,)).items[0]
    fund_id = str(fund.fund_item_id.representative.normalized_value)
    record_json = canonical_record_json(fund)

    class Verifier:
        def __init__(self, payload: str) -> None:
            self._payload = payload

        def iter_linked_record_json(
            self,
            *,
            tables: Any,
            side: Any,
            exact_ids: tuple[str, ...],
        ) -> Iterator[tuple[LinkedRecordJson, ...]]:
            del tables
            assert side.value == "fund"
            assert exact_ids == (fund_id,)
            yield (LinkedRecordJson(product_id=fund_id, record_json=self._payload),)

    assert _verify_linked_side(
        relation_verifier=Verifier(record_json),
        tables=object(),
        side_name="fund",
        exact_ids=(fund_id,),
        model_type=FundItem,
    ) == (1, 1)
    with pytest.raises(ValueError, match="canonical"):
        _verify_linked_side(
            relation_verifier=Verifier(record_json + " "),
            tables=object(),
            side_name="fund",
            exact_ids=(fund_id,),
            model_type=FundItem,
        )

    spec = TABLE_SPEC_BY_NAME["silver_fund_item"]
    physical = dict(serialize_table_row(spec, fund))
    assert logical_table_row(spec, physical)["record_json"] == record_json
    with pytest.raises(ValueError, match="typed projection"):
        logical_table_row(spec, {**physical, "fund_item_id": "foreign"})


def test_exact_evidence_observations_are_factory_only_owned_consistent_and_bounded() -> None:
    from copy import copy

    from finproof.data.artifacts.links import _issue_exact_evidence_observations
    from finproof.data.artifacts.reports import (
        ExactEvidenceVerificationObservations,
        ExpectedObservedCount,
        ExpectedObservedSha256,
    )

    owner = object()
    observed = _issue_exact_evidence_observations(
        owner=owner,
        exact_links=ExpectedObservedCount(expected=1, observed=1),
        exact_link_evidence=ExpectedObservedCount(expected=3, observed=3),
        exact_link_pair_sha256=ExpectedObservedSha256(
            expected="a" * 64,
            observed="a" * 64,
        ),
        matched_bronze_cells=3,
        matched_left_records=1,
        matched_right_records=1,
        max_relation_batch_rows=3,
    )

    assert type(observed) is ExactEvidenceVerificationObservations
    assert observed._issuance.owner is owner
    assert tuple(observed.__dataclass_fields__) == (
        "exact_links",
        "exact_link_evidence",
        "exact_link_pair_sha256",
        "matched_bronze_cells",
        "matched_left_records",
        "matched_right_records",
        "max_relation_batch_rows",
    )
    with pytest.raises(TypeError):
        ExactEvidenceVerificationObservations()
    with pytest.raises(TypeError):
        copy(observed)
    with pytest.raises(ValueError, match="inconsistent"):
        _issue_exact_evidence_observations(
            owner=owner,
            exact_links=observed.exact_links,
            exact_link_evidence=observed.exact_link_evidence,
            exact_link_pair_sha256=observed.exact_link_pair_sha256,
            matched_bronze_cells=3,
            matched_left_records=1,
            matched_right_records=1,
            max_relation_batch_rows=65_537,
        )
