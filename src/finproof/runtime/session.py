"""One owner for expected-verified registries and the read-only artifact database."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol

from finproof.core.settings import Settings
from finproof.core.versions import VersionBundle
from finproof.data.artifacts.database import open_read_only_database
from finproof.data.artifacts.manifest import ArtifactManifest, VerifiedArtifactSet
from finproof.registry.loader import RegistryBundle


class _ClosableConnection(Protocol):
    def close(self) -> None: ...


class RuntimeArtifactSession:
    """Live path-free capability over one verified runtime generation."""

    __slots__ = ("_connection", "_registries", "_verified", "_versions")

    _connection: _ClosableConnection | None
    _registries: RegistryBundle
    _verified: VerifiedArtifactSet
    _versions: VersionBundle

    def __new__(cls) -> "RuntimeArtifactSession":
        raise TypeError("RuntimeArtifactSession is composition-owned")

    @classmethod
    def _issue(
        cls,
        *,
        connection: _ClosableConnection,
        verified: VerifiedArtifactSet,
        registries: RegistryBundle,
        versions: VersionBundle,
    ) -> "RuntimeArtifactSession":
        if (
            cls is not RuntimeArtifactSession
            or type(verified) is not VerifiedArtifactSet
            or type(registries) is not RegistryBundle
            or type(versions) is not VersionBundle
        ):
            raise TypeError("runtime session inputs differ")
        versions.require_runtime(verified=verified, registries=registries)
        value = object.__new__(cls)
        value._connection = connection
        value._verified = verified
        value._registries = registries
        value._versions = versions
        return value

    @property
    def verified_artifacts(self) -> VerifiedArtifactSet:
        self.assert_live()
        return self._verified

    @property
    def registries(self) -> RegistryBundle:
        self.assert_live()
        return self._registries

    @property
    def versions(self) -> VersionBundle:
        self.assert_live()
        return self._versions

    def assert_live(self) -> None:
        if self._connection is None:
            raise RuntimeError("runtime artifact session is closed")
        self._versions.require_runtime(
            verified=self._verified,
            registries=self._registries,
        )

    def _close(self) -> None:
        connection = self._connection
        if connection is None:
            return
        self._connection = None
        connection.close()


@contextmanager
def open_runtime_artifact_session(settings: Settings) -> Iterator[RuntimeArtifactSession]:
    """Expected-verify the published root before opening its declared database."""
    if type(settings) is not Settings:
        raise TypeError("runtime session requires exact settings")
    manifest = ArtifactManifest.load(settings.artifact_dir / "manifest.json")
    if type(manifest) is not ArtifactManifest:
        raise TypeError("runtime manifest type differs")
    verified = manifest.verify(settings.artifact_dir)
    if type(verified) is not VerifiedArtifactSet:
        raise TypeError("runtime verification type differs")
    registries = RegistryBundle.from_package()
    registries.require_issued()
    versions = VersionBundle.from_runtime(
        verified=verified,
        registries=registries,
        execution_mode=settings.execution_mode,
    )
    database_path = settings.artifact_dir / manifest.database_path
    if database_path != settings.database_path:
        raise ValueError("manifest database path differs from settings")
    connection = open_read_only_database(database_path)
    try:
        session = RuntimeArtifactSession._issue(
            connection=connection,
            verified=verified,
            registries=registries,
            versions=versions,
        )
    except BaseException:
        connection.close()
        raise
    try:
        yield session
    finally:
        session._close()
