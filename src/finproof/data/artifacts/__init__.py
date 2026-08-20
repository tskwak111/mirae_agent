"""Closed public artifact build and read contracts."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finproof.data.artifacts.builder import build_artifacts
    from finproof.data.artifacts.config import ArtifactBuildOptions
    from finproof.data.artifacts.database import open_read_only_database
    from finproof.data.artifacts.manifest import ArtifactManifest

__all__ = (
    "ArtifactBuildOptions",
    "ArtifactManifest",
    "build_artifacts",
    "open_read_only_database",
)


def __getattr__(name: str) -> object:
    value: object
    if name == "ArtifactBuildOptions":
        from finproof.data.artifacts.config import ArtifactBuildOptions

        value = ArtifactBuildOptions
    elif name == "ArtifactManifest":
        from finproof.data.artifacts.manifest import ArtifactManifest

        value = ArtifactManifest
    elif name == "build_artifacts":
        from finproof.data.artifacts.builder import build_artifacts

        value = build_artifacts
    elif name == "open_read_only_database":
        from finproof.data.artifacts.database import open_read_only_database

        value = open_read_only_database
    else:
        raise AttributeError(name)
    globals()[name] = value
    return value
