"""Vertica joined-table grammar and strict AST validation."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.lineage import lineage
from sqlglot.optimizer import optimize
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from tests.helpers import assert_roundtrip


@pytest.mark.parametrize(
    ("sql", "method", "side", "kind"),
    [
        ("SELECT * FROM a JOIN b ON a.id = b.id", "", "", ""),
        ("SELECT * FROM a INNER JOIN b USING (id)", "", "", "INNER"),
        ("SELECT * FROM a LEFT JOIN b ON a.id = b.id", "", "LEFT", ""),
        ("SELECT * FROM a LEFT OUTER JOIN b USING (id)", "", "LEFT", "OUTER"),
        ("SELECT * FROM a RIGHT JOIN b ON a.id = b.id", "", "RIGHT", ""),
        ("SELECT * FROM a RIGHT OUTER JOIN b USING (id)", "", "RIGHT", "OUTER"),
        ("SELECT * FROM a FULL JOIN b ON a.id = b.id", "", "FULL", ""),
        ("SELECT * FROM a FULL OUTER JOIN b USING (id)", "", "FULL", "OUTER"),
        ("SELECT * FROM a NATURAL JOIN b", "NATURAL", "", ""),
        ("SELECT * FROM a NATURAL INNER JOIN b", "NATURAL", "", "INNER"),
        ("SELECT * FROM a NATURAL LEFT OUTER JOIN b", "NATURAL", "LEFT", "OUTER"),
        ("SELECT * FROM a NATURAL RIGHT OUTER JOIN b", "NATURAL", "RIGHT", "OUTER"),
        ("SELECT * FROM a NATURAL FULL OUTER JOIN b", "NATURAL", "FULL", "OUTER"),
        ("SELECT * FROM a CROSS JOIN b", "", "", "CROSS"),
        ("SELECT * FROM a, b", "", "", ""),
    ],
)
def test_documented_join_kinds_round_trip(sql: str, method: str, side: str, kind: str) -> None:
    expression = assert_roundtrip(sql)
    join = expression.args["joins"][0]
    assert isinstance(join, exp.Join)
    assert join.method == method
    assert join.side == side
    assert join.kind == kind


def test_tablesample_and_structured_hint_keep_legal_positions() -> None:
    expression = assert_roundtrip(
        "SELECT /*+SYNTACTIC_JOIN*/ * FROM a TABLESAMPLE(25) "
        "JOIN /*+JTYPE(H),DISTRIB(L,R)*/ b TABLESAMPLE(50) ON a.id=b.id",
        "SELECT /*+ SYNTACTIC_JOIN */ * FROM a TABLESAMPLE (25) "
        "JOIN /*+ JTYPE(H), DISTRIB(L, R) */ b TABLESAMPLE (50) ON a.id = b.id",
    )
    join = expression.args["joins"][0]
    assert isinstance(join.args.get("hint"), exp.Hint)
    assert isinstance(expression.args["from_"].this.args.get("sample"), exp.TableSample)
    assert isinstance(join.this.args.get("sample"), exp.TableSample)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM a JOIN (SELECT id FROM b) AS q ON a.id = q.id",
        "WITH q AS (SELECT id FROM b) SELECT * FROM a LEFT JOIN q USING (id)",
        "SELECT * FROM (a JOIN b ON a.id = b.id) JOIN c ON b.id = c.id",
        "SELECT * FROM a JOIN b ON a.id = b.id JOIN c USING (id)",
        "SELECT * FROM a /* left */ JOIN /* join */ b ON a.id = b.id /* predicate */",
    ],
)
def test_nested_chained_cte_and_comments_round_trip(sql: str) -> None:
    assert_roundtrip(sql)


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (
            "SELECT * FROM a LEFT SEMI JOIN b ON a.id = b.id",
            "SELECT * FROM a WHERE EXISTS(SELECT 1 FROM b WHERE a.id = b.id)",
        ),
        (
            "SELECT * FROM a LEFT ANTI JOIN b ON a.id = b.id",
            "SELECT * FROM a WHERE NOT EXISTS(SELECT 1 FROM b WHERE a.id = b.id)",
        ),
        (
            "SELECT * FROM a CROSS APPLY (SELECT a.id) AS q",
            "SELECT * FROM a INNER JOIN LATERAL (SELECT a.id) AS q ON TRUE",
        ),
        (
            "SELECT * FROM a OUTER APPLY (SELECT a.id) AS q",
            "SELECT * FROM a LEFT JOIN LATERAL (SELECT a.id) AS q ON TRUE",
        ),
    ],
)
def test_architecture_approved_join_lowerings(sql: str, expected: str) -> None:
    expression = parse_one(sql, read="vertica")
    generated = expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
    assert generated == expected
    assert parse_one(generated, read="vertica").sql(dialect="vertica") == expected


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM a JOIN b",
        "SELECT * FROM a LEFT JOIN b",
        "SELECT * FROM a OUTER JOIN b ON a.id = b.id",
        "SELECT * FROM a LEFT INNER JOIN b ON a.id = b.id",
        "SELECT * FROM a NATURAL CROSS JOIN b",
        "SELECT * FROM a NATURAL LEFT JOIN b",
        "SELECT * FROM a NATURAL JOIN b ON a.id = b.id",
        "SELECT * FROM a NATURAL JOIN b USING (id)",
        "SELECT * FROM a CROSS JOIN b ON a.id = b.id",
        "SELECT * FROM a CROSS JOIN b USING (id)",
        "SELECT * FROM a ASOF JOIN b ON a.id = b.id",
        "SELECT * FROM a STRAIGHT_JOIN b ON a.id = b.id",
        "SELECT * FROM a RIGHT SEMI JOIN b ON a.id = b.id",
        "SELECT * FROM a SEMI JOIN b USING (id)",
        "SELECT * FROM a JOIN b USING ()",
    ],
)
@pytest.mark.parametrize("error_level", list(ErrorLevel))
def test_recognized_invalid_joins_fail_at_every_error_level(
    sql: str, error_level: ErrorLevel
) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


def _select_with_join(join: exp.Join) -> exp.Select:
    expression = exp.select("*").from_("a")
    expression.set("joins", [join])
    return expression


@pytest.mark.parametrize(
    "join",
    [
        exp.Join(this=exp.to_table("b"), method="ASOF", on=exp.true()),
        exp.Join(this=exp.to_table("b"), method="POSITIONAL", on=exp.true()),
        exp.Join(this=exp.to_table("b"), kind="STRAIGHT_JOIN", on=exp.true()),
        exp.Join(this=exp.to_table("b"), kind="CROSS", on=exp.true()),
        exp.Join(this=exp.to_table("b"), method="NATURAL", on=exp.true()),
        exp.Join(this=exp.to_table("b"), side="LEFT"),
        exp.Join(this=exp.to_table("b"), side="RIGHT", kind="INNER", on=exp.true()),
        exp.Join(this=exp.to_table("b"), kind="OUTER", on=exp.true()),
        exp.Join(this=exp.to_table("b"), on=exp.true(), using=[exp.to_identifier("id")]),
        exp.Join(this=exp.to_table("b"), side="LEFT", using=[]),
        exp.Join(this=exp.to_table("b"), side="LEFT", using=[exp.column("id")]),
        exp.Join(this=exp.to_table("b"), side="LEFT", on="bad"),
        exp.Join(this=exp.to_table("b"), global_=False, on=exp.true()),
        exp.Join(this=exp.to_table("b"), match_condition=None, on=exp.true()),
        exp.Join(this=exp.to_table("b"), directed=False, on=exp.true()),
        exp.Join(this=exp.to_table("b"), expressions=[], on=exp.true()),
        exp.Join(this=exp.to_table("b"), pivots=[], on=exp.true()),
        exp.Join(this=exp.to_table("b"), hint="JTYPE", on=exp.true()),
        exp.Join(
            this=exp.to_table("b"),
            hint=exp.Hint(expressions=[exp.var("UNKNOWN")]),
            on=exp.true(),
        ),
        exp.Join(this=None, on=exp.true()),
        exp.Join(this=exp.to_table("b"), mystery=False, on=exp.true()),
        exp.Join(this=exp.to_table("b"), kind="SEMI", side="RIGHT", on=exp.true()),
    ],
)
def test_programmatic_join_mutations_fail_strict_generation(join: exp.Join) -> None:
    with pytest.raises(UnsupportedError):
        _select_with_join(join).sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_direct_semi_join_fragment_cannot_bypass_select_lowering() -> None:
    join = exp.Join(this=exp.to_table("b"), kind="SEMI", on=exp.true())
    with pytest.raises(UnsupportedError, match="SELECT-owned"):
        join.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_dump_copy_transform_and_parent_metadata() -> None:
    expression = assert_roundtrip("SELECT a.id FROM a LEFT JOIN b ON a.id = b.id JOIN c USING (id)")
    loaded = exp.Expression.load(expression.dump())
    assert loaded == expression
    transformed = expression.copy().transform(
        lambda node: (
            exp.column("key", table=node.table)
            if isinstance(node, exp.Column) and node.name == "id"
            else node
        )
    )
    joins = transformed.args["joins"]
    assert all(join.parent is transformed for join in joins)
    assert [join.index for join in joins] == [0, 1]
    assert all(join.arg_key == "joins" for join in joins)
    assert joins[0].args["on"].parent is joins[0]
    assert joins[1].args["using"][0].parent is joins[1]
    assert parse_one(transformed.sql(dialect="vertica"), read="vertica") == transformed


def test_scope_qualification_optimization_and_lineage_remain_canonical() -> None:
    sql = "SELECT a.id FROM a JOIN b ON a.id = b.a_id"
    schema = {"a": {"id": "INT"}, "b": {"a_id": "INT"}}
    for analyzed in (
        qualify(parse_one(sql, read="vertica"), schema=schema, dialect="vertica"),
        optimize(parse_one(sql, read="vertica"), schema=schema, dialect="vertica"),
    ):
        assert list(traverse_scope(analyzed))
        assert isinstance(analyzed.args["joins"][0], exp.Join)
        assert parse_one(analyzed.sql(dialect="vertica"), read="vertica") == analyzed

    node = lineage("id", parse_one(sql, read="vertica"), schema=schema, dialect="vertica")
    assert "a.id" in {downstream.name for downstream in node.walk()}


def test_foreign_parsed_valid_join_generates_vertica() -> None:
    expression = parse_one("SELECT * FROM a LEFT JOIN b USING (id)", read="postgres")
    assert expression.sql(dialect="vertica") == "SELECT * FROM a LEFT JOIN b USING (id)"
