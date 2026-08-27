"""Safe foreign-dialect transforms for Vertica-specific expression wrappers."""

from __future__ import annotations

from sqlglot import exp
from sqlglot.generator import Generator

from sqlglot_vertica import expressions as vexp


def _postgres_listagg_expression(
    generator: Generator,
    expression: vexp.ListAgg,
    order: exp.Expr | None = None,
) -> exp.GroupConcat | None:
    """Lower Vertica LISTAGG to the canonical aggregate PostgreSQL understands."""

    aggregate = expression.this
    if not isinstance(aggregate, exp.GroupConcat):
        generator.unsupported("Vertica LISTAGG requires a canonical GroupConcat child")
        return None

    aggregate = aggregate.copy()
    unsupported_parameters: list[str] = []
    for parameter in expression.args.get("parameters") or []:
        if (
            not isinstance(parameter, exp.EQ)
            or not isinstance(parameter.this, exp.Identifier)
            or parameter.expression is None
        ):
            generator.unsupported(
                "Vertica LISTAGG parameters must be identifier=value pairs for PostgreSQL"
            )
            continue

        name = parameter.this.name.lower()
        if name == "separator":
            if aggregate.args.get("separator") is not None:
                generator.unsupported(
                    "Vertica LISTAGG cannot specify both positional and parameter separators "
                    "for PostgreSQL"
                )
            aggregate.set("separator", parameter.expression.copy())
        else:
            unsupported_parameters.append(name)

    if unsupported_parameters:
        names = ", ".join(dict.fromkeys(unsupported_parameters))
        generator.unsupported(
            f"PostgreSQL STRING_AGG does not support Vertica LISTAGG parameter(s): {names}"
        )

    if order is not None:
        if not isinstance(order, exp.Order):
            generator.unsupported("Vertica LISTAGG WITHIN GROUP requires an ORDER BY clause")
            return None

        order = order.copy()
        order.set("this", aggregate.this)
        aggregate.set("this", order)

    return aggregate


def _postgres_listagg_sql(generator: Generator, expression: vexp.ListAgg) -> str:
    aggregate = _postgres_listagg_expression(generator, expression)
    return generator.sql(aggregate)


def _postgres_withingroup_sql(generator: Generator, expression: exp.WithinGroup) -> str:
    if isinstance(expression.this, vexp.ListAgg):
        aggregate = _postgres_listagg_expression(
            generator,
            expression.this,
            expression.expression,
        )
        return generator.sql(aggregate)

    return generator.withingroup_sql(expression)


def _postgres_group_sql(generator: Generator, expression: vexp.VerticaGroup) -> str:
    """Lower an ordinary-only Vertica GROUP BY without dropping custom fields."""

    expressions = expression.args.get("expressions")
    if (
        set(expression.args) != {"expressions"}
        or not isinstance(expressions, list)
        or not expressions
        or not all(isinstance(item, exp.Expr) for item in expressions)
        or any(isinstance(item, (exp.Cube, exp.Rollup, exp.GroupingSets)) for item in expressions)
    ):
        raise ValueError("Unsupported expression type VerticaGroup")

    return generator.group_sql(exp.Group(expressions=[item.copy() for item in expressions]))


def _postgres_create_sql(generator: Generator, expression: exp.Create) -> str:
    """Lower only explicit LOCAL Vertica temporary CREATE trees to PostgreSQL."""

    properties = expression.args.get("properties")
    if not isinstance(properties, exp.Properties):
        return generator.create_sql(expression)

    property_types = [type(prop) for prop in properties.expressions]
    if vexp.VerticaGlobalProperty in property_types and (
        property_types.count(vexp.VerticaGlobalProperty) != 1
        or property_types.count(exp.TemporaryProperty) != 1
    ):
        raise ValueError("Unsupported expression type VerticaGlobalProperty")
    if vexp.VerticaGlobalProperty in property_types:
        raise ValueError("PostgreSQL cannot preserve Vertica GLOBAL temporary-table visibility")

    local_count = property_types.count(vexp.LocalProperty)
    if not local_count:
        return generator.create_sql(expression)

    if (
        type(expression) is not exp.Create
        or expression.args.get("kind") != "TABLE"
        or local_count != 1
        or property_types.count(exp.TemporaryProperty) != 1
        or exp.GlobalProperty in property_types
    ):
        raise ValueError("Unsupported expression type LocalProperty")

    lowered = expression.copy()
    lowered_properties = lowered.args.get("properties")
    assert isinstance(lowered_properties, exp.Properties)
    lowered_properties.set(
        "expressions",
        [
            prop
            for prop in lowered_properties.expressions
            if not isinstance(prop, vexp.LocalProperty)
        ],
    )
    return generator.create_sql(lowered)


def _postgres_vertica_ordered_sql(generator: Generator, expression: vexp.VerticaOrdered) -> str:
    """Render source-explicit FIRST/LAST without consulting PostgreSQL defaults."""

    this = expression.args.get("this")
    desc = expression.args.get("desc")
    nulls_first = expression.args.get("nulls_first")
    nulls = expression.args.get("nulls")
    if (
        not isinstance(this, exp.Expr)
        or desc not in {None, False, True}
        or not isinstance(desc, (bool, type(None)))
        or not isinstance(nulls_first, bool)
        or not isinstance(nulls, exp.Var)
        or nulls.name not in {"FIRST", "LAST"}
        or nulls_first is not (nulls.name == "FIRST")
        or expression.args.get("with_fill") is not None
        or any(
            key not in {"this", "desc", "nulls_first", "nulls", "with_fill"}
            for key in expression.args
        )
    ):
        raise ValueError("PostgreSQL supports only valid explicit NULLS FIRST or NULLS LAST")

    direction = " DESC" if desc else (" ASC" if desc is False else "")
    return f"{generator.sql(this)}{direction} NULLS {nulls.name}"


def patch_postgres_transforms() -> None:
    """Register semantics-preserving Vertica expression subsets with PostgreSQL.

    SQLGlot caches generator dispatch tables after first use, so invalidate an
    already-built PostgreSQL table as well as updating the class transforms.
    """

    from sqlglot import generator as generator_module
    from sqlglot.generators.postgres import PostgresGenerator

    PostgresGenerator.TRANSFORMS = {
        **PostgresGenerator.TRANSFORMS,
        exp.Create: _postgres_create_sql,
        exp.WithinGroup: _postgres_withingroup_sql,
        vexp.ListAgg: _postgres_listagg_sql,
        vexp.VerticaGroup: _postgres_group_sql,
        vexp.VerticaOrdered: _postgres_vertica_ordered_sql,
    }
    generator_module._DISPATCH_CACHE.pop(PostgresGenerator, None)
