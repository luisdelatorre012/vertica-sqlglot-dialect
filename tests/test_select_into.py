"""Vertica SELECT ``INTO [TABLE]`` clause regressions."""

from __future__ import annotations

import contextlib

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.lineage import lineage
from sqlglot.optimizer import optimize
from sqlglot.optimizer.qualify import qualify

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip

FOREIGN_DIALECTS = ["postgres", "duckdb", "mysql", "sqlite"]
ALL_PARSE_LEVELS = [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]
ALL_UNSUPPORTED_LEVELS = [ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]


def parse_select_into(sql: str, expected: str | None = None) -> vexp.SelectInto:
    expression = assert_roundtrip(sql, expected)
    assert isinstance(expression, vexp.SelectInto)
    clause = expression.args["into"]
    assert isinstance(clause, vexp.IntoTableClause)
    return expression


def test_permanent_documented_example() -> None:
    expression = parse_select_into(
        "SELECT * INTO TABLE newTable FROM customer_dimension",
        "SELECT * INTO TABLE newTable FROM customer_dimension",
    )
    clause = expression.args["into"]
    assert isinstance(clause.this, exp.Table)
    assert clause.this.name == "newTable"
    assert clause.args.get("temporary") is None
    assert clause.args.get("spelling") is None
    assert clause.args.get("scope") is None
    assert clause.args.get("on_commit") is None


def test_optional_table_keyword_is_canonicalized_in() -> None:
    """The documented optional TABLE noise word always regenerates."""

    parse_select_into(
        "SELECT * INTO newTable FROM customer_dimension",
        "SELECT * INTO TABLE newTable FROM customer_dimension",
    )
    parse_select_into(
        "SELECT * INTO TEMP newTempTable FROM customer_dimension",
        "SELECT * INTO TEMP TABLE newTempTable FROM customer_dimension",
    )


@pytest.mark.parametrize("spelling", ["TEMP", "TEMPORARY"])
def test_temporary_spelling_is_preserved_exactly(spelling: str) -> None:
    expression = parse_select_into(
        f"SELECT * INTO {spelling} TABLE t FROM x",
        f"SELECT * INTO {spelling} TABLE t FROM x",
    )
    clause = expression.args["into"]
    assert clause.args["temporary"] is True
    assert clause.args["spelling"] == spelling


def test_documented_local_temp_example_parses() -> None:
    """The 26.2 INTO TABLE page's own example previously raised ParseError."""

    expression = parse_select_into(
        "SELECT * INTO LOCAL TEMP TABLE newTempTableLocal ON COMMIT PRESERVE ROWS "
        "FROM customer_dimension",
        "SELECT * INTO LOCAL TEMP TABLE newTempTableLocal ON COMMIT PRESERVE ROWS "
        "FROM customer_dimension",
    )
    clause = expression.args["into"]
    assert clause.args["temporary"] is True
    assert clause.args["spelling"] == "TEMP"
    assert clause.args["scope"] == "LOCAL"
    assert clause.args["on_commit"] == "PRESERVE"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * INTO GLOBAL TEMP TABLE t FROM x",
        "SELECT * INTO GLOBAL TEMPORARY TABLE t FROM x",
        "SELECT * INTO LOCAL TEMPORARY TABLE t FROM x",
        "SELECT * INTO TEMP TABLE t ON COMMIT DELETE ROWS FROM x",
        "SELECT * INTO TEMPORARY TABLE t ON COMMIT PRESERVE ROWS FROM x",
        "SELECT * INTO GLOBAL TEMP TABLE t ON COMMIT DELETE ROWS FROM x",
        "SELECT * INTO LOCAL TEMPORARY TABLE t ON COMMIT PRESERVE ROWS FROM x",
    ],
)
def test_scope_spelling_and_on_commit_combinations(sql: str) -> None:
    """Explicit scope and ON COMMIT stay exactly as written; absence stays absent."""

    expression = parse_select_into(sql, sql)
    clause = expression.args["into"]
    assert clause.args["temporary"] is True
    assert ("GLOBAL" in sql) == (clause.args.get("scope") == "GLOBAL")
    assert ("LOCAL" in sql) == (clause.args.get("scope") == "LOCAL")
    assert ("DELETE ROWS" in sql) == (clause.args.get("on_commit") == "DELETE")
    assert ("PRESERVE ROWS" in sql) == (clause.args.get("on_commit") == "PRESERVE")


def test_unscoped_temporary_omits_scope() -> None:
    expression = parse_select_into(
        "SELECT * INTO TEMP TABLE newTempTable FROM customer_dimension",
        "SELECT * INTO TEMP TABLE newTempTable FROM customer_dimension",
    )
    assert expression.args["into"].args.get("scope") is None


def test_qualification_shapes() -> None:
    permanent = parse_select_into(
        "SELECT * INTO TABLE analytics_ns.public.t FROM x",
        "SELECT * INTO TABLE analytics_ns.public.t FROM x",
    )
    target = permanent.args["into"].this
    assert target.catalog == "analytics_ns"
    assert target.db == "public"
    assert target.name == "t"

    parse_select_into("SELECT * INTO TABLE s.t FROM x", "SELECT * INTO TABLE s.t FROM x")
    parse_select_into(
        "SELECT * INTO LOCAL TEMP TABLE db.s.t FROM x",
        "SELECT * INTO LOCAL TEMP TABLE db.s.t FROM x",
    )
    parse_select_into(
        'SELECT * INTO TABLE "quoted name" FROM x',
        'SELECT * INTO TABLE "quoted name" FROM x',
    )
    parse_select_into(
        'SELECT * INTO TABLE "täble" FROM x',
        'SELECT * INTO TABLE "täble" FROM x',
    )


def test_keywords_normalize_case() -> None:
    parse_select_into(
        "select * into local temp table t on commit preserve rows from x",
        "SELECT * INTO LOCAL TEMP TABLE t ON COMMIT PRESERVE ROWS FROM x",
    )


def test_into_without_from() -> None:
    parse_select_into("SELECT 1 INTO TABLE t", "SELECT 1 INTO TABLE t")


def test_multi_statement_boundaries() -> None:
    statements = parse(
        "SELECT * INTO TEMP TABLE t FROM x; SELECT * FROM t",
        read="vertica",
    )
    assert len(statements) == 2
    assert isinstance(statements[0], vexp.SelectInto)
    assert type(statements[1]) is exp.Select


def test_leading_comment_is_retained() -> None:
    expression = parse_one("/* build scratch */ SELECT * INTO TABLE t FROM x", read="vertica")
    assert isinstance(expression, vexp.SelectInto)
    assert "build scratch" in expression.sql(dialect="vertica")


@pytest.mark.parametrize("name", ["local", "global", "strict", "unlogged"])
def test_contextual_words_remain_valid_target_names(name: str) -> None:
    expression = parse_select_into(
        f"SELECT * INTO {name} FROM x",
        f"SELECT * INTO TABLE {name} FROM x",
    )
    assert expression.args["into"].this.name == name


def test_quoted_keyword_payloads_are_ordinary_targets() -> None:
    parse_select_into('SELECT * INTO "TABLE" FROM x', 'SELECT * INTO TABLE "TABLE" FROM x')
    parse_select_into('SELECT * INTO TABLE "TEMP" FROM x', 'SELECT * INTO TABLE "TEMP" FROM x')


@pytest.mark.parametrize(
    "sql",
    [
        'SELECT * INTO "GLOBAL" TEMP TABLE t FROM x',
        'SELECT * INTO "TEMP" TABLE t FROM x',
        'SELECT * INTO TEMP TABLE t ON COMMIT "PRESERVE" ROWS FROM x',
    ],
)
def test_quoted_keyword_provenance_never_parses_as_clause_keyword(sql: str) -> None:
    expression: exp.Expr | None = None
    with contextlib.suppress(ParseError):
        expression = parse_one(sql, read="vertica")
    assert not isinstance(expression, vexp.SelectInto)


def test_union_arm_is_promoted_and_atomic() -> None:
    sql = "SELECT a INTO TABLE t FROM x UNION SELECT a FROM y"
    expression = assert_roundtrip(sql, sql)
    assert isinstance(expression, exp.Union)
    assert isinstance(expression.this, vexp.SelectInto)
    for dialect in FOREIGN_DIALECTS:
        with pytest.raises(ValueError, match="SelectInto"):
            expression.sql(dialect=dialect, unsupported_level=ErrorLevel.IGNORE)


def test_timeseries_select_keeps_typed_into_clause() -> None:
    sql = (
        "SELECT slice_time INTO TEMP TABLE t FROM ticks "
        "TIMESERIES slice_time AS '1 minute' OVER (PARTITION BY symbol ORDER BY ts)"
    )
    expression = assert_roundtrip(sql, sql)
    assert isinstance(expression, vexp.TimeseriesSelect)
    assert isinstance(expression.args["into"], vexp.IntoTableClause)
    for dialect in FOREIGN_DIALECTS:
        with pytest.raises(ValueError, match="TimeseriesSelect"):
            expression.sql(dialect=dialect, unsupported_level=ErrorLevel.IGNORE)


def test_dispatch_neighbors_unchanged() -> None:
    insert = assert_roundtrip("INSERT INTO t SELECT 1", "INSERT INTO t SELECT 1")
    assert type(insert) is exp.Insert
    ctas = assert_roundtrip("CREATE TABLE t AS SELECT 1 AS id", "CREATE TABLE t AS SELECT 1 AS id")
    assert type(ctas) is exp.Create
    plain = assert_roundtrip("SELECT * FROM x", "SELECT * FROM x")
    assert type(plain) is exp.Select


def test_parent_metadata_and_copy_stability() -> None:
    expression = parse_select_into(
        "SELECT a INTO GLOBAL TEMP TABLE s.t ON COMMIT DELETE ROWS FROM x"
    )
    clause = expression.args["into"]
    assert clause.parent is expression
    assert clause.arg_key == "into"
    assert clause.this.parent is clause
    assert clause.this.arg_key == "this"

    duplicate = expression.copy()
    assert duplicate == expression
    assert duplicate is not expression
    transformed = expression.transform(lambda node: node)
    assert transformed == expression


@pytest.mark.parametrize(
    "sql",
    [
        # scope requires TEMP[ORARY]
        "SELECT * INTO GLOBAL TABLE t FROM x",
        "SELECT * INTO LOCAL TABLE t FROM x",
        # ON COMMIT contract
        "SELECT * INTO TABLE t ON COMMIT DELETE ROWS FROM x",
        "SELECT * INTO t ON COMMIT PRESERVE ROWS FROM x",
        "SELECT * INTO TEMP TABLE t ON COMMIT ROWS FROM x",
        "SELECT * INTO TEMP TABLE t ON COMMIT PRESERVE FROM x",
        "SELECT * INTO TEMP TABLE t ON COMMIT KEEP ROWS FROM x",
        "SELECT * INTO TEMP TABLE t ON PRESERVE ROWS FROM x",
        # foreign PostgreSQL / PL forms
        "SELECT * INTO STRICT v FROM x",
        "SELECT * INTO UNLOGGED TABLE t FROM x",
        "SELECT * INTO UNLOGGED t FROM x",
        "SELECT a, b INTO x, y FROM t",
        # malformed targets
        "SELECT * INTO TABLE a.b.c.d FROM x",
        "SELECT * INTO FROM x",
        "SELECT 1 INTO",
        "SELECT * INTO TABLE FROM x",
        "SELECT * INTO TABLE t (a, b) FROM x",
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_recognized_invalid_into_fails_closed(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * INTO TABLE t FROM x",
        "SELECT * INTO TEMP TABLE t FROM x",
        "SELECT * INTO LOCAL TEMP TABLE t ON COMMIT PRESERVE ROWS FROM x",
        "SELECT * INTO GLOBAL TEMPORARY TABLE t ON COMMIT DELETE ROWS FROM x",
    ],
)
@pytest.mark.parametrize("dialect", FOREIGN_DIALECTS)
@pytest.mark.parametrize("unsupported_level", ALL_UNSUPPORTED_LEVELS)
def test_direct_foreign_generation_fails_atomically(
    sql: str, dialect: str, unsupported_level: ErrorLevel
) -> None:
    """No foreign dialect may pop the clause or rewrite the statement into a CTAS."""

    expression = parse_one(sql, read="vertica")
    with pytest.raises(ValueError, match="SelectInto"):
        expression.sql(dialect=dialect, unsupported_level=unsupported_level)


@pytest.mark.parametrize("dialect", FOREIGN_DIALECTS)
@pytest.mark.parametrize("unsupported_level", ALL_UNSUPPORTED_LEVELS)
def test_nested_foreign_generation_fails_atomically(
    dialect: str, unsupported_level: ErrorLevel
) -> None:
    expression = parse_one(
        "SELECT q.a FROM (SELECT a INTO TEMP TABLE t FROM x) AS q",
        read="vertica",
    )
    with pytest.raises(ValueError, match="SelectInto"):
        expression.sql(dialect=dialect, unsupported_level=unsupported_level)


@pytest.mark.parametrize("dialect", FOREIGN_DIALECTS)
def test_detached_clause_fails_atomically_in_foreign_dialects(dialect: str) -> None:
    clause = vexp.IntoTableClause(this=exp.to_table("t"))
    with pytest.raises(ValueError, match="IntoTableClause"):
        clause.sql(dialect=dialect, unsupported_level=ErrorLevel.IGNORE)


def build_valid_clause() -> vexp.IntoTableClause:
    return vexp.IntoTableClause(
        this=exp.to_table("t"),
        temporary=True,
        spelling="TEMP",
        scope="LOCAL",
        on_commit="PRESERVE",
    )


def test_programmatic_valid_clause_renders() -> None:
    select = vexp.SelectInto(
        expressions=[exp.Star()],
        into=build_valid_clause(),
        from_=exp.From(this=exp.to_table("x")),
    )
    assert (
        select.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
        == "SELECT * INTO LOCAL TEMP TABLE t ON COMMIT PRESERVE ROWS FROM x"
    )


def mutate(**overrides: object) -> vexp.IntoTableClause:
    clause = build_valid_clause()
    for key, value in overrides.items():
        clause.set(key, value)
    return clause


@pytest.mark.parametrize(
    "clause_builder",
    [
        pytest.param(lambda: mutate(this=None), id="missing-target"),
        pytest.param(lambda: mutate(this=exp.column("t")), id="non-table-target"),
        pytest.param(
            lambda: mutate(
                this=exp.Table(
                    this=exp.Dot(this=exp.to_identifier("c"), expression=exp.to_identifier("d")),
                    db=exp.to_identifier("b"),
                    catalog=exp.to_identifier("a"),
                )
            ),
            id="four-part-target",
        ),
        pytest.param(
            lambda: mutate(this=exp.Table(this=exp.to_identifier("t"), alias="a")),
            id="aliased-target",
        ),
        pytest.param(lambda: mutate(spelling=None), id="temporary-without-spelling"),
        pytest.param(lambda: mutate(temporary=None), id="spelling-without-temporary"),
        pytest.param(lambda: mutate(temporary="yes"), id="non-boolean-temporary"),
        pytest.param(lambda: mutate(spelling="TMP"), id="invalid-spelling"),
        pytest.param(lambda: mutate(scope="REGIONAL"), id="invalid-scope"),
        pytest.param(
            lambda: mutate(temporary=None, spelling=None, on_commit=None),
            id="scope-without-temporary",
        ),
        pytest.param(lambda: mutate(on_commit="KEEP"), id="invalid-on-commit"),
        pytest.param(
            lambda: mutate(temporary=None, spelling=None, scope=None),
            id="on-commit-without-temporary",
        ),
        pytest.param(lambda: mutate(unlogged=True), id="foreign-unlogged-field"),
        pytest.param(lambda: mutate(bulk_collect=True), id="foreign-bulk-collect-field"),
        pytest.param(
            lambda: mutate(expressions=[exp.column("v")]), id="foreign-variable-list-field"
        ),
    ],
)
def test_programmatic_clause_mutations_fail_with_unsupported_error(
    clause_builder: object,
) -> None:
    clause = clause_builder()  # type: ignore[operator]
    select = vexp.SelectInto(
        expressions=[exp.Star()],
        into=clause,
        from_=exp.From(this=exp.to_table("x")),
    )
    with pytest.raises(UnsupportedError):
        select.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_select_into_root_requires_typed_clause() -> None:
    missing = vexp.SelectInto(expressions=[exp.Star()])
    with pytest.raises(UnsupportedError):
        missing.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    canonical = vexp.SelectInto(
        expressions=[exp.Star()],
        into=exp.Into(this=exp.to_table("t")),
    )
    with pytest.raises(UnsupportedError):
        canonical.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_canonical_into_passthrough_stays_valid_vertica() -> None:
    """Foreign-parsed canonical SELECT INTO still transpiles to valid Vertica."""

    postgres = parse_one("SELECT * INTO TEMPORARY t FROM x", read="postgres")
    assert postgres.sql(dialect="vertica") == "SELECT * INTO TEMPORARY t FROM x"

    unlogged = parse_one("SELECT * INTO UNLOGGED t FROM x", read="postgres")
    with pytest.raises(UnsupportedError):
        unlogged.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_optimizer_qualification_and_lineage() -> None:
    schema = {"src": {"a": "INT", "b": "VARCHAR"}}
    expression = parse_select_into("SELECT a, b INTO LOCAL TEMP TABLE t2 FROM src")

    qualified = qualify(expression.copy(), dialect="vertica", schema=schema)
    assert isinstance(qualified, vexp.SelectInto)
    assert "INTO LOCAL TEMP TABLE" in qualified.sql(dialect="vertica")
    source_columns = {
        column.name: column.table
        for column in qualified.find_all(exp.Column)
        if column.name in {"a", "b"}
    }
    assert source_columns == {"a": "src", "b": "src"}
    assert qualified.args["into"].this.name == "t2"

    optimized = optimize(expression.copy(), dialect="vertica", schema=schema)
    assert isinstance(optimized, vexp.SelectInto)
    assert isinstance(optimized.args["into"], vexp.IntoTableClause)
    restored = exp.Expr.load(optimized.dump())
    assert restored == optimized

    node = lineage("a", expression.copy(), schema=schema, dialect="vertica")
    assert {downstream.name for downstream in node.walk()} >= {"a", "src.a"}
