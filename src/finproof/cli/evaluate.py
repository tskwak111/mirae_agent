"""Canonical evaluation command composition."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from finproof.answer.hcx_verbalizer import (
    ANSWER_PROMPT_VERSION,
    answer_schema_sha256,
)
from finproof.api.dependencies import ApiDependencies
from finproof.core.errors import FinProofError
from finproof.core.settings import ExecutionMode, Settings
from finproof.domain.answers import (
    AnswerClaim,
    AnswerRequest,
    AnswerResult,
    ClaimKind,
    FactPack,
    VerifiedAnswer,
)
from finproof.domain.execution import TraceValidation
from finproof.domain.query_plan import (
    AggregationFunction,
    Intent,
    ProductType,
    QueryPlan,
    ResultGrain,
)
from finproof.evaluation.adversarial import (
    AdversarialCase,
    AdversarialObservation,
    AdversarialRunner,
    AdversarialService,
    RobustnessReport,
    load_adversarial_cases,
)
from finproof.evaluation.loader import load_blind_suite, load_golden_cases, load_suite
from finproof.evaluation.metamorphic import MetamorphicKind
from finproof.evaluation.models import (
    ExpectedAggregate,
    ExpectedValue,
    GoldenCase,
    ObservedAggregate,
    ObservedCase,
    ObservedSegment,
    ObservedValue,
    ProductIdentity,
    ValueType,
    native_result_grain,
)
from finproof.evaluation.paraphrases import ParaphraseRules, generate_rule_paraphrases
from finproof.evaluation.runner import (
    EvaluationMode,
    EvaluationReport,
    EvaluationRunner,
    EvaluationService,
    ReplayVersions,
)
from finproof.planner.prompts import PROMPT_VERSION
from finproof.planner.service import PlanningRequest
from finproof.query import FieldRegistry
from finproof.registry.loader import RegistryBundle
from finproof.runtime import open_runtime_artifact_session
from finproof.runtime.session import RuntimeArtifactSession
from finproof.service.answer_service import AnswerService
from finproof.service.limits import RequestDeadline
from finproof.service.orchestrator import EvaluationOrchestrator
from finproof.service.publication import build_safe_publication


def run_evaluation(
    suite: str,
    output: Path,
    mode: EvaluationMode,
    *,
    repository_root: Path | None = None,
    service: RobustnessService | None = None,
) -> None:
    root = repository_root or Path(__file__).resolve().parents[3]
    try:
        if suite not in {
            "canonical",
            "robustness",
            "organizer_20260824",
            "blind_development",
            "blind_holdout",
        }:
            raise ValueError("unknown evaluation suite")
        if suite == "canonical":
            cases = load_golden_cases(
                tuple(sorted((root / "evaluation" / "canonical").glob("*.jsonl")))
            )
        elif suite == "organizer_20260824":
            cases = load_suite(suite, repository_root=root)
        elif suite in {"blind_development", "blind_holdout"}:
            cases = load_blind_suite(suite, repository_root=root)
        else:
            quality, paraphrases = _robustness_cases(root)
            cases = (*quality, *paraphrases)
        if service is not None:
            if service.replay_versions().execution_mode is ExecutionMode.EVALUATION:
                raise ValueError("evaluation service graph cannot be overridden")
            report = _run_suite(suite, root, mode, cases, service)
        else:
            settings = Settings(repository_root=root)
            if (
                suite
                in {
                    "organizer_20260824",
                    "blind_development",
                    "blind_holdout",
                }
                and mode is EvaluationMode.DETERMINISTIC_CORE
            ):
                settings = settings.model_copy(
                    update={
                        "execution_mode": ExecutionMode.EXTENDED_DEMO,
                        "hcx_enabled": False,
                        "hcx_api_key": None,
                    }
                )
                service_context = _open_reviewed_plan_service(settings)
            else:
                service_context = _open_local_service(settings)
            with service_context as local_service:
                report = _run_suite(suite, root, mode, cases, local_service)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.tmp")
        temporary.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(output)
    except (OSError, ValueError, TypeError) as error:
        raise FinProofError(f"{suite} evaluation could not be completed") from error


class RobustnessService(EvaluationService, AdversarialService, Protocol):
    pass


def _run_suite(
    suite: str,
    root: Path,
    mode: EvaluationMode,
    cases: Sequence[GoldenCase],
    service: RobustnessService,
) -> EvaluationReport | RobustnessReport:
    evaluation = EvaluationRunner(mode=mode).run(cases, service)
    if suite != "robustness":
        return evaluation
    quality_count = sum(case.category.value == "quality" for case in cases)
    return RobustnessReport(
        evaluation=evaluation,
        adversarial=AdversarialRunner().run(
            load_adversarial_cases(root / "evaluation" / "adversarial_cases.jsonl"),
            service,
        ),
        quality_case_count=quality_count,
        paraphrase_case_count=len(cases) - quality_count,
        metamorphic_relations=tuple(kind.value for kind in MetamorphicKind),
    )


def _robustness_cases(root: Path) -> tuple[tuple[GoldenCase, ...], tuple[GoldenCase, ...]]:
    canonical_root = root / "evaluation" / "canonical"
    quality = load_golden_cases((canonical_root / "quality.jsonl",))
    canonical = load_golden_cases(tuple(sorted(canonical_root.glob("*.jsonl"))))
    rules = ParaphraseRules.load(root / "evaluation" / "paraphrase_rules.yaml")
    by_rule: dict[str, GoldenCase] = {}
    for case in canonical:
        for derived in generate_rule_paraphrases(case, rules):
            by_rule.setdefault(derived.transformation_id, derived)
    if len(by_rule) != len(rules.rules):
        raise ValueError("every paraphrase rule requires a canonical application")
    return quality, tuple(by_rule[rule.rule_id] for rule in rules.rules)


def _reviewed_plan(case: GoldenCase, *, fields: FieldRegistry | None = None) -> QueryPlan:
    field_registry = fields or FieldRegistry.from_bundle(RegistryBundle.from_package())
    payload = case.expected_plan.model_dump(exclude={"native_segments"})
    filters: list[dict[str, object]] = []
    for clause in case.expected_plan.filters or ():
        clause_payload = clause.model_dump(
            exclude={"value"}
            if clause.operator.value in {"is_missing", "is_not_missing"}
            else set()
        )
        projections = tuple(
            field_registry.projections.get((clause.field, product_type))
            for product_type in case.expected_plan.product_types
        )
        if projections and all(
            projection is not None and projection.value_type == "decimal"
            for projection in projections
        ):
            value = clause_payload.get("value")
            if type(value) is str:
                clause_payload["value"] = Decimal(value)
            elif isinstance(value, tuple):
                clause_payload["value"] = tuple(
                    Decimal(item) if type(item) is str else item for item in value
                )
        filters.append(clause_payload)
    payload["filters"] = tuple(filters)
    return QueryPlan.model_validate(
        {
            **payload,
            "entities": case.reviewed_entities,
        }
    )


class _LocalEvaluationService:
    def __init__(
        self,
        *,
        session: RuntimeArtifactSession,
        orchestrator: EvaluationOrchestrator | None,
        loop: asyncio.AbstractEventLoop,
        settings: Settings,
    ) -> None:
        self._session = session
        self._orchestrator = orchestrator
        self._loop = loop
        self._settings = settings

    def replay_versions(self) -> ReplayVersions:
        facts = self._session.versions.runtime_facts()
        hcx_enabled = self._settings.hcx_enabled
        return ReplayVersions.from_configuration(
            artifact_version=facts["artifact_manifest_hash"],
            config_versions={
                key: value
                for key, value in facts.items()
                if key.endswith("_version") and key not in {"planner_version"}
            },
            prompt_version=PROMPT_VERSION,
            answer_prompt_version=ANSWER_PROMPT_VERSION if hcx_enabled else None,
            answer_schema_sha256=answer_schema_sha256() if hcx_enabled else None,
            wording_verification_mode=(
                "allowlisted-presentation-plus-exact-surface-v1" if hcx_enabled else None
            ),
            planner_version=facts["planner_version"],
            execution_mode=self._settings.execution_mode,
            hcx_enabled=hcx_enabled,
            planner_model=self._settings.hcx_model_name if hcx_enabled else None,
            fallback_enabled=not hcx_enabled,
            structured_outputs_enabled=hcx_enabled,
        )

    def observe(self, case: GoldenCase, mode: EvaluationMode) -> ObservedCase:
        deadline = RequestDeadline.start()
        planning_request = PlanningRequest(
            question=case.question,
            request_id=case.case_id,
            as_of_date=case.expected_plan.as_of_date,
            execution_mode=self._session.versions.execution_mode,
        )
        if mode is EvaluationMode.PLAN_ONLY:
            if self._orchestrator is None:
                raise ValueError("reviewed-plan service only supports deterministic core")
            plan_only_result = self._loop.run_until_complete(
                self._orchestrator.plan(planning_request, deadline=deadline)
            )
            return ObservedCase(
                plan=plan_only_result.plan,
                latency_ms=(plan_only_result.latency_ms,),
            )
        if mode is EvaluationMode.DETERMINISTIC_CORE:
            plan = _reviewed_plan(case)
            prepared = AnswerService(self._session).prepare_plan(
                AnswerRequest(question_id=case.case_id, question=case.question),
                plan,
                deadline,
            )
            result = AnswerResult(
                answer=VerifiedAnswer(
                    text=prepared.fact_pack.surface_parts[0].text,
                    claims=prepared.claims,
                ),
                retrieved_context=prepared.retrieved_context,
                trace=prepared.trace,
            )
            return _observed(case, plan, result, 0)
        if self._orchestrator is None:
            raise ValueError("reviewed-plan service only supports deterministic core")
        request = AnswerRequest(question_id=case.case_id, question=case.question)
        safe = build_safe_publication(
            request,
            correlation_id=f"cli-{case.case_id}"[:200],
            snapshot_date=self._settings.dataset_snapshot_date,
            deadline=deadline,
        ).result
        planned, result = self._loop.run_until_complete(
            self._orchestrator.answer_with_plan(request, deadline=deadline, safe_result=safe)
        )
        if planned is None:
            return ObservedCase(answer_text=result.answer.text)
        return _observed(case, planned.plan, result, planned.latency_ms)

    def observe_adversarial(self, case: AdversarialCase) -> AdversarialObservation:
        if self._orchestrator is None:
            raise ValueError("reviewed-plan service does not support adversarial replay")
        try:
            request = AnswerRequest(question_id=case.case_id, question=case.question)
            deadline = RequestDeadline.start()
            _ = PlanningRequest(
                question=case.question,
                request_id=case.case_id,
                as_of_date=self._settings.dataset_snapshot_date,
                execution_mode=self._session.versions.execution_mode,
            )
        except ValidationError:
            return AdversarialObservation(rejected=True)
        safe = build_safe_publication(
            request,
            correlation_id=f"cli-{case.case_id}"[:200],
            snapshot_date=self._settings.dataset_snapshot_date,
            deadline=deadline,
        ).result
        planned, result = self._loop.run_until_complete(
            self._orchestrator.answer_with_plan(request, deadline=deadline, safe_result=safe)
        )
        if planned is None:
            return AdversarialObservation(answer=result.answer, trace=result.trace)
        return AdversarialObservation(
            plan=planned.plan,
            validated=True,
            answer=result.answer,
            trace=result.trace,
        )


@contextmanager
def _open_local_service(settings: Settings) -> Iterator[_LocalEvaluationService]:
    loop = asyncio.new_event_loop()
    orchestrator_context = None
    orchestrator_open = False
    try:
        with open_runtime_artifact_session(settings) as session:
            dependencies = ApiDependencies()
            orchestrator_context = dependencies.open_orchestrator(session, settings)
            orchestrator = loop.run_until_complete(orchestrator_context.__aenter__())
            orchestrator_open = True
            if type(orchestrator) is not EvaluationOrchestrator:
                raise TypeError("evaluation graph differs")
            yield _LocalEvaluationService(
                session=session,
                orchestrator=orchestrator,
                loop=loop,
                settings=settings,
            )
    finally:
        if orchestrator_context is not None and orchestrator_open:
            loop.run_until_complete(orchestrator_context.__aexit__(None, None, None))
        loop.close()


@contextmanager
def _open_reviewed_plan_service(settings: Settings) -> Iterator[_LocalEvaluationService]:
    loop = asyncio.new_event_loop()
    try:
        with open_runtime_artifact_session(settings) as session:
            yield _LocalEvaluationService(
                session=session,
                orchestrator=None,
                loop=loop,
                settings=settings,
            )
    finally:
        loop.close()


def _observed(
    case: GoldenCase,
    plan: QueryPlan,
    result: AnswerResult,
    planner_latency_ms: int,
) -> ObservedCase:
    payload = json.loads(result.retrieved_context)
    fact_pack = FactPack.model_validate_json(result.retrieved_context)
    claims = result.answer.claims
    if tuple(claim.claim_id for claim in claims) != fact_pack.required_claim_ids:
        raise ValueError("observed fact-pack claims differ")
    evidence_ids = tuple(
        dict.fromkeys(evidence_id for claim in claims for evidence_id in claim.evidence_ids)
    )
    products = _observed_claim_products(plan, claims)
    values = _observed_claim_values(case.expected_result.values, claims)
    aggregates = _observed_claim_aggregates(plan, case.expected_result.aggregates, claims)
    signature = sha256(
        json.dumps(
            {
                "plan": result.trace.model_dump(mode="json"),
                "context": payload,
                "answer": result.answer.text,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return ObservedCase(
        plan=plan,
        products=products,
        values=values,
        aggregates=aggregates,
        answer_text=result.answer.text,
        evidence_ids=evidence_ids,
        limitation_present=bool(fact_pack.required_limitation_codes)
        or any(claim.kind is ClaimKind.LIMITATION for claim in result.answer.claims),
        clarification_present=result.trace.validation is TraceValidation.CLARIFY,
        repeat_signatures=(signature,),
        segments=tuple(
            ObservedSegment(
                product_type=segment.product_type,
                native_result_grain=segment.native_result_grain,
                compatibility_partition=segment.partition_key,
            )
            for segment in result.trace.segments
        ),
        compatibility_partitions=tuple(
            dict.fromkeys(segment.partition_key for segment in result.trace.segments)
        ),
        assembled_envelope=(
            result.trace.result_grain is ResultGrain.PRODUCT
            and len({segment.native_result_grain for segment in result.trace.segments}) > 1
        ),
        latency_ms=(planner_latency_ms + sum(result.trace.latency_ms.values()),),
    )


def _observed_claim_products(
    plan: QueryPlan,
    claims: Sequence[AnswerClaim],
) -> tuple[ProductIdentity, ...]:
    if plan.intent is Intent.AGGREGATE:
        return ()
    return tuple(
        dict.fromkeys(
            ProductIdentity(
                product_type=claim.product_type,
                native_result_grain=native_result_grain(claim.product_type),
                product_id=claim.product_id,
            )
            for claim in claims
            if claim.product_type is not None and claim.product_id is not None
        )
    )


def _observed_claim_values(
    expected: Sequence[ExpectedValue],
    claims: Sequence[AnswerClaim],
) -> tuple[ObservedValue, ...]:
    by_key: dict[tuple[str | None, str], object] = {
        (claim.product_id, claim.field_id): claim.value
        for claim in claims
        if claim.product_id is not None and claim.field_id is not None
    }
    return tuple(
        ObservedValue(
            product_id=item.product_id,
            field_id=item.field_id,
            value_type=item.value_type,
            value=_typed_value(item.value_type, by_key[(item.product_id, item.field_id)]),
        )
        for item in expected
        if (item.product_id, item.field_id) in by_key
    )


def _observed_claim_aggregates(
    plan: QueryPlan,
    expected: Sequence[ExpectedAggregate],
    claims: Sequence[AnswerClaim],
) -> tuple[ObservedAggregate, ...]:
    if plan.aggregation is None:
        return ()
    observed: list[ObservedAggregate] = []
    for claim in claims:
        if (
            claim.product_type is None
            or len(claim.native_result_grains) != 1
            or claim.partition_key is None
            or claim.field_id != plan.aggregation.field
            or claim.value is None
        ):
            continue
        candidates = tuple(
            item
            for item in expected
            if item.function is plan.aggregation.function
            and item.field_id == claim.field_id
            and item.product_type is claim.product_type
            and item.native_result_grain is claim.native_result_grains[0]
            and item.partition_key == claim.partition_key
            and tuple((value.field_id, value.value) for value in item.group_values)
            == tuple((value.field_id, value.value) for value in claim.group_values)
        )
        if len(candidates) > 1:
            raise ValueError("aggregate claim identity is ambiguous")
        value_type = (
            candidates[0].value_type
            if candidates
            else ValueType.INTEGER
            if plan.aggregation.function is AggregationFunction.COUNT
            else ValueType.DECIMAL
        )
        group_values = (
            tuple(value.model_dump(mode="python") for value in candidates[0].group_values)
            if candidates
            else tuple(_inferred_group_value(value.model_dump()) for value in claim.group_values)
        )
        observed.append(
            ObservedAggregate.model_validate(
                {
                    "function": plan.aggregation.function,
                    "field_id": claim.field_id,
                    "product_type": claim.product_type,
                    "native_result_grain": claim.native_result_grains[0],
                    "partition_key": claim.partition_key,
                    "group_values": group_values,
                    "value_type": value_type,
                    "value": _typed_value(value_type, claim.value),
                }
            )
        )
    return tuple(observed)


def _observed_products(
    plan: QueryPlan,
    evidence: Sequence[Mapping[str, object]],
    summaries: Sequence[Mapping[str, object]],
) -> tuple[ProductIdentity, ...]:
    if plan.intent is Intent.AGGREGATE:
        return ()
    ranked = tuple(
        _summary_product_identity(summary) for summary in summaries if summary.get("kind") == "rank"
    )
    if ranked:
        return tuple(dict.fromkeys(ranked))
    selected = tuple(
        ProductIdentity(
            product_type=ProductType(str(value["product_type"])),
            native_result_grain=native_result_grain(ProductType(str(value["product_type"]))),
            product_id=str(value["product_id"]),
        )
        for value in evidence
        if value.get("product_id") is not None
    )
    return tuple(dict.fromkeys(selected))


def _summary_product_identity(summary: Mapping[str, object]) -> ProductIdentity:
    product_types = summary.get("product_types")
    native_grains = summary.get("native_result_grains")
    product_id = summary.get("product_id")
    if (
        not isinstance(product_types, Sequence)
        or isinstance(product_types, (str, bytes))
        or len(product_types) != 1
        or not isinstance(native_grains, Sequence)
        or isinstance(native_grains, (str, bytes))
        or len(native_grains) != 1
        or product_id is None
    ):
        raise ValueError("rank summary product identity differs")
    return ProductIdentity(
        product_type=ProductType(str(product_types[0])),
        native_result_grain=ResultGrain(str(native_grains[0])),
        product_id=str(product_id),
    )


def _observed_aggregates(
    expected: Sequence[ExpectedAggregate],
    summaries: Sequence[Mapping[str, object]],
) -> tuple[ObservedAggregate, ...]:
    observed: list[ObservedAggregate] = []
    for summary in summaries:
        if summary.get("kind") != "aggregate":
            continue
        function = _summary_aggregation_function(summary)
        product = _summary_aggregate_product(summary)
        partition_key = summary.get("partition_key")
        field_id = summary.get("metric_id")
        group_values = summary.get("group_values", ())
        if (
            type(partition_key) is not str
            or not isinstance(group_values, Sequence)
            or isinstance(group_values, (str, bytes))
        ):
            raise ValueError("aggregate summary identity differs")
        raw_groups = tuple(group_values)
        candidates = tuple(
            item
            for item in expected
            if item.function is function
            and item.field_id == field_id
            and item.product_type is product.product_type
            and item.native_result_grain is product.native_result_grain
            and item.partition_key == partition_key
            and _groups_match(item, raw_groups)
        )
        if len(candidates) > 1:
            raise ValueError("aggregate summary group values are ambiguous")
        typed_groups: tuple[dict[str, object], ...]
        if candidates:
            expectation = candidates[0]
            typed_groups = tuple(
                {
                    "field_id": group.field_id,
                    "value_type": group.value_type,
                    "value": _typed_value(group.value_type, raw["value"]),
                }
                for group, raw in zip(expectation.group_values, raw_groups, strict=True)
                if isinstance(raw, Mapping)
            )
            value_type = expectation.value_type
        else:
            typed_groups = tuple(_inferred_group_value(raw) for raw in raw_groups)
            value_type = (
                ValueType.NULL
                if summary.get("value") is None
                else ValueType.INTEGER
                if function is AggregationFunction.COUNT
                else ValueType.DECIMAL
            )
        observed.append(
            ObservedAggregate.model_validate(
                {
                    "function": function,
                    "field_id": field_id,
                    "product_type": product.product_type,
                    "native_result_grain": product.native_result_grain,
                    "partition_key": partition_key,
                    "group_values": typed_groups,
                    "value_type": value_type,
                    "value": _typed_value(value_type, summary.get("value")),
                }
            )
        )
    return tuple(observed)


def _summary_aggregation_function(summary: Mapping[str, object]) -> AggregationFunction:
    policies = summary.get("policy_versions")
    if not isinstance(policies, Sequence) or isinstance(policies, (str, bytes)):
        raise ValueError("aggregate summary policy identity differs")
    functions: set[AggregationFunction] = set()
    for policy in policies:
        try:
            functions.add(AggregationFunction(str(policy).rsplit(":", 1)[-1]))
        except ValueError:
            continue
    if len(functions) != 1:
        raise ValueError("aggregate summary function differs")
    return next(iter(functions))


def _summary_aggregate_product(summary: Mapping[str, object]) -> ProductIdentity:
    return _summary_product_identity({**summary, "product_id": "aggregate"})


def _groups_match(expectation: ExpectedAggregate, raw_groups: Sequence[object]) -> bool:
    if len(expectation.group_values) != len(raw_groups):
        return False
    for expected, raw in zip(expectation.group_values, raw_groups, strict=True):
        if not isinstance(raw, Mapping) or raw.get("field_id") != expected.field_id:
            return False
        try:
            actual = _typed_value(expected.value_type, raw.get("value"))
        except (TypeError, ValueError):
            return False
        if actual != expected.value:
            return False
    return True


def _inferred_group_value(raw: object) -> dict[str, object]:
    if not isinstance(raw, Mapping) or type(raw.get("field_id")) is not str:
        raise ValueError("aggregate group value differs")
    value = raw.get("value")
    value_type = (
        ValueType.NULL
        if value is None
        else ValueType.BOOLEAN
        if type(value) is bool
        else ValueType.INTEGER
        if type(value) is int
        else ValueType.TEXT
    )
    return {"field_id": raw["field_id"], "value_type": value_type, "value": value}


def _rows(payload: Mapping[str, object], name: str) -> tuple[dict[str, object], ...]:
    fields = payload.get(f"{name}_fields", ())
    rows = payload.get(name, ())
    if not isinstance(fields, Sequence) or not isinstance(rows, Sequence):
        raise ValueError("evidence context shape differs")
    return tuple(dict(zip(fields, row, strict=True)) for row in rows if isinstance(row, Sequence))


def _observed_values(
    expected: Sequence[ExpectedValue],
    evidence: Sequence[Mapping[str, object]],
    summaries: Sequence[Mapping[str, object]],
) -> tuple[ObservedValue, ...]:
    by_key = {
        (value.get("product_id"), value.get("field_id")): value.get(
            "normalized_value", value.get("value")
        )
        for value in evidence
    }
    by_key.update(
        {
            (value.get("product_id"), value.get("metric_id")): value.get("value")
            for value in summaries
        }
    )
    observed: list[ObservedValue] = []
    for expectation in expected:
        key = (expectation.product_id, expectation.field_id)
        if key not in by_key:
            continue
        observed.append(
            ObservedValue(
                product_id=expectation.product_id,
                field_id=expectation.field_id,
                value_type=expectation.value_type,
                value=_typed_value(expectation.value_type, by_key[key]),
            )
        )
    return tuple(observed)


def _typed_value(value_type: ValueType, value: object) -> Decimal | date | str | bool | int | None:
    if value_type is ValueType.DECIMAL:
        return Decimal(str(value))
    if value_type is ValueType.INTEGER:
        return int(str(value))
    if value_type is ValueType.DATE:
        return date.fromisoformat(str(value))
    if value_type is ValueType.BOOLEAN:
        if type(value) is not bool:
            raise ValueError("observed boolean differs")
        return value
    if value_type is ValueType.NULL:
        if value is not None:
            raise ValueError("observed null differs")
        return None
    return str(value)
