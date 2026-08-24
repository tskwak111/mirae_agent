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

from finproof.core.errors import FinProofError
from finproof.core.settings import Settings
from finproof.domain.answers import AnswerRequest, AnswerResult, ClaimKind
from finproof.domain.execution import TraceValidation
from finproof.domain.query_plan import QueryPlan, ResultGrain
from finproof.entity import EntityIndex, EntityResolver
from finproof.evaluation.loader import load_golden_cases
from finproof.evaluation.models import (
    ExpectedValue,
    GoldenCase,
    ObservedCase,
    ObservedSegment,
    ObservedValue,
    ValueType,
)
from finproof.evaluation.runner import (
    EvaluationMode,
    EvaluationRunner,
    EvaluationService,
    ReplayVersions,
)
from finproof.planner.hcx_client import HcxClient, create_hcx_http_client
from finproof.planner.json_planner import StrictJsonPlanner
from finproof.planner.prompts import PROMPT_VERSION
from finproof.planner.rule_fallback import RuleFallbackPlanner
from finproof.planner.service import (
    LocalPlanValidator,
    PlannerProtocol,
    PlannerService,
    PlanningRequest,
)
from finproof.query import FieldRegistry, SemanticValidator
from finproof.runtime import open_runtime_artifact_session
from finproof.runtime.session import RuntimeArtifactSession
from finproof.service import AnswerService


def run_evaluation(
    suite: str,
    output: Path,
    mode: EvaluationMode,
    *,
    repository_root: Path | None = None,
    service: EvaluationService | None = None,
) -> None:
    root = repository_root or Path(__file__).resolve().parents[3]
    try:
        if suite != "canonical":
            raise ValueError("unknown evaluation suite")
        paths = tuple(sorted((root / "evaluation" / "canonical").glob("*.jsonl")))
        cases = load_golden_cases(paths)
        if service is not None:
            report = EvaluationRunner(mode=mode).run(cases, service)
        else:
            with _open_local_service(Settings(repository_root=root)) as local_service:
                report = EvaluationRunner(mode=mode).run(cases, local_service)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.tmp")
        temporary.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(output)
    except (OSError, ValueError, TypeError) as error:
        raise FinProofError("canonical evaluation could not be completed") from error


class _LocalEvaluationService:
    def __init__(
        self,
        *,
        session: RuntimeArtifactSession,
        planner: PlannerProtocol,
        answer_service: AnswerService,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._session = session
        self._planner = planner
        self._answer_service = answer_service
        self._loop = loop

    def replay_versions(self) -> ReplayVersions:
        facts = self._session.versions.runtime_facts()
        return ReplayVersions(
            artifact_version=facts["artifact_manifest_hash"],
            config_versions={
                key: value
                for key, value in facts.items()
                if key.endswith("_version") and key not in {"planner_version"}
            },
            prompt_version=PROMPT_VERSION,
            planner_version=facts["planner_version"],
        )

    def observe(self, case: GoldenCase, mode: EvaluationMode) -> ObservedCase:
        planned = self._loop.run_until_complete(
            self._planner.plan(
                PlanningRequest.start(
                    question=case.question,
                    request_id=case.case_id,
                    as_of_date=case.expected_plan.as_of_date,
                    execution_mode=self._session.versions.execution_mode,
                    deadline_seconds=15.0,
                )
            )
        )
        if mode is EvaluationMode.PLAN_ONLY:
            return ObservedCase(plan=planned.plan, latency_ms=(planned.latency_ms,))
        if mode is EvaluationMode.DETERMINISTIC_CORE:
            raise ValueError("deterministic-core CLI replay requires executable reviewed plans")
        result = self._answer_service.answer_plan(
            AnswerRequest(question_id=case.case_id, question=case.question),
            planned.plan,
        )
        return _observed(case, planned.plan, result, planned.latency_ms)


@contextmanager
def _open_local_service(settings: Settings) -> Iterator[_LocalEvaluationService]:
    loop = asyncio.new_event_loop()
    http_context = None
    try:
        with open_runtime_artifact_session(settings) as session:
            fields = FieldRegistry.from_bundle(session.registries)
            validator = LocalPlanValidator(
                SemanticValidator(fields),
                entity_resolver=EntityResolver(EntityIndex.from_session(session)),
            )
            fallback = RuleFallbackPlanner(validator=validator)
            planner: PlannerProtocol = fallback
            if settings.hcx_enabled:
                if settings.hcx_api_key is None:
                    raise ValueError("HCX API key is missing")
                http_context = create_hcx_http_client()
                client = loop.run_until_complete(http_context.__aenter__())
                planner = PlannerService(
                    strict_json_planner=StrictJsonPlanner(
                        generator=HcxClient(http_client=client, api_key=settings.hcx_api_key),
                        validator=validator,
                        registries=session.registries,
                        model_name=settings.hcx_model_name,
                    ),
                    rule_fallback=fallback,
                )
            yield _LocalEvaluationService(
                session=session,
                planner=planner,
                answer_service=AnswerService(session),
                loop=loop,
            )
    finally:
        if http_context is not None:
            loop.run_until_complete(http_context.__aexit__(None, None, None))
        loop.close()


def _observed(
    case: GoldenCase,
    plan: QueryPlan,
    result: AnswerResult,
    planner_latency_ms: int,
) -> ObservedCase:
    payload = json.loads(result.retrieved_context)
    direct = _rows(payload, "direct")
    derived = _rows(payload, "derived")
    summaries = tuple(value for value in payload.get("summaries", ()) if isinstance(value, Mapping))
    evidence_ids = tuple(
        dict.fromkeys(
            (
                *(str(value["evidence_id"]) for value in direct),
                *(str(value["evidence_id"]) for value in derived),
                *(str(value["summary_id"]) for value in summaries),
            )
        )
    )
    products = tuple(
        dict.fromkeys(
            str(value["product_id"])
            for value in (*direct, *derived)
            if value.get("product_id") is not None
        )
    )
    values = _observed_values(case.expected_result.values, (*direct, *derived), summaries)
    limitations = payload.get("material_policy_limitations", ())
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
        product_ids=products,
        values=values,
        answer_text=result.answer.text,
        evidence_ids=evidence_ids,
        limitation_present=bool(limitations)
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
        assembled_envelope=result.trace.result_grain is ResultGrain.PRODUCT,
        latency_ms=(planner_latency_ms + sum(result.trace.latency_ms.values()),),
    )


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


def _typed_value(value_type: ValueType, value: object) -> Decimal | date | str | bool | int:
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
    return str(value)
