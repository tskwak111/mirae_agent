"""Focused Phase 2 expected-verified runtime-session tests."""

import copy
import inspect
from pathlib import Path

import pytest
from tests.helpers.query_runtime import verified_artifacts

from finproof.data.artifacts.manifest import ArtifactManifest, VerifiedArtifactSet
from finproof.registry.loader import RegistryBundle


def test_version_bundle_has_no_defaults_and_is_issued_from_verified_runtime_facts() -> None:
    """Only exact verified artifacts and loader-issued registries create runtime versions."""
    from finproof.core.settings import ExecutionMode
    from finproof.core.versions import VersionBundle
    from finproof.registry.loader import RegistryBundle

    registries = RegistryBundle.from_package()
    verified = verified_artifacts()
    signature = inspect.signature(VersionBundle.from_runtime)
    assert all(
        parameter.default is inspect.Parameter.empty
        for name, parameter in signature.parameters.items()
        if name not in {"cls"}
    )

    versions = VersionBundle.from_runtime(
        verified=verified,
        registries=registries,
        execution_mode=ExecutionMode.EVALUATION,
    )
    assert versions.runtime_facts() == {
        "dataset_version": "2026-07-11",
        "artifact_manifest_hash": verified.overall_manifest_logical_hash,
        "dataset_registry_version": "1.0.0",
        "field_registry_version": "1.1.0",
        "metric_registry_version": "1.0.0",
        "state_rule_version": "1.1.0",
        "quality_rule_version": "1.0.0",
        "rating_rule_version": "1.0.0",
        "answer_policy_version": "1.0.0",
        "planner_version": "1.0.0",
        "execution_mode": "evaluation",
    }
    versions.require_runtime(verified=verified, registries=registries)

    with pytest.raises(TypeError):
        VersionBundle().require_runtime(verified=verified, registries=registries)
    with pytest.raises(TypeError):
        VersionBundle.from_runtime(
            verified=verified,
            registries=copy.copy(registries),
            execution_mode=ExecutionMode.EVALUATION,
        )


def test_runtime_session_expected_verifies_before_declared_database_open_and_closes_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Composition verifies expected identity before opening and owns one close."""
    from tests.helpers.artifacts import artifact_staging_settings, manifest_payload

    import finproof.runtime.session as runtime_module
    from finproof.runtime.session import open_runtime_artifact_session

    settings = artifact_staging_settings(tmp_path / "repository")
    settings.artifact_dir.mkdir()
    manifest = ArtifactManifest.model_validate(manifest_payload(), strict=True)
    verified = verified_artifacts()
    registries = RegistryBundle.from_package()
    events: list[str] = []

    class Connection:
        def close(self) -> None:
            events.append("close")

    def load(path: Path) -> ArtifactManifest:
        assert path == settings.artifact_dir / "manifest.json"
        events.append("load")
        return manifest

    def verify(self: ArtifactManifest, root: Path) -> VerifiedArtifactSet:
        assert self is manifest
        assert root == settings.artifact_dir
        events.append("verify")
        return verified

    def load_registries() -> RegistryBundle:
        events.append("registries")
        return registries

    def open_database(path: Path) -> Connection:
        assert events == ["load", "verify", "registries"]
        assert path == settings.artifact_dir / manifest.database_path
        events.append("open")
        return Connection()

    monkeypatch.setattr(ArtifactManifest, "load", staticmethod(load))
    monkeypatch.setattr(ArtifactManifest, "verify", verify)
    monkeypatch.setattr(RegistryBundle, "from_package", staticmethod(load_registries))
    monkeypatch.setattr(runtime_module, "open_read_only_database", open_database)

    def consume() -> None:
        with open_runtime_artifact_session(settings) as session:
            session.assert_live()
            assert session.verified_artifacts is verified
            assert session.registries is registries
            raise RuntimeError("consumer")

    with pytest.raises(RuntimeError, match="consumer"):
        consume()
    assert events == ["load", "verify", "registries", "open", "close"]


def test_runtime_session_rejects_foreign_registry_result_and_exposes_no_path_connection_or_sql(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runtime capability neither accepts copied registries nor leaks storage handles."""
    from tests.helpers.artifacts import artifact_staging_settings, manifest_payload

    import finproof.runtime.session as runtime_module
    from finproof.runtime.session import RuntimeArtifactSession, open_runtime_artifact_session

    public_names = {name for name in dir(RuntimeArtifactSession) if not name.startswith("_")}
    assert public_names == {"assert_live", "registries", "verified_artifacts", "versions"}
    assert not public_names & {"connection", "cursor", "database_path", "execute", "path", "sql"}

    settings = artifact_staging_settings(tmp_path / "repository")
    settings.artifact_dir.mkdir()
    manifest = ArtifactManifest.model_validate(manifest_payload(), strict=True)
    registries = copy.copy(RegistryBundle.from_package())
    opened = False

    monkeypatch.setattr(ArtifactManifest, "load", staticmethod(lambda _path: manifest))
    monkeypatch.setattr(ArtifactManifest, "verify", lambda _self, _root: verified_artifacts())
    monkeypatch.setattr(RegistryBundle, "from_package", staticmethod(lambda: registries))

    def open_database(_path: Path) -> None:
        nonlocal opened
        opened = True
        pytest.fail("foreign registry result reached database open")

    monkeypatch.setattr(runtime_module, "open_read_only_database", open_database)

    def open_foreign() -> None:
        with open_runtime_artifact_session(settings):
            pytest.fail("foreign registry result issued a runtime session")

    with pytest.raises(TypeError, match="loader-issued"):
        open_foreign()
    assert opened is False
