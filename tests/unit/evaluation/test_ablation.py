import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

import finproof.evaluation.ablation as ablation
from finproof.core.settings import ExecutionMode
from finproof.domain.query_plan import ProductType, QueryPlan, ResultGrain
from finproof.evaluation.ablation import (
    AblationMeasurement,
    AblationRunner,
    AblationVariant,
    main,
)
from finproof.evaluation.ablation_experiment import (
    _approved_plans,
    _CaseRun,
    _direct_request,
    _Experiment,
    _parse_direct_answer,
    _planner_for_ablation,
    _policy_observation,
    _RecordingGenerator,
    _within_case_deadline,
)
from finproof.evaluation.ablation_experiment import (
    _measurement as _experiment_measurement,
)
from finproof.evaluation.latency import LatencySummary
from finproof.evaluation.loader import load_golden_cases, suite_checksum
from finproof.evaluation.models import GoldenCase, ObservedCase
from finproof.planner.hcx_client import HcxClient, HcxRateLimitError
from finproof.planner.models import HcxMessage, HcxRequest, HcxResponse, HcxUsage
from finproof.planner.rate_limits import HcxRateLimitSnapshot
from finproof.planner.service import (
    HcxGenerator,
    LocalPlanValidator,
    PlannedQuery,
    PlanningRequest,
)
from finproof.planner.structured_planner import StructuredOutputPlanner
from finproof.quality import PolicyExecutionResult
from finproof.quality.metric_policy import MetricPolicyResult
from finproof.registry.loader import RegistryBundle
from finproof.runtime import RuntimeArtifactSession
from finproof.service.limits import RequestDeadline
from finproof.storage.repositories.products import (
    RawExecutionResult,
    RawFieldValue,
    RawProductRow,
    RawSegmentResult,
)


class _FailingPlanner:
    async def plan(self, _request: PlanningRequest) -> PlannedQuery:
        raise ValueError("local plan validation failed")


class _UsageGenerator:
    def __init__(self) -> None:
        self.responses: list[object] = []

    def usage_since(self, _index: int) -> tuple[int, int]:
        return 13, 8


def test_direct_ablation_bounds_rows_as_an_explicit_source_ordered_prefix() -> None:
    case = load_golden_cases((Path("evaluation/canonical/lookup.jsonl"),))[0]
    rows = tuple(
        RawProductRow(
            product_type=ProductType.DOMESTIC_ETF,
            native_result_grain=ResultGrain.LISTED_PRODUCT,
            product_id=f"P-{index:03d}",
            values=(
                RawFieldValue(
                    field_id="product_name",
                    value=f"source-{index:03d}-" + "가" * 4_000,
                    quality_status="valid",
                ),
            ),
        )
        for index in range(50)
    )
    raw = RawExecutionResult(
        segments=(
            RawSegmentResult(
                product_type=ProductType.DOMESTIC_ETF,
                native_result_grain=ResultGrain.LISTED_PRODUCT,
                rows=rows,
                candidate_count=50,
                max_batch_rows=50,
            ),
        ),
        candidate_count=50,
    )

    request = _direct_request("HCX-007", case, raw)
    user_payload = json.loads(request.messages[1].content)
    included = user_payload["retrieved_rows"]

    assert 0 < len(included) < 50
    assert [row["product_id"] for row in included] == [
        row.product_id for row in rows[: len(included)]
    ]
    assert user_payload["retrieved_row_count"] == 50
    assert user_payload["included_row_count"] == len(included)
    assert user_payload["truncated"] is True


@pytest.mark.asyncio
async def test_ablation_paces_hcx_calls_from_the_remaining_token_budget() -> None:
    response = HcxResponse(
        status_code="20000",
        status_message="OK",
        message_content="{}",
        usage=HcxUsage(prompt_tokens=9_000, completion_tokens=1_000, total_tokens=10_000),
        rate_limits=HcxRateLimitSnapshot(
            limit_requests=60,
            remaining_requests=59,
            reset_requests_seconds=60.0,
            limit_tokens=60_000,
            remaining_tokens=50_000,
            reset_tokens_seconds=60.0,
        ),
    )
    sleeps: list[float] = []

    class Client:
        async def generate(
            self,
            _request: HcxRequest,
            _request_id: str,
            *,
            deadline: RequestDeadline,
        ) -> HcxResponse:
            assert deadline.remaining_work_seconds() > 0
            return response

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    generator = _RecordingGenerator(cast(HcxClient, Client()), sleep=sleep)
    request = HcxRequest.strict_json(
        model_name="HCX-007",
        messages=(HcxMessage(role="user", content="test"),),
        max_completion_tokens=2_048,
        temperature=0.0,
        seed=17,
    )

    await generator.run(
        lambda: generator.generate(request, "first", deadline=RequestDeadline.start())
    )
    await generator.run(
        lambda: generator.generate(request, "second", deadline=RequestDeadline.start())
    )

    assert sleeps == [13.2576]


@pytest.mark.asyncio
async def test_ablation_waits_for_token_reset_before_a_larger_next_request() -> None:
    response = HcxResponse(
        status_code="20000",
        status_message="OK",
        message_content="{}",
        usage=HcxUsage(prompt_tokens=9_000, completion_tokens=1_000, total_tokens=10_000),
        rate_limits=HcxRateLimitSnapshot(
            remaining_requests=59,
            reset_requests_seconds=60.0,
            remaining_tokens=50_000,
            reset_tokens_seconds=60.0,
        ),
    )
    sleeps: list[float] = []
    attempts = 0

    class Client:
        async def generate(
            self,
            _request: HcxRequest,
            _request_id: str,
            *,
            deadline: RequestDeadline,
        ) -> HcxResponse:
            nonlocal attempts
            assert deadline.remaining_work_seconds() > 0
            attempts += 1
            return response

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    generator = _RecordingGenerator(cast(HcxClient, Client()), sleep=sleep)
    small = HcxRequest.strict_json(
        model_name="HCX-007",
        messages=(HcxMessage(role="user", content="small"),),
        max_completion_tokens=2_048,
        temperature=0.0,
        seed=17,
    )
    large = HcxRequest.strict_json(
        model_name="HCX-007",
        messages=(HcxMessage(role="user", content="가" * 20_000),),
        max_completion_tokens=2_048,
        temperature=0.0,
        seed=17,
    )

    await generator.run(
        lambda: generator.generate(small, "small", deadline=RequestDeadline.start())
    )
    await generator.run(
        lambda: generator.generate(large, "large", deadline=RequestDeadline.start())
    )

    assert attempts == 2
    assert sleeps == [13.2576, 60.0]


@pytest.mark.asyncio
async def test_ablation_retries_one_rate_limited_hcx_call_after_reset() -> None:
    response = HcxResponse(
        status_code="20000",
        status_message="OK",
        message_content="{}",
        usage=HcxUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        rate_limits=HcxRateLimitSnapshot(),
    )
    sleeps: list[float] = []
    attempts = 0

    class Client:
        async def generate(
            self,
            _request: HcxRequest,
            _request_id: str,
            *,
            deadline: RequestDeadline,
        ) -> HcxResponse:
            nonlocal attempts
            assert deadline.remaining_work_seconds() > 0
            attempts += 1
            if attempts == 1:
                raise HcxRateLimitError(
                    "42902",
                    HcxRateLimitSnapshot(
                        reset_requests_seconds=2.0,
                        reset_tokens_seconds=4.0,
                    ),
                )
            return response

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    generator = _RecordingGenerator(cast(HcxClient, Client()), sleep=sleep)
    request = cast(HcxRequest, object())

    observed = await generator.run(
        lambda: generator.generate(request, "rate-limited", deadline=RequestDeadline.start())
    )

    assert observed is response
    assert attempts == 2
    assert sleeps == [4.0]


@pytest.mark.asyncio
async def test_ablation_carries_a_second_rate_limit_reset_to_the_next_call() -> None:
    sleeps: list[float] = []

    class Client:
        async def generate(
            self,
            _request: HcxRequest,
            _request_id: str,
            *,
            deadline: RequestDeadline,
        ) -> HcxResponse:
            assert deadline.remaining_work_seconds() > 0
            raise HcxRateLimitError(
                "42902",
                HcxRateLimitSnapshot(reset_tokens_seconds=4.0),
            )

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    generator = _RecordingGenerator(cast(HcxClient, Client()), sleep=sleep)
    request = cast(HcxRequest, object())

    with pytest.raises(HcxRateLimitError):
        await generator.run(
            lambda: generator.generate(request, "first", deadline=RequestDeadline.start())
        )
    with pytest.raises(HcxRateLimitError):
        await generator.run(
            lambda: generator.generate(request, "second", deadline=RequestDeadline.start())
        )

    assert sleeps == [4.0, 4.0, 4.0]


@pytest.mark.asyncio
async def test_ablation_case_deadline_bounds_a_trickling_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("finproof.evaluation.ablation_experiment._CASE_DEADLINE_SECONDS", 0.001)

    async def never_finishes() -> None:
        await asyncio.Event().wait()

    with pytest.raises(TimeoutError):
        await _within_case_deadline(never_finishes())


def _measurement(
    variant: AblationVariant,
    case_count: int,
    case_checksum: str,
) -> AblationMeasurement:
    return AblationMeasurement(
        variant=variant,
        case_checksum=case_checksum,
        code_commit="b" * 40,
        artifact_version="artifact-v1",
        configuration_sha256="c" * 64,
        prompt_version="1.0.0",
        planner_model="HCX-007",
        environment={"python": "3.12"},
        case_count=case_count,
        product_set_f1=1.0,
        order_accuracy=1.0,
        numeric_exact_match=1.0,
        evidence_coverage=1.0,
        limitation_accuracy=1.0,
        repeat_stability=1.0,
        latency=LatencySummary.from_milliseconds((10, 20)),
        prompt_tokens=10,
        completion_tokens=5,
        error_count=0,
    )


def test_ablation_runner_uses_the_same_cases_and_identity_for_exact_variants() -> None:
    cases = load_golden_cases((Path("evaluation/canonical/lookup.jsonl"),))[:2]
    observed_case_ids: list[tuple[str, ...]] = []

    def measure(
        variant: AblationVariant,
        measured_cases: tuple[GoldenCase, ...],
    ) -> AblationMeasurement:
        observed_case_ids.append(tuple(case.case_id for case in measured_cases))
        return _measurement(variant, len(measured_cases), suite_checksum(cases))

    report = AblationRunner(measure).run(tuple(AblationVariant), cases)

    assert tuple(result.variant for result in report.results) == tuple(AblationVariant)
    assert observed_case_ids == [tuple(case.case_id for case in cases)] * 5
    assert report.case_checksum == suite_checksum(cases)


def test_ablation_runner_keeps_actual_token_latency_and_error_measurements() -> None:
    cases = load_golden_cases((Path("evaluation/canonical/lookup.jsonl"),))[:1]

    def measure(
        variant: AblationVariant,
        measured_cases: tuple[GoldenCase, ...],
    ) -> AblationMeasurement:
        return _measurement(variant, len(measured_cases), suite_checksum(cases)).model_copy(
            update={"error_count": 1 if variant is AblationVariant.A_DIRECT_HCX else 0}
        )

    report = AblationRunner(measure).run(tuple(AblationVariant), cases)

    direct = report.results[0]
    assert direct.prompt_tokens == 10
    assert direct.completion_tokens == 5
    assert direct.latency.p95_ms == 20
    assert direct.error_count == 1


def test_ablation_runner_rejects_measurements_from_other_cases() -> None:
    cases = load_golden_cases((Path("evaluation/canonical/lookup.jsonl"),))[:1]

    def measure(
        variant: AblationVariant,
        measured_cases: tuple[GoldenCase, ...],
    ) -> AblationMeasurement:
        return _measurement(variant, len(measured_cases), "d" * 64)

    with pytest.raises(ValueError, match="case checksum differs"):
        AblationRunner(measure).run(tuple(AblationVariant), cases)


def test_ablation_command_validates_raw_variant_measurements(tmp_path: Path) -> None:
    cases = load_golden_cases(tuple(sorted(Path("evaluation/canonical").glob("*.jsonl"))))
    measurement_dir = tmp_path / "raw"
    measurement_dir.mkdir()
    for variant in AblationVariant:
        (measurement_dir / f"{variant.name}.json").write_text(
            _measurement(variant, len(cases), suite_checksum(cases)).model_dump_json(),
            encoding="utf-8",
        )
    output = tmp_path / "ablation.json"

    assert (
        main(
            [
                "--repository-root",
                str(Path.cwd()),
                "--measurement-dir",
                str(measurement_dir),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert len(output.read_text(encoding="utf-8")) > 0


def test_ablation_command_can_produce_then_validate_raw_measurements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cases = load_golden_cases(tuple(sorted(Path("evaluation/canonical").glob("*.jsonl"))))
    measurement_dir = tmp_path / "raw"
    output = tmp_path / "ablation.json"
    observed: list[tuple[Path, Path, int]] = []

    def produce_raw_measurements(
        repository_root: Path,
        destination: Path,
        *,
        artifact_dir: Path,
        repeats: int,
    ) -> None:
        observed.append((repository_root, artifact_dir, repeats))
        destination.mkdir()
        for variant in AblationVariant:
            (destination / f"{variant.name}.json").write_text(
                _measurement(variant, len(cases), suite_checksum(cases)).model_dump_json(),
                encoding="utf-8",
            )

    monkeypatch.setattr(ablation, "produce_raw_measurements", produce_raw_measurements)

    assert (
        main(
            [
                "--repository-root",
                str(Path.cwd()),
                "--measurement-dir",
                str(measurement_dir),
                "--output",
                str(output),
                "--produce",
                "--artifact-dir",
                str(tmp_path / "official-artifacts"),
                "--repeats",
                "2",
            ]
        )
        == 0
    )
    assert observed == [(Path.cwd(), tmp_path / "official-artifacts", 2)]


def test_ablation_experiment_loads_an_approved_plan_for_every_canonical_case() -> None:
    cases = load_golden_cases(tuple(sorted(Path("evaluation/canonical").glob("*.jsonl"))))

    plans = _approved_plans(Path.cwd(), cases)

    assert set(plans) == {case.case_id for case in cases}


def test_ablation_experiment_uses_the_dormant_structured_planner() -> None:
    planner = _planner_for_ablation(
        generator=cast(HcxGenerator, object()),
        validator=cast(LocalPlanValidator, object()),
        registries=RegistryBundle.from_package(),
        model_name="HCX-007",
    )

    assert type(planner) is StructuredOutputPlanner


def test_direct_ablation_accepts_one_hcx_json_fence() -> None:
    answer = _parse_direct_answer(
        '```json\n{"products":[],"values":[],"answer":"조회 결과",'
        '"limitation_present":false}\n```\n설명'
    )

    assert answer.answer == "조회 결과"
    assert not answer.limitation_present


@pytest.mark.asyncio
async def test_ablation_keeps_tokens_when_structured_plan_validation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = load_golden_cases((Path("evaluation/canonical/clarification.jsonl"),))[0]
    plan = _approved_plans(Path.cwd(), (case,))[case.case_id]
    experiment = object.__new__(_Experiment)
    experiment.session = cast(
        RuntimeArtifactSession,
        SimpleNamespace(versions=SimpleNamespace(execution_mode=ExecutionMode.EVALUATION)),
    )
    experiment.planner = _FailingPlanner()
    experiment.generator = cast(_RecordingGenerator, _UsageGenerator())

    async def direct(
        self: _Experiment,
        measured_case: GoldenCase,
        approved_plan: QueryPlan,
        repeat: int,
    ) -> _CaseRun:
        return _CaseRun(
            observation=ObservedCase(latency_ms=(1,)),
            latency_ms=1,
            prompt_tokens=1,
            completion_tokens=1,
        )

    monkeypatch.setattr(_Experiment, "_direct", direct)
    runs = await experiment.run_case(case, plan, 1)

    assert all(run.prompt_tokens == 13 for run in tuple(runs.values())[1:])
    assert all(run.completion_tokens == 8 for run in tuple(runs.values())[1:])


def test_domain_policy_observation_does_not_require_the_evidence_stage() -> None:
    cases = load_golden_cases((Path("evaluation/canonical/clarification.jsonl"),))
    case = cases[0]
    plan = _approved_plans(Path.cwd(), cases)[case.case_id]
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
        warnings=("policy limitation",),
    )

    observed = _policy_observation(case, plan, policy, 12)

    assert observed.limitation_present
    assert observed.latency_ms == (12,)


def test_ablation_measurement_counts_failed_latency_samples() -> None:
    case = load_golden_cases((Path("evaluation/canonical/clarification.jsonl"),))[0]
    failed = _CaseRun(
        observation=ObservedCase(latency_ms=(15_000,)),
        latency_ms=15_000,
        prompt_tokens=10,
        completion_tokens=5,
        error=True,
    )

    measurement = _experiment_measurement(
        AblationVariant.B_CONSTRAINED_PLAN,
        (case,),
        {case.case_id: (failed, failed)},
        {
            "case_checksum": suite_checksum((case,)),
            "code_commit": "a" * 40,
            "artifact_version": "artifact-v1",
            "configuration_sha256": "b" * 64,
            "prompt_version": "prompt-v1",
            "planner_model": "HCX-007",
            "environment": {"python": "3.12"},
        },
    )

    assert measurement.latency.success_count == 0
    assert measurement.latency.failure_count == 2
