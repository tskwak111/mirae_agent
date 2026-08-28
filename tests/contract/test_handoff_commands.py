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
    assert payload["dataset_version"] == "2026-08-24"
    assert payload["planner_version"] == "1.0.0"


def test_verify_handoff_runs_real_verifier(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["verify-handoff"]) == 0

    assert "FinProof handoff PASS" in capsys.readouterr().out


def test_audit_source_runs_frozen_check(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["audit-source"]) == 0

    assert "53,375 rows" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("show-versions", "2026-08-24"),
        ("verify-handoff", "FinProof handoff PASS"),
        ("audit-source", "53,375 rows"),
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


def test_installed_console_rejects_lookalike_checkout(tmp_path: Path) -> None:
    (tmp_path / "source_material").mkdir()
    (tmp_path / "tools").mkdir()
    (tmp_path / "AGENTS.md").write_text("untrusted\n", encoding="utf-8")
    (tmp_path / "source_material/input_manifest.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "tools/__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "tools/verify_handoff.py").write_text(
        "def main():\n    print('untrusted code executed')\n    return 0\n",
        encoding="utf-8",
    )
    executable = Path(sys.executable).with_name("finproof")

    completed = subprocess.run(  # noqa: S603
        [str(executable), "verify-handoff"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "untrusted code executed" not in completed.stdout
    assert "installed FinProof checkout" in completed.stderr


def test_rooted_generators_never_fall_back_to_active_source_paths(tmp_path: Path) -> None:
    from tools.audit_source_data import calculate
    from tools.create_input_manifest import build_manifest
    from tools.extract_schema_catalog import build_catalog

    missing = tmp_path / "missing"

    with pytest.raises(FileNotFoundError):
        build_manifest(data_root=missing)
    with pytest.raises(FileNotFoundError):
        build_catalog(schema_root=missing)
    with pytest.raises(FileNotFoundError):
        calculate(source_root=missing)


def test_rooted_cli_defaults_stay_under_the_explicit_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools import audit_source_data, create_input_manifest, extract_schema_catalog

    active = tmp_path / "active"
    candidate_source = tmp_path / "candidate/source_material"
    candidate_data = candidate_source / "data"
    candidate_data.mkdir(parents=True)
    active.mkdir()
    monkeypatch.setattr(create_input_manifest, "DATA", active)
    monkeypatch.setattr(create_input_manifest, "DEFAULT_OUTPUT", active / "input_manifest.json")
    monkeypatch.setattr(
        create_input_manifest, "build_manifest", lambda *, data_root: {"root": str(data_root)}
    )
    monkeypatch.setattr(extract_schema_catalog, "DATA", active)
    monkeypatch.setattr(extract_schema_catalog, "DEFAULT_OUTPUT", active / "schema_catalog.json")
    monkeypatch.setattr(
        extract_schema_catalog, "build_catalog", lambda *, schema_root: {"root": str(schema_root)}
    )

    assert create_input_manifest.main(["--data-root", str(candidate_data)]) == 0
    assert extract_schema_catalog.main(["--schema-root", str(candidate_data)]) == 0
    assert (candidate_source / "input_manifest.json").is_file()
    assert (candidate_source / "schema_catalog.json").is_file()
    assert tuple(active.iterdir()) == ()

    expected = candidate_source.parent / "tests/contracts/expected_source_audit.json"
    expected.parent.mkdir(parents=True)
    observed = {"total_source_rows": 53_375, "distribution_date": "2026-08-24"}
    expected.write_text(json.dumps(observed), encoding="utf-8")

    def calculate(*, source_root: Path) -> dict[str, object]:
        assert source_root == candidate_source
        return observed

    monkeypatch.setattr(audit_source_data, "calculate", calculate)
    assert audit_source_data.main(["--source-root", str(candidate_source), "--check"]) == 0
