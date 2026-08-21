"""Official 26.2 SELECT-family documentation corpus regressions.

Statements are adapted from the worked examples on the SELECT statement page
and its FROM/joined-table, WHERE, GROUP BY, HAVING, ORDER BY, LIMIT, OFFSET,
UNION, INTERSECT, EXCEPT, MINUS, WITH, and WITH-clause-recursion subpages,
plus the data-analysis subqueries guide, adapted only where determinism
requires (for example dropping nondeterministic result-set commentary).
"""

from __future__ import annotations

import pytest
from sqlglot import exp

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


def test_select_all_is_default_and_elided() -> None:
    assert_roundtrip(
        "SELECT ALL customer_name FROM customer_dimension",
        "SELECT customer_name FROM customer_dimension",
    )


def test_select_distinct() -> None:
    assert_roundtrip(
        "SELECT DISTINCT customer_name FROM customer_dimension",
        "SELECT DISTINCT customer_name FROM customer_dimension",
    )


def test_select_match_columns_pattern() -> None:
    expression = assert_roundtrip(
        "SELECT MATCH_COLUMNS('cust.*') FROM customer_dimension",
        "SELECT MATCH_COLUMNS('cust.*') FROM customer_dimension",
    )
    assert isinstance(expression.selects[0], exp.Anonymous)


def test_select_for_update_lock() -> None:
    expression = assert_roundtrip(
        "SELECT balance FROM accounts WHERE account_id = 3476 FOR UPDATE",
        "SELECT balance FROM accounts WHERE account_id = 3476 FOR UPDATE",
    )
    lock = expression.args["locks"][0]
    assert isinstance(lock, exp.Lock)
    assert lock.args["update"] is True


def test_select_for_update_of_table_list() -> None:
    expression = assert_roundtrip(
        "SELECT balance FROM accounts WHERE account_id = 3476 FOR UPDATE OF accounts",
        "SELECT balance FROM accounts WHERE account_id = 3476 FOR UPDATE OF accounts",
    )
    lock = expression.args["locks"][0]
    assert [table.name for table in lock.expressions] == ["accounts"]


def test_from_tablesample() -> None:
    expression = assert_roundtrip(
        "SELECT customer_name, customer_state FROM customer_dimension "
        "TABLESAMPLE(0.5) WHERE customer_state = 'IL'",
        "SELECT customer_name, customer_state FROM customer_dimension "
        "TABLESAMPLE (0.5) WHERE customer_state = 'IL'",
    )
    assert expression.args["from_"].this.args.get("sample") is not None


def test_from_multicolumn_named_subquery() -> None:
    assert_roundtrip(
        "SELECT e.employee_first_name, e.annual_salary, s.average "
        "FROM employee_dimension AS e, "
        "(SELECT employee_region, AVG(annual_salary) AS average FROM employee_dimension "
        "GROUP BY employee_region) AS s "
        "WHERE e.employee_region = s.employee_region AND e.annual_salary > s.average",
    )


def test_where_boolean_expression_with_ilike() -> None:
    assert_roundtrip(
        "SELECT DISTINCT customer_name FROM customer_dimension "
        "WHERE customer_region = 'East' AND customer_name ILIKE 'Amer%'",
        "SELECT DISTINCT customer_name FROM customer_dimension "
        "WHERE customer_region = 'East' AND customer_name ILIKE 'Amer%'",
    )


def test_where_parenthesized_not_precedence() -> None:
    expression = assert_roundtrip(
        "SELECT * FROM t WHERE NOT (a = 1 AND b = 2) OR c = 3",
        "SELECT * FROM t WHERE NOT (a = 1 AND b = 2) OR c = 3",
    )
    assert isinstance(expression.args["where"].this, exp.Or)


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (
            "SELECT * FROM a JOIN b ON a.id = b.id",
            "SELECT * FROM a JOIN b ON a.id = b.id",
        ),
        (
            "SELECT * FROM a LEFT JOIN b ON a.id = b.id",
            "SELECT * FROM a LEFT JOIN b ON a.id = b.id",
        ),
        (
            "SELECT * FROM a LEFT OUTER JOIN b ON a.id = b.id",
            "SELECT * FROM a LEFT OUTER JOIN b ON a.id = b.id",
        ),
        (
            "SELECT * FROM a RIGHT JOIN b ON a.id = b.id",
            "SELECT * FROM a RIGHT JOIN b ON a.id = b.id",
        ),
        (
            "SELECT * FROM a FULL JOIN b ON a.id = b.id",
            "SELECT * FROM a FULL JOIN b ON a.id = b.id",
        ),
        (
            "SELECT * FROM a FULL OUTER JOIN b ON a.id = b.id",
            "SELECT * FROM a FULL OUTER JOIN b ON a.id = b.id",
        ),
    ],
)
def test_joined_table_default_and_outer_variants(sql: str, expected: str) -> None:
    expression = assert_roundtrip(sql, expected)
    assert isinstance(expression.args["joins"][0], exp.Join)


def test_joined_table_natural() -> None:
    expression = assert_roundtrip(
        "SELECT * FROM a NATURAL JOIN b", "SELECT * FROM a NATURAL JOIN b"
    )
    assert expression.args["joins"][0].args.get("method") == "NATURAL"


def test_joined_table_cross() -> None:
    expression = assert_roundtrip("SELECT * FROM a CROSS JOIN b", "SELECT * FROM a CROSS JOIN b")
    assert expression.args["joins"][0].args.get("kind") == "CROSS"


def test_joined_table_tablesample_on_both_sides() -> None:
    assert_roundtrip(
        "SELECT user_id.id, user_name.name FROM user_name TABLESAMPLE(50) "
        "JOIN user_id TABLESAMPLE(50) ON user_name.id = user_id.id",
        "SELECT user_id.id, user_name.name FROM user_name TABLESAMPLE (50) "
        "JOIN user_id TABLESAMPLE (50) ON user_name.id = user_id.id",
    )


def test_group_by_basic_aggregate() -> None:
    expression = assert_roundtrip(
        "SELECT employee_last_name, SUM(vacation_days) FROM employee_dimension "
        "WHERE employee_last_name ILIKE 'S%' GROUP BY employee_last_name",
        "SELECT employee_last_name, SUM(vacation_days) FROM employee_dimension "
        "WHERE employee_last_name ILIKE 'S%' GROUP BY employee_last_name",
    )
    assert isinstance(expression.args["group"], exp.Group)


def test_group_by_mixed_expressions_and_rollup_preserves_order() -> None:
    assert_roundtrip(
        "SELECT a, b, c, d, SUM(e) FROM t GROUP BY a, b, c, d, ROLLUP(a, b)",
        "SELECT a, b, c, d, SUM(e) FROM t GROUP BY a, b, c, d, ROLLUP (a, b)",
    )


def test_group_by_rollup_cube_grouping_sets_ast_shape() -> None:
    expression = assert_roundtrip(
        "SELECT a, b, c, SUM(e) FROM t GROUP BY ROLLUP(a), CUBE(b), GROUPING SETS(c)",
        "SELECT a, b, c, SUM(e) FROM t GROUP BY ROLLUP (a), CUBE (b), GROUPING SETS (c)",
    )
    group = expression.args["group"]
    assert [type(item) for item in group.expressions] == [
        exp.Rollup,
        exp.Cube,
        exp.GroupingSets,
    ]


def test_having_filters_aggregate() -> None:
    assert_roundtrip(
        "SELECT employee_last_name, MAX(annual_salary) AS highest_salary "
        "FROM employee_dimension GROUP BY employee_last_name "
        "HAVING MAX(annual_salary) > 800000 ORDER BY highest_salary DESC",
        "SELECT employee_last_name, MAX(annual_salary) AS highest_salary "
        "FROM employee_dimension GROUP BY employee_last_name "
        "HAVING MAX(annual_salary) > 800000 ORDER BY highest_salary DESC",
    )


def test_having_with_subquery() -> None:
    expression = assert_roundtrip(
        "SELECT s.product_key, COUNT(s.customer_key) FROM store.store_sales_fact AS s "
        "GROUP BY s.product_key HAVING s.product_key IN "
        "(SELECT product_key FROM product_dimension WHERE diet_type = 'Low Fat')",
        "SELECT s.product_key, COUNT(s.customer_key) FROM store.store_sales_fact AS s "
        "GROUP BY s.product_key HAVING s.product_key IN "
        "(SELECT product_key FROM product_dimension WHERE diet_type = 'Low Fat')",
    )
    assert expression.find(exp.Subquery) is not None


def test_order_by_direction() -> None:
    assert_roundtrip(
        "SELECT customer_city, deal_size FROM customer_dimension "
        "WHERE customer_name = 'Metamedia' ORDER BY deal_size DESC",
        "SELECT customer_city, deal_size FROM customer_dimension "
        "WHERE customer_name = 'Metamedia' ORDER BY deal_size DESC",
    )


def test_order_by_ordinal_positions() -> None:
    assert_roundtrip(
        "SELECT a, b FROM t ORDER BY 2, 1 DESC", "SELECT a, b FROM t ORDER BY 2, 1 DESC"
    )


def test_limit_all_canonicalizes_to_clause_absence() -> None:
    # Q11 makes this an explicit semantic-no-op canonicalization rather than
    # the accidental base-SQLGlot loss originally recorded by Q04.
    expression = assert_roundtrip(
        "SELECT * FROM t ORDER BY a LIMIT ALL", "SELECT * FROM t ORDER BY a"
    )
    assert expression.args.get("limit") is None


def test_offset_alone_requires_no_limit() -> None:
    assert_roundtrip(
        "SELECT customer_name, customer_gender FROM customer_dimension "
        "WHERE occupation = 'Dancer' AND customer_city = 'San Francisco' "
        "ORDER BY customer_name OFFSET 8",
        "SELECT customer_name, customer_gender FROM customer_dimension "
        "WHERE occupation = 'Dancer' AND customer_city = 'San Francisco' "
        "ORDER BY customer_name OFFSET 8",
    )


def test_limit_and_offset_combined() -> None:
    assert_roundtrip(
        "SELECT customer_name FROM customer_dimension ORDER BY customer_name LIMIT 5 OFFSET 8",
        "SELECT customer_name FROM customer_dimension ORDER BY customer_name LIMIT 5 OFFSET 8",
    )


def test_union_distinct_default_is_elided() -> None:
    expression = assert_roundtrip(
        "SELECT id, emp_name FROM company_a UNION DISTINCT SELECT id, emp_name FROM company_b "
        "ORDER BY id",
        "SELECT id, emp_name FROM company_a UNION SELECT id, emp_name FROM company_b ORDER BY id",
    )
    assert isinstance(expression, exp.Union)


def test_union_all() -> None:
    assert_roundtrip(
        "SELECT id, emp_name FROM company_a UNION ALL SELECT id, emp_name FROM company_b "
        "ORDER BY id",
        "SELECT id, emp_name FROM company_a UNION ALL SELECT id, emp_name FROM company_b "
        "ORDER BY id",
    )


def test_union_branches_with_individual_order_by_and_limit() -> None:
    assert_roundtrip(
        "(SELECT id, emp_name, sales FROM company_a ORDER BY sales DESC LIMIT 2) "
        "UNION ALL "
        "(SELECT id, emp_name, sales FROM company_b ORDER BY sales DESC LIMIT 2)",
        "(SELECT id, emp_name, sales FROM company_a ORDER BY sales DESC LIMIT 2) "
        "UNION ALL (SELECT id, emp_name, sales FROM company_b ORDER BY sales DESC LIMIT 2)",
    )


def test_intersect_basic() -> None:
    expression = assert_roundtrip(
        "SELECT id, emp_lname FROM company_a INTERSECT SELECT id, emp_lname FROM company_b",
        "SELECT id, emp_lname FROM company_a INTERSECT SELECT id, emp_lname FROM company_b",
    )
    assert isinstance(expression, exp.Intersect)


def test_intersect_chained_three_way() -> None:
    assert_roundtrip(
        "SELECT id, emp_lname FROM company_a INTERSECT SELECT id, emp_lname FROM company_b "
        "INTERSECT SELECT id, emp_lname FROM company_c",
        "SELECT id, emp_lname FROM company_a INTERSECT SELECT id, emp_lname FROM company_b "
        "INTERSECT SELECT id, emp_lname FROM company_c",
    )


def test_except_basic() -> None:
    expression = assert_roundtrip(
        "SELECT id, emp_lname FROM company_a EXCEPT SELECT id, emp_lname FROM company_b",
        "SELECT id, emp_lname FROM company_a EXCEPT SELECT id, emp_lname FROM company_b",
    )
    assert isinstance(expression, exp.Except)


def test_except_chained() -> None:
    assert_roundtrip(
        "SELECT id, emp_lname FROM company_a EXCEPT SELECT id, emp_lname FROM company_b "
        "EXCEPT SELECT id, emp_lname FROM company_c",
        "SELECT id, emp_lname FROM company_a EXCEPT SELECT id, emp_lname FROM company_b "
        "EXCEPT SELECT id, emp_lname FROM company_c",
    )


def test_minus_is_an_except_alias() -> None:
    expression = assert_roundtrip(
        "SELECT id, emp_lname FROM company_a MINUS SELECT id, emp_lname FROM company_b",
        "SELECT id, emp_lname FROM company_a EXCEPT SELECT id, emp_lname FROM company_b",
    )
    assert isinstance(expression, exp.Except)


def test_with_single_cte() -> None:
    expression = assert_roundtrip(
        "WITH revenue (vkey, total_revenue) AS ("
        "SELECT vendor_key, SUM(total_order_cost) "
        "FROM store.store_orders_fact "
        "GROUP BY vendor_key ORDER BY 1) "
        "SELECT v.vendor_name, v.vendor_address, v.vendor_city, r.total_revenue "
        "FROM vendor_dimension v JOIN revenue r ON v.vendor_key = r.vkey "
        "WHERE r.total_revenue = (SELECT MAX(total_revenue) FROM revenue) "
        "ORDER BY vendor_name",
        "WITH revenue(vkey, total_revenue) AS "
        "(SELECT vendor_key, SUM(total_order_cost) FROM store.store_orders_fact "
        "GROUP BY vendor_key ORDER BY 1) "
        "SELECT v.vendor_name, v.vendor_address, v.vendor_city, r.total_revenue "
        "FROM vendor_dimension AS v JOIN revenue AS r ON v.vendor_key = r.vkey "
        "WHERE r.total_revenue = (SELECT MAX(total_revenue) FROM revenue) "
        "ORDER BY vendor_name",
    )
    assert len(expression.args["with_"].expressions) == 1


def test_with_multiple_ctes_and_rollup_grouping_id() -> None:
    expression = assert_roundtrip(
        "WITH "
        "regional_sales (region, total_sales) AS ("
        "SELECT sd.store_region, SUM(of.total_order_cost) AS total_sales "
        "FROM store.store_dimension sd JOIN store.store_orders_fact of "
        "ON sd.store_key = of.store_key "
        "GROUP BY store_region), "
        "top_regions AS ("
        "SELECT region, total_sales "
        "FROM regional_sales ORDER BY total_sales DESC LIMIT 3) "
        "SELECT sd.store_region AS region, pd.department_description AS department, "
        "SUM(of.total_order_cost) AS product_sales "
        "FROM store.store_orders_fact of "
        "JOIN store.store_dimension sd ON sd.store_key = of.store_key "
        "JOIN public.product_dimension pd ON of.product_key = pd.product_key "
        "WHERE sd.store_region IN (SELECT region FROM top_regions) "
        "GROUP BY ROLLUP (region, department) ORDER BY region, product_sales DESC, GROUPING_ID()",
        "WITH regional_sales(region, total_sales) AS "
        "(SELECT sd.store_region, SUM(of.total_order_cost) AS total_sales "
        "FROM store.store_dimension AS sd JOIN store.store_orders_fact AS of "
        "ON sd.store_key = of.store_key GROUP BY store_region), "
        "top_regions AS (SELECT region, total_sales FROM regional_sales "
        "ORDER BY total_sales DESC LIMIT 3) "
        "SELECT sd.store_region AS region, pd.department_description AS department, "
        "SUM(of.total_order_cost) AS product_sales "
        "FROM store.store_orders_fact AS of "
        "JOIN store.store_dimension AS sd ON sd.store_key = of.store_key "
        "JOIN public.product_dimension AS pd ON of.product_key = pd.product_key "
        "WHERE sd.store_region IN (SELECT region FROM top_regions) "
        "GROUP BY ROLLUP (region, department) "
        "ORDER BY region, product_sales DESC, GROUPING_ID()",
    )
    assert len(expression.args["with_"].expressions) == 2


def test_with_recursive_plain_without_hint() -> None:
    expression = assert_roundtrip(
        "WITH RECURSIVE nums (n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM nums) SELECT n FROM nums",
        "WITH RECURSIVE nums(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM nums) SELECT n FROM nums",
    )
    assert expression.args["with_"].args.get("recursive") is True


def test_subquery_scalar_in_where() -> None:
    expression = assert_roundtrip(
        "SELECT employee_key, employee_first_name, employee_last_name, hire_date "
        "FROM employee_dimension "
        "WHERE hire_date = (SELECT MIN(hire_date) FROM employee_dimension)",
        "SELECT employee_key, employee_first_name, employee_last_name, hire_date "
        "FROM employee_dimension "
        "WHERE hire_date = (SELECT MIN(hire_date) FROM employee_dimension)",
    )
    assert expression.find(exp.Subquery) is not None


def test_subquery_in_list_in_where() -> None:
    assert_roundtrip(
        "SELECT employee_first_name, employee_last_name, annual_salary, employee_region "
        "FROM employee_dimension "
        "WHERE annual_salary IN "
        "(SELECT MAX(annual_salary) FROM employee_dimension GROUP BY employee_region) "
        "ORDER BY annual_salary DESC",
        "SELECT employee_first_name, employee_last_name, annual_salary, employee_region "
        "FROM employee_dimension WHERE annual_salary IN "
        "(SELECT MAX(annual_salary) FROM employee_dimension GROUP BY employee_region) "
        "ORDER BY annual_salary DESC",
    )


def test_subquery_named_in_from_clause() -> None:
    expression = assert_roundtrip(
        "SELECT e.employee_first_name, e.employee_last_name, e.annual_salary, "
        "e.employee_region, s.average FROM employee_dimension e, "
        "(SELECT employee_region, AVG(annual_salary) AS average FROM employee_dimension "
        "GROUP BY employee_region) AS s "
        "WHERE e.employee_region = s.employee_region AND e.annual_salary > s.average "
        "ORDER BY annual_salary DESC",
        "SELECT e.employee_first_name, e.employee_last_name, e.annual_salary, "
        "e.employee_region, s.average FROM employee_dimension AS e, "
        "(SELECT employee_region, AVG(annual_salary) AS average FROM employee_dimension "
        "GROUP BY employee_region) AS s "
        "WHERE e.employee_region = s.employee_region AND e.annual_salary > s.average "
        "ORDER BY annual_salary DESC",
    )
    assert isinstance(expression.args["joins"][0].this, exp.Subquery)


def test_subquery_with_union_in_where() -> None:
    assert_roundtrip(
        "SELECT DISTINCT customer_key, customer_name FROM public.customer_dimension "
        "WHERE customer_key IN (SELECT customer_key FROM store.store_sales_fact "
        "WHERE sales_dollar_amount > 500 "
        "UNION ALL "
        "SELECT customer_key FROM online_sales.online_sales_fact "
        "WHERE sales_dollar_amount > 500) "
        "AND customer_state = 'CT'",
        "SELECT DISTINCT customer_key, customer_name FROM public.customer_dimension "
        "WHERE customer_key IN (SELECT customer_key FROM store.store_sales_fact "
        "WHERE sales_dollar_amount > 500 "
        "UNION ALL "
        "SELECT customer_key FROM online_sales.online_sales_fact "
        "WHERE sales_dollar_amount > 500) "
        "AND customer_state = 'CT'",
    )


def test_at_epoch_query_prefix_epoch_latest() -> None:
    # SELECT's own [ AT epoch ] prefix (26.2 formal syntax; no worked example
    # exists on any SELECT-family page). See tests/test_at_epoch_query.py for
    # the family's full contract, including malformed forms and foreign
    # generation.
    assert_roundtrip(
        "AT EPOCH LATEST SELECT * FROM t",
        "AT EPOCH LATEST SELECT * FROM t",
    )


def test_at_epoch_query_prefix_epoch_integer() -> None:
    assert_roundtrip(
        "AT EPOCH 5 SELECT * FROM t",
        "AT EPOCH 5 SELECT * FROM t",
    )


def test_at_epoch_query_prefix_time_literal() -> None:
    assert_roundtrip(
        "AT TIME '2024-01-01 00:00:00' SELECT * FROM t",
        "AT TIME '2024-01-01 00:00:00' SELECT * FROM t",
    )


def test_at_epoch_query_prefix_scopes_a_with_clause() -> None:
    assert_roundtrip(
        "AT EPOCH LATEST WITH cte AS (SELECT 1) SELECT * FROM cte",
        "AT EPOCH LATEST WITH cte AS (SELECT 1) SELECT * FROM cte",
    )


def test_at_epoch_query_prefix_scopes_a_union_chain() -> None:
    # The prefix precedes the whole union-clause/intersect-clause/except-clause
    # production, not one bare SELECT, so it must wrap the entire compound
    # query rather than only its first branch.
    expression = assert_roundtrip(
        "AT EPOCH LATEST SELECT 1 UNION SELECT 2",
        "AT EPOCH LATEST SELECT 1 UNION SELECT 2",
    )
    assert isinstance(expression, vexp.AtEpochUnion)
