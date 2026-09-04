"""Release-candidate competition and evidence-report checks."""

import json
import shutil
from pathlib import Path

from tools.check_claim_evidence_report import validate_report
from tools.check_competition_compliance import check_repository

ROOT = Path(__file__).parents[2]
REPORT = ROOT / "artifacts/evaluation/organizer-20260824.json"


def test_repository_satisfies_competition_runtime_contract() -> None:
    assert check_repository(ROOT) == []


def test_compliance_rejects_extended_demo_as_the_default_runtime(tmp_path: Path) -> None:
    candidate = tmp_path / "repository"
    shutil.copytree(ROOT / "src", candidate / "src")
    (candidate / "schemas").mkdir()
    shutil.copy2(ROOT / "schemas/api_response.schema.json", candidate / "schemas")
    for relative in ("pyproject.toml", "Dockerfile", ".dockerignore"):
        shutil.copy2(ROOT / relative, candidate / relative)
    settings = candidate / "src/finproof/core/settings.py"
    settings.write_text(
        settings.read_text(encoding="utf-8").replace(
            "execution_mode: ExecutionMode = ExecutionMode.EVALUATION",
            "execution_mode: ExecutionMode = ExecutionMode.EXTENDED_DEMO",
        ),
        encoding="utf-8",
    )

    assert "evaluation must be the default runtime mode" in check_repository(candidate)


def test_organizer_report_has_complete_claim_evidence_coverage() -> None:
    assert validate_report(REPORT) == []


def test_claim_evidence_check_rejects_lost_coverage(tmp_path: Path) -> None:
    payload = json.loads(REPORT.read_bytes())
    payload["aggregates"]["evidence_coverage"]["numerator"] -= 1
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(payload), encoding="utf-8")

    assert "aggregate evidence_coverage is incomplete" in validate_report(broken)


def test_claim_evidence_check_accepts_complete_blind_development_inventory(
    tmp_path: Path,
) -> None:
    payload = json.loads(REPORT.read_bytes())
    template = payload["case_scores"][0]
    payload["case_scores"] = [
        {
            **json.loads(json.dumps(template)),
            "case_id": f"CQ-{batch:03d}-{index:03d}",
        }
        for batch in range(12, 18)
        for index in range(1, 25)
    ]
    payload["latency"].update(count=144, success_count=144, failure_count=0)
    report = tmp_path / "blind-development.json"
    report.write_text(json.dumps(payload), encoding="utf-8")

    assert validate_report(report) == []
