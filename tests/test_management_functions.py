"""Vertica management meta-function parsing and AST regressions."""

from __future__ import annotations

import pytest
from sqlglot import exp

from tests.helpers import assert_roundtrip

MANAGEMENT_FUNCTION_CASES = [
    pytest.param(
        "SELECT /*+LABEL(partition_rollover)*/ "
        "MOVE_PARTITIONS_TO_TABLE('prod.sales','2026-01-01','2026-01-31',"
        "'archive.sales',TRUE)",
        "SELECT /*+ LABEL(partition_rollover) */ "
        "MOVE_PARTITIONS_TO_TABLE('prod.sales', '2026-01-01', '2026-01-31', "
        "'archive.sales', TRUE)",
        "MOVE_PARTITIONS_TO_TABLE",
        5,
        True,
        id="move-partitions-with-label",
    ),
    pytest.param(
        "SELECT SWAP_PARTITIONS_BETWEEN_TABLES('stage.sales','202601','202601','prod.sales',FALSE)",
        "SELECT SWAP_PARTITIONS_BETWEEN_TABLES("
        "'stage.sales', '202601', '202601', 'prod.sales', FALSE)",
        "SWAP_PARTITIONS_BETWEEN_TABLES",
        5,
        False,
        id="swap-partitions",
    ),
    pytest.param(
        "SELECT DROP_PARTITIONS('public.store_orders','2015-05-30','2016-01-16','true')",
        "SELECT DROP_PARTITIONS('public.store_orders', '2015-05-30', '2016-01-16', 'true')",
        "DROP_PARTITIONS",
        4,
        False,
        id="drop-partitions",
    ),
    pytest.param(
        "SELECT COPY_PARTITIONS_TO_TABLE("
        "'prod.sales','2026-01-01','2026-01-31','archive.sales','true')",
        "SELECT COPY_PARTITIONS_TO_TABLE("
        "'prod.sales', '2026-01-01', '2026-01-31', 'archive.sales', 'true')",
        "COPY_PARTITIONS_TO_TABLE",
        5,
        False,
        id="copy-partitions",
    ),
    pytest.param(
        "SELECT PARTITION_TABLE('public.store_orders')",
        "SELECT PARTITION_TABLE('public.store_orders')",
        "PARTITION_TABLE",
        1,
        False,
        id="partition-table",
    ),
    pytest.param(
        "SELECT PARTITION_PROJECTION('public.store_orders_super')",
        "SELECT PARTITION_PROJECTION('public.store_orders_super')",
        "PARTITION_PROJECTION",
        1,
        False,
        id="partition-projection",
    ),
    pytest.param(
        "SELECT DO_TM_TASK('mergeout','public.store_orders')",
        "SELECT DO_TM_TASK('mergeout', 'public.store_orders')",
        "DO_TM_TASK",
        2,
        False,
        id="tuple-mover-mergeout",
    ),
    pytest.param(
        "SELECT DO_TM_TASK('reshardmergeout','public.store_orders','2001','2005')",
        "SELECT DO_TM_TASK('reshardmergeout', 'public.store_orders', '2001', '2005')",
        "DO_TM_TASK",
        4,
        False,
        id="tuple-mover-reshard-range",
    ),
    pytest.param(
        "SELECT START_REFRESH()",
        "SELECT START_REFRESH()",
        "START_REFRESH",
        0,
        False,
        id="start-refresh",
    ),
    pytest.param(
        "SELECT REFRESH('public.t1, public.t2')",
        "SELECT REFRESH('public.t1, public.t2')",
        "REFRESH",
        1,
        False,
        id="refresh",
    ),
    pytest.param(
        "SELECT REFRESH_COLUMNS('public.t1','a, b')",
        "SELECT REFRESH_COLUMNS('public.t1', 'a, b')",
        "REFRESH_COLUMNS",
        2,
        False,
        id="refresh-columns",
    ),
    pytest.param(
        "SELECT CLEAR_PROJECTION_REFRESHES()",
        "SELECT CLEAR_PROJECTION_REFRESHES()",
        "CLEAR_PROJECTION_REFRESHES",
        0,
        False,
        id="clear-projection-refreshes",
    ),
    pytest.param(
        "SELECT PURGE()",
        "SELECT PURGE()",
        "PURGE",
        0,
        False,
        id="purge",
    ),
    pytest.param(
        "SELECT PURGE_TABLE('public.store_orders')",
        "SELECT PURGE_TABLE('public.store_orders')",
        "PURGE_TABLE",
        1,
        False,
        id="purge-table",
    ),
    pytest.param(
        "SELECT PURGE_TABLE_PROJECTIONS('public.store_orders')",
        "SELECT PURGE_TABLE_PROJECTIONS('public.store_orders')",
        "PURGE_TABLE_PROJECTIONS",
        1,
        False,
        id="purge-table-legacy-alias",
    ),
    pytest.param(
        "SELECT PURGE_PROJECTION('public.store_orders_super')",
        "SELECT PURGE_PROJECTION('public.store_orders_super')",
        "PURGE_PROJECTION",
        1,
        False,
        id="purge-projection",
    ),
    pytest.param(
        "SELECT PURGE_PARTITION('public.store_orders',2026)",
        "SELECT PURGE_PARTITION('public.store_orders', 2026)",
        "PURGE_PARTITION",
        2,
        False,
        id="purge-partition",
    ),
    pytest.param(
        "SELECT EXPORT_DIRECTED_QUERIES('/tmp/in.sql','/tmp/out.sql')",
        "SELECT EXPORT_DIRECTED_QUERIES('/tmp/in.sql', '/tmp/out.sql')",
        "EXPORT_DIRECTED_QUERIES",
        2,
        False,
        id="export-directed-queries",
    ),
    pytest.param(
        "SELECT IMPORT_DIRECTED_QUERIES('/tmp/out.sql','dq_opt')",
        "SELECT IMPORT_DIRECTED_QUERIES('/tmp/out.sql', 'dq_opt')",
        "IMPORT_DIRECTED_QUERIES",
        2,
        False,
        id="import-directed-queries",
    ),
    pytest.param(
        "SELECT /*+LABEL(management_audit)*/ "
        "SAVE_PLANS(10,TIMESTAMP '2026-01-01',TRUE,'pre-upgrade')",
        "SELECT /*+ LABEL(management_audit) */ "
        "SAVE_PLANS(10, CAST('2026-01-01' AS TIMESTAMP), TRUE, 'pre-upgrade')",
        "SAVE_PLANS",
        4,
        True,
        id="save-plans-with-label",
    ),
    pytest.param(
        "SELECT CLEAR_DIRECTED_QUERY_USAGE('dq_opt')",
        "SELECT CLEAR_DIRECTED_QUERY_USAGE('dq_opt')",
        "CLEAR_DIRECTED_QUERY_USAGE",
        1,
        False,
        id="clear-directed-query-usage",
    ),
    pytest.param(
        "SELECT EXPORT_CATALOG('/tmp/dq.sql','DIRECTED_QUERIES')",
        "SELECT EXPORT_CATALOG('/tmp/dq.sql', 'DIRECTED_QUERIES')",
        "EXPORT_CATALOG",
        2,
        False,
        id="export-directed-query-catalog",
    ),
]


def _expected_pretty_sql(compact_sql: str, has_label: bool) -> str:
    if has_label:
        select_and_hint, projection = compact_sql.split(" */ ", maxsplit=1)
        return f"{select_and_hint} */\n  {projection}"
    return f"SELECT\n  {compact_sql.removeprefix('SELECT ')}"


@pytest.mark.parametrize(
    ("sql", "expected", "function_name", "argument_count", "has_label"),
    MANAGEMENT_FUNCTION_CASES,
)
def test_management_functions_keep_canonical_select_and_anonymous_ast(
    sql: str,
    expected: str,
    function_name: str,
    argument_count: int,
    has_label: bool,
) -> None:
    expression = assert_roundtrip(sql, expected)

    assert type(expression) is exp.Select
    function = expression.expressions[0]
    assert type(function) is exp.Anonymous
    assert function.name == function_name
    assert len(function.expressions) == argument_count
    assert function.parent is expression

    walked_ids = {id(node) for node in expression.walk()}
    assert id(function) in walked_ids
    assert all(id(argument) in walked_ids for argument in function.expressions)
    assert function in expression.find_all(exp.Anonymous)

    # Vertica's object names in these APIs are string arguments, not SQL table references.
    assert not list(expression.find_all(exp.Table))
    assert expression.sql(dialect="vertica", pretty=True) == _expected_pretty_sql(
        expected, has_label
    )

    hint = expression.args.get("hint")
    if has_label:
        assert isinstance(hint, exp.Hint)
        label = hint.expressions[0]
        assert isinstance(label, exp.Anonymous)
        assert label.name == "LABEL"
    else:
        assert hint is None

    restored = exp.Expr.load(expression.dump())
    assert type(restored) is exp.Select
    assert restored.sql(dialect="vertica") == expected


@pytest.mark.parametrize(
    ("sql", "expected", "function_name"),
    [
        pytest.param(
            "SELECT MOVE_PARTITIONS_TO_TABLE('source','1')",
            "SELECT MOVE_PARTITIONS_TO_TABLE('source', '1')",
            "MOVE_PARTITIONS_TO_TABLE",
            id="wrong-partition-function-arity",
        ),
        pytest.param(
            "SELECT DO_TM_TASK('not_a_task','public.t')",
            "SELECT DO_TM_TASK('not_a_task', 'public.t')",
            "DO_TM_TASK",
            id="unknown-tuple-mover-task",
        ),
        pytest.param(
            "SELECT START_REFRESH(1)",
            "SELECT START_REFRESH(1)",
            "START_REFRESH",
            id="wrong-refresh-arity",
        ),
        pytest.param(
            "SELECT REFRESH('public.t') FROM system.tables",
            "SELECT REFRESH('public.t') FROM system.tables",
            "REFRESH",
            id="meta-function-with-from-clause",
        ),
        pytest.param(
            "SELECT COALESCE(PURGE(),0)",
            "SELECT COALESCE(PURGE(), 0)",
            "PURGE",
            id="nested-meta-function",
        ),
        pytest.param(
            "SELECT SAVE_PLANS(0)",
            "SELECT SAVE_PLANS(0)",
            "SAVE_PLANS",
            id="save-plans-budget-out-of-range",
        ),
    ],
)
def test_server_validated_management_restrictions_remain_parser_permissive(
    sql: str, expected: str, function_name: str
) -> None:
    """Catalog, arity, and top-level-only checks belong to the Vertica server."""

    expression = assert_roundtrip(sql, expected)
    assert type(expression) is exp.Select
    function = next(
        node for node in expression.find_all(exp.Anonymous) if node.name == function_name
    )
    assert function in expression.walk()
