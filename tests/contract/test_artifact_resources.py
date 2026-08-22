"""Artifact schema packaging and runtime-loading contracts."""

import hashlib
import os
import shutil
import subprocess
import tomllib
import zipfile
from enum import StrEnum
from importlib import metadata as importlib_metadata
from importlib import resources as importlib_resources
from pathlib import Path
from typing import Self

import pytest

ROOT = Path(__file__).parents[2]
_UV_EXECUTABLE = shutil.which("uv")
if _UV_EXECUTABLE is None:
    raise RuntimeError("uv executable is required for resource contract tests")
UV: str = _UV_EXECUTABLE
_SCHEMA_DESTINATIONS = {
    "finproof/resources/schemas/artifact_manifest.schema.json": ROOT
    / "schemas/artifact_manifest.schema.json",
    "finproof/resources/schemas/quality_issue.schema.json": ROOT
    / "schemas/quality_issue.schema.json",
}
_EXPECTED_CONTRACT_SOURCE = ROOT / "config/expected_phase1_artifacts.json"


class _MemoryTraversable:
    def __init__(
        self,
        files: dict[tuple[str, ...], bytes],
        directories: set[tuple[str, ...]] | None = None,
        parts: tuple[str, ...] = (),
    ) -> None:
        self._files = files
        self._directories = directories or set()
        self._parts = parts

    @property
    def name(self) -> str:
        return self._parts[-1] if self._parts else "finproof"

    def joinpath(self, *descendants: str) -> Self:
        return type(self)(
            self._files,
            self._directories,
            self._parts + tuple(descendants),
        )

    def is_file(self) -> bool:
        return self._parts in self._files

    def is_dir(self) -> bool:
        return self._parts in self._directories

    def read_bytes(self) -> bytes:
        try:
            return self._files[self._parts]
        except KeyError as exc:
            raise FileNotFoundError(self.name) from exc


class _ForgedRuntimeArtifactResource(StrEnum):
    ARTIFACT_MANIFEST_SCHEMA = "finproof/resources/schemas/artifact_manifest.schema.json"


class _ForgedResourceObject:
    value = "finproof/resources/schemas/artifact_manifest.schema.json"


class _SyntheticDistribution:
    def __init__(self, root: Path) -> None:
        self._root = root
        self.requested: list[str] = []

    def locate_file(self, path: str) -> Path:
        self.requested.append(path)
        return self._root / path


class _RedirectedDistribution(_SyntheticDistribution):
    def __init__(self, root: Path, redirected: Path) -> None:
        super().__init__(root)
        self._redirected = redirected

    def locate_file(self, path: str) -> Path:
        self.requested.append(path)
        if path == "":
            return self._root
        return self._redirected


class _CandidateProbe:
    def __init__(self, source: bool, resource: bool) -> None:
        self._source = source
        self._resource = resource
        self.second_checks = 0

    def source_exists(self) -> bool:
        return self._source

    def resource_exists(self) -> bool:
        return self._resource

    def second_check(self) -> None:
        self.second_checks += 1


def test_built_wheel_archive_contains_exact_schema_sources(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "wheel"
    subprocess.run(  # noqa: S603
        [UV, "build", "--wheel", "--out-dir", str(wheel_dir)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(wheel_dir.glob("*.whl"))

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        for destination, source in _SCHEMA_DESTINATIONS.items():
            source_bytes = source.read_bytes()
            packaged_bytes = archive.read(destination)
            assert destination in names
            assert packaged_bytes == source_bytes
            assert (
                hashlib.sha256(packaged_bytes).hexdigest()
                == hashlib.sha256(source_bytes).hexdigest()
            )
        expected_destination = "finproof/resources/contracts/expected_phase1_artifacts.json"
        assert archive.read(expected_destination) == _EXPECTED_CONTRACT_SOURCE.read_bytes()
        assert all("build_candidate_artifacts" not in name for name in names)


def test_source_resource_anchor_exists_without_expected_contract() -> None:
    import finproof.resources

    anchor = Path(finproof.resources.__file__)
    assert anchor == ROOT / "src/finproof/resources/__init__.py"
    assert not (anchor.parent / "contracts/expected_phase1_artifacts.json").exists()


def test_primary_schema_loader_reads_generic_traversable_and_reports_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.data.artifacts import resources
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    files: dict[tuple[str, ...], bytes] = {
        ("resources", "schemas", "artifact_manifest.schema.json"): b"manifest",
        ("resources", "schemas", "quality_issue.schema.json"): b"quality",
    }
    monkeypatch.setattr(
        importlib_resources,
        "files",
        lambda _package: _MemoryTraversable(files),
    )
    monkeypatch.setattr(
        importlib_metadata,
        "distribution",
        lambda _name: pytest.fail("primary unit touched metadata fallback"),
    )

    assert resources.artifact_manifest_schema_bytes() == b"manifest"
    assert resources.quality_issue_schema_bytes() == b"quality"

    monkeypatch.setattr(
        importlib_resources,
        "files",
        lambda _package: _MemoryTraversable({}),
    )
    with pytest.raises(ArtifactContractError) as caught:
        resources._primary_read(resources.RuntimeArtifactResource.ARTIFACT_MANIFEST_SCHEMA)
    assert caught.value.code is ArtifactErrorCode.SCHEMA_INVALID


def test_primary_schema_loader_rejects_generic_traversable_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.data.artifacts import resources
    from finproof.data.artifacts.errors import ArtifactContractError

    directory = ("resources", "schemas", "artifact_manifest.schema.json")
    monkeypatch.setattr(
        importlib_resources,
        "files",
        lambda _package: _MemoryTraversable({}, {directory}),
    )

    with pytest.raises(ArtifactContractError) as caught:
        resources.artifact_manifest_schema_bytes()
    assert caught.value.internal_context == {"reason": "invalid_primary_resource"}


@pytest.mark.parametrize(
    "forged_resource",
    [_ForgedRuntimeArtifactResource.ARTIFACT_MANIFEST_SCHEMA, _ForgedResourceObject()],
    ids=["forged-enum", "forged-object"],
)
@pytest.mark.parametrize(
    "operation",
    ["primary-read", "primary-exists", "editable-read", "editable-exists"],
)
def test_resource_adapters_reject_forged_resource_before_access(
    monkeypatch: pytest.MonkeyPatch,
    forged_resource: object,
    operation: str,
) -> None:
    from finproof.data.artifacts import resources
    from finproof.data.artifacts.errors import ArtifactContractError

    accessed = False

    def unexpected_files(_package: str) -> _MemoryTraversable:
        nonlocal accessed
        accessed = True
        return _MemoryTraversable({})

    monkeypatch.setattr(importlib_resources, "files", unexpected_files)

    def invoke_operation() -> object:
        if operation == "primary-read":
            return resources._primary_read(forged_resource)  # type: ignore[arg-type]
        if operation == "primary-exists":
            return resources._primary_exists(forged_resource)  # type: ignore[arg-type]
        if operation == "editable-read":
            return resources._editable_read(forged_resource)  # type: ignore[arg-type]
        return resources._editable_exists(forged_resource)  # type: ignore[arg-type]

    with pytest.raises(ArtifactContractError) as caught:
        invoke_operation()

    assert caught.value.internal_context == {"reason": "invalid_runtime_resource"}
    assert accessed is False


@pytest.mark.parametrize(
    ("resource_name", "payload"),
    [("ARTIFACT_MANIFEST_SCHEMA", b"manifest"), ("QUALITY_ISSUE_SCHEMA", b"quality")],
)
def test_private_editable_adapter_reads_exact_valid_distribution_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    resource_name: str,
    payload: bytes,
) -> None:
    from finproof.data.artifacts import resources

    resource = getattr(resources.RuntimeArtifactResource, resource_name)
    destination = tmp_path / resource.value
    destination.parent.mkdir(parents=True)
    destination.write_bytes(payload)
    distribution = _SyntheticDistribution(tmp_path)
    monkeypatch.setattr(importlib_metadata, "distribution", lambda _name: distribution)

    assert resources._editable_exists(resource) is True
    assert resources._editable_read(resource) == payload
    assert distribution.requested == ["", resource.value, "", resource.value]


@pytest.mark.parametrize(
    "unsafe_shape",
    ["leaf-symlink", "intermediate-symlink", "special-file-as-missing"],
)
def test_filesystem_primary_adapter_rejects_unsafe_static_shapes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsafe_shape: str,
) -> None:
    from finproof.data.artifacts import resources
    from finproof.data.artifacts.errors import ArtifactContractError

    package_root = tmp_path / "package" / "finproof"
    candidate = package_root / "resources/schemas/artifact_manifest.schema.json"
    external_root = tmp_path / "external"
    external_file = external_root / "leaf.json"
    external_nested = external_root / "schemas/artifact_manifest.schema.json"
    external_nested.parent.mkdir(parents=True)
    external_file.write_bytes(b"external")
    external_nested.write_bytes(b"external")

    if unsafe_shape == "leaf-symlink":
        candidate.parent.mkdir(parents=True)
        candidate.symlink_to(external_file)
    elif unsafe_shape == "intermediate-symlink":
        package_root.mkdir(parents=True)
        (package_root / "resources").symlink_to(external_root)
    else:
        candidate.parent.mkdir(parents=True)
        os.mkfifo(candidate)

    monkeypatch.setattr(importlib_resources, "files", lambda _package: package_root)

    resource = resources.RuntimeArtifactResource.ARTIFACT_MANIFEST_SCHEMA
    operation = (
        resources._primary_exists
        if unsafe_shape == "special-file-as-missing"
        else resources._primary_read
    )
    with pytest.raises(ArtifactContractError) as caught:
        operation(resource)
    assert caught.value.internal_context == {"reason": "invalid_primary_resource"}


@pytest.mark.parametrize(
    "unsafe_shape",
    [
        "wrong-destination",
        "leaf-symlink",
        "intermediate-symlink",
        "directory",
        "special-file",
    ],
)
def test_editable_adapter_rejects_unsafe_static_shapes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsafe_shape: str,
) -> None:
    from finproof.data.artifacts import resources
    from finproof.data.artifacts.errors import ArtifactContractError

    resource = resources.RuntimeArtifactResource.ARTIFACT_MANIFEST_SCHEMA
    distribution_root = tmp_path / "distribution"
    candidate = distribution_root / resource.value
    external_root = tmp_path / "external"
    external_file = external_root / "leaf.json"
    external_nested = external_root / "schemas/artifact_manifest.schema.json"
    external_nested.parent.mkdir(parents=True)
    external_file.write_bytes(b"external")
    external_nested.write_bytes(b"external")
    distribution: _SyntheticDistribution

    if unsafe_shape == "wrong-destination":
        distribution = _RedirectedDistribution(distribution_root, external_file)
    else:
        distribution = _SyntheticDistribution(distribution_root)
        if unsafe_shape == "leaf-symlink":
            candidate.parent.mkdir(parents=True)
            candidate.symlink_to(external_file)
        elif unsafe_shape == "intermediate-symlink":
            (distribution_root / "finproof").mkdir(parents=True)
            (distribution_root / "finproof/resources").symlink_to(external_root)
        elif unsafe_shape == "directory":
            candidate.mkdir(parents=True)
        else:
            candidate.parent.mkdir(parents=True)
            os.mkfifo(candidate)

    monkeypatch.setattr(importlib_metadata, "distribution", lambda _name: distribution)

    operation = (
        resources._editable_exists
        if unsafe_shape in {"directory", "special-file"}
        else resources._editable_read
    )
    with pytest.raises(ArtifactContractError) as caught:
        operation(resource)
    assert caught.value.internal_context == {"reason": "invalid_editable_resource"}


def test_editable_adapter_reports_missing_leaf_as_typed_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.data.artifacts import resources
    from finproof.data.artifacts.errors import ArtifactContractError

    distribution = _SyntheticDistribution(tmp_path / "distribution")
    missing_leaf = (
        tmp_path / "distribution/finproof/resources/schemas/artifact_manifest.schema.json"
    )
    missing_leaf.parent.mkdir(parents=True)
    monkeypatch.setattr(importlib_metadata, "distribution", lambda _name: distribution)

    with pytest.raises(ArtifactContractError) as caught:
        resources._editable_read(resources.RuntimeArtifactResource.ARTIFACT_MANIFEST_SCHEMA)
    assert caught.value.internal_context == {"reason": "missing_editable_resource"}


@pytest.mark.parametrize("adapter", ["primary", "editable"])
def test_filesystem_resource_adapters_reject_atomic_parent_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    adapter: str,
) -> None:
    from finproof.data.artifacts import resources
    from finproof.data.artifacts.errors import ArtifactContractError

    resource = resources.RuntimeArtifactResource.ARTIFACT_MANIFEST_SCHEMA
    if adapter == "primary":
        root = tmp_path / "package" / "finproof"
        candidate = root / "resources/schemas/artifact_manifest.schema.json"
        swapped_parent = root / "resources"
        swap_component = "resources"
        monkeypatch.setattr(importlib_resources, "files", lambda _package: root)
    else:
        root = tmp_path / "distribution"
        candidate = root / resource.value
        swapped_parent = root / "finproof"
        swap_component = "finproof"
        distribution = _SyntheticDistribution(root)
        monkeypatch.setattr(importlib_metadata, "distribution", lambda _name: distribution)

    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"trusted")
    held_parent = swapped_parent.with_name(f"{swapped_parent.name}-held")
    swapped = False
    real_os_open = os.open
    real_os_stat = os.stat

    def swap_parent_once() -> None:
        nonlocal swapped
        if swapped:
            return
        swapped = True
        swapped_parent.rename(held_parent)
        replacement = root.joinpath(*resource.value.split("/")[:-1])
        if adapter == "primary":
            replacement = root.joinpath(*resource.value.removeprefix("finproof/").split("/")[:-1])
        replacement.mkdir(parents=True)
        (replacement / "artifact_manifest.schema.json").write_bytes(b"external")

    def racing_os_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if dir_fd is None and isinstance(path, (str, Path)) and Path(path) == candidate:
            swap_parent_once()
        return real_os_open(path, flags, mode, dir_fd=dir_fd)

    def racing_os_stat(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *,
        dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> os.stat_result:
        result = real_os_stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)
        if dir_fd is not None and path == swap_component:
            swap_parent_once()
        return result

    monkeypatch.setattr(os, "open", racing_os_open)
    monkeypatch.setattr(os, "stat", racing_os_stat)

    operation = resources._primary_read if adapter == "primary" else resources._editable_read
    with pytest.raises(ArtifactContractError) as caught:
        operation(resource)
    assert caught.value.internal_context == {"reason": f"invalid_{adapter}_resource"}


@pytest.mark.parametrize(
    "case",
    [
        "primary-leaf-removed-after-lookup",
        "primary-parent-replaced-after-lookup",
        "generic-primary-directory-exists",
        "editable-read-leaf-removed-after-lookup",
        "editable-exists-leaf-removed-after-lookup",
    ],
)
def test_resource_adapters_never_downgrade_invalid_or_racy_paths_to_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    from finproof.data.artifacts import resources
    from finproof.data.artifacts.errors import ArtifactContractError

    resource = resources.RuntimeArtifactResource.ARTIFACT_MANIFEST_SCHEMA
    if case == "generic-primary-directory-exists":
        directory = ("resources", "schemas", "artifact_manifest.schema.json")
        monkeypatch.setattr(
            importlib_resources,
            "files",
            lambda _package: _MemoryTraversable({}, {directory}),
        )
        with pytest.raises(ArtifactContractError) as caught:
            resources._primary_exists(resource)
        assert caught.value.internal_context == {"reason": "invalid_primary_resource"}
        return

    fallback_calls = 0
    if case.startswith("primary"):
        root = tmp_path / "package/finproof"
        candidate = root / "resources/schemas/artifact_manifest.schema.json"
        monkeypatch.setattr(importlib_resources, "files", lambda _package: root)

        def editable_fallback(_resource: object) -> bytes:
            nonlocal fallback_calls
            fallback_calls += 1
            return b"fallback"

        monkeypatch.setattr(resources, "_editable_read", editable_fallback)
        invalid_reason = "invalid_primary_resource"
    else:
        root = tmp_path / "distribution"
        candidate = root / resource.value
        distribution = _SyntheticDistribution(root)
        monkeypatch.setattr(importlib_metadata, "distribution", lambda _name: distribution)
        invalid_reason = "invalid_editable_resource"

    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"trusted")
    raced = False
    real_os_stat = os.stat

    def racing_os_stat(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *,
        dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> os.stat_result:
        nonlocal raced
        result = real_os_stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)
        should_replace_parent = (
            case == "primary-parent-replaced-after-lookup" and path == "resources"
        )
        should_remove_leaf = (
            case != "primary-parent-replaced-after-lookup"
            and path == "artifact_manifest.schema.json"
        )
        if dir_fd is not None and not raced and (should_replace_parent or should_remove_leaf):
            raced = True
            if should_replace_parent:
                parent = root / "resources"
                parent.rename(root / "resources-held")
                parent.mkdir()
            else:
                candidate.unlink()
        return result

    monkeypatch.setattr("finproof.data.artifacts.safe_files.os.stat", racing_os_stat)

    def invoke_operation() -> object:
        if case.startswith("primary"):
            return resources._resource_bytes(resource)
        if "-read-" in case:
            return resources._editable_read(resource)
        return resources._editable_exists(resource)

    with pytest.raises(ArtifactContractError) as caught:
        invoke_operation()
    assert caught.value.internal_context == {"reason": invalid_reason}
    assert fallback_calls == 0


@pytest.mark.parametrize("operation", ["primary", "editable-read", "editable-exists"])
def test_resource_adapters_reject_missing_leaf_after_ancestor_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    from finproof.data.artifacts import resources
    from finproof.data.artifacts.errors import ArtifactContractError

    resource = resources.RuntimeArtifactResource.ARTIFACT_MANIFEST_SCHEMA
    fallback_calls = 0
    if operation == "primary":
        root = tmp_path / "package/finproof"
        candidate = root / "resources/schemas/artifact_manifest.schema.json"
        monkeypatch.setattr(importlib_resources, "files", lambda _package: root)

        def editable_fallback(_resource: object) -> bytes:
            nonlocal fallback_calls
            fallback_calls += 1
            return b"fallback"

        monkeypatch.setattr(resources, "_editable_read", editable_fallback)
        invalid_reason = "invalid_primary_resource"
    else:
        root = tmp_path / "distribution"
        candidate = root / resource.value
        distribution = _SyntheticDistribution(root)
        monkeypatch.setattr(importlib_metadata, "distribution", lambda _name: distribution)
        invalid_reason = "invalid_editable_resource"

    candidate.parent.mkdir(parents=True)
    resources_parent = candidate.parent.parent
    swapped = False
    real_os_stat = os.stat

    def racing_os_stat(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *,
        dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> os.stat_result:
        nonlocal swapped
        if dir_fd is not None and not swapped and path == "artifact_manifest.schema.json":
            swapped = True
            resources_parent.rename(resources_parent.with_name("resources-held"))
            resources_parent.mkdir()
            (resources_parent / "schemas").mkdir()
        return real_os_stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)

    monkeypatch.setattr("finproof.data.artifacts.safe_files.os.stat", racing_os_stat)

    def invoke_operation() -> object:
        if operation == "primary":
            return resources._resource_bytes(resource)
        if operation == "editable-read":
            return resources._editable_read(resource)
        return resources._editable_exists(resource)

    with pytest.raises(ArtifactContractError) as caught:
        invoke_operation()
    assert swapped
    assert caught.value.internal_context == {"reason": invalid_reason}
    assert fallback_calls == 0


@pytest.mark.parametrize(
    "requirement",
    [
        "jsonschema>=4.26,<5",
        "rfc3339-validator>=0.1.4,<0.2",
        "pyarrow>=21,<24",
    ],
)
def test_artifact_runtime_dependencies_are_owned_by_project_metadata(
    requirement: str,
) -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    runtime = metadata["project"]["dependencies"]
    development = metadata["dependency-groups"]["dev"]
    package_name = requirement.split(">=", maxsplit=1)[0]

    assert requirement in runtime
    assert not any(
        dependency.split(">=", maxsplit=1)[0] == package_name for dependency in development
    )


def test_runtime_schema_resources_equal_repository_bytes() -> None:
    from finproof.data.artifacts.resources import (
        artifact_manifest_schema_bytes,
        quality_issue_schema_bytes,
    )

    assert (
        artifact_manifest_schema_bytes()
        == (ROOT / "schemas/artifact_manifest.schema.json").read_bytes()
    )
    assert quality_issue_schema_bytes() == (ROOT / "schemas/quality_issue.schema.json").read_bytes()


def test_expected_contract_resource_matches_reviewed_source_bytes() -> None:
    from finproof.data.artifacts.expected_contract import ExpectedPhase1ArtifactContract
    from finproof.data.artifacts.resources import expected_phase1_contract_bytes

    source = _EXPECTED_CONTRACT_SOURCE.read_bytes()
    resource = expected_phase1_contract_bytes()

    assert resource == source
    assert hashlib.sha256(resource).hexdigest() == (
        "67b0d32fd89607a39378aa733a2071bffa146baa66454b3913d0276040f191e9"
    )
    ExpectedPhase1ArtifactContract.model_validate_json(resource, strict=True)


def test_active_standard_editable_expected_contract_loader_matches_source_outside_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.data.artifacts.resources import expected_phase1_contract_bytes

    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)

    assert expected_phase1_contract_bytes() == _EXPECTED_CONTRACT_SOURCE.read_bytes()


def test_standard_editable_expected_contract_loader_uses_distribution_fallback_when_src_shadows(
    tmp_path: Path,
) -> None:
    venv = tmp_path / "editable-venv"
    subprocess.run(  # noqa: S603
        [UV, "venv", "--python", "3.12", str(venv)],
        check=True,
        capture_output=True,
        text=True,
    )
    python = venv / "bin/python"
    subprocess.run(  # noqa: S603
        [UV, "pip", "install", "--python", str(python), "-e", str(ROOT)],
        check=True,
        capture_output=True,
        text=True,
    )
    unrelated = tmp_path / "outside"
    (unrelated / "finproof/resources/contracts").mkdir(parents=True)
    (unrelated / "finproof/resources/contracts/expected_phase1_artifacts.json").write_bytes(
        b"conflict"
    )
    script = """
from pathlib import Path
from finproof.data.artifacts.resources import expected_phase1_contract_bytes
root = Path(__import__('sys').argv[1])
source = (root / 'config/expected_phase1_artifacts.json').read_bytes()
assert expected_phase1_contract_bytes() == source
"""
    subprocess.run(  # noqa: S603
        [str(python), "-c", script, str(ROOT)],
        cwd=unrelated,
        check=True,
        capture_output=True,
        text=True,
    )


def test_built_wheel_expected_contract_loader_uses_importlib_resources_primary(
    tmp_path: Path,
) -> None:
    wheel_dir = tmp_path / "wheel"
    subprocess.run(  # noqa: S603
        [UV, "build", "--wheel", "--out-dir", str(wheel_dir)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(wheel_dir.glob("*.whl"))
    venv = tmp_path / "wheel-venv"
    subprocess.run(  # noqa: S603
        [UV, "venv", "--python", "3.12", str(venv)],
        check=True,
        capture_output=True,
        text=True,
    )
    python = venv / "bin/python"
    subprocess.run(  # noqa: S603
        [UV, "pip", "install", "--python", str(python), str(wheel)],
        check=True,
        capture_output=True,
        text=True,
    )
    script = """
from importlib import metadata
from pathlib import Path
def forbidden_distribution(_name):
    raise AssertionError('wheel primary touched metadata fallback')
metadata.distribution = forbidden_distribution
from finproof.data.artifacts.resources import expected_phase1_contract_bytes
root = Path(__import__('sys').argv[1])
source = (root / 'config/expected_phase1_artifacts.json').read_bytes()
assert expected_phase1_contract_bytes() == source
"""
    subprocess.run(  # noqa: S603
        [str(python), "-c", script, str(ROOT)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )


def test_active_editable_manifest_schema_resource_matches_new_contract_outside_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.data.artifacts.resources import artifact_manifest_schema_bytes

    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)
    source = ROOT / "schemas/artifact_manifest.schema.json"
    loaded = artifact_manifest_schema_bytes()

    assert loaded == source.read_bytes()
    assert hashlib.sha256(loaded).hexdigest() == hashlib.sha256(source.read_bytes()).hexdigest()


def test_active_standard_editable_schema_loader_matches_current_repository_sources_outside_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import finproof
    from finproof.data.artifacts import resources

    conflict_root = tmp_path / "unrelated"
    conflict_schemas = conflict_root / "finproof/resources/schemas"
    conflict_schemas.mkdir(parents=True)
    for destination in _SCHEMA_DESTINATIONS:
        (conflict_root / destination).write_bytes(b"conflict")
    monkeypatch.chdir(conflict_root)

    assert Path(finproof.__file__).resolve() == (ROOT / "src/finproof/__init__.py").resolve()
    primary_root = importlib_resources.files("finproof")
    distribution = importlib_metadata.distribution("finproof")
    distribution_root = Path(str(distribution.locate_file("")))

    for destination, source in _SCHEMA_DESTINATIONS.items():
        relative = destination.removeprefix("finproof/").split("/")
        assert primary_root.joinpath(*relative).is_file() is False
        located = Path(str(distribution.locate_file(destination)))
        assert located == distribution_root.joinpath(*destination.split("/"))
        assert located.is_file()
        current = distribution_root
        assert not current.is_symlink()
        for part in destination.split("/"):
            current = current / part
            assert not current.is_symlink()
        loaded = (
            resources.artifact_manifest_schema_bytes()
            if "artifact_manifest" in destination
            else resources.quality_issue_schema_bytes()
        )
        source_bytes = source.read_bytes()
        assert loaded == source_bytes
        assert hashlib.sha256(loaded).hexdigest() == hashlib.sha256(source_bytes).hexdigest()

    expected_location = distribution.locate_file(
        "finproof/resources/contracts/expected_phase1_artifacts.json"
    )
    assert Path(str(expected_location)).read_bytes() == _EXPECTED_CONTRACT_SOURCE.read_bytes()


def test_standard_editable_schema_loader_uses_distribution_fallback_when_src_shadows(
    tmp_path: Path,
) -> None:
    venv = tmp_path / "editable-venv"
    subprocess.run(  # noqa: S603
        [UV, "venv", "--python", "3.12", str(venv)],
        check=True,
        capture_output=True,
        text=True,
    )
    python = venv / "bin/python"
    subprocess.run(  # noqa: S603
        [UV, "pip", "install", "--python", str(python), "-e", str(ROOT)],
        check=True,
        capture_output=True,
        text=True,
    )
    unrelated = tmp_path / "unrelated"
    conflict_schemas = unrelated / "finproof/resources/schemas"
    conflict_schemas.mkdir(parents=True)
    (conflict_schemas / "artifact_manifest.schema.json").write_bytes(b"conflict")
    (conflict_schemas / "quality_issue.schema.json").write_bytes(b"conflict")

    script = """
import hashlib
from importlib import metadata, resources
from pathlib import Path
import finproof
from finproof.data.artifacts.resources import (
    artifact_manifest_schema_bytes,
    expected_phase1_contract_bytes,
    quality_issue_schema_bytes,
)

root = Path(__import__('sys').argv[1])
assert Path(finproof.__file__).resolve() == (root / 'src/finproof/__init__.py').resolve()
package_root = resources.files('finproof')
distribution = metadata.distribution('finproof')
distribution_root = Path(distribution.locate_file(''))
items = (
    (
        'finproof/resources/schemas/artifact_manifest.schema.json',
        root / 'schemas/artifact_manifest.schema.json',
        artifact_manifest_schema_bytes,
    ),
    (
        'finproof/resources/schemas/quality_issue.schema.json',
        root / 'schemas/quality_issue.schema.json',
        quality_issue_schema_bytes,
    ),
)
for destination, source, loader in items:
    assert not package_root.joinpath(*destination.removeprefix('finproof/').split('/')).is_file()
    located = Path(distribution.locate_file(destination))
    assert located == distribution_root.joinpath(*destination.split('/'))
    assert located.is_file()
    current = distribution_root
    assert not current.is_symlink()
    for part in destination.split('/'):
        current = current / part
        assert not current.is_symlink()
    loaded = loader()
    source_bytes = source.read_bytes()
    assert loaded == source_bytes
    assert hashlib.sha256(loaded).digest() == hashlib.sha256(source_bytes).digest()
expected = distribution.locate_file(
    'finproof/resources/contracts/expected_phase1_artifacts.json'
)
assert Path(expected).read_bytes() == (root / 'config/expected_phase1_artifacts.json').read_bytes()
assert expected_phase1_contract_bytes() == (
    root / 'config/expected_phase1_artifacts.json'
).read_bytes()
"""
    subprocess.run(  # noqa: S603
        [str(python), "-c", script, str(ROOT)],
        cwd=unrelated,
        check=True,
        capture_output=True,
        text=True,
    )


def test_built_wheel_schema_loader_uses_importlib_resources_primary(
    tmp_path: Path,
) -> None:
    wheel_dir = tmp_path / "wheel"
    subprocess.run(  # noqa: S603
        [UV, "build", "--wheel", "--out-dir", str(wheel_dir)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(wheel_dir.glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert set(_SCHEMA_DESTINATIONS) <= names
        assert archive.read("finproof/resources/contracts/expected_phase1_artifacts.json") == (
            _EXPECTED_CONTRACT_SOURCE.read_bytes()
        )
        assert all("build_candidate_artifacts" not in name for name in names)

    venv = tmp_path / "wheel-venv"
    subprocess.run(  # noqa: S603
        [UV, "venv", "--python", "3.12", str(venv)],
        check=True,
        capture_output=True,
        text=True,
    )
    python = venv / "bin/python"
    subprocess.run(  # noqa: S603
        [UV, "pip", "install", "--python", str(python), str(wheel)],
        check=True,
        capture_output=True,
        text=True,
    )
    unrelated = tmp_path / "outside-wheel"
    unrelated.mkdir()
    script = """
import hashlib
from importlib import metadata
from pathlib import Path
import sys

def forbidden_distribution(_name):
    raise AssertionError('wheel primary touched metadata fallback')

metadata.distribution = forbidden_distribution
from finproof.data.artifacts.resources import (
    artifact_manifest_schema_bytes,
    expected_phase1_contract_bytes,
    quality_issue_schema_bytes,
)
root = Path(sys.argv[1])
for loader, source in (
    (artifact_manifest_schema_bytes, root / 'schemas/artifact_manifest.schema.json'),
    (quality_issue_schema_bytes, root / 'schemas/quality_issue.schema.json'),
):
    loaded = loader()
    source_bytes = source.read_bytes()
    assert loaded == source_bytes
    assert hashlib.sha256(loaded).digest() == hashlib.sha256(source_bytes).digest()
expected = expected_phase1_contract_bytes()
expected_source = (root / 'config/expected_phase1_artifacts.json').read_bytes()
assert expected == expected_source
assert hashlib.sha256(expected).digest() == hashlib.sha256(expected_source).digest()
"""
    subprocess.run(  # noqa: S603
        [str(python), "-c", script, str(ROOT)],
        cwd=unrelated,
        check=True,
        capture_output=True,
        text=True,
    )


def test_candidate_bootstrap_guard_allows_absent_without_second_check() -> None:
    from tools.build_candidate_artifacts import assert_candidate_bootstrap_allowed

    probe = _CandidateProbe(False, False)

    assert_candidate_bootstrap_allowed(probe)

    assert probe.second_checks == 0


@pytest.mark.parametrize(
    ("source_exists", "resource_exists"),
    [(True, False), (False, True), (True, True)],
    ids=["source-present", "resource-present", "both-present"],
)
def test_candidate_bootstrap_guard_refuses_every_existing_baseline_state(
    source_exists: bool,
    resource_exists: bool,
) -> None:
    from tools.build_candidate_artifacts import assert_candidate_bootstrap_allowed

    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    probe = _CandidateProbe(source_exists, resource_exists)

    with pytest.raises(ArtifactContractError) as caught:
        assert_candidate_bootstrap_allowed(probe)

    assert caught.value.code is ArtifactErrorCode.BASELINE_ALREADY_EXISTS
    assert caught.value.internal_context == {}
    assert probe.second_checks == 0


def test_candidate_production_probe_and_tool_remain_private_and_absent() -> None:
    from tools.build_candidate_artifacts import _ProductionCandidateBaselineProbe

    import finproof
    from finproof.core.settings import Settings
    from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode

    settings = Settings(
        repository_root=ROOT,
        source_root=ROOT / "source_material",
        data_dir=ROOT / "source_material/data",
        artifact_dir=ROOT / "artifacts",
        database_path=ROOT / "artifacts/finproof.duckdb",
        artifact_build_config_path=ROOT / "config/artifact_build.yaml",
        expected_artifact_contract_path=ROOT / "config/expected_phase1_artifacts.json",
    )
    probe = _ProductionCandidateBaselineProbe(settings)

    assert probe.source_exists() is True
    assert probe.resource_exists() is True
    with pytest.raises(ArtifactContractError) as caught:
        probe.second_check()
    assert caught.value.code is ArtifactErrorCode.BASELINE_ALREADY_EXISTS
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]
    assert set(scripts) == {"finproof"}
    assert not hasattr(finproof, "build_candidate_artifacts")


def test_artifact_package_exports_only_closed_public_runtime_surface() -> None:
    from finproof.data import artifacts

    assert artifacts.__all__ == (
        "ArtifactBuildOptions",
        "ArtifactManifest",
        "build_artifacts",
        "open_read_only_database",
    )
    assert (
        tuple(name for name in artifacts.__all__ if hasattr(artifacts, name)) == artifacts.__all__
    )
    for forbidden in (
        "ArtifactCoreBuildOutcome",
        "ArtifactBuildTelemetry",
        "CandidateArtifactSet",
        "build_candidate_artifacts",
        "build_verified_candidate_stage",
        "PublicationState",
        "recover_owned_remnants",
    ):
        assert not hasattr(artifacts, forbidden)


def test_artifact_public_surface_exposes_no_core_candidate_or_expected_bypass() -> None:
    import finproof
    from finproof.data import artifacts

    assert artifacts.__all__ == (
        "ArtifactBuildOptions",
        "ArtifactManifest",
        "build_artifacts",
        "open_read_only_database",
    )
    assert set(tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]) == {
        "finproof"
    }
    for owner in (finproof, artifacts):
        for forbidden in (
            "ArtifactBuildOutcome",
            "ArtifactCoreBuildOutcome",
            "ArtifactBuildTelemetry",
            "CandidateArtifactSet",
            "ExpectedAcceptedPublicationStage",
            "VerifiedArtifactSet",
            "_LiveArtifactBuildCandidate",
            "_ExpectedAcceptedReceiverAdmission",
            "accept_expected_contract",
            "build_candidate_artifacts",
            "build_verified_candidate_stage",
            "compare_expected_artifact_contract",
            "recover_owned_remnants",
            "skip_expected_contract",
            "update_expected_contract",
        ):
            assert not hasattr(owner, forbidden)
