import subprocess
from pathlib import Path
from shutil import which

from finproof.evaluation.load import reviewed_benchmark_mix


def test_reviewed_benchmark_mix_covers_required_request_shapes() -> None:
    cases = reviewed_benchmark_mix(Path.cwd())

    assert tuple(case.question_type for case in cases) == (
        "simple_rank",
        "heterogeneous_cross_product",
        "zero_missing_policy",
        "unsupported_code_table",
    )
    assert tuple(case.case_id for case in cases) == (
        "ORG-20260824-E-002",
        "ORG-20260824-H-009",
        "ORG-20260824-H-007",
        "ORG-20260824-U-001",
    )
    assert all("2026-07-11" not in case.question for case in cases)


def test_benchmark_shell_entrypoints_are_strict_valid_shell() -> None:
    scripts = (
        Path("scripts/run_ablation.sh"),
        Path("scripts/run_load.sh"),
        Path("scripts/run_soak.sh"),
    )

    assert all(path.is_file() for path in scripts)
    bash = which("bash")
    assert bash is not None
    subprocess.run(  # noqa: S603 -- fixed executable and repository-owned paths
        [bash, "-n", *(str(path) for path in scripts)], check=True
    )


def test_benchmark_runbook_preserves_frozen_runtime_boundaries() -> None:
    runbook = Path("docs/benchmark/README.md").read_text(encoding="utf-8")

    assert "A_DIRECT_HCX" in runbook
    assert "24시간" in runbook
    assert "`GET /answer`" in runbook
    assert "공개 health/readiness/version 경로를 추가하지 않는다" in runbook
    assert "캐시 손상 실험은 N/A" in runbook
