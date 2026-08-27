"""Q38 PostgreSQL lowering for Vertica partitioned LIMIT."""

from __future__ import annotations

import subprocess
import sys

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import UnsupportedError
from sqlglot.lineage import lineage
from sqlglot.optimizer import optimize
from sqlglot.optimizer.annotate_types import annotate_types
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from sqlglot_vertica import expressions as vexp

ALL_LEVELS = tuple(ErrorLevel)


def _postgres_sql(source: str, level: ErrorLevel = ErrorLevel.RAISE) -> str:
    expression = parse_one(source, read="vertica")
    before = expression.dump()
    target = expression.sql(dialect="postgres", unsupported_level=level)
    assert expression.dump() == before
    parse_one(target, read="postgres")
    return target


@pytest.mark.parametrize("level", ALL_LEVELS)
def test_report_fixture_lowers_to_private_row_number_filter(level: ErrorLevel) -> None:
    target = _postgres_sql(
        "SELECT 1 AS x LIMIT 1 OVER (PARTITION BY x ORDER BY x)",
        level,
    )
    expression = parse_one(target, read="postgres")

    assert expression.named_selects == ["x"]
    assert len(list(expression.find_all(exp.Subquery))) == 2
    window = expression.find(exp.Window)
    assert isinstance(window, exp.Window)
    assert isinstance(window.this, exp.RowNumber)
    assert isinstance(expression.args.get("where"), exp.Where)
    assert "_vertica_pl_row_number" not in expression.named_selects


@pytest.mark.parametrize(
    "source",
    [
        "SELECT customer_id, order_id, total FROM orders "
        "LIMIT 3 OVER (PARTITION BY customer_id ORDER BY total DESC)",
        "SELECT a AS x, b AS y, c AS z FROM t "
        "LIMIT 2 OVER (PARTITION BY x, y ORDER BY z DESC, x ASC)",
        "SELECT a AS x, b AS y FROM t LIMIT 2 OVER (PARTITION BY 1 ORDER BY 2 DESC)",
        "SELECT a AS x, b FROM t LIMIT 2 OVER (PARTITION BY a + 1 ORDER BY b * 2 DESC)",
        "SELECT a, b FROM t LIMIT 2 OVER (PARTITION BY a ORDER BY b DESC NULLS FIRST)",
    ],
)
def test_partition_and_order_shapes_lower_without_exposing_helpers(source: str) -> None:
    source_expression = parse_one(source, read="vertica")
    target = _postgres_sql(source)
    target_expression = parse_one(target, read="postgres")

    assert target_expression.named_selects == source_expression.named_selects
    assert isinstance(target_expression.find(exp.RowNumber), exp.RowNumber)
    assert all("_vertica_pl_" not in name for name in target_expression.named_selects)


@pytest.mark.parametrize(
    "source",
    [
        "SELECT o.customer_id AS customer_id, SUM(o.total) AS total "
        "FROM orders AS o JOIN customers AS c ON o.customer_id = c.id "
        "WHERE c.active = 1 GROUP BY o.customer_id HAVING SUM(o.total) > 0 "
        "LIMIT 2 OVER (PARTITION BY customer_id ORDER BY total DESC)",
        "SELECT DISTINCT a FROM t LIMIT 1 OVER (PARTITION BY a ORDER BY a)",
        "WITH q AS (SELECT a, b FROM t) SELECT a, b FROM q "
        "LIMIT 1 OVER (PARTITION BY a ORDER BY b)",
        "SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.a = t.a) "
        "LIMIT 1 OVER (PARTITION BY a ORDER BY a)",
        "SELECT a FROM t UNION ALL (SELECT a FROM u LIMIT 1 OVER (PARTITION BY a ORDER BY a))",
    ],
)
def test_group_join_distinct_cte_subquery_and_set_branch_owners(source: str) -> None:
    target = _postgres_sql(source)
    assert "ROW_NUMBER() OVER" in target
    assert "_vertica_pl_row_number" in target


def test_outer_order_and_offset_are_applied_after_private_filter() -> None:
    target = _postgres_sql(
        "SELECT a, b FROM t ORDER BY b DESC LIMIT 1 OVER (PARTITION BY a ORDER BY b) OFFSET 2"
    )

    where_position = target.rindex(" WHERE ")
    order_position = target.rindex(" ORDER BY ")
    offset_position = target.rindex(" OFFSET ")
    assert where_position < order_position < offset_position


def test_volatile_projection_alias_is_evaluated_once() -> None:
    target = _postgres_sql("SELECT RANDOM() AS r FROM t LIMIT 1 OVER (PARTITION BY r ORDER BY r)")

    assert target.count("RANDOM()") == 1


def test_comments_and_helper_name_collisions_remain_safe() -> None:
    source = (
        "/* root */ SELECT a AS _vertica_pl_row_number, b AS _vertica_pl_source "
        "FROM t LIMIT /* top per group */ 1 OVER ("
        "PARTITION BY _vertica_pl_source ORDER BY _vertica_pl_row_number)"
    )
    target = _postgres_sql(source)
    expression = parse_one(target, read="postgres")

    assert "root" in target
    assert "top per group" in target
    assert expression.named_selects == ["_vertica_pl_row_number", "_vertica_pl_source"]
    helper_aliases = [
        alias.alias
        for alias in expression.find_all(exp.Alias)
        if isinstance(alias.this, exp.Window)
    ]
    assert helper_aliases
    assert helper_aliases[0] not in expression.named_selects


def test_source_analysis_and_tree_operations_remain_unchanged() -> None:
    source = (
        "SELECT customer_id AS customer_id, total AS total FROM orders "
        "LIMIT 2 OVER (PARTITION BY customer_id ORDER BY total DESC)"
    )
    expression = parse_one(source, read="vertica")
    schema = {"orders": {"customer_id": "INT", "total": "DECIMAL"}}

    trees = (
        exp.Expr.load(expression.dump()),
        expression.copy(),
        expression.transform(lambda node: node),
        qualify(expression.copy(), dialect="vertica", schema=schema),
        optimize(expression.copy(), dialect="vertica", schema=schema),
        annotate_types(expression.copy(), dialect="vertica", schema=schema),
    )
    for tree in trees:
        assert isinstance(tree.find(vexp.PartitionedLimit), vexp.PartitionedLimit)
        tree.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)

    assert list(traverse_scope(expression))
    assert lineage("total", expression, dialect="vertica", schema=schema).downstream


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            "SELECT * FROM t LIMIT 1 OVER (PARTITION BY a ORDER BY b)",
            "star projection",
        ),
        (
            "SELECT a + 1 FROM t LIMIT 1 OVER (PARTITION BY a ORDER BY a)",
            "stable name",
        ),
        (
            "SELECT a AS x, b AS x FROM t LIMIT 1 OVER (PARTITION BY x ORDER BY x)",
            "duplicate SELECT alias",
        ),
        (
            "SELECT DISTINCT a FROM t LIMIT 1 OVER (PARTITION BY b ORDER BY b)",
            "DISTINCT requires",
        ),
        (
            "SELECT a FROM t LIMIT 1 OVER (PARTITION BY a ORDER BY a) FOR UPDATE",
            "lock tail",
        ),
        (
            "SELECT a INTO TABLE sink FROM t LIMIT 1 OVER (PARTITION BY a ORDER BY a)",
            "SelectInto",
        ),
        (
            "AT EPOCH LATEST SELECT a FROM t LIMIT 1 OVER (PARTITION BY a ORDER BY a)",
            "AtEpochSelect",
        ),
        (
            "SELECT slice_time FROM t TIMESERIES slice_time AS '1 minute' "
            "OVER (ORDER BY ts) LIMIT 1 OVER (PARTITION BY slice_time ORDER BY slice_time)",
            "TimeseriesSelect",
        ),
        (
            "SELECT a FROM t UNION ALL SELECT a FROM u LIMIT 1 OVER (PARTITION BY a ORDER BY a)",
            "set-operation root",
        ),
    ],
)
@pytest.mark.parametrize("level", ALL_LEVELS)
def test_unsafe_query_shapes_fail_atomically(source: str, message: str, level: ErrorLevel) -> None:
    expression = parse_one(source, read="vertica")
    with pytest.raises(ValueError, match=message):
        expression.sql(dialect="postgres", unsupported_level=level)


@pytest.mark.parametrize("level", ALL_LEVELS)
def test_detached_and_malformed_partitioned_limits_fail_atomically(level: ErrorLevel) -> None:
    detached = vexp.PartitionedLimit(
        expression=exp.Literal.number(1),
        partition_by=[exp.column("a")],
        order=exp.Order(expressions=[exp.Ordered(this=exp.column("a"))]),
    )
    with pytest.raises(ValueError, match="complete SELECT owner"):
        detached.sql(dialect="postgres", unsupported_level=level)

    malformed = parse_one(
        "SELECT a FROM t LIMIT 1 OVER (PARTITION BY a ORDER BY a)", read="vertica"
    )
    malformed_limit = malformed.args["limit"]
    assert isinstance(malformed_limit, vexp.PartitionedLimit)
    malformed_limit.set("partition_by", [])
    with pytest.raises(ValueError, match="positive integer, PARTITION BY, and ORDER BY"):
        malformed.sql(dialect="postgres", unsupported_level=level)


@pytest.mark.parametrize("dialect", ("duckdb", "mysql", "sqlite"))
def test_other_foreign_dialects_remain_atomic(dialect: str) -> None:
    expression = parse_one(
        "SELECT a FROM t LIMIT 1 OVER (PARTITION BY a ORDER BY a)", read="vertica"
    )
    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize("foreign_first", (False, True))
def test_postgres_patch_survives_import_order_and_dispatch_cache(foreign_first: bool) -> None:
    prefix = (
        "from sqlglot import exp; from sqlglot.generators.postgres import PostgresGenerator; "
        "PostgresGenerator().generate(exp.select('x')); "
        if foreign_first
        else ""
    )
    code = prefix + (
        "from sqlglot import ErrorLevel, parse_one; import sqlglot_vertica; "
        "tree = parse_one('SELECT 1 AS x LIMIT 1 OVER (PARTITION BY x ORDER BY x)', "
        "read='vertica'); target = tree.sql(dialect='postgres', "
        "unsupported_level=ErrorLevel.RAISE); assert 'ROW_NUMBER() OVER' in target; "
        "assert parse_one(target, read='postgres').named_selects == ['x']"
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
