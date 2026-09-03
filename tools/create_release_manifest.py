"""Create release metadata over an explicit clean ancestor commit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

_PREFIXES = (
    "config/",
    "evaluation/organizer_20260824/",
    "prompts/",
    "schemas/",
    "scripts/",
    "source_material/official_notices/",
    "src/",
    "tools/",
)
_REQUIRED = {
    ".dockerignore",
    "Dockerfile",
    "pyproject.toml",
    "source_material/input_manifest.json",
    "source_material/schema_catalog.json",
    "uv.lock",
}
_REPORTS = (
    "artifacts/evaluation/final-load.json",
    "artifacts/evaluation/final-soak.json",
    "artifacts/evaluation/organizer-20260824.json",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


def _git_binary() -> str:
    value = shutil.which("git")
    if value is None:
        raise RuntimeError("git executable is required")
    return value


_GIT = _git_binary()


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run([_GIT, *args], cwd=root, check=check, capture_output=True)


def _git_bytes(root: Path, covered_commit: str, path: str) -> bytes:
    return _git(root, "show", f"{covered_commit}:{path}").stdout


def _covered_paths(root: Path, covered_commit: str) -> tuple[str, ...]:
    names = _git(root, "ls-tree", "-r", "--name-only", "-z", covered_commit).stdout
    paths = tuple(name.decode("utf-8") for name in names.split(b"\0") if name)
    selected = tuple(
        path
        for path in paths
        if path in _REQUIRED
        or path in _REPORTS
        or any(path.startswith(prefix) for prefix in _PREFIXES)
    )
    missing = (_REQUIRED | set(_REPORTS)) - set(selected)
    missing_prefixes = [
        prefix for prefix in _PREFIXES if not any(p.startswith(prefix) for p in selected)
    ]
    if missing or missing_prefixes:
        raise ValueError(
            "covered commit lacks release inputs: "
            + ", ".join(sorted(missing) + sorted(missing_prefixes))
        )
    return selected


def _require_candidate(root: Path, covered_commit: str) -> None:
    if not _COMMIT.fullmatch(covered_commit):
        raise ValueError("covered commit must be a 40-character lowercase hash")
    if _git(root, "cat-file", "-e", f"{covered_commit}^{{commit}}", check=False).returncode:
        raise ValueError("unknown covered commit")
    head = _git(root, "rev-parse", "HEAD").stdout.decode().strip()
    if _git(root, "merge-base", "--is-ancestor", covered_commit, head, check=False).returncode:
        raise ValueError("covered commit must be an ancestor of HEAD")
    if (
        covered_commit == head
        and _git(root, "status", "--porcelain", "--untracked-files=all").stdout
    ):
        raise ValueError("covered candidate worktree is dirty")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validate_artifact_inputs(
    root: Path,
    covered_commit: str,
    artifact: dict[str, Any],
    files: dict[str, str],
) -> None:
    inputs = artifact.get("source_inputs")
    if not isinstance(inputs, list) or not inputs:
        raise ValueError("artifact source inputs differ")
    seen: set[str] = set()
    for value in inputs:
        if not isinstance(value, dict):
            raise ValueError("artifact source inputs differ")
        namespace = value.get("namespace")
        path = value.get("path")
        expected = value.get("sha256")
        if (
            namespace not in {"source_root", "repository"}
            or not isinstance(path, str)
            or not path
            or "\\" in path
            or PurePosixPath(path).is_absolute()
            or PurePosixPath(path).as_posix() != path
            or any(part in {"", ".", ".."} for part in PurePosixPath(path).parts)
            or not isinstance(expected, str)
            or not _SHA256.fullmatch(expected)
        ):
            raise ValueError("artifact source inputs differ")
        relative = f"source_material/{path}" if namespace == "source_root" else path
        if relative in seen or relative not in files:
            raise ValueError("artifact source inputs differ")
        if (
            files[relative] != expected
            or _sha256(_git_bytes(root, covered_commit, relative)) != expected
        ):
            raise ValueError("artifact source input differs from covered Git object")
        seen.add(relative)


def manifest_checksum(payload: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in payload.items() if key != "manifest_sha256"}
    return _sha256(
        json.dumps(unsigned, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    )


def create_manifest(
    *,
    root: Path,
    covered_commit: str,
    image_digest: str,
    artifact_manifest_path: Path,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    _require_candidate(root, covered_commit)
    covered_commit = _git(root, "rev-parse", covered_commit).stdout.decode().strip()
    if not _IMAGE_DIGEST.fullmatch(image_digest):
        raise ValueError("image digest must be sha256:<64 lowercase hex>")
    artifact_raw = artifact_manifest_path.read_bytes()
    artifact = json.loads(artifact_raw)
    if (
        not isinstance(artifact, dict)
        or artifact.get("dataset_version") != "2026-08-24"
        or not isinstance(artifact.get("logical_hash"), str)
        or not _SHA256.fullmatch(artifact["logical_hash"])
    ):
        raise ValueError("artifact manifest identity differs")
    paths = _covered_paths(root, covered_commit)
    files = {path: _sha256(_git_bytes(root, covered_commit, path)) for path in paths}
    _validate_artifact_inputs(root, covered_commit, artifact, files)
    payload: dict[str, Any] = {
        "schema_version": "finproof.release-manifest.v1",
        "covered_commit": covered_commit,
        "covered_commit_created_at": _git(root, "show", "-s", "--format=%cI", covered_commit)
        .stdout.decode()
        .strip(),
        "files": files,
        "image_digest": image_digest,
        "artifact_manifest_sha256": _sha256(artifact_raw),
        "artifact_logical_hash": artifact["logical_hash"],
        "artifact_dataset_version": artifact["dataset_version"],
        "evaluation_reports": {path: files[path] for path in _REPORTS},
    }
    payload["manifest_sha256"] = manifest_checksum(payload)
    return payload


def _image_digest(explicit: str | None) -> str:
    if explicit:
        return explicit
    configured = os.getenv("FINPROOF_RELEASE_IMAGE_DIGEST")
    if configured:
        return configured
    image = os.getenv("FINPROOF_IMAGE")
    docker = shutil.which("docker")
    if not image or not docker:
        raise ValueError("set FINPROOF_IMAGE or FINPROOF_RELEASE_IMAGE_DIGEST")
    return subprocess.run(
        [docker, "image", "inspect", "--format", "{{.Id}}", image],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _artifact_manifest(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    artifact_root = Path(os.getenv("FINPROOF_ARTIFACT_DIR", "artifacts"))
    return artifact_root / "manifest.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--covered-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image-digest")
    parser.add_argument("--artifact-manifest", type=Path)
    args = parser.parse_args(argv)
    payload = create_manifest(
        root=Path.cwd(),
        covered_commit=args.covered_commit,
        image_digest=_image_digest(args.image_digest),
        artifact_manifest_path=_artifact_manifest(args.artifact_manifest),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f".{args.output.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    sys.stdout.write(
        json.dumps({"covered_commit": payload["covered_commit"], "output": str(args.output)}) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
