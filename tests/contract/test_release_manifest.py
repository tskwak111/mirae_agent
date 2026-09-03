"""A-005 parent-commit release-manifest contract."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from tools.create_release_manifest import create_manifest, manifest_checksum
from tools.verify_release_manifest import ReleaseManifestError, verify_manifest

_IMAGE = "sha256:" + "a" * 64


def _git_binary() -> str:
    value = shutil.which("git")
    if value is None:
        raise RuntimeError("git executable is required")
    return value


_GIT = _git_binary()


def test_verify_release_manifest_script_entrypoint_is_importable() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/verify_release_manifest.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def _git(root: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603 -- resolved Git executable and closed test arguments
        [_GIT, *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _repository(tmp_path: Path) -> tuple[Path, Path, str]:
    root = tmp_path / "repository"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "FinProof Test")
    files = {
        ".dockerignore": ".env\nartifacts\nsource_material\n",
        "Dockerfile": "FROM scratch\n",
        "config/policy.yaml": "version: 1\n",
        "schemas/api.json": "{}\n",
        "prompts/planner.md": "HCX\n",
        "pyproject.toml": "[project]\nname='finproof'\nversion='0'\n",
        "scripts/reproduce.sh": "#!/bin/sh\n",
        "src/finproof/app.py": "VALUE = 1\n",
        "source_material/input_manifest.json": "{}\n",
        "source_material/official_notices/notice.md": "official\n",
        "source_material/schema_catalog.json": "{}\n",
        "tools/release.py": "VALUE = 1\n",
        "uv.lock": "version = 1\n",
        "evaluation/organizer_20260824/easy.jsonl": "{}\n",
        "artifacts/evaluation/organizer-20260824.json": "{}\n",
        "artifacts/evaluation/final-load.json": "{}\n",
        "artifacts/evaluation/final-soak.json": "{}\n",
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "candidate")
    covered = _git(root, "rev-parse", "HEAD")

    artifact = tmp_path / "artifact-manifest.json"
    source_inputs = [
        {
            "namespace": "source_root",
            "path": "input_manifest.json",
            "sha256": hashlib.sha256(
                (root / "source_material/input_manifest.json").read_bytes()
            ).hexdigest(),
        },
        {
            "namespace": "repository",
            "path": "config/policy.yaml",
            "sha256": hashlib.sha256((root / "config/policy.yaml").read_bytes()).hexdigest(),
        },
    ]
    artifact.write_text(
        json.dumps(
            {
                "dataset_version": "2026-08-24",
                "logical_hash": "b" * 64,
                "source_inputs": source_inputs,
            }
        ),
        encoding="utf-8",
    )
    return root, artifact, covered


def _write_manifest(root: Path, artifact: Path, covered: str) -> Path:
    manifest = create_manifest(
        root=root,
        covered_commit=covered,
        image_digest=_IMAGE,
        artifact_manifest_path=artifact,
    )
    output = root / "release/manifest.json"
    output.parent.mkdir()
    output.write_text(json.dumps(manifest), encoding="utf-8")
    return output


def test_child_worktree_verifies_parent_object_and_ignores_worktree_substitution(
    tmp_path: Path,
) -> None:
    root, artifact, covered = _repository(tmp_path)
    (root / "metadata.txt").write_text("child\n", encoding="utf-8")
    _git(root, "add", "metadata.txt")
    _git(root, "commit", "-m", "metadata child")
    output = _write_manifest(root, artifact, covered)

    verify_manifest(output, root=root, image_digest=_IMAGE, artifact_manifest_path=artifact)
    (root / "src/finproof/app.py").write_text("substituted\n", encoding="utf-8")
    verify_manifest(output, root=root, image_digest=_IMAGE, artifact_manifest_path=artifact)


@pytest.mark.parametrize("binding", ["image", "artifact"])
def test_bound_image_and_artifact_hash_changes_fail_verification(
    tmp_path: Path, binding: str
) -> None:
    root, artifact, covered = _repository(tmp_path)
    output = _write_manifest(root, artifact, covered)
    payload = json.loads(output.read_bytes())
    key = "image_digest" if binding == "image" else "artifact_manifest_sha256"
    payload[key] = "sha256:" + "c" * 64 if binding == "image" else "c" * 64
    payload["manifest_sha256"] = manifest_checksum(payload)
    output.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ReleaseManifestError):
        verify_manifest(output, root=root, image_digest=_IMAGE, artifact_manifest_path=artifact)


def test_covered_commit_metadata_cannot_be_rewritten(tmp_path: Path) -> None:
    root, artifact, covered = _repository(tmp_path)
    output = _write_manifest(root, artifact, covered)
    payload = json.loads(output.read_bytes())
    payload["covered_commit_created_at"] = "2099-01-01T00:00:00+00:00"
    payload["manifest_sha256"] = manifest_checksum(payload)
    output.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ReleaseManifestError):
        verify_manifest(output, root=root, image_digest=_IMAGE, artifact_manifest_path=artifact)


def test_artifact_inputs_must_match_the_covered_git_object(tmp_path: Path) -> None:
    root, artifact, _covered = _repository(tmp_path)
    (root / "config/policy.yaml").write_text("version: 2\n", encoding="utf-8")
    _git(root, "add", "config/policy.yaml")
    _git(root, "commit", "-m", "change artifact input")
    covered = _git(root, "rev-parse", "HEAD")

    with pytest.raises(ValueError, match="artifact source input differs"):
        create_manifest(
            root=root,
            covered_commit=covered,
            image_digest=_IMAGE,
            artifact_manifest_path=artifact,
        )


def test_unknown_nonancestor_and_dirty_covered_candidates_are_rejected(tmp_path: Path) -> None:
    root, artifact, covered = _repository(tmp_path)
    with pytest.raises(ValueError, match="40-character"):
        create_manifest(
            root=root,
            covered_commit="HEAD",
            image_digest=_IMAGE,
            artifact_manifest_path=artifact,
        )
    with pytest.raises(ValueError, match="unknown"):
        create_manifest(
            root=root,
            covered_commit="f" * 40,
            image_digest=_IMAGE,
            artifact_manifest_path=artifact,
        )

    sibling = tmp_path / "sibling"
    _git(root, "worktree", "add", "--detach", str(sibling), covered)
    (sibling / "other.txt").write_text("sibling\n", encoding="utf-8")
    _git(sibling, "add", "other.txt")
    _git(sibling, "commit", "-m", "sibling")
    sibling_commit = _git(sibling, "rev-parse", "HEAD")
    with pytest.raises(ValueError, match="ancestor"):
        create_manifest(
            root=root,
            covered_commit=sibling_commit,
            image_digest=_IMAGE,
            artifact_manifest_path=artifact,
        )

    (root / "src/finproof/app.py").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(ValueError, match="dirty"):
        create_manifest(
            root=root,
            covered_commit=covered,
            image_digest=_IMAGE,
            artifact_manifest_path=artifact,
        )


def test_clean_room_script_reproduces_exact_commit_without_repeating_full_gate() -> None:
    script = Path("scripts/clean_room_reproduce.sh").read_text(encoding="utf-8")

    assert script.startswith("#!/bin/sh\nset -eu\n")
    for required in (
        "mktemp -d",
        "git clone --no-local",
        "git checkout --detach",
        "uv sync --frozen --all-groups",
        "tools/verify_handoff.py",
        "tools/audit_source_data.py --check",
        "tools/check_competition_compliance.py --check",
        "tests/contract/test_competition_compliance.py",
        "tests/contract/test_release_manifest.py",
        "docker build",
    ):
        assert required in script
    assert "uv run pytest -q\n" not in script
