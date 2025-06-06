#!/usr/bin/env python3
"""
Data Migration Examples for Vertica SQLGlot Dialect

This file demonstrates how to use the Vertica dialect to transpile SQL
for data migration projects, covering:
- DDL (Data Definition Language) migration
- DML (Data Manipulation Language) and query migration
- Handling of Vertica-specific functions and data types
- Batch processing for large-scale migrations
"""

import sys
import os
import concurrent.futures

# Add the parent directory to the path so we can import our dialect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlglot import transpile
from sqlglot.errors import ParseError, UnsupportedError
from vertica_sqlglot_dialect import Vertica


def migrate_ddl(vertica_ddl, target_dialect="postgres"):
    """Migrate a single Vertica DDL statement to a target dialect."""
    try:
        transpiled_ddls = transpile(
            vertica_ddl,
            read=Vertica,
            write=target_dialect,
            pretty=True
        )
        return "\n".join(transpiled_ddls)
    except (ParseError, UnsupportedError) as e:
        print(f"Could not transpile DDL: {vertica_ddl}\nError: {e}")
        return None


def migrate_query(vertica_query, target_dialect="postgres"):
    """Migrate a single Vertica query to a target dialect."""
    try:
        transpiled_query = transpile(
            vertica_query,
            read=Vertica,
            write=target_dialect,
            pretty=True
        )[0]
        return transpiled_query
    except (ParseError, UnsupportedError) as e:
        print(f"Could not transpile query: {vertica_query}\nError: {e}")
        return None


def ddl_migration_examples():
    """Demonstrate DDL migration from Vertica to other databases."""
    print("=" * 60)
    print("DDL MIGRATION EXAMPLES")
    print("=" * 60)
    
    # Example 1: Basic CREATE TABLE
    vertica_ddl = "CREATE TABLE users (id INTEGER, name VARCHAR(100), created_at TIMESTAMPTZ)"
    postgres_ddl = migrate_ddl(vertica_ddl, "postgres")
    
    print("--- Basic CREATE TABLE ---")
    if postgres_ddl:
        print(postgres_ddl)
    print()
    
    # Example 2: Table with constraints
    vertica_ddl = """
    CREATE TABLE products (
        product_id INTEGER PRIMARY KEY,
        sku VARCHAR(50) NOT NULL UNIQUE,
        price NUMERIC(10, 2)
    )
    """
    postgres_ddl = migrate_ddl(vertica_ddl, "postgres")
    
    print("\n--- CREATE TABLE with Constraints ---")
    if postgres_ddl:
        print(postgres_ddl)
    print()

    # Example 3: Vertica-specific DDL (should fail gracefully)
    vertica_ddl = "CREATE PROJECTION products_proj AS SELECT * FROM products;"
    migrate_ddl(vertica_ddl, "postgres")
    print("\n--- Vertica-specific DDL (Projection) ---")
    print("Attempted to migrate a Vertica PROJECTION. Expecting graceful failure or no output.")
    print()


def function_migration_examples():
    """Demonstrate migration of queries with Vertica-specific functions."""
    print("=" * 60)
    print("FUNCTION MIGRATION EXAMPLES")
    print("=" * 60)

    # Example 1: Date/time functions
    vertica_sql = "SELECT DATEDIFF('day', start_date, end_date) FROM events"
    postgres_sql = migrate_query(vertica_sql, "postgres")
    
    print("--- Date/Time Function Migration ---")
    print(f"Vertica: {vertica_sql}")
    if postgres_sql:
        print(f"PostgreSQL: {postgres_sql}")
    print()
    
    # Example 2: String and hash functions
    vertica_sql = "SELECT ILIKE(name, 'A%'), MD5(email) FROM customers"
    postgres_sql = migrate_query(vertica_sql, "postgres")
    
    print("\n--- String/Hash Function Migration ---")
    print(f"Vertica: {vertica_sql}")
    if postgres_sql:
        print(f"PostgreSQL: {postgres_sql}")
    print()

    # Example 3: Aggregate functions
    vertica_sql = "SELECT APPROXIMATE_COUNT_DISTINCT(user_id) FROM sessions"
    postgres_sql = migrate_query(vertica_sql, "postgres")
    
    print("\n--- Aggregate/Analytic Function Migration ---")
    print(f"Vertica: {vertica_sql}")
    if postgres_sql:
        print(f"PostgreSQL: {postgres_sql}")
    print()


def batch_migration_examples(scripts, target_dialect="postgres"):
    """Demonstrate batch processing of SQL scripts for migration."""
    print("=" * 60)
    print(f"BATCH MIGRATION TO {target_dialect.upper()}")
    print("=" * 60)

    def process_script(script_content):
        try:
            # A simple way to distinguish DDL from DML
            if script_content.strip().upper().startswith("CREATE"):
                return migrate_ddl(script_content, target_dialect)
            else:
                return migrate_query(script_content, target_dialect)
        except Exception as e:
            return f"Error processing script: {e}"

    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = list(executor.map(process_script, scripts))
    
    for i, result in enumerate(results):
        print(f"--- Script {i+1} ---")
        if result:
            print(result)
        else:
            print("Migration failed or produced no output.")
        print()


def main():
    """Run all data migration examples"""
    print("Vertica SQLGlot Dialect - Data Migration Examples")
    print("=" * 60)
    print()

    try:
        ddl_migration_examples()
        function_migration_examples()
        
        # Batch processing example
        sql_scripts = [
            "CREATE TABLE employees (id INT, name VARCHAR, dept VARCHAR, hire_date DATE);",
            "SELECT name, DATEDIFF('year', hire_date, CURRENT_DATE) as years_of_service FROM employees WHERE dept = 'Engineering';",
            "CREATE PROJECTION employee_proj AS SELECT * FROM employees;" # This one should fail
        ]
        batch_migration_examples(sql_scripts, target_dialect="duckdb")

        print("All examples completed successfully! ✓")

    except Exception as e:
        print(f"\nError running examples: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
