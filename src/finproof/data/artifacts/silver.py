"""Bounded one-pass Silver artifact emission."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, cast

from finproof.core.versions import VersionBundle
from finproof.data.artifacts.bronze import BronzeBuildResult, require_bronze_build_result
from finproof.data.artifacts.config import ArtifactBuildConfig
from finproof.data.artifacts.input_identity import BuildInputIdentity
from finproof.data.artifacts.parquet_io import (
    ParquetBatchWriter,
    StagedParquetSet,
    verify_staged_parquet_table,
)
from finproof.data.artifacts.quality_persistence import (
    StagedBoundedRelationVerifier,
    persist_quality_issue,
)
from finproof.data.artifacts.reports import (
    ExcludedSilverCount,
    ExpectedObservedCount,
    NamedExpectedObservedCount,
    QualityJoinObservations,
    QualitySummaryReport,
    SilverSourceAuditObservations,
    require_bronze_source_audit_observations,
    require_silver_source_audit_observations,
)
from finproof.data.artifacts.serialization import canonical_record_json, serialize_table_row
from finproof.data.artifacts.staging import (
    ArtifactBuildSession,
    DomesticExactLinkCandidate,
    ExactLinkCandidateStoreCustody,
    ExactLinkIdentifierSource,
    ExternalOrderRelation,
    ExternalOrderRow,
    ExternalOrderStore,
    FundExactLinkCandidate,
)
from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME, TableSpec
from finproof.data.holdings import HoldingOwnerType, build_holding_relations
from finproof.data.normalization.bonds import normalize_bond_lot, project_bond_instrument
from finproof.data.normalization.domestic_listed import normalize_domestic_listed
from finproof.data.normalization.overseas_listed import normalize_overseas_listed
from finproof.data.normalization.public_funds import normalize_public_fund_item
from finproof.data.source_manifest import OFFICIAL_TABLE_IDS
from finproof.domain.bonds import BondInstrument, BondSaleLot
from finproof.domain.domestic_listed import ListedProduct
from finproof.domain.normalization import NormalizationResult
from finproof.domain.overseas_listed import OverseasListedProduct
from finproof.domain.public_funds import PublicFundItem
from finproof.domain.quality import DataQualityIssue
from finproof.domain.query_plan import ProductType
from finproof.domain.source import SourceRow
from finproof.registry.rating import RatingRegistry

_SOURCE_NAMES = ("PRBD01N001", "PREF01N001", "PREF02N001", "PRFD01N001")
_STAGED_RELATION_NAMES = (
    "SILVER_BOND_SALE_LOT",
    "SILVER_DOMESTIC_LISTED_PRODUCT",
    "SILVER_OVERSEAS_LISTED_PRODUCT",
    "SILVER_FUND_ITEM",
    "SILVER_QUALITY_ISSUE",
    "SILVER_PRODUCT_HOLDING",
    "SILVER_PRODUCT_HOLDING_COVERAGE",
)


@dataclass(frozen=True, slots=True)
class NamedObservedCount:
    """One exact closed instrumentation name and its observed count."""

    name: str
    observed: int

    def __post_init__(self) -> None:
        if (
            type(self.name) is not str
            or self.name not in (*_SOURCE_NAMES, *_STAGED_RELATION_NAMES)
            or type(self.observed) is not int
            or self.observed < 0
        ):
            raise ValueError("observed count is outside the closed contract")


class _SilverInstrumentationProvenance:
    __slots__ = ("_result_authorization",)

    _result_authorization: _SilverFinalizerAuthorization


@dataclass(frozen=True, slots=True)
class SilverBuildInstrumentation(_SilverInstrumentationProvenance):
    """Strict bounded counters for one complete Silver source pass."""

    source_rows_consumed: int
    source_consume_counts: tuple[NamedObservedCount, ...]
    normalizer_call_counts: tuple[NamedObservedCount, ...]
    staged_relation_rows: tuple[NamedObservedCount, ...]
    max_live_fund_group_rows: int
    max_writer_batch_rows: int
    max_relation_batch_rows: int

    def __post_init__(self) -> None:
        scalar_values = (
            self.source_rows_consumed,
            self.max_live_fund_group_rows,
            self.max_writer_batch_rows,
            self.max_relation_batch_rows,
        )
        if any(type(value) is not int or value < 0 for value in scalar_values):
            raise ValueError("Silver instrumentation requires nonnegative exact integers")
        if (
            tuple(item.name for item in self.source_consume_counts) != _SOURCE_NAMES
            or tuple(item.name for item in self.normalizer_call_counts) != _SOURCE_NAMES
            or tuple(item.name for item in self.staged_relation_rows) != _STAGED_RELATION_NAMES
            or any(
                type(item) is not NamedObservedCount
                for values in (
                    self.source_consume_counts,
                    self.normalizer_call_counts,
                    self.staged_relation_rows,
                )
                for item in values
            )
            or sum(item.observed for item in self.source_consume_counts)
            != self.source_rows_consumed
            or self.normalizer_call_counts != self.source_consume_counts
            or self.max_live_fund_group_rows > 16
            or self.max_writer_batch_rows > 65_536
            or self.max_relation_batch_rows > 65_536
        ):
            raise ValueError("Silver instrumentation inventory or bounds changed")


class _SilverFinalizerAuthorization:
    __slots__ = ("candidate_custody", "members", "result")

    def __init__(
        self,
        *,
        bronze_result: BronzeBuildResult,
        staged_tables: StagedParquetSet,
        observations: SilverSourceAuditObservations,
        quality_join_observations: QualityJoinObservations,
        quality_report: QualitySummaryReport,
        instrumentation: SilverBuildInstrumentation,
        candidate_custody: ExactLinkCandidateStoreCustody,
    ) -> None:
        self.members = (
            bronze_result,
            staged_tables,
            observations,
            quality_join_observations,
            quality_report,
            instrumentation,
        )
        self.candidate_custody = candidate_custody
        self.result: SilverBuildResult | None = None


class _SilverBatchSink:
    __slots__ = ("_closed", "_limit", "_max_batch_rows", "_rows", "_writer")

    def __init__(self, writer: ParquetBatchWriter, *, limit: int) -> None:
        self._writer = writer
        self._limit = limit
        self._rows: list[Mapping[str, object]] = []
        self._closed = False
        self._max_batch_rows = 0

    def enqueue(self, row: Mapping[str, object]) -> None:
        if self._closed:
            raise ValueError("Silver batch sink is closed")
        self._rows.append(row)
        self._max_batch_rows = max(self._max_batch_rows, len(self._rows))
        if len(self._rows) == self._limit:
            self._flush()

    def close(self) -> None:
        if self._closed:
            return
        self._flush()
        self._writer.close()
        self._closed = True

    def _flush(self) -> None:
        if self._rows:
            self._writer.write_batch(tuple(self._rows))
            self._rows.clear()


class _SilverBuildResultProvenance:
    __slots__ = ("_issuance",)

    _issuance: _SilverBuildResultIssuance


@dataclass(frozen=True, init=False, slots=True)
class SilverBuildResult(_SilverBuildResultProvenance):
    """Builder-issued carrier for one verified eleven-table Silver stage."""

    input_identity: BuildInputIdentity
    staged_tables: StagedParquetSet
    observations: SilverSourceAuditObservations
    quality_join_observations: QualityJoinObservations
    quality_report: QualitySummaryReport
    instrumentation: SilverBuildInstrumentation

    def __new__(cls, *args: object, **kwargs: object) -> SilverBuildResult:
        del args, kwargs
        raise TypeError("SilverBuildResult is builder-issued")

    @classmethod
    def _issue_from_finalizer(
        cls,
        *,
        bronze_result: BronzeBuildResult,
        staged_tables: StagedParquetSet,
        observations: SilverSourceAuditObservations,
        quality_join_observations: QualityJoinObservations,
        quality_report: QualitySummaryReport,
        instrumentation: SilverBuildInstrumentation,
    ) -> SilverBuildResult:
        exact_bronze = require_bronze_build_result(bronze_result)
        require_silver_source_audit_observations(observations)
        validated_join = QualityJoinObservations.model_validate(
            quality_join_observations.model_dump(mode="python"), strict=True
        )
        validated_report = QualitySummaryReport.model_validate(
            quality_report.model_dump(mode="python"), strict=True
        )
        if (
            type(staged_tables) is not StagedParquetSet
            or type(observations) is not SilverSourceAuditObservations
            or type(quality_join_observations) is not QualityJoinObservations
            or validated_join != quality_join_observations
            or type(quality_report) is not QualitySummaryReport
            or validated_report != quality_report
            or type(instrumentation) is not SilverBuildInstrumentation
        ):
            raise TypeError("Silver result requires exact finalizer members")
        staged_tables.assert_live()
        staged_names = tuple(item.logical.name for item in staged_tables.verifications)
        bronze_verifications = exact_bronze.staged_tables.verifications
        if (
            staged_tables._owner is not exact_bronze.staged_tables._owner
            or staged_tables.persistence_timestamp
            != exact_bronze.staged_tables.persistence_timestamp
            or staged_names != tuple(TABLE_SPEC_BY_NAME)[:11]
            or len(bronze_verifications) != 3
            or any(
                staged_tables.verifications[index] is not bronze_verifications[index]
                for index in range(3)
            )
            or observations._issuance.predecessor is not exact_bronze.observations
        ):
            raise ValueError("Silver result predecessor relationship changed")
        observed_rows = {
            item.logical.name: item.logical.row_count for item in staged_tables.verifications
        }
        quality_verification = staged_tables.verification_for("silver_quality_issue")
        if (
            quality_join_observations.persistence_timestamp != staged_tables.persistence_timestamp
            or quality_join_observations.quality_table_logical_hash
            != quality_verification.logical.logical_hash
            or quality_join_observations.total_issues != quality_verification.logical.row_count
            or quality_report.total_issues != quality_join_observations.total_issues
            or quality_report.distinct_affected_source_rows
            != quality_join_observations.distinct_affected_source_rows
            or quality_report.quarantined_issue_count
            != quality_join_observations.quarantined_issue_count
            or quality_report.quarantined_source_row_count
            != quality_join_observations.quarantined_source_row_count
            or quality_report.quality_table_logical_hash
            != quality_join_observations.quality_table_logical_hash
        ):
            raise ValueError("Silver result quality relationship changed")
        source_counts = tuple(
            item.observed_rows for item in exact_bronze.observations.source_tables
        )
        staged_counts = {item.name: item.observed for item in instrumentation.staged_relation_rows}
        unstaged_fund_rows = source_counts[3] - staged_counts["SILVER_FUND_ITEM"]
        if (
            tuple(item.observed for item in instrumentation.source_consume_counts) != source_counts
            or instrumentation.source_rows_consumed != sum(source_counts)
            or staged_counts["SILVER_BOND_SALE_LOT"] != observed_rows["silver_bond_sale_lot"]
            or staged_counts["SILVER_DOMESTIC_LISTED_PRODUCT"]
            != observed_rows["silver_domestic_listed_product"]
            or staged_counts["SILVER_OVERSEAS_LISTED_PRODUCT"]
            != observed_rows["silver_overseas_listed_product"]
            or not 0 <= unstaged_fund_rows <= quality_join_observations.quarantined_source_row_count
            or staged_counts["SILVER_QUALITY_ISSUE"] != observed_rows["silver_quality_issue"]
            or staged_counts["SILVER_PRODUCT_HOLDING"] != observed_rows["silver_product_holding"]
            or staged_counts["SILVER_PRODUCT_HOLDING_COVERAGE"]
            != observed_rows["silver_product_holding_coverage"]
            or staged_counts["SILVER_PRODUCT_HOLDING"] != 0
            or staged_counts["SILVER_PRODUCT_HOLDING_COVERAGE"]
            != (
                observed_rows["silver_domestic_listed_product"]
                + observed_rows["silver_overseas_listed_product"]
                + observed_rows["silver_fund_item"]
            )
        ):
            raise ValueError("Silver result instrumentation relationship changed")
        try:
            authorization = object.__getattribute__(
                instrumentation,
                "_result_authorization",
            )
        except AttributeError as exc:
            raise ValueError("Silver result lacks finalizer authorization") from exc
        supplied_members = (
            exact_bronze,
            staged_tables,
            observations,
            quality_join_observations,
            quality_report,
            instrumentation,
        )
        if (
            type(authorization) is not _SilverFinalizerAuthorization
            or authorization.result is not None
            or any(
                authorized is not supplied
                for authorized, supplied in zip(
                    authorization.members,
                    supplied_members,
                    strict=True,
                )
            )
        ):
            raise ValueError("Silver result finalizer authorization changed")
        value = object.__new__(cls)
        object.__setattr__(value, "input_identity", exact_bronze.input_identity)
        object.__setattr__(value, "staged_tables", staged_tables)
        object.__setattr__(value, "observations", observations)
        object.__setattr__(value, "quality_join_observations", quality_join_observations)
        object.__setattr__(value, "quality_report", quality_report)
        object.__setattr__(value, "instrumentation", instrumentation)
        object.__setattr__(
            value,
            "_issuance",
            _SilverBuildResultIssuance(value, authorization=authorization),
        )
        authorization.result = value
        return value


class _SilverBuildResultIssuance:
    __slots__ = ("authorization", "candidate_custody", "facts", "members", "value")

    candidate_custody: ExactLinkCandidateStoreCustody | None

    def __init__(
        self,
        value: SilverBuildResult,
        *,
        authorization: _SilverFinalizerAuthorization,
    ) -> None:
        self.value = value
        self.authorization = authorization
        self.candidate_custody = authorization.candidate_custody
        self.members = (
            value.input_identity,
            value.staged_tables,
            value.observations,
            value.quality_join_observations,
            value.quality_report,
            value.instrumentation,
        )
        self.facts = (
            value.quality_join_observations.model_dump_json(),
            value.quality_report.model_dump_json(),
            _instrumentation_facts(value.instrumentation),
        )


def require_silver_build_result(value: object) -> SilverBuildResult:
    """Require one unchanged exact builder-issued Silver result object."""
    if type(value) is not SilverBuildResult:
        raise TypeError("Silver result must have the exact runtime type")
    try:
        issuance = object.__getattribute__(value, "_issuance")
        members = (
            value.input_identity,
            value.staged_tables,
            value.observations,
            value.quality_join_observations,
            value.quality_report,
            value.instrumentation,
        )
        if (
            type(issuance) is not _SilverBuildResultIssuance
            or issuance.value is not value
            or issuance.authorization.result is not value
            or any(left is not right for left, right in zip(issuance.members, members, strict=True))
            or issuance.facts
            != (
                value.quality_join_observations.model_dump_json(),
                value.quality_report.model_dump_json(),
                _instrumentation_facts(value.instrumentation),
            )
        ):
            raise ValueError("Silver result issuance changed")
        value.input_identity.assert_unchanged()
        value.staged_tables.assert_live()
        require_silver_source_audit_observations(value.observations)
        QualityJoinObservations.model_validate(
            value.quality_join_observations.model_dump(mode="python"),
            strict=True,
        )
        QualitySummaryReport.model_validate(
            value.quality_report.model_dump(mode="python"),
            strict=True,
        )
        if type(value.instrumentation) is not SilverBuildInstrumentation:
            raise TypeError("Silver instrumentation must have the exact runtime type")
    except AttributeError as exc:
        raise ValueError("Silver result issuance is absent") from exc
    return value


def take_exact_link_candidate_store(
    *,
    silver_result: SilverBuildResult,
) -> ExactLinkCandidateStoreCustody:
    """Move exact-link candidate custody out of one exact Silver result once."""
    exact = require_silver_build_result(silver_result)
    issuance = exact._issuance
    custody = issuance.candidate_custody
    if custody is None:
        raise ValueError("exact-link candidate custody was already taken")
    if (
        type(custody) is not ExactLinkCandidateStoreCustody
        or custody is not issuance.authorization.candidate_custody
    ):
        raise ValueError("exact-link candidate custody changed")
    custody._require_live()
    issuance.candidate_custody = None
    return custody


def require_silver_build_result_successor(
    *,
    silver_result: SilverBuildResult,
    successor: StagedParquetSet,
) -> SilverBuildResult:
    if type(silver_result) is not SilverBuildResult or type(successor) is not StagedParquetSet:
        raise TypeError("Silver successor validation requires exact runtime types")
    issuance = object.__getattribute__(silver_result, "_issuance")
    members = (
        silver_result.input_identity,
        silver_result.staged_tables,
        silver_result.observations,
        silver_result.quality_join_observations,
        silver_result.quality_report,
        silver_result.instrumentation,
    )
    prefix = silver_result.staged_tables
    if (
        type(issuance) is not _SilverBuildResultIssuance
        or issuance.value is not silver_result
        or issuance.authorization.result is not silver_result
        or any(left is not right for left, right in zip(issuance.members, members, strict=True))
        or issuance.facts
        != (
            silver_result.quality_join_observations.model_dump_json(),
            silver_result.quality_report.model_dump_json(),
            _instrumentation_facts(silver_result.instrumentation),
        )
    ):
        raise ValueError("Silver result issuance changed")
    silver_result.input_identity.assert_unchanged()
    require_silver_source_audit_observations(silver_result.observations)
    QualityJoinObservations.model_validate(
        silver_result.quality_join_observations.model_dump(mode="python"),
        strict=True,
    )
    QualitySummaryReport.model_validate(
        silver_result.quality_report.model_dump(mode="python"),
        strict=True,
    )
    if type(silver_result.instrumentation) is not SilverBuildInstrumentation:
        raise TypeError("Silver instrumentation must have the exact runtime type")
    successor.assert_live()
    if (
        len(prefix.verifications) != 11
        or len(successor.verifications) != 13
        or prefix._owner is not successor._owner
        or prefix.persistence_timestamp != successor.persistence_timestamp
        or any(
            actual is not expected
            for actual, expected in zip(
                successor.verifications[:11], prefix.verifications, strict=True
            )
        )
        or any(
            actual is not expected
            for actual, expected in zip(successor.handles[:11], prefix.handles, strict=True)
        )
        or tuple(item.logical.name for item in successor.verifications[11:])
        != (
            "gold_exact_cross_source_link",
            "gold_exact_cross_source_link_evidence",
        )
    ):
        raise ValueError("staged tables are not the exact Silver successor")
    return silver_result


def _instrumentation_facts(value: SilverBuildInstrumentation) -> tuple[object, ...]:
    return (
        value.source_rows_consumed,
        tuple((item.name, item.observed) for item in value.source_consume_counts),
        tuple((item.name, item.observed) for item in value.normalizer_call_counts),
        tuple((item.name, item.observed) for item in value.staged_relation_rows),
        value.max_live_fund_group_rows,
        value.max_writer_batch_rows,
        value.max_relation_batch_rows,
    )


class SilverArtifactEmitter:
    """Session-owned one-pass consumer and finalizer for the six Silver tables."""

    __slots__ = (
        "_config",
        "_excluded_counts",
        "_held_rating_registry",
        "_holding_enabled_products",
        "_instrumentation",
        "_max_live_fund_group_rows",
        "_max_relation_batch_rows",
        "_max_writer_batch_rows",
        "_normalizer_call_counts",
        "_observations",
        "_order_store",
        "_quality_join_observations",
        "_quality_report",
        "_session",
        "_source_consume_counts",
        "_source_rows_consumed",
        "_staged_relation_rows",
        "_staged_tables",
        "_versions",
    )

    _config: ArtifactBuildConfig
    _excluded_counts: dict[str, int]
    _held_rating_registry: RatingRegistry
    _holding_enabled_products: list[tuple[HoldingOwnerType, str]]
    _instrumentation: SilverBuildInstrumentation | None
    _max_live_fund_group_rows: int
    _max_relation_batch_rows: int
    _max_writer_batch_rows: int
    _normalizer_call_counts: dict[str, int]
    _observations: SilverSourceAuditObservations | None
    _order_store: ExternalOrderStore
    _quality_join_observations: QualityJoinObservations | None
    _quality_report: QualitySummaryReport | None
    _session: ArtifactBuildSession
    _source_consume_counts: dict[str, int]
    _source_rows_consumed: int
    _staged_relation_rows: dict[str, int]
    _staged_tables: StagedParquetSet | None
    _versions: VersionBundle

    def __new__(cls) -> SilverArtifactEmitter:
        raise TypeError("SilverArtifactEmitter is factory-owned")

    @classmethod
    def for_session(
        cls,
        *,
        session: ArtifactBuildSession,
        config: ArtifactBuildConfig,
        versions: VersionBundle,
        rating_registry: RatingRegistry,
    ) -> SilverArtifactEmitter:
        if (
            cls is not SilverArtifactEmitter
            or type(session) is not ArtifactBuildSession
            or type(config) is not ArtifactBuildConfig
            or type(versions) is not VersionBundle
            or type(rating_registry) is not RatingRegistry
            or session._versions is not versions
        ):
            raise TypeError("Silver emitter requires exact retained build inputs")
        session.assert_live()
        value = object.__new__(cls)
        value._session = session
        value._config = config
        value._versions = versions
        value._held_rating_registry = rating_registry
        value._holding_enabled_products = []
        value._max_live_fund_group_rows = 0
        value._max_relation_batch_rows = 0
        value._max_writer_batch_rows = 0
        value._source_rows_consumed = 0
        value._source_consume_counts = dict.fromkeys(_SOURCE_NAMES, 0)
        value._normalizer_call_counts = dict.fromkeys(_SOURCE_NAMES, 0)
        value._staged_relation_rows = dict.fromkeys(_STAGED_RELATION_NAMES, 0)
        value._excluded_counts = dict.fromkeys(
            ("instrument", "listed_product", "fund_item"),
            0,
        )
        value._observations = None
        value._quality_join_observations = None
        value._quality_report = None
        value._instrumentation = None
        value._staged_tables = None
        order_store = session.open_external_order_store(config=config)
        value._order_store = order_store.__enter__()
        return value

    def consume(self, row: SourceRow) -> None:
        """Normalize and stage one exact already-Bronze-enqueued source row."""
        if type(row) is not SourceRow:
            raise TypeError("Silver emitter requires an exact SourceRow")
        if row.source_table not in self._source_consume_counts:
            raise ValueError("Silver source table is outside the closed inventory")
        self._source_rows_consumed += 1
        self._source_consume_counts[row.source_table] += 1
        self._normalizer_call_counts[row.source_table] += 1
        result: (
            NormalizationResult[BondSaleLot]
            | NormalizationResult[ListedProduct]
            | NormalizationResult[OverseasListedProduct]
            | NormalizationResult[PublicFundItem]
        )
        if row.source_table == "PRBD01N001":
            result = normalize_bond_lot(row, self._held_rating_registry)
            relation = ExternalOrderRelation.SILVER_BOND_SALE_LOT
        elif row.source_table == "PREF01N001":
            result = normalize_domestic_listed(row, self._versions.dataset_version)
            relation = ExternalOrderRelation.SILVER_DOMESTIC_LISTED_PRODUCT
        elif row.source_table == "PREF02N001":
            result = normalize_overseas_listed(row)
            relation = ExternalOrderRelation.SILVER_OVERSEAS_LISTED_PRODUCT
        else:
            result = normalize_public_fund_item(row)
            relation = ExternalOrderRelation.SILVER_FUND_ITEM
        self._stage_nonfund_result(relation, result)
        self._stage_quality_issues(result.issues)

    def _stage_nonfund_result(
        self,
        relation: ExternalOrderRelation,
        result: (
            NormalizationResult[BondSaleLot]
            | NormalizationResult[ListedProduct]
            | NormalizationResult[OverseasListedProduct]
            | NormalizationResult[PublicFundItem]
        ),
    ) -> None:
        if result.record is None:
            grain = (
                "instrument"
                if relation is ExternalOrderRelation.SILVER_BOND_SALE_LOT
                else "fund_item"
                if relation is ExternalOrderRelation.SILVER_FUND_ITEM
                else "listed_product"
            )
            self._excluded_counts[grain] += 1
            return
        record = result.record
        product_id_wrapper = (
            record.fund_item_id if isinstance(record, PublicFundItem) else record.product_id
        )
        product_id = product_id_wrapper.normalized_value
        if type(product_id) is not str:
            raise ValueError("normalized Silver product ID is missing")
        if type(result.record) is BondSaleLot:
            key: tuple[str | int, ...] = (
                product_id,
                result.record.source_key.exchange_market,
                result.record.source_key.info_base_date,
                result.record.source_key.info_seq,
                result.record.source_key.source_row_number,
            )
        elif type(result.record) is PublicFundItem:
            key = (product_id, result.record.source_row.source_row_number)
        else:
            key = (product_id,)
        self._order_store.insert_batch(
            relation=relation,
            rows=(
                ExternalOrderRow(
                    key=key,
                    payload_json=canonical_record_json(result.record),
                ),
            ),
        )
        if type(record) is ListedProduct:
            listed_type = record.product_type.normalized_value
            owner_type: HoldingOwnerType
            if listed_type == "ETF":
                owner_type = ProductType.DOMESTIC_ETF
            elif listed_type == "ETN":
                owner_type = ProductType.DOMESTIC_ETN
            else:  # pragma: no cover - strict listed normalization enum
                raise ValueError("domestic listed holding owner type is unknown")
            self._holding_enabled_products.append((owner_type, product_id))
        elif type(record) is OverseasListedProduct:
            listed_type = record.product_type.normalized_value
            if listed_type == "ETF":
                owner_type = ProductType.OVERSEAS_ETF
            elif listed_type == "ETN":
                owner_type = ProductType.OVERSEAS_ETN
            else:  # pragma: no cover - strict listed normalization enum
                raise ValueError("overseas listed holding owner type is unknown")
            self._holding_enabled_products.append((owner_type, product_id))
        elif type(record) is PublicFundItem:
            self._holding_enabled_products.append((ProductType.PUBLIC_FUND, product_id))
        if (
            relation is ExternalOrderRelation.SILVER_DOMESTIC_LISTED_PRODUCT
            and type(result.record) is ListedProduct
            and result.record.product_type.normalized_value == "ETF"
        ):
            domestic_candidate = DomesticExactLinkCandidate(
                left_product_id=product_id,
                source_product_type="ETF",
                identifier=ExactLinkIdentifierSource(
                    raw_identifier=result.record.product_id.raw_value,
                    locator=result.record.product_id.source,
                ),
            )
            self._order_store.insert_batch(
                relation=ExternalOrderRelation.EXACT_LINK_LEFT_CANDIDATE,
                rows=(
                    ExternalOrderRow(
                        key=(domestic_candidate.identifier.raw_identifier, product_id),
                        payload_json=canonical_record_json(domestic_candidate),
                    ),
                ),
            )
        elif (
            relation is ExternalOrderRelation.SILVER_FUND_ITEM
            and type(result.record) is PublicFundItem
        ):
            raw_identifier = result.record.ksd_id.raw_value
            if raw_identifier != "":
                fund_candidate = FundExactLinkCandidate(
                    right_product_id=product_id,
                    identifiers=(
                        ExactLinkIdentifierSource(
                            raw_identifier=raw_identifier,
                            locator=result.record.ksd_id.source,
                        ),
                    ),
                )
                self._order_store.insert_batch(
                    relation=ExternalOrderRelation.EXACT_LINK_RIGHT_CANDIDATE,
                    rows=(
                        ExternalOrderRow(
                            key=(raw_identifier, product_id),
                            payload_json=canonical_record_json(fund_candidate),
                        ),
                    ),
                )
        self._staged_relation_rows[relation.name] += 1

    def _stage_quality_issues(self, issues: Sequence[DataQualityIssue]) -> None:
        for issue in issues:
            persisted = persist_quality_issue(
                issue,
                persistence_timestamp=self._session.persistence_timestamp,
            )
            source = persisted.source
            self._order_store.insert_batch(
                relation=ExternalOrderRelation.SILVER_QUALITY_ISSUE,
                rows=(
                    ExternalOrderRow(
                        key=(
                            OFFICIAL_TABLE_IDS.index(source.source_table),
                            source.source_file.as_posix(),
                            source.source_sheet,
                            source.source_row_number,
                            source.source_column_number,
                            persisted.rule_id,
                            persisted.issue_id,
                        ),
                        payload_json=canonical_record_json(persisted),
                    ),
                ),
            )
            self._staged_relation_rows[ExternalOrderRelation.SILVER_QUALITY_ISSUE.name] += 1

    def finalize(self, *, bronze_result: BronzeBuildResult) -> SilverBuildResult:
        """Validate the exact Bronze predecessor before any Silver drain."""
        exact = require_bronze_build_result(bronze_result)
        if (
            exact.input_identity is not self._session._input_identity
            or exact.staged_tables._owner is not self._session
            or exact.staged_tables.persistence_timestamp != self._session.persistence_timestamp
        ):
            raise ValueError("Bronze result does not belong to this Silver emitter")
        exact.staged_tables.assert_live()
        names = tuple(item.logical.name for item in exact.staged_tables.verifications)
        if names != (
            "bronze_source_column",
            "bronze_source_row",
            "bronze_source_cell",
        ):
            raise ValueError("Silver finalization requires the exact Bronze prefix")
        require_bronze_source_audit_observations(exact.observations)
        self._staged_tables = self._drain_silver_tables(exact.staged_tables)
        relation_verifier = StagedBoundedRelationVerifier.for_store(self._order_store)
        self._quality_join_observations = relation_verifier.verify_quality_to_bronze(
            tables=self._staged_tables
        )
        self._quality_report = QualitySummaryReport.from_verified_quality(
            issues=self._iter_persisted_quality_issues(),
            join_observations=self._quality_join_observations,
            excluded_silver_records=tuple(
                ExcludedSilverCount(
                    grain=cast(
                        Literal["instrument", "listed_product", "fund_item"],
                        grain,
                    ),
                    count=count,
                )
                for grain, count in sorted(self._excluded_counts.items())
                if count > 0
            ),
        )
        observed_counts = {
            verification.logical.name: verification.logical.row_count
            for verification in self._staged_tables.verifications
        }
        self._observations = exact.observations.with_silver(
            (
                NamedExpectedObservedCount(
                    name="bond_sale_lot",
                    expected=self._config.silver_counts.bond_sale_lot,
                    observed=observed_counts["silver_bond_sale_lot"],
                ),
                NamedExpectedObservedCount(
                    name="bond_instrument",
                    expected=self._config.silver_counts.bond_instrument,
                    observed=observed_counts["silver_bond_instrument"],
                ),
                NamedExpectedObservedCount(
                    name="domestic_listed_product",
                    expected=self._config.silver_counts.domestic_listed_product,
                    observed=observed_counts["silver_domestic_listed_product"],
                ),
                NamedExpectedObservedCount(
                    name="overseas_listed_product",
                    expected=self._config.silver_counts.overseas_listed_product,
                    observed=observed_counts["silver_overseas_listed_product"],
                ),
                NamedExpectedObservedCount(
                    name="fund_item",
                    expected=self._config.silver_counts.fund_item,
                    observed=observed_counts["silver_fund_item"],
                ),
            ),
            ExpectedObservedCount(
                expected=self._config.quarantine_source_rows,
                observed=self._quality_join_observations.quarantined_source_row_count,
            ),
        )
        self._instrumentation = SilverBuildInstrumentation(
            source_rows_consumed=self._source_rows_consumed,
            source_consume_counts=tuple(
                NamedObservedCount(name=name, observed=self._source_consume_counts[name])
                for name in _SOURCE_NAMES
            ),
            normalizer_call_counts=tuple(
                NamedObservedCount(name=name, observed=self._normalizer_call_counts[name])
                for name in _SOURCE_NAMES
            ),
            staged_relation_rows=tuple(
                NamedObservedCount(name=name, observed=self._staged_relation_rows[name])
                for name in _STAGED_RELATION_NAMES
            ),
            max_live_fund_group_rows=self._max_live_fund_group_rows,
            max_writer_batch_rows=self._max_writer_batch_rows,
            max_relation_batch_rows=self._max_relation_batch_rows,
        )
        candidate_custody = ExactLinkCandidateStoreCustody._issue(
            owner=self._session,
            store=self._order_store,
        )
        authorization = _SilverFinalizerAuthorization(
            bronze_result=exact,
            staged_tables=self._staged_tables,
            observations=self._observations,
            quality_join_observations=self._quality_join_observations,
            quality_report=self._quality_report,
            instrumentation=self._instrumentation,
            candidate_custody=candidate_custody,
        )
        object.__setattr__(
            self._instrumentation,
            "_result_authorization",
            authorization,
        )
        return SilverBuildResult._issue_from_finalizer(
            bronze_result=exact,
            staged_tables=self._staged_tables,
            observations=self._observations,
            quality_join_observations=self._quality_join_observations,
            quality_report=self._quality_report,
            instrumentation=self._instrumentation,
        )

    def _drain_silver_tables(self, bronze_tables: StagedParquetSet) -> StagedParquetSet:
        table_names = (
            "silver_bond_sale_lot",
            "silver_bond_instrument",
            "silver_domestic_listed_product",
            "silver_overseas_listed_product",
            "silver_fund_item",
            "silver_quality_issue",
            "silver_product_holding",
            "silver_product_holding_coverage",
        )
        specs = tuple(TABLE_SPEC_BY_NAME[name] for name in table_names)
        leaves = tuple(self._session.claim_parquet_leaf(spec) for spec in specs)
        writers: list[ParquetBatchWriter] = []
        sinks: list[_SilverBatchSink] = []
        try:
            for spec, leaf in zip(specs, leaves, strict=True):
                writer = ParquetBatchWriter(spec, leaf)
                writers.append(writer)
                sinks.append(
                    _SilverBatchSink(
                        writer,
                        limit=self._config.parquet.writer_batch_rows,
                    )
                )
            self._drain_bond_relation(specs[0], specs[1], sinks[0], sinks[1])
            self._drain_model_relation(
                ExternalOrderRelation.SILVER_DOMESTIC_LISTED_PRODUCT,
                ListedProduct,
                specs[2],
                sinks[2],
            )
            self._drain_model_relation(
                ExternalOrderRelation.SILVER_OVERSEAS_LISTED_PRODUCT,
                OverseasListedProduct,
                specs[3],
                sinks[3],
            )
            self._drain_model_relation(
                ExternalOrderRelation.SILVER_FUND_ITEM,
                PublicFundItem,
                specs[4],
                sinks[4],
            )
            self._drain_model_relation(
                ExternalOrderRelation.SILVER_QUALITY_ISSUE,
                DataQualityIssue,
                specs[5],
                sinks[5],
            )
            # ponytail: sealed official ceiling is 31,492; move this inventory to the
            # external-order store before admitting a larger official product universe.
            if len(self._holding_enabled_products) > 31_492:
                raise ValueError("holding coverage inventory exceeds the sealed ceiling")
            holdings, coverage = build_holding_relations(
                enabled_products=tuple(
                    sorted(
                        self._holding_enabled_products,
                        key=lambda item: (item[0].value, item[1]),
                    )
                ),
                generations=(),
                approved_owner_mappings=(),
            )
            for holding_row in holdings:
                sinks[6].enqueue(serialize_table_row(specs[6], holding_row))
            for coverage_row in coverage:
                sinks[7].enqueue(serialize_table_row(specs[7], coverage_row))
            self._staged_relation_rows["SILVER_PRODUCT_HOLDING"] = len(holdings)
            self._staged_relation_rows["SILVER_PRODUCT_HOLDING_COVERAGE"] = len(coverage)
            for sink in sinks:
                sink.close()
            self._max_writer_batch_rows = max(
                (sink._max_batch_rows for sink in sinks),
                default=0,
            )
            writers.clear()
            verifications = tuple(
                verify_staged_parquet_table(owner=self._session, leaf=leaf, spec=spec)
                for spec, leaf in zip(specs, leaves, strict=True)
            )
            return bronze_tables.extend_verified(
                owner=self._session,
                verifications=verifications,
            )
        except BaseException:
            for writer in reversed(writers):
                with contextlib.suppress(BaseException):
                    writer.abort()
            raise

    def _drain_model_relation(
        self,
        relation: ExternalOrderRelation,
        model_type: type[BondInstrument]
        | type[BondSaleLot]
        | type[ListedProduct]
        | type[OverseasListedProduct]
        | type[PublicFundItem]
        | type[DataQualityIssue],
        spec: TableSpec,
        sink: _SilverBatchSink,
    ) -> None:
        for batch in self._order_store.iter_ordered_batches(relation=relation):
            self._max_relation_batch_rows = max(
                self._max_relation_batch_rows,
                len(batch),
            )
            for staged in batch:
                model = model_type.model_validate_json(staged.payload_json)
                sink.enqueue(serialize_table_row(spec, model))

    def _drain_bond_relation(
        self,
        lot_spec: TableSpec,
        parent_spec: TableSpec,
        lot_sink: _SilverBatchSink,
        parent_sink: _SilverBatchSink,
    ) -> None:
        current_id: str | None = None
        lots: list[BondSaleLot] = []

        def emit_parent() -> None:
            if not lots:
                return
            projection = project_bond_instrument(tuple(lots), as_of=self._versions.dataset_version)
            if projection.record is None:
                self._excluded_counts["instrument"] += 1
            else:
                parent_sink.enqueue(serialize_table_row(parent_spec, projection.record))
            self._stage_quality_issues(projection.issues)
            lots.clear()

        for batch in self._order_store.iter_ordered_batches(
            relation=ExternalOrderRelation.SILVER_BOND_SALE_LOT
        ):
            self._max_relation_batch_rows = max(
                self._max_relation_batch_rows,
                len(batch),
            )
            for staged in batch:
                lot = BondSaleLot.model_validate_json(staged.payload_json)
                product_id = lot.product_id.normalized_value
                if type(product_id) is not str:
                    raise ValueError("bond lot product ID is missing")
                if current_id is not None and product_id != current_id:
                    emit_parent()
                current_id = product_id
                lots.append(lot)
                lot_sink.enqueue(serialize_table_row(lot_spec, lot))
                self._max_live_fund_group_rows = max(
                    self._max_live_fund_group_rows,
                    len(lots),
                )
        emit_parent()

    def _iter_persisted_quality_issues(self) -> Iterator[DataQualityIssue]:
        for batch in self._order_store.iter_ordered_batches(
            relation=ExternalOrderRelation.SILVER_QUALITY_ISSUE
        ):
            self._max_relation_batch_rows = max(
                self._max_relation_batch_rows,
                len(batch),
            )
            for staged in batch:
                yield DataQualityIssue.model_validate_json(
                    staged.payload_json,
                    strict=True,
                )
