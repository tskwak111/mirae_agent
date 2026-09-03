"""Official deterministic policy profiles."""

from collections import Counter
from datetime import date
from decimal import Decimal

from tests.helpers.official_artifact_subprocess import OfficialArtifactSession


def test_official_quality_profiles_match_refresh_state_zero_tie_and_currency_facts(
    official_artifact_session: OfficialArtifactSession,
) -> None:
    from tests.helpers.query_runtime import verified_artifacts

    from finproof.core.settings import ExecutionMode
    from finproof.core.versions import VersionBundle
    from finproof.data.artifacts.database import open_read_only_database
    from finproof.domain.query_plan import (
        AggregationFunction,
        AggregationSpec,
        Intent,
        ProductType,
        QueryPlan,
        ResultGrain,
        SortDirection,
        SortSpec,
        TopKScope,
    )
    from finproof.quality import PolicyEngine
    from finproof.query import (
        ExecutionBundleBuilder,
        FieldRegistry,
        QueryExecutor,
        ResolutionBundle,
        SemanticValidator,
        ValidationContext,
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
    context = ValidationContext(
        as_of_date=date(2026, 8, 24),
        execution_mode=ExecutionMode.EVALUATION,
    )
    fields = FieldRegistry.from_bundle(registries)

    def execute(plan: QueryPlan):  # type: ignore[no-untyped-def]
        validated = SemanticValidator(fields).validate(
            plan,
            resolutions=ResolutionBundle(results=()),
            context=context,
        )
        bundle = ExecutionBundleBuilder(fields).build(validated, context=context)
        raw = QueryExecutor(session).execute(bundle)
        return raw, PolicyEngine().apply(raw, bundle=bundle)

    try:
        bond_raw, bond_policy = execute(
            QueryPlan(
                intent=Intent.AGGREGATE,
                product_types=(ProductType.DOMESTIC_BOND,),
                entities=(),
                as_of_date=context.as_of_date,
                result_grain=ResultGrain.INSTRUMENT,
                filters=(),
                metrics=(),
                sort=(),
                aggregation=AggregationSpec(
                    function=AggregationFunction.COUNT,
                    field=None,
                    group_by=(),
                ),
                top_k=5,
                top_k_scope=TopKScope.GLOBAL,
                needs_clarification=False,
                clarification_reason="",
            )
        )
        assert bond_raw.candidate_count == 20_497
        assert (len(bond_policy.included_rows), bond_policy.excluded_state_count) == (
            20_407,
            90,
        )
        assert bond_policy.aggregates[0].value == 20_407

        tracking_raw, tracking_policy = execute(
            QueryPlan(
                intent=Intent.SCREEN_RANK,
                product_types=(ProductType.DOMESTIC_ETF, ProductType.DOMESTIC_ETN),
                entities=(),
                as_of_date=context.as_of_date,
                result_grain=ResultGrain.PRODUCT,
                filters=(),
                metrics=("tracking_error",),
                sort=(SortSpec(field="tracking_error", direction=SortDirection.ASC),),
                aggregation=None,
                top_k=5,
                top_k_scope=TopKScope.GLOBAL,
                needs_clarification=False,
                clarification_reason="",
            )
        )
        recorded_tracking = tuple(
            item.value
            for segment in tracking_raw.segments
            for row in segment.rows
            for item in row.values
            if item.field_id == "tracking_error" and item.value is not None
        )
        assert len(recorded_tracking) == 1_598
        assert Decimal("0") in set(recorded_tracking)
        assert len(set(recorded_tracking)) > 1
        assert len(tracking_policy.ranks) == 374
        assert {
            (rank.rank, rank.tie_count, rank.value.value) for rank in tracking_policy.ranks
        } == {(1, 374, Decimal("0"))}

        currency_raw, currency_policy = execute(
            QueryPlan(
                intent=Intent.SCREEN_RANK,
                product_types=(ProductType.PUBLIC_FUND,),
                entities=(),
                as_of_date=context.as_of_date,
                result_grain=ResultGrain.FUND_ITEM,
                filters=(),
                metrics=("aum",),
                sort=(SortSpec(field="aum", direction=SortDirection.DESC),),
                aggregation=None,
                top_k=5,
                top_k_scope=TopKScope.PER_PRODUCT_TYPE,
                needs_clarification=False,
                clarification_reason="",
            )
        )
        currencies = Counter(
            item.value
            for row in currency_raw.segments[0].rows
            for item in row.values
            if item.field_id == "currency"
        )
        assert currencies == {"KRW": 23_147, "USD": 453, None: 76}
        assert {
            partition.currency: len(partition.values) for partition in currency_policy.partitions
        } == {"KRW": 9_337, "USD": 76}
    finally:
        session._close()
