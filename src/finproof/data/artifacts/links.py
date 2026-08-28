"""Exact raw-identifier link construction over typed staged candidates."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel

from finproof.data.artifacts.config import ArtifactBuildConfig
from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
from finproof.data.artifacts.parquet_io import (
    ParquetBatchWriter,
    StagedParquetSet,
    StagedParquetVerification,
    verify_staged_parquet_table,
)
from finproof.data.artifacts.reports import (
    BoundedRelationVerifier,
    ExactEvidenceBronzeJoinObservations,
    ExactEvidenceVerificationObservations,
    ExpectedObservedCount,
    ExpectedObservedSha256,
    LinkedRecordJson,
    _ExactEvidenceVerificationIssuance,
)
from finproof.data.artifacts.serialization import (
    ExactCrossSourceLinkEvidenceRecord,
    ExactCrossSourceLinkRecord,
    logical_table_row,
    serialize_table_row,
)
from finproof.data.artifacts.silver import SilverBuildResult, require_silver_build_result
from finproof.data.artifacts.staging import (
    ArtifactBuildSession,
    ExactLinkCandidateJoinRow,
    ExactLinkCandidateStoreCustody,
)
from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME, TableSpec

_RULE_ID: Literal["cross_source.domestic_etf_public_fund.exact_raw_identifier"] = (
    "cross_source.domestic_etf_public_fund.exact_raw_identifier"
)
_RULE_VERSION: Literal["1.0.0"] = "1.0.0"
_LEFT_TABLE: Literal["silver_domestic_listed_product"] = "silver_domestic_listed_product"
_RIGHT_TABLE: Literal["silver_fund_item"] = "silver_fund_item"


class _ExactLinkBuildResultProvenance:
    __slots__ = ("_issuance",)

    _issuance: _ExactLinkBuildResultIssuance


@dataclass(frozen=True, init=False, slots=True)
class ExactLinkBuildResult(_ExactLinkBuildResultProvenance):
    """Builder-issued exact-link records, evidence, and canonical pair facts."""

    links: tuple[ExactCrossSourceLinkRecord, ...]
    evidence: tuple[ExactCrossSourceLinkEvidenceRecord, ...]
    canonical_pair_tsv: bytes
    pair_sha256: str
    max_candidate_batch_rows: int

    def __new__(cls, *args: object, **kwargs: object) -> Self:
        del args, kwargs
        raise TypeError("ExactLinkBuildResult is builder-issued")

    def __copy__(self) -> Self:
        raise TypeError("ExactLinkBuildResult cannot be copied")

    def __deepcopy__(self, memo: object) -> Self:
        del memo
        raise TypeError("ExactLinkBuildResult cannot be copied")

    def __reduce__(self) -> tuple[object, ...]:
        raise TypeError("ExactLinkBuildResult cannot be serialized")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del kwargs
        raise TypeError("ExactLinkBuildResult cannot be subclassed")


class _ExactLinkBuildResultIssuance:
    __slots__ = ("custody", "facts", "silver_result", "value")

    def __init__(
        self,
        value: ExactLinkBuildResult,
        *,
        silver_result: SilverBuildResult,
        custody: ExactLinkCandidateStoreCustody,
    ) -> None:
        self.value = value
        self.silver_result = silver_result
        self.custody = custody
        self.facts = _exact_link_result_facts(value)


def build_exact_links(
    *,
    silver_result: SilverBuildResult,
    custody: ExactLinkCandidateStoreCustody,
    config: ArtifactBuildConfig,
) -> ExactLinkBuildResult:
    """Consume one exact candidate stream and seal its canonical evidence."""
    exact_silver = require_silver_build_result(silver_result)
    _require_exact_build_inputs(
        silver_result=exact_silver,
        custody=custody,
        config=config,
    )
    candidate_limit = config.exact_link_candidate_limit
    candidates, max_batch_rows = _consume_candidate_batches(
        custody.iter_candidate_join_batches(),
        expected_links=candidate_limit,
    )
    links, evidence = _build_link_and_evidence_records(candidates)
    if len(links) > candidate_limit or len(evidence) != len(links) * 2:
        raise ValueError("exact link or evidence count exceeded the closed bound")
    pair_tsv = canonical_link_pair_tsv(links, expected_links=len(links))
    pair_sha256 = exact_link_pair_sha256(pair_tsv)
    custody.admit_exact_evidence(iter(evidence))
    value = object.__new__(ExactLinkBuildResult)
    object.__setattr__(value, "links", links)
    object.__setattr__(value, "evidence", evidence)
    object.__setattr__(value, "canonical_pair_tsv", pair_tsv)
    object.__setattr__(value, "pair_sha256", pair_sha256)
    object.__setattr__(value, "max_candidate_batch_rows", max_batch_rows)
    object.__setattr__(
        value,
        "_issuance",
        _ExactLinkBuildResultIssuance(
            value,
            silver_result=exact_silver,
            custody=custody,
        ),
    )
    return value


def _consume_candidate_batches(
    batches: Iterable[tuple[ExactLinkCandidateJoinRow, ...]],
    *,
    expected_links: int,
) -> tuple[tuple[ExactLinkCandidateJoinRow, ...], int]:
    if type(expected_links) is not int or expected_links != 217:
        raise ValueError("expected candidate count must equal the immutable ceiling")
    rows: list[ExactLinkCandidateJoinRow] = []
    max_batch_rows = 0
    for batch in batches:
        if type(batch) is not tuple or any(
            type(row) is not ExactLinkCandidateJoinRow for row in batch
        ):
            raise ValueError("exact candidate batch changed")
        if len(batch) > 217:
            raise ValueError("exact candidate batch exceeded immutable ceiling")
        max_batch_rows = max(max_batch_rows, len(batch))
        rows.extend(batch)
        if len(rows) > expected_links:
            raise ValueError("exact candidate count exceeded expectation")
    return tuple(rows), max_batch_rows


def _require_exact_build_inputs(
    *,
    silver_result: SilverBuildResult,
    custody: ExactLinkCandidateStoreCustody,
    config: ArtifactBuildConfig,
) -> None:
    if type(config) is not ArtifactBuildConfig:
        raise TypeError("exact-link build config must have the exact runtime type")
    validated = ArtifactBuildConfig.model_validate(
        config.model_dump(mode="python"),
        strict=True,
    )
    counts = (
        validated.exact_link_candidate_limit,
        validated.exact_link_candidate_limit * 2,
    )
    if (
        validated != config
        or counts != (217, 434)
        or type(custody) is not ExactLinkCandidateStoreCustody
    ):
        raise ValueError("exact-link build inputs changed")
    issuance = silver_result._issuance
    if (
        issuance.candidate_custody is not None
        or issuance.authorization.candidate_custody is not custody
    ):
        raise ValueError("exact-link custody is not bound to the Silver result")
    custody._require_live()


def _exact_link_result_facts(value: ExactLinkBuildResult) -> tuple[object, ...]:
    return (
        value.links,
        value.evidence,
        value.canonical_pair_tsv,
        value.pair_sha256,
        value.max_candidate_batch_rows,
    )


def _require_exact_link_build_result(value: object) -> ExactLinkBuildResult:
    value = _require_exact_link_build_result_facts(value)
    issuance = object.__getattribute__(value, "_issuance")
    require_silver_build_result(issuance.silver_result)
    issuance.custody._require_live()
    return value


def _require_exact_link_build_result_facts(value: object) -> ExactLinkBuildResult:
    """Deeply revalidate exact-link facts without assuming custody is still live."""
    if type(value) is not ExactLinkBuildResult:
        raise TypeError("exact-link result must have the exact runtime type")
    issuance = object.__getattribute__(value, "_issuance")
    if (
        type(issuance) is not _ExactLinkBuildResultIssuance
        or issuance.value is not value
        or issuance.facts != _exact_link_result_facts(value)
        or type(value.links) is not tuple
        or type(value.evidence) is not tuple
        or any(type(row) is not ExactCrossSourceLinkRecord for row in value.links)
        or any(type(row) is not ExactCrossSourceLinkEvidenceRecord for row in value.evidence)
        or type(value.canonical_pair_tsv) is not bytes
        or type(value.pair_sha256) is not str
        or type(value.max_candidate_batch_rows) is not int
        or not 0 <= value.max_candidate_batch_rows <= 217
        or len(value.links) > 217
        or len(value.evidence) > 434
        or canonical_link_pair_tsv(value.links, expected_links=len(value.links))
        != value.canonical_pair_tsv
        or exact_link_pair_sha256(value.canonical_pair_tsv) != value.pair_sha256
    ):
        raise ValueError("exact-link result issuance changed")
    for link_row in value.links:
        _require_frozen_link_record(link_row)
    for evidence_row in value.evidence:
        if (
            ExactCrossSourceLinkEvidenceRecord.model_validate(
                evidence_row.model_dump(mode="python"),
                strict=True,
            )
            != evidence_row
        ):
            raise ValueError("exact-link evidence fact changed")
    _verify_evidence_relationships(
        links=value.links,
        evidence=value.evidence,
        bronze=ExactEvidenceBronzeJoinObservations(
            matched_bronze_cells=len(value.evidence),
            max_batch_rows=0,
        ),
    )
    return value


def _write_exact_gold_verifications(
    *,
    owner: ArtifactBuildSession,
    build_result: ExactLinkBuildResult,
) -> tuple[StagedParquetVerification, StagedParquetVerification]:
    exact = _require_exact_link_build_result(build_result)
    if type(owner) is not ArtifactBuildSession or exact._issuance.custody._owner is not owner:
        raise ValueError("Gold exact-link writer owner changed")
    specs = (
        TABLE_SPEC_BY_NAME["gold_exact_cross_source_link"],
        TABLE_SPEC_BY_NAME["gold_exact_cross_source_link_evidence"],
    )
    rows = (exact.links, exact.evidence)
    leaves = tuple(owner.claim_parquet_leaf(spec) for spec in specs)
    writers: list[ParquetBatchWriter] = []
    try:
        for spec, leaf, records in zip(specs, leaves, rows, strict=True):
            writer = ParquetBatchWriter(spec, leaf)
            writers.append(writer)
            if records:
                writer.write_batch(tuple(serialize_table_row(spec, record) for record in records))
            writer.close()
            writers.pop()
        verifications = tuple(
            verify_staged_parquet_table(owner=owner, leaf=leaf, spec=spec)
            for spec, leaf in zip(specs, leaves, strict=True)
        )
        return verifications[0], verifications[1]
    except BaseException:
        for writer in reversed(writers):
            with suppress(BaseException):
                writer.abort()
        raise


def _extend_silver_with_exact_links(
    *,
    silver_result: SilverBuildResult,
    owner: ArtifactBuildSession,
    verifications: tuple[StagedParquetVerification, StagedParquetVerification],
) -> StagedParquetSet:
    exact = require_silver_build_result(silver_result)
    if (
        type(owner) is not ArtifactBuildSession
        or exact.staged_tables._owner is not owner
        or type(verifications) is not tuple
        or len(verifications) != 2
        or any(type(item) is not StagedParquetVerification for item in verifications)
        or tuple(item.logical.name for item in verifications)
        != (
            "gold_exact_cross_source_link",
            "gold_exact_cross_source_link_evidence",
        )
    ):
        raise ValueError("exact Gold extension inputs changed")
    return exact.staged_tables.extend_verified(
        owner=owner,
        verifications=verifications,
    )


def _build_and_extend_exact_links(
    *,
    silver_result: SilverBuildResult,
    custody: ExactLinkCandidateStoreCustody,
    config: ArtifactBuildConfig,
    owner: ArtifactBuildSession,
) -> tuple[ExactLinkBuildResult, StagedParquetSet]:
    build_result = build_exact_links(
        silver_result=silver_result,
        custody=custody,
        config=config,
    )
    verifications = _write_exact_gold_verifications(
        owner=owner,
        build_result=build_result,
    )
    successor = _extend_silver_with_exact_links(
        silver_result=silver_result,
        owner=owner,
        verifications=verifications,
    )
    return build_result, successor


def _verify_evidence_relationships(
    *,
    links: tuple[ExactCrossSourceLinkRecord, ...],
    evidence: tuple[ExactCrossSourceLinkEvidenceRecord, ...],
    bronze: ExactEvidenceBronzeJoinObservations,
) -> None:
    if (
        type(links) is not tuple
        or type(evidence) is not tuple
        or type(bronze) is not ExactEvidenceBronzeJoinObservations
        or any(type(row) is not ExactCrossSourceLinkRecord for row in links)
        or any(type(row) is not ExactCrossSourceLinkEvidenceRecord for row in evidence)
        or len(links) > 217
        or len(evidence) > 434
    ):
        raise TypeError("exact evidence relationships require exact tuples and facts")
    if len(evidence) != len(links) * 2:
        raise ValueError("exact evidence count is incomplete")
    ExactEvidenceBronzeJoinObservations.model_validate(
        bronze.model_dump(mode="python"),
        strict=True,
    )
    by_id: dict[str, ExactCrossSourceLinkRecord] = {}
    for link in links:
        _require_frozen_link_record(link)
        if link.link_id in by_id:
            raise ValueError("duplicate exact link parent")
        by_id[link.link_id] = link
    grouped: dict[str, list[ExactCrossSourceLinkEvidenceRecord]] = {
        link_id: [] for link_id in by_id
    }
    previous: tuple[str, int, int] | None = None
    for row in evidence:
        validated = ExactCrossSourceLinkEvidenceRecord.model_validate(
            row.model_dump(mode="python"), strict=True
        )
        key = (row.link_id, row.evidence_role_order, row.evidence_ordinal)
        parent = by_id.get(row.link_id)
        if (
            validated != row
            or (previous is not None and key <= previous)
            or parent is None
            or row.raw_identifier != parent.matched_raw_identifier
        ):
            raise ValueError("exact evidence parent/raw/order changed")
        grouped[row.link_id].append(row)
        previous = key
    for rows in grouped.values():
        if (
            len(rows) != 2
            or rows[0].evidence_role != "left_identifier"
            or rows[0].evidence_role_order != 0
            or rows[0].evidence_ordinal != 0
            or any(
                row.evidence_role != "right_identifier"
                or row.evidence_role_order != 1
                or row.evidence_ordinal != ordinal
                for ordinal, row in enumerate(rows[1:])
            )
        ):
            raise ValueError("exact evidence roles are incomplete")
    if bronze.matched_bronze_cells != len(evidence):
        raise ValueError("exact evidence/Bronze relation is incomplete")


def _strict_parse_filtered_linked_records(
    *,
    batches: Iterable[tuple[LinkedRecordJson, ...]],
    exact_ids: tuple[str, ...],
    model_type: type[BaseModel],
) -> tuple[BaseModel, ...]:
    if (
        type(exact_ids) is not tuple
        or len(exact_ids) > 217
        or any(type(value) is not str or not value for value in exact_ids)
        or tuple(sorted(set(exact_ids))) != exact_ids
        or not isinstance(model_type, type)
        or not issubclass(model_type, BaseModel)
    ):
        raise TypeError("linked record parse inputs changed")
    wanted = set(exact_ids)
    parsed: list[BaseModel] = []
    observed: list[str] = []
    for batch in batches:
        if type(batch) is not tuple or len(batch) > 217:
            raise ValueError("linked record batch is not bounded")
        for row in batch:
            if type(row) is not LinkedRecordJson:
                raise TypeError("linked record projection must be exact")
            if row.product_id not in wanted:
                continue
            model = model_type.model_validate_json(row.record_json, strict=True)
            product_id = getattr(model, "product_id", None)
            if product_id != row.product_id:
                raise ValueError("linked record ID and strict payload disagree")
            observed.append(row.product_id)
            parsed.append(model)
    if tuple(observed) != exact_ids:
        raise ValueError("linked record IDs are incomplete or reordered")
    return tuple(parsed)


def _issue_exact_evidence_observations(
    *,
    owner: object,
    exact_links: ExpectedObservedCount,
    exact_link_evidence: ExpectedObservedCount,
    exact_link_pair_sha256: ExpectedObservedSha256,
    matched_bronze_cells: int,
    matched_left_records: int,
    matched_right_records: int,
    max_relation_batch_rows: int,
) -> ExactEvidenceVerificationObservations:
    if (
        type(exact_links) is not ExpectedObservedCount
        or type(exact_link_evidence) is not ExpectedObservedCount
        or type(exact_link_pair_sha256) is not ExpectedObservedSha256
        or any(
            type(value) is not int or value < 0
            for value in (
                matched_bronze_cells,
                matched_left_records,
                matched_right_records,
                max_relation_batch_rows,
            )
        )
        or max_relation_batch_rows > 65_536
        or exact_links.observed > 217
        or exact_link_evidence.observed > 434
        or exact_link_evidence.observed != exact_links.observed * 2
        or matched_bronze_cells != exact_link_evidence.observed
        or matched_left_records != exact_links.observed
        or matched_right_records != exact_links.observed
    ):
        raise ValueError("exact evidence verification facts are inconsistent")
    for value, model_type in (
        (exact_links, ExpectedObservedCount),
        (exact_link_evidence, ExpectedObservedCount),
        (exact_link_pair_sha256, ExpectedObservedSha256),
    ):
        if model_type.model_validate(value.model_dump(mode="python"), strict=True) != value:
            raise ValueError("exact evidence expected/observed fact changed")
    result = object.__new__(ExactEvidenceVerificationObservations)
    object.__setattr__(result, "exact_links", exact_links)
    object.__setattr__(result, "exact_link_evidence", exact_link_evidence)
    object.__setattr__(result, "exact_link_pair_sha256", exact_link_pair_sha256)
    object.__setattr__(result, "matched_bronze_cells", matched_bronze_cells)
    object.__setattr__(result, "matched_left_records", matched_left_records)
    object.__setattr__(result, "matched_right_records", matched_right_records)
    object.__setattr__(result, "max_relation_batch_rows", max_relation_batch_rows)
    object.__setattr__(
        result,
        "_issuance",
        _ExactEvidenceVerificationIssuance(result, owner=owner),
    )
    return result


def verify_exact_link_evidence(
    *,
    tables: StagedParquetSet,
    relation_verifier: BoundedRelationVerifier,
    build_result: ExactLinkBuildResult,
    config: ArtifactBuildConfig,
) -> ExactEvidenceVerificationObservations:
    """Verify the sealed evidence relation and both linked wide-table sides."""
    from finproof.data.artifacts.quality_persistence import StagedBoundedRelationVerifier
    from finproof.data.artifacts.silver import require_silver_build_result_successor
    from finproof.domain.domestic_listed import ListedProduct
    from finproof.domain.public_funds import PublicFundItem

    if (
        type(relation_verifier) is not StagedBoundedRelationVerifier
        or type(build_result) is not ExactLinkBuildResult
        or type(config) is not ArtifactBuildConfig
    ):
        raise TypeError("exact evidence verification requires exact owned inputs")
    issuance = object.__getattribute__(build_result, "_issuance")
    if (
        type(issuance) is not _ExactLinkBuildResultIssuance
        or issuance.value is not build_result
        or issuance.facts != _exact_link_result_facts(build_result)
    ):
        raise ValueError("exact-link result issuance changed")
    require_silver_build_result_successor(
        silver_result=issuance.silver_result,
        successor=tables,
    )
    validated_config = ArtifactBuildConfig.model_validate(
        config.model_dump(mode="python"), strict=True
    )
    if validated_config != config:
        raise ValueError("exact evidence config changed")
    bronze = relation_verifier.verify_exact_evidence_to_bronze(
        tables=tables,
        gold_evidence=build_result.evidence,
    )
    _verify_evidence_relationships(
        links=build_result.links,
        evidence=build_result.evidence,
        bronze=bronze,
    )
    left_ids = tuple(sorted(link.left_product_id for link in build_result.links))
    right_ids = tuple(sorted(link.right_product_id for link in build_result.links))
    matched_left, left_max = _verify_linked_side(
        relation_verifier=relation_verifier,
        tables=tables,
        side_name="domestic",
        exact_ids=left_ids,
        model_type=ListedProduct,
    )
    matched_right, right_max = _verify_linked_side(
        relation_verifier=relation_verifier,
        tables=tables,
        side_name="fund",
        exact_ids=right_ids,
        model_type=PublicFundItem,
    )
    return _issue_exact_evidence_observations(
        owner=build_result,
        exact_links=ExpectedObservedCount(
            expected=len(build_result.links),
            observed=len(build_result.links),
        ),
        exact_link_evidence=ExpectedObservedCount(
            expected=len(build_result.evidence),
            observed=len(build_result.evidence),
        ),
        exact_link_pair_sha256=ExpectedObservedSha256(
            expected=build_result.pair_sha256,
            observed=build_result.pair_sha256,
        ),
        matched_bronze_cells=bronze.matched_bronze_cells,
        matched_left_records=matched_left,
        matched_right_records=matched_right,
        max_relation_batch_rows=max(bronze.max_batch_rows, left_max, right_max),
    )


def _verify_linked_side(
    *,
    relation_verifier: BoundedRelationVerifier,
    tables: StagedParquetSet,
    side_name: str,
    exact_ids: tuple[str, ...],
    model_type: type[BaseModel],
) -> tuple[int, int]:
    from finproof.data.artifacts.reports import ExactLinkedSide
    from finproof.domain.domestic_listed import ListedProduct
    from finproof.domain.public_funds import PublicFundItem

    observed: list[str] = []
    max_batch = 0
    for batch in relation_verifier.iter_linked_record_json(
        tables=tables,
        side=ExactLinkedSide(side_name),
        exact_ids=exact_ids,
    ):
        if type(batch) is not tuple or len(batch) > 217:
            raise ValueError("linked wide-record batch is not bounded")
        max_batch = max(max_batch, len(batch))
        for row in batch:
            if type(row) is not LinkedRecordJson:
                raise TypeError("linked wide-record projection changed")
            if model_type is ListedProduct:
                listed = _parse_registered_wide_record_json(
                    model_type=ListedProduct,
                    spec=TABLE_SPEC_BY_NAME["silver_domestic_listed_product"],
                    record_json=row.record_json,
                )
                product_id = listed.product_id.normalized_value
            elif model_type is PublicFundItem:
                fund = _parse_registered_wide_record_json(
                    model_type=PublicFundItem,
                    spec=TABLE_SPEC_BY_NAME["silver_fund_item"],
                    record_json=row.record_json,
                )
                product_id = fund.fund_item_id.normalized_value
            else:
                raise TypeError("linked wide-record model changed")
            if product_id != row.product_id:
                raise ValueError("linked wide-record ID disagrees with strict payload")
            observed.append(row.product_id)
    if tuple(observed) != exact_ids:
        raise ValueError("linked wide-record IDs are incomplete")
    return len(observed), max_batch


def _parse_registered_wide_record_json[ModelT: BaseModel](
    *,
    model_type: type[ModelT],
    spec: TableSpec,
    record_json: str,
) -> ModelT:
    parsed = model_type.model_validate_json(record_json)
    physical = dict(serialize_table_row(spec, parsed))
    if physical["record_json"] != record_json:
        raise ValueError("linked wide record_json is not canonical")
    logical_table_row(spec, physical)
    return parsed


def _link_from_candidate(
    candidate: ExactLinkCandidateJoinRow,
) -> ExactCrossSourceLinkRecord:
    if type(candidate) is not ExactLinkCandidateJoinRow:
        raise TypeError("exact link construction requires one exact candidate")
    fields = (
        _RULE_ID,
        _RULE_VERSION,
        _LEFT_TABLE,
        candidate.left.left_product_id,
        _RIGHT_TABLE,
        candidate.right.right_product_id,
        candidate.matched_raw_identifier,
    )
    link_id = hashlib.sha256(b"\0".join(value.encode("utf-8") for value in fields)).hexdigest()
    return ExactCrossSourceLinkRecord(
        link_id=link_id,
        left_table=_LEFT_TABLE,
        left_product_id=candidate.left.left_product_id,
        left_identifier_field="pd_itm_no",
        right_table=_RIGHT_TABLE,
        right_product_id=candidate.right.right_product_id,
        right_identifier_field="ksd_itm_no",
        matched_raw_identifier=candidate.matched_raw_identifier,
        link_type="exact_identifier",
        confidence=Decimal("1.0"),
        rule_id=_RULE_ID,
        rule_version=_RULE_VERSION,
    )


def _reject_left_conflicts(
    candidates: tuple[ExactLinkCandidateJoinRow, ...],
) -> None:
    if (
        type(candidates) is not tuple
        or len(candidates) > 217
        or any(type(candidate) is not ExactLinkCandidateJoinRow for candidate in candidates)
    ):
        raise TypeError("left conflict validation requires exact candidate rows")
    rights_by_left: dict[str, set[str]] = {}
    for candidate in candidates:
        rights_by_left.setdefault(candidate.left.left_product_id, set()).add(
            candidate.right.right_product_id
        )
    if any(len(rights) > 1 for rights in rights_by_left.values()):
        raise ArtifactContractError(
            ArtifactErrorCode.EXACT_LINK_CONFLICT,
            operation_id="build-exact-links",
            internal_context={"reason": "left_identifier_conflict"},
        )


def _reject_right_and_duplicate_conflicts(
    candidates: tuple[ExactLinkCandidateJoinRow, ...],
) -> None:
    if (
        type(candidates) is not tuple
        or len(candidates) > 217
        or any(type(candidate) is not ExactLinkCandidateJoinRow for candidate in candidates)
    ):
        raise TypeError("right conflict validation requires exact candidate rows")
    lefts_by_right: dict[str, set[str]] = {}
    keys: set[tuple[str, str, str]] = set()
    for candidate in candidates:
        key = (
            candidate.matched_raw_identifier,
            candidate.left.left_product_id,
            candidate.right.right_product_id,
        )
        if key in keys:
            raise ArtifactContractError(
                ArtifactErrorCode.EXACT_LINK_CONFLICT,
                operation_id="build-exact-links",
                internal_context={"reason": "duplicate_candidate_key"},
            )
        keys.add(key)
        lefts_by_right.setdefault(candidate.right.right_product_id, set()).add(
            candidate.left.left_product_id
        )
    if any(len(lefts) > 1 for lefts in lefts_by_right.values()):
        raise ArtifactContractError(
            ArtifactErrorCode.EXACT_LINK_CONFLICT,
            operation_id="build-exact-links",
            internal_context={"reason": "right_identifier_conflict"},
        )


def _evidence_from_candidate(
    candidate: ExactLinkCandidateJoinRow,
    link: ExactCrossSourceLinkRecord,
) -> tuple[ExactCrossSourceLinkEvidenceRecord, ...]:
    if (
        type(candidate) is not ExactLinkCandidateJoinRow
        or type(link) is not ExactCrossSourceLinkRecord
    ):
        raise TypeError("evidence construction requires exact candidate and link records")
    if len(candidate.right.identifiers) != 1:
        raise ValueError("exact evidence requires one direct fund-item identifier")
    rows = [
        _evidence_record(
            link_id=link.link_id,
            role="left_identifier",
            role_order=0,
            ordinal=0,
            raw_identifier=candidate.matched_raw_identifier,
            source=candidate.left.identifier,
        )
    ]
    rows.extend(
        _evidence_record(
            link_id=link.link_id,
            role="right_identifier",
            role_order=1,
            ordinal=ordinal,
            raw_identifier=candidate.matched_raw_identifier,
            source=source,
        )
        for ordinal, source in enumerate(candidate.right.identifiers)
    )
    return tuple(rows)


def _evidence_record(
    *,
    link_id: str,
    role: Literal["left_identifier", "right_identifier"],
    role_order: int,
    ordinal: int,
    raw_identifier: str,
    source: object,
) -> ExactCrossSourceLinkEvidenceRecord:
    from finproof.data.artifacts.staging import ExactLinkIdentifierSource

    if type(source) is not ExactLinkIdentifierSource:
        raise TypeError("evidence source must be exact")
    locator = source.locator
    return ExactCrossSourceLinkEvidenceRecord(
        link_id=link_id,
        evidence_role=role,
        evidence_role_order=role_order,
        evidence_ordinal=ordinal,
        raw_identifier=raw_identifier,
        source_table=locator.source_table,
        source_file=locator.source_file,
        source_sheet=locator.source_sheet,
        source_row_number=locator.source_row_number,
        source_column_name=locator.source_column_name,
        source_column_number=locator.source_column_number,
        source_column_letter=locator.source_column_letter,
        source_checksum=locator.source_checksum,
        source_snapshot_date=locator.source_snapshot_date,
        source_applicable_date=locator.source_applicable_date,
    )


def _require_candidate_evidence(
    candidate: ExactLinkCandidateJoinRow,
    link: ExactCrossSourceLinkRecord,
    evidence: tuple[ExactCrossSourceLinkEvidenceRecord, ...],
) -> None:
    if (
        type(candidate) is not ExactLinkCandidateJoinRow
        or type(link) is not ExactCrossSourceLinkRecord
        or type(evidence) is not tuple
        or any(type(row) is not ExactCrossSourceLinkEvidenceRecord for row in evidence)
        or link != _link_from_candidate(candidate)
        or evidence != _evidence_from_candidate(candidate, link)
    ):
        raise ValueError("exact candidate evidence changed")


def _build_link_and_evidence_records(
    candidates: tuple[ExactLinkCandidateJoinRow, ...],
) -> tuple[
    tuple[ExactCrossSourceLinkRecord, ...],
    tuple[ExactCrossSourceLinkEvidenceRecord, ...],
]:
    if type(candidates) is not tuple or any(
        type(candidate) is not ExactLinkCandidateJoinRow for candidate in candidates
    ):
        raise TypeError("exact link composition requires an exact candidate tuple")
    _reject_left_conflicts(candidates)
    _reject_right_and_duplicate_conflicts(candidates)
    ordered = tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                candidate.left.left_product_id,
                candidate.right.right_product_id,
                _RULE_VERSION,
            ),
        )
    )
    pairs = tuple((candidate, _link_from_candidate(candidate)) for candidate in ordered)
    links = tuple(link for _candidate_row, link in pairs)
    evidence_rows: list[ExactCrossSourceLinkEvidenceRecord] = []
    for candidate, link in pairs:
        evidence = _evidence_from_candidate(candidate, link)
        _require_candidate_evidence(candidate, link, evidence)
        evidence_rows.extend(evidence)
    evidence_rows.sort(key=lambda row: (row.link_id, row.evidence_role_order, row.evidence_ordinal))
    return links, tuple(evidence_rows)


def canonical_link_pair_tsv(
    rows: Iterable[ExactCrossSourceLinkRecord],
    *,
    expected_links: int,
) -> bytes:
    if type(expected_links) is not int or not 0 <= expected_links <= 217:
        raise ValueError("expected link count is outside the closed bound")
    iterator = iter(rows)
    payload = bytearray()
    previous: tuple[str, str] | None = None
    count = 0
    for row in iterator:
        _require_frozen_link_record(row)
        pair = (row.left_product_id, row.right_product_id)
        if previous is not None and pair <= previous:
            raise ValueError("exact link pair order or uniqueness changed")
        previous = pair
        fields: list[bytes] = []
        for identifier in pair:
            if type(identifier) is not str or not identifier:
                raise ValueError("exact link identifier is empty")
            encoded = identifier.encode("utf-8", errors="strict")
            if len(encoded) > 4_096 or any(
                marker in encoded for marker in (b"\0", b"\t", b"\r", b"\n")
            ):
                raise ValueError("exact link identifier is unsafe")
            fields.append(encoded)
        payload.extend(fields[0])
        payload.extend(b"\t")
        payload.extend(fields[1])
        payload.extend(b"\n")
        count += 1
        if count > expected_links or len(payload) > expected_links * 8_194:
            raise ValueError("canonical pair payload exceeded its bound")
    if count != expected_links:
        raise ValueError("canonical pair row count changed")
    return bytes(payload)


def _require_frozen_link_record(row: object) -> ExactCrossSourceLinkRecord:
    if type(row) is not ExactCrossSourceLinkRecord:
        raise TypeError("canonical pair rows must be exact CP3 records")
    validated = ExactCrossSourceLinkRecord.model_validate(
        row.model_dump(mode="python"),
        strict=True,
    )
    fields = (
        _RULE_ID,
        _RULE_VERSION,
        _LEFT_TABLE,
        row.left_product_id,
        _RIGHT_TABLE,
        row.right_product_id,
        row.matched_raw_identifier,
    )
    expected_link_id = hashlib.sha256(
        b"\0".join(value.encode("utf-8") for value in fields)
    ).hexdigest()
    if (
        validated != row
        or row.left_table != _LEFT_TABLE
        or row.left_identifier_field != "pd_itm_no"
        or row.right_table != _RIGHT_TABLE
        or row.right_identifier_field != "ksd_itm_no"
        or row.link_type != "exact_identifier"
        or row.confidence != Decimal("1.0")
        or row.rule_id != _RULE_ID
        or row.rule_version != _RULE_VERSION
        or row.link_id != expected_link_id
    ):
        raise ValueError("exact link record constants changed")
    return row


def exact_link_pair_sha256(payload: bytes) -> str:
    if type(payload) is not bytes:
        raise TypeError("exact link pair payload must be exact bytes")
    return hashlib.sha256(payload).hexdigest()
