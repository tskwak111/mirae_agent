"""Official read-only deterministic runtime query."""

from tests.helpers.official_artifact_subprocess import OfficialArtifactSession


def test_official_runtime_session_executes_one_read_only_supported_query(
    official_artifact_session: OfficialArtifactSession,
) -> None:
    from tests.helpers.query_runtime import verified_artifacts
    from tests.unit.query.test_semantic_validator import _context, _plan

    from finproof.core.settings import ExecutionMode
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.database import open_read_only_database
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        QueryExecutor,
        ResolutionBundle,
        SemanticValidator,
    )
    from finproof.registry.loader import RegistryBundle
    from finproof.runtime.session import RuntimeArtifactSession

    official = official_artifact_session
    verified = verified_artifacts()
    registries = RegistryBundle.from_package()
    session = RuntimeArtifactSession._issue(
        connection=open_read_only_database(official.root / "finproof.duckdb"),
        verified=verified,
        registries=registries,
        versions=VersionBundle.from_runtime(
            verified=verified,
            registries=registries,
            execution_mode=ExecutionMode.EVALUATION,
        ),
    )
    try:
        fields = FieldRegistry.from_bundle(registries)
        plan = _plan()
        validated = SemanticValidator(fields).validate(
            plan,
            resolutions=ResolutionBundle(results=()),
            context=_context(),
        )
        bundle = ExecutionBundleBuilder(fields).build(validated, context=_context())

        raw = QueryExecutor(session).execute(bundle)

        assert raw.candidate_count == 20_497
        assert raw.segments[0].candidate_count == 20_497
        assert all(row.product_type is plan.product_types[0] for row in raw.segments[0].rows)
    finally:
        session._close()
