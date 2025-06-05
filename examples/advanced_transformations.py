#!/usr/bin/env python3
"""
Advanced Transformations for Vertica SQLGlot Dialect

This file demonstrates advanced SQLGlot functionality:
- AST transformations and rewrites
- Query optimization patterns
- Schema extraction and analysis
- Custom transformations for Vertica-specific patterns
"""

import os
import sys
from typing import Dict, List

# Add the parent directory to the path so we can import our dialect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlglot import parse_one, transpile, exp
from sqlglot_vertica.vertica import Vertica
from sqlglot.optimizer import optimize


def query_optimization_examples():
    """Demonstrate query optimization with SQLGlot"""
    print("=" * 60)
    print("QUERY OPTIMIZATION EXAMPLES")
    print("=" * 60)
    
    # Example 1: Predicate pushdown
    sql = """
    SELECT e.name, d.name as dept_name
    FROM (
        SELECT * FROM employees WHERE active = true
    ) e
    JOIN departments d ON e.dept_id = d.id
    WHERE e.salary > 50000
    """
    
    ast = parse_one(sql, read=Vertica)
    optimized = optimize(ast, dialect=Vertica)
    
    print("Original query:")
    print(ast.sql(dialect=Vertica, pretty=True))
    print("\nOptimized query (predicate pushdown):")
    print(optimized.sql(dialect=Vertica, pretty=True))
    print()
    
    # Example 2: Subquery elimination
    sql = """
    SELECT emp_id, name
    FROM employees
    WHERE dept_id IN (
        SELECT id FROM departments WHERE budget > 100000
    )
    """
    
    ast = parse_one(sql, read=Vertica)
    optimized = optimize(ast, dialect=Vertica)
    
    print("Original query with subquery:")
    print(ast.sql(dialect=Vertica, pretty=True))
    print("\nOptimized query (subquery to join):")
    print(optimized.sql(dialect=Vertica, pretty=True))
    print()


def ast_transformation_examples():
    """Demonstrate custom AST transformations"""
    print("=" * 60)
    print("AST TRANSFORMATION EXAMPLES")
    print("=" * 60)
    
    # Example 1: Replace function calls
    def replace_md5_with_sha1(node):
        """Transform MD5 calls to SHA1 calls"""
        if isinstance(node, exp.Anonymous) and node.this == "MD5":
            return exp.Anonymous(this="SHA1", expressions=node.expressions)
        return node
    
    sql = "SELECT MD5(email), MD5(password) FROM users"
    ast = parse_one(sql, read=Vertica)
    
    print(f"Original: {sql}")
    
    # Apply transformation
    transformed = ast.transform(replace_md5_with_sha1)
    print(f"Transformed: {transformed.sql(dialect=Vertica)}")
    print()
    
    # Example 2: Add table aliases
    def add_table_aliases(node):
        """Add aliases to tables that don't have them"""
        if isinstance(node, exp.Table) and not node.alias:
            table_name = node.name.lower()
            alias_name = table_name[0] if len(table_name) > 0 else "t"
            node.set("alias", exp.TableAlias(this=exp.Identifier(this=alias_name)))
        return node
    
    sql = "SELECT name FROM employees JOIN departments ON employees.dept_id = departments.id"
    ast = parse_one(sql, read=Vertica)
    
    print(f"Original: {sql}")
    
    transformed = ast.transform(add_table_aliases)
    print(f"With aliases: {transformed.sql(dialect=Vertica)}")
    print()
    
    # Example 3: Convert CASE to COALESCE where possible
    def case_to_coalesce(node):
        """Convert simple NULL-checking CASE to COALESCE"""
        if (isinstance(node, exp.Case) and 
            node.args.get("ifs") and 
            len(node.args["ifs"]) == 1 and 
            isinstance(node.args["ifs"][0].this, exp.Is) and
            isinstance(node.args["ifs"][0].this.expression, exp.Null)):
            
            # CASE WHEN col IS NULL THEN default ELSE col END -> COALESCE(col, default)
            column = node.args["ifs"][0].this.this
            default_value = node.args["ifs"][0].args.get("true")
            return exp.Coalesce(expressions=[column, default_value])
        return node
    
    sql = "SELECT CASE WHEN name IS NULL THEN 'Unknown' ELSE name END FROM employees"
    ast = parse_one(sql, read=Vertica)
    
    print(f"Original: {sql}")
    
    transformed = ast.transform(case_to_coalesce)
    print(f"Simplified: {transformed.sql(dialect=Vertica)}")
    print()


def schema_analysis_examples():
    """Demonstrate schema extraction and analysis"""
    print("=" * 60)
    print("SCHEMA ANALYSIS EXAMPLES")
    print("=" * 60)
    
    # Example query with multiple tables and complex relationships
    sql = """
    WITH monthly_sales AS (
        SELECT 
            DATE_TRUNC('month', o.order_date) as month,
            p.category,
            SUM(oi.quantity * oi.price) as revenue
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        WHERE o.order_date >= '2023-01-01'
        GROUP BY 1, 2
    )
    SELECT 
        ms.month,
        ms.category,
        ms.revenue,
        LAG(ms.revenue) OVER (PARTITION BY ms.category ORDER BY ms.month) as prev_revenue,
        ROUND((ms.revenue - LAG(ms.revenue) OVER (PARTITION BY ms.category ORDER BY ms.month)) / 
              LAG(ms.revenue) OVER (PARTITION BY ms.category ORDER BY ms.month) * 100, 2) as growth_pct
    FROM monthly_sales ms
    ORDER BY ms.category, ms.month
    """
    
    ast = parse_one(sql, read=Vertica)
    
    # Extract schema information
    def analyze_query_schema(ast) -> Dict:
        """Extract comprehensive schema information from query"""
        schema_info = {
            'tables': set(),
            'columns': set(),
            'functions': [],
            'window_functions': [],
            'joins': [],
            'ctes': [],
            'aggregations': []
        }
        
        # Find all tables
        for table in ast.find_all(exp.Table):
            schema_info['tables'].add(table.name)
        
        # Find all columns
        for col in ast.find_all(exp.Column):
            if col.table:
                schema_info['columns'].add(f"{col.table}.{col.name}")
            else:
                schema_info['columns'].add(col.name)
        
        # Find functions
        for func in ast.find_all(exp.Func):
            schema_info['functions'].append(func.sql())
        
        # Find window functions
        for window in ast.find_all(exp.Window):
            schema_info['window_functions'].append(window.sql())
        
        # Find joins
        for join in ast.find_all(exp.Join):
            join_type = join.kind or "INNER"
            schema_info['joins'].append(f"{join_type} JOIN")
        
        # Find CTEs
        for cte in ast.find_all(exp.CTE):
            schema_info['ctes'].append(cte.alias)
        
        # Find aggregations
        for agg in ast.find_all(exp.AggFunc):
            schema_info['aggregations'].append(agg.sql())
        
        return schema_info
    
    schema = analyze_query_schema(ast)
    
    print("Schema Analysis Results:")
    print(f"Tables: {sorted(schema['tables'])}")
    print(f"Columns: {sorted(schema['columns'])}")
    print(f"Functions: {schema['functions']}")
    print(f"Window Functions: {schema['window_functions']}")
    print(f"Joins: {schema['joins']}")
    print(f"CTEs: {schema['ctes']}")
    print(f"Aggregations: {schema['aggregations']}")
    print()


def vertica_specific_transformations():
    """Demonstrate Vertica-specific transformation patterns"""
    print("=" * 60)
    print("VERTICA-SPECIFIC TRANSFORMATIONS")
    print("=" * 60)
    
    # Example 1: Convert PostgreSQL array syntax to Vertica-compatible syntax
    def postgres_arrays_to_vertica(node):
        """Convert PostgreSQL array literals to Vertica ARRAY constructor"""
        if isinstance(node, exp.Array):
            # Convert ARRAY[1,2,3] to ARRAY[1,2,3] (keep same format for Vertica)
            return node
        return node
    
    # Example 2: Optimize Vertica analytic functions
    sql = """
    SELECT 
        emp_id,
        salary,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY salary) OVER (PARTITION BY dept_id) as median_salary,
        APPROXIMATE_COUNT_DISTINCT(manager_id) OVER (PARTITION BY dept_id) as unique_managers
    FROM employees
    """
    
    ast = parse_one(sql, read=Vertica)
    print("Vertica analytic query:")
    print(ast.sql(dialect=Vertica, pretty=True))
    print()
    
    # Example 3: Convert to other dialects and back
    print("Cross-dialect compatibility test:")
    
    # Start with Vertica
    vertica_sql = "SELECT DATEDIFF('day', hire_date, CURRENT_DATE) as tenure_days FROM employees"
    print(f"Vertica: {vertica_sql}")
    
    # Convert to PostgreSQL
    postgres_sql = transpile(vertica_sql, read=Vertica, write="postgres")[0]
    print(f"PostgreSQL: {postgres_sql}")
    
    # Convert back to Vertica (round trip test)
    back_to_vertica = transpile(postgres_sql, read="postgres", write=Vertica)[0]
    print(f"Back to Vertica: {back_to_vertica}")
    print()


def data_lineage_tracking():
    """Demonstrate data lineage tracking through transformations"""
    print("=" * 60)
    print("DATA LINEAGE TRACKING")
    print("=" * 60)
    
    sql = """
    WITH customer_metrics AS (
        SELECT 
            c.customer_id,
            c.name,
            COUNT(o.id) as order_count,
            SUM(o.total_amount) as total_spent,
            AVG(o.total_amount) as avg_order_value
        FROM customers c
        LEFT JOIN orders o ON c.id = o.customer_id
        WHERE c.active = true
        GROUP BY c.customer_id, c.name
    ),
    customer_segments AS (
        SELECT 
            *,
            CASE 
                WHEN total_spent > 1000 THEN 'High Value'
                WHEN total_spent > 500 THEN 'Medium Value'
                ELSE 'Low Value'
            END as segment
        FROM customer_metrics
    )
    SELECT 
        segment,
        COUNT(*) as customer_count,
        AVG(total_spent) as avg_spent_per_segment
    FROM customer_segments
    GROUP BY segment
    ORDER BY avg_spent_per_segment DESC
    """
    
    ast = parse_one(sql, read=Vertica)
    
    # Track data flow through CTEs
    def trace_column_lineage(ast) -> Dict[str, List[str]]:
        """Trace where each column in the final SELECT comes from"""
        lineage = {}
        
        # This is a simplified lineage tracker
        # In practice, you'd want a more sophisticated implementation
        for select in ast.find_all(exp.Select):
            for projection in select.expressions:
                if isinstance(projection, exp.Alias):
                    alias_name = projection.alias
                    lineage[alias_name] = [projection.this.sql()]
                elif hasattr(projection, 'name'):
                    lineage[projection.name] = [projection.sql()]
        
        return lineage
    
    lineage = trace_column_lineage(ast)
    print("Column Lineage:")
    for column, sources in lineage.items():
        print(f"  {column} ← {', '.join(sources)}")
    print()


def main():
    """Run all advanced examples"""
    print("Vertica SQLGlot Dialect - Advanced Transformations")
    print("=" * 60)
    print()
    
    try:
        query_optimization_examples()
        ast_transformation_examples() 
        schema_analysis_examples()
        vertica_specific_transformations()
        data_lineage_tracking()
        
        print("All advanced examples completed successfully! ✓")
        
    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 