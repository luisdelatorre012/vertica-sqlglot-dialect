#!/usr/bin/env python3
"""
Advanced Transformation Examples for Vertica SQLGlot Dialect

This file demonstrates advanced AST transformations, including:
- Custom AST manipulation functions
- Query optimization with SQLGlot's optimizer
- Schema extraction and data lineage
- Cross-dialect compatibility testing
"""

import sys
import os

# Add the parent directory to the path so we can import our dialect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlglot import parse_one, transpile, exp
from sqlglot.optimizer import optimize


def replace_md5_with_sha1(node):
    """
    A custom transformation function to replace MD5 with SHA1.
    This can be used with `ast.transform()`.
    """
    if isinstance(node, exp.Anonymous) and node.this == "MD5":
        return exp.Anonymous(this="SHA1", expressions=node.expressions)
    return node


def add_table_alias(node, alias):
    """Adds a table alias if one is not present."""
    if isinstance(node, exp.Table):
        if not node.alias:
            node.set('alias', exp.to_identifier(alias))
    return node


def convert_case_to_coalesce(node):
    """Converts a simple CASE statement to a COALESCE call."""
    if isinstance(node, exp.Case) and len(node.args.get("ifs", [])) == 1:
        if_condition = node.args["ifs"][0]
        if isinstance(if_condition.this, exp.Is) and if_condition.this.this.sql() == "name":
             return exp.Coalesce(this=exp.to_identifier("name"), expressions=[if_condition.true])
    return node


def advanced_transformation_examples():
    """Demonstrate advanced AST transformations and rewrites"""
    print("=" * 60)
    print("ADVANCED TRANSFORMATION EXAMPLES")
    print("=" * 60)
    
    # Example 1: Replace function call (MD5 -> SHA1)
    sql = "SELECT MD5(password) FROM users"
    ast = parse_one(sql, read="vertica")
    # We need to find the function call and replace it.
    # For this example, we'll manually replace it.
    for func in ast.find_all(exp.Anonymous):
        if func.this == "MD5":
            func.this = "SHA1"
            
    print(f"Original SQL: {sql}")
    print(f"Transformed SQL: {ast.sql(dialect='vertica')}")
    print()
    
    # Example 2: Add table alias automatically using transform
    sql = "SELECT id, name FROM users"
    ast = parse_one(sql, read="vertica")
    transformed_ast = ast.transform(add_table_alias, "u")
    print(f"Original SQL: {sql}")
    print(f"Transformed SQL: {transformed_ast.sql(dialect='vertica')}")
    print()

    # Example 3: Convert CASE to COALESCE
    sql = "SELECT CASE WHEN name IS NOT NULL THEN name ELSE 'N/A' END FROM products"
    ast = parse_one(sql, read="vertica")
    # This is a bit more complex, we'll just show the concept
    print(f"Original SQL: {sql}")
    print(f"Conceptually transformed SQL: SELECT COALESCE(name, 'N/A') FROM products")
    print()


def query_optimization_examples():
    """Demonstrate query optimization using SQLGlot's optimizer"""
    print("=" * 60)
    print("QUERY OPTIMIZATION EXAMPLES")
    print("=" * 60)

    # Example 1: Basic optimization (qualify columns)
    sql = "SELECT id, name FROM users JOIN roles ON users.role_id = roles.id"
    optimized_sql = optimize(sql, read="vertica").sql("vertica")
    print(f"Original SQL: {sql}")
    print(f"Optimized SQL: {optimized_sql}")
    print()

    # Example 2: Pushing down predicates
    sql = """
    SELECT u.id, p.name 
    FROM (SELECT id FROM users WHERE last_login > '2023-01-01') u
    JOIN products p ON u.id = p.owner_id
    """
    optimized_sql = optimize(sql, read="vertica").sql("vertica", pretty=True)
    print(f"Original SQL: {sql.strip()}")
    print(f"Optimized SQL: {optimized_sql}")
    print()
    
    # Example 3: Simplifying expressions
    sql = "SELECT 1 = 1 AND name = 'test'"
    optimized_sql = optimize(sql, read="vertica").sql("vertica")
    print(f"Original SQL: {sql}")
    print(f"Optimized SQL: {optimized_sql}")
    print()


def schema_and_lineage_examples():
    """Demonstrate schema-based analysis and data lineage"""
    print("=" * 60)
    print("SCHEMA AND LINEAGE EXAMPLES")
    print("=" * 60)

    schema = {
        "users": {"id": "int", "name": "varchar"},
        "orders": {"id": "int", "user_id": "int", "amount": "decimal"}
    }
    
    sql = "SELECT u.id, o.amount FROM users u JOIN orders o ON u.id = o.user_id"
    
    # Example 1: Qualify columns with schema
    qualified_ast = parse_one(sql, read="vertica")
    qualified_ast.qualify(schema=schema)
    print(f"Original SQL: {sql}")
    print(f"Qualified SQL: {qualified_ast.sql(dialect='vertica')}")
    print()


def cross_dialect_compatibility_examples():
    """Demonstrate cross-dialect compatibility testing"""
    print("=" * 60)
    print("CROSS-DIALECT COMPATIBILITY EXAMPLES")
    print("=" * 60)

    vertica_sql = "SELECT TO_CHAR(CURRENT_DATE, 'YYYY-MM-DD')"
    
    # Transpile to PostgreSQL
    postgres_sql = transpile(vertica_sql, read="vertica", write="postgres")[0]
    print(f"Vertica: {vertica_sql}")
    print(f"Postgres: {postgres_sql}")
    print()
    
    # Transpile to BigQuery
    bigquery_sql = transpile(vertica_sql, read="vertica", write="bigquery")[0]
    print(f"Vertica: {vertica_sql}")
    print(f"BigQuery: {bigquery_sql}")
    print()

    # Example with unsupported function
    vertica_sql = "SELECT APPROXIMATE_COUNT_DISTINCT(user_id) FROM sessions"
    
    try:
        # Transpiling to standard SQL might fail
        transpile(vertica_sql, read="vertica", write="duckdb")
    except Exception as e:
        print(f"✓ Correctly caught transpilation error for: {vertica_sql}")
        print(f"  {e}")
    print()


def main():
    """Run all examples"""
    print("Vertica SQLGlot Dialect - Advanced Transformation Examples")
    print("=" * 60)
    print()

    try:
        advanced_transformation_examples()
        query_optimization_examples()
        schema_and_lineage_examples()
        cross_dialect_compatibility_examples()
        
        print("All examples completed successfully! ✓")

    except Exception as e:
        print(f"\nError running examples: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 