"""Safe foreign-dialect transforms for Vertica-specific expression wrappers."""

from __future__ import annotations

from sqlglot import exp
from sqlglot.generator import Generator
from sqlglot.optimizer.annotate_types import annotate_types

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


def _postgres_statement_timestamp_sql(
    generator: Generator, expression: vexp.StatementTimestamp
) -> str:
    """Preserve Vertica's statement-start, session-local TIMESTAMP contract."""

    if type(expression) is not vexp.StatementTimestamp or expression.args:
        raise ValueError("PostgreSQL requires a valid Vertica statement timestamp")

    return generator.sql(exp.cast(exp.Anonymous(this="STATEMENT_TIMESTAMP"), exp.DType.TIMESTAMP))


def _postgres_utc_statement_timestamp_sql(
    generator: Generator, expression: vexp.UtcStatementTimestamp
) -> str:
    """Preserve Vertica's statement-start UTC TIMESTAMP contract."""

    if type(expression) is not vexp.UtcStatementTimestamp or expression.args:
        raise ValueError("PostgreSQL requires a valid Vertica UTC statement timestamp")

    return generator.sql(
        exp.cast(
            exp.AtTimeZone(
                this=exp.Anonymous(this="STATEMENT_TIMESTAMP"),
                zone=exp.Literal.string("UTC"),
            ),
            exp.DType.TIMESTAMP,
        )
    )


_POSTGRES_SAFE_TO_CHAR_INTEGER_TYPES = {
    exp.DType.TINYINT,
    exp.DType.SMALLINT,
    exp.DType.INT,
    exp.DType.BIGINT,
}


def _postgres_vertica_to_char_sql(generator: Generator, expression: vexp.VerticaToChar) -> str:
    """Lower only statically integral one-argument TO_CHAR calls to text casts."""

    function = expression.args.get("this")
    if (
        set(expression.args) != {"this"}
        or not isinstance(function, exp.Anonymous)
        or function.name.upper() != "TO_CHAR"
        or set(function.args) != {"this", "expressions"}
        or len(function.expressions) != 1
    ):
        raise ValueError("PostgreSQL requires a valid one-argument Vertica TO_CHAR call")

    value = function.expressions[0]
    annotated = annotate_types(value.copy(), dialect="vertica")
    if annotated.type.this not in _POSTGRES_SAFE_TO_CHAR_INTEGER_TYPES:
        raise ValueError(
            "PostgreSQL text conversion is proven only for statically integral "
            "one-argument Vertica TO_CHAR inputs"
        )

    return generator.sql(exp.cast(value.copy(), exp.DType.TEXT))


_REGEX_META_CHARACTERS = frozenset(r".\\^$*+?{}[]|()")


def _postgres_vertica_regexp_like_sql(
    generator: Generator, expression: vexp.VerticaRegexpLike
) -> str:
    """Lower the engine-independent literal-pattern subset to POSITION."""

    predicate = expression.args.get("this")
    modifiers = expression.args.get("modifiers") or []
    if (
        not set(expression.args) <= {"this", "modifiers"}
        or "this" not in expression.args
        or not isinstance(predicate, exp.RegexpLike)
        or set(predicate.args) != {"this", "expression"}
        or not isinstance(predicate.this, exp.Expr)
        or not isinstance(predicate.expression, exp.Literal)
        or not predicate.expression.is_string
        or not isinstance(modifiers, list)
        or any(
            not isinstance(modifier, exp.Literal) or not modifier.is_string
            for modifier in modifiers
        )
        or [modifier.this for modifier in modifiers] not in ([], ["c"])
    ):
        raise ValueError(
            "PostgreSQL REGEXP_LIKE lowering requires a literal pattern and omitted or 'c' mode"
        )

    pattern = predicate.expression.this
    try:
        pattern.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("PostgreSQL REGEXP_LIKE literal pattern must be valid UTF-8") from error

    if any(character in _REGEX_META_CHARACTERS for character in pattern):
        raise ValueError(
            "PostgreSQL cannot preserve Vertica Perl REGEXP_LIKE metacharacter semantics"
        )

    return generator.sql(
        exp.GT(
            this=exp.StrPosition(
                this=predicate.this.copy(),
                substr=predicate.expression.copy(),
            ),
            expression=exp.Literal.number(0),
        )
    )


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
        vexp.StatementTimestamp: _postgres_statement_timestamp_sql,
        vexp.UtcStatementTimestamp: _postgres_utc_statement_timestamp_sql,
        vexp.VerticaGroup: _postgres_group_sql,
        vexp.VerticaOrdered: _postgres_vertica_ordered_sql,
        vexp.VerticaRegexpLike: _postgres_vertica_regexp_like_sql,
        vexp.VerticaToChar: _postgres_vertica_to_char_sql,
    }
    generator_module._DISPATCH_CACHE.pop(PostgresGenerator, None)
