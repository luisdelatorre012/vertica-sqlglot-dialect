#!/usr/bin/env python3
"""
Data Migration Examples for Vertica SQLGlot Dialect

This file demonstrates practical data migration scenarios:
- Converting DDL statements between databases
- Migrating stored procedures and functions
- Handling data type conversions
- Batch processing of migration scripts
"""

import os
import sys

# Add the parent directory to the path so we can import our dialect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlglot import parse_one, transpile, exp
from sqlglot_vertica.vertica import Vertica


def ddl_migration_examples():
    """Demonstrate DDL migration between databases"""
    print("=" * 60)
    print("DDL MIGRATION EXAMPLES")
    print("=" * 60)

    # Example 1: Table creation with Vertica-specific types
    vertica_ddl = """
    CREATE TABLE customer_analytics (
        id INTEGER PRIMARY KEY,
        customer_uuid UUID,
        data_blob BYTEA,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        metadata JSON,
        scores ARRAY[FLOAT],
        is_active BOOLEAN DEFAULT true
    )
    """

    print("Original Vertica DDL:")
    print(vertica_ddl)
    print()

    # Convert to different target databases
    targets = ["postgres", "mysql", "sqlite"]

    for target in targets:
        try:
            converted = transpile(vertica_ddl, read=Vertica, write=target)[0]
            print(f"Converted to {target.upper()}:")
            print(converted)
            print()
        except Exception as e:
            print(f"Error converting to {target}: {e}")
            print()

    # Example 2: Index creation
    vertica_index = """
    CREATE INDEX idx_customer_analytics_created 
    ON customer_analytics (DATE_TRUNC('day', created_at))
    """

    print("Vertica functional index:")
    print(vertica_index)

    for target in targets:
        try:
            converted = transpile(vertica_index, read=Vertica, write=target)[0]
            print(f"Converted to {target.upper()}:")
            print(converted)
            print()
        except Exception as e:
            print(f"Error converting index to {target}: {e}")
            print()


def query_migration_examples():
    """Demonstrate query migration scenarios"""
    print("=" * 60)
    print("QUERY MIGRATION EXAMPLES")
    print("=" * 60)

    # Example 1: Analytics query with Vertica-specific functions
    vertica_analytics = """
    SELECT 
        customer_id,
        DATE_TRUNC('month', order_date) as month,
        SUM(amount) as total_amount,
        APPROXIMATE_COUNT_DISTINCT(product_id) as unique_products,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY amount) as median_amount,
        DATEDIFF('day', MIN(order_date), MAX(order_date)) as date_range_days
    FROM orders 
    WHERE order_date >= DATEADD('month', -12, CURRENT_DATE)
    GROUP BY customer_id, DATE_TRUNC('month', order_date)
    HAVING SUM(amount) > 1000
    ORDER BY customer_id, month
    """

    print("Original Vertica Analytics Query:")
    print(vertica_analytics)
    print()

    # Convert to PostgreSQL
    postgres_version = transpile(vertica_analytics, read=Vertica, write="postgres")[0]
    print("PostgreSQL version:")
    print(postgres_version)
    print()

    # Example 2: Window functions with Vertica syntax
    vertica_window = """
    SELECT 
        employee_id,
        department,
        salary,
        ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) as dept_rank,
        LAG(salary, 1) OVER (PARTITION BY department ORDER BY hire_date) as prev_salary,
        FIRST_VALUE(salary) OVER (PARTITION BY department ORDER BY salary DESC 
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as max_dept_salary
    FROM employees
    """

    print("Vertica window function query:")
    print(vertica_window)
    print()

    # Convert to MySQL
    mysql_version = transpile(vertica_window, read=Vertica, write="mysql")[0]
    print("MySQL version:")
    print(mysql_version)
    print()


def batch_migration_processor():
    """Demonstrate batch processing of migration scripts"""
    print("=" * 60)
    print("BATCH MIGRATION PROCESSOR")
    print("=" * 60)

    # Sample migration script with multiple statements
    migration_script = """
    -- Create customers table
    CREATE TABLE customers (
        id INTEGER PRIMARY KEY,
        name VARCHAR(255),
        email VARCHAR(255),
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    -- Create orders table
    CREATE TABLE orders (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER,
        amount DECIMAL(10,2),
        order_date DATE,
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    );
    
    -- Insert sample data
    INSERT INTO customers (id, name, email) VALUES 
    (1, 'John Doe', 'john@example.com'),
    (2, 'Jane Smith', 'jane@example.com');
    
    -- Analytics query
    SELECT 
        c.name,
        COUNT(o.id) as order_count,
        SUM(o.amount) as total_spent,
        DATEDIFF('day', MIN(o.order_date), MAX(o.order_date)) as customer_lifetime_days
    FROM customers c
    LEFT JOIN orders o ON c.id = o.customer_id
    GROUP BY c.id, c.name
    ORDER BY total_spent DESC;
    """

    def parse_migration_script(script: str) -> list[str]:
        """Parse a migration script into individual statements"""
        # Simple statement splitter (in practice, you'd want a more robust parser)
        statements = []
        current_statement = ""

        for line in script.split('\n'):
            line = line.strip()
            if line and not line.startswith('--'):
                current_statement += line + " "
                if line.endswith(';'):
                    statements.append(current_statement.strip())
                    current_statement = ""

        return statements

    def migrate_script(script: str, target_dialect: str) -> dict[str, list[str]]:
        """Migrate an entire script to target dialect"""
        statements = parse_migration_script(script)
        results = {
            'successful': [],
            'failed': [],
            'errors': []
        }

        for j, statement in enumerate(statements):
            try:
                if statement.strip():
                    converted = transpile(statement, read=Vertica, write=target_dialect)[0]
                    results['successful'].append(converted)
            except Exception as e:
                results['failed'].append(statement)
                results['errors'].append(f"Statement {j + 1}: {str(e)}")

        return results

    # Process migration to PostgreSQL
    postgres_results = migrate_script(migration_script, "postgres")

    print("Migration to PostgreSQL:")
    print(f"Successful statements: {len(postgres_results['successful'])}")
    print(f"Failed statements: {len(postgres_results['failed'])}")
    print()

    if postgres_results['successful']:
        print("Converted statements:")
        for i, stmt in enumerate(postgres_results['successful'], 1):
            print(f"{i}. {stmt}")
        print()

    if postgres_results['errors']:
        print("Conversion errors:")
        for error in postgres_results['errors']:
            print(f"  - {error}")
        print()


def data_type_mapping_examples():
    """Demonstrate data type mapping between systems"""
    print("=" * 60)
    print("DATA TYPE MAPPING EXAMPLES")
    print("=" * 60)

    # Define comprehensive data type mappings
    type_mappings = {
        'vertica_to_postgres': {
            'BYTEA': 'BYTEA',
            'TIMESTAMPTZ': 'TIMESTAMPTZ',
            'UUID': 'UUID',
            'JSON': 'JSONB',
            'ARRAY[FLOAT]': 'FLOAT[]',
            'ARRAY[INTEGER]': 'INTEGER[]',
            'LONG VARBINARY': 'BYTEA',
            'LONG VARCHAR': 'TEXT'
        },
        'vertica_to_mysql': {
            'BYTEA': 'LONGBLOB',
            'TIMESTAMPTZ': 'TIMESTAMP',
            'UUID': 'CHAR(36)',
            'JSON': 'JSON',
            'ARRAY[FLOAT]': 'TEXT',  # MySQL doesn't have native arrays
            'ARRAY[INTEGER]': 'TEXT',
            'LONG VARBINARY': 'LONGBLOB',
            'LONG VARCHAR': 'LONGTEXT'
        }
    }

    # Example tables with various data types
    test_tables = [
        """
        CREATE TABLE binary_data (
            id INTEGER,
            data BYTEA,
            metadata JSON
        )
        """,
        """
        CREATE TABLE time_series (
            id INTEGER,
            timestamp_col TIMESTAMPTZ,
            values ARRAY[FLOAT]
        )
        """,
        """
        CREATE TABLE identifiers (
            id INTEGER,
            uuid_col UUID,
            description LONG VARCHAR
        )
        """
    ]

    for table_ddl in test_tables:
        print(f"Original Vertica DDL:")
        print(table_ddl.strip())
        print()

        # Convert to PostgreSQL
        try:
            postgres_ddl = transpile(table_ddl, read=Vertica, write="postgres")[0]
            print(f"PostgreSQL equivalent:")
            print(postgres_ddl)
        except Exception as e:
            print(f"Error converting to PostgreSQL: {e}")

        # Convert to MySQL
        try:
            mysql_ddl = transpile(table_ddl, read=Vertica, write="mysql")[0]
            print(f"MySQL equivalent:")
            print(mysql_ddl)
        except Exception as e:
            print(f"Error converting to MySQL: {e}")

        print("-" * 40)
        print()


def function_migration_examples():
    """Demonstrate function and procedure migration"""
    print("=" * 60)
    print("FUNCTION MIGRATION EXAMPLES")
    print("=" * 60)

    # Example 1: Date/time functions
    vertica_date_queries = [
        "SELECT DATEADD('day', 7, CURRENT_DATE) as next_week",
        "SELECT DATEDIFF('hour', '2023-01-01', '2023-01-02') as hours_diff",
        "SELECT DATE_TRUNC('month', order_date) FROM orders",
        "SELECT TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') FROM events"
    ]

    print("Date/Time Function Conversions:")
    for query in vertica_date_queries:
        print(f"Vertica: {query}")

        # Convert to PostgreSQL
        postgres_query = transpile(query, read=Vertica, write="postgres")[0]
        print(f"PostgreSQL: {postgres_query}")

        # Convert to MySQL
        mysql_query = transpile(query, read=Vertica, write="mysql")[0]
        print(f"MySQL: {mysql_query}")
        print()

    # Example 2: String functions
    vertica_string_queries = [
        "SELECT MD5(password) FROM users",
        "SELECT SHA1(sensitive_data) FROM secure_table",
        "SELECT ILIKE(name, 'John%') FROM customers",
        "SELECT REGEXP_REPLACE(phone, '[^0-9]', '') FROM contacts"
    ]

    print("String Function Conversions:")
    for query in vertica_string_queries:
        print(f"Vertica: {query}")

        try:
            postgres_query = transpile(query, read=Vertica, write="postgres")[0]
            print(f"PostgreSQL: {postgres_query}")
        except Exception as e:
            print(f"PostgreSQL: Error - {e}")

        try:
            mysql_query = transpile(query, read=Vertica, write="mysql")[0]
            print(f"MySQL: {mysql_query}")
        except Exception as e:
            print(f"MySQL: Error - {e}")
        print()


def migration_validation():
    """Demonstrate validation of migrated queries"""
    print("=" * 60)
    print("MIGRATION VALIDATION")
    print("=" * 60)

    def validate_migration(original_sql: str, target_dialect: str) -> dict:
        """Validate that a migration preserves query semantics"""
        result = {
            'original': original_sql,
            'target_dialect': target_dialect,
            'converted': None,
            'valid': False,
            'issues': []
        }

        try:
            # Parse original
            original_ast = parse_one(original_sql, read=Vertica)

            # Convert to target
            converted_sql = transpile(original_sql, read=Vertica, write=target_dialect)[0]
            result['converted'] = converted_sql

            # Parse converted to ensure it's valid
            converted_ast = parse_one(converted_sql, read=target_dialect)

            # Basic validation checks
            if len(original_ast.find_all(exp.Table)) != len(converted_ast.find_all(exp.Table)):
                result['issues'].append("Table count mismatch")

            if len(original_ast.find_all(exp.Column)) != len(converted_ast.find_all(exp.Column)):
                result['issues'].append("Column count mismatch")

            result['valid'] = len(result['issues']) == 0

        except Exception as e:
            result['issues'].append(f"Conversion error: {e}")

        return result

    # Test queries for validation
    test_queries = [
        "SELECT COUNT(*) FROM employees WHERE hire_date > '2023-01-01'",
        "SELECT dept_id, AVG(salary) FROM employees GROUP BY dept_id",
        "SELECT e.name, d.name FROM employees e JOIN departments d ON e.dept_id = d.id"
    ]

    print("Migration Validation Results:")
    for query in test_queries:
        print(f"\nOriginal: {query}")

        for target in ["postgres", "mysql"]:
            validation = validate_migration(query, target)

            if validation['valid']:
                print(f"✓ {target.upper()}: {validation['converted']}")
            else:
                print(f"✗ {target.upper()}: {validation['issues']}")
                if validation['converted']:
                    print(f"  Converted: {validation['converted']}")


def main():
    """Run all migration examples"""
    print("Vertica SQLGlot Dialect - Data Migration Examples")
    print("=" * 60)
    print()

    try:
        ddl_migration_examples()
        query_migration_examples()
        batch_migration_processor()
        data_type_mapping_examples()
        function_migration_examples()
        migration_validation()

        print("All migration examples completed successfully! ✓")

    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
