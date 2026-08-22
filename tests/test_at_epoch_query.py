"""Vertica SELECT ``[ AT epoch ]`` historical-query prefix regressions."""

from __future__ import annotations

import typing as t

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import OptimizeError, ParseError, UnsupportedError
from sqlglot.lineage import lineage
from sqlglot.optimizer import optimize
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip

FOREIGN_DIALECTS = ["postgres", "duckdb", "mysql", "sqlite"]
ALL_PARSE_LEVELS = [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]
ALL_UNSUPPORTED_LEVELS = [ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]
HISTORICAL_QUERY_TYPES = (
    vexp.AtEpochSelect,
    vexp.AtEpochUnion,
    vexp.AtEpochIntersect,
    vexp.AtEpochExcept,
)
HistoricalQuery: t.TypeAlias = t.Union[
    vexp.AtEpochSelect,
    vexp.AtEpochUnion,
    vexp.AtEpochIntersect,
    vexp.AtEpochExcept,
]


def parse_at_epoch_query(sql: str, expected: str | None = None) -> HistoricalQuery:
    expression = assert_roundtrip(sql, expected)
    assert isinstance(expression, HISTORICAL_QUERY_TYPES)
    return expression


def test_epoch_latest() -> None:
    expression = parse_at_epoch_query(
        "AT EPOCH LATEST SELECT * FROM t", "AT EPOCH LATEST SELECT * FROM t"
    )
    assert expression.args["at_epoch_kind"] == exp.var("EPOCH")
    assert expression.args["at_epoch_value"] == exp.var("LATEST")
    assert type(expression) is vexp.AtEpochSelect


def test_epoch_integer() -> None:
    expression = parse_at_epoch_query("AT EPOCH 5 SELECT * FROM t", "AT EPOCH 5 SELECT * FROM t")
    value = expression.args["at_epoch_value"]
    assert isinstance(value, exp.Literal) and value.is_int and value.name == "5"


def test_time_literal() -> None:
    expression = parse_at_epoch_query(
        "AT TIME '2024-01-01 00:00:00' SELECT * FROM t",
        "AT TIME '2024-01-01 00:00:00' SELECT * FROM t",
    )
    value = expression.args["at_epoch_value"]
    assert isinstance(value, exp.Literal) and value.is_string
    assert value.name == "2024-01-01 00:00:00"


def test_keywords_normalize_case() -> None:
    parse_at_epoch_query("at epoch latest select * from t", "AT EPOCH LATEST SELECT * FROM t")


def test_prefix_scopes_a_with_clause() -> None:
    expression = parse_at_epoch_query(
        "AT EPOCH LATEST WITH cte AS (SELECT 1) SELECT * FROM cte",
        "AT EPOCH LATEST WITH cte AS (SELECT 1) SELECT * FROM cte",
    )
    assert type(expression) is vexp.AtEpochSelect
    assert expression.args.get("with_") is not None


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
    expected_type = {
        exp.Union: vexp.AtEpochUnion,
        exp.Intersect: vexp.AtEpochIntersect,
        exp.Except: vexp.AtEpochExcept,
    }[root_type]
    assert type(expression) is expected_type


def test_prefix_scopes_a_with_clause_and_a_union_chain() -> None:
    sql = "AT EPOCH LATEST WITH cte AS (SELECT 1) SELECT * FROM cte UNION SELECT * FROM cte"
    expression = parse_at_epoch_query(sql, sql)
    assert type(expression) is vexp.AtEpochUnion
    assert expression.args.get("with_") is not None


@pytest.mark.parametrize(
    ("sql", "expected", "root_type"),
    [
        (
            "AT EPOCH LATEST WITH c AS (SELECT a FROM t) "
            "SELECT a FROM c UNION (SELECT a FROM u ORDER BY a LIMIT 1)",
            "AT EPOCH LATEST WITH c AS (SELECT a FROM t) "
            "SELECT a FROM c UNION (SELECT a FROM u ORDER BY a LIMIT 1)",
            vexp.AtEpochUnion,
        ),
        (
            "AT EPOCH 7 WITH c AS (SELECT a FROM t) "
            "SELECT a FROM c UNION ALL (SELECT a FROM u ORDER BY a LIMIT 1)",
            "AT EPOCH 7 WITH c AS (SELECT a FROM t) "
            "SELECT a FROM c UNION ALL (SELECT a FROM u ORDER BY a LIMIT 1)",
            vexp.AtEpochUnion,
        ),
        (
            "AT TIME '2024-01-01' WITH c AS (SELECT a FROM t) "
            "SELECT a FROM c UNION DISTINCT (SELECT a FROM u ORDER BY a LIMIT 1)",
            "AT TIME '2024-01-01' WITH c AS (SELECT a FROM t) "
            "SELECT a FROM c UNION (SELECT a FROM u ORDER BY a LIMIT 1)",
            vexp.AtEpochUnion,
        ),
        (
            "AT EPOCH LATEST WITH c AS (WITH d AS (SELECT a FROM t) SELECT a FROM d) "
            "SELECT a FROM c INTERSECT DISTINCT (SELECT a FROM u ORDER BY a LIMIT 1)",
            "AT EPOCH LATEST WITH c AS (WITH d AS (SELECT a FROM t) SELECT a FROM d) "
            "SELECT a FROM c INTERSECT (SELECT a FROM u ORDER BY a LIMIT 1)",
            vexp.AtEpochIntersect,
        ),
        (
            "AT EPOCH 9 WITH /*+ENABLE_WITH_CLAUSE_MATERIALIZATION */ "
            "c AS (SELECT a FROM t) SELECT a FROM c EXCEPT DISTINCT "
            "(SELECT a FROM u ORDER BY a LIMIT 1)",
            "AT EPOCH 9 WITH /*+ ENABLE_WITH_CLAUSE_MATERIALIZATION */ "
            "c AS (SELECT a FROM t) SELECT a FROM c EXCEPT "
            "(SELECT a FROM u ORDER BY a LIMIT 1)",
            vexp.AtEpochExcept,
        ),
        (
            "AT TIME '2024-01-02' WITH c AS (SELECT a FROM t) "
            "SELECT a FROM c MINUS (SELECT a FROM u ORDER BY a LIMIT 1) "
            "ORDER BY a LIMIT 2",
            "AT TIME '2024-01-02' WITH c AS (SELECT a FROM t) "
            "SELECT a FROM c EXCEPT (SELECT a FROM u ORDER BY a LIMIT 1) "
            "ORDER BY a LIMIT 2",
            vexp.AtEpochExcept,
        ),
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_prefix_with_and_parenthesized_set_branches_compose(
    sql: str,
    expected: str,
    root_type: type[exp.SetOperation],
    error_level: ErrorLevel,
) -> None:
    expression = parse_one(sql, read="vertica", error_level=error_level)
    assert type(expression) is root_type
    assert isinstance(expression.args.get("with_"), exp.With)
    assert isinstance(expression.expression, exp.Subquery)
    assert expression.sql(dialect="vertica") == expected

    pretty = expression.sql(dialect="vertica", pretty=True)
    assert parse_one(pretty, read="vertica") == expression
    assert exp.Expr.load(expression.dump()) == expression


@pytest.mark.parametrize(
    ("sql", "comment"),
    [
        (
            "/* before_at */ AT EPOCH LATEST WITH c AS (SELECT a FROM t) "
            "SELECT a FROM c UNION ALL SELECT a FROM u",
            "before_at",
        ),
        (
            "AT /* after_at */ EPOCH LATEST WITH c AS (SELECT a FROM t) "
            "SELECT a FROM c UNION ALL SELECT a FROM u",
            "after_at",
        ),
        (
            "AT EPOCH LATEST WITH /* with_boundary */ c AS (SELECT a FROM t) "
            "SELECT a FROM c UNION ALL SELECT a FROM u",
            "with_boundary",
        ),
    ],
)
def test_prefix_comments_have_one_stable_historical_root_owner(sql: str, comment: str) -> None:
    expression = parse_one(sql, read="vertica")
    assert isinstance(expression, vexp.AtEpochUnion)
    assert expression.comments and any(comment in value for value in expression.comments)
    assert [node for node in expression.walk() if node.comments] == [expression]

    compact = expression.sql(dialect="vertica")
    pretty = expression.sql(dialect="vertica", pretty=True)
    for generated in (compact, pretty):
        assert generated.lstrip().startswith(f"/* {comment} */")
        assert generated.lstrip()[len(f"/* {comment} */") :].lstrip().startswith("AT EPOCH LATEST")
        reparsed = parse_one(generated, read="vertica")
        assert reparsed == expression
        assert reparsed.sql(dialect="vertica", pretty=generated == pretty) == generated


def test_set_boundary_comment_remains_on_its_source_and_is_text_stable() -> None:
    expression = parse_one(
        "AT EPOCH LATEST WITH c AS (SELECT a FROM t) "
        "SELECT a FROM c /* set_boundary */ UNION ALL SELECT a FROM u",
        read="vertica",
    )
    comment_owners = [node for node in expression.walk() if node.comments]
    assert len(comment_owners) == 1
    assert isinstance(comment_owners[0], exp.Table)

    generated = expression.sql(dialect="vertica")
    reparsed = parse_one(generated, read="vertica")
    assert reparsed == expression
    assert reparsed.sql(dialect="vertica") == generated


def test_composed_historical_set_root_parent_and_analysis_contract() -> None:
    sql = (
        "AT EPOCH LATEST WITH c AS (SELECT a FROM t) "
        "SELECT a FROM c UNION ALL (SELECT a FROM u ORDER BY a LIMIT 1)"
    )
    schema = {"t": {"a": "INT"}, "u": {"a": "INT"}}
    expression = parse_at_epoch_query(sql, sql)
    assert isinstance(expression, vexp.AtEpochUnion)
    assert isinstance(expression.expression, exp.Subquery)
    assert expression.expression.parent is expression
    assert expression.expression.arg_key == "expression"
    assert expression.args["with_"].parent is expression

    for analysis in (qualify, optimize):
        analyzed = analysis(expression.copy(), dialect="vertica", schema=schema)
        assert isinstance(analyzed, vexp.AtEpochUnion)
        assert list(traverse_scope(analyzed))
        assert analyzed.sql(dialect="vertica").startswith("AT EPOCH LATEST")

    lineage_names = {
        node.name for node in lineage("a", expression, schema=schema, dialect="vertica").walk()
    }
    assert lineage_names >= {"t.a", "u.a"}


@pytest.mark.parametrize("dialect", FOREIGN_DIALECTS)
@pytest.mark.parametrize("unsupported_level", ALL_UNSUPPORTED_LEVELS)
def test_composed_historical_set_root_fails_atomically_abroad(
    dialect: str, unsupported_level: ErrorLevel
) -> None:
    expression = parse_one(
        "AT EPOCH LATEST WITH c AS (SELECT a FROM t) "
        "SELECT a FROM c UNION ALL (SELECT a FROM u ORDER BY a LIMIT 1)",
        read="vertica",
    )
    nested = exp.select("*").from_(expression.subquery("historical"))
    for candidate in (expression, nested):
        with pytest.raises(ValueError, match="AtEpochUnion"):
            candidate.sql(dialect=dialect, unsupported_level=unsupported_level)


def test_multi_statement_boundaries() -> None:
    statements = parse("AT EPOCH LATEST SELECT 1; AT EPOCH 2 SELECT 2", read="vertica")
    assert len(statements) == 2
    assert all(isinstance(statement, HISTORICAL_QUERY_TYPES) for statement in statements)


def test_leading_comment_is_retained() -> None:
    expression = parse_one("/* scratch */ AT EPOCH LATEST SELECT * FROM t", read="vertica")
    assert isinstance(expression, HISTORICAL_QUERY_TYPES)
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
    assert not any(isinstance(prop, HISTORICAL_QUERY_TYPES) for prop in properties)


@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_cte_body_rejects_a_statement_level_historical_prefix(
    error_level: ErrorLevel,
) -> None:
    with pytest.raises(ParseError, match="CTE bodies require a SELECT query expression"):
        parse_one(
            "WITH cte AS (AT EPOCH LATEST SELECT 1) SELECT * FROM cte",
            read="vertica",
            error_level=error_level,
        )


@pytest.mark.parametrize(
    "sql",
    [
        "WITH cte AS (SELECT 1) AT EPOCH LATEST SELECT * FROM cte",
    ],
)
def test_prefix_after_an_outer_with_clause_fails_closed(sql: str) -> None:
    """The analyzer-safe root has a WITH slot, so parser provenance must still
    enforce the documented prefix-before-WITH order explicitly.
    """

    with pytest.raises(ParseError, match="must precede a WITH clause"):
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
    assert not isinstance(expression, HISTORICAL_QUERY_TYPES)


def test_parent_metadata_and_copy_stability() -> None:
    expression = parse_at_epoch_query("AT EPOCH 5 SELECT a FROM t")
    assert isinstance(expression, vexp.AtEpochSelect)
    projection = expression.expressions[0]
    assert projection.parent is expression
    assert projection.arg_key == "expressions"
    assert expression.args["at_epoch_kind"].parent is expression
    assert expression.args["at_epoch_value"].parent is expression

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
    with pytest.raises(ValueError, match="AtEpoch"):
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
    """The Q06 wrapper remains a supported serialized-AST compatibility path."""

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

    restored = exp.Expr.load(integer_form.dump())
    assert type(restored) is vexp.AtEpochQuery
    assert restored.sql(dialect="vertica") == "AT EPOCH 5 SELECT a FROM t"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("at_epoch_kind", None),
        ("at_epoch_kind", exp.var("SNAPSHOT")),
        ("at_epoch_value", None),
        ("at_epoch_value", exp.Literal.string("LATEST")),
    ],
)
def test_malformed_programmatic_analyzer_safe_roots_fail_atomically(
    field: str, value: exp.Expr | None
) -> None:
    expression = parse_at_epoch_query("AT EPOCH LATEST SELECT a FROM t")
    expression.set(field, value)
    with pytest.raises(UnsupportedError):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_malformed_programmatic_historical_set_root_fails_atomically() -> None:
    expression = parse_at_epoch_query("AT EPOCH LATEST SELECT a FROM t UNION SELECT a FROM u")
    expression.set("expression", exp.column("not_a_query"))
    with pytest.raises(UnsupportedError):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


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


def test_optimizer_qualification_and_scope_match_the_unprefixed_select() -> None:
    schema = {"t": {"a": "INT", "b": "VARCHAR"}}
    expression = parse_at_epoch_query("AT EPOCH LATEST SELECT a, b FROM t")
    control = parse_one("SELECT a, b FROM t", read="vertica")

    qualified = qualify(expression.copy(), dialect="vertica", schema=schema)
    qualified_control = qualify(control, dialect="vertica", schema=schema)
    assert isinstance(qualified, vexp.AtEpochSelect)
    historical_columns = {
        column.name: column.table
        for column in qualified.find_all(exp.Column)
        if column.name in {"a", "b"}
    }
    control_columns = {
        column.name: column.table
        for column in qualified_control.find_all(exp.Column)
        if column.name in {"a", "b"}
    }
    assert historical_columns == control_columns == {"a": "t", "b": "t"}
    assert [set(scope.sources) for scope in traverse_scope(qualified)] == [
        set(scope.sources) for scope in traverse_scope(qualified_control)
    ]

    optimized = optimize(expression.copy(), dialect="vertica", schema=schema)
    assert isinstance(optimized, vexp.AtEpochSelect)
    restored = exp.Expr.load(optimized.dump())
    assert restored == optimized


def test_lineage_accepts_the_historical_select_root_directly() -> None:
    schema = {"t": {"a": "INT", "b": "VARCHAR"}}
    expression = parse_at_epoch_query("AT EPOCH LATEST SELECT a, b FROM t")
    node = lineage("a", expression, schema=schema, dialect="vertica")
    assert {downstream.name for downstream in node.walk()} >= {"a", "t.a"}


@pytest.mark.parametrize(
    ("operator", "root_type"),
    [
        ("UNION", vexp.AtEpochUnion),
        ("INTERSECT", vexp.AtEpochIntersect),
        ("EXCEPT", vexp.AtEpochExcept),
    ],
)
def test_set_operation_roots_have_direct_analysis_parity(
    operator: str, root_type: type[exp.SetOperation]
) -> None:
    schema = {"t": {"a": "INT"}, "u": {"a": "INT"}}
    body = f"SELECT a FROM t {operator} SELECT a FROM u"
    historical = parse_at_epoch_query(f"AT EPOCH LATEST {body}")
    control = parse_one(body, read="vertica")

    assert type(historical) is root_type
    assert [set(scope.sources) for scope in traverse_scope(historical)] == [
        set(scope.sources) for scope in traverse_scope(control)
    ]
    qualified = qualify(historical.copy(), dialect="vertica", schema=schema)
    optimized = optimize(historical.copy(), dialect="vertica", schema=schema)
    assert type(qualified) is root_type
    assert type(optimized) is root_type
    lineage_names = {
        node.name for node in lineage("a", historical, schema=schema, dialect="vertica").walk()
    }
    assert lineage_names >= {
        "t.a",
        "u.a",
    }


def test_joined_grouped_cte_analysis_uses_the_public_historical_root() -> None:
    sql = (
        "AT EPOCH LATEST WITH c AS (SELECT t.a, u.b FROM t "
        "JOIN u ON t.id = u.id) SELECT a, COUNT(b) AS n FROM c GROUP BY a"
    )
    schema = {
        "t": {"id": "INT", "a": "INT"},
        "u": {"id": "INT", "b": "INT"},
    }
    expression = parse_at_epoch_query(sql)
    qualified = qualify(expression.copy(), dialect="vertica", schema=schema)
    assert isinstance(qualified, vexp.AtEpochSelect)
    assert [set(scope.sources) for scope in traverse_scope(qualified)] == [{"t", "u"}, {"c"}]
    lineage_names = {
        node.name for node in lineage("a", expression, schema=schema, dialect="vertica").walk()
    }
    assert lineage_names >= {
        "c.a",
        "t.a",
    }


def test_lineage_source_expansion_accepts_the_public_historical_root() -> None:
    expression = parse_at_epoch_query("AT EPOCH LATEST SELECT a FROM supplied")
    node = lineage(
        "a",
        expression,
        sources={"supplied": "SELECT a FROM raw_source"},
        schema={"raw_source": {"a": "INT"}},
        dialect="vertica",
    )
    assert {downstream.name for downstream in node.walk()} >= {
        "supplied.a",
        "raw_source.a",
    }


def test_ambiguous_column_failure_matches_the_unprefixed_query() -> None:
    schema = {"t": {"id": "INT"}, "u": {"id": "INT"}}
    historical = parse_at_epoch_query("AT EPOCH LATEST SELECT id FROM t JOIN u ON t.id = u.id")
    control = parse_one("SELECT id FROM t JOIN u ON t.id = u.id", read="vertica")
    for expression in (historical, control):
        with pytest.raises(OptimizeError, match="could not be resolved"):
            qualify(expression, dialect="vertica", schema=schema)
