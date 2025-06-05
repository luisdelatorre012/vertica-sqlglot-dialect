#!/usr/bin/env python3
"""
Performance Analysis Examples for Vertica SQLGlot Dialect

This file demonstrates performance-related functionality:
- Query complexity analysis
- Performance anti-pattern detection
- Query optimization suggestions
- Index recommendation analysis
- Resource usage estimation
"""

import sys
import os
import time
from dataclasses import dataclass

# Add the parent directory to the path so we can import our dialect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlglot import parse_one, exp
from sqlglot_vertica.vertica import Vertica
from sqlglot.optimizer import optimize


@dataclass
class QueryMetrics:
    """Metrics for query analysis"""
    table_count: int
    join_count: int
    subquery_count: int
    function_count: int
    window_function_count: int
    aggregate_count: int
    complexity_score: int
    estimated_cost: str


def query_complexity_analysis():
    """Analyze query complexity and provide metrics"""
    print("=" * 60)
    print("QUERY COMPLEXITY ANALYSIS")
    print("=" * 60)
    
    def analyze_query_complexity(sql: str) -> QueryMetrics:
        """Analyze a query and return complexity metrics"""
        ast = parse_one(sql, read=Vertica)
        
        # Count various elements
        tables = list(ast.find_all(exp.Table))
        joins = list(ast.find_all(exp.Join))
        subqueries = list(ast.find_all(exp.Select))[1:]  # Exclude main query
        functions = list(ast.find_all(exp.Func))
        windows = list(ast.find_all(exp.Window))
        aggregates = list(ast.find_all(exp.AggFunc))
        
        # Calculate complexity score
        complexity = (
            len(tables) * 1 +
            len(joins) * 2 +
            len(subqueries) * 3 +
            len(functions) * 1 +
            len(windows) * 2 +
            len(aggregates) * 1
        )
        
        # Estimate cost category
        if complexity <= 5:
            cost = "LOW"
        elif complexity <= 15:
            cost = "MEDIUM"
        elif complexity <= 30:
            cost = "HIGH"
        else:
            cost = "VERY HIGH"
        
        return QueryMetrics(
            table_count=len(tables),
            join_count=len(joins),
            subquery_count=len(subqueries),
            function_count=len(functions),
            window_function_count=len(windows),
            aggregate_count=len(aggregates),
            complexity_score=complexity,
            estimated_cost=cost
        )
    
    # Test queries with different complexity levels
    test_queries = [
        # Simple query
        "SELECT name, salary FROM employees WHERE dept_id = 1",
        
        # Medium complexity
        """
        SELECT 
            e.name,
            d.name as dept_name,
            AVG(e.salary) OVER (PARTITION BY e.dept_id) as avg_dept_salary
        FROM employees e
        JOIN departments d ON e.dept_id = d.id
        WHERE e.active = true
        """,
        
        # High complexity
        """
        WITH monthly_metrics AS (
            SELECT 
                emp_id,
                DATE_TRUNC('month', activity_date) as month,
                COUNT(*) as activity_count,
                SUM(hours_worked) as total_hours
            FROM employee_activities
            WHERE activity_date >= DATEADD('year', -1, CURRENT_DATE)
            GROUP BY emp_id, DATE_TRUNC('month', activity_date)
        ),
        performance_ranks AS (
            SELECT 
                emp_id,
                month,
                activity_count,
                total_hours,
                ROW_NUMBER() OVER (PARTITION BY month ORDER BY total_hours DESC) as monthly_rank,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_hours) 
                    OVER (PARTITION BY month) as median_hours
            FROM monthly_metrics
        )
        SELECT 
            e.name,
            e.dept_id,
            pr.month,
            pr.total_hours,
            pr.monthly_rank,
            pr.median_hours,
            CASE 
                WHEN pr.total_hours > pr.median_hours * 1.2 THEN 'High Performer'
                WHEN pr.total_hours < pr.median_hours * 0.8 THEN 'Low Performer'
                ELSE 'Average Performer'
            END as performance_category
        FROM performance_ranks pr
        JOIN employees e ON pr.emp_id = e.id
        WHERE pr.monthly_rank <= 10
        ORDER BY pr.month, pr.monthly_rank
        """
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"Query {i}:")
        print(query.strip()[:100] + "..." if len(query.strip()) > 100 else query.strip())
        print()
        
        metrics = analyze_query_complexity(query)
        print("Complexity Analysis:")
        print(f"  Tables: {metrics.table_count}")
        print(f"  Joins: {metrics.join_count}")
        print(f"  Subqueries: {metrics.subquery_count}")
        print(f"  Functions: {metrics.function_count}")
        print(f"  Window Functions: {metrics.window_function_count}")
        print(f"  Aggregates: {metrics.aggregate_count}")
        print(f"  Complexity Score: {metrics.complexity_score}")
        print(f"  Estimated Cost: {metrics.estimated_cost}")
        print("-" * 40)
        print()


def anti_pattern_detection():
    """Detect common performance anti-patterns"""
    print("=" * 60)
    print("ANTI-PATTERN DETECTION")
    print("=" * 60)
    
    def detect_anti_patterns(sql: str) -> list[str]:
        """Detect common SQL anti-patterns"""
        issues = []
        ast = parse_one(sql, read=Vertica)
        sql_upper = sql.upper()
        
        # 1. SELECT * usage
        for select in ast.find_all(exp.Select):
            for projection in select.expressions:
                if isinstance(projection, exp.Star):
                    issues.append("SELECT * detected - specify only needed columns")
        
        # 2. Missing WHERE clauses on large tables
        for select in ast.find_all(exp.Select):
            if not select.find(exp.Where):
                issues.append("Query without WHERE clause - may scan entire table")
        
        # 3. Functions in WHERE clause on columns
        for where in ast.find_all(exp.Where):
            for func in where.find_all(exp.Func):
                if func.find(exp.Column):
                    issues.append("Function on column in WHERE clause - prevents index usage")
        
        # 4. Subqueries that could be JOINs
        for select in ast.find_all(exp.Select):
            subqueries = list(select.find_all(exp.Subquery))
            if len(subqueries) > 0:
                issues.append("Subqueries detected - consider converting to JOINs")
        
        # 5. DISTINCT without ORDER BY
        if "DISTINCT" in sql_upper and "ORDER BY" not in sql_upper:
            issues.append("DISTINCT without ORDER BY - results may be non-deterministic")
        
        # 6. Large IN clauses
        for in_clause in ast.find_all(exp.In):
            if hasattr(in_clause, 'expressions') and len(in_clause.expressions) > 100:
                issues.append("Large IN clause detected - consider using temporary table")
        
        # 7. LIKE with leading wildcard
        for like in ast.find_all(exp.Like):
            if hasattr(like, 'expression') and str(like.expression).startswith("'%"):
                issues.append("LIKE with leading wildcard - prevents index usage")
        
        # 8. UNION without ALL
        if " UNION " in sql_upper and " UNION ALL " not in sql_upper:
            issues.append("UNION without ALL - may perform unnecessary deduplication")
        
        return issues
    
    # Test queries with various anti-patterns
    test_queries = [
        # Good query
        "SELECT emp_id, name FROM employees WHERE dept_id = 1 AND active = true",
        
        # Multiple anti-patterns
        """
        SELECT * 
        FROM employees e
        WHERE UPPER(e.name) LIKE '%john%'
        AND e.emp_id IN (
            SELECT emp_id FROM employee_activities 
            WHERE activity_date > '2023-01-01'
        )
        """,
        
        # More anti-patterns
        """
        SELECT DISTINCT name, dept_id
        FROM employees
        UNION
        SELECT name, dept_id
        FROM contractors
        """,
        
        # Table scan
        "SELECT COUNT(*) FROM large_transaction_table"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"Query {i}:")
        print(query.strip())
        print()
        
        issues = detect_anti_patterns(query)
        if issues:
            print("⚠️  Anti-patterns detected:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("✅ No anti-patterns detected")
        
        print("-" * 40)
        print()


def optimization_suggestions():
    """Provide optimization suggestions for queries"""
    print("=" * 60)
    print("OPTIMIZATION SUGGESTIONS")
    print("=" * 60)
    
    def suggest_optimizations(query: str) -> str:
        suggestions = []
        ast = parse_one(query, read=Vertica)

        # Analyze and suggest optimizations
        joins = list(ast.find_all(exp.Join))
        windows = list(ast.find_all(exp.Window))

        # 1. Index suggestions
        for col in ast.find_all(exp.Column):
            if col.table:
                suggestions.append(f"Consider index on {col.table}.{col.name}")
        
        # 2. Join optimization
        if len(joins) > 3:
            suggestions.append("Multiple joins detected - verify join order optimization")
        
        # 3. Window function optimization
        if len(windows) > 1:
            # Check for similar partition clauses
            partitions = []
            for window in windows:
                if hasattr(window, 'partition_by'):
                    partitions.append(str(window.partition_by))
            if len(set(partitions)) < len(partitions):
                suggestions.append("Similar window partitions - consider combining calculations")
        
        # 4. Projection optimization
        for select in ast.find_all(exp.Select):
            projections = len(select.expressions)
            if projections > 20:
                suggestions.append("Large projection list - consider if all columns are needed")
        
        # 5. Predicate pushdown opportunities
        for select in ast.find_all(exp.Select):
            if select.find(exp.From) and select.find(exp.From).find(exp.Subquery):
                suggestions.append("Subquery in FROM - check if predicates can be pushed down")
        
        return suggestions
    
    def show_optimized_version(sql: str) -> str:
        """Show an optimized version using SQLGlot optimizer"""
        try:
            ast = parse_one(sql, read=Vertica)
            # Try to run basic optimization - if it fails, just return the original
            try:
                optimized = optimize(ast)
                return optimized.sql(dialect=Vertica, pretty=True)
            except Exception:
                # If optimization fails, just return the prettified original
                return ast.sql(dialect=Vertica, pretty=True)
        except Exception as e:
            return f"Failed to parse query: {e}"
    
    # Test queries for optimization
    test_queries = [
        """
        SELECT 
            e.emp_id,
            e.name,
            d.name as dept_name,
            (SELECT COUNT(*) FROM projects WHERE lead_id = e.emp_id) as project_count
        FROM employees e
        JOIN departments d ON e.dept_id = d.id
        WHERE e.salary > 50000
        """,
        
        """
        SELECT 
            customer_id,
            order_date,
            SUM(amount) OVER (PARTITION BY customer_id ORDER BY order_date) as running_total,
            AVG(amount) OVER (PARTITION BY customer_id ORDER BY order_date) as running_avg,
            COUNT(*) OVER (PARTITION BY customer_id ORDER BY order_date) as running_count
        FROM orders
        WHERE order_date >= '2023-01-01'
        """
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"Query {i}:")
        print(query.strip())
        print()
        
        suggestions = suggest_optimizations(query)
        if suggestions:
            print("💡 Optimization suggestions:")
            for suggestion in suggestions:
                print(f"  - {suggestion}")
        else:
            print("✅ Query appears well-optimized")
        
        print("\n🔄 SQLGlot optimized version:")
        try:
            optimized = show_optimized_version(query)
            print(optimized)
        except Exception as e:
            print(f"Could not generate optimized version: {e}")
        
        print("-" * 40)
        print()


def index_recommendation_analysis():
    """Analyze queries and recommend indexes"""
    print("=" * 60)
    print("INDEX RECOMMENDATION ANALYSIS")
    print("=" * 60)
    
    def analyze_index_needs(queries: list[str]) -> dict[str, set[str]]:
        """Analyze multiple queries and recommend indexes"""
        index_recommendations = {}
        
        for sql in queries:
            ast = parse_one(sql, read=Vertica)
            
            # Find columns used in WHERE clauses
            for where in ast.find_all(exp.Where):
                for col in where.find_all(exp.Column):
                    if hasattr(col, 'table') and col.table:
                        table_name = str(col.table) if col.table else None
                        column_name = str(col.name) if hasattr(col, 'name') and col.name else None
                        
                        if table_name and column_name:
                            if table_name not in index_recommendations:
                                index_recommendations[table_name] = set()
                            index_recommendations[table_name].add(column_name)
            
            # Find columns used in JOIN conditions
            for join in ast.find_all(exp.Join):
                if hasattr(join, 'on') and join.on:
                    for col in join.on.find_all(exp.Column):
                        if hasattr(col, 'table') and col.table:
                            table_name = str(col.table) if col.table else None
                            column_name = str(col.name) if hasattr(col, 'name') and col.name else None
                            
                            if table_name and column_name:
                                if table_name not in index_recommendations:
                                    index_recommendations[table_name] = set()
                                index_recommendations[table_name].add(column_name)
            
            # Find columns used in ORDER BY
            for order in ast.find_all(exp.Order):
                for col in order.find_all(exp.Column):
                    if hasattr(col, 'table') and col.table:
                        table_name = str(col.table) if col.table else None
                        column_name = str(col.name) if hasattr(col, 'name') and col.name else None
                        
                        if table_name and column_name:
                            if table_name not in index_recommendations:
                                index_recommendations[table_name] = set()
                            index_recommendations[table_name].add(column_name)
        
        return index_recommendations
    
    # Sample workload of queries
    workload_queries = [
        "SELECT * FROM employees WHERE dept_id = 1 AND active = true",
        "SELECT * FROM employees WHERE hire_date > '2023-01-01'",
        "SELECT e.name, d.name FROM employees e JOIN departments d ON e.dept_id = d.id",
        "SELECT * FROM orders WHERE customer_id = 123 ORDER BY order_date DESC",
        "SELECT * FROM orders WHERE order_date BETWEEN '2023-01-01' AND '2023-12-31'",
        "SELECT COUNT(*) FROM employee_activities WHERE emp_id = 456 AND activity_date > '2023-06-01'"
    ]
    
    print("Analyzing workload of queries...")
    print(f"Total queries: {len(workload_queries)}")
    print()
    
    recommendations = analyze_index_needs(workload_queries)
    
    print("📊 Index Recommendations:")
    for table, columns in recommendations.items():
        print(f"\nTable: {table}")
        print("Recommended indexes:")
        
        # Single column indexes
        for column in columns:
            print(f"  CREATE INDEX idx_{table}_{column} ON {table} ({column});")
        
        # Composite index suggestions
        if len(columns) > 1:
            sorted_columns = sorted(columns)
            print("  -- Consider composite index:")
            print(f"  CREATE INDEX idx_{table}_composite ON {table} ({', '.join(sorted_columns)});")
    
    print()


def performance_benchmarking():
    """Demonstrate performance benchmarking of different query approaches"""
    print("=" * 60)
    print("PERFORMANCE BENCHMARKING")
    print("=" * 60)
    
    def benchmark_query_variants(query_variants: list[tuple[str, str]]) -> None:
        """Benchmark different approaches to the same query"""
        iterations = 10
        
        for name, query in query_variants:
            print(f"Approach: {name}")
            print(f"Query: {query.strip()}")
            
            # Analyze complexity
            ast = parse_one(query, read=Vertica)
            
            # Count operations
            joins = len(list(ast.find_all(exp.Join)))
            subqueries = len(list(ast.find_all(exp.Select))) - 1
            functions = len(list(ast.find_all(exp.Func)))
            
            print("Analysis:")
            print(f"  Joins: {joins}")
            print(f"  Subqueries: {subqueries}")
            print(f"  Functions: {functions}")
            
            # Simple parsing benchmark
            start_time = time.time()
            for _ in range(iterations):
                parse_one(query, read=Vertica)
            parse_time = time.time() - start_time
            
            print(f"  Parse time (100 iterations): {parse_time:.4f}s")
            print("-" * 30)
    
    # Compare different approaches to the same problem
    print("Comparing approaches: Finding top customers by revenue")
    
    customer_revenue_variants = [
        ("Subquery Approach", """
        SELECT customer_id, name
        FROM customers 
        WHERE customer_id IN (
            SELECT customer_id 
            FROM orders 
            GROUP BY customer_id 
            HAVING SUM(amount) > 10000
        )
        """),
        
        ("JOIN Approach", """
        SELECT DISTINCT c.customer_id, c.name
        FROM customers c
        JOIN (
            SELECT customer_id
            FROM orders
            GROUP BY customer_id
            HAVING SUM(amount) > 10000
        ) high_value ON c.customer_id = high_value.customer_id
        """),
        
        ("Window Function Approach", """
        WITH customer_totals AS (
            SELECT 
                c.customer_id,
                c.name,
                SUM(o.amount) OVER (PARTITION BY c.customer_id) as total_revenue
            FROM customers c
            LEFT JOIN orders o ON c.customer_id = o.customer_id
        )
        SELECT DISTINCT customer_id, name
        FROM customer_totals
        WHERE total_revenue > 10000
        """)
    ]
    
    benchmark_query_variants(customer_revenue_variants)
    
    print("\nComparing approaches: Running totals calculation")
    
    running_totals_variants = [
        ("Correlated Subquery", """
        SELECT 
            order_id,
            order_date,
            amount,
            (SELECT SUM(amount) 
             FROM orders o2 
             WHERE o2.customer_id = o1.customer_id 
             AND o2.order_date <= o1.order_date) as running_total
        FROM orders o1
        ORDER BY customer_id, order_date
        """),
        
        ("Window Function", """
        SELECT 
            order_id,
            order_date,
            amount,
            SUM(amount) OVER (
                PARTITION BY customer_id 
                ORDER BY order_date 
                ROWS UNBOUNDED PRECEDING
            ) as running_total
        FROM orders
        ORDER BY customer_id, order_date
        """)
    ]
    
    benchmark_query_variants(running_totals_variants)


def main():
    """Run all performance analysis examples"""
    print("Vertica SQLGlot Dialect - Performance Analysis Examples")
    print("=" * 60)
    print()
    
    try:
        print("Running query complexity analysis...")
        query_complexity_analysis()
        print("✓ Query complexity analysis completed\n")
        
        print("Running anti-pattern detection...")
        try:
            anti_pattern_detection()
            print("✓ Anti-pattern detection completed\n")
        except Exception as e:
            print(f"Anti-pattern detection failed: {e}")
            import traceback
            traceback.print_exc()
        
        print("Running optimization suggestions...")
        optimization_suggestions()
        print("✓ Optimization suggestions completed\n")
        
        print("Running index recommendation analysis...")
        try:
            index_recommendation_analysis()
            print("✓ Index recommendation analysis completed\n")
        except Exception as e:
            print(f"Index recommendation analysis failed: {e}")
            import traceback
            traceback.print_exc()
        
        print("Running performance benchmarking...")
        try:
            performance_benchmarking()
            print("✓ Performance benchmarking completed\n")
        except Exception as e:
            print(f"Performance benchmarking failed: {e}")
            import traceback
            traceback.print_exc()
        
        print("All performance analysis examples completed successfully! ✓")
        
    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 