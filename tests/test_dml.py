"""Vertica core-DML grammar and AST safety regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError, UnsupportedError

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


@pytest.mark.parametrize(
    ("sql", "expected", "expression_type"),
    [
        (
            "INSERT /*+LABEL('load')*/ INTO db.public.sales(id,amount,note) "
            "VALUES (1,10.5,DEFAULT),(2,NULL,'ok')",
            "INSERT /*+ LABEL('load') */ INTO db.public.sales (id, amount, note) "
            "VALUES (1, 10.5, DEFAULT), (2, NULL, 'ok')",
            exp.Insert,
        ),
        ("INSERT INTO sales DEFAULT VALUES", None, exp.Insert),
        (
            "INSERT INTO archive SELECT * FROM sales WHERE ts<CURRENT_DATE",
            "INSERT INTO archive SELECT * FROM sales WHERE ts < CURRENT_DATE",
            exp.Insert,
        ),
        ("INSERT INTO archive (SELECT id FROM sales)", None, exp.Insert),
        (
            "INSERT INTO archive WITH recent AS (SELECT id FROM sales) SELECT id FROM recent",
            None,
            exp.Insert,
        ),
        (
            "INSERT INTO archive WITH /*+ENABLE_WITH_CLAUSE_MATERIALIZATION*/ "
            "recent AS (SELECT id FROM sales) SELECT id FROM recent",
            "INSERT INTO archive WITH /*+ ENABLE_WITH_CLAUSE_MATERIALIZATION */ "
            "recent AS (SELECT id FROM sales) SELECT id FROM recent",
            exp.Insert,
        ),
        (
            "MERGE INTO target AS t USING source AS s ON t.id=s.id "
            "WHEN MATCHED AND s.changed THEN UPDATE SET value=s.value "
            "WHEN NOT MATCHED AND s.active THEN INSERT (id,value) VALUES (s.id,s.value)",
            "MERGE INTO target AS t USING source AS s ON t.id = s.id "
            "WHEN MATCHED AND s.changed THEN UPDATE SET value = s.value "
            "WHEN NOT MATCHED AND s.active THEN INSERT (id, value) VALUES (s.id, s.value)",
            exp.Merge,
        ),
        (
            "MERGE INTO target t USING (SELECT id,value FROM source) s ON t.id=s.id "
            "WHEN MATCHED THEN UPDATE SET value=s.value WHERE s.value>0",
            "MERGE INTO target AS t USING (SELECT id, value FROM source) AS s "
            "ON t.id = s.id WHEN MATCHED THEN UPDATE SET value = s.value WHERE s.value > 0",
            exp.Merge,
        ),
        (
            "MERGE /*+LABEL('merge-load')*/ INTO target USING source "
            "ON target.id=source.id WHEN NOT MATCHED THEN "
            "INSERT (id) VALUES (source.id) WHERE source.active",
            "MERGE /*+ LABEL('merge-load') */ INTO target USING source "
            "ON target.id = source.id WHEN NOT MATCHED THEN "
            "INSERT (id) VALUES (source.id) WHERE source.active",
            vexp.VerticaMerge,
        ),
        (
            "UPDATE target AS t(old_id) SET value=s.value,updated_at=DEFAULT "
            "FROM source AS s WHERE t.old_id=s.id",
            "UPDATE target AS t(old_id) SET value = s.value, updated_at = DEFAULT "
            "FROM source AS s WHERE t.old_id = s.id",
            exp.Update,
        ),
        (
            "UPDATE target t SET value=s.value FROM DEFAULT LEFT OUTER JOIN source s "
            "ON t.id=s.id WHERE s.active",
            "UPDATE target AS t SET value = s.value FROM DEFAULT LEFT OUTER JOIN source AS s "
            "ON t.id = s.id WHERE s.active",
            exp.Update,
        ),
        (
            "DELETE /*+LABEL(delete_job)*/ FROM public.target "
            "WHERE id IN (SELECT id FROM source WHERE active)",
            "DELETE /*+ LABEL(delete_job) */ FROM public.target "
            "WHERE id IN (SELECT id FROM source WHERE active)",
            exp.Delete,
        ),
        ("DELETE FROM public.target", None, exp.Delete),
        ("TRUNCATE TABLE db.public.staging", None, exp.TruncateTable),
    ],
)
def test_documented_dml_round_trips(
    sql: str, expected: str | None, expression_type: type[exp.Expr]
) -> None:
    expression = assert_roundtrip(sql, expected)
    assert isinstance(expression, expression_type)


def test_merge_filters_and_hint_are_structured_without_losing_canonical_roots() -> None:
    canonical = assert_roundtrip(
        "MERGE INTO t USING s ON t.id=s.id "
        "WHEN MATCHED AND s.a>0 THEN UPDATE SET a=s.a "
        "WHEN NOT MATCHED THEN INSERT (id) VALUES (s.id) WHERE s.id>0",
        "MERGE INTO t USING s ON t.id = s.id "
        "WHEN MATCHED AND s.a > 0 THEN UPDATE SET a = s.a "
        "WHEN NOT MATCHED THEN INSERT (id) VALUES (s.id) WHERE s.id > 0",
    )
    assert type(canonical) is exp.Merge
    matched, not_matched = canonical.args["whens"].expressions
    assert isinstance(matched.args["condition"], exp.GT)
    assert matched.args["then"].args.get("where") is None
    assert not_matched.args.get("condition") is None
    assert isinstance(not_matched.args["then"].args["where"], exp.Where)

    hinted = assert_roundtrip(
        "MERGE /*+LABEL(job)*/ INTO t USING s ON t.id=s.id WHEN MATCHED THEN UPDATE SET a=s.a"
    )
    assert isinstance(hinted, vexp.VerticaMerge)
    assert isinstance(hinted.args["hint"], exp.Hint)


def test_update_default_relation_is_not_catalog_lineage_and_keeps_parents() -> None:
    expression = assert_roundtrip(
        "UPDATE t SET value=s.value FROM DEFAULT INNER JOIN source s ON t.id=s.id WHERE s.active",
        "UPDATE t SET value = s.value FROM DEFAULT INNER JOIN source AS s "
        "ON t.id = s.id WHERE s.active",
    )
    from_ = expression.args["from_"]
    relation = from_.this
    assert isinstance(relation, vexp.UpdateDefaultRelation)
    assert relation.parent is from_
    assert relation.args["joins"][0].parent is relation
    assert {table.name for table in expression.find_all(exp.Table)} == {"t", "source"}

    restored = exp.Expr.load(expression.dump())
    assert isinstance(restored.args["from_"].this, vexp.UpdateDefaultRelation)
    assert restored == expression


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        (
            "MERGE target USING source ON target.id=source.id WHEN MATCHED THEN UPDATE SET a=1",
            "requires INTO",
        ),
        (
            "MERGE INTO (SELECT 1) t USING source ON true WHEN MATCHED THEN UPDATE SET a=1",
            "table target",
        ),
        (
            "MERGE INTO target t(a) USING source ON true WHEN MATCHED THEN UPDATE SET a=1",
            "target aliases",
        ),
        ("MERGE INTO target source ON true WHEN MATCHED THEN UPDATE SET a=1", "requires USING"),
        ("MERGE INTO target USING source WHEN MATCHED THEN UPDATE SET a=1", "requires ON"),
        (
            "MERGE INTO target USING source ON WHEN MATCHED THEN UPDATE SET a=1",
            "ON requires a condition",
        ),
        ("MERGE INTO target USING source ON true", "matching clause"),
        (
            "MERGE INTO target USING (SELECT 1) ON true WHEN MATCHED THEN UPDATE SET a=1",
            "subquery sources require an alias",
        ),
        (
            "MERGE INTO target USING source s(a) ON true WHEN MATCHED THEN UPDATE SET a=1",
            "source aliases",
        ),
        (
            "MERGE INTO target USING source ON true WHEN MATCHED BY SOURCE THEN UPDATE SET a=1",
            "does not support MATCHED BY",
        ),
        (
            "MERGE INTO target USING source ON true WHEN MATCHED BY TARGET THEN UPDATE SET a=1",
            "does not support MATCHED BY",
        ),
        ("MERGE INTO target USING source ON true WHEN MATCHED UPDATE SET a=1", "require THEN"),
        ("MERGE INTO target USING source ON true WHEN MATCHED THEN DELETE", "requires UPDATE"),
        (
            "MERGE INTO target USING source ON true WHEN MATCHED THEN INSERT VALUES (1)",
            "requires UPDATE",
        ),
        ("MERGE INTO target USING source ON true WHEN MATCHED THEN UPDATE a=1", "requires SET"),
        (
            "MERGE INTO target USING source ON true WHEN MATCHED THEN UPDATE SET",
            "at least one assignment",
        ),
        (
            "MERGE INTO target USING source ON true WHEN MATCHED THEN UPDATE SET target.a=1",
            "unqualified columns",
        ),
        (
            "MERGE INTO target USING source ON true WHEN NOT MATCHED THEN UPDATE SET a=1",
            "requires INSERT",
        ),
        ("MERGE INTO target USING source ON true WHEN NOT MATCHED THEN DELETE", "requires INSERT"),
        (
            "MERGE INTO target USING source ON true WHEN NOT MATCHED THEN INSERT (a)",
            "requires VALUES",
        ),
        (
            "MERGE INTO target USING source ON true WHEN NOT MATCHED THEN INSERT VALUES 1",
            "requires parentheses",
        ),
        (
            "MERGE INTO target USING source ON true WHEN NOT MATCHED THEN INSERT () VALUES (1)",
            "column lists cannot be empty",
        ),
        (
            "MERGE INTO target USING source ON true WHEN NOT MATCHED "
            "THEN INSERT (target.a) VALUES (1)",
            "must be unqualified",
        ),
        (
            "MERGE INTO target USING source ON true WHEN NOT MATCHED THEN INSERT VALUES ()",
            "nonempty VALUES",
        ),
        (
            "MERGE INTO target USING source ON true "
            "WHEN MATCHED AND source.a>0 THEN UPDATE SET a=1 WHERE source.b>0",
            "both AND and trailing WHERE",
        ),
        (
            "MERGE INTO target USING source ON true "
            "WHEN MATCHED THEN UPDATE SET a=1 WHEN MATCHED THEN UPDATE SET b=2",
            "at most one WHEN MATCHED",
        ),
        (
            "MERGE INTO target USING source ON true "
            "WHEN NOT MATCHED THEN INSERT VALUES (1) "
            "WHEN NOT MATCHED THEN INSERT VALUES (2)",
            "at most one WHEN NOT MATCHED",
        ),
        (
            "MERGE INTO target USING source ON true WHEN MATCHED THEN UPDATE SET a=1 RETURNING a",
            "Unexpected token",
        ),
        (
            "WITH source AS (SELECT 1) MERGE INTO target USING source ON true "
            "WHEN MATCHED THEN UPDATE SET a=1",
            "leading WITH",
        ),
        (
            "MERGE /*+JTYPE(H)*/ INTO target USING source ON true WHEN MATCHED THEN UPDATE SET a=1",
            "only LABEL",
        ),
        (
            "MERGE /*+LABEL(a),LABEL(b)*/ INTO target USING source ON true "
            "WHEN MATCHED THEN UPDATE SET a=1",
            "exactly one LABEL",
        ),
    ],
)
def test_merge_rejects_non_vertica_grammar(sql: str, message: str) -> None:
    with pytest.raises(ParseError, match=message):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        ("INSERT target VALUES (1)", "requires INTO"),
        ("INSERT TABLE target VALUES (1)", "requires INTO"),
        ("INSERT INTO", "Expected table name"),
        ("INSERT INTO (SELECT 1) VALUES (1)", "table target"),
        ("INSERT INTO target AS t VALUES (1)", "do not support aliases"),
        ("INSERT INTO target() VALUES (1)", "column lists cannot be empty"),
        ("INSERT INTO target", "requires DEFAULT VALUES, VALUES, or a query"),
        ("INSERT INTO target VALUES ()", "rows cannot be empty"),
        ("INSERT INTO target(a) DEFAULT VALUES", "cannot include a target column list"),
        ("INSERT INTO target VALUES ((SELECT 1))", "does not support subqueries"),
        ("INSERT INTO target VALUES (1) AS rows", "does not support an alias"),
        ("WITH x AS (SELECT 1) INSERT INTO target SELECT * FROM x", "leading WITH"),
        ("INSERT INTO target VALUES (1) RETURNING id", "does not support RETURNING"),
        ("INSERT OVERWRITE TABLE target VALUES (1)", "requires INTO"),
        ("INSERT INTO target VALUES (1) ON CONFLICT DO NOTHING", "does not support ON CONFLICT"),
        ("INSERT /*+JTYPE(H)*/ INTO target VALUES (1)", "only LABEL"),
        ("INSERT /*+LABEL(a),LABEL(b)*/ INTO target VALUES (1)", "exactly one LABEL"),
    ],
)
def test_insert_rejects_non_vertica_grammar(sql: str, message: str) -> None:
    with pytest.raises(ParseError, match=message):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        ("UPDATE SET a=1", "table target"),
        ("UPDATE target WHERE id=1", "requires at least one assignment"),
        ("UPDATE target SET a", "column = expression"),
        ("UPDATE target SET target.a=1", "unqualified columns"),
        ("UPDATE target SET a=(SELECT 1)", "do not support subqueries"),
        ("WITH x AS (SELECT 1) UPDATE target SET a=1", "leading WITH"),
        ("UPDATE target SET a=1 RETURNING a", "does not support RETURNING"),
        ("UPDATE target SET a=1 ORDER BY a", "does not support ORDER BY"),
        ("UPDATE target SET a=1 LIMIT 1", "does not support LIMIT"),
        ("UPDATE target SET a=1 FROM DEFAULT", "requires a JOIN"),
        ("UPDATE target SET a=1 FROM DEFAULT, source", "explicit JOIN syntax"),
        ("UPDATE target SET a=1 FROM source JOIN DEFAULT ON true", "must be the first"),
        (
            "UPDATE target SET a=1 FROM DEFAULT JOIN source ON true JOIN DEFAULT ON true",
            "only once",
        ),
    ],
)
def test_update_rejects_non_vertica_grammar(sql: str, message: str) -> None:
    with pytest.raises(ParseError, match=message):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        ("DELETE target WHERE id=1", "requires FROM"),
        ("DELETE FROM", "Expected table name"),
        ("DELETE FROM target t WHERE t.id=1", "aliases or joins"),
        ("DELETE FROM target JOIN source ON target.id=source.id", "aliases or joins"),
        ("DELETE FROM target USING source WHERE target.id=source.id", "does not support USING"),
        ("WITH x AS (SELECT 1) DELETE FROM target", "leading WITH"),
        ("DELETE FROM target RETURNING id", "does not support RETURNING"),
        ("DELETE FROM target ORDER BY id", "does not support ORDER BY"),
        ("DELETE FROM target LIMIT 1", "does not support LIMIT"),
        ("DELETE t1 FROM t1 JOIN t2 ON t1.id=t2.id", "requires FROM"),
        ("DELETE /*+JTYPE(H)*/ FROM target", "only LABEL"),
    ],
)
def test_delete_rejects_non_vertica_grammar(sql: str, message: str) -> None:
    with pytest.raises(ParseError, match=message):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        ("TRUNCATE target", "requires TABLE"),
        ("TRUNCATE DATABASE db", "requires TABLE"),
        ("TRUNCATE TABLE", "Expected table name"),
        ("TRUNCATE TABLE IF EXISTS target", "Unexpected Vertica TRUNCATE clause"),
        ("TRUNCATE TABLE target, source", "Unexpected Vertica TRUNCATE clause"),
        ("TRUNCATE TABLE target RESTART IDENTITY", "Unexpected Vertica TRUNCATE clause"),
        ("TRUNCATE TABLE target CONTINUE IDENTITY", "Unexpected Vertica TRUNCATE clause"),
        ("TRUNCATE TABLE target CASCADE", "Unexpected Vertica TRUNCATE clause"),
        ("TRUNCATE TABLE target RESTRICT", "Unexpected Vertica TRUNCATE clause"),
        ("TRUNCATE TABLE target PARTITION (1)", "Unexpected Vertica TRUNCATE clause"),
        ("TRUNCATE TABLE target ON CLUSTER c", "Unexpected Vertica TRUNCATE clause"),
        ("TRUNCATE TABLE target AS t", "Unexpected Vertica TRUNCATE clause"),
    ],
)
def test_truncate_rejects_non_vertica_grammar(sql: str, message: str) -> None:
    with pytest.raises(ParseError, match=message):
        parse_one(sql, read="vertica")


def test_programmatic_and_foreign_dml_generation_contracts() -> None:
    canonical_sql = [
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET a=1 WHERE id=2",
        "DELETE FROM t WHERE id=2",
        "MERGE INTO t USING s ON t.id=s.id WHEN MATCHED THEN UPDATE SET a=s.a",
        "TRUNCATE TABLE t",
    ]
    for sql in canonical_sql:
        expression = parse_one(sql, read="vertica")
        assert expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)

    update_default = parse_one(
        "UPDATE t SET a=s.a FROM DEFAULT JOIN s ON t.id=s.id", read="vertica"
    )
    with pytest.raises(ValueError, match="UpdateDefaultRelation"):
        update_default.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)

    merge_where = parse_one(
        "MERGE INTO t USING s ON t.id=s.id WHEN MATCHED THEN UPDATE SET a=s.a WHERE s.a>0",
        read="vertica",
    )
    with pytest.raises(UnsupportedError, match="WHERE clause in MERGE UPDATE"):
        merge_where.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    ("expression", "message"),
    [
        (exp.Insert(this=exp.to_table("t")), "requires DEFAULT VALUES"),
        (
            exp.Insert(this=exp.to_table("t"), expression=exp.Values(expressions=[])),
            "VALUES requires at least one row",
        ),
        (exp.Update(this=exp.to_table("t")), "requires at least one assignment"),
        (exp.Delete(this=exp.to_table("t"), using=[exp.to_table("s")]), "does not support USING"),
        (exp.Merge(this=exp.to_table("t")), "requires a table or subquery source"),
        (exp.TruncateTable(expressions=[]), "requires exactly one table"),
        (
            exp.TruncateTable(expressions=[exp.to_table("t")], option="CASCADE"),
            "does not support CASCADE or RESTRICT",
        ),
    ],
)
def test_strict_vertica_generation_rejects_malformed_canonical_trees(
    expression: exp.Expr, message: str
) -> None:
    with pytest.raises(UnsupportedError, match=message):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_strict_generation_rejects_malformed_update_default_leaf() -> None:
    expression = exp.Update(
        this=exp.to_table("t"),
        expressions=[exp.EQ(this=exp.column("a"), expression=exp.Literal.number(1))],
        from_=exp.From(this=vexp.UpdateDefaultRelation(joins=[])),
    )
    with pytest.raises(UnsupportedError, match="requires a JOIN"):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_strict_generation_validates_programmatic_dml_shape_variants() -> None:
    valid_update = exp.Update(
        this=exp.to_table("t"),
        expressions=[exp.EQ(this=exp.column("a"), expression=exp.Literal.number(1))],
    )
    valid_insert_action = exp.Insert(
        this=exp.Tuple(expressions=[exp.column("a")]),
        expression=exp.Tuple(expressions=[exp.Literal.number(1)]),
    )
    invalid_insert_action = valid_insert_action.copy()
    invalid_insert_action.set("conflict", exp.OnConflict())

    invalid: list[tuple[exp.Expr, str]] = [
        (
            exp.Insert(
                this=exp.to_table("t"),
                default=True,
                expression=exp.select("a"),
            ),
            "exactly one source form",
        ),
        (
            exp.Insert(
                this=exp.to_table("t"),
                expression=exp.Values(expressions=[exp.Literal.number(1)]),
            ),
            "rows cannot be empty",
        ),
        (
            exp.Insert(
                this=exp.to_table("t"),
                expression=exp.Literal.number(1),
            ),
            "source must be VALUES or a query",
        ),
        (
            exp.Insert(
                this=exp.to_table("t"),
                expression=exp.Values(expressions=[exp.Tuple(expressions=[exp.Literal.number(1)])]),
                hint=exp.var("LABEL"),
            ),
            "exactly one LABEL hint",
        ),
        (
            exp.Merge(
                this=exp.Literal.string("not_a_table"),
                using=exp.to_table("s"),
                on=exp.true(),
                whens=exp.Whens(expressions=[exp.When(matched=True, then=valid_update.copy())]),
            ),
            "requires a table target",
        ),
        (
            exp.Merge(
                this=exp.to_table("t"),
                using=exp.to_table("s"),
                on=exp.true(),
                using_cond=[exp.column("id")],
                returning=exp.Returning(expressions=[exp.column("id")]),
                with_=exp.With(expressions=[]),
                whens=exp.Whens(expressions=[exp.Literal.number(1)]),
            ),
            "second USING condition",
        ),
        (
            exp.Merge(
                this=exp.to_table("t"),
                using=exp.to_table("s"),
                on=exp.true(),
                whens=exp.Whens(
                    expressions=[
                        exp.When(
                            matched=None,
                            source=True,
                            then=invalid_insert_action,
                        )
                    ]
                ),
            ),
            "MATCHED BY SOURCE or TARGET",
        ),
        (
            exp.Merge(
                this=exp.to_table("t"),
                using=exp.to_table("s"),
                on=exp.true(),
                whens=exp.Whens(
                    expressions=[exp.When(matched=True, then=valid_insert_action.copy())]
                ),
            ),
            "WHEN MATCHED requires UPDATE",
        ),
        (
            exp.Merge(
                this=exp.to_table("t"),
                using=exp.to_table("s"),
                on=exp.true(),
                whens=exp.Whens(expressions=[exp.When(matched=False, then=valid_update.copy())]),
            ),
            "WHEN NOT MATCHED requires INSERT",
        ),
        (
            exp.Update(
                this=exp.Literal.string("not_a_table"),
                expressions=valid_update.expressions,
            ),
            "requires a table target",
        ),
        (
            exp.Delete(this=exp.Literal.string("not_a_table")),
            "requires a table target",
        ),
        (
            exp.TruncateTable(expressions=[exp.Literal.string("not_a_table")]),
            "requires a table target",
        ),
        (
            exp.TruncateTable(expressions=[exp.to_table("t").as_("alias")]),
            "does not support target aliases",
        ),
    ]

    for expression, message in invalid:
        with pytest.raises(UnsupportedError, match=message):
            expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_truncate_function_call_is_not_misclassified_as_ddl() -> None:
    expression = parse_one("TRUNCATE(1.25, 1)", read="vertica")
    assert isinstance(expression, exp.Trunc)
    assert expression.sql(dialect="vertica") == "TRUNC(1.25, 1)"
