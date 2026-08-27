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


def patch_postgres_transforms() -> None:
    """Register semantics-preserving Vertica expression subsets with PostgreSQL.

    SQLGlot caches generator dispatch tables after first use, so invalidate an
    already-built PostgreSQL table as well as updating the class transforms.
    """

    from sqlglot import generator as generator_module
    from sqlglot.generators.postgres import PostgresGenerator

    PostgresGenerator.TRANSFORMS = {
        **PostgresGenerator.TRANSFORMS,
        exp.WithinGroup: _postgres_withingroup_sql,
        vexp.ListAgg: _postgres_listagg_sql,
        vexp.VerticaGroup: _postgres_group_sql,
    }
    generator_module._DISPATCH_CACHE.pop(PostgresGenerator, None)
