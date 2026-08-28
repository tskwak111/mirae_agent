"""Live, evaluation-only producer for the A-E ablation raw measurements."""

from __future__ import annotations

import asyncio
import json
import platform
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from time import monotonic

from pydantic import BaseModel, ConfigDict, Field

from finproof.cli.evaluate import (
    _observed,
    _observed_values,
    _typed_value,
)
from finproof.core.settings import Settings
from finproof.domain.answers import AnswerRequest
from finproof.domain.execution import ExecutionSegment
from finproof.domain.query_plan import AggregationFunction, Intent, ProductType, QueryPlan
from finproof.entity import EntityIndex, EntityResolver
from finproof.evaluation.ablation import AblationMeasurement, AblationVariant
from finproof.evaluation.latency import LatencySample, LatencySummary
from finproof.evaluation.loader import load_golden_cases, suite_checksum
from finproof.evaluation.models import (
    AggregateGroupValue,
    GoldenCase,
    ObservedAggregate,
    ObservedCase,
    ObservedSegment,
    ObservedValue,
    ProductIdentity,
    ValueType,
    native_result_grain,
)
from finproof.evaluation.runner import _code_commit
from finproof.evaluation.scoring import CaseScore, RatioScore, score_case
from finproof.planner.hcx_client import HcxClient, create_hcx_http_client
from finproof.planner.models import HcxMessage, HcxRequest, HcxResponse
from finproof.planner.prompts import PROMPT_VERSION
from finproof.planner.service import (
    HcxGenerator,
    LocalPlanValidator,
    PlannedQuery,
    PlannerProtocol,
    PlanningRequest,
)
from finproof.planner.structured_planner import StructuredOutputPlanner
from finproof.quality import PolicyEngine, PolicyExecutionResult
from finproof.query import (
    ExecutionBundleBuilder,
    FieldRegistry,
    QueryExecutor,
    SemanticValidator,
    ValidationContext,
)
from finproof.registry.loader import RegistryBundle
from finproof.runtime import RuntimeArtifactSession, open_runtime_artifact_session
from finproof.service import AnswerService
from finproof.storage.repositories.products import RawExecutionResult

_DIRECT_PROMPT_VERSION = "ablation-direct-answer.v1"


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class _DirectProduct(_FrozenModel):
    product_type: ProductType
    product_id: str = Field(min_length=1, max_length=300)


class _DirectAnswer(_FrozenModel):
    products: tuple[_DirectProduct, ...] = ()
    values: tuple[dict[str, object], ...] = ()
    answer: str
    limitation_present: bool = False


class _RecordingGenerator:
    def __init__(self, client: HcxClient) -> None:
        self._client = client
        self.responses: list[HcxResponse] = []

    async def generate(self, request: HcxRequest, request_id: str) -> HcxResponse:
        response = await self._client.generate(request, request_id)
        self.responses.append(response)
        return response

    def usage_since(self, index: int) -> tuple[int, int]:
        return (
            sum(response.usage.prompt_tokens for response in self.responses[index:]),
            sum(response.usage.completion_tokens for response in self.responses[index:]),
        )


@dataclass(frozen=True)
class _CaseRun:
    observation: ObservedCase
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    error: bool = False


@dataclass
class _Experiment:
    settings: Settings
    session: RuntimeArtifactSession
    planner: PlannerProtocol
    generator: _RecordingGenerator

    def __post_init__(self) -> None:
        fields = FieldRegistry.from_bundle(self.session.registries)
        self._segmenter = ExecutionBundleBuilder(fields)
        self._executor = QueryExecutor(self.session)
        self._policy = PolicyEngine()
        self._answer = AnswerService(self.session)
        self._validator = LocalPlanValidator(
            SemanticValidator(fields),
            entity_resolver=EntityResolver(EntityIndex.from_session(self.session)),
        )

    def _planning_request(self, case: GoldenCase) -> PlanningRequest:
        return PlanningRequest.start(
            question=case.question,
            request_id=case.case_id,
            as_of_date=case.expected_plan.as_of_date,
            execution_mode=self.session.versions.execution_mode,
            deadline_seconds=15.0,
        )

    async def run_case(
        self,
        case: GoldenCase,
        approved_plan: QueryPlan,
        repeat: int,
    ) -> dict[AblationVariant, _CaseRun]:
        runs = {AblationVariant.A_DIRECT_HCX: await self._direct(case, approved_plan, repeat)}
        usage_index = len(self.generator.responses)
        planning_started = monotonic()
        try:
            planned = await self.planner.plan(self._planning_request(case))
        except Exception:  # provider/domain errors become measured failures
            elapsed = _elapsed_ms(planning_started)
            prompt_tokens, completion_tokens = self.generator.usage_since(usage_index)
            failed = _failed_run(elapsed, prompt_tokens, completion_tokens)
            runs.update(dict.fromkeys(tuple(AblationVariant)[1:], failed))
            return runs
        prompt_tokens, completion_tokens = self.generator.usage_since(usage_index)
        planner_error = _planner_had_error(planned)
        planner_latency = _elapsed_ms(planning_started)
        runs[AblationVariant.B_CONSTRAINED_PLAN] = _CaseRun(
            observation=ObservedCase(plan=planned.plan, latency_ms=(planner_latency,)),
            latency_ms=planner_latency,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            error=planner_error,
        )

        stage_started = monotonic()
        try:
            bundle = self._segmenter.build(
                planned.validated_plan,
                context=_validation_context(planned),
            )
            raw = self._executor.execute(bundle)
            core_latency = planner_latency + _elapsed_ms(stage_started)
            runs[AblationVariant.C_DETERMINISTIC_EXECUTOR] = _CaseRun(
                observation=_raw_observation(
                    case, planned.plan, bundle.segments, raw, core_latency
                ),
                latency_ms=core_latency,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                error=planner_error,
            )
        except Exception:
            elapsed = planner_latency + _elapsed_ms(stage_started)
            runs[AblationVariant.C_DETERMINISTIC_EXECUTOR] = _failed_run(
                elapsed, prompt_tokens, completion_tokens
            )
            runs[AblationVariant.D_DOMAIN_POLICY] = _failed_run(
                elapsed, prompt_tokens, completion_tokens
            )
        else:
            policy_started = monotonic()
            try:
                policy = self._policy.apply(raw, bundle=bundle)
                policy_latency = core_latency + _elapsed_ms(policy_started)
                runs[AblationVariant.D_DOMAIN_POLICY] = _CaseRun(
                    observation=_policy_observation(
                        case,
                        planned.plan,
                        policy,
                        policy_latency,
                    ),
                    latency_ms=policy_latency,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    error=planner_error,
                )
            except Exception:
                elapsed = core_latency + _elapsed_ms(policy_started)
                runs[AblationVariant.D_DOMAIN_POLICY] = _failed_run(
                    elapsed, prompt_tokens, completion_tokens
                )

        end_started = monotonic()
        try:
            result = self._answer.answer_plan(
                AnswerRequest(question_id=case.case_id, question=case.question),
                planned.plan,
            )
            end_latency = planner_latency + _elapsed_ms(end_started)
            runs[AblationVariant.E_VERIFIED_ANSWER] = _CaseRun(
                observation=_observed(case, planned.plan, result, planner_latency),
                latency_ms=end_latency,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                error=planner_error,
            )
        except Exception:
            elapsed = planner_latency + _elapsed_ms(end_started)
            runs[AblationVariant.E_VERIFIED_ANSWER] = _failed_run(
                elapsed, prompt_tokens, completion_tokens
            )
        return runs

    async def _direct(
        self,
        case: GoldenCase,
        approved_plan: QueryPlan,
        repeat: int,
    ) -> _CaseRun:
        started = monotonic()
        usage_index = len(self.generator.responses)
        try:
            validated = self._validator.validate(approved_plan, self._planning_request(case))
            context = validated.context
            if type(context) is not ValidationContext:
                raise TypeError("validated ablation context differs")
            bundle = self._segmenter.build(validated, context=context)
            raw = self._executor.execute(bundle)
            response = await self.generator.generate(
                _direct_request(self.settings.hcx_model_name, case, raw),
                request_id=f"{case.case_id}-ablation-a-{repeat}",
            )
            answer = _parse_direct_answer(response.message_content)
            observation = _direct_observation(answer, _elapsed_ms(started))
        except Exception:
            prompt_tokens, completion_tokens = self.generator.usage_since(usage_index)
            return _failed_run(_elapsed_ms(started), prompt_tokens, completion_tokens)
        prompt_tokens, completion_tokens = self.generator.usage_since(usage_index)
        return _CaseRun(
            observation=observation,
            latency_ms=_elapsed_ms(started),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


def produce_raw_measurements(
    repository_root: Path,
    destination: Path,
    *,
    artifact_dir: Path,
    repeats: int,
) -> None:
    """Run all five variants over the exact canonical cases and atomically persist summaries."""
    if repeats < 2:
        raise ValueError("ablation requires at least two repeats")
    root = repository_root.resolve(strict=True)
    artifacts = artifact_dir.resolve(strict=True)
    cases = load_golden_cases(tuple(sorted((root / "evaluation/canonical").glob("*.jsonl"))))
    plans = _approved_plans(root, cases)
    settings = Settings(
        repository_root=root,
        artifact_dir=artifacts,
        database_path=artifacts / "finproof.duckdb",
        hcx_enabled=True,
    )
    measurements = asyncio.run(_run(settings, cases, plans, repeats))
    destination.mkdir(parents=True, exist_ok=True)
    for measurement in measurements:
        path = destination / f"{measurement.variant.name}.json"
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(measurement.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)


async def _run(
    settings: Settings,
    cases: tuple[GoldenCase, ...],
    plans: Mapping[str, QueryPlan],
    repeats: int,
) -> tuple[AblationMeasurement, ...]:
    async with create_hcx_http_client() as http_client:
        if settings.hcx_api_key is None:
            raise ValueError("HCX API key is missing")
        client = HcxClient(http_client=http_client, api_key=settings.hcx_api_key)
        generator = _RecordingGenerator(client)
        with open_runtime_artifact_session(settings) as session:
            fields = FieldRegistry.from_bundle(session.registries)
            validator = LocalPlanValidator(
                SemanticValidator(fields),
                entity_resolver=EntityResolver(EntityIndex.from_session(session)),
            )
            planner = _planner_for_ablation(
                generator=generator,
                validator=validator,
                registries=session.registries,
                model_name=settings.hcx_model_name,
            )
            experiment = _Experiment(settings, session, planner, generator)
            observed: dict[AblationVariant, dict[str, list[_CaseRun]]] = {
                variant: {case.case_id: [] for case in cases} for variant in AblationVariant
            }
            for repeat in range(1, repeats + 1):
                for case in cases:
                    for variant, run in (
                        await experiment.run_case(case, plans[case.case_id], repeat)
                    ).items():
                        observed[variant][case.case_id].append(run)
            facts = session.versions.runtime_facts()
            configuration_sha256 = sha256(
                json.dumps(
                    {
                        "facts": facts,
                        "model": settings.hcx_model_name,
                        "planner_prompt": PROMPT_VERSION,
                        "direct_prompt": _DIRECT_PROMPT_VERSION,
                        "repeats": repeats,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            identity = {
                "case_checksum": suite_checksum(cases),
                "code_commit": _code_commit(settings.repository_root),
                "artifact_version": facts["artifact_manifest_hash"],
                "configuration_sha256": configuration_sha256,
                "prompt_version": f"{PROMPT_VERSION}+{_DIRECT_PROMPT_VERSION}",
                "planner_model": settings.hcx_model_name,
                "environment": {
                    "python": platform.python_version(),
                    "implementation": sys.implementation.name,
                    "platform": platform.platform(),
                },
            }
            return tuple(
                _measurement(variant, cases, observed[variant], identity)
                for variant in AblationVariant
            )


def _measurement(
    variant: AblationVariant,
    cases: Sequence[GoldenCase],
    runs_by_case: Mapping[str, Sequence[_CaseRun]],
    identity: Mapping[str, object],
) -> AblationMeasurement:
    scores: list[CaseScore] = []
    latency: list[LatencySample] = []
    prompt_tokens = completion_tokens = 0
    errors = 0
    limitation_numerator = limitation_denominator = 0
    for case in cases:
        runs = tuple(runs_by_case[case.case_id])
        first = runs[0]
        observation = first.observation.model_copy(
            update={"repeat_signatures": tuple(_signature(run.observation) for run in runs)}
        )
        scores.append(score_case(case, observation))
        latency.extend(
            LatencySample(total_ms=run.latency_ms, succeeded=not run.error) for run in runs
        )
        prompt_tokens += sum(run.prompt_tokens for run in runs)
        completion_tokens += sum(run.completion_tokens for run in runs)
        errors += int(any(run.error for run in runs))
        expected = case.expected_answer.expect_limitation
        if expected is not None:
            limitation_denominator += 1
            limitation_numerator += int(expected is observation.limitation_present)
    numeric = _combined_ratio(scores, "numeric_values", "aggregate_values")
    return AblationMeasurement(
        variant=variant,
        case_checksum=str(identity["case_checksum"]),
        code_commit=str(identity["code_commit"]),
        artifact_version=str(identity["artifact_version"]),
        configuration_sha256=str(identity["configuration_sha256"]),
        prompt_version=str(identity["prompt_version"]),
        planner_model=str(identity["planner_model"]),
        environment={
            str(key): str(value) for key, value in _mapping(identity["environment"]).items()
        },
        case_count=len(cases),
        product_set_f1=_aggregate_ratio(scores, "product_set"),
        order_accuracy=_aggregate_ratio(scores, "product_order"),
        numeric_exact_match=numeric,
        evidence_coverage=_aggregate_ratio(scores, "evidence_coverage"),
        limitation_accuracy=(
            1.0 if limitation_denominator == 0 else limitation_numerator / limitation_denominator
        ),
        repeat_stability=_aggregate_ratio(scores, "repeat_stability"),
        latency=LatencySummary.from_samples(latency),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        error_count=errors,
    )


def _aggregate_ratio(scores: Sequence[CaseScore], field: str) -> float:
    ratios = tuple(getattr(score, field) for score in scores)
    numerator = sum(value.numerator for value in ratios)
    denominator = sum(value.denominator for value in ratios)
    return 1.0 if denominator == 0 else numerator / denominator


def _combined_ratio(scores: Sequence[CaseScore], *fields: str) -> float:
    ratios: tuple[RatioScore, ...] = tuple(
        getattr(score, field) for score in scores for field in fields
    )
    numerator = sum(value.numerator for value in ratios)
    denominator = sum(value.denominator for value in ratios)
    return 1.0 if denominator == 0 else numerator / denominator


def _approved_plans(root: Path, cases: Sequence[GoldenCase]) -> dict[str, QueryPlan]:
    by_id = {case.case_id: case for case in cases}
    plans: dict[str, QueryPlan] = {}
    for path in sorted((root / "evaluation/review_batches").glob("batch-*-reference-review.json")):
        raw = path.read_bytes()
        payload = json.loads(raw)
        for item in payload["cases"]:
            case_id = item["case_id"]
            case = by_id.get(case_id)
            if case is None:
                continue
            if (
                item["question"] != case.question
                or f"{path.name} sha256:{sha256(raw).hexdigest()}" not in case.review.source
            ):
                raise ValueError(f"canonical source identity differs: {case_id}")
            plans[case_id] = _plan_from_case(case, item["plan"]["entities"])
    for case in cases:
        if case.case_id in plans:
            continue
        if case.expected_plan.intent not in {Intent.CLARIFY, Intent.UNSUPPORTED}:
            raise ValueError(f"approved executable plan is missing: {case.case_id}")
        plans[case.case_id] = _plan_from_case(case, ())
    return plans


def _plan_from_case(case: GoldenCase, entities: object) -> QueryPlan:
    payload = case.expected_plan.model_dump(
        mode="json",
        exclude={"native_segments"},
    )
    for clause in payload.get("filters") or ():
        if clause.get("operator") in {"is_missing", "is_not_missing"}:
            clause.pop("value", None)
    for field in ("filters", "metrics", "sort"):
        payload[field] = payload[field] or []
    payload["entities"] = entities
    return QueryPlan.model_validate_json(json.dumps(payload, ensure_ascii=False))


def _raw_observation(
    case: GoldenCase,
    plan: QueryPlan,
    segments: Sequence[ExecutionSegment],
    raw: RawExecutionResult,
    latency_ms: int,
) -> ObservedCase:
    rows = tuple(row for segment in raw.segments for row in segment.rows)
    by_key = {(row.product_id, value.field_id): value.value for row in rows for value in row.values}
    values = tuple(
        ObservedValue(
            product_id=expectation.product_id,
            field_id=expectation.field_id,
            value_type=expectation.value_type,
            value=_typed_value(expectation.value_type, by_key[key]),
        )
        for expectation in case.expected_result.values
        if (key := (expectation.product_id, expectation.field_id)) in by_key
    )
    return ObservedCase(
        plan=plan,
        products=tuple(
            dict.fromkeys(
                ProductIdentity(
                    product_type=row.product_type,
                    native_result_grain=row.native_result_grain,
                    product_id=row.product_id,
                )
                for row in rows
            )
        ),
        values=values,
        segments=tuple(
            ObservedSegment(
                product_type=segment.product_type,
                native_result_grain=segment.native_result_grain,
                compatibility_partition=segment.product_type.value,
            )
            for segment in segments
        ),
        latency_ms=(latency_ms,),
    )


def _policy_observation(
    case: GoldenCase,
    plan: QueryPlan,
    policy: PolicyExecutionResult,
    latency_ms: int,
) -> ObservedCase:
    selected_rows = tuple(row.raw for row in policy.selected_rows)
    products = (
        ()
        if plan.intent is Intent.AGGREGATE
        else tuple(
            dict.fromkeys(
                ProductIdentity(
                    product_type=rank.value.product_type,
                    native_result_grain=rank.native_result_grain,
                    product_id=rank.value.product_id,
                )
                for rank in sorted(
                    policy.ranks,
                    key=lambda value: (value.rank, value.value.product_id),
                )
            )
        )
        if policy.ranks
        else tuple(
            dict.fromkeys(
                ProductIdentity(
                    product_type=row.product_type,
                    native_result_grain=row.native_result_grain,
                    product_id=row.product_id,
                )
                for row in selected_rows
            )
        )
    )
    values = [
        {
            "product_id": row.product_id,
            "field_id": value.field_id,
            "value": value.value,
        }
        for row in selected_rows
        for value in row.values
    ]
    values.extend(
        {
            "product_id": rank.value.product_id,
            "field_id": rank.field_id,
            "value": rank.value.value,
        }
        for rank in policy.ranks
    )
    return ObservedCase(
        plan=plan,
        products=products,
        values=_observed_values(case.expected_result.values, values, ()),
        aggregates=_policy_aggregates(case, plan, policy),
        limitation_present=bool(
            policy.warnings
            or policy.metric_policy.warnings
            or policy.dual_lens_labels
            or any(partition.caveats for partition in policy.partitions)
        ),
        latency_ms=(latency_ms,),
    )


def _policy_aggregates(
    case: GoldenCase,
    plan: QueryPlan,
    policy: PolicyExecutionResult,
) -> tuple[ObservedAggregate, ...]:
    aggregation = plan.aggregation
    if aggregation is None:
        return ()
    observed: list[ObservedAggregate] = []
    for result in policy.aggregates:
        expectation = next(
            (
                item
                for item in case.expected_result.aggregates
                if item.function is aggregation.function
                and item.field_id == result.field_id
                and item.product_type is result.product_type
                and item.native_result_grain is result.native_result_grain
                and item.partition_key == result.partition_key
                and len(item.group_values) == len(result.group_values)
                and all(
                    expected.field_id == actual.field_id
                    and expected.value == _typed_value(expected.value_type, actual.value)
                    for expected, actual in zip(
                        item.group_values,
                        result.group_values,
                        strict=True,
                    )
                )
            ),
            None,
        )
        value_type = (
            expectation.value_type
            if expectation is not None
            else _aggregate_value_type(aggregation.function, result.value)
        )
        groups = (
            expectation.group_values
            if expectation is not None
            else tuple(
                AggregateGroupValue(
                    field_id=value.field_id,
                    value_type=_value_type(value.value),
                    value=_typed_value(_value_type(value.value), value.value),
                )
                for value in result.group_values
            )
        )
        observed.append(
            ObservedAggregate(
                function=aggregation.function,
                field_id=result.field_id,
                product_type=result.product_type,
                native_result_grain=result.native_result_grain,
                partition_key=result.partition_key,
                group_values=groups,
                value_type=value_type,
                value=_typed_value(value_type, result.value),
            )
        )
    return tuple(observed)


def _aggregate_value_type(function: AggregationFunction, value: object) -> ValueType:
    if value is None:
        return ValueType.NULL
    if function is AggregationFunction.COUNT:
        return ValueType.INTEGER
    return ValueType.DECIMAL


def _value_type(value: object) -> ValueType:
    if value is None:
        return ValueType.NULL
    if type(value) is bool:
        return ValueType.BOOLEAN
    if type(value) is int:
        return ValueType.INTEGER
    if type(value) is Decimal:
        return ValueType.DECIMAL
    if type(value) is date:
        return ValueType.DATE
    return ValueType.TEXT


def _direct_request(model_name: str, case: GoldenCase, raw: RawExecutionResult) -> HcxRequest:
    rows = [
        {
            "product_type": row.product_type.value,
            "product_id": row.product_id,
            "values": [value.model_dump(mode="json") for value in row.values],
        }
        for segment in raw.segments
        for row in segment.rows
    ]
    system = (
        "Answer only from the supplied official retrieved rows. Return one JSON object with "
        "keys products, values, answer, limitation_present. products items contain product_type "
        "and product_id. values items contain product_id, field_id, value_type "
        "(decimal|integer|date|text|boolean|null), and value. Do not invent missing facts."
    )
    return HcxRequest.strict_json(
        model_name=model_name,
        messages=(
            HcxMessage(role="system", content=system),
            HcxMessage(
                role="user",
                content=json.dumps(
                    {"question": case.question, "retrieved_rows": rows},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            ),
        ),
        max_completion_tokens=2_048,
        temperature=0.0,
        seed=17,
    )


def _parse_direct_answer(content: str) -> _DirectAnswer:
    value = content.strip()
    if value.startswith("```json\n"):
        value = value[8:]
        if (closing_fence := value.find("\n```")) >= 0:
            value = value[:closing_fence]
    return _DirectAnswer.model_validate_json(value)


def _planner_for_ablation(
    *,
    generator: HcxGenerator,
    validator: LocalPlanValidator,
    registries: RegistryBundle,
    model_name: str,
) -> PlannerProtocol:
    return StructuredOutputPlanner(
        generator=generator,
        validator=validator,
        registries=registries,
        model_name=model_name,
    )


def _direct_observation(answer: _DirectAnswer, latency_ms: int) -> ObservedCase:
    return ObservedCase.model_validate(
        {
            "products": [
                {
                    "product_type": item.product_type,
                    "native_result_grain": native_result_grain(item.product_type),
                    "product_id": item.product_id,
                }
                for item in answer.products
            ],
            "values": answer.values,
            "answer_text": answer.answer,
            "limitation_present": answer.limitation_present,
            "latency_ms": (latency_ms,),
        }
    )


def _planner_had_error(planned: PlannedQuery) -> bool:
    attempts = planned.attempts
    return attempts.fallback_used or any(
        (attempts.parse_failures, attempts.semantic_failures, attempts.transport_failures)
    )


def _validation_context(planned: PlannedQuery) -> ValidationContext:
    context = planned.validated_plan.context
    if type(context) is not ValidationContext:
        raise TypeError("validated ablation context differs")
    return context


def _mapping(value: object) -> Mapping[object, object]:
    if not isinstance(value, Mapping):
        raise TypeError("ablation identity mapping differs")
    return value


def _failed_run(
    latency_ms: int,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> _CaseRun:
    return _CaseRun(
        observation=ObservedCase(latency_ms=(latency_ms,)),
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        error=True,
    )


def _signature(observation: ObservedCase) -> str:
    stable = observation.model_copy(update={"repeat_signatures": (), "latency_ms": ()})
    return sha256(stable.model_dump_json().encode()).hexdigest()


def _elapsed_ms(started: float) -> int:
    return max(0, int((monotonic() - started) * 1_000))
