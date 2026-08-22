from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from finproof.core.settings import Settings


def test_hcx_settings_fail_closed_and_redact_the_api_key(tmp_path: Path) -> None:
    disabled = Settings(repository_root=tmp_path, hcx_enabled=False)
    assert disabled.hcx_api_key is None

    with pytest.raises(ValidationError, match="API key"):
        Settings(repository_root=tmp_path, hcx_enabled=True)

    enabled = Settings(
        repository_root=tmp_path,
        hcx_enabled=True,
        hcx_api_key=SecretStr("secret"),
        hcx_model_name="HCX-007",
    )
    assert "secret" not in repr(enabled)


def test_hcx_settings_reject_non_hcx_model_names(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="HCX-"):
        Settings(repository_root=tmp_path, hcx_model_name="other-model")


def test_hcx_settings_expose_no_provider_origin_or_structured_toggle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FINPROOF_HCX_BASE_URL", "https://example.invalid")
    monkeypatch.setenv("FINPROOF_HCX_STRUCTURED_ENABLED", "true")

    settings = Settings(repository_root=tmp_path)

    assert not hasattr(settings, "hcx_base_url")
    assert not hasattr(settings, "hcx_structured_enabled")
