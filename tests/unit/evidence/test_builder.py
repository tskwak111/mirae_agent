"""Focused evidence construction contracts."""

import json
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Self, cast

import pytest
from tests.helpers.source_rows import source_row

from finproof.data.artifacts.serialization import canonical_record_json
from finproof.data.normalization.bonds import normalize_bond_lot, project_bond_instrument
from finproof.domain.bonds import BondInstrument
from finproof.registry.rating import RatingRegistry
from finproof.runtime.session import RuntimeArtifactSession

ROOT = Path(__file__).resolve().parents[3]
RATING_REGISTRY = RatingRegistry.from_yaml(ROOT / "config/rating_scale.yaml")


def _candidate_registry_session(connection: object) -> RuntimeArtifactSession:
    from tests.helpers.query_runtime import verified_artifacts

    from finproof.core.settings import ExecutionMode
    from finproof.core.versions import VersionBundle
    from finproof.registry.loader import RegistryBundle
    from finproof.registry.resources import REGISTRY_RESOURCE_NAMES, registry_resource_bytes

    payloads = {name: registry_resource_bytes(name) for name in REGISTRY_RESOURCE_NAMES}
    registries = RegistryBundle._from_resource_bytes(payloads)
    verified = verified_artifacts()
    return RuntimeArtifactSession._issue(
        connection=connection,  # type: ignore[arg-type]
        verified=verified,
        registries=registries,
        versions=VersionBundle.from_runtime(
            verified=verified,
            registries=registries,
            execution_mode=ExecutionMode.EVALUATION,
        ),
    )


def test_evidence_and_answer_skeleton_exposes_exact_interfaces() -> None:
    from finproof.answer import AnswerRenderer
    from finproof.evidence import ClaimVerifier, EvidenceBuilder
    from finproof.service import AnswerService
    from finproof.storage.repositories.evidence import EvidenceRepository

    assert all(
        isinstance(value, type)
        for value in (
            EvidenceRepository,
            EvidenceBuilder,
            ClaimVerifier,
            AnswerRenderer,
            AnswerService,
        )
    )


def test_overseas_return_1y_limitation_reaches_evidence_renderer_and_verifier() -> None:
    from finproof.answer import AnswerRenderer
    from finproof.core.settings import ExecutionMode
    from finproof.domain.answers import AnswerRequest
    from finproof.domain.execution import ExecutionLimitationCode
    from finproof.domain.query_plan import (
        Intent,
        ProductType,
        QueryPlan,
        ResultGrain,
        TopKScope,
    )
    from finproof.evidence import ClaimVerifier, EvidenceBuilder, serialize_evidence_context
    from finproof.quality import MetricPolicyResult, PolicyExecutionResult
    from finproof.query import FieldRegistry, ResolutionBundle, SemanticValidator, ValidationContext
    from finproof.registry.loader import RegistryBundle
    from finproof.storage.repositories.evidence import EvidenceRepository

    session, _ = _bond_evidence_session()
    plan = QueryPlan(
        intent=Intent.SCREEN,
        product_types=(ProductType.DOMESTIC_ETF, ProductType.OVERSEAS_ETF),
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.PRODUCT,
        filters=(),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.PER_PRODUCT_TYPE,
        needs_clarification=False,
        clarification_reason="",
    )
    context = ValidationContext(
        as_of_date=plan.as_of_date,
        execution_mode=ExecutionMode.EVALUATION,
    )
    validated = SemanticValidator(
        FieldRegistry.from_bundle(RegistryBundle.from_package())
    ).validate(plan, resolutions=ResolutionBundle(results=()), context=context)
    policy = PolicyExecutionResult(
        included_rows=(),
        excluded_filter_count=0,
        excluded_state_count=0,
        excluded_metric_count=0,
        metric_policy=MetricPolicyResult(
            recorded_values=(),
            comparison_valid_values=(),
            excluded_count=0,
            warnings=(),
        ),
        dual_lens_labels=(),
        selected_rows=(),
        partitions=(),
        aggregates=(),
        ranks=(),
        warnings=(),
        limitations=(ExecutionLimitationCode.OVERSEAS_RETURN_1Y_UNAVAILABLE,),
    )
    try:
        evidence = EvidenceBuilder().build(
            plan=validated,
            policy_result=policy,
            repository=EvidenceRepository(session),
        )
    finally:
        session._close()

    limitation = (
        "해외 ETF/ETN의 1년 수익률은 제공 데이터에 없어 "
        "해당 상품을 1년 수익률 비교에서 제외했습니다."
    )
    wording = RegistryBundle.from_package().answers.document["wording"]
    assert isinstance(wording, Mapping)
    assert evidence.material_policy_limitations[0] == wording["snapshot_assumption"]
    assert limitation in evidence.material_policy_limitations
    assert limitation in serialize_evidence_context(evidence)
    draft = AnswerRenderer().render(
        request=AnswerRequest(question_id="q", question="1년 수익률"),
        plan=plan,
        evidence=evidence,
    )
    assert limitation in ClaimVerifier().verify(draft, evidence).text


def test_mixed_complete_and_unavailable_holding_coverage_warns_without_absence_claim() -> None:
    from finproof.answer import AnswerRenderer
    from finproof.core.settings import ExecutionMode
    from finproof.domain.answers import AnswerRequest, ClaimKind
    from finproof.domain.query_plan import (
        FilterClause,
        FilterOperator,
        Intent,
        ProductType,
        QueryPlan,
        ResultGrain,
        TopKScope,
    )
    from finproof.entity import (
        HoldingResolutionCandidate,
        HoldingResolutionResult,
    )
    from finproof.evidence import ClaimVerifier, EvidenceBuilder
    from finproof.quality import MetricPolicyResult, PolicyExecutionResult
    from finproof.query import FieldRegistry, ResolutionBundle, SemanticValidator, ValidationContext
    from finproof.registry.loader import RegistryBundle
    from finproof.storage.repositories.evidence import EvidenceRepository

    class Connection:
        def execute(self, _sql: str, _parameters: object) -> Self:
            return self

        def fetchall(self) -> tuple[tuple[object, ...], ...]:
            return (
                ("domestic_etf", "complete", 3),
                ("domestic_etf", "unavailable", 2),
            )

        def close(self) -> None: ...

    plan = QueryPlan(
        intent=Intent.SCREEN,
        product_types=(ProductType.DOMESTIC_ETF,),
        entities=(),
        as_of_date=date(2026, 8, 24),
        result_grain=ResultGrain.LISTED_PRODUCT,
        filters=(
            FilterClause(
                field="holding_constituent",
                operator=FilterOperator.EQ,
                value="삼성전자",
            ),
        ),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.GLOBAL,
        needs_clarification=False,
        clarification_reason="",
    )
    candidate = HoldingResolutionCandidate(
        constituent_identifier="KR7005930003",
        constituent_identifier_type="isin",
        display_name="삼성전자",
    )
    context = ValidationContext(
        as_of_date=plan.as_of_date,
        execution_mode=ExecutionMode.EVALUATION,
    )
    validated = SemanticValidator(
        FieldRegistry.from_bundle(RegistryBundle.from_package())
    ).validate(
        plan,
        resolutions=ResolutionBundle(
            results=(),
            holding_constituent=HoldingResolutionResult(
                selected=candidate,
                candidates=(candidate,),
            ),
        ),
        context=context,
    )
    policy = PolicyExecutionResult(
        included_rows=(),
        excluded_filter_count=0,
        excluded_state_count=0,
        excluded_metric_count=0,
        metric_policy=MetricPolicyResult(
            recorded_values=(),
            comparison_valid_values=(),
            excluded_count=0,
            warnings=(),
        ),
        dual_lens_labels=(),
        selected_rows=(),
        partitions=(),
        aggregates=(),
        ranks=(),
        warnings=(),
    )
    session = _candidate_registry_session(Connection())
    try:
        evidence = EvidenceBuilder().build(
            plan=validated,
            policy_result=policy,
            repository=EvidenceRepository(session),
        )
    finally:
        session._close()

    limitation = (
        "domestic_etf 구성종목 자료 중 일부는 제공되지 않아 "
        "검색되지 않은 종목의 부재를 판단하지 않았습니다."
    )
    assert limitation in evidence.material_policy_limitations
    unavailable = next(
        summary
        for summary in evidence.summaries
        if summary.partition_key == "holding-coverage:domestic_etf:unavailable"
    )
    draft = AnswerRenderer().render(
        request=AnswerRequest(question_id="q-mixed-coverage", question="삼성전자 보유 ETF"),
        plan=plan,
        evidence=evidence,
    )
    claim = next(
        item
        for item in draft.claims
        if item.kind is ClaimKind.LIMITATION and item.value == limitation
    )
    assert claim.evidence_ids == (unavailable.summary_id,)
    assert ClaimVerifier().verify(draft, evidence).text == draft.text


def test_holding_repository_reparses_canonical_rows_and_uses_full_owner_generation_count(
    tmp_path: Path,
) -> None:
    import duckdb
    from tests.helpers.artifacts import write_database_artifact_tree
    from tests.unit.data.test_holdings import _coverage, _holding

    from finproof.data.artifacts.serialization import serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from finproof.data.holdings import HoldingRecord
    from finproof.storage.repositories.evidence import EvidenceRepository, HoldingEvidenceLookup

    matching = cast(HoldingRecord, _holding())
    other = _holding("KR7006600007")
    coverage = _coverage(observed_holding_count=2)
    root = tmp_path / "holding-evidence"
    write_database_artifact_tree(
        root,
        {
            "silver_product_holding": (
                dict(serialize_table_row(TABLE_SPEC_BY_NAME["silver_product_holding"], matching)),
                dict(serialize_table_row(TABLE_SPEC_BY_NAME["silver_product_holding"], other)),
            ),
            "silver_product_holding_coverage": (
                dict(
                    serialize_table_row(
                        TABLE_SPEC_BY_NAME["silver_product_holding_coverage"], coverage
                    )
                ),
            ),
        },
    )
    connection = duckdb.connect(str(root / "finproof.duckdb"), read_only=True)
    session = _candidate_registry_session(connection)
    try:
        result = EvidenceRepository(session).fetch_holding_evidence(
            (
                HoldingEvidenceLookup(
                    product_type=matching.owner_product_type,
                    product_ids=(matching.owner_product_id,),
                    constituent_identifier=matching.constituent_identifier,
                    constituent_identifier_type=matching.constituent_identifier_type,
                ),
            )
        )
    finally:
        session._close()

    assert len(result.holding_records) == 1
    assert result.holding_records[0].constituent_identifier == matching.constituent_identifier
    assert result.holding_coverage[0].observed_holding_count == 2


def test_holding_repository_rejects_same_generation_with_different_shared_provenance(
    tmp_path: Path,
) -> None:
    import duckdb
    from tests.helpers.artifacts import write_database_artifact_tree
    from tests.unit.data.test_holdings import _coverage, _holding

    from finproof.data.artifacts.serialization import serialize_table_row
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from finproof.data.holdings import HoldingCoverageRecord, HoldingRecord
    from finproof.storage.repositories.evidence import EvidenceRepository, HoldingEvidenceLookup

    holding = cast(HoldingRecord, _holding())
    coverage_payload = cast(HoldingCoverageRecord, _coverage()).model_dump(mode="python")
    coverage_payload["source_owner"] = "서로 다른 출처"
    coverage = HoldingCoverageRecord.model_validate(coverage_payload, strict=True)
    root = tmp_path / "holding-provenance-mismatch"
    write_database_artifact_tree(
        root,
        {
            "silver_product_holding": (
                dict(serialize_table_row(TABLE_SPEC_BY_NAME["silver_product_holding"], holding)),
            ),
            "silver_product_holding_coverage": (
                dict(
                    serialize_table_row(
                        TABLE_SPEC_BY_NAME["silver_product_holding_coverage"], coverage
                    )
                ),
            ),
        },
    )
    session = _candidate_registry_session(
        duckdb.connect(str(root / "finproof.duckdb"), read_only=True)
    )
    try:
        with pytest.raises(ValueError, match="provenance"):
            EvidenceRepository(session).fetch_holding_evidence(
                (
                    HoldingEvidenceLookup(
                        product_type=holding.owner_product_type,
                        product_ids=(holding.owner_product_id,),
                        constituent_identifier=holding.constituent_identifier,
                        constituent_identifier_type=holding.constituent_identifier_type,
                    ),
                )
            )
    finally:
        session._close()


def test_final_product_claims_use_complete_source_cell_lineage() -> None:
    from finproof.domain.query_plan import ProductType
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, record = _bond_evidence_session()
    evidence = (
        EvidenceRepository(session)
        .fetch_final_record_evidence(
            (
                EvidenceLookup(
                    product_type=ProductType.DOMESTIC_BOND,
                    product_ids=("KR0000000001",),
                    field_ids=("buy_yield",),
                ),
            )
        )[0]
        .direct[0]
    )

    assert evidence.value == record.buy_yield
    assert evidence.product_type is ProductType.DOMESTIC_BOND
    assert evidence.value.source.source_table == "PRBD01N001"
    assert evidence.value.source.source_row_number == 77
    assert evidence.value.source.source_column_name == "buy_yield"
    assert evidence.value.source.source_column_letter
    assert evidence.value.source.source_checksum
    assert evidence.value.source.source_snapshot_date == date(2026, 8, 24)
    session._close()


def test_derived_claims_bind_formula_inputs_rule_and_as_of() -> None:
    from finproof.domain.query_plan import ProductType
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, record = _bond_evidence_session()
    evidence = (
        EvidenceRepository(session)
        .fetch_final_record_evidence(
            (
                EvidenceLookup(
                    product_type=ProductType.DOMESTIC_BOND,
                    product_ids=("KR0000000001",),
                    field_ids=("remaining_days_at_as_of",),
                ),
            )
        )[0]
        .derived[0]
    )

    assert evidence.value == record.remaining_days_at_as_of
    assert evidence.value.rule_id == "bond.remaining_days_at_as_of"
    assert evidence.value.rule_version
    assert evidence.value.as_of_date == date(2026, 8, 22)
    assert tuple(item.source_column_name for item in evidence.value.inputs) == ("mat_dt",)
    session._close()


def test_public_fund_evidence_restores_canonical_nested_lineage() -> None:
    from tests.unit.data.artifacts.test_serialization import _fund_record

    from finproof.domain.query_plan import ProductType
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    fund = _fund_record()
    product_id = fund.fund_item_id.normalized_value
    assert type(product_id) is str

    class Connection:
        def execute(self, _sql: str, _parameters: object) -> Self:
            return self

        def fetchall(self) -> tuple[tuple[object, ...], ...]:
            return ((product_id, canonical_record_json(fund)),)

        def close(self) -> None: ...

    session = _candidate_registry_session(Connection())

    record = EvidenceRepository(session).fetch_final_record_evidence(
        (
            EvidenceLookup(
                product_type=ProductType.PUBLIC_FUND,
                product_ids=(product_id,),
                field_ids=("product_id",),
            ),
        )
    )[0]

    assert record.direct[0].value.normalized_value == product_id
    assert record.direct[0].value.source == fund.fund_item_id.source
    session._close()


def test_count_exclusion_rank_tie_partition_and_aggregate_summaries_are_bounded() -> None:
    from pydantic import ValidationError

    from finproof.domain.evidence import EvidenceSummary, EvidenceSummaryKind

    summaries = tuple(
        EvidenceSummary(
            summary_id=f"summary:{kind.value}",
            kind=kind,
            included_count=254,
            excluded_count=71,
            evidence_ids=("evidence:1",),
            policy_versions=("policy:1.0.0",),
            validated_plan_sha256="a" * 64,
            version_bundle_sha256="b" * 64,
            artifact_manifest_hash="c" * 64,
        )
        for kind in EvidenceSummaryKind
    )

    assert tuple(summary.kind for summary in summaries) == tuple(EvidenceSummaryKind)
    assert all(summary.included_count + summary.excluded_count == 325 for summary in summaries)
    with pytest.raises(ValidationError):
        EvidenceSummary.model_validate(
            {
                **summaries[0].model_dump(),
                "evidence_ids": tuple(f"evidence:{index}" for index in range(101)),
            }
        )


def test_builder_preserves_rank_value_identity_and_partition() -> None:
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.domain.query_plan import Intent, ProductType, ResultGrain, SortDirection, SortSpec
    from finproof.evidence import EvidenceBuilder
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.storage import (
        RawExecutionResult,
        RawFieldValue,
        RawProductRow,
        RawSegmentResult,
    )
    from finproof.storage.repositories.evidence import EvidenceRepository

    session, _ = _bond_evidence_session()
    fields = FieldRegistry.from_bundle(RegistryBundle.from_package())
    plan = _plan().model_copy(
        update={
            "intent": Intent.SCREEN_RANK,
            "sort": (SortSpec(field="buy_yield", direction=SortDirection.DESC),),
            "top_k": 1,
        }
    )
    validated = SemanticValidator(fields).validate(
        plan, resolutions=ResolutionBundle(results=()), context=_context()
    )
    bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())
    row = RawProductRow(
        product_type=ProductType.DOMESTIC_BOND,
        native_result_grain=ResultGrain.INSTRUMENT,
        product_id="KR0000000001",
        values=(
            RawFieldValue(field_id="product_id", value="KR0000000001", quality_status="valid"),
            RawFieldValue(field_id="buy_yield", value=Decimal("2.25"), quality_status="valid"),
            RawFieldValue(field_id="buyable_quantity", value=Decimal("10"), quality_status="valid"),
            RawFieldValue(
                field_id="maturity_date", value=date(2027, 7, 11), quality_status="valid"
            ),
        ),
    )
    policy = PolicyEngine().apply(
        RawExecutionResult(
            segments=(
                RawSegmentResult(
                    product_type=ProductType.DOMESTIC_BOND,
                    native_result_grain=ResultGrain.INSTRUMENT,
                    rows=(row, row, row),
                    candidate_count=3,
                    max_batch_rows=3,
                ),
            ),
            candidate_count=3,
        ),
        bundle=bundle,
    )

    evidence = EvidenceBuilder().build(
        plan=validated,
        policy_result=policy,
        repository=EvidenceRepository(session),
    )
    rank_summaries = tuple(item for item in evidence.summaries if item.kind.value == "rank")
    summary = rank_summaries[0]
    tie_summary = next(item for item in evidence.summaries if item.kind.value == "tie")
    partition_summary = next(item for item in evidence.summaries if item.kind.value == "partition")

    assert len(rank_summaries) == 1
    assert partition_summary.value == len(policy.partitions[0].selected_values)
    assert summary.product_types == (ProductType.DOMESTIC_BOND,)
    assert summary.native_result_grains == (ResultGrain.INSTRUMENT,)
    assert summary.partition_key == policy.ranks[0].partition_key
    assert (summary.product_id, summary.metric_id, summary.rank, summary.value) == (
        "KR0000000001",
        "buy_yield",
        1,
        Decimal("2.25"),
    )
    assert summary.tie_count == 3
    assert tie_summary.evidence_ids == summary.evidence_ids
    assert any("동률" in limitation for limitation in evidence.material_policy_limitations)
    session._close()


def test_explicit_metric_targets_bound_evidence_fields_per_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.unit.quality.test_pipeline_order import _listed
    from tests.unit.query.test_semantic_validator import _context

    from finproof.domain.query_plan import (
        Intent,
        MetricTarget,
        ProductType,
        QueryPlan,
        ResultGrain,
        SortDirection,
        SortSpec,
        TopKScope,
    )
    from finproof.evidence import EvidenceBuilder
    from finproof.quality import PolicyEngine
    from finproof.query import ExecutionBundleBuilder, ResolutionBundle, SemanticValidator
    from finproof.storage import RawExecutionResult, RawFieldValue, RawSegmentResult
    from finproof.storage.repositories.evidence import (
        EvidenceLookup,
        EvidenceRepository,
        RecordEvidence,
    )

    session, _ = _bond_evidence_session()
    repository = EvidenceRepository(session)
    template = repository.fetch_final_record_evidence(
        (
            EvidenceLookup(
                product_type=ProductType.DOMESTIC_BOND,
                product_ids=("KR0000000001",),
                field_ids=("product_id",),
            ),
        )
    )[0].direct[0]
    plan = QueryPlan(
        intent=Intent.SCREEN_RANK,
        product_types=(ProductType.DOMESTIC_ETF, ProductType.OVERSEAS_ETF),
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.PRODUCT,
        filters=(),
        metrics=("total_fee", "return_1d"),
        metric_targets=(
            MetricTarget(product_type=ProductType.DOMESTIC_ETF, metrics=("total_fee",)),
            MetricTarget(product_type=ProductType.OVERSEAS_ETF, metrics=("return_1d",)),
        ),
        sort=(
            SortSpec(field="total_fee", direction=SortDirection.ASC),
            SortSpec(field="return_1d", direction=SortDirection.DESC),
        ),
        aggregation=None,
        top_k=1,
        top_k_scope=TopKScope.PER_PRODUCT_TYPE,
        needs_clarification=False,
        clarification_reason="",
    )
    validated = SemanticValidator(repository._fields).validate(
        plan,
        resolutions=ResolutionBundle(results=()),
        context=_context(),
    )
    bundle = ExecutionBundleBuilder(repository._fields).build(validated, context=_context())
    rows = {
        product_type: listed.model_copy(
            update={
                "values": (
                    *listed.values,
                    RawFieldValue(field_id=field_id, value=value, quality_status="valid"),
                )
            }
        )
        for product_type, listed, field_id, value in (
            (
                ProductType.DOMESTIC_ETF,
                _listed("KR-ETF", ProductType.DOMESTIC_ETF, "KRW", "100"),
                "total_fee",
                Decimal("0.1"),
            ),
            (
                ProductType.OVERSEAS_ETF,
                _listed("US-ETF", ProductType.OVERSEAS_ETF, "USD", "100"),
                "return_1d",
                Decimal("2.0"),
            ),
        )
    }
    policy = PolicyEngine().apply(
        RawExecutionResult(
            segments=tuple(
                RawSegmentResult(
                    product_type=product_type,
                    native_result_grain=ResultGrain.LISTED_PRODUCT,
                    rows=(row,),
                    candidate_count=1,
                    max_batch_rows=1,
                )
                for product_type, row in rows.items()
            ),
            candidate_count=2,
        ),
        bundle=bundle,
    )
    requested: dict[ProductType, tuple[str, ...]] = {}

    def fetch(
        _repository: EvidenceRepository,
        requests: tuple[EvidenceLookup, ...],
    ) -> tuple[RecordEvidence, ...]:
        records = []
        for request in requests:
            requested[request.product_type] = request.field_ids
            for product_id in request.product_ids:
                records.append(
                    RecordEvidence(
                        product_type=request.product_type,
                        product_id=product_id,
                        direct=tuple(
                            template.model_copy(
                                update={
                                    "evidence_id": (
                                        f"{request.product_type.value}:{product_id}:{field_id}"
                                    ),
                                    "product_type": request.product_type,
                                    "product_id": product_id,
                                    "field_id": field_id,
                                }
                            )
                            for field_id in request.field_ids
                        ),
                        derived=(),
                    )
                )
        return tuple(records)

    monkeypatch.setattr(EvidenceRepository, "fetch_final_record_evidence", fetch)
    try:
        EvidenceBuilder().build(plan=validated, policy_result=policy, repository=repository)
    finally:
        session._close()

    assert "total_fee" in requested[ProductType.DOMESTIC_ETF]
    assert "return_1d" not in requested[ProductType.DOMESTIC_ETF]
    assert "return_1d" in requested[ProductType.OVERSEAS_ETF]
    assert "total_fee" not in requested[ProductType.OVERSEAS_ETF]


def test_cross_product_dual_lens_rank_summaries_stay_within_context_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Global cell refs and per-row tie summaries must not overflow a bounded fact pack."""
    from tests.unit.quality.test_pipeline_order import _listed
    from tests.unit.query.test_semantic_validator import _context

    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest, ClaimKind
    from finproof.domain.quality import QualityStatus
    from finproof.domain.query_plan import (
        Intent,
        ProductType,
        QueryPlan,
        ResultGrain,
        SortDirection,
        SortSpec,
        TopKScope,
    )
    from finproof.evidence import ClaimVerifier, EvidenceBuilder, serialize_evidence_context
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.storage import (
        RawExecutionResult,
        RawFieldValue,
        RawProductRow,
        RawSegmentResult,
    )
    from finproof.storage.repositories.evidence import (
        EvidenceLookup,
        EvidenceRepository,
        RecordEvidence,
    )

    session, _ = _bond_evidence_session()
    repository = EvidenceRepository(session)
    template = repository.fetch_final_record_evidence(
        (
            EvidenceLookup(
                product_type=ProductType.DOMESTIC_BOND,
                product_ids=("KR0000000001",),
                field_ids=("product_id", "buy_yield"),
            ),
        )
    )[0]
    templates = {item.field_id: item for item in template.direct}
    ranked = {
        ProductType.DOMESTIC_ETF: (
            ("KR7251340006", Decimal("0.64")),
            ("KR7236350005", Decimal("0.59")),
            ("KR7091160002", Decimal("0.52")),
            ("KR7091220004", Decimal("0.52")),
        ),
        ProductType.OVERSEAS_ETF: (
            ("SURI.K", Decimal("2.50")),
            ("TXXD.O", Decimal("1.89")),
            ("TXXH.O", Decimal("1.89")),
            ("TXXS.O", Decimal("1.89")),
        ),
    }
    recorded = {
        ProductType.DOMESTIC_ETF: (
            "KR7069500007",
            "KR7069660009",
            "KR7091170001",
            "KR7091180000",
        ),
        ProductType.OVERSEAS_ETF: ("AAAU.K", "ADIV.K", "AGQ", "AIBD.K"),
    }
    values_by_identity = {
        (product_type, product_id): (value, QualityStatus.VALID)
        for product_type, items in ranked.items()
        for product_id, value in items
    } | {
        (product_type, product_id): (
            Decimal(0),
            QualityStatus.RECORDED_ZERO_UNVERIFIED,
        )
        for product_type, product_ids in recorded.items()
        for product_id in product_ids
    }

    def row(
        product_type: ProductType,
        product_id: str,
        value: Decimal,
        quality: QualityStatus,
    ) -> RawProductRow:
        listed = _listed(
            product_id,
            product_type,
            "KRW" if product_type is ProductType.DOMESTIC_ETF else "USD",
            "100",
        )
        return listed.model_copy(
            update={
                "values": (
                    *listed.values,
                    RawFieldValue(field_id="total_fee", value=value, quality_status=quality),
                )
            }
        )

    plan = QueryPlan(
        intent=Intent.SCREEN_RANK,
        product_types=tuple(ranked),
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.PRODUCT,
        filters=(),
        metrics=("total_fee",),
        sort=(SortSpec(field="total_fee", direction=SortDirection.DESC),),
        aggregation=None,
        top_k=4,
        top_k_scope=TopKScope.PER_PRODUCT_TYPE,
        needs_clarification=False,
        clarification_reason="",
    )
    validated = SemanticValidator(repository._fields).validate(
        plan,
        resolutions=ResolutionBundle(results=()),
        context=_context(),
    )
    bundle = ExecutionBundleBuilder(repository._fields).build(validated, context=_context())
    segments = tuple(
        RawSegmentResult(
            product_type=product_type,
            native_result_grain=ResultGrain.LISTED_PRODUCT,
            rows=tuple(
                row(product_type, product_id, value, quality)
                for (selected_type, product_id), (value, quality) in values_by_identity.items()
                if selected_type is product_type
            ),
            candidate_count=8,
            max_batch_rows=8,
        )
        for product_type in ranked
    )
    policy = PolicyEngine().apply(
        RawExecutionResult(segments=segments, candidate_count=16),
        bundle=bundle,
    )

    def fetch(
        _repository: EvidenceRepository,
        requests: tuple[EvidenceLookup, ...],
    ) -> tuple[RecordEvidence, ...]:
        records = []
        for request in requests:
            for product_id in request.product_ids:
                value, item_quality = values_by_identity[(request.product_type, product_id)]
                direct = []
                for field_id in request.field_ids:
                    template_item = templates[
                        "product_id" if field_id == "product_id" else "buy_yield"
                    ]
                    normalized = product_id if field_id == "product_id" else value
                    quality = QualityStatus.VALID if field_id == "product_id" else item_quality
                    direct.append(
                        template_item.model_copy(
                            update={
                                "evidence_id": (
                                    f"{request.product_type.value}:{product_id}:{field_id}"
                                ),
                                "product_type": request.product_type,
                                "product_id": product_id,
                                "field_id": field_id,
                                "value": template_item.value.model_copy(
                                    update={
                                        "raw_value": str(normalized),
                                        "normalized_value": normalized,
                                        "quality_status": quality,
                                    }
                                ),
                            }
                        )
                    )
                records.append(
                    RecordEvidence(
                        product_type=request.product_type,
                        product_id=product_id,
                        direct=tuple(direct),
                        derived=(),
                    )
                )
        return tuple(records)

    monkeypatch.setattr(EvidenceRepository, "fetch_final_record_evidence", fetch)
    evidence = EvidenceBuilder().build(
        plan=validated,
        policy_result=policy,
        repository=repository,
    )
    context = serialize_evidence_context(evidence)
    general = tuple(
        item for item in evidence.summaries if item.kind.value in {"count", "exclusion"}
    )
    partitions = tuple(item for item in evidence.summaries if item.kind.value == "partition")
    ties = tuple(item for item in evidence.summaries if item.kind.value == "tie")
    verified = ClaimVerifier().verify(
        AnswerRenderer().render(
            request=AnswerRequest(question_id="q-bounded-cross-product", question="총보수 순위"),
            plan=plan,
            evidence=evidence,
        ),
        evidence,
    )

    assert len(context.encode()) <= 24_000
    assert all(not item.evidence_ids for item in general)
    assert {len(item.evidence_ids) for item in partitions} == {4}
    assert len(ties) == 2
    assert {len(item.evidence_ids) for item in ties} == {2, 3}
    assert all(claim.evidence_ids for claim in verified.claims if claim.kind is ClaimKind.NUMERIC)
    session._close()


def test_builder_exposes_empty_per_product_type_rank_partition_in_answer() -> None:
    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest
    from finproof.domain.execution import ValidatedQueryPlan
    from finproof.domain.query_plan import (
        Intent,
        ProductType,
        QueryPlan,
        ResultGrain,
        SortDirection,
        SortSpec,
        TopKScope,
    )
    from finproof.evidence import ClaimVerifier, EvidenceBuilder
    from finproof.quality import (
        CompatibilityPartition,
        MetricPolicyResult,
        MetricValue,
        PolicyExecutionResult,
        PolicyRow,
        StateEvaluation,
    )
    from finproof.storage import RawFieldValue, RawProductRow
    from finproof.storage.repositories.evidence import EvidenceRepository

    session, _ = _bond_evidence_session()

    def row(product_type: ProductType, product_id: str) -> PolicyRow:
        return PolicyRow(
            raw=RawProductRow(
                product_type=product_type,
                native_result_grain=ResultGrain.LISTED_PRODUCT,
                product_id=product_id,
                values=(
                    RawFieldValue(field_id="product_id", value=product_id, quality_status="valid"),
                ),
            ),
            state=StateEvaluation(product_id=product_id, eligible=True, state_ids=(), warnings=()),
        )

    rows = (
        row(ProductType.DOMESTIC_ETN, "DOMESTIC-MISSING"),
        row(ProductType.OVERSEAS_ETN, "OVERSEAS-VALID"),
    )
    overseas_value = MetricValue(
        metric_id="overseas_etf.total_fee",
        product_type=ProductType.OVERSEAS_ETN,
        product_id="OVERSEAS-VALID",
        value=Decimal("0.85"),
        quality_status="valid",
        period="annual_source_convention",
    )
    policy = PolicyExecutionResult(
        included_rows=rows,
        excluded_filter_count=0,
        excluded_state_count=0,
        excluded_metric_count=1,
        metric_policy=MetricPolicyResult(
            recorded_values=(overseas_value,),
            comparison_valid_values=(overseas_value,),
            excluded_count=1,
            warnings=("metric values excluded from comparison",),
        ),
        dual_lens_labels=(),
        selected_rows=(),
        partitions=(
            CompatibilityPartition(
                compatibility_key=(
                    "annual_fee:None:annual_source_convention:same_definition_with_source_caveat"
                ),
                currency=None,
                period="annual_source_convention",
                values=(overseas_value,),
                selected_values=(),
                caveats=(),
            ),
        ),
        aggregates=(),
        ranks=(),
        warnings=("metric values excluded from comparison",),
    )
    plan = QueryPlan(
        intent=Intent.SCREEN_RANK,
        product_types=(ProductType.DOMESTIC_ETN, ProductType.OVERSEAS_ETN),
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.PRODUCT,
        filters=(),
        metrics=("total_fee",),
        sort=(SortSpec(field="total_fee", direction=SortDirection.ASC),),
        aggregation=None,
        top_k=3,
        top_k_scope=TopKScope.PER_PRODUCT_TYPE,
        needs_clarification=False,
        clarification_reason="",
    )

    evidence = EvidenceBuilder().build(
        plan=ValidatedQueryPlan._issue(plan=plan, resolutions=(), context=()),
        policy_result=policy,
        repository=EvidenceRepository(session),
    )
    domestic = next(
        summary
        for summary in evidence.summaries
        if summary.kind.value == "partition"
        and summary.product_types == (ProductType.DOMESTIC_ETN,)
    )
    draft = AnswerRenderer().render(
        request=AnswerRequest(question_id="q-empty-partition", question="ETN 유형별 하위 3개"),
        plan=plan,
        evidence=evidence,
    )

    assert (domestic.included_count, domestic.excluded_count, domestic.value) == (0, 1, 0)
    assert "국내 ETN 비교 가능 결과: 0건" in draft.text
    assert "domestic_etn/listed_product" not in draft.text
    assert "0건" in draft.text
    assert ClaimVerifier().verify(draft, evidence).claims == draft.claims
    session._close()


def test_builder_translates_dual_lens_labels_from_answer_registry() -> None:
    from tests.unit.query.test_semantic_validator import _plan

    from finproof.answer.templates import wording_text
    from finproof.domain.execution import ValidatedQueryPlan
    from finproof.evidence import EvidenceBuilder
    from finproof.quality import PolicyExecutionResult
    from finproof.quality.metric_policy import MetricPolicyResult
    from finproof.storage.repositories.evidence import EvidenceRepository

    session, _ = _bond_evidence_session()
    policy = PolicyExecutionResult(
        included_rows=(),
        excluded_filter_count=0,
        excluded_state_count=0,
        excluded_metric_count=0,
        metric_policy=MetricPolicyResult(
            recorded_values=(), comparison_valid_values=(), excluded_count=0, warnings=()
        ),
        dual_lens_labels=("recorded", "comparison_valid"),
        selected_rows=(),
        partitions=(),
        aggregates=(),
        ranks=(),
        warnings=(),
    )
    evidence = EvidenceBuilder().build(
        plan=ValidatedQueryPlan._issue(
            plan=_plan().model_copy(update={"top_k": 1}), resolutions=(), context=()
        ),
        policy_result=policy,
        repository=EvidenceRepository(session),
    )
    wording = session.registries.answers.document["wording"]
    assert isinstance(wording, Mapping)
    assert wording_text(wording, "recorded_view_label") in evidence.material_policy_limitations
    assert wording_text(wording, "comparison_view_label") in evidence.material_policy_limitations
    assert "recorded" not in evidence.material_policy_limitations
    assert "comparison_valid" not in evidence.material_policy_limitations
    session._close()


def test_builder_records_post_filter_count_before_state_exclusions() -> None:
    """Removing the pre-state count value would hide the source-recorded lens."""
    from tests.unit.query.test_semantic_validator import _plan

    from finproof.domain.execution import ValidatedQueryPlan
    from finproof.domain.query_plan import (
        AggregationFunction,
        AggregationSpec,
        Intent,
        ProductType,
        ResultGrain,
    )
    from finproof.evidence import EvidenceBuilder
    from finproof.quality import AggregatePolicyResult, PolicyExecutionResult, PolicyRow
    from finproof.quality.metric_policy import MetricPolicyResult
    from finproof.quality.state import StateEvaluation
    from finproof.storage import RawFieldValue, RawProductRow
    from finproof.storage.repositories.evidence import EvidenceRepository

    session, _ = _bond_evidence_session()
    row = PolicyRow(
        raw=RawProductRow(
            product_type=ProductType.DOMESTIC_BOND,
            native_result_grain=ResultGrain.INSTRUMENT,
            product_id="KR0000000001",
            values=(
                RawFieldValue(field_id="product_id", value="KR0000000001", quality_status="valid"),
            ),
        ),
        state=StateEvaluation(product_id="KR0000000001", eligible=True, state_ids=(), warnings=()),
    )
    policy = PolicyExecutionResult(
        included_rows=(row,) * 254,
        excluded_filter_count=0,
        excluded_state_count=71,
        excluded_metric_count=0,
        metric_policy=MetricPolicyResult(
            recorded_values=(), comparison_valid_values=(), excluded_count=0, warnings=()
        ),
        dual_lens_labels=(),
        selected_rows=(),
        partitions=(),
        aggregates=(
            AggregatePolicyResult(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                partition_key="count:instrument:domestic_bond",
                field_id=None,
                group_values=(),
                value=254,
                included_count=254,
                excluded_count=71,
                policy_id="count:count",
                evidence_requirements=("value", "quality", "count"),
            ),
        ),
        ranks=(),
        warnings=(),
    )
    plan = ValidatedQueryPlan._issue(
        plan=_plan().model_copy(
            update={
                "intent": Intent.AGGREGATE,
                "metrics": (),
                "aggregation": AggregationSpec(
                    function=AggregationFunction.COUNT, field=None, group_by=()
                ),
            }
        ),
        resolutions=(),
        context=(),
    )
    evidence = EvidenceBuilder().build(
        plan=plan,
        policy_result=policy,
        repository=EvidenceRepository(session),
    )

    count = next(item for item in evidence.summaries if item.kind.value == "count")
    assert (count.value, count.included_count, count.excluded_count) == (325, 254, 71)
    session._close()


def test_aggregate_included_count_and_missing_limitation_are_bound() -> None:
    from tests.unit.query.test_semantic_validator import _plan

    from finproof.domain.execution import ValidatedQueryPlan
    from finproof.domain.query_plan import (
        AggregationFunction,
        AggregationSpec,
        Intent,
        ProductType,
        ResultGrain,
    )
    from finproof.evidence import EvidenceBuilder
    from finproof.quality import (
        AggregatePolicyResult,
        MetricValue,
        PolicyExecutionResult,
        PolicyRow,
    )
    from finproof.quality.metric_policy import MetricPolicyResult
    from finproof.quality.state import StateEvaluation
    from finproof.storage import RawFieldValue, RawProductRow
    from finproof.storage.repositories.evidence import EvidenceRepository

    session, _ = _bond_evidence_session()
    row = PolicyRow(
        raw=RawProductRow(
            product_type=ProductType.DOMESTIC_BOND,
            native_result_grain=ResultGrain.INSTRUMENT,
            product_id="KR0000000001",
            values=(
                RawFieldValue(field_id="product_id", value="KR0000000001", quality_status="valid"),
                RawFieldValue(field_id="buy_yield", value=Decimal("2.25"), quality_status="valid"),
            ),
        ),
        state=StateEvaluation(product_id="KR0000000001", eligible=True, state_ids=(), warnings=()),
    )
    valid = MetricValue(
        metric_id="bond.buy_yield",
        product_type=ProductType.DOMESTIC_BOND,
        product_id="KR0000000001",
        value=Decimal("2.25"),
        quality_status="valid",
    )
    missing = MetricValue(
        metric_id="bond.buy_yield",
        product_type=ProductType.DOMESTIC_BOND,
        product_id="MISSING",
        value=None,
        quality_status="missing_blank",
    )
    policy = PolicyExecutionResult(
        included_rows=(row,),
        excluded_filter_count=0,
        excluded_state_count=0,
        excluded_metric_count=1,
        metric_policy=MetricPolicyResult(
            recorded_values=(valid,),
            comparison_valid_values=(valid,),
            excluded_count=1,
            warnings=("metric values excluded from comparison",),
        ),
        dual_lens_labels=(),
        selected_rows=(),
        partitions=(),
        aggregates=(
            AggregatePolicyResult(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                partition_key="bond_buy_yield:none",
                field_id="buy_yield",
                group_values=(),
                value=Decimal("2.25"),
                included_count=1,
                excluded_count=1,
                policy_id="bond.buy_yield:avg",
                evidence_requirements=("value", "quality", "count"),
                product_ids=("KR0000000001",),
            ),
        ),
        ranks=(),
        warnings=("metric values excluded from comparison",),
        metric_values=(valid, missing),
    )
    plan = ValidatedQueryPlan._issue(
        plan=_plan().model_copy(
            update={
                "intent": Intent.AGGREGATE,
                "metrics": (),
                "aggregation": AggregationSpec(
                    function=AggregationFunction.AVG,
                    field="buy_yield",
                    group_by=(),
                ),
            }
        ),
        resolutions=(),
        context=(),
    )

    evidence = EvidenceBuilder().build(
        plan=plan,
        policy_result=policy,
        repository=EvidenceRepository(session),
    )

    aggregate = next(item for item in evidence.summaries if item.kind.value == "aggregate")
    assert (aggregate.included_count, aggregate.excluded_count) == (1, 1)
    assert any(
        "1건" in limitation and "포함" in limitation and "제외" in limitation
        for limitation in evidence.material_policy_limitations
    )
    session._close()


def test_aggregate_sample_rows_obey_the_configured_table_bound() -> None:
    from tests.unit.query.test_semantic_validator import _plan

    from finproof.domain.query_plan import AggregationFunction, AggregationSpec, Intent
    from finproof.evidence.builder import _bounded_selected_rows, _partition_values_for_evidence
    from finproof.quality import CompatibilityPartition, PolicyRow
    from finproof.storage.repositories.evidence import EvidenceRepository

    session, _ = _bond_evidence_session()
    plan = _plan().model_copy(
        update={
            "intent": Intent.AGGREGATE,
            "metrics": (),
            "aggregation": AggregationSpec(
                function=AggregationFunction.COUNT, field=None, group_by=()
            ),
        }
    )
    rows = cast(tuple[PolicyRow, ...], tuple(object() for _ in range(50)))

    assert len(_bounded_selected_rows(plan, rows, EvidenceRepository(session))) == 20
    partitions = cast(tuple[CompatibilityPartition, ...], (object(),))
    assert _partition_values_for_evidence(plan, (), partitions) == ()
    session._close()


def test_builder_exposes_recorded_zero_with_matching_source_evidence() -> None:
    """Dropping the recorded lens would hide policy-excluded source values."""
    from tests.unit.query.test_semantic_validator import _plan

    from finproof.domain.execution import ValidatedQueryPlan
    from finproof.domain.query_plan import (
        Intent,
        ProductType,
        ResultGrain,
        SortDirection,
        SortSpec,
    )
    from finproof.evidence import EvidenceBuilder
    from finproof.evidence.builder import _bounded_recorded_values
    from finproof.quality import PolicyExecutionResult, PolicyRow
    from finproof.quality.metric_policy import MetricPolicyResult, MetricValue
    from finproof.quality.state import StateEvaluation
    from finproof.storage import RawFieldValue, RawProductRow
    from finproof.storage.repositories.evidence import EvidenceRepository

    session, _ = _bond_evidence_session(buy_yield="0")
    row = PolicyRow(
        raw=RawProductRow(
            product_type=ProductType.DOMESTIC_BOND,
            native_result_grain=ResultGrain.INSTRUMENT,
            product_id="KR0000000001",
            values=(
                RawFieldValue(field_id="product_id", value="KR0000000001", quality_status="valid"),
                RawFieldValue(
                    field_id="buy_yield",
                    value=Decimal("0"),
                    quality_status="recorded_zero_unverified",
                ),
            ),
        ),
        state=StateEvaluation(product_id="KR0000000001", eligible=True, state_ids=(), warnings=()),
    )
    policy = PolicyExecutionResult(
        included_rows=(row,),
        excluded_filter_count=0,
        excluded_state_count=0,
        excluded_metric_count=1,
        metric_policy=MetricPolicyResult(
            recorded_values=(
                MetricValue(
                    metric_id="bond.buy_yield",
                    product_type=ProductType.DOMESTIC_BOND,
                    product_id="KR0000000001",
                    value=Decimal("0"),
                    quality_status="recorded_zero_unverified",
                ),
            ),
            comparison_valid_values=(),
            excluded_count=1,
            warnings=("recorded zero excluded from comparison",),
        ),
        dual_lens_labels=("recorded", "comparison_valid"),
        selected_rows=(),
        partitions=(),
        aggregates=(),
        ranks=(),
        warnings=("recorded zero excluded from comparison",),
    )
    plan = ValidatedQueryPlan._issue(
        plan=_plan().model_copy(
            update={
                "intent": Intent.SCREEN_RANK,
                "sort": (SortSpec(field="buy_yield", direction=SortDirection.ASC),),
            }
        ),
        resolutions=(),
        context=(),
    )
    recorded_zero = policy.metric_policy.recorded_values[0]
    recorded_values = _bounded_recorded_values(
        plan=plan.plan,
        policy_result=policy.model_copy(
            update={
                "metric_policy": policy.metric_policy.model_copy(
                    update={
                        "recorded_values": (
                            recorded_zero,
                            recorded_zero.model_copy(
                                update={
                                    "product_id": "NONZERO-EXCLUDED",
                                    "value": Decimal("-4381.56"),
                                }
                            ),
                        )
                    }
                )
            }
        ),
        repository=EvidenceRepository(session),
    )
    assert recorded_values == (recorded_zero,)

    descending = _bounded_recorded_values(
        plan=plan.plan.model_copy(
            update={
                "sort": (SortSpec(field="buy_yield", direction=SortDirection.DESC),),
                "top_k": 1,
            }
        ),
        policy_result=policy.model_copy(
            update={
                "metric_policy": policy.metric_policy.model_copy(
                    update={
                        "recorded_values": (
                            recorded_zero,
                            recorded_zero.model_copy(
                                update={
                                    "product_id": "VALID-HIGH",
                                    "value": Decimal("5"),
                                    "quality_status": "valid",
                                }
                            ),
                        ),
                        "comparison_valid_values": (
                            recorded_zero.model_copy(
                                update={
                                    "product_id": "VALID-HIGH",
                                    "value": Decimal("5"),
                                    "quality_status": "valid",
                                }
                            ),
                        ),
                    }
                )
            }
        ),
        repository=EvidenceRepository(session),
    )
    assert descending == ()

    evidence = EvidenceBuilder().build(
        plan=plan,
        policy_result=policy,
        repository=EvidenceRepository(session),
    )

    assert next(item for item in evidence.summaries if item.kind.value == "count").value is None
    recorded = next(item for item in evidence.summaries if item.kind.value == "recorded")
    assert (recorded.product_id, recorded.metric_id, recorded.value) == (
        "KR0000000001",
        "buy_yield",
        Decimal("0"),
    )
    direct = next(item for item in evidence.direct if item.evidence_id in recorded.evidence_ids)
    assert direct.value.normalized_value == Decimal("0")
    assert any(
        "실제 무보수" in item and "검증되지 않았" in item
        for item in evidence.material_policy_limitations
    )
    session._close()


def test_recorded_zero_lens_uses_each_product_types_compatible_sort() -> None:
    """A heterogeneous rank must not apply one product type's field to another."""
    from tests.unit.query.test_semantic_validator import _plan

    from finproof.domain.query_plan import (
        Intent,
        ProductType,
        SortDirection,
        SortSpec,
        TopKScope,
    )
    from finproof.evidence.builder import _bounded_recorded_values
    from finproof.quality import PolicyExecutionResult
    from finproof.quality.metric_policy import MetricPolicyResult, MetricValue
    from finproof.storage.repositories.evidence import EvidenceRepository

    session, _ = _bond_evidence_session()
    bond_zero = MetricValue(
        metric_id="bond.buy_yield",
        product_type=ProductType.DOMESTIC_BOND,
        product_id="BOND-ZERO",
        value=Decimal("0"),
        quality_status="recorded_zero_unverified",
    )
    etf_zero = MetricValue(
        metric_id="domestic_etf.total_fee",
        product_type=ProductType.DOMESTIC_ETF,
        product_id="ETF-ZERO",
        value=Decimal("0"),
        quality_status="recorded_zero_unverified",
    )
    policy = PolicyExecutionResult(
        included_rows=(),
        excluded_filter_count=0,
        excluded_state_count=0,
        excluded_metric_count=2,
        metric_policy=MetricPolicyResult(
            recorded_values=(bond_zero, etf_zero),
            comparison_valid_values=(),
            excluded_count=2,
            warnings=("recorded zero excluded from comparison",),
        ),
        dual_lens_labels=("recorded", "comparison_valid"),
        selected_rows=(),
        partitions=(),
        aggregates=(),
        ranks=(),
        warnings=("recorded zero excluded from comparison",),
    )
    plan = _plan().model_copy(
        update={
            "intent": Intent.SCREEN_RANK,
            "product_types": (
                ProductType.DOMESTIC_BOND,
                ProductType.DOMESTIC_ETF,
            ),
            "metrics": ("buy_yield", "total_fee"),
            "sort": (
                SortSpec(field="buy_yield", direction=SortDirection.ASC),
                SortSpec(field="total_fee", direction=SortDirection.ASC),
            ),
            "top_k": 1,
            "top_k_scope": TopKScope.PER_PRODUCT_TYPE,
        }
    )

    assert _bounded_recorded_values(
        plan=plan,
        policy_result=policy,
        repository=EvidenceRepository(session),
    ) == (bond_zero, etf_zero)
    session._close()


def test_recorded_selection_stays_within_final_evidence_budget() -> None:
    """A recorded-only product cannot turn an existing 50-product selection into 51."""
    from finproof.domain.query_plan import ProductType
    from finproof.evidence.builder import _fit_recorded_values
    from finproof.quality.metric_policy import MetricValue

    selected = dict.fromkeys((ProductType.DOMESTIC_BOND, f"BOND-{index:02}") for index in range(50))
    recorded = MetricValue(
        metric_id="bond.buy_yield",
        product_type=ProductType.DOMESTIC_BOND,
        product_id="RECORDED-ONLY",
        value=Decimal("0"),
        quality_status="recorded_zero_unverified",
    )

    assert _fit_recorded_values(selected, (recorded,)) == ()
    assert len(selected) == 50


def test_recorded_evidence_matching_keeps_product_type_identity() -> None:
    """Matching only product_id would cross-link equal identifiers across product types."""
    from finproof.domain.query_plan import ProductType
    from finproof.evidence.builder import _recorded_evidence_ids
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, _ = _bond_evidence_session()
    record = EvidenceRepository(session).fetch_final_record_evidence(
        (
            EvidenceLookup(
                product_type=ProductType.DOMESTIC_BOND,
                product_ids=("KR0000000001",),
                field_ids=("buy_yield", "remaining_days_at_as_of"),
            ),
        )
    )[0]
    bond_direct, bond_derived = record.direct[0], record.derived[0]
    etf_direct = bond_direct.model_copy(
        update={
            "evidence_id": "domestic_etf:SAME:buy_yield",
            "product_type": ProductType.DOMESTIC_ETF,
            "product_id": "SAME",
        }
    )
    etf_derived = bond_derived.model_copy(
        update={
            "evidence_id": "domestic_etf:SAME:remaining_days_at_as_of",
            "product_type": ProductType.DOMESTIC_ETF,
            "product_id": "SAME",
        }
    )
    bond_direct = bond_direct.model_copy(
        update={"evidence_id": "domestic_bond:SAME:buy_yield", "product_id": "SAME"}
    )
    bond_derived = bond_derived.model_copy(
        update={"evidence_id": "domestic_bond:SAME:remaining_days_at_as_of", "product_id": "SAME"}
    )

    assert _recorded_evidence_ids(
        items=(bond_direct, etf_direct, bond_derived, etf_derived),
        product_type=ProductType.DOMESTIC_BOND,
        product_id="SAME",
        field_id="buy_yield",
    ) == ("domestic_bond:SAME:buy_yield",)
    assert _recorded_evidence_ids(
        items=(bond_direct, etf_direct, bond_derived, etf_derived),
        product_type=ProductType.DOMESTIC_BOND,
        product_id="SAME",
        field_id="remaining_days_at_as_of",
    ) == ("domestic_bond:SAME:remaining_days_at_as_of",)
    session._close()


def test_builder_exposes_credit_rating_threshold_policy_limitation() -> None:
    from tests.unit.query.test_semantic_validator import _plan

    from finproof.domain.execution import ValidatedQueryPlan
    from finproof.domain.query_plan import (
        FilterClause,
        FilterOperator,
        Intent,
        SortDirection,
        SortSpec,
    )
    from finproof.evidence import EvidenceBuilder
    from finproof.quality import PolicyExecutionResult
    from finproof.quality.metric_policy import MetricPolicyResult
    from finproof.storage.repositories.evidence import EvidenceRepository

    session, _ = _bond_evidence_session()
    policy = PolicyExecutionResult(
        included_rows=(),
        excluded_filter_count=0,
        excluded_state_count=0,
        excluded_metric_count=0,
        metric_policy=MetricPolicyResult(
            recorded_values=(), comparison_valid_values=(), excluded_count=0, warnings=()
        ),
        dual_lens_labels=(),
        selected_rows=(),
        partitions=(),
        aggregates=(),
        ranks=(),
        warnings=(),
    )
    plan = _plan().model_copy(
        update={
            "filters": (
                FilterClause(field="credit_rating", operator=FilterOperator.GTE, value="AA-"),
            )
        }
    )
    evidence = EvidenceBuilder().build(
        plan=ValidatedQueryPlan._issue(plan=plan, resolutions=(), context=()),
        policy_result=policy,
        repository=EvidenceRepository(session),
    )
    assert any(
        "대표 원천 등급" in item and "미평가" in item and "등록되지 않은 등급" in item
        for item in evidence.material_policy_limitations
    )
    assert all("복수 평가기관" not in item for item in evidence.material_policy_limitations)
    rank_plan = plan.model_copy(
        update={
            "intent": Intent.SCREEN_RANK,
            "filters": (
                FilterClause(field="credit_rating", operator=FilterOperator.IS_NOT_MISSING),
            ),
            "metrics": ("credit_rating",),
            "sort": (SortSpec(field="credit_rating", direction=SortDirection.DESC),),
        }
    )
    rank_evidence = EvidenceBuilder().build(
        plan=ValidatedQueryPlan._issue(plan=rank_plan, resolutions=(), context=()),
        policy_result=policy,
        repository=EvidenceRepository(session),
    )
    assert any(
        "레지스트리 순서" in item and "미평가" in item and "등록되지 않은 등급" in item
        for item in rank_evidence.material_policy_limitations
    )
    session._close()


def test_builder_cross_currency_limitation_names_missing_fixed_fx_basis() -> None:
    """Currency separation alone would omit why an integrated AUM rank is invalid."""
    from finproof.evidence.builder import _cross_currency_limitations

    assert any(
        "고정 환율 기준이 없어" in item and "통합 순위" in item
        for item in _cross_currency_limitations({"KRW", "USD"})
    )
    assert _cross_currency_limitations({"USD"}) == ()


def test_compare_builder_and_renderer_expose_evidenced_remaining_days_difference() -> None:
    """Listing two remaining-day values would omit the requested deterministic difference."""
    from tests.unit.answer.test_renderer import _plan

    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest
    from finproof.domain.evidence import EvidenceBundle
    from finproof.domain.query_plan import Intent, ProductType
    from finproof.evidence import ClaimVerifier
    from finproof.evidence.builder import _remaining_days_difference
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, _ = _bond_evidence_session()
    template = (
        EvidenceRepository(session)
        .fetch_final_record_evidence(
            (
                EvidenceLookup(
                    product_type=ProductType.DOMESTIC_BOND,
                    product_ids=("KR0000000001",),
                    field_ids=("remaining_days_at_as_of",),
                ),
            )
        )[0]
        .derived[0]
    )
    product_ids = ("KR101501DD13", "KR101501DD47")
    remaining_days = (569, 659)
    items = tuple(
        template.model_copy(
            update={
                "evidence_id": f"domestic_bond:{product_id}:remaining_days_at_as_of",
                "product_id": product_id,
                "value": template.value.model_copy(
                    update={
                        "value": days,
                        "inputs": tuple(
                            source.model_copy(update={"source_row_number": 77 + index})
                            for source in template.value.inputs
                        ),
                    }
                ),
            }
        )
        for index, (product_id, days) in enumerate(zip(product_ids, remaining_days, strict=True))
    )
    plan = _plan().model_copy(
        update={
            "intent": Intent.COMPARE,
            "metrics": ("remaining_days_at_as_of",),
            "top_k": 2,
        }
    )
    difference = _remaining_days_difference(
        plan=plan,
        items=items,
        rule_version="1.0.0",
    )[0]
    evidence = EvidenceBundle(
        direct=(),
        derived=(*items, difference),
        summaries=(),
        material_policy_limitations=(),
    )
    draft = AnswerRenderer().render(
        request=AnswerRequest(question_id="q-days-difference", question="잔존기간 차이는?"),
        plan=plan,
        evidence=evidence,
    )

    assert difference.product_id == "KR101501DD47"
    assert difference.value.value == 90
    assert len(difference.value.inputs) == 2
    assert "KR101501DD47의 기준일 잔존일수가 KR101501DD13보다 90일 깁니다." in draft.text
    assert ClaimVerifier().verify(draft, evidence).claims == draft.claims
    session._close()


def test_generic_comparison_difference_supports_decimal_and_date_and_rejects_one_value() -> None:
    from tests.unit.answer.test_renderer import _plan

    from finproof.domain.query_plan import Intent, ProductType
    from finproof.evidence.builder import _comparison_difference, _comparison_evidence
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    assert _comparison_difference(Decimal("144.07"), Decimal("144.21")) == Decimal("0.14")
    assert _comparison_difference(date(2029, 12, 19), date(2031, 7, 21)) == 579
    assert _comparison_difference(Decimal("1"), None) is None

    session, _ = _bond_evidence_session()
    template = (
        EvidenceRepository(session)
        .fetch_final_record_evidence(
            (
                EvidenceLookup(
                    product_type=ProductType.DOMESTIC_BOND,
                    product_ids=("KR0000000001",),
                    field_ids=("buy_yield",),
                ),
            )
        )[0]
        .direct[0]
    )
    direct = tuple(
        template.model_copy(
            update={
                "evidence_id": f"domestic_bond:{product_id}:buy_yield",
                "product_id": product_id,
                "value": template.value.model_copy(update={"normalized_value": value}),
            }
        )
        for product_id, value in (("B1", Decimal("2.843")), ("B2", Decimal("2.934")))
    )
    comparison = _comparison_evidence(
        plan=_plan().model_copy(
            update={"intent": Intent.COMPARE, "metrics": ("buy_yield",), "top_k": 2}
        ),
        items=direct,
        allowed_identities={(ProductType.DOMESTIC_BOND, "B1"), (ProductType.DOMESTIC_BOND, "B2")},
        rule_version="1.0.0",
    )
    assert comparison[0].product_id == "B2"
    assert comparison[0].value.value == Decimal("0.091")
    session._close()


def test_tie_identity_uses_sort_value_and_aggregate_evidence_is_scoped() -> None:
    from finproof.domain.query_plan import ProductType, ResultGrain, TopKScope
    from finproof.evidence.builder import (
        _aggregate_evidence_ids,
        _rank_tie_identity,
        _rank_tie_key,
    )
    from finproof.quality import MetricValue, RankPolicyResult
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    aa = MetricValue(
        metric_id="bond.credit_rating",
        product_type=ProductType.DOMESTIC_BOND,
        product_id="AA",
        value="AA",
        quality_status="valid",
        sort_value=-5,
    )
    aa_zero = aa.model_copy(update={"product_id": "AA0", "value": "AA0"})
    assert _rank_tie_identity(aa) == _rank_tie_identity(aa_zero) == -5
    first = RankPolicyResult(
        value=aa,
        native_result_grain=ResultGrain.INSTRUMENT,
        partition_key="global-rating",
        field_id="credit_rating",
        rank=1,
        tie_count=2,
        policy_id="bond.credit_rating:rank",
        evidence_requirements=("value", "quality", "tie"),
    )
    second = first.model_copy(
        update={
            "value": aa_zero.model_copy(update={"product_type": ProductType.PUBLIC_FUND}),
            "native_result_grain": ResultGrain.FUND_ITEM,
            "policy_id": "fund.risk_grade:rank",
        }
    )
    assert _rank_tie_key(first, scope=TopKScope.GLOBAL) == _rank_tie_key(
        second, scope=TopKScope.GLOBAL
    )

    session, _ = _bond_evidence_session()
    records = EvidenceRepository(session).fetch_final_record_evidence(
        (
            EvidenceLookup(
                product_type=ProductType.DOMESTIC_BOND,
                product_ids=("KR0000000001",),
                field_ids=("buy_yield", "product_id"),
            ),
        )
    )
    direct = records[0].direct
    foreign = direct[0].model_copy(
        update={
            "evidence_id": "public_fund:F1:return_3m",
            "product_type": ProductType.PUBLIC_FUND,
            "product_id": "F1",
            "field_id": "return_3m",
        }
    )
    assert _aggregate_evidence_ids(
        items=(*direct, foreign),
        product_type=ProductType.DOMESTIC_BOND,
        product_ids=("KR0000000001",),
        field_ids=("buy_yield",),
    ) == ("domestic_bond:KR0000000001:buy_yield",)
    session._close()


def test_explicit_state_lens_and_zero_missing_population_remain_visible() -> None:
    from tests.unit.query.test_semantic_validator import _plan

    from finproof.domain.execution import ValidatedQueryPlan
    from finproof.domain.query_plan import (
        AggregationFunction,
        AggregationSpec,
        FilterClause,
        FilterOperator,
        Intent,
    )
    from finproof.evidence import EvidenceBuilder
    from finproof.evidence.builder import _requests_source_lens
    from finproof.quality import PolicyExecutionResult
    from finproof.quality.metric_policy import MetricPolicyResult
    from finproof.storage.repositories.evidence import EvidenceRepository

    policy = PolicyExecutionResult(
        included_rows=(),
        excluded_filter_count=0,
        excluded_state_count=0,
        excluded_metric_count=0,
        metric_policy=MetricPolicyResult(
            recorded_values=(), comparison_valid_values=(), excluded_count=0, warnings=()
        ),
        dual_lens_labels=(),
        selected_rows=(),
        partitions=(),
        aggregates=(),
        ranks=(),
        warnings=(),
    )
    state_plan = _plan().model_copy(
        update={
            "intent": Intent.AGGREGATE,
            "filters": (FilterClause(field="saleable", operator=FilterOperator.EQ, value=True),),
            "metrics": (),
            "aggregation": AggregationSpec(
                function=AggregationFunction.COUNT, field=None, group_by=()
            ),
        }
    )
    assert _requests_source_lens(state_plan, policy_result=policy)

    missing_plan = _plan().model_copy(
        update={
            "intent": Intent.AGGREGATE,
            "filters": (FilterClause(field="buy_yield", operator=FilterOperator.IS_MISSING),),
            "metrics": (),
            "aggregation": AggregationSpec(
                function=AggregationFunction.COUNT, field=None, group_by=()
            ),
        }
    )
    session, _ = _bond_evidence_session()
    evidence = EvidenceBuilder().build(
        plan=ValidatedQueryPlan._issue(plan=missing_plan, resolutions=(), context=()),
        policy_result=policy,
        repository=EvidenceRepository(session),
    )
    missing = next(
        item for item in evidence.summaries if item.partition_key == "policy:bond.buy_yield:missing"
    )
    assert missing.value == 0
    assert any(
        "결측 지표값" in item and "순위에서 제외" in item
        for item in evidence.material_policy_limitations
    )
    session._close()


def test_direct_unverified_zero_warning_is_emitted_without_comparison_warning_duplication() -> None:
    from finproof.domain.quality import QualityStatus
    from finproof.domain.query_plan import ProductType
    from finproof.evidence.builder import _direct_recorded_zero_limitations
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, _ = _bond_evidence_session(buy_yield="0")
    item = (
        EvidenceRepository(session)
        .fetch_final_record_evidence(
            (
                EvidenceLookup(
                    product_type=ProductType.DOMESTIC_BOND,
                    product_ids=("KR0000000001",),
                    field_ids=("buy_yield",),
                ),
            )
        )[0]
        .direct[0]
    )
    item = item.model_copy(
        update={
            "value": item.value.model_copy(
                update={"quality_status": QualityStatus.RECORDED_ZERO_UNVERIFIED}
            )
        }
    )
    warning = _direct_recorded_zero_limitations((item,), existing_warnings=())
    assert len(warning) == 1
    assert "0값" in warning[0]
    assert "검증되지 않" in warning[0]
    assert (
        _direct_recorded_zero_limitations(
            (item,), existing_warnings=("recorded zero excluded from comparison",)
        )
        == ()
    )
    session._close()


def test_rank_evidence_bound_uses_global_or_per_product_type_scope() -> None:
    from finproof.domain.query_plan import ProductType, ResultGrain, TopKScope
    from finproof.evidence.builder import _bounded_ranks
    from finproof.quality import MetricValue, RankPolicyResult

    ranks = tuple(
        RankPolicyResult(
            value=MetricValue(
                metric_id="return_1m",
                product_type=product_type,
                product_id=product_id,
                value=Decimal("5"),
                quality_status="valid",
                currency=None,
                period="1m",
            ),
            native_result_grain=grain,
            partition_key="return_1m|percent|1m|none|available|compatible",
            field_id="return_1m",
            rank=1,
            tie_count=2,
            policy_id="return_1m:rank",
            evidence_requirements=("value", "quality", "tie"),
        )
        for product_type, grain, product_id in (
            (ProductType.DOMESTIC_ETF, ResultGrain.LISTED_PRODUCT, "ETF-1"),
            (ProductType.PUBLIC_FUND, ResultGrain.FUND_ITEM, "FUND-1"),
        )
    )

    assert tuple(
        rank.value.product_id for rank in _bounded_ranks(ranks, top_k=1, scope=TopKScope.GLOBAL)
    ) == ("ETF-1",)
    assert tuple(
        rank.value.product_id
        for rank in _bounded_ranks(ranks, top_k=1, scope=TopKScope.PER_PRODUCT_TYPE)
    ) == ("ETF-1", "FUND-1")


def test_builder_restores_interleaved_global_selection_order_after_grouped_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.domain.execution import ValidatedQueryPlan
    from finproof.domain.query_plan import (
        Intent,
        ProductType,
        QueryPlan,
        ResultGrain,
        TopKScope,
    )
    from finproof.evidence import EvidenceBuilder
    from finproof.quality import PolicyExecutionResult, PolicyRow
    from finproof.quality.metric_policy import MetricPolicyResult
    from finproof.quality.state import StateEvaluation
    from finproof.storage import RawFieldValue, RawProductRow
    from finproof.storage.repositories.evidence import (
        EvidenceLookup,
        EvidenceRepository,
        RecordEvidence,
    )

    session, _ = _bond_evidence_session()
    repository = EvidenceRepository(session)
    template = repository.fetch_final_record_evidence(
        (
            EvidenceLookup(
                product_type=ProductType.DOMESTIC_BOND,
                product_ids=("KR0000000001",),
                field_ids=("product_id",),
            ),
        )
    )[0].direct[0]

    def policy_row(product_type: ProductType, product_id: str) -> PolicyRow:
        raw = RawProductRow(
            product_type=product_type,
            native_result_grain=ResultGrain.LISTED_PRODUCT,
            product_id=product_id,
            values=(
                RawFieldValue(
                    field_id="product_id",
                    value=product_id,
                    quality_status="valid",
                ),
            ),
        )
        return PolicyRow(
            raw=raw,
            state=StateEvaluation(
                product_id=product_id,
                eligible=True,
                state_ids=(),
                warnings=(),
            ),
        )

    selected = (
        policy_row(ProductType.DOMESTIC_ETF, "ETF-1"),
        policy_row(ProductType.DOMESTIC_ETN, "ETN-1"),
        policy_row(ProductType.DOMESTIC_ETF, "ETF-2"),
    )
    supporting = policy_row(ProductType.DOMESTIC_ETN, "UNSELECTED")
    policy = PolicyExecutionResult(
        included_rows=(*selected, supporting),
        excluded_filter_count=0,
        excluded_state_count=0,
        excluded_metric_count=0,
        metric_policy=MetricPolicyResult(
            recorded_values=(),
            comparison_valid_values=(),
            excluded_count=0,
            warnings=(),
        ),
        dual_lens_labels=(),
        selected_rows=selected,
        partitions=(),
        aggregates=(),
        ranks=(),
        warnings=(),
    )
    plan = ValidatedQueryPlan._issue(
        plan=QueryPlan(
            intent=Intent.SCREEN,
            product_types=(ProductType.DOMESTIC_ETF, ProductType.DOMESTIC_ETN),
            entities=(),
            as_of_date=date(2026, 7, 11),
            result_grain=ResultGrain.LISTED_PRODUCT,
            filters=(),
            metrics=(),
            sort=(),
            aggregation=None,
            top_k=3,
            top_k_scope=TopKScope.GLOBAL,
            needs_clarification=False,
            clarification_reason="",
        ),
        resolutions=(),
        context=(),
    )

    def grouped_fetch(
        _repository: EvidenceRepository,
        requests: tuple[EvidenceLookup, ...],
    ) -> tuple[RecordEvidence, ...]:
        return tuple(
            RecordEvidence(
                product_type=request.product_type,
                product_id=product_id,
                direct=(
                    template.model_copy(
                        update={
                            "evidence_id": (
                                f"{request.product_type.value}:{product_id}:product_id"
                            ),
                            "product_type": request.product_type,
                            "product_id": product_id,
                            "value": template.value.model_copy(
                                update={"raw_value": product_id, "normalized_value": product_id}
                            ),
                        }
                    ),
                ),
                derived=(),
            )
            for request in requests
            for product_id in request.product_ids
        )

    monkeypatch.setattr(EvidenceRepository, "fetch_final_record_evidence", grouped_fetch)

    evidence = EvidenceBuilder().build(
        plan=plan,
        policy_result=policy,
        repository=repository,
    )

    assert tuple((item.product_type, item.product_id) for item in evidence.direct) == (
        (ProductType.DOMESTIC_ETF, "ETF-1"),
        (ProductType.DOMESTIC_ETN, "ETN-1"),
        (ProductType.DOMESTIC_ETF, "ETF-2"),
    )
    assert all(item.product_id != "UNSELECTED" for item in evidence.direct)
    session._close()


def test_context_serialization_is_stable_json_safe_size_bounded_and_contains_no_local_runtime_path() -> (  # noqa: E501
    None
):
    import json

    from finproof.domain.evidence import EvidenceBundle
    from finproof.domain.query_plan import ProductType
    from finproof.evidence.serializer import serialize_evidence_context
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, _ = _bond_evidence_session()
    record = EvidenceRepository(session).fetch_final_record_evidence(
        (
            EvidenceLookup(
                product_type=ProductType.DOMESTIC_BOND,
                product_ids=("KR0000000001",),
                field_ids=("buy_yield", "remaining_days_at_as_of"),
            ),
        )
    )[0]
    bundle = EvidenceBundle(
        direct=record.direct,
        derived=record.derived,
        summaries=(),
        material_policy_limitations=("2026-07-11 제공 스냅샷 기준",),
    )

    first = serialize_evidence_context(bundle)
    second = serialize_evidence_context(bundle)

    assert first == second
    payload = json.loads(first)
    direct = dict(zip(payload["direct_fields"], payload["direct"][0], strict=True))
    assert direct["normalized_value"] == "2.25"
    derived = dict(zip(payload["derived_fields"], payload["derived"][0], strict=True))
    source = payload["sources"][derived["inputs"][0][0]]
    assert derived["as_of_date"] == "2026-08-22"
    assert source["source_file"]
    assert source["source_sheet"]
    assert source["source_checksum"]
    assert len(first.encode()) <= 24_000
    assert "/Users/example/runtime/artifacts.duckdb" not in first
    with pytest.raises(ValueError, match="local path"):
        serialize_evidence_context(
            bundle.model_copy(
                update={"material_policy_limitations": ("/Users/example/runtime/artifacts.duckdb",)}
            )
        )
    session._close()


def test_valid_top_k_50_evidence_and_claim_boundary_serializes() -> None:
    from tests.unit.answer.test_renderer import _plan

    from finproof.answer import AnswerRenderer
    from finproof.domain.answers import AnswerRequest
    from finproof.domain.evidence import EvidenceBundle
    from finproof.domain.query_plan import ProductType
    from finproof.evidence import serialize_evidence_context
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    session, _ = _bond_evidence_session()
    originals = (
        EvidenceRepository(session)
        .fetch_final_record_evidence(
            (
                EvidenceLookup(
                    product_type=ProductType.DOMESTIC_BOND,
                    product_ids=("KR0000000001",),
                    field_ids=("buy_yield", "maturity_date"),
                ),
            )
        )[0]
        .direct
    )
    direct = tuple(
        item.model_copy(
            update={
                "evidence_id": f"domestic_bond:B{index:02d}:{item.field_id}",
                "product_id": f"B{index:02d}",
            }
        )
        for index in range(50)
        for item in originals
    )
    evidence = EvidenceBundle(
        direct=direct,
        derived=(),
        summaries=(),
        material_policy_limitations=(),
    )

    context = serialize_evidence_context(evidence)
    draft = AnswerRenderer().render(
        request=AnswerRequest(question_id="q-top-50", question="조건에 맞는 채권 추천"),
        plan=_plan().model_copy(update={"top_k": 50}),
        evidence=evidence,
    )

    payload = json.loads(context)
    assert len(context.encode()) <= 24_000
    direct_records = tuple(
        dict(zip(payload["direct_fields"], item, strict=True)) for item in payload["direct"]
    )
    expected_values = {
        "buy_yield": ("2.25", "2.25", "buy_yield"),
        "maturity_date": ("20270822", "2027-08-22", "mat_dt"),
    }
    assert {item["evidence_id"] for item in direct_records} == {item.evidence_id for item in direct}
    assert all(
        payload["sources"][item["source"]]["source_table"] == "PRBD01N001"
        and payload["sources"][item["source"]]["source_file"]
        and payload["sources"][item["source"]]["source_sheet"]
        and payload["sources"][item["source"]]["source_checksum"]
        and payload["sources"][item["source"]]["source_snapshot_date"] == "2026-08-24"
        and (item["raw_value"], item["normalized_value"], item["source_column_name"])
        == expected_values[item["field_id"]]
        and item["quality_status"] == "valid"
        and item["rule_id"]
        and item["rule_version"]
        and item["source_row_number"] == 77
        and item["source_column_number"]
        and item["source_column_letter"]
        and item["source_applicable_date"] is None
        for item in direct_records
    )
    assert len(draft.claims) == 151
    session._close()


def test_source_samples_use_only_capacity_remaining_after_primary_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.domain.execution import ValidatedQueryPlan
    from finproof.domain.query_plan import Intent, ProductType, QueryPlan, ResultGrain, TopKScope
    from finproof.evidence import EvidenceBuilder
    from finproof.quality import PolicyExecutionResult, PolicyRow
    from finproof.quality.metric_policy import MetricPolicyResult
    from finproof.quality.state import StateEvaluation
    from finproof.storage import RawFieldValue, RawProductRow
    from finproof.storage.repositories.evidence import (
        EvidenceLookup,
        EvidenceRepository,
        RecordEvidence,
    )

    session, _ = _bond_evidence_session()
    repository = EvidenceRepository(session)
    template = repository.fetch_final_record_evidence(
        (
            EvidenceLookup(
                product_type=ProductType.DOMESTIC_BOND,
                product_ids=("KR0000000001",),
                field_ids=("product_id",),
            ),
        )
    )[0].direct[0]

    def row(index: int, *, eligible: bool) -> PolicyRow:
        product_id = f"B{index:02d}"
        return PolicyRow(
            raw=RawProductRow(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                product_id=product_id,
                values=(
                    RawFieldValue(field_id="product_id", value=product_id, quality_status="valid"),
                    RawFieldValue(
                        field_id="buy_yield",
                        value=Decimal("2.5"),
                        quality_status="valid",
                    ),
                ),
            ),
            state=StateEvaluation(
                product_id=product_id,
                eligible=eligible,
                state_ids=(),
                warnings=(),
            ),
        )

    selected = tuple(row(index, eligible=True) for index in range(50))
    source_only = tuple(row(index, eligible=False) for index in range(50, 55))
    policy = PolicyExecutionResult(
        included_rows=selected,
        excluded_filter_count=0,
        excluded_state_count=5,
        excluded_metric_count=0,
        metric_policy=MetricPolicyResult(
            recorded_values=(), comparison_valid_values=(), excluded_count=0, warnings=()
        ),
        dual_lens_labels=(),
        selected_rows=selected,
        partitions=(),
        aggregates=(),
        ranks=(),
        warnings=(),
        source_rows=(*selected, *source_only),
    )
    plan = ValidatedQueryPlan._issue(
        plan=QueryPlan(
            intent=Intent.COMPARE,
            product_types=(ProductType.DOMESTIC_BOND,),
            entities=(),
            as_of_date=date(2026, 7, 11),
            result_grain=ResultGrain.INSTRUMENT,
            filters=(),
            metrics=("buy_yield",),
            sort=(),
            aggregation=None,
            top_k=50,
            top_k_scope=TopKScope.GLOBAL,
            needs_clarification=False,
            clarification_reason="",
        ),
        resolutions=(),
        context=(),
    )

    def fetch(
        _repository: EvidenceRepository,
        requests: tuple[EvidenceLookup, ...],
    ) -> tuple[RecordEvidence, ...]:
        return tuple(
            RecordEvidence(
                product_type=request.product_type,
                product_id=product_id,
                direct=(
                    template.model_copy(
                        update={
                            "evidence_id": f"domestic_bond:{product_id}:product_id",
                            "product_id": product_id,
                            "value": template.value.model_copy(
                                update={"raw_value": product_id, "normalized_value": product_id}
                            ),
                        }
                    ),
                ),
                derived=(),
            )
            for request in requests
            for product_id in request.product_ids
        )

    monkeypatch.setattr(EvidenceRepository, "fetch_final_record_evidence", fetch)
    evidence = EvidenceBuilder().build(plan=plan, policy_result=policy, repository=repository)

    assert len({item.product_id for item in evidence.direct}) == 50
    assert not any(summary.kind.value == "recorded" for summary in evidence.summaries)
    session._close()


def test_heterogeneous_source_lens_skips_metrics_absent_from_product_projection() -> None:
    from finproof.domain.query_plan import Intent, ProductType, QueryPlan, ResultGrain, TopKScope
    from finproof.evidence.builder import _source_lens_summaries
    from finproof.quality import PolicyExecutionResult, PolicyRow
    from finproof.quality.metric_policy import MetricPolicyResult
    from finproof.quality.state import StateEvaluation
    from finproof.storage import RawFieldValue, RawProductRow

    rows = (
        PolicyRow(
            raw=RawProductRow(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                product_id="B1",
                values=(
                    RawFieldValue(field_id="product_id", value="B1", quality_status="valid"),
                    RawFieldValue(
                        field_id="maturity_date",
                        value=date(2027, 7, 11),
                        quality_status="valid",
                    ),
                ),
            ),
            state=StateEvaluation(product_id="B1", eligible=False, state_ids=(), warnings=()),
        ),
        PolicyRow(
            raw=RawProductRow(
                product_type=ProductType.DOMESTIC_ETF,
                native_result_grain=ResultGrain.LISTED_PRODUCT,
                product_id="E1",
                values=(
                    RawFieldValue(field_id="product_id", value="E1", quality_status="valid"),
                    RawFieldValue(
                        field_id="total_fee",
                        value=Decimal("0.1"),
                        quality_status="valid",
                    ),
                ),
            ),
            state=StateEvaluation(product_id="E1", eligible=False, state_ids=(), warnings=()),
        ),
    )
    policy = PolicyExecutionResult(
        included_rows=(),
        excluded_filter_count=0,
        excluded_state_count=2,
        excluded_metric_count=0,
        metric_policy=MetricPolicyResult(
            recorded_values=(), comparison_valid_values=(), excluded_count=0, warnings=()
        ),
        dual_lens_labels=(),
        selected_rows=(),
        partitions=(),
        aggregates=(),
        ranks=(),
        warnings=(),
        source_rows=rows,
    )
    plan = QueryPlan(
        intent=Intent.COMPARE,
        product_types=(ProductType.DOMESTIC_BOND, ProductType.DOMESTIC_ETF),
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.PRODUCT,
        filters=(),
        metrics=("maturity_date", "total_fee"),
        sort=(),
        aggregation=None,
        top_k=2,
        top_k_scope=TopKScope.PER_PRODUCT_TYPE,
        needs_clarification=False,
        clarification_reason="",
    )

    summaries = _source_lens_summaries(
        plan=plan,
        policy_result=policy,
        source_only_rows=rows,
        items=(),
        policy_versions=("test:1",),
        plan_hash="a" * 64,
        version_hash="b" * 64,
        artifact_hash="c" * 64,
    )

    assert {
        (summary.product_id, summary.metric_id)
        for summary in summaries
        if summary.kind.value == "recorded"
    } == {("B1", "maturity_date"), ("E1", "total_fee")}


def test_metrics_empty_screen_does_not_select_state_excluded_source_rows() -> None:
    from finproof.domain.query_plan import (
        FilterClause,
        FilterOperator,
        Intent,
        ProductType,
        QueryPlan,
        ResultGrain,
        TopKScope,
    )
    from finproof.evidence.builder import _bounded_source_rows
    from finproof.quality import PolicyExecutionResult, PolicyRow
    from finproof.quality.metric_policy import MetricPolicyResult
    from finproof.quality.state import StateEvaluation
    from finproof.storage import RawFieldValue, RawProductRow

    rows = tuple(
        PolicyRow(
            raw=RawProductRow(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                product_id=product_id,
                values=(
                    RawFieldValue(field_id="product_id", value=product_id, quality_status="valid"),
                ),
            ),
            state=StateEvaluation(
                product_id=product_id,
                eligible=eligible,
                state_ids=(),
                warnings=(),
            ),
        )
        for product_id, eligible in (("VALID", True), ("MATURED", False))
    )
    policy = PolicyExecutionResult(
        included_rows=(rows[0],),
        excluded_filter_count=0,
        excluded_state_count=1,
        excluded_metric_count=0,
        metric_policy=MetricPolicyResult(
            recorded_values=(), comparison_valid_values=(), excluded_count=0, warnings=()
        ),
        dual_lens_labels=(),
        selected_rows=(rows[0],),
        partitions=(),
        aggregates=(),
        ranks=(),
        warnings=(),
        source_rows=rows,
    )
    plan = QueryPlan(
        intent=Intent.SCREEN,
        product_types=(ProductType.DOMESTIC_BOND,),
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.INSTRUMENT,
        filters=(
            FilterClause(field="buyable_quantity", operator=FilterOperator.GT, value=Decimal("0")),
        ),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.GLOBAL,
        needs_clarification=False,
        clarification_reason="",
    )

    assert _bounded_source_rows(plan=plan, policy_result=policy) == ()


def test_nonmetric_date_screen_rank_emits_competition_ranks_tie_and_boundary_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.domain.evidence import EvidenceSummaryKind
    from finproof.domain.execution import ValidatedQueryPlan
    from finproof.domain.query_plan import (
        Intent,
        ProductType,
        QueryPlan,
        ResultGrain,
        SortDirection,
        SortSpec,
        TopKScope,
    )
    from finproof.evidence import EvidenceBuilder
    from finproof.quality import PolicyExecutionResult, PolicyRow
    from finproof.quality.metric_policy import MetricPolicyResult
    from finproof.quality.state import StateEvaluation
    from finproof.storage import RawFieldValue, RawProductRow
    from finproof.storage.repositories.evidence import (
        EvidenceLookup,
        EvidenceRepository,
        RecordEvidence,
    )

    values = {
        "A": date(2026, 7, 20),
        "B": date(2026, 7, 21),
        "C": date(2026, 7, 22),
        "D": date(2026, 7, 31),
        "E": date(2026, 7, 31),
        "F": date(2026, 7, 31),
        "G": date(2026, 7, 31),
    }

    def row(product_id: str) -> PolicyRow:
        return PolicyRow(
            raw=RawProductRow(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                product_id=product_id,
                values=(
                    RawFieldValue(field_id="product_id", value=product_id, quality_status="valid"),
                    RawFieldValue(
                        field_id="maturity_date",
                        value=values[product_id],
                        quality_status="valid",
                    ),
                ),
            ),
            state=StateEvaluation(product_id=product_id, eligible=True, state_ids=(), warnings=()),
        )

    included = tuple(row(product_id) for product_id in values)
    policy = PolicyExecutionResult(
        included_rows=included,
        excluded_filter_count=0,
        excluded_state_count=0,
        excluded_metric_count=0,
        metric_policy=MetricPolicyResult(
            recorded_values=(), comparison_valid_values=(), excluded_count=0, warnings=()
        ),
        dual_lens_labels=(),
        selected_rows=included[:5],
        partitions=(),
        aggregates=(),
        ranks=(),
        warnings=(),
        source_rows=included,
    )
    plan = ValidatedQueryPlan._issue(
        plan=QueryPlan(
            intent=Intent.SCREEN_RANK,
            product_types=(ProductType.DOMESTIC_BOND,),
            entities=(),
            as_of_date=date(2026, 7, 11),
            result_grain=ResultGrain.INSTRUMENT,
            filters=(),
            metrics=("maturity_date",),
            sort=(SortSpec(field="maturity_date", direction=SortDirection.ASC),),
            aggregation=None,
            top_k=5,
            top_k_scope=TopKScope.GLOBAL,
            needs_clarification=False,
            clarification_reason="",
        ),
        resolutions=(),
        context=(),
    )
    session, _ = _bond_evidence_session()
    repository = EvidenceRepository(session)
    templates = {
        item.field_id: item
        for item in repository.fetch_final_record_evidence(
            (
                EvidenceLookup(
                    product_type=ProductType.DOMESTIC_BOND,
                    product_ids=("KR0000000001",),
                    field_ids=("product_id", "product_name", "maturity_date"),
                ),
            )
        )[0].direct
    }

    def fetch(
        _repository: EvidenceRepository,
        requests: tuple[EvidenceLookup, ...],
    ) -> tuple[RecordEvidence, ...]:
        return tuple(
            RecordEvidence(
                product_type=request.product_type,
                product_id=product_id,
                direct=tuple(
                    templates[field_id].model_copy(
                        update={
                            "evidence_id": f"domestic_bond:{product_id}:{field_id}",
                            "product_id": product_id,
                            "value": templates[field_id].value.model_copy(
                                update={
                                    "raw_value": {
                                        "product_id": product_id,
                                        "product_name": f"Bond {product_id}",
                                        "maturity_date": values[product_id],
                                    }[field_id],
                                    "normalized_value": {
                                        "product_id": product_id,
                                        "product_name": f"Bond {product_id}",
                                        "maturity_date": values[product_id],
                                    }[field_id],
                                }
                            ),
                        }
                    )
                    for field_id in request.field_ids
                ),
                derived=(),
            )
            for request in requests
            for product_id in request.product_ids
        )

    monkeypatch.setattr(EvidenceRepository, "fetch_final_record_evidence", fetch)
    evidence = EvidenceBuilder().build(plan=plan, policy_result=policy, repository=repository)

    ranks = tuple(
        summary for summary in evidence.summaries if summary.kind is EvidenceSummaryKind.RANK
    )
    ties = tuple(
        summary for summary in evidence.summaries if summary.kind is EvidenceSummaryKind.TIE
    )
    assert tuple((summary.product_id, summary.rank, summary.tie_count) for summary in ranks) == (
        ("A", 1, 1),
        ("B", 2, 1),
        ("C", 3, 1),
        ("D", 4, 4),
        ("E", 4, 4),
    )
    assert len(ties) == 1
    assert ties[0].rank == 4
    assert ties[0].tie_count == 4
    assert any("동률로 top-k 경계" in item for item in evidence.material_policy_limitations)
    session._close()


def test_purchaseability_evidence_is_identical_for_different_raw_quantities() -> None:
    from tests.helpers.query_runtime import verified_artifacts

    from finproof.core.settings import ExecutionMode
    from finproof.core.versions import VersionBundle
    from finproof.domain.evidence import EvidenceBundle
    from finproof.domain.execution import ValidatedQueryPlan
    from finproof.domain.query_plan import (
        FilterClause,
        FilterOperator,
        Intent,
        ProductType,
        QueryPlan,
        ResultGrain,
        TopKScope,
    )
    from finproof.evidence import EvidenceBuilder
    from finproof.quality import PolicyExecutionResult, PolicyRow
    from finproof.quality.metric_policy import MetricPolicyResult
    from finproof.quality.state import StateEvaluation
    from finproof.registry.loader import RegistryBundle
    from finproof.registry.resources import REGISTRY_RESOURCE_NAMES, registry_resource_bytes
    from finproof.runtime.session import RuntimeArtifactSession
    from finproof.storage import RawFieldValue, RawProductRow
    from finproof.storage.repositories.evidence import EvidenceRepository

    plan = ValidatedQueryPlan._issue(
        plan=QueryPlan(
            intent=Intent.SCREEN,
            product_types=(ProductType.DOMESTIC_BOND,),
            entities=(),
            as_of_date=date(2026, 8, 22),
            result_grain=ResultGrain.INSTRUMENT,
            filters=(
                FilterClause(
                    field="buyable_quantity",
                    operator=FilterOperator.EQ,
                    value=Decimal("0"),
                ),
            ),
            metrics=(),
            sort=(),
            aggregation=None,
            top_k=5,
            top_k_scope=TopKScope.GLOBAL,
            needs_clarification=False,
            clarification_reason="",
        ),
        resolutions=(),
        context=(),
    )
    payloads = {name: registry_resource_bytes(name) for name in REGISTRY_RESOURCE_NAMES}
    registries = RegistryBundle._from_resource_bytes(payloads)
    verified = verified_artifacts()
    versions = VersionBundle.from_runtime(
        verified=verified,
        registries=registries,
        execution_mode=ExecutionMode.EVALUATION,
    )

    class Connection:
        def close(self) -> None: ...

    session = RuntimeArtifactSession._issue(
        connection=Connection(),
        verified=verified,
        registries=registries,
        versions=versions,
    )
    repository = EvidenceRepository(session)

    def evidence_for(quantity: int) -> EvidenceBundle:
        row = PolicyRow(
            raw=RawProductRow(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                product_id="KR0000000001",
                values=(
                    RawFieldValue(
                        field_id="product_id",
                        value="KR0000000001",
                        quality_status="valid",
                    ),
                    RawFieldValue(
                        field_id="buyable_quantity",
                        value=quantity,
                        quality_status="valid",
                    ),
                ),
            ),
            state=StateEvaluation(
                product_id="KR0000000001",
                eligible=False,
                state_ids=(),
                warnings=(),
            ),
        )
        policy = PolicyExecutionResult(
            included_rows=(),
            excluded_filter_count=0,
            excluded_state_count=1,
            excluded_metric_count=0,
            metric_policy=MetricPolicyResult(
                recorded_values=(), comparison_valid_values=(), excluded_count=0, warnings=()
            ),
            dual_lens_labels=(),
            selected_rows=(),
            partitions=(),
            aggregates=(),
            ranks=(),
            warnings=(),
            source_rows=(row,),
        )
        return EvidenceBuilder().build(
            plan=plan,
            policy_result=policy,
            repository=repository,
        )

    zero = evidence_for(0)
    large = evidence_for(999_999)
    assert zero.model_dump(mode="json") == large.model_dump(mode="json")
    count = next(summary for summary in zero.summaries if summary.summary_id == "summary:count")
    assert count.value is None
    session._close()


def test_buy_yield_evidence_binds_material_multi_lot_range_and_selection_rule() -> None:
    from tests.unit.query.test_semantic_validator import _plan

    from finproof.domain.execution import ValidatedQueryPlan
    from finproof.domain.query_plan import ProductType, ResultGrain
    from finproof.evidence import EvidenceBuilder
    from finproof.quality import PolicyExecutionResult, PolicyRow
    from finproof.quality.metric_policy import MetricPolicyResult
    from finproof.quality.state import StateEvaluation
    from finproof.storage import RawFieldValue, RawProductRow
    from finproof.storage.repositories.evidence import EvidenceRepository

    session, _ = _bond_evidence_session(lot_yields=("3.1", "bad", "4.2"))
    row = PolicyRow(
        raw=RawProductRow(
            product_type=ProductType.DOMESTIC_BOND,
            native_result_grain=ResultGrain.INSTRUMENT,
            product_id="KR0000000001",
            values=(
                RawFieldValue(
                    field_id="product_id",
                    value="KR0000000001",
                    quality_status="valid",
                ),
                RawFieldValue(
                    field_id="buy_yield",
                    value=Decimal("4.2"),
                    quality_status="valid",
                ),
            ),
        ),
        state=StateEvaluation(
            product_id="KR0000000001",
            eligible=True,
            state_ids=(),
            warnings=(),
        ),
    )
    policy = PolicyExecutionResult(
        included_rows=(row,),
        excluded_filter_count=0,
        excluded_state_count=0,
        excluded_metric_count=0,
        metric_policy=MetricPolicyResult(
            recorded_values=(), comparison_valid_values=(), excluded_count=0, warnings=()
        ),
        dual_lens_labels=(),
        selected_rows=(row,),
        partitions=(),
        aggregates=(),
        ranks=(),
        warnings=(),
        source_rows=(row,),
    )
    evidence = EvidenceBuilder().build(
        plan=ValidatedQueryPlan._issue(
            plan=_plan().model_copy(update={"as_of_date": date(2026, 8, 22)}),
            resolutions=(),
            context=(),
        ),
        policy_result=policy,
        repository=EvidenceRepository(session),
    )

    range_evidence = next(item for item in evidence.derived if item.field_id == "buy_yield_range")
    assert range_evidence.value.value == (Decimal("3.1"), Decimal("4.2"))
    assert tuple(source.source_row_number for source in range_evidence.value.inputs) == (77, 78, 79)
    assert any(
        "최댓값" in limitation and "3.1~4.2" in limitation
        for limitation in evidence.material_policy_limitations
    )
    session._close()

    for lot_yields in (("4.2",), ("4.2", "4.2")):
        equal_session, _ = _bond_evidence_session(lot_yields=lot_yields)
        equal_evidence = EvidenceBuilder().build(
            plan=ValidatedQueryPlan._issue(
                plan=_plan().model_copy(update={"as_of_date": date(2026, 8, 22)}),
                resolutions=(),
                context=(),
            ),
            policy_result=policy,
            repository=EvidenceRepository(equal_session),
        )
        assert not any(item.field_id == "buy_yield_range" for item in equal_evidence.derived)
        assert all(
            "유효 로트 중 최댓값" not in limitation
            for limitation in equal_evidence.material_policy_limitations
        )
        equal_session._close()


def _bond_evidence_session(
    *,
    buy_yield: str = "2.25",
    buyable_quantity: str = "10",
    lot_yields: tuple[str, ...] | None = None,
) -> tuple[RuntimeArtifactSession, BondInstrument]:
    lots = tuple(
        normalize_bond_lot(
            source_row(
                "PRBD01N001",
                {
                    "pd_no": "KR0000000001",
                    "info_seq": str(index),
                    "buy_yield": lot_yield,
                    "buyable_quantity": buyable_quantity,
                    "mat_dt": "20270822",
                    "eval_price": "99",
                },
                excel_row=76 + index,
            ),
            RATING_REGISTRY,
        ).record
        for index, lot_yield in enumerate(lot_yields or (buy_yield,), start=1)
    )
    assert all(lot is not None for lot in lots)
    record = project_bond_instrument(lots, as_of=date(2026, 8, 22)).record  # type: ignore[arg-type]
    assert isinstance(record, BondInstrument)
    bond = record

    class Connection:
        def execute(self, _sql: str, _parameters: object) -> Self:
            return self

        def fetchall(self) -> tuple[tuple[object, ...], ...]:
            return (("KR0000000001", canonical_record_json(bond)),)

        def close(self) -> None: ...

    return _candidate_registry_session(Connection()), bond
