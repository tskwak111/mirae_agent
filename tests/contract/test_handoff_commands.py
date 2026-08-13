import json
import subprocess
import sys
from pathlib import Path

import pytest

from finproof.cli.main import main

ROOT = Path(__file__).resolve().parents[2]


def test_show_versions_emits_deterministic_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["show-versions"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["dataset_version"] == "2026-07-11"
    assert payload["planner_version"] == "1.0.0"


def test_verify_handoff_runs_real_verifier(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["verify-handoff"]) == 0

    assert "FinProof handoff PASS" in capsys.readouterr().out


def test_audit_source_runs_frozen_check(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["audit-source"]) == 0

    assert "145,393 rows" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("show-versions", "2026-07-11"),
        ("verify-handoff", "FinProof handoff PASS"),
        ("audit-source", "145,393 rows"),
    ],
)
def test_installed_console_entry_point_runs_from_checkout(command: str, expected: str) -> None:
    executable = Path(sys.executable).with_name("finproof")

    completed = subprocess.run(  # noqa: S603
        [str(executable), command],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert expected in completed.stdout
