#!/usr/bin/env python3
"""
Run All Examples - Comprehensive Vertica SQLGlot Dialect Demonstration

This script runs all example files and provides a comprehensive overview
of the Vertica dialect's capabilities.
"""

import sys
import os
import time
import subprocess
from typing import List, Tuple

# Add the parent directory to the path so we can import our dialect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlglot import parse_one, transpile, exp
from sqlglot_vertica.vertica import Vertica


def run_example_script(script_name: str) -> Tuple[bool, str, float]:
    """Run an example script and return success status, output, and execution time"""
    start_time = time.time()
    
    try:
        result = subprocess.run(
            [sys.executable, script_name],
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        execution_time = time.time() - start_time
        success = result.returncode == 0
        output = result.stdout if success else result.stderr
        
        return success, output, execution_time
        
    except subprocess.TimeoutExpired:
        execution_time = time.time() - start_time
        return False, "Script timed out after 30 seconds", execution_time
    except Exception as e:
        execution_time = time.time() - start_time
        return False, f"Error running script: {e}", execution_time


def quick_dialect_validation():
    """Perform quick validation of core dialect functionality"""
    print("🔍 QUICK DIALECT VALIDATION")
    print("=" * 60)
    
    test_cases = [
        # Basic parsing
        ("Basic SELECT", "SELECT name, salary FROM employees WHERE active = true"),
        
        # Vertica functions
        ("Date functions", "SELECT DATEADD('day', 7, hire_date), DATEDIFF('month', start_date, end_date) FROM projects"),
        
        # String functions  
        ("String functions", "SELECT MD5(email), SHA1(password), ILIKE(name, 'John%') FROM users"),
        
        # Window functions
        ("Window functions", "SELECT emp_id, ROW_NUMBER() OVER (PARTITION BY dept_id ORDER BY salary DESC) FROM employees"),
        
        # Complex query
        ("Complex query", """
        WITH dept_stats AS (
            SELECT dept_id, AVG(salary) as avg_salary
            FROM employees
            GROUP BY dept_id
        )
        SELECT e.name, e.salary, ds.avg_salary
        FROM employees e
        JOIN dept_stats ds ON e.dept_id = ds.dept_id
        WHERE e.salary > ds.avg_salary
        """),
        
        # DDL
        ("DDL", "CREATE TABLE test (id INTEGER PRIMARY KEY, data BYTEA, created_at TIMESTAMPTZ)"),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, sql in test_cases:
        try:
            ast = parse_one(sql, read=Vertica)
            generated = ast.sql(dialect=Vertica)
            print(f"✅ {test_name}: PASSED")
            passed += 1
        except Exception as e:
            print(f"❌ {test_name}: FAILED - {e}")
            failed += 1
    
    print(f"\nValidation Results: {passed} passed, {failed} failed")
    print()


def demonstrate_key_features():
    """Demonstrate key features of the dialect"""
    print("🌟 KEY FEATURES DEMONSTRATION")
    print("=" * 60)
    
    # Feature 1: Cross-dialect transpilation
    print("1. Cross-Dialect Transpilation:")
    vertica_sql = "SELECT DATEDIFF('day', start_date, end_date) as duration FROM projects"
    
    targets = ['postgres', 'mysql', 'sqlite']
    for target in targets:
        try:
            converted = transpile(vertica_sql, read=Vertica, write=target)[0]
            print(f"   {target.upper()}: {converted}")
        except Exception as e:
            print(f"   {target.upper()}: Error - {e}")
    print()
    
    # Feature 2: Error handling for unsupported features
    print("2. Error Handling for Unsupported Features:")
    
    unsupported_cases = [
        ("Dollar-quoted strings", "SELECT $$invalid$$ FROM test"),
        ("LATERAL joins", "SELECT * FROM a LEFT JOIN LATERAL (SELECT * FROM b) x ON true"),
        ("COPY FROM LOCAL", "COPY table1 FROM LOCAL '/tmp/data.csv'"),
    ]
    
    for feature_name, sql in unsupported_cases:
        try:
            parse_one(sql, read=Vertica)
            print(f"   ❌ {feature_name}: Should have failed but didn't")
        except Exception as e:
            print(f"   ✅ {feature_name}: Correctly rejected - {type(e).__name__}")
    print()
    
    # Feature 3: Vertica-specific functions
    print("3. Vertica-Specific Functions:")
    vertica_functions = [
        "SELECT APPROXIMATE_COUNT_DISTINCT(user_id) FROM sessions",
        "SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY salary) FROM employees",
        "SELECT TO_CHAR(created_at, 'YYYY-MM-DD') FROM events",
        "SELECT REGEXP_REPLACE(phone, '[^0-9]', '') FROM contacts"
    ]
    
    for sql in vertica_functions:
        try:
            ast = parse_one(sql, read=Vertica)
            print(f"   ✅ {sql}")
        except Exception as e:
            print(f"   ❌ {sql} - Error: {e}")
    print()


def show_performance_summary():
    """Show performance characteristics"""
    print("⚡ PERFORMANCE SUMMARY")
    print("=" * 60)
    
    # Parsing performance test
    test_sql = """
    WITH monthly_sales AS (
        SELECT 
            customer_id,
            DATE_TRUNC('month', order_date) as month,
            SUM(amount) as total
        FROM orders
        WHERE order_date >= DATEADD('year', -1, CURRENT_DATE)
        GROUP BY customer_id, DATE_TRUNC('month', order_date)
    )
    SELECT 
        customer_id,
        month,
        total,
        LAG(total) OVER (PARTITION BY customer_id ORDER BY month) as prev_total
    FROM monthly_sales
    ORDER BY customer_id, month
    """
    
    # Measure parsing time
    iterations = 100
    start_time = time.time()
    
    for _ in range(iterations):
        parse_one(test_sql, read=Vertica)
    
    parse_time = time.time() - start_time
    avg_parse_time = (parse_time / iterations) * 1000  # Convert to milliseconds
    
    print(f"Parse Performance:")
    print(f"  Complex query parsing: {avg_parse_time:.2f}ms average ({iterations} iterations)")
    print(f"  Total time: {parse_time:.3f}s")
    
    # AST complexity
    ast = parse_one(test_sql, read=Vertica)
    tables = len(list(ast.find_all(exp.Table)))
    functions = len(list(ast.find_all(exp.Func)))
    windows = len(list(ast.find_all(exp.Window)))
    
    print(f"\nAST Complexity:")
    print(f"  Tables: {tables}")
    print(f"  Functions: {functions}")
    print(f"  Window functions: {windows}")
    print()


def main():
    """Run all examples and provide comprehensive overview"""
    print("🚀 VERTICA SQLGLOT DIALECT - COMPREHENSIVE DEMONSTRATION")
    print("=" * 80)
    print()
    
    # Quick validation first
    quick_dialect_validation()
    
    # Demonstrate key features
    demonstrate_key_features()
    
    # Show performance summary
    show_performance_summary()
    
    # Run all example scripts
    print("📋 RUNNING ALL EXAMPLE SCRIPTS")
    print("=" * 60)
    
    example_scripts = [
        'basic_usage.py',
        'advanced_transformations.py', 
        'data_migration.py',
        'performance_analysis.py'
    ]
    
    total_start = time.time()
    results = []
    
    for script in example_scripts:
        print(f"Running {script}...")
        success, output, exec_time = run_example_script(script)
        results.append((script, success, exec_time))
        
        if success:
            print(f"  ✅ Completed successfully in {exec_time:.2f}s")
        else:
            print(f"  ❌ Failed after {exec_time:.2f}s")
            print(f"  Error: {output[:200]}...")
        print()
    
    total_time = time.time() - total_start
    
    # Summary
    print("📊 EXECUTION SUMMARY")
    print("=" * 60)
    
    successful = sum(1 for _, success, _ in results if success)
    total_scripts = len(results)
    
    print(f"Scripts executed: {total_scripts}")
    print(f"Successful: {successful}")
    print(f"Failed: {total_scripts - successful}")
    print(f"Total execution time: {total_time:.2f}s")
    print()
    
    print("Individual script results:")
    for script, success, exec_time in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"  {script:<25} {status:<10} ({exec_time:.2f}s)")
    print()
    
    # Final status
    if successful == total_scripts:
        print("🎉 ALL EXAMPLES COMPLETED SUCCESSFULLY!")
        print("The Vertica SQLGlot dialect is working perfectly!")
        return 0
    else:
        print("⚠️  Some examples failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 