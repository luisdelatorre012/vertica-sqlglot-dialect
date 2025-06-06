#!/usr/bin/env python3
"""
Performance Analysis Examples for Vertica SQLGlot Dialect

This file provides examples of how to analyze SQL queries for performance
issues, including:
- Calculating query complexity metrics
- Detecting common performance anti-patterns
- Suggesting optimizations
"""

import sys
import os
import json
import hashlib
from collections import defaultdict
import time

# Add the parent directory to the path so we can import our dialect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlglot import parse_one, exp


def analyze_query_complexity(sql, dialect="vertica"):
    """
    Analyzes a SQL query and returns a set of complexity metrics.
    """
    ast = parse_one(sql, read=dialect)
    if not ast:
        return {"error": "Could not parse SQL"}

    metrics = {
        "join_count": len(list(ast.find_all(exp.Join))),
        "subquery_count": len(list(ast.find_all(exp.Subquery))),
        "function_count": len(list(ast.find_all(exp.Func))),
        "table_count": len(list(ast.find_all(exp.Table))),
        "column_count": len(list(ast.find_all(exp.Column))),
    }
    return metrics


def detect_performance_anti_patterns(sql, dialect="vertica"):
    """
    Detects common performance anti-patterns in a SQL query.
    """
    ast = parse_one(sql, read=dialect)
    if not ast:
        return ["Could not parse SQL"]

    anti_patterns = []
    
    # Anti-pattern: Using SELECT *
    if any(isinstance(s, exp.Star) for s in ast.find_all(exp.Select)):
        anti_patterns.append("Avoid using SELECT *; specify columns explicitly.")

    # Anti-pattern: Function on indexed column
    for where in ast.find_all(exp.Where):
        for func in where.find_all(exp.Func):
            if func.find(exp.Column):
                anti_patterns.append(f"Function `{func.sql()}` on a column in WHERE clause can prevent index usage.")

    return anti_patterns


def suggest_optimizations(sql, dialect="vertica"):
    """
    Suggests potential optimizations for a given SQL query.
    """
    ast = parse_one(sql, read=dialect)
    if not ast:
        return ["Could not parse SQL"]

    suggestions = []
    for where in ast.find_all(exp.Where):
        for eq in where.find_all(exp.EQ):
            if eq.left.find(exp.Column) and eq.right.find(exp.Literal):
                suggestions.append(f"Consider an index on column `{eq.left.sql()}` for faster lookups.")
    
    if "SELECT *" in sql.upper():
        suggestions.append("Specify columns explicitly instead of using SELECT *.")
        
    return suggestions


def complexity_analysis_examples():
    """Demonstrate query complexity analysis."""
    print("=" * 60)
    print("COMPLEXITY ANALYSIS EXAMPLES")
    print("=" * 60)
    
    sql1 = "SELECT id, name FROM users WHERE status = 'active'"
    metrics1 = analyze_query_complexity(sql1)
    print(f"Query: {sql1}")
    print(f"Complexity Metrics: {json.dumps(metrics1, indent=2)}\n")

    sql2 = "SELECT c.name, COUNT(*) as order_count FROM customers c JOIN orders o ON c.id = o.customer_id GROUP BY c.name"
    metrics2 = analyze_query_complexity(sql2)
    print(f"Query: {sql2.strip()}")
    print(f"Complexity Metrics: {json.dumps(metrics2, indent=2)}\n")


def anti_pattern_detection_examples():
    """Demonstrate anti-pattern detection."""
    print("=" * 60)
    print("ANTI-PATTERN DETECTION EXAMPLES")
    print("=" * 60)
    
    sql1 = "SELECT * FROM products"
    patterns1 = detect_performance_anti_patterns(sql1)
    print(f"Query: {sql1}")
    print(f"Detected Anti-patterns: {patterns1}\n")

    sql2 = "SELECT id FROM logs WHERE DATE(event_time) = '2023-01-15'"
    patterns2 = detect_performance_anti_patterns(sql2)
    print(f"Query: {sql2}")
    print(f"Detected Anti-patterns: {patterns2}\n")


def optimization_suggestion_examples():
    """Demonstrate optimization suggestions."""
    print("=" * 60)
    print("OPTIMIZATION SUGGESTION EXAMPLES")
    print("=" * 60)

    sql1 = "SELECT * FROM orders WHERE customer_id = 123"
    suggestions1 = suggest_optimizations(sql1)
    print(f"Query: {sql1}")
    print(f"Suggestions: {suggestions1}\n")

    sql2 = "SELECT user_id, COUNT(*) FROM events WHERE EXTRACT(YEAR FROM event_date) = 2023 GROUP BY user_id"
    suggestions2 = suggest_optimizations(sql2)
    print(f"Query: {sql2}")
    print(f"Suggestions: {suggestions2}\n")


def main():
    """Run all performance analysis examples"""
    print("Vertica SQLGlot Dialect - Performance Analysis Examples")
    print("=" * 60)
    print()

    try:
        complexity_analysis_examples()
        anti_pattern_detection_examples()
        optimization_suggestion_examples()
        
        print("All examples completed successfully! ✓")

    except Exception as e:
        print(f"\nError running examples: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 