"""Synthetic end-to-end constituent-query contracts."""

import json
from collections.abc import Mapping
from datetime import date
from pathlib import Path

from tests.helpers.artifacts import write_database_artifact_tree
from tests.helpers.source_rows import source_row
from tests.unit.evidence.test_builder import _candidate_registry_session

from finproof.data.artifacts.serialization import serialize_table_row
from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
from finproof.data.holdings import HoldingCoverageRecord, HoldingRecord
from finproof.data.normalization.domestic_listed import normalize_domestic_listed
from finproof.data.normalization.public_funds import normalize_public_fund_item
from finproof.domain.answers import AnswerRequest, AnswerResult
from finproof.domain.query_plan import (
    FilterClause,
    FilterOperator,
    Intent,
    ProductType,
    QueryPlan,
    ResultGrain,
    SortDirection,
    SortSpec,
    TopKScope,
)
from finproof.entity import HoldingResolver
from finproof.query import (
    ExecutionBundleBuilder,
    FieldRegistry,
    QueryAst,
    ResolutionBundle,
    SemanticValidator,
    SqlCompiler,
    ValidationContext,
)
from finproof.registry.loader import RegistryBundle
from finproof.runtime.session import RuntimeArtifactSession
from finproof.service import AnswerService

AS_OF = date(2026, 8, 24)
CONSTITUENT_ID = "KR7005930003"
CONSTITUENT_ID_TYPE = "isin"


def _native_records() -> tuple[object, object, object]:
    domestic = normalize_domestic_listed(
        source_row(
            "PREF01N001",
            {
                "pd_itm_no": "KR7000000001",
                "pd_grp_no": "ETF",
                "pd_nm": "삼성 보유 테스트 ETF",
                "du_er_1y": "12.50",
                "du_upt_dt": "2026-08-22 09:00:00",
            },
        ),
        AS_OF,
    ).record
    etn = normalize_domestic_listed(
        source_row(
            "PREF01N001",
            {
                "pd_itm_no": "KR7000000002",
                "pd_grp_no": "ETN",
                "pd_nm": "자료 미제공 테스트 ETN",
                "du_er_1y": "7.00",
                "du_upt_dt": "2026-08-22 09:00:00",
            },
            excel_row=3,
        ),
        AS_OF,
    ).record
    fund = normalize_public_fund_item(
        source_row(
            "PRFD01N001",
            {
                "itm_no": "KR5114601001",
                "ksd_itm_no": "KR5114601001",
                "itm_nm": "삼성 보유 테스트 공모펀드",
                "fd_yr1_ern_r": "9.25",
            },
        )
    ).record
    assert domestic is not None
    assert etn is not None
    assert fund is not None
    return domestic, etn, fund


def _reowner(
    value: object,
    *,
    product_type: ProductType,
    product_id: str,
    owner_identifier_type: str,
    row_ordinal: int,
) -> HoldingRecord:
    payload = value.model_dump(mode="python")  # type: ignore[attr-defined]
    payload.update(
        {
            "owner_product_type": product_type,
            "owner_product_id": product_id,
            "owner_source_identifier": product_id,
            "owner_identifier_type": owner_identifier_type,
            "source_row_ordinal": row_ordinal,
        }
    )
    locator = dict(payload["source_locator"])
    locator["source_row_number"] = row_ordinal
    payload["source_locator"] = locator
    for field in ("quantity", "market_value", "weight"):
        wrapped = dict(payload[field])
        source = dict(wrapped["source"])
        source["source_row_number"] = row_ordinal
        wrapped["source"] = source
        payload[field] = wrapped
    return HoldingRecord.model_validate(payload, strict=True)


def _reowner_coverage(
    value: object,
    *,
    product_type: ProductType,
    product_id: str,
    owner_identifier_type: str,
) -> HoldingCoverageRecord:
    payload = value.model_dump(mode="python")  # type: ignore[attr-defined]
    payload.update(
        {
            "owner_product_type": product_type,
            "owner_product_id": product_id,
            "owner_source_identifier": product_id,
            "owner_identifier_type": owner_identifier_type,
        }
    )
    return HoldingCoverageRecord.model_validate(payload, strict=True)


def _synthetic_session(tmp_path: Path) -> RuntimeArtifactSession:
    import duckdb
    from tests.unit.data.test_holdings import _coverage, _holding

    domestic, etn, fund = _native_records()
    domestic_id = domestic.product_id.normalized_value  # type: ignore[attr-defined]
    etn_id = etn.product_id.normalized_value  # type: ignore[attr-defined]
    fund_id = fund.fund_item_id.normalized_value  # type: ignore[attr-defined]
    assert isinstance(domestic_id, str)
    assert isinstance(etn_id, str)
    assert isinstance(fund_id, str)
    base_holding = _holding(CONSTITUENT_ID, owner_product_id=domestic_id)
    domestic_holding = _reowner(
        base_holding,
        product_type=ProductType.DOMESTIC_ETF,
        product_id=domestic_id,
        owner_identifier_type="krx_isu_cd",
        row_ordinal=1,
    )
    fund_holding = _reowner(
        base_holding,
        product_type=ProductType.PUBLIC_FUND,
        product_id=fund_id,
        owner_identifier_type="published_fund_identifier",
        row_ordinal=2,
    )
    base_coverage = _coverage(owner_product_id=domestic_id)
    domestic_coverage = _reowner_coverage(
        base_coverage,
        product_type=ProductType.DOMESTIC_ETF,
        product_id=domestic_id,
        owner_identifier_type="krx_isu_cd",
    )
    fund_coverage = _reowner_coverage(
        base_coverage,
        product_type=ProductType.PUBLIC_FUND,
        product_id=fund_id,
        owner_identifier_type="published_fund_identifier",
    )
    unavailable = (
        HoldingCoverageRecord.unavailable(
            owner_product_type=ProductType.DOMESTIC_ETN,
            owner_product_id=etn_id,
        ),
        HoldingCoverageRecord.unavailable(
            owner_product_type=ProductType.OVERSEAS_ETF,
            owner_product_id="BND.O",
        ),
    )
    root = tmp_path / "cross-product-holding"
    write_database_artifact_tree(
        root,
        {
            "silver_domestic_listed_product": tuple(
                dict(
                    serialize_table_row(
                        TABLE_SPEC_BY_NAME["silver_domestic_listed_product"], record
                    )
                )
                for record in (domestic, etn)
            ),
            "silver_fund_item": (
                dict(serialize_table_row(TABLE_SPEC_BY_NAME["silver_fund_item"], fund)),
            ),
            "silver_product_holding": tuple(
                dict(serialize_table_row(TABLE_SPEC_BY_NAME["silver_product_holding"], record))
                for record in (domestic_holding, fund_holding)
            ),
            "silver_product_holding_coverage": tuple(
                dict(
                    serialize_table_row(
                        TABLE_SPEC_BY_NAME["silver_product_holding_coverage"], record
                    )
                )
                for record in (domestic_coverage, fund_coverage, *unavailable)
            ),
        },
    )
    return _candidate_registry_session(
        duckdb.connect(str(root / "finproof.duckdb"), read_only=True)
    )


def _plan(
    *,
    product_types: tuple[ProductType, ...],
    ranking: bool,
) -> QueryPlan:
    return QueryPlan(
        intent=Intent.SCREEN_RANK if ranking else Intent.SCREEN,
        product_types=product_types,
        entities=(),
        as_of_date=AS_OF,
        result_grain=ResultGrain.PRODUCT,
        filters=(
            FilterClause(
                field="holding_constituent",
                operator=FilterOperator.EQ,
                value="삼성전자",
            ),
        ),
        metrics=("return_1y",) if ranking else ("product_name",),
        sort=(SortSpec(field="return_1y", direction=SortDirection.DESC),) if ranking else (),
        aggregation=None,
        top_k=10,
        top_k_scope=TopKScope.GLOBAL if ranking else TopKScope.PER_PRODUCT_TYPE,
        needs_clarification=False,
        clarification_reason="",
    )


def test_constituent_request_keeps_native_segments_and_unavailable_etn_fail_closed(
    tmp_path: Path,
) -> None:
    session = _synthetic_session(tmp_path)
    plan = _plan(
        product_types=(
            ProductType.DOMESTIC_ETF,
            ProductType.DOMESTIC_ETN,
            ProductType.PUBLIC_FUND,
        ),
        ranking=False,
    )
    try:
        fields = FieldRegistry.from_bundle(session.registries)
        context = ValidationContext(
            as_of_date=AS_OF,
            execution_mode=session.versions.execution_mode,
        )
        resolution = HoldingResolver.from_session(session).resolve("삼성전자")
        validated = SemanticValidator(fields).validate(
            plan,
            resolutions=ResolutionBundle(results=(), holding_constituent=resolution),
            context=context,
        )
        compiled = tuple(
            SqlCompiler().compile(QueryAst.from_segment(segment, fields=fields))
            for segment in ExecutionBundleBuilder(fields).build(validated, context=context).segments
        )
        assert all(query.sql.count("EXISTS") == 1 for query in compiled)
        assert all("UNION" not in query.sql for query in compiled)
        assert tuple(query.parameters[-3:] for query in compiled) == tuple(
            (product_type.value, CONSTITUENT_ID, CONSTITUENT_ID_TYPE)
            for product_type in plan.product_types
        )
        result = AnswerService(session).answer_plan(
            AnswerRequest(question_id="Q-HOLDING", question="삼성전자 보유 상품 추천"),
            plan,
        )
    finally:
        session._close()

    payload = json.loads(result.retrieved_context)
    assert payload["format"] == "evidence_context.v3"
    assert {
        (item["owner_product_type"], item["owner_product_id"])
        for item in payload["holding_records"]
    } == {("domestic_etf", "KR7000000001"), ("public_fund", "KR5114601001")}
    assert tuple(segment.product_type for segment in result.trace.segments) == (
        ProductType.DOMESTIC_ETF,
        ProductType.DOMESTIC_ETN,
        ProductType.PUBLIC_FUND,
    )
    assert result.trace.segments[1].returned == 0
    assert "domestic_etn 구성종목 자료는 제공되지 않아" in result.answer.text
    assert "보유하지 않았다는 결론" in result.answer.text


def test_mixed_return_1y_ranks_domestic_and_fund_and_prunes_overseas(
    tmp_path: Path,
) -> None:
    session = _synthetic_session(tmp_path)
    try:
        result: AnswerResult = AnswerService(session).answer_plan(
            AnswerRequest(
                question_id="Q-HOLDING-RANK",
                question="삼성전자를 보유한 ETF와 공모펀드의 1년 수익률 TOP10",
            ),
            _plan(
                product_types=(
                    ProductType.DOMESTIC_ETF,
                    ProductType.OVERSEAS_ETF,
                    ProductType.PUBLIC_FUND,
                ),
                ranking=True,
            ),
        )
    finally:
        session._close()

    payload = json.loads(result.retrieved_context)
    ranks = [item for item in payload["summaries"] if item["kind"] == "rank"]
    assert [(item["product_types"], item["rank"]) for item in ranks] == [
        (["domestic_etf"], 1),
        (["public_fund"], 2),
    ]
    assert tuple(segment.product_type for segment in result.trace.segments) == (
        ProductType.DOMESTIC_ETF,
        ProductType.PUBLIC_FUND,
    )
    assert "해외 ETF/ETN의 1년 수익률은 제공 데이터에 없어" in result.answer.text
    wording = RegistryBundle.from_package().answers.document["wording"]
    assert isinstance(wording, Mapping)
    assert result.answer.text.startswith(wording["snapshot_assumption"])
    assert "보유하지 않았다는 결론" in result.answer.text
