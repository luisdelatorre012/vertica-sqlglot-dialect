# SQLGlot Vertica Dialect

A comprehensive Vertica dialect implementation for [SQLGlot](https://github.com/tobymao/sqlglot), a Python SQL parser and transpiler.

## Features

This Vertica dialect provides full-featured support for Vertica SQL syntax, including:

### Core Functionality
- Complete SQL parsing and generation
- Vertica-specific data types (TIMESTAMPTZ, BINARY, etc.)
- Identifier quoting with double quotes
- Heredoc string support

### Date and Time Functions
- `DATEADD(unit, interval, timestamp)` - Add intervals to dates/timestamps
- `DATEDIFF(unit, start_date, end_date)` - Calculate date differences
- `DATE_TRUNC(unit, timestamp)` - Truncate timestamps to specified unit
- `TO_CHAR(timestamp, format)` - Format timestamps as strings
- `TO_DATE(string, format)` - Parse strings as dates
- `TO_TIMESTAMP(string, format)` - Parse strings as timestamps
- `CURRENT_DATE`, `CURRENT_TIME`, `CURRENT_TIMESTAMP`, `NOW()`

### String Functions
- `ILIKE` / `NOT ILIKE` - Case-insensitive pattern matching
- `LIKE` / `NOT LIKE` - Case-sensitive pattern matching
- `SUBSTRING(string, start, length)` - Extract substrings
- `TRIM()` - Remove whitespace
- Standard string functions (`LENGTH`, `UPPER`, `LOWER`, etc.)

### Mathematical Functions
- `RANDOM()` - Generate random numbers
- Standard math functions (`ABS`, `CEIL`, `FLOOR`, `ROUND`, `SQRT`, `POWER`)

### Hash Functions
- `MD5(string)` - MD5 hash
- `SHA1(string)` - SHA1 hash

### Array Support
- `ARRAY[...]` syntax for array literals
- Array operations and functions

### Window Functions
- Complete support for window functions
- `ROW_NUMBER()`, `RANK()`, `LAG()`, `LEAD()`, etc.
- `OVER` clauses with `PARTITION BY` and `ORDER BY`

### Advanced Features
- Common Table Expressions (CTEs)
- Subqueries and EXISTS clauses
- All JOIN types (INNER, LEFT, RIGHT, FULL OUTER, CROSS)
- Aggregate functions with GROUP BY and HAVING
- CASE WHEN expressions
- Complex data types and constraints

## Installation

```bash
pip install sqlglot-vertica
```

For development:
```bash
pip install sqlglot-vertica[dev]
```

## Usage

### Basic Usage

```python
from sqlglot import transpile
from sqlglot_vertica.vertica import Vertica

# Parse and generate Vertica SQL
sql = "SELECT DATEADD(DAY, 1, CURRENT_DATE)"
parsed = Vertica.parse(sql)[0]
generated = Vertica().generate(parsed)
print(generated)  # SELECT DATEADD(DAY, 1, CURRENT_DATE)

# Transpile from other dialects to Vertica
postgres_sql = "SELECT NOW()"
vertica_sql = transpile(postgres_sql, read='postgres', write='vertica')[0]
print(vertica_sql)  # SELECT CURRENT_TIMESTAMP
```

### Advanced Examples

```python
# Complex query with CTEs and window functions
complex_query = """
WITH sales_data AS (
    SELECT 
        region,
        DATE_TRUNC(MONTH, sale_date) AS month,
        SUM(amount) AS total_sales,
        ROW_NUMBER() OVER (PARTITION BY region ORDER BY SUM(amount) DESC) AS rank
    FROM sales
    WHERE sale_date >= CURRENT_DATE - INTERVAL '1' YEAR
    GROUP BY region, DATE_TRUNC(MONTH, sale_date)
)
SELECT 
    region,
    month,
    total_sales,
    CASE 
        WHEN rank = 1 THEN 'Top Month'
        ELSE 'Other'
    END AS category
FROM sales_data
WHERE rank <= 5
ORDER BY region, total_sales DESC
"""

parsed = Vertica.parse(complex_query)[0]
print(parsed)
```

### Vertica-Specific Features

```python
# Date functions
sql = "SELECT DATEDIFF(DAY, '2023-01-01', '2023-12-31')"
result = Vertica().generate(Vertica.parse(sql)[0])

# Array operations
sql = "SELECT ARRAY[1, 2, 3, 4, 5]"
result = Vertica().generate(Vertica.parse(sql)[0])

# Case-insensitive matching
sql = "SELECT * FROM users WHERE name ILIKE '%john%'"
result = Vertica().generate(Vertica.parse(sql)[0])

# Timestamp with timezone
sql = "CREATE TABLE events (id INTEGER, created_at TIMESTAMPTZ)"
result = Vertica().generate(Vertica.parse(sql)[0])
```

## Development

### Setup Development Environment

```bash
git clone https://github.com/luisdelatorre/sqlglot-vertica.git
cd sqlglot-vertica
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .[dev]
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=sqlglot_vertica

# Run specific test file
pytest tests/test_vertica.py

# Run specific test method
pytest tests/test_vertica.py::TestVertica::test_vertica_date_functions
```

### Code Quality

```bash
# Format code
black sqlglot_vertica tests

# Sort imports
isort sqlglot_vertica tests

# Type checking
mypy sqlglot_vertica
```

## Testing

The dialect includes comprehensive tests covering:

- Basic SQL operations (SELECT, INSERT, UPDATE, DELETE)
- All supported data types
- Date and time functions
- String and mathematical functions
- Window functions and aggregations
- JOIN operations
- Subqueries and CTEs
- Complex query patterns
- Transpilation from other dialects
- Edge cases and error conditions

The test suite follows the same patterns as other SQLGlot dialect tests, ensuring consistency and reliability.

## Compatibility

- **Python**: 3.8+
- **SQLGlot**: 26.0.0+
- **Vertica**: Compatible with Vertica SQL syntax

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## 📁 Examples

This package includes comprehensive examples demonstrating various use cases. See the `examples/` directory for detailed demonstrations.

### 🚀 Quick Start Examples
```bash
# Run basic usage examples
python examples/basic_usage.py

# Run advanced transformation examples  
python examples/advanced_transformations.py

# Run data migration examples
python examples/data_migration.py

# Run performance analysis examples
python examples/performance_analysis.py

# Run comprehensive demonstration
python examples/run_all_examples.py
```

### 📋 Example Categories

1. **`examples/basic_usage.py`** - Fundamental operations
   - Basic SQL parsing with Vertica syntax
   - Cross-dialect transpilation
   - AST inspection and manipulation
   - Error handling for unsupported features

2. **`examples/advanced_transformations.py`** - AST manipulation
   - Custom query transformations
   - Query optimization using SQLGlot
   - Schema analysis and lineage tracking
   - Advanced AST rewriting patterns

3. **`examples/data_migration.py`** - Database migration
   - DDL conversion between databases
   - Function migration (date/time, string, hash)
   - Data type mapping
   - Batch script processing and validation

4. **`examples/performance_analysis.py`** - Query optimization
   - Query complexity analysis
   - Anti-pattern detection
   - Index recommendation
   - Performance benchmarking

### Common Use Cases

```python
# Database Migration
from sqlglot import transpile
from sqlglot_vertica.vertica import Vertica

vertica_sql = "SELECT DATEDIFF('day', hire_date, CURRENT_DATE) FROM employees"
postgres_sql = transpile(vertica_sql, read=Vertica, write="postgres")[0]

# Query Analysis  
from sqlglot import parse_one
ast = parse_one("SELECT MD5(email) FROM users WHERE active = true", read=Vertica)
tables = [table.name for table in ast.find_all(exp.Table)]
functions = [func.sql() for func in ast.find_all(exp.Func)]

# Error Handling
from sqlglot.errors import ParseError, UnsupportedError
try:
    parse_one("SELECT $$invalid syntax$$", read=Vertica)
except ParseError as e:
    print(f"Parse error: {e}")
```

## Acknowledgments

- Built on top of the excellent [SQLGlot](https://github.com/tobymao/sqlglot) library
- Inspired by existing SQLGlot dialect implementations, particularly Postgres
- Designed to be compatible with Vertica SQL syntax and semantics 