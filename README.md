# SQLGlot Vertica dialect

`vertica-sqlglot-dialect` is a separately distributed
[SQLGlot](https://github.com/tobymao/sqlglot) dialect for Vertica / OpenText
Analytics Database SQL.

This repository is a from-scratch successor to the 0.1.x package. Its design is
coverage-driven: every supported Vertica language family is tracked in
[`docs/COVERAGE.md`](docs/COVERAGE.md), and dialect behavior is protected by
round-trip and cross-dialect regression tests.

The AST and compatibility rules are documented in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), with the audited primary
references listed in [`docs/SOURCES.md`](docs/SOURCES.md).
The remaining implementation phases and their release gates are tracked in
[`docs/ROADMAP.md`](docs/ROADMAP.md).

The current development baseline is:

- OpenText Analytics Database / Vertica 26.2 SQL
- SQLGlot 30.13.x
- Python 3.9 through 3.15

Python 3.15 support is tested against the latest available prerelease until
CPython 3.15 reaches general availability.

The SQLGlot dependency is intentionally bounded to one minor line because
dialect parser/generator subclass APIs can change between minor releases. The
supported runtime is pure-Python SQLGlot; the optional compiled `sqlglot[c]`
runtime does not currently guarantee custom-dialect subclass compatibility.

## Installation

```console
pip install vertica-sqlglot-dialect
```

SQLGlot discovers the dialect through the package entry point:

```python
from sqlglot import parse_one, transpile

tree = parse_one("SELECT TIMESTAMPADD(day, 1, created_at) FROM events", read="vertica")
print(tree.sql(dialect="vertica"))

print(transpile("SELECT NOW()", read="postgres", write="vertica")[0])
```

The class can also be passed directly, which is useful in environments that do
not load Python package entry points:

```python
from sqlglot import parse_one
from sqlglot_vertica import Vertica

tree = parse_one("SELECT 1", read=Vertica)
```

## Development

```console
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pre_commit install --install-hooks
.venv/Scripts/python -m pre_commit run --all-files --show-diff-on-failure
.venv/Scripts/python -m pytest
.venv/Scripts/ruff check .
.venv/Scripts/ruff format --check .
.venv/Scripts/mypy src
```

On POSIX systems, replace `.venv/Scripts` with `.venv/bin`. The installed hooks
run repository hygiene and safety checks, Ruff autofixes and formatting, strict
mypy, and [Conventional Commits](https://www.conventionalcommits.org/) message
validation. Commit without `--no-verify`; if a hook fixes a file, review the
change, restage it, and rerun the checks before retrying the commit.

The full coverage, multi-version, build, and installed-wheel checks remain in
the documented agent release gate and CI. Hook revisions are frozen to immutable
commits; maintainers can update them deliberately with
`python -m pre_commit autoupdate --freeze`.

The coverage matrix distinguishes semantic support from lossless command
preservation. “Preserved” means SQLGlot retains a statement as a command but
does not yet expose all of its clauses as traversable AST nodes.

Security-policy DDL includes a typed, non-secret PROFILE lifecycle. CREATE and
ALTER retain ordered password-policy metadata, ALTER also supports reset and
rename actions, and DROP retains ordered targets and dependency cascading.
PROFILE nodes never contain password values; user assignment and catalog
effects remain separate server concerns.

The non-secret USER lifecycle also retains ordered time and capacity policy:
grace, idle-session and query-runtime intervals; database/node connection
limits; memory and temporary-space caps; and ALTER-only hash-algorithm
selection. Credential clauses remain outside the AST and fail with sanitized
errors.

Executable `PROFILE statement` is also semantic: the wrapper retains a
traversable SELECT, INSERT, UPDATE, DELETE, COPY, or MERGE child so analysis and
optimizer traversal can inspect the statement that Vertica profiles.

## License

MIT
