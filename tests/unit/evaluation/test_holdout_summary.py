import hashlib
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError
from tools import summarize_blind_holdout as cli

from finproof.core.settings import ExecutionMode
from finproof.evaluation.holdout import (
    HoldoutCandidateIdentity,
    HoldoutManifest,
    HoldoutSummary,
    summarize_holdout,
)
from finproof.evaluation.latency import LatencySample, LatencySummary
from finproof.evaluation.load import LoadReport, LoadSample
from finproof.evaluation.runner import (
    EvaluationMode,
    EvaluationReport,
    PlannerRuntimeMode,
    ReplayMetadata,
)
from finproof.evaluation.scoring import CaseScore, RatioScore

SUITE_SHA256 = "a" * 64
ARTIFACT_SHA256 = "b" * 64
CONFIGURATION_SHA256 = "c" * 64
RESPONSE_VERSION_SHA256 = "d" * 64
CODE_COMMIT = "e" * 40
FAMILY_COUNTS = {
    "cross_metric": 14,
    "holding_sector": 12,
    "missing_zero": 8,
    "unsupported": 8,
    "entity_variant": 6,
}
AGGREGATE_KEYS = (
    "plan_fields",
    "filter_slots",
    "top_k_scope",
    "segment_assignment",
    "compatibility_partitions",
    "assembled_envelope",
    "product_set",
    "product_order",
    "numeric_values",
    "aggregate_values",
    "evidence_coverage",
    "answer_semantics",
    "repeat_stability",
)


def _ratio(*, failures: tuple[str, ...] = ()) -> RatioScore:
    return RatioScore(value=1.0, numerator=1, denominator=1, failures=failures)


def _case_score(case_id: str) -> CaseScore:
    ratio = _ratio()
    return CaseScore.model_validate(
        {
            "case_id": case_id,
            **dict.fromkeys(AGGREGATE_KEYS, ratio),
            "latency": None,
            "failures": (),
        }
    )


def _manifest() -> HoldoutManifest:
    return HoldoutManifest(
        protocol_version="blind-holdout-manifest.v1",
        suite_checksum=SUITE_SHA256,
        case_count=48,
        family_counts=FAMILY_COUNTS,
        curator_identity="independent-blind-curator",
        authoring_version="canonical-question-candidates-v22",
        reference_version="canonical-reference-v1",
        artifact_version=ARTIFACT_SHA256,
        created_at=datetime(2026, 9, 3, tzinfo=UTC),
    )


def _candidate() -> HoldoutCandidateIdentity:
    return HoldoutCandidateIdentity(
        protocol_version="blind-holdout-candidate.v1",
        suite_checksum=SUITE_SHA256,
        code_commit=CODE_COMMIT,
        image_digest=f"sha256:{'f' * 64}",
        artifact_version=ARTIFACT_SHA256,
        configuration_sha256=CONFIGURATION_SHA256,
        prompt_version="phase4-planner-v13",
        answer_prompt_version="phase4-answer-v1",
        answer_schema_sha256="1" * 64,
        planner_version="1.2.0",
        planner_model="HCX-007",
        response_version_sha256=RESPONSE_VERSION_SHA256,
        frozen_at=datetime(2026, 9, 3, 1, tzinfo=UTC),
    )


def _evaluation(*, count: int = 48) -> EvaluationReport:
    aggregates = {key: _ratio() for key in AGGREGATE_KEYS}
    aggregates["answer_semantics"] = _ratio(
        failures=("HOLDOUT-001: secret question and per-case failure",)
    )
    return EvaluationReport(
        replay=ReplayMetadata(
            artifact_version=ARTIFACT_SHA256,
            config_versions={"dataset_version": "2026-08-24"},
            prompt_version="phase4-planner-v13",
            answer_prompt_version="phase4-answer-v1",
            answer_schema_sha256="1" * 64,
            wording_verification_mode="allowlisted-presentation-plus-exact-surface-v1",
            planner_version="1.2.0",
            execution_mode=ExecutionMode.EVALUATION,
            planner_mode=PlannerRuntimeMode.HCX_STRUCTURED_OUTPUTS_VERIFIED_WORDING,
            planner_provider="naver-hyperclova-x",
            planner_model="HCX-007",
            hcx_enabled=True,
            fallback_enabled=False,
            structured_outputs_enabled=True,
            configuration_sha256=CONFIGURATION_SHA256,
            code_commit=CODE_COMMIT,
            environment={"python": "3.12"},
            started_at=datetime(2026, 9, 3, 2, tzinfo=UTC),
            ended_at=datetime(2026, 9, 3, 3, tzinfo=UTC),
            case_checksum=SUITE_SHA256,
            mode=EvaluationMode.END_TO_END,
        ),
        case_scores=tuple(_case_score(f"HOLDOUT-{index:03d}") for index in range(count)),
        aggregates=aggregates,
        latency=LatencySummary.from_milliseconds((10,) * count),
    )


def _load(*, count: int = 48) -> LoadReport:
    samples = tuple(
        LoadSample(
            request_index=index,
            case_id=f"HOLDOUT-{index:03d}",
            question_type="blind",
            status_code=200,
            total_ms=10,
            stage_ms={},
            response_schema_valid=True,
            request_succeeded=True,
            answer_sha256="2" * 64,
            version_sha256=RESPONSE_VERSION_SHA256,
        )
        for index in range(count)
    )
    return LoadReport(
        request_count=count,
        success_count=count,
        failure_count=0,
        latency=LatencySummary.from_milliseconds((10,) * count),
        samples=samples,
    )


def _summarize(
    *,
    manifest: HoldoutManifest | None = None,
    candidate: HoldoutCandidateIdentity | None = None,
    evaluation: EvaluationReport | None = None,
    load: LoadReport | None = None,
) -> HoldoutSummary:
    return summarize_holdout(
        manifest or _manifest(),
        candidate or _candidate(),
        evaluation or _evaluation(),
        load or _load(),
        evaluation_sha256="3" * 64,
        load_sha256="4" * 64,
    )


def test_holdout_summary_has_no_case_level_or_question_material() -> None:
    summary = _summarize()

    serialized = summary.model_dump_json()

    assert "question" not in serialized
    assert "case_scores" not in serialized
    assert "HOLDOUT-" not in serialized
    assert all(not score.failures for score in summary.aggregates.values())
    assert summary.case_count == 48
    assert summary.request_failure_count == 0


@pytest.mark.parametrize(
    "evaluation",
    [
        _evaluation().model_copy(
            update={
                "replay": _evaluation().replay.model_copy(update={"artifact_version": "9" * 64})
            }
        ),
        _evaluation(count=47),
    ],
)
def test_holdout_summary_rejects_artifact_or_count_mismatch(
    evaluation: EvaluationReport,
) -> None:
    with pytest.raises(ValueError, match="holdout identity differs"):
        _summarize(evaluation=evaluation)


def test_holdout_summary_rejects_suite_or_replay_identity_mismatch() -> None:
    replay = _evaluation().replay.model_copy(update={"case_checksum": "9" * 64})

    with pytest.raises(ValueError, match="holdout identity differs"):
        _summarize(evaluation=_evaluation().model_copy(update={"replay": replay}))


def test_holdout_summary_requires_candidate_freeze_before_execution() -> None:
    candidate = _candidate().model_copy(
        update={"frozen_at": datetime(2026, 9, 3, 2, 0, 1, tzinfo=UTC)}
    )

    with pytest.raises(ValueError, match="holdout identity differs"):
        _summarize(candidate=candidate)


def test_holdout_summary_cross_checks_request_counts_against_samples() -> None:
    load = _load()
    samples = list(load.samples)
    samples[0] = samples[0].model_copy(update={"request_succeeded": False})

    with pytest.raises(ValueError, match="holdout identity differs"):
        _summarize(load=load.model_copy(update={"samples": tuple(samples)}))


def test_holdout_summary_rejects_unexpected_latency_stage() -> None:
    load = _load()
    samples = list(load.samples)
    samples[0] = samples[0].model_copy(update={"stage_ms": {"HOLDOUT-001 secret question": 1}})
    latency = LatencySummary.from_samples(
        tuple(
            LatencySample(
                total_ms=sample.total_ms,
                stage_ms=sample.stage_ms,
                succeeded=sample.request_succeeded,
            )
            for sample in samples
        )
    )

    with pytest.raises(ValueError, match="holdout latency differs"):
        _summarize(load=load.model_copy(update={"samples": tuple(samples), "latency": latency}))


def test_holdout_summary_rejects_latency_aggregate_not_rebuilt_from_samples() -> None:
    load = _load()

    with pytest.raises(ValueError, match="holdout latency differs"):
        _summarize(
            load=load.model_copy(update={"latency": load.latency.model_copy(update={"p95_ms": 11})})
        )


@pytest.mark.parametrize("mismatch", ["evaluation_duplicate", "load_duplicate", "load_other"])
def test_holdout_summary_rejects_repeated_or_mismatched_case_ids(mismatch: str) -> None:
    evaluation = _evaluation()
    load = _load()
    if mismatch == "evaluation_duplicate":
        scores = list(evaluation.case_scores)
        scores[-1] = scores[-1].model_copy(update={"case_id": scores[0].case_id})
        evaluation = evaluation.model_copy(update={"case_scores": tuple(scores)})
    else:
        samples = list(load.samples)
        case_id = samples[0].case_id if mismatch == "load_duplicate" else "OTHER-047"
        samples[-1] = samples[-1].model_copy(update={"case_id": case_id})
        load = load.model_copy(update={"samples": tuple(samples)})

    with pytest.raises(ValueError, match="holdout identity differs"):
        _summarize(evaluation=evaluation, load=load)


@pytest.mark.parametrize(
    ("update", "invalidate_schema", "message"),
    [
        ({"request_count": 47}, False, "holdout identity differs"),
        ({}, True, "invalid-schema response"),
    ],
)
def test_holdout_summary_rejects_load_count_or_invalid_schema(
    update: dict[str, int],
    invalidate_schema: bool,
    message: str,
) -> None:
    load = _load().model_copy(update=update)
    if invalidate_schema:
        samples = list(load.samples)
        samples[0] = samples[0].model_copy(
            update={"response_schema_valid": False, "request_succeeded": False}
        )
        load = load.model_copy(update={"samples": tuple(samples)})

    with pytest.raises(ValueError, match=message):
        _summarize(load=load)


@pytest.mark.parametrize("version", [None, "9" * 64])
def test_holdout_summary_requires_one_non_null_candidate_response_version(
    version: str | None,
) -> None:
    load = _load()
    samples = list(load.samples)
    samples[-1] = samples[-1].model_copy(update={"version_sha256": version})

    with pytest.raises(ValueError, match="response version"):
        _summarize(load=load.model_copy(update={"samples": tuple(samples)}))


def test_holdout_summary_accepts_safe_failure_empty_version_surface() -> None:
    load = _load()
    samples = list(load.samples)
    samples[0] = samples[0].model_copy(
        update={
            "request_succeeded": False,
            "version_sha256": hashlib.sha256(b"{}").hexdigest(),
            "error_category": "safe_failure",
        }
    )
    latency = LatencySummary.from_samples(
        tuple(
            LatencySample(
                total_ms=sample.total_ms,
                stage_ms=sample.stage_ms,
                succeeded=sample.request_succeeded,
            )
            for sample in samples
        )
    )
    load = load.model_copy(
        update={
            "success_count": 47,
            "failure_count": 1,
            "latency": latency,
            "samples": tuple(samples),
        }
    )

    summary = _summarize(load=load)

    assert summary.response_version_sha256 == RESPONSE_VERSION_SHA256
    assert summary.request_failure_count == 1


def test_holdout_contracts_reject_wrong_counts_unknown_fields_and_non_utc_times() -> None:
    with pytest.raises(ValidationError):
        HoldoutManifest.model_validate({**_manifest().model_dump(), "case_count": 47})
    with pytest.raises(ValidationError, match="family counts"):
        HoldoutManifest.model_validate(
            {**_manifest().model_dump(), "family_counts": {**FAMILY_COUNTS, "unsupported": 7}}
        )
    with pytest.raises(ValidationError, match="UTC"):
        HoldoutCandidateIdentity.model_validate(
            {
                **_candidate().model_dump(),
                "frozen_at": datetime(2026, 9, 3, tzinfo=timezone(timedelta(hours=9))),
            }
        )
    with pytest.raises(ValidationError):
        HoldoutManifest.model_validate({**_manifest().model_dump(), "questions": []})


def test_holdout_summary_rejects_malformed_hash_or_unknown_aggregate() -> None:
    with pytest.raises(ValidationError):
        summarize_holdout(
            _manifest(),
            _candidate(),
            _evaluation(),
            _load(),
            evaluation_sha256="not-a-hash",
            load_sha256="4" * 64,
        )
    evaluation = _evaluation().model_copy(
        update={"aggregates": {**_evaluation().aggregates, "question_accuracy": _ratio()}}
    )
    with pytest.raises(ValueError, match="aggregate"):
        _summarize(evaluation=evaluation)


def test_cli_hashes_raw_reports_and_atomically_writes_summary(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    candidate_path = tmp_path / "candidate.json"
    evaluation_path = tmp_path / "evaluation.json"
    load_path = tmp_path / "load.json"
    output = tmp_path / "summary.json"
    for path, model in (
        (manifest_path, _manifest()),
        (candidate_path, _candidate()),
        (evaluation_path, _evaluation()),
        (load_path, _load()),
    ):
        path.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")

    assert (
        cli.main(
            [
                "--manifest",
                str(manifest_path),
                "--candidate",
                str(candidate_path),
                "--evaluation-report",
                str(evaluation_path),
                "--load-report",
                str(load_path),
                "--output",
                str(output),
            ]
        )
        == 0
    )

    payload = HoldoutSummary.model_validate_json(output.read_text(encoding="utf-8"))
    assert (
        payload.evaluation_report_sha256 == hashlib.sha256(evaluation_path.read_bytes()).hexdigest()
    )
    assert payload.load_report_sha256 == hashlib.sha256(load_path.read_bytes()).hexdigest()
    assert not output.with_name(f".{output.name}.tmp").exists()
