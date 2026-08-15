"""Directed-query statements, constant annotations, and table reorganization."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError, TokenError, UnsupportedError
from sqlglot.optimizer import optimize
from sqlglot.optimizer.annotate_types import annotate_types

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


def _assert_parent_links(expression: exp.Expr) -> None:
    for parent in expression.walk():
        for child in parent.iter_expressions():
            assert child.parent is parent


@pytest.mark.parametrize(
    ("sql", "expected", "expression_type"),
    [
        (
            "SAVE QUERY SELECT a FROM t WHERE city = 'Boston' /*+:v(1)*/",
            "SAVE QUERY SELECT a FROM t WHERE city = 'Boston' /*+:v(1)*/",
            vexp.SaveQuery,
        ),
        (
            "SAVE QUERY WITH x AS (SELECT a FROM t) SELECT a FROM x",
            "SAVE QUERY WITH x AS (SELECT a FROM t) SELECT a FROM x",
            vexp.SaveQuery,
        ),
        (
            "GET DIRECTED QUERY SELECT 1 UNION SELECT 2",
            "GET DIRECTED QUERY SELECT 1 UNION SELECT 2",
            vexp.GetDirectedQuery,
        ),
        (
            "CREATE DIRECTED QUERY OPT dq_opt SELECT a FROM t WHERE b = 1",
            "CREATE DIRECTED QUERY OPT dq_opt SELECT a FROM t WHERE b = 1",
            vexp.CreateDirectedQuery,
        ),
        (
            "CREATE DIRECTED QUERY OPTIMIZER 'dq optimizer' COMMENT 'baseline' SELECT a FROM t",
            "CREATE DIRECTED QUERY OPTIMIZER 'dq optimizer' COMMENT 'baseline' SELECT a FROM t",
            vexp.CreateDirectedQuery,
        ),
        (
            "CREATE DIRECTED QUERY CUSTOM dq_custom SELECT /*+verbatim*/ a FROM t",
            "CREATE DIRECTED QUERY CUSTOM dq_custom SELECT /*+ VERBATIM */ a FROM t",
            vexp.CreateDirectedQuery,
        ),
        (
            "CREATE DIRECTED QUERY CUSTOM 'dq export' COMMENT 'saved plan' "
            "OPTVER 'Vertica Analytic Database v26.2' "
            "PSDATE '2026-08-15 01:02:03' SELECT 1",
            "CREATE DIRECTED QUERY CUSTOM 'dq export' COMMENT 'saved plan' "
            "OPTVER 'Vertica Analytic Database v26.2' "
            "PSDATE '2026-08-15 01:02:03' SELECT 1",
            vexp.CreateDirectedQuery,
        ),
        (
            'CREATE DIRECTED QUERY OPT "dq name" SELECT 1',
            'CREATE DIRECTED QUERY OPT "dq name" SELECT 1',
            vexp.CreateDirectedQuery,
        ),
    ],
)
def test_directed_query_definition_roundtrips_with_query_children(
    sql: str, expected: str, expression_type: type[exp.Expr]
) -> None:
    expression = assert_roundtrip(sql, expected)
    assert isinstance(expression, expression_type)

    query = (
        expression.args.get("expression")
        if isinstance(expression, vexp.CreateDirectedQuery)
        else expression.args.get("this")
    )
    assert isinstance(query, exp.Query)
    assert query.parent is expression
    assert list(expression.find_all(exp.Select))
    _assert_parent_links(expression)


def test_create_directed_query_export_metadata_is_typed_and_ordered() -> None:
    expression = assert_roundtrip(
        "CREATE DIRECTED QUERY CUSTOM dq COMMENT 'catalog plan' "
        "OPTVER 'v26.2' PSDATE '2026-08-15 12:00:00' SELECT a FROM t"
    )
    assert isinstance(expression, vexp.CreateDirectedQuery)
    assert isinstance(expression.this, exp.Identifier)
    assert isinstance(expression.args["mode"], exp.Var)
    assert expression.args["mode"].name == "CUSTOM"

    for key in ("comment", "optimizer_version", "plan_date"):
        value = expression.args[key]
        assert isinstance(value, exp.Literal) and value.is_string
        assert value.parent is expression


@pytest.mark.parametrize(
    ("sql", "action", "target_key", "target_type"),
    [
        ("ACTIVATE DIRECTED QUERY dq_opt", "ACTIVATE", "this", exp.Identifier),
        (
            "ACTIVATE DIRECTED QUERY WHERE save_plans_version = 21",
            "ACTIVATE",
            "where",
            exp.Where,
        ),
        ("DEACTIVATE DIRECTED QUERY 'dq opt'", "DEACTIVATE", "this", exp.Literal),
        (
            "DEACTIVATE DIRECTED QUERY SELECT a FROM t WHERE city = 'Boston'",
            "DEACTIVATE",
            "expression",
            exp.Select,
        ),
        (
            "DEACTIVATE DIRECTED QUERY WHERE save_plans_version = 21",
            "DEACTIVATE",
            "where",
            exp.Where,
        ),
        ("DROP DIRECTED QUERY dq_opt", "DROP", "this", exp.Identifier),
        (
            "DROP DIRECTED QUERY WHERE save_plans_version = 21",
            "DROP",
            "where",
            exp.Where,
        ),
    ],
)
def test_directed_query_actions_have_exactly_one_traversable_target(
    sql: str,
    action: str,
    target_key: str,
    target_type: type[exp.Expr],
) -> None:
    expression = assert_roundtrip(sql, sql)
    assert isinstance(expression, vexp.DirectedQueryAction)
    assert isinstance(expression.args["action"], exp.Var)
    assert expression.args["action"].name == action
    assert isinstance(expression.args[target_key], target_type)
    assert expression.args[target_key].parent is expression
    assert sum(expression.args.get(key) is not None for key in ("this", "expression", "where")) == 1
    _assert_parent_links(expression)


@pytest.mark.parametrize(
    ("sql", "expected", "directive", "index"),
    [
        ("SELECT 8 /*+:v(1)*/", "SELECT 8 /*+:v(1)*/", ":v", 1),
        (
            "SELECT 8 /*+IGNORECONST(2)*/",
            "SELECT 8 /*+IGNORECONST(2)*/",
            "IGNORECONST",
            2,
        ),
        (
            "SELECT 8 /*+IgnoreConst(3)*/",
            "SELECT 8 /*+IGNORECONST(3)*/",
            "IGNORECONST",
            3,
        ),
        (
            "SELECT 8 /*+IGNORECONSTANT(4)*/",
            "SELECT 8 /*+IGNORECONST(4)*/",
            "IGNORECONST",
            4,
        ),
        ("SELECT -1 /*+:c*/", "SELECT -1 /*+:c*/", ":c", None),
        (
            "SELECT 'Boston'::VARCHAR(6) /*+:v(5)*/",
            "SELECT CAST('Boston' AS VARCHAR(6)) /*+:v(5)*/",
            ":v",
            5,
        ),
        ("SELECT 8 /* + :v(6) */", "SELECT 8 /*+:v(6)*/", ":v", 6),
    ],
)
def test_directed_constant_annotations_are_structural_and_exact(
    sql: str, expected: str, directive: str, index: int | None
) -> None:
    expression = assert_roundtrip(sql, expected)
    hint = expression.find(vexp.DirectedConstantHint)
    assert hint is not None
    assert isinstance(hint.this, exp.Expr)
    assert hint.this.parent is hint
    assert isinstance(hint.args["directive"], exp.Var)
    assert hint.args["directive"].name == directive
    assert hint.args["directive"].parent is hint

    index_expression = hint.args.get("index")
    if index is None:
        assert index_expression is None
    else:
        assert isinstance(index_expression, exp.Literal)
        assert index_expression.to_py() == index
        assert index_expression.parent is hint
    _assert_parent_links(expression)


def test_repeated_pairing_ids_and_ordinary_comments_are_preserved() -> None:
    expression = assert_roundtrip(
        "SELECT * FROM s JOIN t ON s.a = t.b "
        "WHERE s.a = 8 /* ordinary */ /*+:v(1)*/ AND t.b = 8 /*+:v(1)*/"
    )
    hints = list(expression.find_all(vexp.DirectedConstantHint))
    assert len(hints) == 2
    assert [hint.args["index"].to_py() for hint in hints] == [1, 1]
    assert hints[0].this.comments == [" ordinary "]
    assert "/* ordinary */ /*+:v(1)*/" in expression.sql(dialect="vertica")


def test_directed_constant_annotations_remain_optimizer_visible_and_typed() -> None:
    expression = parse_one(
        "SELECT a FROM t WHERE x = 8 /*+:v(1)*/",
        read="vertica",
    )
    schema = {"t": {"a": "INT", "x": "INT"}}
    annotated = annotate_types(expression.copy(), dialect="vertica", schema=schema)
    annotated_hint = annotated.find(vexp.DirectedConstantHint)
    assert annotated_hint is not None
    assert annotated_hint.is_type(exp.DType.INT)
    assert annotated_hint.this.is_type(exp.DType.INT)

    optimized = optimize(expression, dialect="vertica", schema=schema)
    optimized_hint = optimized.find(vexp.DirectedConstantHint)
    assert optimized_hint is not None
    assert optimized_hint.is_type(exp.DType.INT)
    assert optimized_hint.parent is not None
    assert optimized.sql(dialect="vertica").endswith('"t"."x" = 8 /*+:v(1)*/')
    assert {column.table for column in optimized.find_all(exp.Column)} == {"t"}
    assert exp.Expr.load(optimized.dump()) == optimized


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1 /* :c */",
        "SELECT 1 /*:c*/",
        "SELECT 1 -- :c",
        "SELECT 1 /*__SQLGLOT_VERTICA_DIRECTED_CONSTANT__:c*/",
        "SELECT 1 /*++:c*/",
        "SELECT 1 /*++:v(1)*/",
        "SELECT 1 /*++IGNORECONST(1)*/",
    ],
)
def test_only_actual_plus_hint_comments_become_directed_annotations(sql: str) -> None:
    expression = parse_one(sql, read="vertica")
    assert expression.find(vexp.DirectedConstantHint) is None
    assert exp.Expr.load(expression.dump()) == expression


@pytest.mark.parametrize(
    "sql",
    [
        "/*+:c*/ SELECT 1",
        "SELECT 1 FROM /*+:c*/ t",
        "SELECT 1 WHERE /*+:c*/ 1 = 1",
        "SELECT 1 + /*+:c*/ 2",
        "SELECT 1 = /*+:v(1)*/ 2",
        "SELECT CASE /*+:c*/ WHEN TRUE THEN 1 END",
        "SELECT CASE WHEN /*+:c*/ TRUE THEN 1 END",
        "SELECT 1 AS /*+:c*/ x",
        "SELECT f(/*+:c*/ 1)",
        "SELECT * FROM t /*+:c*/",
        "SAVE QUERY /*+:c*/ SELECT 1",
        "GET DIRECTED QUERY /*+:v(1)*/ SELECT 1",
        "CREATE DIRECTED QUERY OPT dq /*+:c*/ SELECT 1",
        "CREATE DIRECTED QUERY CUSTOM dq COMMENT 'x' /*+:c*/ SELECT 1",
        "CREATE DIRECTED QUERY CUSTOM dq OPTVER 'v26.2' /*+:c*/ SELECT 1",
        "CREATE DIRECTED QUERY CUSTOM dq PSDATE 'today' /*+:c*/ SELECT 1",
        "ACTIVATE DIRECTED QUERY /*+:c*/ dq",
        "ACTIVATE DIRECTED QUERY dq /*+:c*/",
        "DEACTIVATE DIRECTED QUERY 'dq' /*+:v(1)*/",
        "DROP DIRECTED QUERY /*+:c*/ dq",
        "DROP DIRECTED QUERY dq /*+:c*/",
    ],
)
def test_directed_annotations_outside_postfix_query_values_are_rejected(sql: str) -> None:
    with pytest.raises(ParseError, match=r"directed-query|Directed-query"):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    ("sql", "expected", "child_type"),
    [
        (
            "SELECT 1 /*+:v(1)*/ AS x",
            "SELECT 1 /*+:v(1)*/ AS x",
            exp.Literal,
        ),
        (
            "SELECT F(1) /*+:v(1)*/ x",
            "SELECT F(1) /*+:v(1)*/ AS x",
            exp.Anonymous,
        ),
        (
            "SELECT CAST(1 AS INT) /*+:c*/ AS x",
            "SELECT CAST(1 AS BIGINT) /*+:c*/ AS x",
            exp.Cast,
        ),
        (
            "SELECT (1) /*+:c*/ x",
            "SELECT (1) /*+:c*/ AS x",
            exp.Paren,
        ),
    ],
)
def test_annotation_before_alias_stays_on_aliased_value(
    sql: str, expected: str, child_type: type[exp.Expr]
) -> None:
    expression = assert_roundtrip(sql, expected)
    alias = expression.find(exp.Alias)
    assert alias is not None
    assert isinstance(alias.this, vexp.DirectedConstantHint)
    assert isinstance(alias.this.this, child_type)


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("SELECT 1\n/*+:c*/", "SELECT 1 /*+:c*/"),
        ("SELECT 1 \n  /* + :v(1) */", "SELECT 1 /*+:v(1)*/"),
        ("SELECT (1)\n/*+:c*/", "SELECT (1) /*+:c*/"),
        (
            "SAVE QUERY SELECT x FROM t WHERE x = 1\n/*+:v(1)*/",
            "SAVE QUERY SELECT x FROM t WHERE x = 1 /*+:v(1)*/",
        ),
    ],
)
def test_postfix_annotation_can_follow_value_on_a_new_line(sql: str, expected: str) -> None:
    assert_roundtrip(sql, expected)


@pytest.mark.parametrize(
    ("sql", "child_type"),
    [
        ("SELECT DATE '2020-01-01' /*+:c*/", exp.Cast),
        ("SELECT TIMESTAMP '2020-01-01 01:02:03' /*+:c*/", exp.Cast),
        ("SELECT TIME '01:02:03' /*+:c*/", exp.Cast),
        ("SELECT INTERVAL '1' DAY /*+:c*/", exp.Interval),
        ("SELECT INTERVAL(3) '1' DAY /*+:c*/", vexp.VerticaInterval),
        ("SELECT INTERVAL '1-2' YEAR TO MONTH /*+:c*/", exp.Interval),
        ("SELECT ARRAY[1] /*+:c*/", exp.Array),
        ("SELECT SET[1] /*+:c*/", vexp.SetLiteral),
        ("SELECT 1! /*+:c*/", exp.Factorial),
    ],
)
def test_annotation_wraps_the_complete_typed_or_constructed_value(
    sql: str, child_type: type[exp.Expr]
) -> None:
    expression = parse_one(sql, read="vertica")
    hint = expression.find(vexp.DirectedConstantHint)
    assert hint is not None
    assert isinstance(hint.this, child_type)
    annotated = annotate_types(expression, dialect="vertica")
    annotated_hint = annotated.find(vexp.DirectedConstantHint)
    assert annotated_hint is not None
    assert annotated_hint.type == annotated_hint.this.type
    assert assert_roundtrip(sql).find(vexp.DirectedConstantHint) is not None


@pytest.mark.parametrize(
    ("sql", "child_type"),
    [
        ("SELECT x /*+:c*/ FROM t", exp.Column),
        ("SELECT ABS(x) /*+:v(1)*/ FROM t", exp.Abs),
    ],
)
def test_nonliteral_query_value_annotations_remain_scope_and_optimizer_visible(
    sql: str, child_type: type[exp.Expr]
) -> None:
    expression = parse_one(sql, read="vertica")
    hint = expression.find(vexp.DirectedConstantHint)
    assert hint is not None and isinstance(hint.this, child_type)
    schema = {"t": {"x": "INT"}}
    optimized = optimize(expression, dialect="vertica", schema=schema)
    optimized_hint = optimized.find(vexp.DirectedConstantHint)
    assert optimized_hint is not None
    assert optimized_hint.find(exp.Column) is not None
    assert optimized_hint.find_ancestor(exp.Select) is not None
    assert optimized.sql(dialect="vertica").count("/*+") == 1


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE DIRECTED QUERY dq SELECT 1",
        "CREATE DIRECTED QUERY OPTI dq SELECT 1",
        "CREATE DIRECTED QUERY OPT",
        "CREATE DIRECTED QUERY CUSTOM dq",
        "CREATE DIRECTED QUERY CUSTOM dq COMMENT 42 SELECT 1",
        "CREATE DIRECTED QUERY OPT dq OPTVER 'v26.2' SELECT 1",
        "CREATE DIRECTED QUERY OPT dq PSDATE '2026-08-15' SELECT 1",
        "CREATE DIRECTED QUERY CUSTOM dq PSDATE 'date' OPTVER 'version' SELECT 1",
        "CREATE OR REPLACE DIRECTED QUERY OPT dq SELECT 1",
        "CREATE IF NOT EXISTS DIRECTED QUERY OPT dq SELECT 1",
        "CREATE TEMPORARY DIRECTED QUERY OPT dq SELECT 1",
        "CREATE GLOBAL TEMPORARY DIRECTED QUERY OPT dq SELECT 1",
        "CREATE LOCAL TEMPORARY DIRECTED QUERY OPT dq SELECT 1",
        "CREATE MATERIALIZED DIRECTED QUERY OPT dq SELECT 1",
        f"CREATE DIRECTED QUERY CUSTOM dq COMMENT '{'x' * 129}' SELECT 1",
        "SAVE QUERY",
        "SAVE QUERY dq",
        "SAVE QUERY SELECT",
        "SAVE QUERY SELECT FROM t",
        "GET DIRECTED QUERY",
        "GET DIRECTED QUERY dq",
        "GET DIRECTED QUERY SELECT FROM t",
        "CREATE DIRECTED QUERY OPT dq SELECT",
        "CREATE DIRECTED QUERY CUSTOM dq SELECT FROM t",
        "ACTIVATE DIRECTED QUERY",
        "ACTIVATE DIRECTED QUERY SELECT 1",
        "ACTIVATE DIRECTED QUERY dq WHERE save_plans_version = 1",
        "DEACTIVATE DIRECTED QUERY",
        "DEACTIVATE DIRECTED QUERY WHERE",
        "DEACTIVATE DIRECTED QUERY SELECT",
        "DROP DIRECTED QUERY",
        "DROP DIRECTED QUERY SELECT 1",
        "DROP DIRECTED QUERY dq1, dq2",
        "DROP DIRECTED QUERY IF EXISTS dq",
        "DROP IF EXISTS DIRECTED QUERY dq",
        "DROP TEMPORARY DIRECTED QUERY dq",
        "DROP DIRECTED QUERY dq CASCADE",
    ],
)
def test_malformed_directed_query_statements_are_rejected(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 8 /*+:v*/",
        "SELECT 8 /*+:v()*/",
        "SELECT 8 /*+:v(foo)*/",
        "SELECT 8 /*+:v(1, 2)*/",
        "SELECT 8 /*+:c(1)*/",
        "SELECT 8 /*+:v(1)*/ /*+:c*/",
        "SELECT /*+:v(1)*/ 8",
        "SELECT /*+IGNORECONST(foo)*/ 8",
    ],
)
def test_malformed_directed_constant_annotations_are_rejected(sql: str) -> None:
    with pytest.raises(ParseError, match=r"directed-query|only one"):
        parse_one(sql, read="vertica")


def test_unterminated_directed_constant_annotation_is_a_token_error() -> None:
    with pytest.raises(TokenError):
        parse_one("SELECT 8 /*+:v(1)", read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "SAVE QUERY SELECT 1 UNION (SELECT 2)",
        "GET DIRECTED QUERY SELECT 1 UNION ALL (SELECT 2 ORDER BY 1)",
        "CREATE DIRECTED QUERY OPT dq SELECT 1 INTERSECT (SELECT 1)",
        "DEACTIVATE DIRECTED QUERY SELECT 1 EXCEPT (SELECT 2)",
    ],
)
def test_parenthesized_set_operation_branches_are_valid_directed_queries(sql: str) -> None:
    expression = assert_roundtrip(sql)
    assert isinstance(expression.find(exp.SetOperation), exp.SetOperation)


@pytest.mark.parametrize(
    ("sql", "expected", "expression_type", "reorganize"),
    [
        (
            "ALTER TABLE store_orders REORGANIZE",
            "ALTER TABLE store_orders REORGANIZE",
            vexp.ReorganizeTable,
            True,
        ),
        (
            "ALTER TABLE public.store_orders PARTITION BY order_date::DATE",
            "ALTER TABLE public.store_orders PARTITION BY CAST(order_date AS DATE)",
            vexp.AlterTablePartition,
            False,
        ),
        (
            "ALTER TABLE public.store_orders PARTITION BY order_date::DATE REORGANIZE",
            "ALTER TABLE public.store_orders PARTITION BY CAST(order_date AS DATE) REORGANIZE",
            vexp.AlterTablePartition,
            True,
        ),
        (
            "ALTER TABLE store_orders PARTITION BY order_date::DATE "
            "GROUP BY DATE_TRUNC('year', order_date::DATE) REORGANIZE",
            "ALTER TABLE store_orders PARTITION BY CAST(order_date AS DATE) "
            "GROUP BY DATE_TRUNC('YEAR', CAST(order_date AS DATE)) REORGANIZE",
            vexp.AlterTablePartition,
            True,
        ),
        (
            "ALTER TABLE store_orders PARTITION BY YEAR(order_date) SET ACTIVEPARTITIONCOUNT 5",
            "ALTER TABLE store_orders PARTITION BY YEAR(order_date) SET ACTIVEPARTITIONCOUNT 5",
            vexp.AlterTablePartition,
            False,
        ),
        (
            "ALTER TABLE store_orders PARTITION BY YEAR(order_date) "
            "SET ACTIVEPARTITIONCOUNT 5 REORGANIZE",
            "ALTER TABLE store_orders PARTITION BY YEAR(order_date) "
            "SET ACTIVEPARTITIONCOUNT 5 REORGANIZE",
            vexp.AlterTablePartition,
            True,
        ),
    ],
)
def test_alter_table_partition_and_reorganization_roundtrip(
    sql: str,
    expected: str,
    expression_type: type[exp.Alter],
    reorganize: bool,
) -> None:
    expression = assert_roundtrip(sql, expected)
    assert isinstance(expression, expression_type)
    assert isinstance(expression.this, exp.Table)
    assert expression.this.parent is expression

    if isinstance(expression, vexp.AlterTablePartition):
        partition = expression.args["partition"]
        assert isinstance(partition, vexp.TablePartitionProperty)
        assert partition.parent is expression
        assert expression.args.get("reorganize") is reorganize
        assert expression.actions == []
    else:
        assert len(expression.actions) == 1
        assert isinstance(expression.actions[0], exp.Var)
        assert expression.actions[0].name == "REORGANIZE"
    _assert_parent_links(expression)


@pytest.mark.parametrize(
    "sql",
    [
        "ALTER TABLE REORGANIZE",
        "ALTER TABLE store_orders REORGANIZE()",
        "ALTER TABLE store_orders REORGANIZE BY order_date",
        "ALTER TABLE store_orders PARTITION BY",
        "ALTER TABLE store_orders PARTITION BY order_date GROUP BY",
        "ALTER TABLE store_orders PARTITION BY order_date SET ACTIVEPARTITIONCOUNT",
        "ALTER TABLE store_orders PARTITION BY order_date ACTIVEPARTITIONCOUNT 5",
        "ALTER TABLE store_orders PARTITION BY order_date REORGANIZE GROUP BY YEAR(order_date)",
        "ALTER TABLE store_orders REORGANIZE PARTITION BY order_date",
    ],
)
def test_malformed_table_reorganization_is_rejected(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


def test_nested_commas_and_reorganize_identifiers_do_not_trigger_mixed_action_guard() -> None:
    assert_roundtrip(
        "ALTER TABLE t PARTITION BY reorganize(x, y)",
        "ALTER TABLE t PARTITION BY REORGANIZE(x, y)",
    )
    assert_roundtrip(
        "ALTER TABLE t PARTITION BY x GROUP BY DATE_TRUNC('year', x) REORGANIZE",
        "ALTER TABLE t PARTITION BY x GROUP BY DATE_TRUNC('YEAR', x) REORGANIZE",
    )
    parse_one("ALTER TABLE t ADD COLUMN reorganize INT, ADD COLUMN y INT", read="vertica")
    parse_one("ALTER TABLE reorganize ADD COLUMN x INT, ADD COLUMN y INT", read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "ALTER TABLE t ADD COLUMN x INT, REORGANIZE",
        "ALTER TABLE t PARTITION BY YEAR(ts), REORGANIZE",
        "ALTER TABLE t REORGANIZE, ADD COLUMN x INT",
    ],
)
def test_mixed_reorganize_action_lists_fail_closed_until_semantically_modeled(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "SAVE QUERY SELECT 1",
        "GET DIRECTED QUERY SELECT 1",
        "CREATE DIRECTED QUERY OPT dq SELECT 1",
        "ACTIVATE DIRECTED QUERY dq",
        "SELECT 8 /*+:v(1)*/",
        "ALTER TABLE t PARTITION BY YEAR(ts)",
        "ALTER TABLE t REORGANIZE",
    ],
)
def test_directed_and_reorganization_nodes_fail_atomically_in_postgres(sql: str) -> None:
    expression = parse_one(sql, read="vertica")
    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    ("expression", "message"),
    [
        (vexp.SaveQuery(this=exp.table_("t")), "SELECT query child"),
        (vexp.SaveQuery(this=exp.Select()), "nonempty SELECT"),
        (vexp.GetDirectedQuery(this=exp.Select()), "nonempty SELECT"),
        (
            vexp.GetDirectedQuery(this=exp.Subquery(this=exp.select("1"))),
            "nonempty SELECT",
        ),
        (
            vexp.CreateDirectedQuery(
                this=exp.to_identifier("dq"),
                mode=exp.var("AUTO"),
                expression=exp.select("1"),
            ),
            "mode must be",
        ),
        (
            vexp.CreateDirectedQuery(
                this=exp.to_identifier("dq"),
                mode=exp.var("OPT"),
                expression=exp.Select(),
            ),
            "nonempty SELECT",
        ),
        (
            vexp.CreateDirectedQuery(
                this=exp.to_identifier("dq"),
                mode=exp.var("OPT"),
                expression=exp.select("1"),
                optimizer_version=exp.Literal.string("v26.2"),
            ),
            "only for CUSTOM",
        ),
        (
            vexp.DirectedQueryAction(action=exp.var("ACTIVATE")),
            "exactly one target",
        ),
        (
            vexp.DirectedQueryAction(
                action=exp.var("DEACTIVATE"),
                expression=exp.Select(),
            ),
            "nonempty SELECT",
        ),
        (
            vexp.DirectedQueryAction(
                action=exp.var("DROP"),
                expression=exp.select("1"),
            ),
            "does not accept an input query",
        ),
        (
            vexp.DirectedConstantHint(
                this=exp.Literal.number(1),
                directive=exp.var(":v"),
            ),
            "require an integer index",
        ),
        (
            vexp.DirectedConstantHint(
                this=exp.Literal.number(1),
                directive=exp.var(":c"),
                index=exp.Literal.number(1),
            ),
            "does not accept an index",
        ),
        (
            vexp.AlterTablePartition(
                this=exp.table_("t"),
                kind="TABLE",
            ),
            "requires a partition expression",
        ),
        (
            vexp.ReorganizeTable(
                this=exp.table_("t"),
                kind="TABLE",
                actions=[],
            ),
            "exactly one REORGANIZE action",
        ),
    ],
)
def test_programmatic_directed_ast_generation_is_guarded(
    expression: exp.Expr, message: str
) -> None:
    with pytest.raises(UnsupportedError, match=message):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_programmatic_annotation_preserves_explicit_parentheses() -> None:
    annotation = vexp.DirectedConstantHint(
        this=exp.Paren(this=exp.Add(this=exp.Literal.number(1), expression=exp.Literal.number(2))),
        directive=exp.var(":c"),
    )
    expression = exp.select(exp.Mul(this=annotation, expression=exp.Literal.number(3)))
    sql = expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
    assert sql == "SELECT (1 + 2) /*+:c*/ * 3"
    assert parse_one(sql, read="vertica") == expression
