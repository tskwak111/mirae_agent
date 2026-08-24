"""Focused evidence construction contracts."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Self

import pytest
from tests.helpers.source_rows import source_row
from tests.integration.query.test_executor import _session

from finproof.data.artifacts.serialization import canonical_record_json
from finproof.data.normalization.bonds import normalize_bond
from finproof.domain.bonds import BondInstrument
from finproof.registry.rating import RatingRegistry
from finproof.runtime.session import RuntimeArtifactSession


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
    assert evidence.value.source.source_column_name == "BUY_YIELD"
    assert evidence.value.source.source_column_letter
    assert evidence.value.source.source_checksum
    assert evidence.value.source.source_snapshot_date == date(2026, 7, 11)
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
    assert evidence.value.as_of_date == date(2026, 7, 11)
    assert tuple(item.source_column_name for item in evidence.value.inputs) == ("MAT_DT",)
    session._close()


def test_public_fund_evidence_restores_canonical_nested_lineage() -> None:
    from tests.unit.data.artifacts.test_serialization import _fund_record

    from finproof.domain.query_plan import ProductType
    from finproof.storage.repositories.evidence import EvidenceLookup, EvidenceRepository

    fund = _fund_record()
    product_id = fund.fund_item_id.representative.normalized_value
    assert type(product_id) is str

    class Connection:
        def execute(self, _sql: str, _parameters: object) -> Self:
            return self

        def fetchall(self) -> tuple[tuple[object, ...], ...]:
            return ((product_id, canonical_record_json(fund)),)

        def close(self) -> None: ...

    session = _session(Connection())  # type: ignore[arg-type]

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
    assert record.direct[0].value.source == fund.fund_item_id.representative.source
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
    assert any("동률" in limitation for limitation in evidence.material_policy_limitations)
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
    assert derived["as_of_date"] == "2026-07-11"
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
                    field_ids=("buy_yield", "buyable_quantity"),
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
        "buy_yield": ("2.25", "2.25", "BUY_YIELD"),
        "buyable_quantity": ("10", "10", "BUYABLE_QUANTITY"),
    }
    assert {item["evidence_id"] for item in direct_records} == {item.evidence_id for item in direct}
    assert all(
        payload["sources"][item["source"]]["source_table"] == "PRBD01N001"
        and payload["sources"][item["source"]]["source_file"]
        and payload["sources"][item["source"]]["source_sheet"]
        and payload["sources"][item["source"]]["source_checksum"]
        and payload["sources"][item["source"]]["source_snapshot_date"] == "2026-07-11"
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


def _bond_evidence_session() -> tuple[RuntimeArtifactSession, BondInstrument]:
    record = normalize_bond(
        source_row(
            "PRBD01N001",
            {
                "PD_NO": "KR0000000001",
                "BUY_YIELD": "2.25",
                "BUYABLE_QUANTITY": "10",
                "MAT_DT": "20270711",
            },
            excel_row=77,
        ),
        date(2026, 7, 11),
        RatingRegistry.from_yaml(Path(__file__).resolve().parents[3] / "config/rating_scale.yaml"),
    ).record
    assert isinstance(record, BondInstrument)
    bond = record

    class Connection:
        def execute(self, _sql: str, _parameters: object) -> Self:
            return self

        def fetchall(self) -> tuple[tuple[object, ...], ...]:
            return (("KR0000000001", canonical_record_json(bond)),)

        def close(self) -> None: ...

    return _session(Connection()), bond  # type: ignore[arg-type]
