from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from finproof.core.settings import ExecutionMode, Settings


def test_settings_use_frozen_evaluation_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings(
        data_dir=tmp_path / "source",
        artifact_dir=tmp_path / "artifacts",
        database_path=tmp_path / "artifacts/finproof.duckdb",
    )

    assert settings.dataset_snapshot_date == date(2026, 7, 11)
    assert settings.execution_mode is ExecutionMode.EVALUATION
    assert settings.default_top_k == 5
    assert settings.max_top_k == 50


def test_settings_reject_default_top_k_above_maximum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValidationError, match="default_top_k"):
        Settings(default_top_k=51, max_top_k=50)


def test_settings_parse_prefixed_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FINPROOF_EXECUTION_MODE", "extended_demo")
    monkeypatch.setenv("FINPROOF_DEFAULT_TOP_K", "7")

    settings = Settings()

    assert settings.execution_mode is ExecutionMode.EXTENDED_DEMO
    assert settings.default_top_k == 7
