"""Vertica WITH/CTE query-expression and placement regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.lineage import lineage
from sqlglot.optimizer import optimize
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip

ALL_PARSE_LEVELS = [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]


@pytest.mark.parametrize(
    "sql",
    [
        "WITH c AS (SELECT 1 AS x) SELECT x FROM c",
        "WITH a AS (SELECT 1 AS x), b AS (SELECT x FROM a) SELECT x FROM b",
        "WITH c AS (WITH d AS (SELECT 1 AS x) SELECT x FROM d) SELECT x FROM c",
        "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c WHERE x < 2) "
        "SELECT x FROM c",
        "WITH c AS (SELECT 1 UNION SELECT 2 INTERSECT SELECT 2) SELECT * FROM c",
        "WITH c AS (SELECT ts FROM events TIMESERIES slice AS '1 minute' "
        "OVER (ORDER BY ts)) SELECT * FROM c",
        "INSERT INTO target WITH c AS (SELECT 1 AS x) SELECT x FROM c",
    ],
)
def test_documented_cte_query_forms_roundtrip(sql: str) -> None:
    assert_roundtrip(sql, sql)


def test_clause_level_materialization_hint_and_recursive_cte_survive() -> None:
    expression = assert_roundtrip(
        "WITH /*+ENABLE_WITH_CLAUSE_MATERIALIZATION*/ RECURSIVE "
        "c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c WHERE x < 2) SELECT x FROM c",
        "WITH /*+ ENABLE_WITH_CLAUSE_MATERIALIZATION */ RECURSIVE "
        "c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c WHERE x < 2) SELECT x FROM c",
    )
    with_ = expression.args["with_"]
    assert isinstance(with_, vexp.WithHint)
    assert with_.args["recursive"] is True
    assert isinstance(with_.expressions[0].this, exp.Union)


@pytest.mark.parametrize(
    "body",
    [
        "VALUES (1)",
        "FROM t",
        "SELECT",
        "SELECT 1 UNION SELECT",
        "PROFILE SELECT 1",
        "EXPLAIN SELECT 1",
        "AT EPOCH LATEST SELECT 1",
        "SELECT 1 INTO TABLE side_effect",
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET x = 1",
        "DELETE FROM t",
        "MERGE INTO t USING s ON t.x = s.x WHEN MATCHED THEN UPDATE SET x = s.x",
        "CREATE TABLE t (x INT)",
        "DROP TABLE t",
        "TRUNCATE TABLE t",
        "COPY t FROM STDIN",
        "SAVE QUERY SELECT 1",
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_nonquery_cte_bodies_fail_closed(body: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(
            f"WITH c AS ({body}) SELECT * FROM c",
            read="vertica",
            error_level=error_level,
        )


@pytest.mark.parametrize(
    "sql",
    [
        "WITH c AS (SELECT 1) INSERT INTO t SELECT * FROM c",
        "WITH c AS (SELECT 1) UPDATE t SET x = 1",
        "WITH c AS (SELECT 1) DELETE FROM t",
        "WITH c AS (SELECT 1) MERGE INTO t USING s ON t.x = s.x "
        "WHEN MATCHED THEN UPDATE SET x = s.x",
        "WITH c AS (SELECT 1) CREATE TABLE t (x INT)",
        "WITH c AS (SELECT 1) DROP TABLE t",
        "WITH c AS (SELECT 1) TRUNCATE TABLE t",
        "WITH c AS (SELECT 1) COPY t FROM STDIN",
        "WITH c AS (SELECT 1) PROFILE SELECT * FROM c",
        "WITH c AS (SELECT 1) EXPLAIN SELECT * FROM c",
        "WITH c AS (SELECT 1) AT EPOCH LATEST SELECT * FROM c",
        "WITH c AS (SELECT 1) SELECT",
        "WITH c AS (SELECT 1); SELECT 2",
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_invalid_outer_with_placement_fails_closed(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "sql",
    [
        "WITH c AS MATERIALIZED (SELECT 1) SELECT * FROM c",
        "WITH c AS NOT MATERIALIZED (SELECT 1) SELECT * FROM c",
        "WITH c USING KEY (x) AS (SELECT 1 AS x) SELECT * FROM c",
        "WITH RECURSIVE c(x) AS (SELECT 1) SEARCH DEPTH FIRST BY x SET order_col SELECT * FROM c",
        "WITH RECURSIVE c(x) AS (SELECT 1) CYCLE x SET is_cycle SELECT * FROM c",
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_inherited_cte_modifiers_fail_closed(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


def test_comments_and_multi_statement_boundaries() -> None:
    statements = parse(
        "WITH c AS (/* body */ SELECT 1 AS x) SELECT x FROM c; "
        "INSERT INTO t WITH d AS (SELECT 2 AS x) SELECT x FROM d",
        read="vertica",
    )
    assert [type(statement) for statement in statements] == [exp.Select, exp.Insert]
    assert "body" in statements[0].sql(dialect="vertica")
    assert all(
        parse_one(statement.sql(dialect="vertica"), read="vertica") == statement
        for statement in statements
    )


def test_cte_analysis_and_parent_metadata() -> None:
    sql = "WITH c AS (SELECT t.x FROM t) SELECT c.x FROM c"
    schema = {"t": {"x": "INT"}}
    expression = assert_roundtrip(sql)
    copied = expression.copy()
    with_ = copied.args["with_"]
    cte = with_.expressions[0]
    assert with_.parent is copied and with_.arg_key == "with_"
    assert cte.parent is with_ and cte.arg_key == "expressions" and cte.index == 0
    assert cte.this.parent is cte and cte.this.arg_key == "this"

    for analyzed in (
        qualify(parse_one(sql, read="vertica"), schema=schema, dialect="vertica"),
        optimize(parse_one(sql, read="vertica"), schema=schema, dialect="vertica"),
    ):
        assert list(traverse_scope(analyzed))
        assert parse_one(analyzed.sql(dialect="vertica"), read="vertica") == analyzed

    node = lineage("x", parse_one(sql, read="vertica"), schema=schema, dialect="vertica")
    assert "t.x" in {downstream.name for downstream in node.walk()}


def _with_query(cte: exp.CTE, **with_args: object) -> exp.Select:
    query = exp.select("*").from_("c")
    query.set("with_", exp.With(expressions=[cte], **with_args))
    return query


@pytest.mark.parametrize(
    "expression",
    [
        exp.With(expressions=[]),
        _with_query(exp.CTE(this=exp.select("1"))),
        _with_query(
            exp.CTE(
                this=exp.Values(expressions=[exp.Tuple(expressions=[exp.Literal.number(1)])]),
                alias=exp.TableAlias(this=exp.to_identifier("c")),
            )
        ),
        _with_query(
            exp.CTE(this=exp.select("1"), alias=exp.TableAlias(this=exp.to_identifier("c"))),
            recursive=False,
        ),
        _with_query(
            exp.CTE(this=exp.select("1"), alias=exp.TableAlias(this=exp.to_identifier("c"))),
            search=exp.var("SEARCH"),
        ),
        _with_query(
            exp.CTE(
                this=exp.select("1"),
                alias=exp.TableAlias(this=exp.to_identifier("c")),
                materialized=True,
            )
        ),
        _with_query(
            exp.CTE(
                this=exp.select("1"),
                alias=exp.TableAlias(this=exp.to_identifier("c")),
                key_expressions=[exp.column("x")],
            )
        ),
        _with_query(
            exp.CTE(
                this=vexp.SelectInto(
                    expressions=[exp.Literal.number(1)],
                    into=vexp.IntoTableClause(this=exp.to_table("t")),
                ),
                alias=exp.TableAlias(this=exp.to_identifier("c")),
            )
        ),
    ],
)
def test_programmatic_with_and_cte_mutations_fail_atomically(expression: exp.Expr) -> None:
    with pytest.raises(UnsupportedError):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_plain_canonical_cte_remains_foreign_portable() -> None:
    expression = parse_one("WITH c AS (SELECT 1 AS x) SELECT x FROM c", read="vertica")
    assert expression.sql(dialect="postgres") == "WITH c AS (SELECT 1 AS x) SELECT x FROM c"


@pytest.mark.parametrize("dialect", ["postgres", "duckdb", "mysql", "sqlite"])
def test_materialization_hint_fails_atomically_abroad(dialect: str) -> None:
    expression = parse_one(
        "WITH /*+ENABLE_WITH_CLAUSE_MATERIALIZATION*/ c AS (SELECT 1) SELECT * FROM c",
        read="vertica",
    )
    with pytest.raises(ValueError, match="WithHint"):
        expression.sql(dialect=dialect, unsupported_level=ErrorLevel.IGNORE)
