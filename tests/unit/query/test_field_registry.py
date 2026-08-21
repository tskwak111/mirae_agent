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
