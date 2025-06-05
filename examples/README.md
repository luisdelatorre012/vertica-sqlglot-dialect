# Vertica SQLGlot Dialect Examples

This directory contains comprehensive examples demonstrating how to use the Vertica SQLGlot dialect for various real-world scenarios.

## 🚀 Quick Start

Make sure you have the Vertica dialect installed and available in your Python path, then run any example:

```bash
python examples/basic_usage.py
python examples/advanced_transformations.py
python examples/data_migration.py
python examples/performance_analysis.py
```

## 📁 Example Files

### 1. `basic_usage.py` - Fundamental Operations
**What it demonstrates:**
- Basic SQL parsing with Vertica-specific syntax
- Transpiling between different database dialects
- AST inspection and manipulation
- Error handling for unsupported features

**Key Features:**
- Parse Vertica functions (DATEADD, MD5, ILIKE, etc.)
- Convert queries to PostgreSQL/MySQL
- Extract tables, columns, and functions from AST
- Handle dollar-quoted strings and LATERAL join errors

### 2. `advanced_transformations.py` - AST Manipulation
**What it demonstrates:**
- Advanced AST transformations and rewrites
- Query optimization using SQLGlot's optimizer
- Schema extraction and analysis
- Custom transformation patterns

**Key Features:**
- Replace function calls (MD5 → SHA1)
- Add table aliases automatically
- Convert CASE statements to COALESCE
- Schema analysis with lineage tracking
- Cross-dialect compatibility testing

### 3. `data_migration.py` - Database Migration
**What it demonstrates:**
- Converting DDL statements between databases
- Migrating complex queries with Vertica-specific functions
- Handling data type conversions
- Batch processing of migration scripts

**Key Features:**
- DDL migration (CREATE TABLE, INDEX)
- Function migration (date/time, string, hash functions)
- Data type mapping between systems
- Migration validation and error handling
- Batch script processing

### 4. `performance_analysis.py` - Query Optimization
**What it demonstrates:**
- Query complexity analysis and metrics
- Performance anti-pattern detection
- Optimization suggestions
- Index recommendation analysis
- Performance benchmarking

**Key Features:**
- Complexity scoring and cost estimation
- Anti-pattern detection (SELECT *, missing indexes, etc.)
- Automated optimization suggestions
- Index recommendations from query workloads
- Performance comparison of different approaches

## 🔧 Common Use Cases

### Database Migration
```python
from sqlglot import transpile
from sqlglot_vertica.vertica import Vertica

# Convert Vertica query to PostgreSQL
vertica_sql = "SELECT DATEDIFF('day', hire_date, CURRENT_DATE) FROM employees"
postgres_sql = transpile(vertica_sql, read=Vertica, write="postgres")[0]
```

### Query Analysis
```python
from sqlglot import parse_one
from sqlglot_vertica.vertica import Vertica

# Parse and analyze Vertica query
ast = parse_one("SELECT MD5(email) FROM users WHERE active = true", read=Vertica)
tables = [table.name for table in ast.find_all(ast.Table)]
functions = [func.sql() for func in ast.find_all(ast.Function)]
```

### Error Handling
```python
from sqlglot import parse_one
from sqlglot_vertica.vertica import Vertica
from sqlglot.errors import ParseError, UnsupportedError

try:
    # This will raise ParseError - dollar-quoted strings not supported
    parse_one("SELECT $$invalid syntax$$", read=Vertica)
except ParseError as e:
    print(f"Parse error: {e}")
```

## 📊 Performance Metrics

The examples include performance analysis tools that can help you:

- **Analyze Query Complexity**: Get metrics on joins, subqueries, functions
- **Detect Anti-patterns**: Find common performance issues
- **Suggest Optimizations**: Get recommendations for query improvements
- **Recommend Indexes**: Analyze workloads and suggest optimal indexes
- **Benchmark Approaches**: Compare different query strategies

## 🛠️ Customization

Each example is designed to be modular and extensible. You can:

- Add your own transformation functions
- Extend the anti-pattern detection rules
- Customize the complexity scoring algorithm
- Add support for additional target dialects
- Implement custom optimization rules

## 🔍 Error Handling

The Vertica dialect includes proper error handling for unsupported features:

- **Dollar-quoted strings** (`$$text$$`) - raises ParseError
- **LATERAL joins** - raises ParseError  
- **COPY FROM LOCAL** - raises UnsupportedError
- **UNLOAD statements** - raises UnsupportedError

## 📈 Integration Examples

These examples can be integrated into larger systems for:

- **ETL Pipelines**: Automated query migration between systems
- **Code Analysis**: Static analysis of SQL codebases
- **Performance Monitoring**: Automated detection of problematic queries
- **Documentation Generation**: Automatic schema and query documentation
- **Testing Frameworks**: Validation of SQL migrations

## 🤝 Contributing

Feel free to extend these examples with additional use cases, optimization rules, or target dialects. The modular design makes it easy to add new functionality while maintaining backward compatibility. 