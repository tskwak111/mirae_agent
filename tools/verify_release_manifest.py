"""Verify release metadata against its covered Git object and bound artifacts."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__:
    from tools.create_release_manifest import (
        _COMMIT,
        _IMAGE_DIGEST,
        _REPORTS,
        _artifact_manifest,
        _covered_paths,
        _git,
        _git_bytes,
        _image_digest,
        _sha256,
        _validate_artifact_inputs,
        manifest_checksum,
    )
else:
    from create_release_manifest import (  # type: ignore[import-not-found,no-redef]
        _COMMIT,
        _IMAGE_DIGEST,
        _REPORTS,
        _artifact_manifest,
        _covered_paths,
        _git,
        _git_bytes,
        _image_digest,
        _sha256,
        _validate_artifact_inputs,
        manifest_checksum,
    )

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_KEYS = {
    "artifact_dataset_version",
    "artifact_logical_hash",
    "artifact_manifest_sha256",
    "covered_commit",
    "covered_commit_created_at",
    "evaluation_reports",
    "files",
    "image_digest",
    "manifest_sha256",
    "schema_version",
}


class ReleaseManifestError(ValueError):
    """Release metadata did not match its immutable inputs."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseManifestError("release manifest is unreadable") from error
    if not isinstance(value, dict) or set(value) != _KEYS:
        raise ReleaseManifestError("release manifest shape differs")
    return value


def verify_manifest(
    path: Path,
    *,
    root: Path,
    image_digest: str,
    artifact_manifest_path: Path,
) -> None:
    payload = _load(path)
    if payload.get("schema_version") != "finproof.release-manifest.v1" or (
        not isinstance(payload.get("manifest_sha256"), str)
        or not _SHA256.fullmatch(payload["manifest_sha256"])
        or payload["manifest_sha256"] != manifest_checksum(payload)
    ):
        raise ReleaseManifestError("release manifest checksum differs")
    if payload.get("image_digest") != image_digest or not _IMAGE_DIGEST.fullmatch(image_digest):
        raise ReleaseManifestError("bound image digest differs")

    root = root.resolve(strict=True)
    commit = payload.get("covered_commit")
    if (
        not isinstance(commit, str)
        or not _COMMIT.fullmatch(commit)
        or _git(root, "cat-file", "-e", f"{commit}^{{commit}}", check=False).returncode
    ):
        raise ReleaseManifestError("covered commit is unknown")
    head = _git(root, "rev-parse", "HEAD").stdout.decode().strip()
    if _git(root, "merge-base", "--is-ancestor", commit, head, check=False).returncode:
        raise ReleaseManifestError("covered commit is not an ancestor")
    commit_created_at = _git(root, "show", "-s", "--format=%cI", commit).stdout.decode().strip()
    if payload.get("covered_commit_created_at") != commit_created_at:
        raise ReleaseManifestError("covered commit metadata differs")
    expected_paths = _covered_paths(root, commit)
    files = payload.get("files")
    if not isinstance(files, dict) or set(files) != set(expected_paths):
        raise ReleaseManifestError("covered file inventory differs")
    for relative in expected_paths:
        if files.get(relative) != _sha256(_git_bytes(root, commit, relative)):
            raise ReleaseManifestError(f"covered Git object differs: {relative}")
    if payload.get("evaluation_reports") != {path: files[path] for path in _REPORTS}:
        raise ReleaseManifestError("evaluation report binding differs")

    artifact_raw = artifact_manifest_path.read_bytes()
    artifact = json.loads(artifact_raw)
    if (
        payload.get("artifact_manifest_sha256") != _sha256(artifact_raw)
        or payload.get("artifact_logical_hash") != artifact.get("logical_hash")
        or payload.get("artifact_dataset_version") != artifact.get("dataset_version")
    ):
        raise ReleaseManifestError("bound artifact manifest differs")
    _validate_artifact_inputs(root, commit, artifact, files)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--image-digest")
    parser.add_argument("--artifact-manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        verify_manifest(
            args.manifest,
            root=Path.cwd(),
            image_digest=_image_digest(args.image_digest),
            artifact_manifest_path=_artifact_manifest(args.artifact_manifest),
        )
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        sys.stderr.write(f"release manifest verification failed: {error}\n")
        return 1
    sys.stdout.write(json.dumps({"status": "passed", "manifest": str(args.manifest)}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
