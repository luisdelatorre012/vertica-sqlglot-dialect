"""Strict Vertica SELECT qualifier, row-tail, and lock regressions."""

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
    ("sql", "expected", "distinct"),
    [
        ("SELECT a FROM t", "SELECT a FROM t", False),
        ("SELECT ALL a FROM t", "SELECT a FROM t", False),
        ("SELECT DISTINCT a FROM t", "SELECT DISTINCT a FROM t", True),
    ],
)
def test_documented_select_qualifiers(sql: str, expected: str, distinct: bool) -> None:
    expression = assert_roundtrip(sql, expected)
    distinct_expression = expression.args.get("distinct")
    assert isinstance(distinct_expression, exp.Distinct) is distinct
    if distinct_expression:
        assert distinct_expression.args == {"on": None}


@pytest.mark.parametrize("count", ["0", "1", "999999999999999999999999999999999999", "?"])
@pytest.mark.parametrize("clause", ["LIMIT", "OFFSET"])
def test_ordinary_row_counts_preserve_boundaries_and_parameters(count: str, clause: str) -> None:
    expression = assert_roundtrip(f"SELECT a FROM t {clause} {count}")
    tail = expression.args[clause.lower()]
    assert isinstance(tail, exp.Limit if clause == "LIMIT" else exp.Offset)
    if count == "?":
        assert isinstance(tail.expression, exp.Placeholder)
        assert tail.expression.args == {"jdbc": True}
    else:
        assert isinstance(tail.expression, exp.Literal)
        assert tail.expression.this == count


def test_limit_all_is_deliberate_no_op_and_composes_with_later_tails() -> None:
    expression = assert_roundtrip(
        "SELECT a FROM t LIMIT ALL OFFSET 2 FOR UPDATE",
        "SELECT a FROM t OFFSET 2 FOR UPDATE",
    )
    assert expression.args.get("limit") is None
    assert isinstance(expression.args.get("offset"), exp.Offset)
    assert len(expression.args["locks"]) == 1


def test_both_source_backed_limit_offset_orders_canonicalize_stably() -> None:
    # SELECT's formal syntax places OFFSET before LIMIT, while the official
    # set-operation pages and long-standing examples use LIMIT before OFFSET.
    # Both are accepted and canonicalized to SQLGlot's stable LIMIT/OFFSET order.
    for sql in (
        "SELECT a FROM t ORDER BY a OFFSET 2 LIMIT 5",
        "SELECT a FROM t ORDER BY a LIMIT 5 OFFSET 2",
    ):
        expression = assert_roundtrip(sql, "SELECT a FROM t ORDER BY a LIMIT 5 OFFSET 2")
        assert isinstance(expression.args.get("limit"), exp.Limit)
        assert isinstance(expression.args.get("offset"), exp.Offset)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT a FROM t FOR UPDATE",
        "SELECT a FROM t FOR UPDATE OF t",
        "SELECT a FROM t FOR UPDATE OF t, s.u",
        "SELECT a FROM t LIMIT 5 FOR UPDATE OF t",
    ],
)
def test_documented_for_update_forms(sql: str) -> None:
    expression = assert_roundtrip(sql)
    locks = expression.args.get("locks")
    assert isinstance(locks, list) and len(locks) == 1
    assert locks[0].args.get("update") is True
    assert locks[0].args.get("wait") is None
    assert locks[0].args.get("key") is None
    assert not list(locks[0].find_all(exp.Table))


def _lock_target_names(expression: exp.Expr) -> tuple[tuple[str, ...], ...]:
    lock = expression.args["locks"][0]
    return tuple(
        tuple(
            part.name
            for part in ([target] if isinstance(target, exp.Identifier) else target.flatten())
        )
        for target in lock.expressions
    )


@pytest.mark.parametrize(
    ("sql", "schema", "targets", "lineage_names"),
    [
        (
            "SELECT a FROM t FOR UPDATE OF t",
            {"t": {"a": "INT"}},
            (("t",),),
            {"a", "t.a"},
        ),
        (
            "SELECT x.a AS a FROM t AS x FOR UPDATE OF x",
            {"t": {"a": "INT"}},
            (("x",),),
            {"a", "x.a"},
        ),
        (
            "SELECT t.a AS a FROM t JOIN u ON t.id = u.id FOR UPDATE OF t, u",
            {"t": {"a": "INT", "id": "INT"}, "u": {"id": "INT"}},
            (("t",), ("u",)),
            {"a", "t.a"},
        ),
        (
            "SELECT q.a AS a FROM (SELECT a FROM t) AS q FOR UPDATE OF q",
            {"t": {"a": "INT"}},
            (("q",),),
            {"a", "q.a", "t.a"},
        ),
        (
            "WITH c AS (SELECT a FROM t) SELECT c.a AS a FROM c FOR UPDATE OF c",
            {"t": {"a": "INT"}},
            (("c",),),
            {"a", "c.a", "t.a"},
        ),
        (
            "SELECT a FROM t UNION ALL SELECT a FROM u FOR UPDATE OF t, u",
            {"t": {"a": "INT"}, "u": {"a": "INT"}},
            (("t",), ("u",)),
            {"UNION", "0", "t.a", "u.a"},
        ),
        (
            "AT EPOCH LATEST SELECT a FROM t FOR UPDATE OF t",
            {"t": {"a": "INT"}},
            (("t",),),
            {"a", "t.a"},
        ),
        (
            "AT EPOCH 7 SELECT a FROM t INTERSECT SELECT a FROM u FOR UPDATE OF t, u",
            {"t": {"a": "INT"}, "u": {"a": "INT"}},
            (("t",), ("u",)),
            {"ATEPOCHINTERSECT", "0", "t.a", "u.a"},
        ),
    ],
)
def test_for_update_targets_are_analyzer_safe(
    sql: str,
    schema: dict[str, dict[str, str]],
    targets: tuple[tuple[str, ...], ...],
    lineage_names: set[str],
) -> None:
    expression = assert_roundtrip(sql)
    assert _lock_target_names(expression) == targets

    scopes = traverse_scope(expression)
    assert scopes
    selected_sources = [scope.selected_sources for scope in scopes]
    assert any(selected_sources)

    for analyzed in (
        qualify(expression.copy(), schema=schema, dialect="vertica"),
        optimize(expression.copy(), schema=schema, dialect="vertica"),
    ):
        assert _lock_target_names(analyzed) == targets
        assert parse_one(analyzed.sql(dialect="vertica"), read="vertica") == analyzed

    node = lineage("a", expression.copy(), schema=schema, dialect="vertica")
    assert {downstream.name for downstream in node.walk()} == lineage_names


def test_qualified_lock_targets_serialize_copy_transform_and_keep_comments() -> None:
    sql = 'SELECT a FROM db.s.t FOR UPDATE OF db.s.t, "LockAlias" /* lock target */'
    expression = assert_roundtrip(sql)
    assert _lock_target_names(expression) == (("db", "s", "t"), ("LockAlias",))
    assert "lock target" in expression.sql(dialect="vertica")

    loaded = exp.Expression.load(expression.dump())
    copied = expression.copy()
    transformed = copied.transform(
        lambda node: (
            exp.to_identifier("renamed", quoted=True)
            if isinstance(node, exp.Identifier) and node.name == "LockAlias"
            else node
        )
    )
    assert loaded == expression
    assert _lock_target_names(transformed) == (("db", "s", "t"), ("renamed",))
    lock = transformed.args["locks"][0]
    assert all(
        target.parent is lock and target.arg_key == "expressions" for target in lock.expressions
    )
    qualified = lock.expressions[0]
    assert isinstance(qualified, exp.Dot)
    assert all(part.parent is not None for part in qualified.flatten())


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT a FROM t LIMIT 2",
        "SELECT * FROM (SELECT a FROM t LIMIT 2) AS q",
        "WITH q AS (SELECT a FROM t OFFSET 1 LIMIT 2) SELECT * FROM q",
        "(SELECT a FROM t LIMIT 2) UNION ALL (SELECT a FROM u OFFSET 1 LIMIT 3)",
        "SELECT a FROM t UNION ALL SELECT a FROM u ORDER BY a LIMIT 4 OFFSET 2 FOR UPDATE",
    ],
)
def test_direct_nested_cte_branch_and_compound_tail_ownership(sql: str) -> None:
    expression = assert_roundtrip(sql)
    assert list(expression.find_all((exp.Limit, exp.Offset, exp.Lock)))


def test_comments_and_multi_statement_boundaries_survive() -> None:
    script = (
        "SELECT a FROM t ORDER BY a /* before limit */ LIMIT 2 /* before lock */ FOR UPDATE; "
        "SELECT b FROM u OFFSET 1"
    )
    statements = parse(script, read="vertica")
    assert len(statements) == 2
    generated = "; ".join(statement.sql(dialect="vertica") for statement in statements if statement)
    assert "before limit" in generated
    assert "before lock" in generated
    assert len(parse(generated, read="vertica")) == 2


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT DISTINCT ON (a) a FROM t",
        "SELECT ALL DISTINCT a FROM t",
        "SELECT DISTINCT ALL a FROM t",
        "SELECT ALL ALL a FROM t",
        "SELECT DISTINCT DISTINCT a FROM t",
        "SELECT TOP 5 a FROM t",
        "SELECT TOP (5) a FROM t",
        "SELECT a FROM t FETCH FIRST 5 ROWS ONLY",
        "SELECT a FROM t FETCH NEXT ROWS ONLY",
        "SELECT a FROM t LIMIT 5, 10",
        "SELECT a FROM t LIMIT 10 PERCENT",
        "SELECT a FROM t LIMIT 10 ROWS ONLY",
        "SELECT a FROM t LIMIT 10 WITH TIES",
        "SELECT a FROM t LIMIT 10 BY a",
        "SELECT a FROM t LIMIT -1",
        "SELECT a FROM t LIMIT 1.5",
        "SELECT a FROM t LIMIT '1'",
        "SELECT a FROM t LIMIT 1 + 1",
        "SELECT a FROM t LIMIT :count",
        "SELECT a FROM t OFFSET -1",
        "SELECT a FROM t OFFSET 1.5",
        "SELECT a FROM t OFFSET '1'",
        "SELECT a FROM t OFFSET 1 + 1",
        "SELECT a FROM t OFFSET :count",
        "SELECT a FROM t OFFSET 1 ROW",
        "SELECT a FROM t OFFSET 1 ROWS",
        "SELECT a FROM t OFFSET 1 BY a",
        "SELECT a FROM t FOR SHARE",
        "SELECT a FROM t FOR KEY SHARE",
        "SELECT a FROM t FOR NO KEY UPDATE",
        "SELECT a FROM t FOR UPDATE NOWAIT",
        "SELECT a FROM t FOR UPDATE WAIT 5",
        "SELECT a FROM t FOR UPDATE SKIP LOCKED",
        "SELECT a FROM t FOR UPDATE OF",
        "SELECT a FROM t FOR UPDATE FOR UPDATE",
        "SELECT a FROM t LIMIT 1 LIMIT 2",
        "SELECT a FROM t OFFSET 1 OFFSET 2",
        "SELECT a FROM t ORDER BY a ORDER BY b",
        "SELECT a FROM t LIMIT 2 ORDER BY a",
        "SELECT a FROM t FOR UPDATE LIMIT 2",
        "SELECT a FROM t LIMIT 0 OVER (PARTITION BY a ORDER BY b)",
        "SELECT a FROM t LIMIT ? OVER (PARTITION BY a ORDER BY b)",
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_recognized_invalid_select_modifiers_fail_closed(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


def valid_select() -> exp.Select:
    return exp.select("a").from_("t").limit(2).offset(1)


def mutated_select(key: str, value: object) -> exp.Select:
    expression = valid_select()
    expression.set(key, value)
    return expression


@pytest.mark.parametrize(
    "expression",
    [
        mutated_select("distinct", exp.Distinct(on=exp.Tuple(expressions=[exp.column("a")]))),
        mutated_select("distinct", exp.Distinct(expressions=[])),
        mutated_select("distinct", False),
        mutated_select("kind", "STRUCT"),
        mutated_select("kind", ""),
        mutated_select("operation_modifiers", []),
        mutated_select("limit", exp.Fetch(direction="FIRST", count=exp.Literal.number(2))),
        mutated_select("limit", exp.Limit(expression=exp.Literal.number(-1))),
        mutated_select("limit", exp.Limit(expression=exp.column("n"))),
        mutated_select(
            "limit",
            exp.Limit(
                expression=exp.Literal.number(2),
                limit_options=exp.LimitOptions(percent=False),
            ),
        ),
        mutated_select("limit", exp.Limit(expression=exp.Literal.number(2), expressions=[])),
        mutated_select("limit", exp.Limit(this=False, expression=exp.Literal.number(2))),
        mutated_select("offset", exp.Offset(expression=exp.Literal.number(-1))),
        mutated_select("offset", exp.Offset(expression=exp.column("n"))),
        mutated_select("offset", exp.Offset(expression=exp.Literal.number(1), expressions=[])),
        mutated_select("offset", exp.Offset(this=False, expression=exp.Literal.number(1))),
        mutated_select("locks", []),
        mutated_select("locks", [exp.Lock(update=False)]),
        mutated_select("locks", [exp.Lock(update=True, key=False)]),
        mutated_select("locks", [exp.Lock(update=True, wait=False)]),
        mutated_select("locks", [exp.Lock(update=True, expressions=[])]),
        mutated_select("locks", [exp.Lock(update=True, expressions=[exp.column("t")])]),
        mutated_select(
            "locks", [exp.Lock(update=True, expressions=[exp.Identifier(this="", quoted=True)])]
        ),
        mutated_select(
            "locks",
            [
                exp.Lock(
                    update=True, expressions=[exp.Identifier(this="t", quoted=False, extra=False)]
                )
            ],
        ),
        mutated_select(
            "locks",
            [
                exp.Lock(
                    update=True,
                    expressions=[
                        exp.Dot.build([exp.to_identifier(part) for part in ("a", "b", "c", "d")])
                    ],
                )
            ],
        ),
        mutated_select(
            "locks",
            [
                exp.Lock(
                    update=True,
                    expressions=[
                        exp.Table(
                            this=exp.to_identifier("t"),
                            alias=exp.TableAlias(this=exp.to_identifier("x")),
                        )
                    ],
                )
            ],
        ),
        mutated_select("locks", [exp.Lock(update=True), exp.Lock(update=True)]),
        mutated_select("locks", [exp.column("lock")]),
    ],
)
def test_programmatic_select_mutations_fail_atomically(expression: exp.Select) -> None:
    with pytest.raises(UnsupportedError):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "expression",
    [
        exp.Fetch(direction="FIRST", count=exp.Literal.number(2)),
        exp.Limit(expression=exp.column("n")),
        exp.Offset(expression=exp.column("n")),
        exp.Lock(update=False),
        vexp.PartitionedLimit(
            expression=exp.Literal.number(0),
            partition_by=[exp.column("a")],
            order=exp.Order(expressions=[exp.Ordered(this=exp.column("b"))]),
        ),
    ],
)
def test_direct_invalid_tail_nodes_fail_atomically(expression: exp.Expr) -> None:
    with pytest.raises(UnsupportedError):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_invalid_nested_tail_fails_before_sql_is_returned() -> None:
    inner = exp.select("a").from_("t")
    inner.set("limit", exp.Fetch(direction="FIRST", count=exp.Literal.number(2)))
    outer = exp.select("*").from_(inner.subquery("q"))
    with pytest.raises(UnsupportedError):
        outer.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_copy_transform_scope_qualification_optimization_and_lineage() -> None:
    sql = "SELECT a FROM t ORDER BY a LIMIT 2 OFFSET 1 FOR UPDATE"
    schema = {"t": {"a": "INT"}}
    expression = assert_roundtrip(sql)
    copied = expression.copy()
    transformed = copied.transform(
        lambda node: exp.column("b") if isinstance(node, exp.Column) and node.name == "a" else node
    )
    assert transformed.args["limit"].parent is transformed
    assert transformed.args["offset"].parent is transformed
    assert transformed.args["locks"][0].parent is transformed

    for analyzed in (
        qualify(parse_one(sql, read="vertica"), schema=schema, dialect="vertica"),
        optimize(parse_one(sql, read="vertica"), schema=schema, dialect="vertica"),
    ):
        assert isinstance(analyzed.args.get("limit"), exp.Limit)
        assert isinstance(analyzed.args.get("offset"), exp.Offset)
        assert list(traverse_scope(analyzed))
        assert parse_one(analyzed.sql(dialect="vertica"), read="vertica") == analyzed

    node = lineage("a", parse_one(sql, read="vertica"), schema=schema, dialect="vertica")
    assert "t.a" in {downstream.name for downstream in node.walk()}


def test_foreign_parsed_valid_canonical_tail_generates_vertica() -> None:
    expression = parse_one(
        "SELECT DISTINCT a FROM t LIMIT 2 OFFSET 1 FOR UPDATE OF t", read="postgres"
    )
    assert (
        expression.sql(dialect="vertica")
        == "SELECT DISTINCT a FROM t LIMIT 2 OFFSET 1 FOR UPDATE OF t"
    )


def test_for_update_target_foreign_generation_behavior_is_unchanged() -> None:
    expression = parse_one("SELECT a FROM t FOR UPDATE OF t, s.u", read="vertica")
    for dialect in ("postgres", "mysql"):
        assert (
            expression.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)
            == "SELECT a FROM t FOR UPDATE OF t, s.u"
        )
    for dialect in ("duckdb", "sqlite"):
        with pytest.raises(UnsupportedError):
            expression.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)
