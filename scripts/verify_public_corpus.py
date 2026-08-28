"""Rebuild and verify the Q42 public Vertica SQL corpus snapshot.

This script is intentionally outside the ordinary test suite.  It expects
local checkouts of the exact revisions listed in ``REVISIONS`` and never
clones or fetches them.  The generated JSON is the offline test fixture.
"""

# ruff: noqa: E501 -- source SQL and provenance strings intentionally remain verbatim.

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", category=SyntaxWarning)


REVISIONS = {
    "dbt-vertica": "0fdd229ee901eea542d3b9fd0a7ddeeac3b33093",
    "VerticaPy": "6b3d33537a4267a679059151b6a93aae9b284f74",
    "vertica-python": "1395e62dc714538401f5dce00cb2525b25c5495a",
    "ODBC-Loader": "846baa37b1b8651f151ae988c12a82f2deee0673",
    "dblink": "d9df82155590f94033f747bb28dc1f4e9c151bdc",
    "vertica-sql-go": "8d0b7b159d40fbffafcdfa9fae4e46d0866a1c86",
    "vertica.dplyr": "ebac291d100bd354d3e0f29c8e2a843bb0f85f60",
    "vertica-hyperloglog": "dd2d9f52857617cf9c7f89e58762cc08bcfc0504",
    "puppet-vertica": "d0962b9f65efbb684be8fc44b2a052e756c94654",
}

STATIC_REPOS = (
    "dbt-vertica",
    "VerticaPy",
    "vertica-python",
    "ODBC-Loader",
    "dblink",
    "vertica-sql-go",
    "vertica-hyperloglog",
)

LEADING_COMMENTS = re.compile(
    r"\A\s*(?:(?:--[^\n]*(?:\n|\Z))|(?:/\*[\s\S]*?\*/\s*))*", re.MULTILINE
)
SQL_START = re.compile(
    r"\A(?:SELECT|WITH|INSERT|CREATE|DROP|DELETE|UPDATE|MERGE|TRUNCATE|COPY|EXPLAIN|PROFILE)\b",
    re.IGNORECASE,
)
FORMAT_FIELD = re.compile(r"\{(?:\d+|[A-Za-z_][^}]*)?\}")
INCOMPLETE_END = re.compile(
    r"(?:\b(?:AS|BY|FROM|IN|INTO|JOIN|ON|OR|SELECT|TABLE|THEN|UNION|UPDATE|WHERE|WITH)|[=(.,]|['\"])\s*;?\s*\Z",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Candidate:
    source: str
    revision: str
    path: str
    line: int
    sql: str
    adaptation: str = "none"
    status: str = "admitted"
    exclusion_reason: str | None = None
    label: str | None = None


def is_candidate(text: str) -> bool:
    text = text.strip()
    if len(text) < 6 or len(text) > 50_000:
        return False
    without_comments = text[LEADING_COMMENTS.match(text).end() :]
    return not (
        not SQL_START.match(without_comments)
        or "{{" in text
        or "{%" in text
        or FORMAT_FIELD.search(text)
        or "%s" in text
        or re.search(r"%\([^)]+\)s", text)
        or INCOMPLETE_END.search(text)
    )


def q_scope(sql: str) -> bool:
    text = sql[LEADING_COMMENTS.match(sql).end() :].lstrip().upper()
    return bool(
        text.startswith(("SELECT", "WITH", "INSERT"))
        or re.match(r"CREATE\s+(?:(?:GLOBAL|LOCAL)\s+)?TEMP(?:ORARY)?\s+TABLE\b", text)
        or re.match(r"DROP\s+TABLE\b", text)
    )


def split_sql_script(text: str) -> list[tuple[int, str]]:
    statements: list[tuple[int, str]] = []
    start = 0
    start_line = line = 1
    quote: str | None = None
    line_comment = block_comment = False
    index = 0
    while index < len(text):
        char = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if char == "\n":
            line += 1
            line_comment = False
        if line_comment:
            index += 1
            continue
        if block_comment:
            if char == "*" and following == "/":
                block_comment = False
                index += 2
                continue
            index += 1
            continue
        if quote:
            if char == quote:
                if following == quote:
                    index += 2
                    continue
                quote = None
            index += 1
            continue
        if char == "-" and following == "-":
            line_comment = True
            index += 2
            continue
        if char == "/" and following == "*":
            block_comment = True
            index += 2
            continue
        if char in {"'", '"'}:
            quote = char
            index += 1
            continue
        if char == ";":
            statement = text[start:index].strip()
            if statement:
                statements.append((start_line, statement))
            start = index + 1
            start_line = line
        index += 1
    statement = text[start:].strip()
    if statement:
        statements.append((start_line, statement))
    return statements


def python_candidates(repo: str, root: Path, path: Path) -> list[Candidate]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    found: list[Candidate] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and not isinstance(parents.get(node), ast.JoinedStr)
            and is_candidate(node.value.strip())
        ):
            found.append(
                Candidate(
                    repo,
                    REVISIONS[repo],
                    path.relative_to(root).as_posix(),
                    node.lineno,
                    node.value.strip(),
                )
            )
    return found


def collect(repo: str, root: Path) -> list[Candidate]:
    found: list[Candidate] = []
    for path in root.rglob("*.py"):
        if ".git" not in path.parts:
            found.extend(python_candidates(repo, root, path))
    for path in root.rglob("*.sql"):
        if ".git" in path.parts:
            continue
        try:
            sql = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        adaptation = "none"
        if repo == "dbt-vertica" and "example/demo_dbt_vmart/models" in path.as_posix():
            original = sql
            sql = re.sub(r"\{\{\s*config\s*\([\s\S]*?\)\s*\}\}", "", sql, flags=re.I)
            sql = re.sub(
                r"\{\{\s*source\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}",
                r"\1.\2",
                sql,
                flags=re.I,
            )
            sql = re.sub(
                r"\{\{\s*ref\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}",
                r"\1",
                sql,
                flags=re.I,
            )
            sql = re.sub(r"\{\{\s*this\s*\}\}", path.stem, sql, flags=re.I)
            sql = re.sub(r"\{%\s*(?:if\s+is_incremental\(\)|endif)\s*%\}", "", sql)
            if sql != original:
                adaptation = (
                    "dbt config/control tags removed; source/ref/this resolved deterministically"
                )
        sql = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("\\"))
        for line, statement in split_sql_script(sql):
            if is_candidate(statement):
                found.append(
                    Candidate(
                        repo,
                        REVISIONS[repo],
                        path.relative_to(root).as_posix(),
                        line,
                        statement.strip(),
                        adaptation,
                    )
                )
    return found


VMART = {
    "01": """SELECT fat_content
FROM (
  SELECT DISTINCT fat_content
  FROM product_dimension
  WHERE department_description
  IN ('Dairy') ) AS food
  ORDER BY fat_content
  LIMIT 5;""",
    "02": """SELECT order_number, date_ordered
FROM store.store_orders_fact orders
WHERE orders.store_key IN (
  SELECT store_key FROM store.store_dimension WHERE store_state = 'MA')
AND orders.vendor_key NOT IN (
  SELECT vendor_key FROM public.vendor_dimension WHERE vendor_state = 'MA')
AND date_ordered < '2012-03-01';""",
    "03": """SELECT customer_name, annual_income
FROM public.customer_dimension
WHERE (customer_gender, annual_income) IN (
  SELECT customer_gender, MAX(annual_income)
  FROM public.customer_dimension GROUP BY customer_gender);""",
    "04": """SELECT DISTINCT s.product_key, p.product_description
FROM store.store_sales_fact s, public.product_dimension p
WHERE s.product_key = p.product_key AND s.product_version = p.product_version
AND s.store_key IN (SELECT store_key FROM store.store_dimension WHERE store_state = 'MA')
ORDER BY s.product_key;""",
    "05": """SELECT store_key, order_number, date_ordered
FROM store.store_orders_fact
WHERE EXISTS (SELECT 1 FROM public.vendor_dimension
WHERE public.vendor_dimension.vendor_key = store.store_orders_fact.vendor_key)
AND date_ordered = '2012-01-02';""",
    "06": """SELECT store_key, order_number, date_ordered
FROM store.store_orders_fact ord, public.vendor_dimension vd
WHERE ord.vendor_key = vd.vendor_key
AND vd.deal_size IN (SELECT MAX(deal_size) FROM public.vendor_dimension)
AND date_ordered = '2013-01-04';""",
    "07": """SELECT product_description, sku_number, department_description
FROM public.product_dimension
WHERE (category_description, department_description, product_cost) IN (
  SELECT category_description, department_description, MAX(product_cost)
  FROM product_dimension GROUP BY category_description, department_description);""",
    "08": """SELECT page_description, page_type, start_date, end_date
FROM online_sales.online_sales_fact f, online_sales.online_page_dimension d
WHERE f.online_page_key = d.online_page_key
AND page_number IN (SELECT MAX(page_number) FROM online_sales.online_page_dimension)
AND page_type = 'monthly' AND start_date = '2012-06-02';""",
    "09": """SELECT sales_quantity, sales_dollar_amount, transaction_type, cc_name
FROM online_sales.online_sales_fact
INNER JOIN online_sales.call_center_dimension
ON (online_sales.online_sales_fact.call_center_key = online_sales.call_center_dimension.call_center_key
AND sale_date_key = 156)
ORDER BY sales_dollar_amount DESC;""",
}

CURATED = {
    **{
        f"vmart-{number}": Candidate(
            "Vertica-VMart",
            "26.2",
            f"getting-started/appendix/sample-scripts/vmart-query-{number}-sql/",
            1,
            sql,
            "documentation headings and expected vsql output omitted",
        )
        for number, sql in VMART.items()
    },
    "dblink-select": Candidate(
        "dblink",
        REVISIONS["dblink"],
        "README.md",
        8,
        "SELECT DBLINK(USING PARAMETERS\n    cid='pgdb', query='SELECT COUNT(*) FROM tpch.lineitem') OVER();",
        "vsql prompt omitted",
    ),
    "dblink-ctas": Candidate(
        "dblink",
        REVISIONS["dblink"],
        "README.md",
        30,
        "CREATE TABLE public.customer AS SELECT DBLINK(USING PARAMETERS\n    cid='pgdb', query='SELECT * FROM tpch.customer WHERE RANDOM() < 0.1') OVER();",
        "vsql prompt omitted",
    ),
    "dblink-join": Candidate(
        "dblink",
        REVISIONS["dblink"],
        "README.md",
        50,
        "SELECT r.r_name, count(*) FROM tpch.nation n LEFT OUTER JOIN\n(SELECT DBLINK(USING PARAMETERS cid='mypg', query='SELECT r_name, r_regionkey FROM tpch.region') OVER()) r\nON n.n_regionkey = r.r_regionkey GROUP BY 1;",
        "vsql prompt omitted",
    ),
    "verticapy-correlation": Candidate(
        "VerticaPy",
        REVISIONS["VerticaPy"],
        "README.md",
        368,
        'SELECT /*+LABEL(\'vDataFrame._aggregate_matrix\')*/ CORR_MATRIX("pclass", "survived", "age", "sibsp", "parch", "fare", "body") OVER () FROM (SELECT RANK() OVER (ORDER BY "pclass") AS "pclass", RANK() OVER (ORDER BY "survived") AS "survived", RANK() OVER (ORDER BY "age") AS "age", RANK() OVER (ORDER BY "sibsp") AS "sibsp", RANK() OVER (ORDER BY "parch") AS "parch", RANK() OVER (ORDER BY "fare") AS "fare", RANK() OVER (ORDER BY "body") AS "body" FROM "public"."titanic") spearman_table',
        "HTML table formatting removed",
    ),
    "dplyr-filter": Candidate(
        "vertica.dplyr",
        REVISIONS["vertica.dplyr"],
        "README.md",
        367,
        'SELECT * FROM (SELECT "year" AS "year", "month" AS "month", "day" AS "day", "origin" AS "origin", "arr_delay" AS "arr_delay" FROM "flights") "jmuwgnfpix" WHERE (("year" = 2013.0) AND ("month" > 1.0) AND ("month" < 12.0))',
    ),
    "dplyr-analysis": Candidate(
        "vertica.dplyr",
        REVISIONS["vertica.dplyr"],
        "README.md",
        463,
        'SELECT * FROM (SELECT "origin", count(*) AS "count", AVG("arr_delay") AS "delay" FROM (SELECT * FROM (SELECT * FROM (SELECT "year" AS "year", "month" AS "month", "day" AS "day", "origin" AS "origin", "arr_delay" AS "arr_delay" FROM "flights") "sqdztmepka" WHERE (("year" = 2013.0) AND ("month" > 1.0) AND ("month" < 12.0))) "gbpmhczqce" WHERE (NOT(("arr_delay") IS NULL))) "tzdmvoxcvd" GROUP BY "origin") "psjbudtstt" ORDER BY "delay" DESC',
    ),
    "vertica-python-named": Candidate(
        "vertica-python",
        REVISIONS["vertica-python"],
        "vertica_python/tests/integration_tests/test_cursor.py",
        781,
        "SELECT :a, :b",
    ),
    "vertica-python-format": Candidate(
        "vertica-python",
        REVISIONS["vertica-python"],
        "vertica_python/tests/integration_tests/test_cursor.py",
        770,
        "SELECT %s, %s",
    ),
    "vertica-python-qmark": Candidate(
        "vertica-python",
        REVISIONS["vertica-python"],
        "vertica_python/tests/integration_tests/test_cursor.py",
        766,
        "SELECT ?, ?",
    ),
    "hyperloglog-ctas-template": Candidate(
        "vertica-hyperloglog",
        REVISIONS["vertica-hyperloglog"],
        "README.md",
        263,
        "CREATE TABLE test_schema.agg_clicks AS SELECT HOUR(TO_TIMESTAMP(click_ts)) AS hour, banner_id, zone_id, client_id, network_id, HllCreateSynopsis(user_id_fast USING PARAMETERS hllLeadingBits=:precision, bitsPerBucket=:bitsperbucket) AS Synopsis FROM test_schema.fact_clicks WHERE client_id > :minrange AND client_id < :maxrange GROUP BY HOUR(TO_TIMESTAMP(click_ts)), banner_id, zone_id, client_id, network_id;",
        "README indentation normalized",
    ),
    "hyperloglog-select-template": Candidate(
        "vertica-hyperloglog",
        REVISIONS["vertica-hyperloglog"],
        "README.md",
        285,
        "SELECT client_id, HllDistinctCount(synopsis USING PARAMETERS hllLeadingBits=:precision) FROM test_schema.agg_clicks GROUP BY client_id;",
        "README indentation normalized",
    ),
}

EXCLUSIONS = {
    (
        "dbt-vertica",
        "tests/functional/adapter/test_grants.py",
        70,
    ): "incomplete Python string fragment: INSERT lacks INTO and a source",
    (
        "VerticaPy",
        "verticapy/mlops/model_tracking/base.py",
        589,
    ): "incomplete Python string fragment: INSERT keyword only",
    (
        "VerticaPy",
        "verticapy/performance/vertica/qprof_interface.py",
        191,
    ): "prose sentence beginning with 'select', not SQL",
    (
        "VerticaPy",
        "verticapy/tests/sql/test_sql.py",
        190,
    ): "VerticaPy $$$ client interpolation form, not standalone SQL",
    (
        "VerticaPy",
        "verticapy/tests/sql/test_sql.py",
        197,
    ): "VerticaPy $$$ client interpolation form, not standalone SQL",
}


def vbuddy_candidates(root: Path) -> list[Candidate]:
    path = root / "puppet-vertica" / "files" / "vBuddyLite"
    text = path.read_text(encoding="utf-8")
    match = re.search(r'sqlQueriesFile\s*=\s*"""([\s\S]*?)"""', text)
    if match is None:
        raise ValueError("vBuddyLite sqlQueriesFile body not found")
    body_start_line = text.count("\n", 0, match.start(1)) + 1
    found: dict[str, Candidate] = {}
    for offset, source_line in enumerate(match.group(1).splitlines()):
        for _, segment in split_sql_script(source_line):
            sql_match = re.search(r"(?:\A|#{2,3}|\|)\s*((?:SELECT|WITH)\b[\s\S]*)\Z", segment, re.I)
            if sql_match and q_scope(sql_match.group(1).strip()):
                sql = sql_match.group(1).strip()
                found.setdefault(
                    sql,
                    Candidate(
                        "puppet-vertica",
                        REVISIONS["puppet-vertica"],
                        "files/vBuddyLite",
                        body_start_line + offset,
                        sql,
                        "vBuddyLite menu delimiters removed",
                    ),
                )
    return list(found.values())


def build(source_root: Path) -> dict[str, Any]:
    for repo, revision in REVISIONS.items():
        checkout = source_root / repo
        head = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={checkout.as_posix()}",
                "-C",
                str(checkout),
                "rev-parse",
                "HEAD",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if head != revision:
            raise ValueError(f"{repo} is at {head}, expected {revision}")

    ordered: dict[str, Candidate] = {}
    for repo in STATIC_REPOS:
        for candidate in collect(repo, source_root / repo):
            if q_scope(candidate.sql):
                key = (candidate.source, candidate.path, candidate.line)
                reason = EXCLUSIONS.get(key)
                if reason:
                    candidate = Candidate(
                        **{**asdict(candidate), "status": "excluded", "exclusion_reason": reason}
                    )
                ordered.setdefault(candidate.sql, candidate)
    for label, candidate in CURATED.items():
        labeled = Candidate(**{**asdict(candidate), "label": label})
        if candidate.sql in ordered:
            ordered[candidate.sql] = Candidate(**{**asdict(ordered[candidate.sql]), "label": label})
        else:
            ordered[candidate.sql] = labeled
    for candidate in vbuddy_candidates(source_root):
        if "ABS((row_count" in candidate.sql:
            candidate = Candidate(
                **{
                    **asdict(candidate),
                    "label": (
                        "vbuddy-skew-detail"
                        if "WHERE skew_percent > 0" in candidate.sql
                        else "vbuddy-skew-summary"
                    ),
                }
            )
        ordered.setdefault(candidate.sql, candidate)

    entries = []
    for index, candidate in enumerate(ordered.values(), start=1):
        entries.append({"id": f"public-{index:03d}", **asdict(candidate)})
    admitted = sum(entry["status"] == "admitted" for entry in entries)
    excluded = len(entries) - admitted
    if (len(entries), admitted, excluded) != (370, 365, 5):
        raise ValueError(
            f"unexpected corpus counts: total={len(entries)} admitted={admitted} excluded={excluded}"
        )
    return {
        "schema_version": 1,
        "generated_from": "Q42 deterministic extraction rules",
        "counts": {"total": len(entries), "admitted": admitted, "excluded": excluded},
        "revisions": REVISIONS,
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_root", type=Path)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("tests/fixtures/public_vertica_corpus.json"),
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    actual = build(args.source_root.resolve())
    if args.write:
        with args.fixture.open("w", encoding="utf-8", newline="\n") as fixture_file:
            fixture_file.write(json.dumps(actual, indent=2) + "\n")
        print(f"wrote {args.fixture}: {actual['counts']}")
        return 0
    expected = json.loads(args.fixture.read_text(encoding="utf-8"))
    if actual != expected:
        raise SystemExit("public corpus fixture differs from fresh pinned-source extraction")
    print(f"verified {args.fixture}: {actual['counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
