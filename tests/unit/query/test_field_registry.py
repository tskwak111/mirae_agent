"""Focused closed query-field mapping tests."""


def test_query_module_skeleton_exposes_exact_interfaces() -> None:
    from finproof.query import (
        CompiledQuery,
        ExecutionBundleBuilder,
        FieldProjection,
        FieldRegistry,
        QueryAst,
        ResolutionBundle,
        SemanticValidator,
        SqlCompiler,
        ValidationContext,
    )

    assert all(
        isinstance(value, type)
        for value in (
            CompiledQuery,
            ExecutionBundleBuilder,
            FieldProjection,
            FieldRegistry,
            QueryAst,
            ResolutionBundle,
            SemanticValidator,
            SqlCompiler,
            ValidationContext,
        )
    )


def test_field_registry_maps_every_canonical_field_to_closed_table_spec_projection() -> None:
    from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
    from finproof.query import FieldRegistry
    from finproof.registry.loader import RegistryBundle

    registries = RegistryBundle.from_package()
    fields = FieldRegistry.from_bundle(registries)
    expected = {
        (field_id, product_type)
        for field_id, field in registries.fields.entries.items()
        if field_id != "holding_constituent"
        for product_type in (
            field.product_types
            or tuple(
                product_type
                for metric_id in field.metric_ids
                for product_type in registries.metrics.entries[metric_id].product_types
            )
        )
    }

    assert set(fields.projections) == expected
    for projection in fields.projections.values():
        spec = TABLE_SPEC_BY_NAME[projection.table_name]
        column_names = {column.name for column in spec.columns}
        assert projection.column_name in column_names
        assert projection.quality_column_name in column_names


def test_buyable_quantity_is_not_queryable_or_metric_registered() -> None:
    from finproof.registry.loader import RegistryBundle

    registries = RegistryBundle.from_package()

    assert "buyable_quantity" not in registries.fields.entries
    assert "bond.buyable_quantity" not in registries.metrics.entries


def test_holding_constituent_supports_only_eq_without_native_projection() -> None:
    from finproof.domain.query_plan import FilterOperator, ProductType
    from finproof.query.fields import FieldRegistry as QueryFieldRegistry
    from finproof.registry.loader import RegistryBundle

    registries = RegistryBundle.from_package()
    field = registries.fields.entries["holding_constituent"]

    assert registries.fields.version == "1.3.0"
    assert field.operators == (FilterOperator.EQ,)
    assert field.product_types == (
        ProductType.DOMESTIC_ETF,
        ProductType.DOMESTIC_ETN,
        ProductType.OVERSEAS_ETF,
        ProductType.OVERSEAS_ETN,
        ProductType.PUBLIC_FUND,
    )
    query_fields = QueryFieldRegistry.from_bundle(registries)
    assert all(key[0] != "holding_constituent" for key in query_fields.projections)
