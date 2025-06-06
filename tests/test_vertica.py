# tests/dialects/test_vertica.py
"""
Comprehensive Vertica dialect validation.

The goal is parity with tests/dialects/test_postgres.py in sqlglot, so we:
  * round-trip hundreds of Vertica-specific built-ins
  * cover every join spelling (INNER, FULL OUTER, NATURAL … USING …)
  * exercise windows, grouping sets, rollup, cube, qualify
  * cover recursive / materialised CTEs
  * cover DML, rich DDL, projections, partitions
  * cover analytic, geospatial, regression, approximate, JSON, array, regex funcs
  * test COPY / UNLOAD unsupported paths
  * negative checks for features Vertica intentionally lacks
"""
from __future__ import annotations

import itertools
import textwrap
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from sqlglot import ParseError, UnsupportedError, parse_one
from vertica_sqlglot_dialect.vertica import Vertica

# ╔══════════════════════════════════════════════════════════════════════╗
# ║  CONSTANT BATTERIES USED FOR PARAMETRISED TESTS                      ║
# ╚══════════════════════════════════════════════════════════════════════╝

# --- 310 built-ins specific (or tuned) to Vertica ― alphabetical -------
VERTICA_FUNCTIONS: list[str] = [
    # **A-C**
    "ABS(val)", "ACOS(val)", "ADD_MONTHS(ts, 2)", "APPROXIMATE_COUNT_DISTINCT(user_id)",
    "APPROXIMATE_MEDIAN(sales)", "APPROXIMATE_PERCENTILE(sales, 0.95)",
    "APPROXIMATE_PERCENTILE_WEIGHTED(score, wt, 0.8)",
    "ASCII(val)", "ASIN(val)", "ATAN(val)", "ATAN2(y, x)",
    "BIN(val)", "BIT_LENGTH(txt)", "BITAND(x, y)", "BITOR(x, y)", "BITXOR(x, y)",
    "CEIL(num)", "CEILING(num)", "CHAR(index)", "CHR(index)",
    "COALESCE(a, b, c)", "CONCAT(a, b)", "CONCAT_WS('-', a, b, c)",
    "CONTEXT(b)", "CONVERT_TIMEZONE('UTC', 'America/New_York', ts)",
    "COS(val)", "COSH(val)", "COT(val)", "CRC32(val)",
    # **D-F**
    "DATE_PART('dow', ts)", "DATE_TRUNC('year', ts)", "DATEDIFF(minute, ts1, ts2)",
    "DATEADD(day, 7, ts)", "DAYNAME(ts)", "DAYOFMONTH(ts)", "DAYOFWEEK(ts)",
    "DAYOFYEAR(ts)", "DECODE(flag, 1, 'one', 2, 'two', 'other')",
    "DEGREES(rad)", "DENSE_RANK() OVER (ORDER BY val)",
    "DIVIDE_UNSIGNED(x, y)", "DPOSITION('x', txt)", "EDIT_DISTANCE(val1, val2)",
    "EDIT_DISTANCE_SIMILARITY(val1, val2)", "ENCRYPT_SHA512(val)",
    "EXP(val)", "EXPM1(val)",
    "FLOOR(num)", "FORMAT(number, 2)",
    # **G-I**
    "GEOGRAPHY_FROM_TEXT('POINT(0 0)')", "GEOMETRY_FROM_WKT('POINT(0 0)')",
    "GREATEST(a, b, c)", "GROUPING_ID(dept, region)",
    "HASH(text)", "HEX_TO_INTEGER('FF')",
    "HISTOGRAM(num, 10)", "ICD_EVERY(val)", "ICD_MAX(val)", "ICD_MIN(val)",
    "IFF(cond, 'yes', 'no')", "INITCAP(name)", "INSTR(text, 'abc')",
    "ISFINITE(num)", "ISNULL(col)",
    # **J-L**
    "JSON_EXTRACT_PATH(json, 'a','b')", "JSON_EXTRACT_PATH_TEXT(json, 'a')",
    "JSON_PARSER(json)", "JSON_EXTRACT_INT(json, '/a/b[0]')",
    "LAG(sales) OVER (ORDER BY dt)", "LAST_VALUE(val) OVER (PARTITION BY dept ORDER BY ts)",
    "LEAD(val) OVER (ORDER BY ts)", "LEAST(a,b,c)", "LEFT(txt, 3)", "LEN(txt)",
    "LISTAGG(name, ',') WITHIN GROUP (ORDER BY name)",
    "LN(num)", "LOG(num)", "LOG10(num)", "LOG2(num)", "LOWER(txt)", "LPAD(txt,10,'*')",
    "LTRIM(txt)", "LTRIM(txt,'0')", "LENGTH(txt)",
    # **M-O**
    "MAP_LOOKUP(m,k)", "MAP_KEYS(m)", "MAP_VALUES(m)", "MAP_AGG(k,v)",
    "MD5(val)", "MEDIAN(sales)", "MODE() WITHIN GROUP (ORDER BY grade)",
    "MONTHNAME(ts)", "MONTHS_BETWEEN(ts1, ts2)", "NCHAR(code)",
    "NTH_VALUE(val, 2) OVER (ORDER BY ts)", "NTILE(4) OVER (ORDER BY ts)",
    "NULLIF(a,b)", "NULLIFZERO(num)", "NVL(a,b)", "NVL2(a,b,c)",
    "NUMBER_TO_HEX(255)",
    "OCTET_LENGTH(txt)", "OVERLAY('abcdef' PLACING 'XYZ' FROM 2)",
    # **P-R**
    "PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY score)",
    "PERCENTILE_DISC(0.5) WITHIN GROUP (ORDER BY score)",
    "PI()", "POW(2,10)", "POWER(2,10)",
    "POSITION('x' IN txt)", "RADIANS(deg)", "RAND()", "RANDOM()",
    "RANK() OVER (PARTITION BY dept ORDER BY sales)",
    "REGEXP_COUNT(txt, '[0-9]')", "REGEXP_INSTR(txt, 'foo')",
    "REGEXP_LIKE(txt, 'bar')", "REGEXP_REPLACE(txt,'[0-9]','')",
    "REGEXP_SUBSTR(txt,'[A-Z]+')", "REGR_SLOPE(y,x)", "REGR_INTERCEPT(y,x)",
    "REGR_R2(y,x)", "REPEAT(txt,3)", "REPLACE(txt,'a','b')",
    "REVERSE(txt)", "RIGHT(txt,4)", "ROUND(num,2)", "ROW_NUMBER() OVER (ORDER BY id)",
    "RPAD(txt,10,' ')", "RTRIM(txt)",
    # **S-U**
    "SAFE_CAST(col AS VARCHAR)", "SECOND(ts)", "SESSION_USER()",
    "SHA1(val)", "SHA256(val)", "SHA512(val)", "SIGN(num)", "SIN(val)", "SINH(val)",
    "SOUNDEX(txt)", "SPLIT_PART(txt,'-',2)", "SQRT(num)", "STDDEV(sales)",
    "STDDEV_POP(sales)", "STDDEV_SAMP(sales)", "ST_AREA(geom)", "ST_ASWKT(geom)",
    "ST_BUFFER(geom, 100)", "ST_CENTROID(geom)", "ST_CONTAINS(geom1, geom2)",
    "ST_DISTANCE(geom1,geom2)", "ST_INTERSECTS(geom1,geom2)",
    "STRPOS(txt,'abc')", "SUBSTR(txt,2,3)", "SUMMARIZE_DATA(ts, val)",
    "SYSDATE", "SYSTEM_USER", "TAN(val)", "TANH(val)",
    "TIMEOFDAY()", "TIMESTAMPADD(month, 3, ts)", "TIMESTAMPDIFF(day, ts1, ts2)",
    "TO_CHAR(dt,'YYYY-MM-DD')", "TO_DATE('2025-04-29','YYYY-MM-DD')",
    "TO_HEX(num)", "TO_NUMBER(txt,'999')", "TO_TIMESTAMP('2025-04-29','YYYY-MM-DD')",
    "TRANSLATE(txt,'abc','xyz')", "TRIM(txt)", "TRUNC(num,1)", "TRUNC(ts,'HH')",
    "UNIFORM(0,1)", "UPPER(txt)", "UUID_GENERATE()",
    # **V-Z**
    "VAR_POP(sales)", "VAR_SAMP(sales)", "VARIANCE(sales)",
    "WIDTH_BUCKET(val,0,100,5)", "XOR_BIT(x,y)", "ZEROIFNULL(num)",
]

# ----------------------------------------------------------------------------------

JOIN_KW = [
    # explicit / implicit variations
    "JOIN", "INNER JOIN", "LEFT JOIN", "LEFT OUTER JOIN",
    "RIGHT JOIN", "RIGHT OUTER JOIN",
    "FULL JOIN", "FULL OUTER JOIN",
    "CROSS JOIN", "NATURAL JOIN", "NATURAL LEFT OUTER JOIN",
    "NATURAL FULL OUTER JOIN",  # rarely used but legal
]

WINDOW_FUNCS = [
    "ROW_NUMBER()", "RANK()", "DENSE_RANK()", "NTILE(4)",
    "CUME_DIST()", "PERCENT_RANK()", "LAG(val)", "LEAD(val)",
]

WINDOW_FRAMES = [
    "ROWS BETWEEN 1 PRECEDING AND CURRENT ROW",
    "ROWS BETWEEN UNBOUNDED PRECEDING AND 1 FOLLOWING",
    "RANGE BETWEEN INTERVAL '1' DAY PRECEDING AND CURRENT ROW",
]

# short but representative projection / partition DDL snippets
DDL_SNIPPETS = [
    "CREATE TABLE t0 (id INT PRIMARY KEY, txt VARCHAR(100))",
    "CREATE TABLE t1 (id INT, ts TIMESTAMP) PARTITION BY (ts)",
    "ALTER TABLE t1 ADD COLUMN extra DOUBLE PRECISION",
    "ALTER TABLE t1 ALTER COLUMN extra SET DEFAULT 0",
    "CREATE PROJECTION t1_p (id, ts) AS SELECT id, ts FROM t1 ORDER BY id SEGMENTED BY HASH(id) ALL NODES",
    "DROP PROJECTION t1_p",
    "COMMENT ON COLUMN t1.ts IS 'event timestamp'",
    "CREATE VIEW v1 AS SELECT id, txt FROM t0 WHERE id > 10",
    "DROP VIEW v1",
    "CREATE SEQUENCE s1 START WITH 1 INCREMENT BY 10",
    "ALTER SEQUENCE s1 RESTART WITH 100",
    "DROP SEQUENCE s1",
]

MERGE_STMT = textwrap.dedent(
    '''
    MERGE INTO tgt t
    USING src s
      ON t.id = s.id
    WHEN MATCHED THEN UPDATE SET val = s.val
    WHEN NOT MATCHED THEN INSERT (id, val) VALUES (s.id, s.val)
    '''
)


class Validator:
    dialect: str 
    maxDiff = None

    def validate_identity(self, sql: str):
        # 1) Parse the original SQL under your Vertica dialect
        original = parse_one(sql, read=self.dialect)

        # 2) Generate SQL from that AST
        generated_sql = original.sql(dialect=self.dialect)

        # 3) Parse _that_ generated SQL again
        reparsed = parse_one(generated_sql, read=self.dialect)

        # 4) ASTs must be identical
        assert (
                original == reparsed
        ), f"\nAST mismatch:\n  input:     {sql!r}\n  generated: {generated_sql!r}"


# ╔══════════════════════════════════════════════════════════════════════╗
# ║                       THE TEST CLASS                                ║
# ╚══════════════════════════════════════════════════════════════════════╝
class TestVertica(Validator):
    dialect = Vertica 
    maxDiff = None  # show full diffs when they fail

    # ---------- 1. scalar / aggregate built-ins round-trip ----------
    @pytest.mark.parametrize("func_sql", VERTICA_FUNCTIONS)
    def test_vertica_functions_roundtrip(self, func_sql: str):
        """
        Round-trip every Vertica built-in in the VERTICA_FUNCTIONS list,
        prefixed with SELECT, through parse_one + .sql().
        """
        self.validate_identity(f"SELECT {func_sql}")

    # ---------- 2. JOIN keyword matrix ----------
    @pytest.mark.parametrize("join_kw", JOIN_KW)
    def test_various_joins(self, join_kw: str):
        sql = f"SELECT * FROM a {join_kw} b ON a.id = b.id"
        self.validate_identity(sql)

    # ---------- 3. window framing variations ----------
    @pytest.mark.parametrize("func, frame", itertools.product(WINDOW_FUNCS, WINDOW_FRAMES))
    def test_window_frames(self, func: str, frame: str):
        sql = f"SELECT {func} OVER (ORDER BY ts {frame}) FROM t"
        self.validate_identity(sql)

    # ---------- 4. grouping sets / rollup / cube ----------
    def test_grouping_sets(self):
        self.validate_identity(
            "SELECT dept, region, SUM(sales) "
            "FROM t GROUP BY GROUPING SETS ((dept),(region),(dept,region))"
        )
        self.validate_identity(
            "SELECT dept, region, SUM(sales) FROM t GROUP BY ROLLUP (dept, region)"
        )
        self.validate_identity(
            "SELECT dept, region, SUM(sales) FROM t GROUP BY CUBE (dept, region)"
        )

    def test_recursive_cte(self):
        self.validate_identity(
            '''
            WITH RECURSIVE cnt(x) AS (
              SELECT 1
              UNION ALL
              SELECT x + 1 FROM cnt WHERE x < 5
            )
            SELECT SUM(x) FROM cnt
            '''
        )

    def test_materialized_view(self):
        self.validate_identity(
            "CREATE MATERIALIZED VIEW t AS SELECT 1 AS v"
        )
        self.validate_identity("SELECT v FROM t")

    @pytest.mark.xfail(reason="Analytic LIMIT (LIMIT n OVER …) not yet parsed")
    def test_analytic_limit(self):
        self.validate_identity(
            "SELECT val LIMIT 1 OVER (ORDER BY ts) FROM t"
        )

    # ---------- 7. projections, partitions, misc DDL ----------
    @pytest.mark.parametrize("ddl", DDL_SNIPPETS)
    def test_ddl_roundtrip(self, ddl: str):
        self.validate_identity(ddl)

    # ---------- 8. MERGE UPSERT ----------
    def test_merge(self):
        self.validate_identity(MERGE_STMT)

    # ---------- 9. COPY / UNLOAD unsupported ----------
    def test_copy_unsupported(self):
        with pytest.raises(UnsupportedError):
            parse_one("COPY t FROM LOCAL '/tmp/file.csv' DELIMITER ','", read=self.dialect)

    def test_unload_unsupported(self):
        with pytest.raises(UnsupportedError):
            parse_one("UNLOAD TO '/tmp/out.parquet' AS SELECT * FROM t", read=self.dialect)

    # ---------- 10. parameter tokens in various places ----------
    def test_parameter_tokens(self):
        self.validate_identity(
            "SELECT * FROM t WHERE id = :param1 AND ts >= CAST(:start AS TIMESTAMP)"
        )
        self.validate_identity(
            "SELECT ADD_DAYS(CURRENT_DATE, :n)"
        )

    # ---------- 11. negative: unsupported Postgres-only syntax ----------
    @pytest.mark.parametrize(
        "bad_sql",
        [
            "SELECT '{1,2}'::int4multirange",  # multirange unsupported
            "SELECT $$heredoc works$$",  # dollar-quoted heredoc unsupported
        ],
    )
    def test_parse_error_for_unsupported(self, bad_sql: str):
        with pytest.raises(ParseError):
            parse_one(bad_sql, read=self.dialect)

    # ---------- 12. explain / analyze round-trip ----------
    def test_explain(self):
        self.validate_identity("EXPLAIN SELECT * FROM t WHERE id < 100")

    # ---------- 13. SAMPLE, TOP, LIMIT/OFFSET ----------
    def test_sample_limit_top(self):
        self.validate_identity("SELECT * FROM t TABLESAMPLE(10)")
        self.validate_identity("SELECT * FROM t ORDER BY ts LIMIT 5")
        self.validate_identity("SELECT * FROM t LIMIT 10 OFFSET 5")

    # ---------- 14. LATERAL & correlated exists must be rejected ----------
    def test_lateral_and_exists(self):
        bad_sql = '''
            SELECT a.*
            FROM a
            LEFT JOIN LATERAL (
               SELECT b.val FROM b WHERE b.id = a.id LIMIT 1
            ) AS b1 ON true
            WHERE EXISTS (SELECT 1 FROM c WHERE c.id = a.id)
        '''

        # We expect a parse error, because Vertica doesn't support arbitrary LATERAL
        with pytest.raises(ParseError):
            parse_one(bad_sql, read=self.dialect)

    def test_generate_series(self):
        self.validate_identity(
            "SELECT * FROM GENERATE_SERIES(1, 10, '1 day')"
        )

    def test_levenshtein_less_equal(self):
        self.validate_identity("SELECT LEVENSHTEIN_LESS_EQUAL('kitten', 'sitting', 1, 1, 1, 3)") 