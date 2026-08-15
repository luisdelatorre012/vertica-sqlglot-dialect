"""Optimizer, typing, serialization, and foreign-generation contracts."""

from __future__ import annotations

import inspect

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import UnsupportedError
from sqlglot.optimizer import optimize
from sqlglot.optimizer.annotate_types import annotate_types

from sqlglot_vertica import expressions as vexp

CUSTOM_EXPRESSION_TYPES = [
    expression_type
    for _, expression_type in inspect.getmembers(vexp, inspect.isclass)
    if expression_type.__module__ == vexp.__name__ and issubclass(expression_type, exp.Expr)
]


@pytest.mark.parametrize(
    "expression_type",
    CUSTOM_EXPRESSION_TYPES,
    ids=lambda expression_type: expression_type.__name__,
)
def test_every_custom_expression_fails_explicitly_in_postgres(
    expression_type: type[exp.Expr],
) -> None:
    """A newly added custom node must not inherit a generic SQL function fallback."""

    with pytest.raises((UnsupportedError, ValueError)):
        expression_type().sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT SET[1, 2]",
        "SELECT GETDATE()",
        "SELECT GETUTCDATE()",
        "SELECT LISTAGG(city USING PARAMETERS separator=',') FROM places",
    ],
)
def test_vertica_only_values_do_not_emit_invented_postgres_functions(sql: str) -> None:
    expression = parse_one(sql, read="vertica")

    with pytest.raises(ValueError, match="Unsupported expression type"):
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


def test_timeseries_is_optimizer_visible_and_foreign_generation_is_atomic() -> None:
    sql = (
        "SELECT slice_time, TS_FIRST_VALUE(value, 'const') FROM ticks "
        "TIMESERIES slice_time AS '1 minute' "
        "OVER (PARTITION BY symbol ORDER BY ts) ORDER BY slice_time"
    )
    expression = parse_one(sql, read="vertica")

    assert isinstance(expression, vexp.TimeseriesSelect)
    assert len(list(expression.find_all(vexp.TimeseriesSlice))) == 2

    with pytest.raises(ValueError, match="TimeseriesSelect"):
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)

    optimized = optimize(
        expression,
        dialect="vertica",
        schema={
            "ticks": {
                "value": "INT",
                "symbol": "VARCHAR",
                "ts": "TIMESTAMP",
            }
        },
    )

    assert isinstance(optimized, vexp.TimeseriesSelect)
    slices = list(optimized.find_all(vexp.TimeseriesSlice))
    assert len(slices) == 2
    assert all(slice_ref.is_type(exp.DType.TIMESTAMP) for slice_ref in slices)
    assert "TIMESERIES" in optimized.sql(dialect="vertica")

    source_columns = {
        column.name: column.table
        for column in optimized.find_all(exp.Column)
        if column.name in {"value", "symbol", "ts"}
    }
    assert source_columns == {"value": "ticks", "symbol": "ticks", "ts": "ticks"}

    with pytest.raises(ValueError, match="TimeseriesSelect"):
        optimized.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)

    restored = exp.Expr.load(optimized.dump())
    assert restored == optimized
    assert isinstance(restored, vexp.TimeseriesSelect)


def test_materialized_with_survives_stock_optimizer_and_serialization() -> None:
    expression = parse_one(
        "WITH /*+ENABLE_WITH_CLAUSE_MATERIALIZATION*/ x AS (SELECT a FROM t) SELECT a FROM x",
        read="vertica",
    )

    assert isinstance(expression.args["with_"], vexp.WithHint)
    assert len(list(expression.find_all(vexp.MaterializedWithMarker))) == 1

    optimized = optimize(
        expression,
        dialect="vertica",
        schema={"t": {"a": "INT"}},
    )

    # SQLGlot's eliminate_subqueries reconstructs exp.With, but the plugin
    # marker remains on the CTE query and blocks merge_subqueries from inlining.
    assert type(optimized.args["with_"]) is exp.With
    assert len(list(optimized.find_all(vexp.MaterializedWithMarker))) == 1
    assert {table.name for table in optimized.find_all(exp.Table)} == {"t", "x"}

    generated = optimized.sql(dialect="vertica")
    assert generated.count("ENABLE_WITH_CLAUSE_MATERIALIZATION") == 1
    assert generated.startswith("WITH /*+ ENABLE_WITH_CLAUSE_MATERIALIZATION */")

    restored = exp.Expr.load(optimized.dump())
    assert restored == optimized
    assert len(list(restored.find_all(vexp.MaterializedWithMarker))) == 1

    with pytest.raises(ValueError, match="MaterializedWithMarker"):
        optimized.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


def test_custom_scalar_expression_metadata_and_aggregate_visibility() -> None:
    expression = annotate_types(
        parse_one(
            "SELECT SET[1, 2.5], "
            "ROW(1) AS row_value(field_name), "
            "INTERVAL(3) '1' DAY, "
            "GETDATE(), GETUTCDATE(), "
            "LISTAGG(a USING PARAMETERS separator=','), "
            "a INTERPOLATE PREVIOUS VALUE b "
            "FROM t",
            read="vertica",
        ),
        dialect="vertica",
        schema={"t": {"a": "INT", "b": "INT"}},
    )

    expected_types = [
        exp.DType.SET,
        exp.DType.STRUCT,
        exp.DType.INTERVAL,
        exp.DType.TIMESTAMP,
        exp.DType.TIMESTAMP,
        exp.DType.VARCHAR,
        exp.DType.BOOLEAN,
    ]
    assert [item.type.this for item in expression.expressions] == expected_types

    set_literal = expression.find(vexp.SetLiteral)
    assert set_literal is not None and not isinstance(set_literal, exp.Array)
    assert set_literal.type.expressions[0].is_type(exp.DType.DOUBLE)

    listagg = expression.find(vexp.ListAgg)
    assert listagg is not None and isinstance(listagg.this, exp.GroupConcat)
    assert list(listagg.find_all(exp.AggFunc)) == [listagg.this]
    assert not isinstance(listagg, exp.Func)

    assert not isinstance(expression.find(vexp.StatementTimestamp), exp.Func)
    assert not isinstance(expression.find(vexp.UtcStatementTimestamp), exp.Func)
