"""Safe foreign-dialect transforms for Vertica-specific expression wrappers."""

from __future__ import annotations

import typing as t

from sqlglot import exp
from sqlglot.generator import Generator
from sqlglot.optimizer.annotate_types import annotate_types

from sqlglot_vertica import expressions as vexp

_PostgresSelectTransform = t.Callable[[Generator, exp.Expr], str]
_POSTGRES_SELECT_TRANSFORM: _PostgresSelectTransform | None = None
_POSTGRES_SET_TRANSFORMS: dict[type[exp.Expr], _PostgresSelectTransform] = {}


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


def _partitioned_limit_name_factory(expression: exp.Select) -> t.Callable[[str], str]:
    taken = {name.lower() for name in expression.named_selects if name}

    def fresh(prefix: str) -> str:
        index = 0
        candidate = prefix
        while candidate.lower() in taken:
            index += 1
            candidate = f"{prefix}_{index}"
        taken.add(candidate.lower())
        return candidate

    return fresh


def _partitioned_limit_output_identifier(selection: exp.Expr) -> exp.Identifier:
    if isinstance(selection, exp.Alias):
        alias = selection.args.get("alias")
        if isinstance(alias, exp.Identifier) and alias.name:
            return alias.copy()
    elif isinstance(selection, exp.Column) and isinstance(selection.this, exp.Identifier):
        if selection.name:
            return selection.this.copy()

    raise ValueError(
        "PostgreSQL partitioned LIMIT requires every output expression to have a stable name"
    )


def _lower_postgres_partitioned_limit(expression: exp.Select) -> exp.Select:
    """Build base, ranking, and filtering queries without mutating the Vertica tree."""

    limit = expression.args.get("limit")
    if not isinstance(limit, vexp.PartitionedLimit):
        return expression

    if type(expression) is not exp.Select or expression.args.get("into") is not None:
        raise ValueError("PostgreSQL cannot safely lower partitioned LIMIT on SELECT INTO")
    if expression.args.get("timeseries") is not None or expression.args.get("match") is not None:
        raise ValueError(
            "PostgreSQL cannot safely lower partitioned LIMIT on Vertica event-series queries"
        )
    if expression.args.get("locks") is not None:
        raise ValueError(
            "PostgreSQL cannot preserve a Vertica lock tail through partitioned LIMIT lowering"
        )
    if (
        set(limit.args) != {"expression", "partition_by", "order"}
        or not isinstance(limit.expression, exp.Literal)
        or limit.expression.is_string
        or not isinstance(limit.expression.this, str)
        or not limit.expression.this.isdigit()
        or limit.expression.this.strip("0") == ""
        or not isinstance(limit.args.get("partition_by"), list)
        or not limit.args["partition_by"]
        or any(not isinstance(item, exp.Expr) for item in limit.args["partition_by"])
        or not isinstance(limit.args.get("order"), exp.Order)
        or not limit.args["order"].expressions
    ):
        raise ValueError(
            "PostgreSQL partitioned LIMIT requires a positive integer, PARTITION BY, and ORDER BY"
        )

    selections = expression.expressions
    if not selections or any(selection.is_star for selection in selections):
        raise ValueError(
            "PostgreSQL partitioned LIMIT cannot preserve a star projection without schema"
        )

    fresh = _partitioned_limit_name_factory(expression)
    base_alias = fresh("_vertica_pl_source")
    ranked_alias = fresh("_vertica_pl_ranked")
    helper_alias = fresh("_vertica_pl_row_number")

    lowered_base = expression.copy()
    root_comments = lowered_base.pop_comments()
    lowered_limit = lowered_base.args.pop("limit")
    assert isinstance(lowered_limit, vexp.PartitionedLimit)
    outer_order = lowered_base.args.pop("order", None)
    outer_offset = lowered_base.args.pop("offset", None)
    lowered_base.args.pop("locks", None)

    base_projections: list[exp.Expr] = []
    outer_projections: list[exp.Expr] = []
    projection_internal_names: list[str] = []
    output_names: dict[str, list[str]] = {}
    for index, selection in enumerate(selections):
        output_identifier = _partitioned_limit_output_identifier(selection)
        internal_name = fresh(f"_vertica_pl_output_{index}")
        projection_internal_names.append(internal_name)
        value = selection.this if isinstance(selection, exp.Alias) else selection
        base_projections.append(exp.alias_(value.copy(), internal_name))
        outer_projections.append(
            exp.Alias(
                this=exp.column(internal_name, table=ranked_alias),
                alias=output_identifier,
            )
        )
        output_names.setdefault(output_identifier.name.lower(), []).append(internal_name)

    hidden_names: list[str] = []

    def resolve_window_expression(item: exp.Expr) -> exp.Column:
        internal_name: str | None = None
        if (
            isinstance(item, exp.Literal)
            and not item.is_string
            and isinstance(item.this, str)
            and item.this.isdigit()
        ):
            digits = item.this.lstrip("0") or "0"
            maximum = str(len(projection_internal_names))
            if len(digits) < len(maximum) or (len(digits) == len(maximum) and digits <= maximum):
                ordinal = int(digits)
                if ordinal:
                    internal_name = projection_internal_names[ordinal - 1]
        elif isinstance(item, exp.Column) and not item.table:
            matches = output_names.get(item.name.lower(), [])
            if len(matches) > 1:
                raise ValueError(
                    "PostgreSQL partitioned LIMIT cannot resolve a duplicate SELECT alias"
                )
            if matches:
                internal_name = matches[0]

        if internal_name is None:
            internal_name = fresh("_vertica_pl_hidden")
            hidden_names.append(internal_name)
            base_projections.append(exp.alias_(item.copy(), internal_name))

        resolved = exp.column(internal_name, table=base_alias)
        resolved.add_comments(item.comments)
        return resolved

    partition_by = [resolve_window_expression(item) for item in lowered_limit.args["partition_by"]]
    limit_order = t.cast(exp.Order, lowered_limit.args["order"])
    window_order = limit_order.copy()
    for ordered in window_order.expressions:
        if not isinstance(ordered, exp.Ordered) or not isinstance(ordered.this, exp.Expr):
            raise ValueError("PostgreSQL partitioned LIMIT requires canonical ORDER BY items")
        ordered.set("this", resolve_window_expression(ordered.this))

    resolved_outer_order: exp.Order | None = None
    if outer_order is not None:
        if not isinstance(outer_order, exp.Order):
            raise ValueError("PostgreSQL partitioned LIMIT requires a canonical outer ORDER BY")
        resolved_outer_order = outer_order.copy()
        for ordered in resolved_outer_order.expressions:
            if not isinstance(ordered, exp.Ordered) or not isinstance(ordered.this, exp.Expr):
                raise ValueError("PostgreSQL partitioned LIMIT requires canonical outer ordering")
            resolved = resolve_window_expression(ordered.this)
            resolved.set("table", exp.to_identifier(ranked_alias))
            ordered.set("this", resolved)

    if lowered_base.args.get("distinct") is not None and hidden_names:
        raise ValueError(
            "PostgreSQL partitioned LIMIT with DISTINCT requires partition and order expressions "
            "to be projected aliases or ordinals"
        )

    lowered_base.set("expressions", base_projections)
    ranked_projections: list[exp.Expr] = [
        exp.column(projection.alias, table=base_alias)
        for projection in base_projections
        if isinstance(projection, exp.Alias)
    ]
    row_number = exp.Window(
        this=exp.RowNumber(),
        partition_by=partition_by,
        order=window_order,
    )
    row_number.add_comments(lowered_limit.comments)
    ranked_projections.append(exp.alias_(row_number, helper_alias))

    ranked = exp.select(*ranked_projections, copy=False).from_(
        lowered_base.subquery(base_alias, copy=False), copy=False
    )
    result = exp.select(*outer_projections, copy=False).from_(
        ranked.subquery(ranked_alias, copy=False), copy=False
    )
    result.where(
        exp.LTE(
            this=exp.column(helper_alias, table=ranked_alias),
            expression=lowered_limit.expression.copy(),
        ),
        copy=False,
    )
    if resolved_outer_order is not None:
        result.set("order", resolved_outer_order)
    if outer_offset is not None:
        if not isinstance(outer_offset, exp.Offset):
            raise ValueError("PostgreSQL partitioned LIMIT requires a canonical OFFSET")
        result.set("offset", outer_offset.copy())
    result.add_comments(root_comments)
    return result


def _postgres_select_sql(generator: Generator, expression: exp.Expr) -> str:
    original = _POSTGRES_SELECT_TRANSFORM
    if original is None:
        raise RuntimeError("PostgreSQL SELECT transform was not initialized")
    if not isinstance(expression, exp.Select):
        raise ValueError("PostgreSQL partitioned LIMIT lowering requires SELECT")
    from sqlglot.generators.postgres import PostgresGenerator

    if type(generator) is not PostgresGenerator:
        return original(generator, expression)
    return original(generator, _lower_postgres_partitioned_limit(expression))


def _postgres_set_operation_sql(generator: Generator, expression: exp.Expr) -> str:
    original = _POSTGRES_SET_TRANSFORMS.get(type(expression))
    if original is None:
        raise RuntimeError("PostgreSQL set-operation transform was not initialized")
    if isinstance(expression.args.get("limit"), vexp.PartitionedLimit):
        raise ValueError("PostgreSQL cannot safely lower partitioned LIMIT on a set-operation root")
    return original(generator, expression)


def _postgres_unsafe_partitioned_limit_owner_sql(generator: Generator, expression: exp.Expr) -> str:
    if expression.find(vexp.PartitionedLimit):
        raise ValueError(
            f"PostgreSQL cannot safely lower partitioned LIMIT on {type(expression).__name__}"
        )
    raise ValueError(f"Unsupported expression type {type(expression).__name__}")


def _postgres_detached_partitioned_limit_sql(
    generator: Generator, expression: vexp.PartitionedLimit
) -> str:
    raise ValueError("PostgreSQL partitioned LIMIT lowering requires a complete SELECT owner")


def patch_postgres_transforms() -> None:
    """Register semantics-preserving Vertica expression subsets with PostgreSQL.

    SQLGlot caches generator dispatch tables after first use, so invalidate an
    already-built PostgreSQL table as well as updating the class transforms.
    """

    from sqlglot import generator as generator_module
    from sqlglot.generators.postgres import PostgresGenerator

    global _POSTGRES_SELECT_TRANSFORM
    current_select_transform = PostgresGenerator.TRANSFORMS[exp.Select]
    if current_select_transform is not _postgres_select_sql:
        _POSTGRES_SELECT_TRANSFORM = t.cast(_PostgresSelectTransform, current_select_transform)
    for set_type in (exp.Union, exp.Intersect, exp.Except):
        current_set_transform = PostgresGenerator.TRANSFORMS[set_type]
        if current_set_transform is not _postgres_set_operation_sql:
            _POSTGRES_SET_TRANSFORMS[set_type] = t.cast(
                _PostgresSelectTransform, current_set_transform
            )

    PostgresGenerator.TRANSFORMS = {
        **PostgresGenerator.TRANSFORMS,
        exp.Create: _postgres_create_sql,
        exp.Except: _postgres_set_operation_sql,
        exp.Intersect: _postgres_set_operation_sql,
        exp.Select: _postgres_select_sql,
        exp.Union: _postgres_set_operation_sql,
        exp.WithinGroup: _postgres_withingroup_sql,
        vexp.ListAgg: _postgres_listagg_sql,
        vexp.StatementTimestamp: _postgres_statement_timestamp_sql,
        vexp.PartitionedLimit: _postgres_detached_partitioned_limit_sql,
        vexp.SelectInto: _postgres_unsafe_partitioned_limit_owner_sql,
        vexp.TimeseriesSelect: _postgres_unsafe_partitioned_limit_owner_sql,
        vexp.AtEpochSelect: _postgres_unsafe_partitioned_limit_owner_sql,
        vexp.AtEpochUnion: _postgres_unsafe_partitioned_limit_owner_sql,
        vexp.AtEpochIntersect: _postgres_unsafe_partitioned_limit_owner_sql,
        vexp.AtEpochExcept: _postgres_unsafe_partitioned_limit_owner_sql,
        vexp.UtcStatementTimestamp: _postgres_utc_statement_timestamp_sql,
        vexp.VerticaGroup: _postgres_group_sql,
        vexp.VerticaOrdered: _postgres_vertica_ordered_sql,
        vexp.VerticaRegexpLike: _postgres_vertica_regexp_like_sql,
        vexp.VerticaToChar: _postgres_vertica_to_char_sql,
    }
    generator_module._DISPATCH_CACHE.pop(PostgresGenerator, None)
