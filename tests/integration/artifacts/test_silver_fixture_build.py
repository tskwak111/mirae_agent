# mypy: disable-error-code="no-untyped-def"
"""Exact held-input orchestration for the one-pass Silver fixture build."""

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest


def _replace_rating(path: Path, *, restore_original: bool) -> None:
    original = path.with_name("rating_scale.original")
    forged = path.with_name("rating_scale.forged")
    os.replace(path, original)
    descriptor = os.open(forged, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, b'version: "1.0.0"\nmissing_tokens: []\nratings: {}\naliases: {}\n')
    finally:
        os.close(descriptor)
    os.replace(forged, path)
    if restore_original:
        os.replace(path, forged)
        os.replace(original, path)


@pytest.mark.parametrize("mutation", ["none", "before-open", "after-parse", "aba"])
def test_silver_builder_opens_rating_only_through_exact_build_input_identity_and_calls_in_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.builder import build_silver_for_session
    from finproof.data.artifacts.config import (
        ArtifactBuildConfig,
        ArtifactBuildOptions,
        ArtifactInputKind,
    )
    from finproof.data.artifacts.errors import ArtifactContractError
    from finproof.data.artifacts.input_identity import BuildInputIdentity
    from finproof.data.artifacts.silver import SilverArtifactEmitter
    from finproof.data.artifacts.staging import ArtifactBuildSession
    from finproof.registry.rating import RatingRegistry
    from tests.helpers.artifacts import artifact_build_input_identity
    from tests.helpers.xlsx import write_complete_bronze_repository

    versions = VersionBundle()
    settings = write_complete_bronze_repository(tmp_path / mutation / "repository")
    identity = artifact_build_input_identity(settings)
    config = ArtifactBuildConfig.load(
        settings.artifact_build_config_path,
        repository_root=settings.repository_root,
        versions=versions,
    )
    options = ArtifactBuildOptions(persistence_timestamp=datetime(2026, 8, 15, tzinfo=UTC))
    rating_path = settings.repository_root / "config/rating_scale.yaml"
    events: list[str] = []
    bronze_result = object()
    silver_result = object()

    real_open = BuildInputIdentity.open_verified_input
    real_parse = cast(Any, RatingRegistry.from_held_stream).__func__

    def open_verified(self: Any, *, kind: Any) -> Any:
        events.append(f"open:{kind.value}")
        return real_open(self, kind=kind)

    def parse_held(cls: Any, stream: Any) -> Any:
        events.append("parse-rating")
        value = real_parse(cls, stream)
        if mutation == "after-parse":
            _replace_rating(rating_path, restore_original=False)
        elif mutation == "aba":
            _replace_rating(rating_path, restore_original=True)
        return value

    class Emitter:
        def finalize(self, *, bronze_result: object):
            assert bronze_result is globals_bronze_result
            events.append("finalize")
            return silver_result

    globals_bronze_result = bronze_result

    def factory(
        cls: Any,
        *,
        session: Any,
        config: Any,
        versions: Any,
        rating_registry: Any,
    ) -> Any:
        del cls
        assert session is active_session
        assert config is globals_config
        assert versions is globals_versions
        assert type(rating_registry) is RatingRegistry
        events.append("emitter-factory")
        return Emitter()

    def ingest(self: Any, *, consumer: Any = None) -> Any:
        assert self is active_session
        assert type(consumer) is Emitter
        events.append("ingest-bronze")
        return bronze_result

    monkeypatch.setattr(BuildInputIdentity, "open_verified_input", open_verified)
    monkeypatch.setattr(RatingRegistry, "from_held_stream", classmethod(parse_held))
    monkeypatch.setattr(SilverArtifactEmitter, "for_session", classmethod(factory))
    monkeypatch.setattr(ArtifactBuildSession, "ingest_bronze", ingest)
    monkeypatch.setattr(
        Path,
        "open",
        lambda *_args, **_kwargs: pytest.fail("path open used"),
    )
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda *_args, **_kwargs: pytest.fail("path read_bytes used"),
    )
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda *_args, **_kwargs: pytest.fail("path read_text used"),
    )
    globals_config = config
    globals_versions = versions

    with ArtifactBuildSession.initialize(
        settings,
        versions,
        options,
        input_identity=identity,
    ) as active_session:
        if mutation == "before-open":
            _replace_rating(rating_path, restore_original=False)
        if mutation == "none":
            assert (
                build_silver_for_session(
                    session=active_session,
                    config=config,
                    versions=versions,
                )
                is silver_result
            )
            assert events == [
                f"open:{ArtifactInputKind.RATING_SCALE_REGISTRY.value}",
                "parse-rating",
                "emitter-factory",
                "ingest-bronze",
                "finalize",
            ]
        else:
            with pytest.raises(ArtifactContractError):
                build_silver_for_session(
                    session=active_session,
                    config=config,
                    versions=versions,
                )
            assert "ingest-bronze" not in events
