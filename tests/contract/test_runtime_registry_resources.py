"""Installed Phase 2 runtime registry resource contracts."""

import json
import shutil
import subprocess
from pathlib import Path

from finproof.registry.loader import RegistryBundle
from finproof.registry.resources import REGISTRY_RESOURCE_NAMES, registry_resource_bytes

ROOT = Path(__file__).resolve().parents[2]


def test_repository_and_package_registry_bytes_are_identical() -> None:
    """The runtime parses the exact reviewed repository bytes for all eight registries."""
    for name in REGISTRY_RESOURCE_NAMES:
        assert registry_resource_bytes(name) == (ROOT / "config" / name).read_bytes()
    bundle = RegistryBundle.from_package()
    assert bundle.fields.version == "1.3.0"
    assert bundle.planner.version == "1.2.0"


def test_wheel_and_editable_install_load_identical_runtime_registry_resources(
    tmp_path: Path,
) -> None:
    """Both supported installation forms load the same eight issued registries."""
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv executable is required for resource contract tests")
    wheel_dir = tmp_path / "wheel"
    subprocess.run(  # noqa: S603
        [uv, "build", "--wheel", "--out-dir", str(wheel_dir)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(wheel_dir.glob("*.whl"))
    script = """
import hashlib
import json
from finproof.registry.loader import RegistryBundle
from finproof.registry.resources import REGISTRY_RESOURCE_NAMES, registry_resource_bytes
bundle = RegistryBundle.from_package()
bundle.require_issued()
print(json.dumps({
    'hashes': {name: hashlib.sha256(registry_resource_bytes(name)).hexdigest()
               for name in REGISTRY_RESOURCE_NAMES},
    'versions': [
        bundle.datasets.version, bundle.metrics.version, bundle.fields.version,
        bundle.states.version, bundle.quality.version, bundle.ratings.version,
        bundle.answers.version, bundle.planner.version,
    ],
}, sort_keys=True))
"""

    results = []
    for name, package in (("editable", ROOT), ("wheel", wheel)):
        venv = tmp_path / f"{name}-venv"
        subprocess.run(  # noqa: S603
            [uv, "venv", "--python", "3.12", str(venv)],
            check=True,
            capture_output=True,
            text=True,
        )
        python = venv / "bin/python"
        install = [uv, "pip", "install", "--python", str(python)]
        if name == "editable":
            install.append("-e")
        install.append(str(package))
        subprocess.run(install, check=True, capture_output=True, text=True)  # noqa: S603
        completed = subprocess.run(  # noqa: S603
            [str(python), "-c", script],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        )
        results.append(json.loads(completed.stdout))

    assert results[0] == results[1]
