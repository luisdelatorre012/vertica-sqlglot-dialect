"""Vertica WITH/CTE query-expression and placement regressions."""

from __future__ import annotations

import logging

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.lineage import lineage
from sqlglot.optimizer import optimize
from sqlglot.optimizer.annotate_types import annotate_types
from sqlglot.optimizer.eliminate_subqueries import eliminate_subqueries
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip

ALL_PARSE_LEVELS = [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]

USER_REPORTED_OPTIMIZER_CTE_SQL = """-- dialect: vertica
select
    a.i,
    a.n,
    b.r
from s.a as a
inner join s.b as b
    on a.i = b.i
where
    b.u >= :p
    and (
        substring(a.n, 2, 1) between 'A' and 'Z'
        or a.n like '5%'
    )

union all

select
    a.i,
    a.n,
    null as r
from s.a as a
inner join s.b as b
    on a.i = b.i
where
    b.u >= :p
    and a.n like 'P[0-9]%'

union all

select
    null as i,
    c.n,
    null as r
from s.c as c
where
    c.u >= :q
    and not exists (
        select 1
        from s.a as a
        where a.n = c.n
    )
    and c.n like '7%'
"""


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


def test_user_reported_optimizer_generated_nonrecursive_with_is_warning_free(
    caplog: pytest.LogCaptureFixture,
) -> None:
    parsed = parse_one(USER_REPORTED_OPTIMIZER_CTE_SQL, read="vertica")
    assert type(parsed) is exp.Union
    assert parsed.args.get("with_") is None

    optimized = optimize(parsed.copy(), dialect="vertica")
    with_ = optimized.args.get("with_")
    assert type(optimized) is exp.Union
    assert isinstance(with_, exp.With)
    assert with_.args.get("recursive") is False
    assert [cte.alias for cte in with_.expressions] == ["_u_0"]
    assert with_.parent is optimized and with_.arg_key == "with_"

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="sqlglot"):
        generated = optimized.sql(dialect="vertica")
    assert not caplog.records
    assert generated.startswith('WITH "_u_0" AS')
    assert "WITH RECURSIVE" not in generated

    reparsed = parse_one(generated, read="vertica")
    reparsed_with = reparsed.args.get("with_")
    assert type(reparsed) is exp.Union
    assert isinstance(reparsed_with, exp.With)
    assert reparsed_with.args.get("recursive") is None
    assert len(list(reparsed.find_all(exp.CTE))) == 1
    assert "dialect: vertica" in reparsed.sql(dialect="vertica")

    pretty = optimized.sql(dialect="vertica", pretty=True)
    assert "WITH RECURSIVE" not in pretty
    pretty_reparsed = parse_one(pretty, read="vertica")
    assert type(pretty_reparsed) is exp.Union
    assert isinstance(pretty_reparsed.args.get("with_"), exp.With)
    assert exp.Expr.load(optimized.dump()) == optimized
    assert optimized.copy() == optimized
    assert optimized.transform(lambda node: node) == optimized
    assert list(traverse_scope(optimized))
    assert list(traverse_scope(qualify(optimized.copy(), dialect="vertica")))
    assert list(traverse_scope(annotate_types(optimized.copy(), dialect="vertica")))
    assert list(traverse_scope(optimize(optimized.copy(), dialect="vertica")))
    assert lineage("n", optimized.copy(), dialect="vertica").downstream


@pytest.mark.parametrize("unsupported_level", list(ErrorLevel))
def test_user_reported_optimizer_generated_with_renders_at_every_level(
    unsupported_level: ErrorLevel,
) -> None:
    optimized = optimize(
        parse_one(USER_REPORTED_OPTIMIZER_CTE_SQL, read="vertica"), dialect="vertica"
    )
    generated = optimized.sql(dialect="vertica", unsupported_level=unsupported_level)
    assert "WITH RECURSIVE" not in generated
    assert isinstance(parse_one(generated, read="vertica").args.get("with_"), exp.With)


def test_eliminate_subqueries_constructs_supported_nonrecursive_with() -> None:
    expression = parse_one("SELECT d.a FROM (SELECT x.a FROM x) AS d", read="vertica")
    eliminated = eliminate_subqueries(expression)
    with_ = eliminated.args.get("with_")
    assert isinstance(with_, exp.With)
    assert with_.args.get("recursive") is False
    assert eliminated.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE) == (
        "WITH d AS (SELECT x.a FROM x) SELECT d.a FROM d AS d"
    )


def test_nonrecursive_none_and_false_generation_are_equivalent() -> None:
    cte = exp.CTE(
        this=exp.select(exp.alias_(exp.Literal.number(1), "x")),
        alias=exp.TableAlias(this=exp.to_identifier("c")),
    )
    omitted = _with_query(cte.copy())
    explicit_false = _with_query(cte.copy(), recursive=False)
    assert omitted.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE) == (
        explicit_false.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
    )
    assert "RECURSIVE" not in explicit_false.sql(dialect="vertica")


def test_nested_and_hinted_nonrecursive_false_with_trees_generate() -> None:
    inner_cte = exp.CTE(
        this=exp.select(exp.alias_(exp.Literal.number(1), "x")),
        alias=exp.TableAlias(this=exp.to_identifier("c")),
    )
    inner = _with_query(inner_cte, recursive=False)
    outer_cte = exp.CTE(
        this=inner,
        alias=exp.TableAlias(this=exp.to_identifier("outer_cte")),
    )
    outer = _with_query(outer_cte)
    generated = outer.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
    assert generated.count("WITH ") == 2
    assert "WITH RECURSIVE" not in generated
    assert parse_one(generated, read="vertica").sql(dialect="vertica") == generated

    hinted = parse_one(
        "WITH /*+ENABLE_WITH_CLAUSE_MATERIALIZATION*/ c AS (SELECT 1 AS x) SELECT x FROM c",
        read="vertica",
    )
    hinted.args["with_"].set("recursive", False)
    hinted_sql = hinted.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
    assert hinted_sql.startswith("WITH /*+ ENABLE_WITH_CLAUSE_MATERIALIZATION */ c AS")
    assert "WITH RECURSIVE" not in hinted_sql


@pytest.mark.parametrize("recursive", [0, 1, "", "False", [], {}, ()])
def test_nonboolean_recursive_states_fail_atomically(recursive: object) -> None:
    cte = exp.CTE(
        this=exp.select("1"),
        alias=exp.TableAlias(this=exp.to_identifier("c")),
    )
    expression = _with_query(cte, recursive=recursive)
    with pytest.raises(
        UnsupportedError, match="Vertica WITH RECURSIVE must be either present or absent"
    ):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


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


@pytest.mark.parametrize("recursive", [None, False])
@pytest.mark.parametrize("dialect", ["postgres", "duckdb", "mysql", "sqlite"])
def test_plain_canonical_cte_remains_foreign_portable(recursive: bool | None, dialect: str) -> None:
    expression = parse_one("WITH c AS (SELECT 1 AS x) SELECT x FROM c", read="vertica")
    expression.args["with_"].set("recursive", recursive)
    assert expression.sql(dialect=dialect) == "WITH c AS (SELECT 1 AS x) SELECT x FROM c"


@pytest.mark.parametrize("dialect", ["postgres", "duckdb", "mysql", "sqlite"])
def test_materialization_hint_fails_atomically_abroad(dialect: str) -> None:
    expression = parse_one(
        "WITH /*+ENABLE_WITH_CLAUSE_MATERIALIZATION*/ c AS (SELECT 1) SELECT * FROM c",
        read="vertica",
    )
    with pytest.raises(ValueError, match="WithHint"):
        expression.sql(dialect=dialect, unsupported_level=ErrorLevel.IGNORE)
