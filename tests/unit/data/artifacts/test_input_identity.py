# mypy: disable-error-code="attr-defined,no-untyped-def"
"""Held build-input generation and ownership contracts."""

import copy
import inspect
import os
import pickle
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


def _build_settings(repository_root: Path):
    from finproof.core.settings import Settings

    source_root = repository_root / "source_material"
    (source_root / "data").mkdir(parents=True)
    (source_root / "input_manifest.json").write_bytes(b"{}")
    (source_root / "schema_catalog.json").write_bytes(b"{}")
    config_root = repository_root / "config"
    config_root.mkdir()
    for name in (
        "artifact_build.yaml",
        "datasets.yaml",
        "quality_rules.yaml",
        "rating_scale.yaml",
        "state_rules.yaml",
    ):
        (config_root / name).write_text("version: 1.0.0\n", encoding="utf-8")
    schema_root = repository_root / "schemas"
    schema_root.mkdir()
    for name in ("artifact_manifest.schema.json", "quality_issue.schema.json"):
        (schema_root / name).write_bytes(b"{}")
    artifact_root = repository_root / "artifacts"
    return Settings(
        repository_root=repository_root,
        source_root=source_root,
        data_dir=source_root / "data",
        artifact_dir=artifact_root,
        database_path=artifact_root / "finproof.duckdb",
        artifact_build_config_path=config_root / "artifact_build.yaml",
        expected_artifact_contract_path=config_root / "expected_phase1_artifacts.json",
    )


def test_held_build_inputs_skeleton_rejects_exact_resolved_bundle_fixture(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.input_identity import (
        BuildInputIdentity,
        HeldVerifiedBuildInputs,
        ResolvedBuildInputBundle,
        verify_build_inputs,
    )

    with pytest.raises(TypeError, match="factory-owned"):
        ResolvedBuildInputBundle()
    with pytest.raises(TypeError, match="verifier-owned"):
        HeldVerifiedBuildInputs()
    with pytest.raises(TypeError, match="verifier-owned"):
        BuildInputIdentity()
    settings = _build_settings(tmp_path)
    resolved = ResolvedBuildInputBundle.from_settings(settings)
    with verify_build_inputs(settings, resolved) as held:
        seal = held.issue_identity_seal()
    BuildInputIdentity.from_verified(seal=seal).close()


@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "copy",
        "deepcopy",
        "subclass",
        "object-new",
        "structural-fake",
        "foreign-settings",
        "foreign-member",
    ],
)
def test_resolved_build_input_bundle_recomputes_every_path_from_trusted_settings_and_rejects_foreign_members(  # noqa: E501
    tmp_path: Path,
    case: str,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.input_identity import (
        BuildInputIdentity,
        ResolvedBuildInputBundle,
        verify_build_inputs,
    )

    settings = _build_settings(tmp_path / "first")
    bundle = ResolvedBuildInputBundle.from_settings(settings)
    assert not hasattr(bundle, "members")
    assert not hasattr(bundle, "owner_token")

    if case == "valid":
        with verify_build_inputs(settings, bundle) as held:
            seal = held.issue_identity_seal()
        BuildInputIdentity.from_verified(seal=seal).close()
        return
    if case == "copy":
        with pytest.raises(TypeError, match="cannot be copied"):
            copy.copy(bundle)
        return
    if case == "deepcopy":
        with pytest.raises(TypeError, match="cannot be copied"):
            copy.deepcopy(bundle)
        return
    if case == "subclass":
        with pytest.raises(TypeError, match="cannot be subclassed"):

            class _Subclass(ResolvedBuildInputBundle):
                pass

        return
    if case == "object-new":
        supplied: object = object.__new__(ResolvedBuildInputBundle)
    elif case == "structural-fake":
        supplied = SimpleNamespace()
    elif case == "foreign-settings":
        foreign_settings = _build_settings(tmp_path / "second")
        supplied = ResolvedBuildInputBundle.from_settings(foreign_settings)
    else:
        foreign = ResolvedBuildInputBundle.from_settings(settings)
        object.__setattr__(bundle, "_members", foreign._members)
        supplied = bundle

    with pytest.raises(ArtifactContractError) as caught:
        verify_build_inputs(settings, supplied)  # type: ignore[arg-type]
    assert caught.value.code is ArtifactErrorCode.CONFIG_INVALID
    assert caught.value.operation_id == "verify-build-inputs"
    assert dict(caught.value.internal_context) == {"reason": "invalid_resolved_bundle"}


@pytest.mark.parametrize(
    "case",
    ["valid", "missing", "symlink", "directory", "hardlink", "fifo"],
)
def test_held_build_inputs_open_exact_nine_nofollow_generations_and_freeze_observed_facts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.input_identity import (
        BuildInputIdentity,
        ResolvedBuildInputBundle,
        verify_build_inputs,
    )

    settings = _build_settings(tmp_path)
    resolved = ResolvedBuildInputBundle.from_settings(settings)
    target = settings.source_root / "input_manifest.json"
    if case == "missing":
        target.unlink()
    elif case == "symlink":
        target.unlink()
        target.symlink_to(settings.source_root / "schema_catalog.json")
    elif case == "directory":
        target.unlink()
        target.mkdir()
    elif case == "hardlink":
        os.link(target, settings.source_root / "input_manifest.alias")
    elif case == "fifo":
        target.unlink()
        os.mkfifo(target)

    real_open = os.open
    leaf_opens: list[tuple[str, int]] = []

    def tracked_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        descriptor = real_open(path, flags, *args, **kwargs)
        if (
            isinstance(path, str)
            and not flags & getattr(os, "O_DIRECTORY", 0)
            and kwargs.get("dir_fd") is not None
        ):
            leaf_opens.append((path, flags))
        return descriptor

    monkeypatch.setattr(os, "open", tracked_open)

    if case == "valid":
        with verify_build_inputs(settings, resolved) as held:
            seal = held.issue_identity_seal()
        BuildInputIdentity.from_verified(seal=seal).close()
        expected_basenames = (
            "input_manifest.json",
            "schema_catalog.json",
            "artifact_build.yaml",
            "datasets.yaml",
            "quality_rules.yaml",
            "rating_scale.yaml",
            "state_rules.yaml",
            "artifact_manifest.schema.json",
            "quality_issue.schema.json",
        )
        assert tuple(path for path, _ in leaf_opens) == expected_basenames
        assert all(flags & getattr(os, "O_NOFOLLOW", 0) for _, flags in leaf_opens)
        return

    with (
        pytest.raises(ArtifactContractError) as caught,
        verify_build_inputs(settings, resolved),
    ):
        raise AssertionError("unsafe input generation entered the context")
    assert caught.value.code is ArtifactErrorCode.CHECKSUM_MISMATCH
    assert caught.value.operation_id == "verify-build-inputs"
    assert dict(caught.value.internal_context) == {"reason": "invalid_input_generation"}


@pytest.mark.parametrize("case", ["replacement", "same-inode-mutation"])
def test_held_build_inputs_reject_replacement_and_same_inode_mutation_before_seal(
    tmp_path: Path,
    case: str,
) -> None:
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.input_identity import (
        ResolvedBuildInputBundle,
        verify_build_inputs,
    )

    settings = _build_settings(tmp_path)
    target = settings.source_root / "input_manifest.json"
    target.write_bytes(b"original")
    resolved = ResolvedBuildInputBundle.from_settings(settings)
    with verify_build_inputs(settings, resolved) as held:
        if case == "replacement":
            replacement = settings.source_root / "replacement.json"
            replacement.write_bytes(b"replaced")
            os.replace(replacement, target)
        else:
            original = target.stat()
            with target.open("r+b") as stream:
                stream.write(b"mutated!")
                stream.flush()
                os.fsync(stream.fileno())
            changed = target.stat()
            assert (changed.st_dev, changed.st_ino, changed.st_size) == (
                original.st_dev,
                original.st_ino,
                original.st_size,
            )

        with pytest.raises(ArtifactContractError) as caught:
            held.issue_identity_seal()
    assert caught.value.code is ArtifactErrorCode.CHECKSUM_MISMATCH
    assert caught.value.operation_id == "verify-build-inputs"
    assert dict(caught.value.internal_context) == {"reason": "invalid_input_generation"}


@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "seal-reuse",
        "seal-copy",
        "seal-object-new",
        "carrier-copy",
        "carrier-subclass",
        "carrier-object-new",
        "carrier-pickle",
        "open-and-close",
        "tuple-bindings",
        "stale-tuple",
        "structural-fake",
    ],
)
def test_build_input_identity_consumes_only_one_use_held_seal_owns_revalidation_and_rejects_stale_tuple(  # noqa: E501
    tmp_path: Path,
    case: str,
) -> None:
    from finproof.data.artifacts.config import ArtifactInputKind
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
    from finproof.data.artifacts.input_identity import (
        BuildInputIdentity,
        ResolvedBuildInputBundle,
        verify_build_inputs,
    )
    from finproof.data.artifacts.manifest import (
        BuildInputIdentityView,
        _consume_build_input_manifest_seal,
    )

    settings = _build_settings(tmp_path)
    target = settings.source_root / "input_manifest.json"
    target.write_bytes(b"source-generation")
    resolved = ResolvedBuildInputBundle.from_settings(settings)
    with verify_build_inputs(settings, resolved) as held:
        seal = held.issue_identity_seal()
    identity = BuildInputIdentity.from_verified(seal=seal)
    try:
        assert tuple(inspect.signature(BuildInputIdentity.from_verified).parameters) == ("seal",)
        if case == "valid":
            identity.assert_unchanged()
            assert isinstance(identity, BuildInputIdentityView)
            manifest_seal = identity.take_manifest_identity_seal()
            _consume_build_input_manifest_seal(manifest_seal, identity)
            return
        if case == "seal-reuse":
            with pytest.raises(ArtifactContractError):
                BuildInputIdentity.from_verified(seal=seal)
            return
        if case == "seal-copy":
            with pytest.raises(TypeError, match="cannot be copied"):
                copy.copy(seal)
            return
        if case == "seal-object-new":
            supplied_seal = object.__new__(type(seal))
            with pytest.raises(ArtifactContractError):
                BuildInputIdentity.from_verified(seal=supplied_seal)
            return
        if case == "carrier-copy":
            with pytest.raises(TypeError, match="cannot be copied"):
                copy.copy(identity)
            return
        if case == "carrier-subclass":
            with pytest.raises(TypeError, match="cannot be subclassed"):

                class _Subclass(BuildInputIdentity):
                    pass

            return
        if case == "carrier-object-new":
            forged = object.__new__(BuildInputIdentity)
            with pytest.raises(ArtifactContractError):
                forged.assert_unchanged()
            return
        if case == "carrier-pickle":
            with pytest.raises(TypeError, match="cannot be copied"):
                pickle.dumps(identity)
            return
        if case == "open-and-close":
            with identity.open_verified_input(kind=ArtifactInputKind.SOURCE_MANIFEST) as stream:
                assert stream.read() == b"source-generation"
            identity.assert_unchanged()
            identity.close()
            with pytest.raises(ArtifactContractError) as caught:
                identity.assert_unchanged()
            assert caught.value.code is ArtifactErrorCode.CHECKSUM_MISMATCH
            return
        if case == "tuple-bindings":
            assert len(identity.logical_inputs) == 9
            assert identity.source_manifest_sha256 == identity.logical_inputs[0].sha256
            assert identity.schema_catalog_sha256 == identity.logical_inputs[1].sha256
            assert identity.logical_inputs[0].size_bytes == len(b"source-generation")
            return
        if case == "stale-tuple":
            stale = tuple(
                entry.model_copy(update={"sha256": "0" * 64}) if index == 0 else entry
                for index, entry in enumerate(identity.logical_inputs)
            )
            assert all(
                "logical_inputs" not in parameter.name
                for parameter in inspect.signature(
                    BuildInputIdentity.from_verified
                ).parameters.values()
            )
            with pytest.raises(TypeError):
                BuildInputIdentity.from_verified(  # type: ignore[call-arg]
                    seal=object(), logical_inputs=stale
                )
            return

        class _StructuralFake:
            logical_inputs = identity.logical_inputs
            source_manifest_sha256 = identity.source_manifest_sha256
            schema_catalog_sha256 = identity.schema_catalog_sha256

            def assert_unchanged(self) -> None:
                return None

            def take_manifest_identity_seal(self) -> object:
                return object()

        fake = _StructuralFake()
        assert isinstance(fake, BuildInputIdentityView)
        with pytest.raises(ArtifactContractError):
            _consume_build_input_manifest_seal(fake.take_manifest_identity_seal(), fake)
        manifest_seal = identity.take_manifest_identity_seal()
        _consume_build_input_manifest_seal(manifest_seal, identity)
    finally:
        identity.close()
