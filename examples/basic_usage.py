#!/usr/bin/env python3
"""
Basic Usage Examples for Vertica SQLGlot Dialect

This file demonstrates fundamental operations with the Vertica dialect:
- Parsing SQL with Vertica-specific syntax
- Transpiling between dialects
- Basic AST inspection
- Error handling for unsupported features
"""

import sys
import os

# Add the parent directory to the path so we can import our dialect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlglot import parse_one, transpile, exp
from sqlglot_vertica.vertica import Vertica
from sqlglot.errors import ParseError, UnsupportedError


def basic_parsing_examples():
    """Demonstrate basic SQL parsing with Vertica dialect"""
    print("=" * 60)
    print("BASIC PARSING EXAMPLES")
    print("=" * 60)
    
    # Example 1: Basic SELECT with Vertica functions
    sql = "SELECT DATEADD(day, 7, hire_date), MD5(email) FROM employees"
    ast = parse_one(sql, read=Vertica)
    print(f"Original SQL: {sql}")
    print(f"Parsed AST type: {type(ast).__name__}")
    print(f"Generated SQL: {ast.sql(dialect=Vertica)}")
    print()
    
    # Example 2: Window functions with Vertica syntax
    sql = """
    SELECT 
        emp_id,
        salary,
        ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC) as rank
    FROM employees
    """
    ast = parse_one(sql, read=Vertica)
    print(f"Window function SQL: {ast.sql(dialect=Vertica, pretty=True)}")
    print()
    
    # Example 3: Vertica-specific data types
    sql = "CREATE TABLE test (id INTEGER, data BYTEA, ts TIMESTAMPTZ)"
    ast = parse_one(sql, read=Vertica)
    print(f"DDL with Vertica types: {ast.sql(dialect=Vertica)}")
    print()


def dialect_transpilation_examples():
    """Demonstrate transpiling between Vertica and other dialects"""
    print("=" * 60)
    print("DIALECT TRANSPILATION EXAMPLES")
    print("=" * 60)
    
    # Example 1: Vertica to PostgreSQL
    vertica_sql = "SELECT TO_CHAR(hire_date, 'YYYY-MM-DD'), ILIKE(name, 'John%') FROM employees"
    
    # Transpile to different dialects
    postgres_sql = transpile(vertica_sql, read=Vertica, write="postgres")[0]
    mysql_sql = transpile(vertica_sql, read=Vertica, write="mysql")[0]
    
    print(f"Original Vertica SQL:\n  {vertica_sql}")
    print(f"PostgreSQL equivalent:\n  {postgres_sql}")
    print(f"MySQL equivalent:\n  {mysql_sql}")
    print()
    
    # Example 2: Converting date functions
    vertica_sql = "SELECT DATEDIFF(day, start_date, end_date) as duration FROM projects"
    
    postgres_sql = transpile(vertica_sql, read=Vertica, write="postgres")[0]
    print(f"Vertica DATEDIFF:\n  {vertica_sql}")
    print(f"PostgreSQL equivalent:\n  {postgres_sql}")
    print()
    
    # Example 3: Batch transpilation
    vertica_queries = [
        "SELECT MD5(password) FROM users",
        "SELECT APPROXIMATE_COUNT_DISTINCT(user_id) FROM sessions",
        "SELECT DATE_TRUNC('month', created_at) FROM orders"
    ]
    
    print("Batch transpilation to PostgreSQL:")
    for i, query in enumerate(vertica_queries, 1):
        postgres_query = transpile(query, read=Vertica, write="postgres")[0]
        print(f"  {i}. {query}")
        print(f"     → {postgres_query}")
    print()


def ast_inspection_examples():
    """Demonstrate AST inspection and manipulation"""
    print("=" * 60)
    print("AST INSPECTION EXAMPLES")
    print("=" * 60)
    
    sql = """
    SELECT 
        emp.name,
        dept.name as dept_name,
        COUNT(*) OVER (PARTITION BY dept.id) as dept_count
    FROM employees emp
    JOIN departments dept ON emp.dept_id = dept.id
    WHERE emp.salary > 50000
    ORDER BY emp.name
    """
    
    ast = parse_one(sql, read=Vertica)
    
    # Extract table names
    tables = [table.name for table in ast.find_all(exp.Table)]
    print(f"Tables referenced: {tables}")
    
    # Extract column references
    columns = [col.sql() for col in ast.find_all(exp.Column)]
    print(f"Columns referenced: {columns}")
    
    # Extract functions used
    functions = [func.sql() for func in ast.find_all(exp.Func)]
    print(f"Functions used: {functions}")
    
    # Extract window functions
    windows = [win.sql() for win in ast.find_all(exp.Window)]
    print(f"Window functions: {windows}")
    print()


def error_handling_examples():
    """Demonstrate error handling for unsupported features"""
    print("=" * 60)
    print("ERROR HANDLING EXAMPLES")
    print("=" * 60)
    
    # Example 1: Dollar-quoted strings (unsupported)
    try:
        sql = "SELECT $$this is a dollar quoted string$$"
        parse_one(sql, read=Vertica)
    except ParseError as e:
        print("✓ Correctly caught dollar-quoted string error:")
        print(f"  {e}")
    print()
    
    # Example 2: LATERAL joins (unsupported)
    try:
        sql = """
        SELECT * FROM users u
        LEFT JOIN LATERAL (
            SELECT * FROM orders WHERE user_id = u.id LIMIT 1
        ) o ON true
        """
        parse_one(sql, read=Vertica)
    except ParseError as e:
        print("✓ Correctly caught LATERAL join error:")
        print(f"  {e}")
    print()
    
    # Example 3: COPY FROM LOCAL (unsupported)
    try:
        sql = "COPY table1 FROM LOCAL '/tmp/data.csv' DELIMITER ','"
        parse_one(sql, read=Vertica)
    except UnsupportedError as e:
        print("✓ Correctly caught COPY FROM LOCAL error:")
        print(f"  {e}")
    print()
    
    # Example 4: Unsupported data types
    try:
        sql = "SELECT '{1,2,3}'::int4multirange"
        parse_one(sql, read=Vertica)
    except ParseError as e:
        print("✓ Correctly caught unsupported type error:")
        print(f"  {e}")
    print()


def main():
    """Run all examples"""
    print("Vertica SQLGlot Dialect - Basic Usage Examples")
    print("=" * 60)
    print()
    
    try:
        basic_parsing_examples()
        dialect_transpilation_examples()
        ast_inspection_examples()
        error_handling_examples()
        
        print("All examples completed successfully! ✓")
        
    except Exception as e:
        print(f"Error running examples: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 