import os
from datetime import date
from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr

from finproof.answer.hcx_verbalizer import HcxVerbalizer, ProviderWordingError
from finproof.core.settings import ExecutionMode
from finproof.domain.answers import (
    AnswerClaim,
    ClaimKind,
    ClaimSignature,
    EntitySignature,
    FactPack,
    PreparedAnswer,
    SurfacePart,
    ValueSignature,
)
from finproof.domain.execution import ExecutionTrace, TraceValidation
from finproof.domain.query_plan import (
    Intent,
    ProductType,
    ResultGrain,
    TopKScope,
)
from finproof.evidence import ClaimVerificationError, ClaimVerifier
from finproof.planner.hcx_client import HcxClient
from finproof.planner.service import (
    LocalPlanValidator,
    PlannerOutputError,
    PlannerSemanticError,
    PlannerService,
    PlanningRequest,
)
from finproof.planner.structured_planner import StructuredOutputPlanner
from finproof.query import FieldRegistry, SemanticValidator
from finproof.registry.loader import RegistryBundle
from finproof.service.limits import RequestDeadline

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("FINPROOF_RUN_LIVE_HCX") != "1"
        or not os.environ.get("FINPROOF_HCX_API_KEY"),
        reason="live HCX acceptance requires explicit opt-in and credentials",
    ),
]


@pytest.mark.asyncio
async def test_live_hcx_planner_and_verbalizer_verified_surface() -> None:
    api_key = SecretStr(os.environ["FINPROOF_HCX_API_KEY"])
    model_name = os.environ.get("FINPROOF_HCX_MODEL_NAME", "HCX-007")
    deadline = RequestDeadline.start()
    registries = RegistryBundle.from_package()
    validator = LocalPlanValidator(SemanticValidator(FieldRegistry.from_bundle(registries)))

    async with httpx.AsyncClient() as http_client:
        client = HcxClient(http_client=http_client, api_key=api_key)
        planner = PlannerService(
            strict_json_planner=StructuredOutputPlanner(
                generator=client,
                validator=validator,
                registries=registries,
                model_name=model_name,
            )
        )
        planned = await planner.plan(
            PlanningRequest(
                question="국내 ETF 중 추적오차가 낮은 5개를 보여 주세요.",
                request_id="live-planner",
                as_of_date=date(2026, 8, 24),
                execution_mode=ExecutionMode.EVALUATION,
            ),
            deadline=deadline,
        )
        assert planned.plan.product_types == (ProductType.DOMESTIC_ETF,)
        assert planned.plan.top_k == 5

        prepared = _prepared_numeric_rank_answer()
        verbalizer = HcxVerbalizer(generator=client, model_name=model_name)
        verifier = ClaimVerifier()
        wording_repaired = False
        try:
            wording = await verbalizer.verbalize(
                prepared.fact_pack,
                request_id="live-verbalizer",
                deadline=deadline,
            )
        except ProviderWordingError as error:
            wording_repaired = True
            wording = await verbalizer.repair(
                prepared.fact_pack,
                invalid_content=error.invalid_content,
                request_id="live-verbalizer",
                deadline=deadline,
            )
        try:
            verified = verifier.verify_wording(wording, prepared, deadline)
        except ClaimVerificationError:
            if wording_repaired:
                raise
            wording = await verbalizer.repair(
                prepared.fact_pack,
                invalid_content=wording.model_dump_json(),
                request_id="live-verbalizer",
                deadline=deadline,
            )
            verified = verifier.verify_wording(wording, prepared, deadline)

    assert verified.text == prepared.fact_pack.surface_parts[0].text


@pytest.mark.asyncio
async def test_live_hcx_planner_validation_stage_diagnostic() -> None:
    api_key = SecretStr(os.environ["FINPROOF_HCX_API_KEY"])
    deadline = RequestDeadline.start()
    registries = RegistryBundle.from_package()
    async with httpx.AsyncClient() as http_client:
        planner = StructuredOutputPlanner(
            generator=HcxClient(http_client=http_client, api_key=api_key),
            validator=LocalPlanValidator(SemanticValidator(FieldRegistry.from_bundle(registries))),
            registries=registries,
            model_name=os.environ.get("FINPROOF_HCX_MODEL_NAME", "HCX-007"),
        )
        try:
            planned = await planner.plan(
                PlanningRequest(
                    question="국내 ETF 중 추적오차가 낮은 5개를 보여 주세요.",
                    request_id="live-planner-diagnostic",
                    as_of_date=date(2026, 8, 24),
                    execution_mode=ExecutionMode.EVALUATION,
                ),
                deadline=deadline,
            )
        except PlannerOutputError as error:
            pytest.fail(
                "planner_validation_stage="
                f"{error.validation_stage};canonical_substage={error.canonical_substage};"
                f"canonical_path={error.canonical_path};"
                f"canonical_keyword={error.canonical_keyword}"
            )

    assert planned.plan.product_types == (ProductType.DOMESTIC_ETF,)
    assert planned.plan.top_k == 5


@pytest.mark.asyncio
async def test_live_hcx_planner_semantic_reason_diagnostic() -> None:
    api_key = SecretStr(os.environ["FINPROOF_HCX_API_KEY"])
    deadline = RequestDeadline.start()
    registries = RegistryBundle.from_package()
    request = PlanningRequest(
        question="국내 ETF 중 추적오차가 낮은 5개를 보여 주세요.",
        request_id="live-planner-semantic-diagnostic",
        as_of_date=date(2026, 8, 24),
        execution_mode=ExecutionMode.EVALUATION,
    )
    async with httpx.AsyncClient() as http_client:
        planner = StructuredOutputPlanner(
            generator=HcxClient(http_client=http_client, api_key=api_key),
            validator=LocalPlanValidator(SemanticValidator(FieldRegistry.from_bundle(registries))),
            registries=registries,
            model_name=os.environ.get("FINPROOF_HCX_MODEL_NAME", "HCX-007"),
        )
        try:
            planned = await planner.plan(request, deadline=deadline)
        except PlannerOutputError as initial_error:
            try:
                planned = await planner.repair(
                    request,
                    initial_error.content,
                    deadline=deadline,
                )
            except PlannerSemanticError as error:
                pytest.fail(
                    f"planner_semantic_reason={error.reason_code};"
                    f"detail={error.detail};registry_field_id={error.registry_field_id}",
                    pytrace=False,
                )
            except PlannerOutputError as error:
                pytest.fail(
                    "planner_repair_validation_stage="
                    f"{error.validation_stage};canonical_path={error.canonical_path};"
                    f"canonical_keyword={error.canonical_keyword};"
                    f"filter_shape_category={error.filter_shape_category}",
                    pytrace=False,
                )
        except PlannerSemanticError as error:
            pytest.fail(
                f"planner_semantic_reason={error.reason_code};"
                f"detail={error.detail};registry_field_id={error.registry_field_id}",
                pytrace=False,
            )

    assert planned.plan.product_types == (ProductType.DOMESTIC_ETF,)
    assert planned.plan.top_k == 5


def _prepared_numeric_rank_answer() -> PreparedAnswer:
    claim = AnswerClaim(
        claim_id="claim:rank:1",
        kind=ClaimKind.NUMERIC,
        text="공동순위 ETF의 추적오차는 0.10%이며 1위입니다.",
        product_type=ProductType.DOMESTIC_ETF,
        product_id="KR7000000000",
        field_id="tracking_error",
        value=Decimal("0.10"),
        evidence_ids=("evidence:tracking-error",),
    )
    surface = claim.text
    fact_pack = FactPack(
        surface_parts=(
            SurfacePart(
                part_id="surface:answer",
                text=surface,
                claim_ids=(claim.claim_id,),
                limitation_codes=(),
            ),
        ),
        claim_signatures=(
            ClaimSignature(
                claim_id=claim.claim_id,
                kind=claim.kind,
                surface_text=claim.text,
                entities=(
                    EntitySignature(
                        product_type=ProductType.DOMESTIC_ETF,
                        product_id="KR7000000000",
                        display_name="공동순위 ETF",
                    ),
                ),
                values=(
                    ValueSignature(
                        field_id="tracking_error",
                        canonical_normalized_json='"0.10"',
                        display_text="0.10",
                        unit="percent",
                    ),
                ),
                rank=1,
                tie_count=1,
                partition="tracking_error:percent",
                comparison=None,
                evidence_ids=claim.evidence_ids,
                limitation_codes=(),
            ),
        ),
        required_claim_ids=(claim.claim_id,),
        required_limitation_codes=(),
        evidence_context_sha256="0" * 64,
    )
    return PreparedAnswer(
        fact_pack=fact_pack,
        claims=(claim,),
        retrieved_context=fact_pack.model_dump_json(),
        trace=ExecutionTrace(
            correlation_id="live-verbalizer",
            intent=Intent.SCREEN_RANK,
            product_types=(ProductType.DOMESTIC_ETF,),
            as_of_date=date(2026, 8, 24),
            result_grain=ResultGrain.LISTED_PRODUCT,
            top_k_scope=TopKScope.GLOBAL,
            segments=(),
            candidate_counts={"raw": 1, "eligible": 1, "returned": 1},
            tools=("claim_verifier",),
            policy_ids=(),
            validation=TraceValidation.PASSED,
            versions={},
            latency_ms={},
        ),
    )
