"""Vertica SELECT ``[ AT epoch ]`` historical-query prefix regressions."""

from __future__ import annotations

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


def parse_at_epoch_query(sql: str, expected: str | None = None) -> vexp.AtEpochQuery:
    expression = assert_roundtrip(sql, expected)
    assert isinstance(expression, vexp.AtEpochQuery)
    return expression


def test_epoch_latest() -> None:
    expression = parse_at_epoch_query(
        "AT EPOCH LATEST SELECT * FROM t", "AT EPOCH LATEST SELECT * FROM t"
    )
    assert expression.args["kind"] == exp.var("EPOCH")
    assert expression.args["value"] == exp.var("LATEST")
    assert type(expression.this) is exp.Select


def test_epoch_integer() -> None:
    expression = parse_at_epoch_query("AT EPOCH 5 SELECT * FROM t", "AT EPOCH 5 SELECT * FROM t")
    value = expression.args["value"]
    assert isinstance(value, exp.Literal) and value.is_int and value.name == "5"


def test_time_literal() -> None:
    expression = parse_at_epoch_query(
        "AT TIME '2024-01-01 00:00:00' SELECT * FROM t",
        "AT TIME '2024-01-01 00:00:00' SELECT * FROM t",
    )
    value = expression.args["value"]
    assert isinstance(value, exp.Literal) and value.is_string
    assert value.name == "2024-01-01 00:00:00"


def test_keywords_normalize_case() -> None:
    parse_at_epoch_query("at epoch latest select * from t", "AT EPOCH LATEST SELECT * FROM t")


def test_prefix_scopes_a_with_clause() -> None:
    expression = parse_at_epoch_query(
        "AT EPOCH LATEST WITH cte AS (SELECT 1) SELECT * FROM cte",
        "AT EPOCH LATEST WITH cte AS (SELECT 1) SELECT * FROM cte",
    )
    assert type(expression.this) is exp.Select
    assert expression.this.args.get("with_") is not None


@pytest.mark.parametrize(
    ("sql", "root_type"),
    [
        ("AT EPOCH LATEST SELECT 1 UNION SELECT 2", exp.Union),
        ("AT EPOCH LATEST SELECT 1 UNION ALL SELECT 2", exp.Union),
        ("AT EPOCH LATEST SELECT 1 INTERSECT SELECT 2", exp.Intersect),
        ("AT EPOCH LATEST SELECT 1 EXCEPT SELECT 2", exp.Except),
        ("AT EPOCH LATEST SELECT 1 INTERSECT SELECT 2 EXCEPT SELECT 3", exp.Except),
    ],
)
def test_prefix_scopes_the_whole_set_operation_chain(sql: str, root_type: type[exp.Expr]) -> None:
    """The prefix wraps the entire compound query, not only its first branch."""

    expression = parse_at_epoch_query(sql, sql)
    assert type(expression.this) is root_type


def test_prefix_scopes_a_with_clause_and_a_union_chain() -> None:
    sql = "AT EPOCH LATEST WITH cte AS (SELECT 1) SELECT * FROM cte UNION SELECT * FROM cte"
    expression = parse_at_epoch_query(sql, sql)
    assert type(expression.this) is exp.Union
    assert expression.this.args.get("with_") is not None


def test_multi_statement_boundaries() -> None:
    statements = parse("AT EPOCH LATEST SELECT 1; AT EPOCH 2 SELECT 2", read="vertica")
    assert len(statements) == 2
    assert all(isinstance(statement, vexp.AtEpochQuery) for statement in statements)


def test_leading_comment_is_retained() -> None:
    expression = parse_one("/* scratch */ AT EPOCH LATEST SELECT * FROM t", read="vertica")
    assert isinstance(expression, vexp.AtEpochQuery)
    assert "scratch" in expression.sql(dialect="vertica")


def test_dispatch_neighbors_unchanged() -> None:
    plain = assert_roundtrip("SELECT * FROM x", "SELECT * FROM x")
    assert type(plain) is exp.Select

    with_select = assert_roundtrip(
        "WITH cte AS (SELECT 1) SELECT * FROM cte", "WITH cte AS (SELECT 1) SELECT * FROM cte"
    )
    assert type(with_select) is exp.Select

    profile = assert_roundtrip("PROFILE SELECT 1", "PROFILE SELECT 1")
    assert isinstance(profile, vexp.ProfileStatement)

    ctas = assert_roundtrip(
        "CREATE TABLE t AS AT EPOCH LATEST SELECT 1 AS id",
        "CREATE TABLE t AS AT EPOCH LATEST SELECT 1 AS id",
    )
    assert type(ctas) is exp.Create
    properties = ctas.args["properties"].expressions
    assert any(isinstance(prop, vexp.AtEpochProperty) for prop in properties)
    assert not any(isinstance(prop, vexp.AtEpochQuery) for prop in properties)


def test_cte_body_may_carry_its_own_prefix() -> None:
    """Documented, not endorsed: the CTE-body parenthesized query re-enters the
    same top-level statement dispatch as PROFILE/SAVE QUERY/etc. already do, so
    it independently accepts this prefix too. No 26.2 source documents (or
    forbids) an AT-epoch-prefixed CTE body; this pins the observed, pre-existing
    architectural behavior shared with those sibling families rather than a
    new Q06-specific design choice.
    """

    sql = "WITH cte AS (AT EPOCH LATEST SELECT 1) SELECT * FROM cte"
    expression = assert_roundtrip(sql, sql)
    assert type(expression) is exp.Select
    cte_query = expression.args["with_"].expressions[0].this
    assert isinstance(cte_query, vexp.AtEpochQuery)


@pytest.mark.parametrize(
    "sql",
    [
        "WITH cte AS (SELECT 1) AT EPOCH LATEST SELECT * FROM cte",
    ],
)
def test_prefix_after_an_outer_with_clause_fails_closed(sql: str) -> None:
    """The prefix must precede WITH, not follow it; AtEpochQuery also carries
    no ``with_`` slot, so a CTE list arriving after this node parses fails the
    same generic "does not support CTE" check ``ProfileStatement`` already
    relies on rather than silently dropping the CTE list.
    """

    with pytest.raises(ParseError, match="does not support CTE"):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        # missing EPOCH/TIME keyword
        "AT SELECT * FROM t",
        "AT FOO SELECT * FROM t",
        "AT LATEST SELECT * FROM t",
        # non-integer / malformed epoch value
        "AT EPOCH SELECT * FROM t",
        "AT EPOCH abc SELECT * FROM t",
        "AT EPOCH 5.5 SELECT * FROM t",
        "AT EPOCH -5 SELECT * FROM t",
        "AT EPOCH '5' SELECT * FROM t",
        # unquoted or missing TIME value
        "AT TIME SELECT * FROM t",
        "AT TIME 2024-01-01 SELECT * FROM t",
        # missing or non-query trailing statement
        "AT EPOCH LATEST",
        "AT EPOCH LATEST INSERT INTO t VALUES (1)",
        "AT EPOCH LATEST CREATE TABLE t (a INT)",
        "AT EPOCH LATEST AT EPOCH LATEST SELECT 1",
        "PROFILE AT EPOCH LATEST SELECT 1",
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_recognized_invalid_at_epoch_query_fails_closed(sql: str, error_level: ErrorLevel) -> None:
    """Every malformed form recognized by this family's own guaranteed-raise
    wrapper (``_raise_at_epoch_query_error``) fails at every error level.
    """

    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "sql",
    [
        # The prefix is not valid nested inside an ordinary subquery, a CREATE
        # VIEW body, or an INSERT source. Each of these instead reaches a
        # different, pre-existing (non-Q06) parse path -- generic derived-table
        # parenthesization, CREATE VIEW's AS-query requirement, and INSERT's
        # source-query requirement -- so this only pins the default RAISE
        # boundary, not a per-family guarantee at every error level: a control
        # check with unrelated malformed content ("GARBAGE ~~~ 1") in the same
        # three positions reproduces the identical WARN/IGNORE degradation
        # (partial or dropped statements), confirming it is generic,
        # pre-existing behavior in those other families rather than anything
        # specific to AT-epoch syntax or introduced by this task.
        "SELECT * FROM (AT EPOCH LATEST SELECT 1) x",
        "CREATE VIEW v AS AT EPOCH LATEST SELECT 1",
        "INSERT INTO t AT EPOCH LATEST SELECT 1",
    ],
)
def test_at_epoch_query_is_not_valid_outside_statement_position(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize("name", ["at", "epoch", "time", "latest"])
def test_contextual_words_remain_valid_identifiers_when_not_leading(name: str) -> None:
    """The prefix only ever intercepts the very first token of a statement."""

    expression = assert_roundtrip(
        f"SELECT 1 AS {name} FROM t",
        f"SELECT 1 AS {name} FROM t",
    )
    assert type(expression) is exp.Select


@pytest.mark.parametrize(
    "sql",
    [
        'SELECT 1 AS "AT" FROM t',
    ],
)
def test_quoted_keyword_payloads_are_ordinary_identifiers(sql: str) -> None:
    expression = parse_one(sql, read="vertica")
    assert not isinstance(expression, vexp.AtEpochQuery)


def test_parent_metadata_and_copy_stability() -> None:
    expression = parse_at_epoch_query("AT EPOCH 5 SELECT a FROM t")
    assert expression.this.parent is expression
    assert expression.this.arg_key == "this"
    assert expression.args["kind"].parent is expression
    assert expression.args["value"].parent is expression

    duplicate = expression.copy()
    assert duplicate == expression
    assert duplicate is not expression
    transformed = expression.transform(lambda node: node)
    assert transformed == expression


@pytest.mark.parametrize(
    "sql",
    [
        "AT EPOCH LATEST SELECT * FROM t",
        "AT EPOCH 5 SELECT * FROM t",
        "AT TIME '2024-01-01 00:00:00' SELECT * FROM t",
        "AT EPOCH LATEST WITH cte AS (SELECT 1) SELECT * FROM cte",
        "AT EPOCH LATEST SELECT 1 UNION SELECT 2",
    ],
)
@pytest.mark.parametrize("dialect", FOREIGN_DIALECTS)
@pytest.mark.parametrize("unsupported_level", ALL_UNSUPPORTED_LEVELS)
def test_direct_foreign_generation_fails_atomically(
    sql: str, dialect: str, unsupported_level: ErrorLevel
) -> None:
    expression = parse_one(sql, read="vertica")
    with pytest.raises(ValueError, match="AtEpochQuery"):
        expression.sql(dialect=dialect, unsupported_level=unsupported_level)


@pytest.mark.parametrize("dialect", FOREIGN_DIALECTS)
@pytest.mark.parametrize("unsupported_level", ALL_UNSUPPORTED_LEVELS)
def test_cte_body_foreign_generation_fails_atomically(
    dialect: str, unsupported_level: ErrorLevel
) -> None:
    expression = parse_one(
        "WITH cte AS (AT EPOCH LATEST SELECT 1) SELECT * FROM cte", read="vertica"
    )
    with pytest.raises(ValueError, match="AtEpochQuery"):
        expression.sql(dialect=dialect, unsupported_level=unsupported_level)


@pytest.mark.parametrize("dialect", FOREIGN_DIALECTS)
def test_detached_node_fails_atomically_in_foreign_dialects(dialect: str) -> None:
    bare = vexp.AtEpochQuery(this=exp.select("1"), kind=exp.var("EPOCH"), value=exp.var("LATEST"))
    with pytest.raises(ValueError, match="AtEpochQuery"):
        bare.sql(dialect=dialect, unsupported_level=ErrorLevel.IGNORE)


def build_valid_at_epoch_query(**overrides: object) -> vexp.AtEpochQuery:
    fields: dict[str, object] = {
        "this": exp.select("a").from_("t"),
        "kind": exp.var("EPOCH"),
        "value": exp.var("LATEST"),
    }
    fields.update(overrides)
    return vexp.AtEpochQuery(**fields)  # type: ignore[arg-type]


def test_programmatic_valid_node_renders() -> None:
    expression = build_valid_at_epoch_query()
    assert (
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
        == "AT EPOCH LATEST SELECT a FROM t"
    )

    time_form = build_valid_at_epoch_query(
        kind=exp.var("TIME"), value=exp.Literal.string("2024-01-01 00:00:00")
    )
    assert (
        time_form.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
        == "AT TIME '2024-01-01 00:00:00' SELECT a FROM t"
    )

    integer_form = build_valid_at_epoch_query(value=exp.Literal.number(5))
    assert (
        integer_form.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
        == "AT EPOCH 5 SELECT a FROM t"
    )


@pytest.mark.parametrize(
    "node_builder",
    [
        pytest.param(lambda: build_valid_at_epoch_query(kind=exp.var("FOO")), id="invalid-kind"),
        pytest.param(lambda: build_valid_at_epoch_query(kind=None), id="missing-kind"),
        pytest.param(
            lambda: build_valid_at_epoch_query(kind=exp.Literal.string("EPOCH")),
            id="kind-not-a-var",
        ),
        pytest.param(
            lambda: build_valid_at_epoch_query(value=exp.var("SOON")), id="invalid-epoch-word"
        ),
        pytest.param(
            lambda: build_valid_at_epoch_query(value=exp.Literal.string("5")),
            id="epoch-value-is-a-string",
        ),
        pytest.param(
            lambda: build_valid_at_epoch_query(value=exp.Literal.number("5.5")),
            id="epoch-value-is-not-an-integer",
        ),
        pytest.param(lambda: build_valid_at_epoch_query(value=None), id="missing-value"),
        pytest.param(
            lambda: build_valid_at_epoch_query(kind=exp.var("TIME"), value=exp.var("LATEST")),
            id="time-value-is-a-var",
        ),
        pytest.param(
            lambda: build_valid_at_epoch_query(kind=exp.var("TIME"), value=exp.Literal.number(5)),
            id="time-value-is-numeric",
        ),
        pytest.param(lambda: build_valid_at_epoch_query(this=None), id="missing-query"),
        pytest.param(
            lambda: build_valid_at_epoch_query(this=exp.column("x")), id="query-is-a-column"
        ),
        pytest.param(
            lambda: build_valid_at_epoch_query(
                this=exp.Insert(this=exp.to_table("t"), expression=exp.select("1"))
            ),
            id="query-is-an-insert",
        ),
    ],
)
def test_malformed_programmatic_at_epoch_query_asts_fail_atomically(
    node_builder: object,
) -> None:
    expression = node_builder()  # type: ignore[operator]
    with pytest.raises(UnsupportedError):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_optimizer_qualify_and_optimize_are_stable_but_do_not_fully_qualify() -> None:
    """``qualify()``/``optimize()`` do not crash and preserve the ``AtEpochQuery``
    root, dump/load, and structural validity -- the common release gate's
    "optimizer stability" requirement. This is a deliberately weaker claim
    than full support: neither one requires the root itself to be an
    ``exp.Query``, so both run, but their scope-building does not treat the
    wrapped ``this`` as a normal top-level query scope, so previously
    unqualified columns are identifier-quoted only, not resolved to their
    source table, unlike the identical query without the prefix. This is a
    documented residual, not a crash or a wrong answer: already-qualified
    references (for example a JOIN condition written as ``t1.a = t2.b``)
    stay correctly qualified, and no column is ever resolved to the wrong
    table. Out of scope to close in Q06 -- neither qualify/lineage support
    nor the AT-epoch prefix are in Q07's own multi-statement corpus.
    """

    schema = {"t": {"a": "INT", "b": "VARCHAR"}}
    expression = parse_at_epoch_query("AT EPOCH LATEST SELECT a, b FROM t")

    unwrapped_qualified = qualify(expression.this.copy(), dialect="vertica", schema=schema)
    unwrapped_columns = {
        column.name: column.table
        for column in unwrapped_qualified.find_all(exp.Column)
        if column.name in {"a", "b"}
    }
    assert unwrapped_columns == {"a": "t", "b": "t"}

    qualified = qualify(expression.copy(), dialect="vertica", schema=schema)
    assert isinstance(qualified, vexp.AtEpochQuery)
    assert isinstance(qualified.this, exp.Select)
    wrapped_columns = {
        column.name: column.table
        for column in qualified.find_all(exp.Column)
        if column.name in {"a", "b"}
    }
    assert wrapped_columns == {"a": "", "b": ""}
    assert qualified.sql(dialect="vertica") == 'AT EPOCH LATEST SELECT "a", "b" FROM "t"'

    joined = parse_at_epoch_query("AT EPOCH LATEST SELECT a, b FROM t1 JOIN t2 ON t1.a = t2.b")
    join_schema = {"t1": {"a": "INT"}, "t2": {"b": "VARCHAR"}}
    qualified_join = qualify(joined.copy(), dialect="vertica", schema=join_schema)
    already_qualified = {
        column.sql(dialect="vertica")
        for column in qualified_join.find_all(exp.Column)
        if column.table
    }
    assert already_qualified == {'"t1"."a"', '"t2"."b"'}

    optimized = optimize(expression.copy(), dialect="vertica", schema=schema)
    assert isinstance(optimized, vexp.AtEpochQuery)
    restored = exp.Expr.load(optimized.dump())
    assert restored == optimized


def test_lineage_requires_unwrapping_the_prefix() -> None:
    """Documented residual: ``lineage()``'s entry point requires a
    ``Select``-rooted input, so it raises against the wrapper directly and
    must instead be called against ``expression.this``.
    """

    schema = {"t": {"a": "INT", "b": "VARCHAR"}}
    expression = parse_at_epoch_query("AT EPOCH LATEST SELECT a, b FROM t")

    with pytest.raises(Exception, match="must be SELECT"):
        lineage("a", expression, schema=schema, dialect="vertica")

    node = lineage("a", expression.this, schema=schema, dialect="vertica")
    assert {downstream.name for downstream in node.walk()} >= {"a", "t.a"}
