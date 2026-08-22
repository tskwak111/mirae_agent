"""Focused deterministic answer-service composition contracts."""

from datetime import date

import pytest
from tests.integration.query.test_executor import _session


@pytest.mark.parametrize(
    ("intent", "needs_clarification"), [("clarify", True), ("unsupported", False)]
)
def test_clarify_and_unsupported_answers_execute_no_repository_query(
    intent: str,
    needs_clarification: bool,
) -> None:
    from finproof.domain.answers import AnswerRequest
    from finproof.domain.query_plan import Intent, QueryPlan, ResultGrain, TopKScope
    from finproof.service import AnswerService

    class Connection:
        calls = 0

        def execute(self, _sql: str, _parameters: object = ()) -> None:
            self.calls += 1
            raise AssertionError("terminal plans must not execute a repository query")

        def close(self) -> None: ...

    connection = Connection()
    session = _session(connection)  # type: ignore[arg-type]
    plan = QueryPlan(
        intent=Intent(intent),
        product_types=(),
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.INSTRUMENT,
        filters=(),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.GLOBAL,
        needs_clarification=needs_clarification,
        clarification_reason="상품 조건을 확인해 주세요.",
    )

    result = AnswerService(session).answer_plan(
        AnswerRequest(question_id=f"q-{intent}", question="질문"), plan
    )

    assert connection.calls == 0
    assert result.answer.text
    session._close()


def test_answer_service_composes_exact_runtime_resolution_validation_execution_policy_evidence_render_verify_order() -> (  # noqa: E501
    None
):
    from finproof.domain.answers import (
        AnswerDraft,
        AnswerRequest,
        VerifiedAnswer,
    )
    from finproof.domain.evidence import EvidenceBundle
    from finproof.domain.query_plan import (
        EntityMention,
        Intent,
        ProductType,
        QueryPlan,
        ResultGrain,
        TopKScope,
    )
    from finproof.entity import ResolutionCandidate, ResolutionMatchKind, ResolutionResult
    from finproof.service import AnswerService

    class Connection:
        def close(self) -> None: ...

    session = _session(Connection())  # type: ignore[arg-type]
    service = AnswerService(session)
    order: list[str] = []
    evidence = EvidenceBundle(direct=(), derived=(), summaries=(), material_policy_limitations=())
    draft = AnswerDraft(
        text="2026-07-11 제공 스냅샷 기준",
        claims=(),
    )
    verified = VerifiedAnswer(text=draft.text, claims=())
    candidate = ResolutionCandidate(
        product_id="KR0000000001",
        product_type=ProductType.DOMESTIC_BOND,
        name="테스트채권",
        match_kind=ResolutionMatchKind.EXACT_PRODUCT_ID,
        score=10_000,
    )

    class Resolver:
        def resolve(self, *_args: object, **_kwargs: object) -> ResolutionResult:
            order.append("resolution")
            return ResolutionResult(selected=candidate, candidates=(candidate,))

    class Validator:
        def validate(self, *_args: object, **_kwargs: object) -> object:
            order.append("validation")
            return object()

    class Segmenter:
        def build(self, *_args: object, **_kwargs: object) -> object:
            order.append("segmentation")
            return object()

    class Executor:
        def execute(self, *_args: object, **_kwargs: object) -> object:
            order.append("execution")
            return object()

    class Policy:
        def apply(self, *_args: object, **_kwargs: object) -> object:
            order.append("policy")
            return object()

    class Evidence:
        def build(self, *_args: object, **_kwargs: object) -> EvidenceBundle:
            order.append("evidence")
            return evidence

    class Renderer:
        def render(self, *_args: object, **_kwargs: object) -> AnswerDraft:
            order.append("render")
            return draft

    class Verifier:
        def verify(self, *_args: object, **_kwargs: object) -> VerifiedAnswer:
            order.append("verify")
            return verified

    service._resolver = Resolver()  # type: ignore[assignment]
    service._validator = Validator()  # type: ignore[assignment]
    service._segmenter = Segmenter()  # type: ignore[assignment]
    service._executor = Executor()  # type: ignore[assignment]
    service._policy = Policy()  # type: ignore[assignment]
    service._evidence_builder = Evidence()  # type: ignore[assignment]
    service._evidence_repository = object()  # type: ignore[assignment]
    service._renderer = Renderer()  # type: ignore[assignment]
    service._verifier = Verifier()  # type: ignore[assignment]
    plan = QueryPlan(
        intent=Intent.LOOKUP,
        product_types=(ProductType.DOMESTIC_BOND,),
        entities=(EntityMention(text="KR0000000001"),),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.INSTRUMENT,
        filters=(),
        metrics=(),
        sort=(),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.GLOBAL,
        needs_clarification=False,
        clarification_reason="",
    )

    result = service.answer_plan(
        AnswerRequest(question_id="q-order", question="KR0000000001 알려줘"), plan
    )

    assert result.answer == verified
    assert order == [
        "resolution",
        "validation",
        "segmentation",
        "execution",
        "policy",
        "evidence",
        "render",
        "verify",
    ]
    session._close()


def test_official_runtime_returns_one_verified_evidence_backed_answer_and_trace() -> None:
    import json
    from decimal import Decimal

    from tests.unit.evidence.test_builder import _bond_evidence_session

    from finproof.data.artifacts.serialization import canonical_record_json
    from finproof.domain.answers import AnswerRequest, ClaimKind
    from finproof.domain.execution import TraceValidation
    from finproof.domain.query_plan import (
        EntityMention,
        Intent,
        ProductType,
        QueryPlan,
        ResultGrain,
        TopKScope,
    )
    from finproof.service import AnswerService

    record_session, record = _bond_evidence_session()
    record_session._close()

    class Cursor:
        def __init__(self, rows: list[tuple[object, ...]]) -> None:
            self.rows = rows
            self.used = False

        def fetchall(self) -> list[tuple[object, ...]]:
            return self.rows

        def fetchmany(self, _size: int) -> list[tuple[object, ...]]:
            if self.used:
                return []
            self.used = True
            return self.rows

    class Connection:
        def execute(self, sql: str, _parameters: object = ()) -> Cursor:
            if sql.startswith("SELECT product_id, name, short_name "):
                return Cursor([("KR0000000001", "테스트채권", "테스트")])
            if sql.startswith("SELECT product_id, market_identifier, product_type"):
                return Cursor([])
            if sql.startswith("SELECT product_id, market_identifier, isin"):
                return Cursor([])
            if sql.startswith("SELECT fund_item_id"):
                return Cursor([])
            if '"record_json"' in sql:
                return Cursor([("KR0000000001", canonical_record_json(record))])
            if 'FROM "silver_bond_instrument"' in sql:
                return Cursor(
                    [
                        (
                            "KR0000000001",
                            "valid",
                            Decimal("2.25"),
                            "valid",
                            Decimal("10"),
                            "valid",
                            date(2027, 7, 11),
                            "valid",
                        )
                    ]
                )
            raise AssertionError(f"unexpected SQL shape: {sql[:80]}")

        def close(self) -> None: ...

    session = _session(Connection())  # type: ignore[arg-type]
    plan = QueryPlan(
        intent=Intent.LOOKUP,
        product_types=(ProductType.DOMESTIC_BOND,),
        entities=(EntityMention(text="KR0000000001"),),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.INSTRUMENT,
        filters=(),
        metrics=("buy_yield",),
        sort=(),
        aggregation=None,
        top_k=5,
        top_k_scope=TopKScope.GLOBAL,
        needs_clarification=False,
        clarification_reason="",
    )

    result = AnswerService(session).answer_plan(
        AnswerRequest(question_id="q-official-runtime", question="이 채권 수익률 알려줘"),
        plan,
    )

    context = json.loads(result.retrieved_context)
    numeric = tuple(claim for claim in result.answer.claims if claim.kind is ClaimKind.NUMERIC)
    assert "KR0000000001" in result.answer.text
    assert "2.25" in result.answer.text
    assert numeric
    assert numeric[0].evidence_ids
    assert context["direct"]
    assert result.trace.validation is TraceValidation.PASSED
    assert tuple(segment.partition_key for segment in result.trace.segments) == (
        "bond_buy_yield:None:yield_to_maturity_like_source_field:"
        "not_equal_to_historical_period_return",
    )
    assert result.trace.candidate_counts == {"raw": 1, "eligible": 1, "returned": 1}
    assert (
        result.trace.versions["artifact_manifest_hash"] == session.versions.artifact_manifest_hash
    )
    session._close()
