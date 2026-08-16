"""Parser extensions for Vertica SQL."""

from __future__ import annotations

import re
import typing as t

from sqlglot import ErrorLevel, Token, TokenType, exp
from sqlglot.dialects.dialect import Dialect, map_date_part
from sqlglot.errors import ParseError
from sqlglot.helper import seq_get
from sqlglot.parsers.postgres import PostgresParser

from sqlglot_vertica import dml as vdml
from sqlglot_vertica import expressions as vexp
from sqlglot_vertica.tokens import DirectedPostfixComment, MisplacedDirectedComment

if t.TYPE_CHECKING:
    from sqlglot._typing import E


def _build_date_delta(expression_type: type[E]) -> t.Callable[[list[exp.Expr]], E]:
    """Build Vertica's `(datepart, count/start, start/end)` date functions."""

    def _builder(args: list[exp.Expr]) -> E:
        expression = expression_type(
            this=seq_get(args, 2),
            expression=seq_get(args, 1),
            unit=map_date_part(seq_get(args, 0)),
        )
        if expression_type is exp.TsOrDsAdd:
            expression.set("return_type", exp.DType.TIMESTAMP.into_expr())
        return expression

    return _builder


def _build_add_months(args: list[exp.Expr]) -> exp.AddMonths:
    return exp.AddMonths(
        this=seq_get(args, 0),
        expression=seq_get(args, 1),
        preserve_end_of_month=True,
    )


def _build_statement_timestamp(args: list[exp.Expr]) -> vexp.StatementTimestamp:
    return vexp.StatementTimestamp()


def _build_utc_statement_timestamp(args: list[exp.Expr]) -> vexp.UtcStatementTimestamp:
    return vexp.UtcStatementTimestamp()


def _build_greatest(args: list[exp.Expr]) -> exp.Greatest:
    return exp.Greatest(
        this=seq_get(args, 0),
        expressions=args[1:],
        ignore_nulls=False,
    )


def _build_least(args: list[exp.Expr]) -> exp.Least:
    return exp.Least(
        this=seq_get(args, 0),
        expressions=args[1:],
        ignore_nulls=False,
    )


def _build_vertica_explode(args: list[exp.Expr]) -> vexp.VerticaExplode:
    return vexp.VerticaExplode(this=exp.Explode.from_arg_list(args))


def _build_vertica_array_length(args: list[exp.Expr]) -> vexp.VerticaArrayLength:
    return vexp.VerticaArrayLength(this=exp.ArraySize(this=seq_get(args, 0)))


def _build_vertica_regexp_like(args: list[exp.Expr]) -> vexp.VerticaRegexpLike:
    predicate = exp.RegexpLike(
        this=seq_get(args, 0),
        expression=seq_get(args, 1),
    )
    return vexp.VerticaRegexpLike(this=predicate, modifiers=args[2:])


def _build_vertica_instr(args: list[exp.Expr]) -> vexp.VerticaInstr:
    position = exp.StrPosition.from_arg_list(args)
    return vexp.VerticaInstr(this=position)


def _build_to_char(args: list[exp.Expr], dialect: Dialect) -> exp.Expr:
    if len(args) != 2:
        function = exp.Anonymous(this="TO_CHAR", expressions=args)
        return vexp.VerticaToChar(this=function)

    builder = t.cast(t.Callable[..., exp.Expr], PostgresParser.FUNCTIONS["TO_CHAR"])
    return builder(args, dialect=dialect)


class VerticaParser(PostgresParser):
    """Parse Vertica SQL into canonical and Vertica-specific AST nodes."""

    # These Vertica clause words are tokenized specially so they can terminate
    # implicit aliases in their grammatical positions. They remain legal as
    # identifiers (and explicit aliases) everywhere an identifier is expected.
    ID_VAR_TOKENS: t.ClassVar = {
        *PostgresParser.ID_VAR_TOKENS,
        TokenType.MATCH_RECOGNIZE,
        TokenType.POLICY,
    }

    TABLE_HINT_NAMES: t.ClassVar = {"PROJS", "SKIP_PROJS"}
    JOIN_HINT_NAMES: t.ClassVar = {"DISTRIB", "JTYPE"}
    WITH_HINT_NAMES: t.ClassVar = {"ENABLE_WITH_CLAUSE_MATERIALIZATION"}
    CTAS_HINT_NAMES: t.ClassVar = {"LABEL"}
    DIRECTED_CONSTANT_HINT: t.ClassVar[re.Pattern[str]] = re.compile(
        r"^(?:(?P<conserve>:c)|(?P<pair>:v|IGNORECONST(?:ANT)?)\s*"
        r"\(\s*(?P<index>[0-9]+)\s*\))$",
        re.IGNORECASE,
    )
    DIRECTED_CONSTANT_HINT_PREFIX: t.ClassVar[re.Pattern[str]] = re.compile(
        r"^(?::[cv]|IGNORECONST(?:ANT)?)",
        re.IGNORECASE,
    )

    SECURITY_ROUTINE_KINDS: t.ClassVar = (
        "AGGREGATE FUNCTION",
        "ANALYTIC FUNCTION",
        "TRANSFORM FUNCTION",
        "FUNCTION",
        "FILTER",
        "PARSER",
        "SOURCE",
        "PROCEDURE",
    )
    SECURITY_NAMED_TARGET_KINDS: t.ClassVar = (
        "DATABASE",
        "KEY",
        "LIBRARY",
        "MODEL",
        "SCHEMA",
        "SEQUENCE",
        "TABLE",
        "VIEW",
    )
    SECURITY_EXACT_PRIVILEGES: t.ClassVar = {
        "AGGREGATE FUNCTION": {"ALTER", "DROP", "EXECUTE"},
        "ANALYTIC FUNCTION": {"ALTER", "DROP", "EXECUTE"},
        "FILTER": {"ALTER", "DROP", "EXECUTE"},
        "FUNCTION": {"ALTER", "DROP", "EXECUTE"},
        "LOCATION": {"READ", "WRITE"},
        "PARSER": {"ALTER", "DROP", "EXECUTE"},
        "PROCEDURE": {"EXECUTE"},
        "RESOURCE POOL": {"USAGE"},
        "SOURCE": {"ALTER", "DROP", "EXECUTE"},
        "TRANSFORM FUNCTION": {"ALTER", "DROP", "EXECUTE"},
        "WORKLOAD": {"USAGE"},
    }
    SECURITY_EXTEND_DISALLOWED: t.ClassVar = {
        "DATABASE",
        "DATA LOADER",
        "LOCATION",
        "PROCEDURE",
        "RESOURCE POOL",
        "WORKLOAD",
    }
    ROUTING_RULE_OBJECT_BOUNDARIES: t.ClassVar = {
        "DATABASE",
        "DIRECTED",
        "EXTERNAL",
        "FLEX",
        "FLEXIBLE",
        "FUNCTION",
        "INDEX",
        "LIBRARY",
        "LOAD",
        "MODEL",
        "NETWORK",
        "PROCEDURE",
        "PROJECTION",
        "RESOURCE",
        "ROLE",
        "ROUTING",
        "SCHEMA",
        "SEQUENCE",
        "TABLE",
        "TYPE",
        "USER",
        "VIEW",
    }
    LOAD_BALANCE_GROUP_MEMBER_KINDS: t.ClassVar = {
        "ADDRESS",
        "FAULT GROUP",
        "SUBCLUSTER",
    }
    LOAD_BALANCE_GROUP_POLICIES: t.ClassVar = {"NONE", "RANDOM", "ROUNDROBIN"}
    LOAD_BALANCE_GROUP_COMPOUND_BOUNDARIES: t.ClassVar = {
        "DIRECTED QUERY",
        "EXTERNAL PROCEDURE",
        "EXTERNAL TABLE",
        "FLEX EXTERNAL",
        "FLEXIBLE EXTERNAL",
        "NETWORK ADDRESS",
        "NETWORK INTERFACE",
        "RESOURCE POOL",
        "ROUTING RULE",
    }
    NETWORK_ADDRESS_COMPOUND_BOUNDARIES: t.ClassVar = {
        "DIRECTED QUERY",
        "EXTERNAL PROCEDURE",
        "EXTERNAL TABLE",
        "FLEX EXTERNAL",
        "FLEXIBLE EXTERNAL",
        "LOAD BALANCE GROUP",
        "NETWORK INTERFACE",
        "RESOURCE POOL",
        "ROUTING RULE",
    }
    USER_PREFIX_WORDS: t.ClassVar[dict[str, set[str]]] = {
        "CREATE": {
            "CLUSTERED",
            "COLUMNSTORE",
            "CONCURRENTLY",
            "DYNAMIC",
            "EXTERNAL",
            "FLEX",
            "FLEXIBLE",
            "GLOBAL",
            "HYBRID",
            "ICEBERG",
            "LOCAL",
            "MATERIALIZED",
            "MULTISET",
            "NONCLUSTERED",
            "PRIVATE",
            "SECURE",
            "SET",
            "TEMP",
            "TEMPORARY",
            "TRANSIENT",
            "UNIQUE",
            "UNLOGGED",
            "VOLATILE",
        },
        "ALTER": {
            "CONCURRENTLY",
            "EXTERNAL",
            "FLEX",
            "ICEBERG",
            "MATERIALIZED",
            "ONLY",
        },
        "DROP": {
            "CASCADE",
            "CONCURRENTLY",
            "EXTERNAL",
            "ICEBERG",
            "MATERIALIZED",
            "RESTRICT",
            "TEMP",
            "TEMPORARY",
        },
    }
    USER_PREFIX_SEQUENCES: t.ClassVar[dict[str, set[tuple[str, ...]]]] = {
        "CREATE": {
            ("IF", "NOT", "EXISTS"),
            ("OR", "ALTER"),
            ("OR", "REFRESH"),
            ("OR", "REPLACE"),
        },
        "ALTER": {("IF", "EXISTS")},
        "DROP": {("IF", "EXISTS")},
    }
    USER_KEYWORD_TOKEN_TYPES: t.ClassVar[dict[str, TokenType]] = {
        "ACCOUNT": TokenType.VAR,
        "BY": TokenType.VAR,
        "CASCADE": TokenType.VAR,
        "EXPIRE": TokenType.VAR,
        "EXISTS": TokenType.EXISTS,
        "IF": TokenType.VAR,
        "IDENTIFIED": TokenType.VAR,
        "LOCK": TokenType.LOCK,
        "NOT": TokenType.NOT,
        "PASSWORD": TokenType.VAR,
        "RENAME": TokenType.RENAME,
        "RESTRICT": TokenType.VAR,
        "TO": TokenType.VAR,
        "TOTPSECRET": TokenType.VAR,
        "UNLOCK": TokenType.VAR,
    }
    USER_SENSITIVE_LITERAL_TOKENS: t.ClassVar[set[TokenType]] = {
        TokenType.BIT_STRING,
        TokenType.BYTE_STRING,
        TokenType.HEREDOC_STRING,
        TokenType.HEX_STRING,
        TokenType.NATIONAL_STRING,
        TokenType.RAW_STRING,
        TokenType.STRING,
        TokenType.UNICODE_STRING,
    }
    PROFILE_PARAMETERS: t.ClassVar[tuple[str, ...]] = (
        "PASSWORD_LIFE_TIME",
        "PASSWORD_MIN_LIFE_TIME",
        "PASSWORD_GRACE_TIME",
        "FAILED_LOGIN_ATTEMPTS",
        "PASSWORD_LOCK_TIME",
        "PASSWORD_REUSE_MAX",
        "PASSWORD_REUSE_TIME",
        "PASSWORD_MAX_LENGTH",
        "PASSWORD_MIN_LENGTH",
        "PASSWORD_MIN_LETTERS",
        "PASSWORD_MIN_UPPERCASE_LETTERS",
        "PASSWORD_MIN_LOWERCASE_LETTERS",
        "PASSWORD_MIN_DIGITS",
        "PASSWORD_MIN_SYMBOLS",
        "PASSWORD_MIN_CHAR_CHANGE",
    )
    PROFILE_POSITIVE_PARAMETERS: t.ClassVar[set[str]] = {
        "FAILED_LOGIN_ATTEMPTS",
        "PASSWORD_GRACE_TIME",
        "PASSWORD_LIFE_TIME",
        "PASSWORD_LOCK_TIME",
        "PASSWORD_REUSE_MAX",
        "PASSWORD_REUSE_TIME",
    }
    PROFILE_CHARACTER_MINIMUM_PARAMETERS: t.ClassVar[set[str]] = {
        "PASSWORD_MIN_CHAR_CHANGE",
        "PASSWORD_MIN_DIGITS",
        "PASSWORD_MIN_LENGTH",
        "PASSWORD_MIN_LETTERS",
        "PASSWORD_MIN_LOWERCASE_LETTERS",
        "PASSWORD_MIN_SYMBOLS",
        "PASSWORD_MIN_UPPERCASE_LETTERS",
    }

    USER_DEFINED_EXTENSION_KINDS: t.ClassVar = (
        "AGGREGATE FUNCTION",
        "ANALYTIC FUNCTION",
        "TRANSFORM FUNCTION",
        "FUNCTION",
        "FILTER",
        "PARSER",
        "SOURCE",
    )
    USER_DEFINED_EXTENSION_LANGUAGES: t.ClassVar = {
        "AGGREGATE FUNCTION": {"C++"},
        "ANALYTIC FUNCTION": {"C++", "JAVA"},
        "TRANSFORM FUNCTION": {"C++", "JAVA", "PYTHON", "R"},
        "FUNCTION": {"C++", "JAVA", "PYTHON", "R"},
        "FILTER": {"C++", "JAVA", "PYTHON"},
        "PARSER": {"C++", "JAVA", "PYTHON"},
        "SOURCE": {"C++", "JAVA"},
        "LIBRARY": {"C++", "JAVA", "PYTHON", "R"},
    }
    USER_DEFINED_EXTENSION_LANGUAGE_NAMES: t.ClassVar = {
        "C++": "C++",
        "JAVA": "Java",
        "PYTHON": "Python",
        "R": "R",
    }
    USER_DEFINED_LOAD_FUNCTION_KINDS: t.ClassVar = {"FILTER", "PARSER", "SOURCE"}

    RESOURCE_POOL_PARAMETERS: t.ClassVar = {
        "CASCADE TO",
        "CPUAFFINITYMODE",
        "CPUAFFINITYSET",
        "EXECUTIONPARALLELISM",
        "MAXCONCURRENCY",
        "MAXMEMORYSIZE",
        "MAXQUERYMEMORYSIZE",
        "MEMORYSIZE",
        "PLANNEDCONCURRENCY",
        "PRIORITY",
        "QUEUETIMEOUT",
        "RUNTIMECAP",
        "RUNTIMEPRIORITY",
        "RUNTIMEPRIORITYTHRESHOLD",
        "SINGLEINITIATOR",
    }
    RESOURCE_POOL_EXTENDED_PRIORITY_NAMES: t.ClassVar = {"RECOVERY", "SYSQUERY", "TM"}

    INTERVAL_QUALIFIER_ENDS: t.ClassVar = {
        "YEAR": {"MONTH"},
        "MONTH": set(),
        "DAY": {"HOUR", "MINUTE", "SECOND"},
        "HOUR": {"MINUTE", "SECOND"},
        "MINUTE": {"SECOND"},
        "SECOND": set(),
    }

    CONSTRAINT_PARSERS: t.ClassVar = {
        **PostgresParser.CONSTRAINT_PARSERS,
        "ACCESSRANK": lambda self: self._parse_access_rank_column_constraint(),
        "ENCODING": lambda self: self._parse_encoding_column_constraint(),
    }

    COPY_COMPRESSIONS: t.ClassVar = {"UNCOMPRESSED", "BZIP", "GZIP", "LZO", "ZSTD"}
    COPY_COLUMN_PARAMETER_ORDER: t.ClassVar = {
        "DELIMITER": 10,
        "ENCLOSED BY": 20,
        "ENFORCELENGTH": 30,
        "ESCAPE AS": 40,
        "NO ESCAPE": 40,
        "FILLER": 50,
        "FORMAT": 60,
        "NULL AS": 70,
        "TRIM": 80,
    }
    COPY_PARAMETER_ORDER: t.ClassVar = {
        "ABORT ON ERROR": 10,
        "DELIMITER": 20,
        "ENCLOSED BY": 30,
        "ENFORCELENGTH": 40,
        "ERROR TOLERANCE": 50,
        "ESCAPE AS": 60,
        "NO ESCAPE": 60,
        "EXCEPTIONS": 70,
        "FILTER": 75,
        "NULL AS": 80,
        "RECORD TERMINATOR": 90,
        "REJECTED DATA": 100,
        "REJECTED DATA AS TABLE": 100,
        "REJECTMAX": 110,
        "SKIP": 120,
        "SKIP BYTES": 130,
        "STREAM NAME": 140,
        "TRAILING NULLCOLS": 150,
        "TRIM": 160,
        "COLLECTIONDELIMITER": 170,
        "COLLECTIONOPEN": 171,
        "COLLECTIONCLOSE": 172,
        "COLLECTIONNULLELEMENT": 173,
        "COLLECTIONENCLOSE": 174,
        "PARSER": 180,
        "AUTO": 190,
        "DIRECT": 190,
        "TRICKLE": 190,
    }
    EXTERNAL_COPY_PARAMETER_ORDER: t.ClassVar = {
        "ABORT ON ERROR": 10,
        "DELIMITER": 20,
        "ENCLOSED BY": 30,
        "ENFORCELENGTH": 40,
        "ERROR TOLERANCE": 50,
        "ESCAPE AS": 60,
        "NO ESCAPE": 60,
        "EXCEPTIONS": 70,
        "FILTER": 75,
        "NULL AS": 80,
        "PARSER": 85,
        "RECORD TERMINATOR": 90,
        "REJECTED DATA": 100,
        "REJECTMAX": 110,
        "SKIP": 120,
        "SKIP BYTES": 130,
        "TRAILING NULLCOLS": 150,
        "TRIM": 160,
    }
    FLEXIBLE_COPY_PARAMETER_ORDER: t.ClassVar = {
        "PARSER": 5,
        "ABORT ON ERROR": 10,
        "DELIMITER": 20,
        "ENCLOSED BY": 30,
        "ENFORCELENGTH": 40,
        "ESCAPE AS": 60,
        "NO ESCAPE": 60,
        "EXCEPTIONS": 70,
        "NULL AS": 80,
        "RECORD TERMINATOR": 90,
        "REJECTED DATA": 100,
        "REJECTMAX": 110,
        "SKIP": 120,
        "SKIP BYTES": 130,
        "TRAILING NULLCOLS": 150,
        "TRIM": 160,
    }
    ICEBERG_CLAUSE_ORDER: t.ClassVar = {
        "GLUE_DB": 10,
        "GLUE_TABLE": 20,
        "HMS_DB": 30,
        "HMS_TABLE": 40,
        "REST_AUTH": 50,
        "COLUMN TYPES": 60,
    }
    ICEBERG_SIZED_TYPES: t.ClassVar = {
        exp.DType.VARCHAR,
        exp.DType.LONGTEXT,
        exp.DType.VARBINARY,
        exp.DType.LONGBLOB,
    }
    COPY_FORMAT_PARAMETERS: t.ClassVar = {
        "ORC": {
            "HIVE_PARTITION_COLS",
            "ALLOW_NO_MATCH",
            "DO_SOFT_SCHEMA_MATCH_BY_NAME",
            "REJECT_ON_MATERIALIZED_TYPE_ERROR",
        },
        "PARQUET": {
            "HIVE_PARTITION_COLS",
            "ALLOW_NO_MATCH",
            "ALLOW_LONG_VARBINARY_MATCH_COMPLEX_TYPE",
            "DO_SOFT_SCHEMA_MATCH_BY_NAME",
            "REJECT_ON_MATERIALIZED_TYPE_ERROR",
        },
    }
    EXTERNAL_PROCEDURE_TYPES: t.ClassVar = {
        "BIGINT",
        "BOOLEAN",
        "DECIMAL",
        "DOUBLE PRECISION",
        "FLOAT",
        "FLOAT8",
        "INT",
        "INT8",
        "INTEGER",
        "MONEY",
        "NUMBER",
        "NUMERIC",
        "REAL",
        "SMALLINT",
        "TINYINT",
        "VARCHAR",
    }

    FUNCTIONS: t.ClassVar = {
        **PostgresParser.FUNCTIONS,
        "ADD_MONTHS": _build_add_months,
        "ARRAY_LENGTH": _build_vertica_array_length,
        "DATEDIFF": _build_date_delta(exp.TsOrDsDiff),
        "EXPLODE": _build_vertica_explode,
        "GETDATE": _build_statement_timestamp,
        "GETUTCDATE": _build_utc_statement_timestamp,
        "GREATEST": _build_greatest,
        "INSTR": _build_vertica_instr,
        "LEAST": _build_least,
        "REGEXP_LIKE": _build_vertica_regexp_like,
        "ROW": lambda args: exp.Struct(expressions=args),
        "TO_CHAR": _build_to_char,
        "TIMESTAMPADD": _build_date_delta(exp.TsOrDsAdd),
        "TIMESTAMPDIFF": _build_date_delta(exp.TsOrDsDiff),
    }

    FUNCTION_PARSERS: t.ClassVar = {
        **PostgresParser.FUNCTION_PARSERS,
        "LISTAGG": lambda self: self._parse_vertica_listagg(),
        "OVERLAY": lambda self: self._parse_string_unit_function(self._parse_overlay(), "OVERLAY"),
        "POSITION": lambda self: self._parse_string_unit_function(
            self._parse_position(), "POSITION"
        ),
        "SUBSTRING": lambda self: self._parse_string_unit_function(
            self._parse_substring(), "SUBSTRING"
        ),
    }

    FUNCTIONS_WITH_ALIASED_ARGS: t.ClassVar = {
        *PostgresParser.FUNCTIONS_WITH_ALIASED_ARGS,
        "ROW",
    }

    NO_PAREN_FUNCTION_PARSERS: t.ClassVar = {
        **PostgresParser.NO_PAREN_FUNCTION_PARSERS,
        "SYSDATE": lambda self: self._parse_sysdate(),
    }

    ARRAY_CONSTRUCTORS: t.ClassVar = {
        **PostgresParser.ARRAY_CONSTRUCTORS,
        # SQLGlot types constructors as Func subclasses even though the parser
        # only calls them with ``expressions=``. SET deliberately is not a Func
        # so foreign generators cannot invent a SET_LITERAL fallback.
        "SET": t.cast(type[exp.Func], vexp.SetLiteral),
    }

    UNARY_PARSERS: t.ClassVar = {
        **PostgresParser.UNARY_PARSERS,
        TokenType.EXCLAMATION: lambda self: self.expression(
            exp.Factorial(this=self._parse_unary())
        ),
        TokenType.PARAMETER: lambda self: self.expression(exp.Abs(this=self._parse_unary())),
    }

    RANGE_PARSERS: t.ClassVar = {
        **PostgresParser.RANGE_PARSERS,
        TokenType.MATCH: lambda self, this: self._parse_interpolate_predicate(this),
    }

    QUERY_MODIFIER_PARSERS: t.ClassVar = {
        **PostgresParser.QUERY_MODIFIER_PARSERS,
        TokenType.MATCH_RECOGNIZE: lambda self: ("match", self._parse_vertica_match()),
    }
    QUERY_MODIFIER_TOKENS: t.ClassVar = set(QUERY_MODIFIER_PARSERS)

    def _parse_statement(self) -> exp.Expr | None:
        if not self._curr:
            return None
        if any(
            isinstance(comment, MisplacedDirectedComment)
            for token in self._tokens
            for comment in token.comments
        ):
            self.raise_error("A directed-query constant annotation must follow a value expression")
        directed_marker_count = sum(
            self._is_directed_token_comment(comment)
            for token in self._tokens
            for comment in token.comments
        )

        expression: exp.Expr | None
        profile_comments = list(self._curr.comments)
        if self._match_profile_object():
            expression = self._parse_profile_statement(comments=profile_comments)
        elif self._curr.text.upper() == "PROFILE":
            self._raise_profile_error(
                "PROFILE requires the unquoted ASCII PROFILE statement keyword"
            )
        elif self._match_text_seq("SAVE", "QUERY"):
            expression = self._parse_saved_or_get_directed_query(save=True)
        elif self._match_text_seq("GET", "DIRECTED"):
            if not self._match_text_seq("QUERY"):
                self.raise_error("GET DIRECTED must be followed by QUERY")
            expression = self._parse_saved_or_get_directed_query(save=False)
        elif self._match_text_seq("ACTIVATE"):
            if not self._match_text_seq("DIRECTED", "QUERY"):
                self.raise_error("ACTIVATE must be followed by DIRECTED QUERY")
            expression = self._parse_directed_query_action("ACTIVATE")
        elif self._match_text_seq("DEACTIVATE"):
            if not self._match_text_seq("DIRECTED", "QUERY"):
                self.raise_error("DEACTIVATE must be followed by DIRECTED QUERY")
            expression = self._parse_directed_query_action("DEACTIVATE")
        else:
            expression = super()._parse_statement()

        expression = self._structure_directed_constant_hints(expression)
        if expression is not None:
            hints = list(expression.find_all(vexp.DirectedConstantHint))
            if len(hints) != directed_marker_count:
                self.raise_error(
                    "A directed-query constant annotation could not be attached to its value"
                )
            if any(hint.find_ancestor(exp.Query) is None for hint in hints):
                self.raise_error(
                    "Directed-query constant annotations are valid only inside SELECT queries"
                )
        return expression

    def _parse_profile_statement(self, comments: list[str]) -> vexp.ProfileStatement:
        if not self._curr:
            self._raise_profile_error("PROFILE requires one SQL statement")
        if self._match_profile_object(advance=False) or self._curr.text.upper() == "PROFILE":
            self._raise_profile_error("Nested PROFILE statements are not supported")

        body_starts_with_query = self._curr.token_type in {TokenType.SELECT, TokenType.WITH}
        original_error_level = self.error_level
        self.error_level = ErrorLevel.IMMEDIATE
        try:
            statement = super()._parse_statement()
        finally:
            self.error_level = original_error_level
        if isinstance(statement, exp.Query) and not body_starts_with_query:
            self._raise_profile_error("PROFILE query bodies must start with SELECT or WITH")
        if not self._is_profile_statement_body(statement):
            self._raise_profile_error(
                "PROFILE requires SELECT, INSERT, UPDATE, DELETE, COPY, or MERGE"
            )
        assert statement is not None
        return self.expression(vexp.ProfileStatement(this=statement), comments=comments)

    @staticmethod
    def _is_profile_statement_body(statement: exp.Expr | None) -> bool:
        if isinstance(statement, exp.Select):
            return bool(statement.expressions)
        if isinstance(statement, exp.SetOperation):
            return VerticaParser._is_profile_statement_body(
                statement.args.get("this")
            ) and VerticaParser._is_profile_statement_body(statement.args.get("expression"))
        return isinstance(
            statement,
            (exp.Insert, exp.Update, exp.Delete, vexp.VerticaCopy, exp.Merge),
        )

    def _parse_command(  # type: ignore[override]
        self,
    ) -> exp.Command | vexp.ShowWorkload:
        if self._prev.token_type == TokenType.SHOW and self._curr.token_type == TokenType.STRING:
            payload = self._curr.text
            parsed_payload = self._show_workload_payload(payload)
            if parsed_payload is not None:
                normalized, payload_comments, leading_payload_comments = parsed_payload
                if normalized in {"WORKLOAD", "AVAILABLE WORKLOADS"}:
                    previous_comments = list(self._prev_comments or [])
                    retained_previous = (
                        previous_comments[:-leading_payload_comments]
                        if leading_payload_comments
                        else previous_comments
                    )
                    comments = [*retained_previous, *payload_comments]
                    self._advance()
                    return self.expression(
                        vexp.ShowWorkload(
                            this=exp.var("WORKLOAD"),
                            available=normalized == "AVAILABLE WORKLOADS",
                        ),
                        comments=comments,
                    )
                malformed_prefix = next(
                    (
                        prefix
                        for prefix in ("AVAILABLE WORKLOADS", "AVAILABLE WORKLOAD", "WORKLOAD")
                        if normalized.startswith(prefix)
                        and len(normalized) > len(prefix)
                        and normalized[len(prefix)] not in "_$"
                        and not normalized[len(prefix)].isalnum()
                    ),
                    None,
                )
                if normalized == "AVAILABLE WORKLOAD" or malformed_prefix:
                    self.raise_error(f"Unsupported SHOW workload syntax: {payload}")
            elif payload.upper().startswith(("WORKLOAD", "AVAILABLE WORKLOAD")):
                self.raise_error(f"Unsupported SHOW workload syntax: {payload}")
        return super()._parse_command()

    @staticmethod
    def _show_workload_payload(text: str) -> tuple[str, list[str], int] | None:
        comments: list[str] = []
        sql: list[str] = []
        position = 0
        leading_comments = 0
        seen_sql = False
        while position < len(text):
            if text.startswith("/*", position):
                end = text.find("*/", position + 2)
                if end < 0:
                    return None
                comments.append(text[position + 2 : end])
                if not seen_sql:
                    leading_comments += 1
                sql.append(" ")
                position = end + 2
                continue
            if text.startswith("--", position):
                end = text.find("\n", position + 2)
                if end < 0:
                    comments.append(text[position + 2 :])
                    if not seen_sql:
                        leading_comments += 1
                    sql.append(" ")
                    position = len(text)
                    continue
                comments.append(text[position + 2 : end].rstrip("\r"))
                if not seen_sql:
                    leading_comments += 1
                sql.append(" ")
                position = end + 1
                continue
            sql.append(text[position])
            seen_sql = seen_sql or not text[position].isspace()
            position += 1
        return " ".join("".join(sql).upper().split()), comments, leading_comments

    def _parse_set(self, unset: bool = False, tag: bool = False) -> exp.Set | exp.Command:
        if unset or tag:
            return super()._parse_set(unset=unset, tag=tag)

        if self._match_text_seq("SESSION", "WORKLOAD"):
            return self._parse_set_session_routing("WORKLOAD")
        if self._match_text_seq("SESSION", "RESOURCE_POOL"):
            return self._parse_set_session_routing("RESOURCE_POOL")
        return super()._parse_set(unset=unset, tag=tag)

    def _parse_set_session_routing(self, name: str) -> vexp.SetSessionRouting:
        if name == "WORKLOAD":
            if self._match(TokenType.EQ):
                self.raise_error("SET SESSION WORKLOAD requires TO or direct value syntax, not =")
            self._match_text_seq("TO")
            allowed_keywords = {"DEFAULT", "NONE"}
        else:
            if self._match_text_seq("TO", advance=False):
                self.raise_error("SET SESSION RESOURCE_POOL requires =")
            if not self._match(TokenType.EQ):
                self.raise_error("SET SESSION RESOURCE_POOL requires =")
            allowed_keywords = {"DEFAULT"}

        if self._match_texts(allowed_keywords):
            value: exp.Expr = self.expression(exp.var(self._prev.text.upper()))
        elif name == "RESOURCE_POOL" and self._match_text_seq("NONE", advance=False):
            self.raise_error("SET SESSION RESOURCE_POOL does not support NONE")
        else:
            if self._curr.token_type == TokenType.STRING:
                self.raise_error(f"SET SESSION {name} requires an identifier, not a string")
            value = self._parse_connection_policy_identifier(f"SET SESSION {name}")

        if self._curr:
            self.raise_error(f"Unexpected SET SESSION {name} clause at {self._curr.text!r}")

        assignment = self.expression(
            exp.EQ(
                this=exp.Column(this=exp.to_identifier(name)),
                expression=value,
            )
        )
        item = self.expression(exp.SetItem(this=assignment, kind="SESSION"))
        return self.expression(vexp.SetSessionRouting(expressions=[item], unset=False, tag=False))

    def _parse_saved_or_get_directed_query(self, save: bool) -> exp.Expr:
        statement = "SAVE QUERY" if save else "GET DIRECTED QUERY"
        query = self._parse_directed_query_input(statement)
        if self._curr:
            self.raise_error(f"Unexpected {statement} clause at {self._curr.text!r}")

        expression_type = vexp.SaveQuery if save else vexp.GetDirectedQuery
        return self.expression(expression_type(this=query))

    def _parse_directed_query_input(self, statement: str) -> exp.Query:
        query = self._parse_select()
        selects = list(query.find_all(exp.Select)) if isinstance(query, exp.Query) else []
        if (
            not self._is_directed_select_query(query)
            or not selects
            or any(not select.expressions for select in selects)
        ):
            self.raise_error(f"{statement} requires a SELECT query")
        assert isinstance(query, exp.Query)
        return query

    def _is_directed_select_query(
        self, query: exp.Expr | None, *, allow_subquery: bool = False
    ) -> bool:
        if isinstance(query, exp.Select):
            return bool(query.expressions)
        if isinstance(query, exp.Subquery):
            return allow_subquery and self._is_directed_select_query(
                query.args.get("this"), allow_subquery=True
            )
        if isinstance(query, exp.SetOperation):
            return self._is_directed_select_query(
                query.args.get("this"), allow_subquery=True
            ) and self._is_directed_select_query(query.args.get("expression"), allow_subquery=True)
        return False

    def _parse_directed_query_name(self, statement: str) -> exp.Identifier | exp.Literal:
        if self._match(TokenType.STRING):
            return self.expression(exp.Literal.string(self._prev.text))

        name = self._parse_id_var(any_token=False)
        if not isinstance(name, exp.Identifier):
            self.raise_error(f"{statement} requires a directed-query name")
        assert isinstance(name, exp.Identifier)
        return name

    def _parse_directed_query_action(self, action: str) -> vexp.DirectedQueryAction:
        if not self._curr:
            self.raise_error(f"{action} DIRECTED QUERY requires one target")

        name: exp.Expr | None = None
        query = None
        where = None
        if self._match(TokenType.WHERE, advance=False):
            where = self._parse_where()
            if not where or not where.this:
                self.raise_error(f"{action} DIRECTED QUERY WHERE requires a condition")
        elif self._curr.token_type in (TokenType.SELECT, TokenType.WITH):
            if action != "DEACTIVATE":
                self.raise_error(f"{action} DIRECTED QUERY does not accept an input query")
            query = self._parse_directed_query_input(f"{action} DIRECTED QUERY")
        else:
            name = self._parse_directed_query_name(f"{action} DIRECTED QUERY")

        if self._curr:
            self.raise_error(f"Unexpected {action} DIRECTED QUERY clause at {self._curr.text!r}")

        return self.expression(
            vexp.DirectedQueryAction(
                action=exp.var(action),
                this=name,
                expression=query,
                where=where,
            )
        )

    def _structure_directed_constant_hints(self, expression: exp.Expr | None) -> exp.Expr | None:
        if not expression:
            return None

        root = expression
        for node in reversed(list(expression.walk())):
            matches: list[tuple[str, str | None]] = []
            ordinary_comments: list[str] = []
            for comment in node.comments or ():
                if not isinstance(comment, DirectedPostfixComment):
                    ordinary_comments.append(comment)
                    continue
                candidate = self._directed_hint_comment_body(comment)

                match = self.DIRECTED_CONSTANT_HINT.fullmatch(candidate)
                if match:
                    directive = ":c" if match.group("conserve") else match.group("pair")
                    assert directive is not None
                    directive = directive.lower() if directive.startswith(":") else "IGNORECONST"
                    matches.append((directive, match.group("index")))
                elif self.DIRECTED_CONSTANT_HINT_PREFIX.match(candidate):
                    self.raise_error(f"Malformed directed-query constant annotation {comment!r}")
                else:
                    ordinary_comments.append(comment)

            if not matches:
                continue
            if len(matches) != 1:
                self.raise_error("A constant expression accepts only one directed-query annotation")
            if node.parent is None or isinstance(
                node,
                (
                    exp.From,
                    exp.Group,
                    exp.Having,
                    exp.Join,
                    exp.Limit,
                    exp.Offset,
                    exp.Order,
                    exp.Query,
                    exp.Qualify,
                    exp.Subquery,
                    exp.Table,
                    exp.TableAlias,
                    exp.Values,
                    exp.Where,
                    exp.With,
                    exp.Alias,
                ),
            ):
                self.raise_error(
                    "A directed-query constant annotation must follow a value expression"
                )

            directive, index_value = matches[0]
            node.comments = ordinary_comments or None
            parent, arg_key, index = node.parent, node.arg_key, node.index
            wrapper = vexp.DirectedConstantHint(
                directive=exp.var(directive),
                index=exp.Literal.number(index_value) if index_value is not None else None,
            )
            wrapper.meta.update(node.meta)
            if parent and arg_key:
                parent.set(arg_key, wrapper, index)
            else:
                root = wrapper
            wrapper.set("this", node)
            self.validate_expression(wrapper)

        return root

    @staticmethod
    def _directed_hint_comment_body(comment: str) -> str:
        return comment.strip()

    def _is_directed_token_comment(self, comment: str) -> bool:
        return isinstance(comment, DirectedPostfixComment) and bool(
            self.DIRECTED_CONSTANT_HINT_PREFIX.match(self._directed_hint_comment_body(comment))
        )

    def _parse_hint(self) -> exp.Hint | None:
        if self._curr.token_type == TokenType.HINT:
            for comment in self._curr.comments:
                if not isinstance(comment, (DirectedPostfixComment, MisplacedDirectedComment)):
                    continue
                candidate = self._directed_hint_comment_body(comment)
                if self.DIRECTED_CONSTANT_HINT_PREFIX.match(candidate):
                    self.raise_error(
                        "A directed-query constant annotation must follow its expression"
                    )
        return super()._parse_hint()

    def _optimizer_hint_from_comment(
        self, comment: str, allowed_names: t.Collection[str]
    ) -> exp.Hint | None:
        """Parse a hint comment only when every directive is valid in this position.

        SQLGlot's tokenizer intentionally stores comment bodies without their
        delimiters. Once ``/*+`` is configured as a comment start, a comment
        attached to a JOIN, table alias, or WITH token no longer retains the
        leading ``+``. Restricting the accepted directive names by grammar
        position prevents ordinary prose comments from becoming optimizer hints.
        """

        parsed_hint = exp.maybe_parse(comment.strip(), into=exp.Hint, dialect=self.dialect)
        if (
            not isinstance(parsed_hint, exp.Hint)
            or not parsed_hint.expressions
            or not all(isinstance(expression, exp.Expr) for expression in parsed_hint.expressions)
        ):
            return None

        names = {
            expression.name.upper()
            for expression in parsed_hint.expressions
            if isinstance(expression, exp.Expr)
        }
        return parsed_hint if names.issubset(allowed_names) else None

    def _extract_optimizer_hints(
        self, comments: t.Sequence[str] | None, allowed_names: t.Collection[str]
    ) -> tuple[list[exp.Hint], list[str]]:
        hints: list[exp.Hint] = []
        ordinary_comments: list[str] = []
        for comment in comments or ():
            hint = self._optimizer_hint_from_comment(comment, allowed_names)
            if hint:
                hints.append(hint)
            else:
                ordinary_comments.append(comment)
        return hints, ordinary_comments

    def _parse_with(self, skip_with_token: bool = False) -> exp.With | None:
        with_expression = super()._parse_with(skip_with_token=skip_with_token)
        if not with_expression:
            return None

        hints, ordinary_comments = self._extract_optimizer_hints(
            with_expression.comments, self.WITH_HINT_NAMES
        )
        if not hints:
            return with_expression

        hint = self.expression(
            exp.Hint(
                expressions=[
                    directive
                    for optimizer_hint in hints
                    for directive in optimizer_hint.expressions
                ]
            )
        )

        # `eliminate_subqueries` reconstructs an exact exp.With and therefore
        # cannot preserve this custom wrapper. Keep the semantic marker on the
        # CTE query subtree, which that rule does preserve. SELECT query options
        # are also an explicit merge barrier in SQLGlot 30.13.
        for cte in with_expression.expressions:
            query = cte.this
            options = list(query.args.get("options") or [])
            options.append(vexp.MaterializedWithMarker(this=hint.copy()))
            query.set("options", options)

        result = self.expression(
            vexp.WithHint(**with_expression.args, hint=hint),
            comments=ordinary_comments,
        )
        result.meta.update(with_expression.meta)
        return result

    def _parse_select_query(
        self,
        nested: bool = False,
        table: bool = False,
        parse_subquery_alias: bool = True,
        parse_set_operation: bool = True,
    ) -> exp.Expr | None:
        expression = super()._parse_select_query(
            nested=nested,
            table=table,
            parse_subquery_alias=parse_subquery_alias,
            parse_set_operation=parse_set_operation,
        )
        if isinstance(
            expression, (exp.Delete, exp.Insert, exp.Merge, exp.Update)
        ) and expression.args.get("with_"):
            self.raise_error(
                f"Vertica {expression.key.upper()} does not support a leading WITH clause"
            )
        return expression

    def _parse_table(
        self,
        schema: bool = False,
        joins: bool = False,
        alias_tokens: t.Collection[TokenType] | None = None,
        parse_bracket: bool = False,
        is_db_reference: bool = False,
        parse_partition: bool = False,
        consume_pipe: bool = False,
    ) -> exp.Expr | None:
        table = super()._parse_table(
            schema=schema,
            joins=joins,
            alias_tokens=alias_tokens,
            parse_bracket=parse_bracket,
            is_db_reference=is_db_reference,
            parse_partition=parse_partition,
            consume_pipe=consume_pipe,
        )
        if not isinstance(table, exp.Table):
            return table

        parsed_hints: list[exp.Hint] = []
        parsed, ordinary_comments = self._extract_optimizer_hints(
            table.comments, self.TABLE_HINT_NAMES
        )
        parsed_hints.extend(parsed)
        table.comments = ordinary_comments

        alias = table.args.get("alias")
        if isinstance(alias, exp.TableAlias):
            parsed, ordinary_comments = self._extract_optimizer_hints(
                alias.comments, self.TABLE_HINT_NAMES
            )
            parsed_hints.extend(parsed)
            alias.comments = ordinary_comments

        for parsed_hint in parsed_hints:
            table.append(
                "hints",
                self.expression(vexp.TableOptimizerHint(expressions=parsed_hint.expressions)),
            )
        return table

    def _parse_join(
        self,
        skip_join_token: bool = False,
        parse_bracket: bool = False,
        alias_tokens: t.Collection[TokenType] | None = None,
    ) -> exp.Join | None:
        join = super()._parse_join(
            skip_join_token=skip_join_token,
            parse_bracket=parse_bracket,
            alias_tokens=alias_tokens,
        )
        if not join:
            return None

        hints, ordinary_comments = self._extract_optimizer_hints(
            join.comments, self.JOIN_HINT_NAMES
        )
        join.comments = ordinary_comments
        if hints:
            join.set(
                "hint",
                self.expression(
                    exp.Hint(
                        expressions=[
                            directive
                            for optimizer_hint in hints
                            for directive in optimizer_hint.expressions
                        ]
                    )
                ),
            )
        return join

    def _parse_describe(self) -> exp.Describe:
        if self._prev.text.upper() != "EXPLAIN":
            return super()._parse_describe()

        hint = self._parse_hint()
        options = []
        for option in ("LOCAL", "VERBOSE", "JSON", "ANNOTATED"):
            if self._match_text_seq(option):
                options.append(self.expression(exp.var(option)))

        statement = self._parse_statement()
        if not statement:
            self.raise_error("EXPLAIN requires a SQL statement")
        assert statement is not None
        return self.expression(vexp.Explain(this=statement, hint=hint, options=options))

    def _raise_dml_errors(self, errors: list[str]) -> None:
        if errors:
            self.raise_error(errors[0])

    def _parse_insert(self) -> exp.Insert:
        index = self._index
        self._parse_hint()
        has_into = self._match(TokenType.INTO, advance=False)
        self._retreat(index)
        if not has_into:
            self.raise_error("Vertica INSERT requires INTO")

        insert = super()._parse_insert()
        if not isinstance(insert, exp.Insert):
            self.raise_error("Vertica INSERT does not support multi-table forms")
        assert isinstance(insert, exp.Insert)
        self._raise_dml_errors(vdml.insert_errors(insert))
        return insert

    def _parse_merge(self) -> exp.Merge:
        hint = self._parse_hint()
        if not self._match(TokenType.INTO):
            self.raise_error("Vertica MERGE requires INTO")

        target = self._parse_table()
        if not isinstance(target, exp.Table):
            self.raise_error("Vertica MERGE requires a table target")

        if target and self._match(TokenType.ALIAS, advance=False):
            target.set("alias", self._parse_table_alias())

        if not self._match(TokenType.USING):
            self.raise_error("Vertica MERGE requires USING")
        source = self._parse_table()
        if source is None:
            self.raise_error("Vertica MERGE requires a USING source")

        if not self._match(TokenType.ON):
            self.raise_error("Vertica MERGE requires ON")
        on = self._parse_disjunction()
        if on is None:
            self.raise_error("Vertica MERGE ON requires a condition")

        whens = self._parse_vertica_merge_whens()
        merge: exp.Merge
        if hint:
            merge = self.expression(
                vexp.VerticaMerge(
                    this=target,
                    using=source,
                    on=on,
                    whens=whens,
                    hint=hint,
                )
            )
        else:
            merge = self.expression(exp.Merge(this=target, using=source, on=on, whens=whens))
        self._raise_dml_errors(vdml.merge_errors(merge))
        return merge

    def _parse_vertica_merge_whens(self) -> exp.Whens:
        whens: list[exp.When] = []
        while self._match(TokenType.WHEN):
            matched = not self._match(TokenType.NOT)
            if not self._match_text_seq("MATCHED"):
                self.raise_error("Vertica MERGE WHEN requires MATCHED or NOT MATCHED")
            if self._match_text_seq("BY", advance=False):
                self.raise_error("Vertica MERGE does not support MATCHED BY SOURCE or TARGET")

            condition = self._parse_disjunction() if self._match(TokenType.AND) else None
            if not self._match(TokenType.THEN):
                self.raise_error("Vertica MERGE matching clauses require THEN")

            if matched:
                if not self._match(TokenType.UPDATE):
                    self.raise_error("Vertica WHEN MATCHED requires UPDATE")
                if not self._match(TokenType.SET):
                    self.raise_error("Vertica MERGE UPDATE requires SET")
                action: exp.Expr = self.expression(
                    exp.Update(
                        expressions=self._parse_csv(self._parse_equality),
                        where=self._parse_where(),
                    )
                )
            else:
                if not self._match(TokenType.INSERT):
                    self.raise_error("Vertica WHEN NOT MATCHED requires INSERT")
                columns = (
                    self._parse_value(values=False)
                    if self._match(TokenType.L_PAREN, advance=False)
                    else None
                )
                if not self._match_text_seq("VALUES"):
                    self.raise_error("Vertica MERGE INSERT requires VALUES")
                if not self._match(TokenType.L_PAREN, advance=False):
                    self.raise_error("Vertica MERGE INSERT VALUES requires parentheses")
                action = self.expression(
                    exp.Insert(
                        this=columns,
                        expression=self._parse_value(),
                        where=self._parse_where(),
                    )
                )

            whens.append(
                self.expression(exp.When(matched=matched, condition=condition, then=action))
            )

        if not whens:
            self.raise_error("Vertica MERGE requires at least one matching clause")
        return self.expression(exp.Whens(expressions=whens))

    def _parse_update(self) -> exp.Update:
        if not self._curr or self._match(TokenType.SET, advance=False):
            self.raise_error("Vertica UPDATE requires a table target")
        update = super()._parse_update()
        from_ = update.args.get("from_")
        if isinstance(from_, exp.From) and isinstance(from_.this, exp.Table):
            table = from_.this
            identifier = table.this
            if (
                isinstance(identifier, exp.Identifier)
                and identifier.name.upper() == "DEFAULT"
                and not identifier.args.get("quoted")
                and not table.args.get("alias")
                and not table.args.get("catalog")
                and not table.args.get("db")
            ):
                joins = table.args.pop("joins", None) or []
                relation = vexp.UpdateDefaultRelation(joins=joins)
                relation.comments = table.pop_comments()
                relation.meta.update(table.meta)
                from_.set("this", relation)

        self._raise_dml_errors(vdml.update_errors(update))
        return update

    def _parse_delete(self) -> exp.Delete:
        index = self._index
        self._parse_hint()
        has_from = self._match(TokenType.FROM, advance=False)
        self._retreat(index)
        if not has_from:
            self.raise_error("Vertica DELETE requires FROM")

        delete = super()._parse_delete()
        self._raise_dml_errors(vdml.delete_errors(delete))
        return delete

    def _parse_truncate_table(self) -> exp.TruncateTable | exp.Expr | None:
        if self._match(TokenType.L_PAREN, advance=False):
            return super()._parse_truncate_table()
        if not self._match(TokenType.TABLE):
            self.raise_error("Vertica TRUNCATE requires TABLE")

        table = self._parse_table(schema=True)
        if table is None:
            self.raise_error("Vertica TRUNCATE TABLE requires a table")
        if self._curr:
            self.raise_error(f"Unexpected Vertica TRUNCATE clause: {self._curr.text}")

        truncate = self.expression(exp.TruncateTable(expressions=[table]))
        self._raise_dml_errors(vdml.truncate_errors(truncate))
        return truncate

    def _parse_grant(self) -> exp.Grant:
        if self._match_text_seq("AUTHENTICATION"):
            return self._parse_authentication_grant()

        if not self._security_is_object_form("TO"):
            return self._parse_role_grant()

        privileges = self._parse_security_privileges(grant=True)
        if not self._match(TokenType.ON):
            self.raise_error("Object GRANT requires ON")

        target = self._parse_security_privilege_target()
        self._validate_security_privileges(privileges, target, grant=True)
        if not self._match_text_seq("TO"):
            self.raise_error("Object GRANT requires TO")

        principals = self._parse_security_principals("GRANT principal")
        grant_option = self._match_text_seq("WITH", "GRANT", "OPTION")
        if target.args.get("kind") == "WORKLOAD":
            if len(principals) != 1:
                self.raise_error("WORKLOAD GRANT requires exactly one principal")
            if grant_option:
                self.raise_error("WORKLOAD GRANT does not support WITH GRANT OPTION")

        if self._curr:
            self.raise_error(f"Unexpected GRANT clause: {self._curr.text}")

        kind, securable = self._canonical_security_target(target)
        return self.expression(
            exp.Grant(
                privileges=privileges,
                kind=kind,
                securable=securable,
                principals=principals,
                grant_option=grant_option,
            )
        )

    def _parse_revoke(self) -> exp.Revoke:
        if self._match_text_seq("AUTHENTICATION"):
            return self._parse_authentication_revoke()

        if self._match_text_seq("ADMIN", advance=False):
            if not self._match_text_seq("ADMIN", "OPTION", "FOR"):
                self.raise_error("Role REVOKE requires ADMIN OPTION FOR")
            return self._parse_role_revoke(admin_option=True)

        grant_option = False
        if self._match_text_seq("GRANT", advance=False):
            if not self._match_text_seq("GRANT", "OPTION", "FOR"):
                self.raise_error("Object REVOKE requires GRANT OPTION FOR")
            grant_option = True

        if not grant_option and not self._security_is_object_form("FROM"):
            return self._parse_role_revoke(admin_option=False)

        privileges = self._parse_security_privileges(grant=False)
        if not self._match(TokenType.ON):
            self.raise_error("Object REVOKE requires ON")

        target = self._parse_security_privilege_target()
        self._validate_security_privileges(privileges, target, grant=False)
        if not self._match(TokenType.FROM):
            self.raise_error("Object REVOKE requires FROM")

        principals = self._parse_security_principals("REVOKE principal")
        cascade = "CASCADE" if self._match_text_seq("CASCADE") else None
        if target.args.get("kind") == "WORKLOAD":
            if len(principals) != 1:
                self.raise_error("WORKLOAD REVOKE requires exactly one principal")
            if grant_option or cascade:
                self.raise_error("WORKLOAD REVOKE does not support grant options or CASCADE")

        if self._curr:
            self.raise_error(f"Unexpected REVOKE clause: {self._curr.text}")

        kind, securable = self._canonical_security_target(target)
        return self.expression(
            exp.Revoke(
                privileges=privileges,
                kind=kind,
                securable=securable,
                principals=principals,
                grant_option=grant_option,
                cascade=cascade,
            )
        )

    def _security_is_object_form(self, principal_keyword: str) -> bool:
        for token in self._tokens[self._index :]:
            if token.token_type == TokenType.ON:
                return True
            if (
                token.token_type not in self.TEXT_MATCH_EXCLUDED_TOKENS
                and token.text.upper() == principal_keyword
            ):
                return False
        return False

    def _parse_role_grant(self) -> vexp.RoleGrant:
        roles = self._parse_security_identifiers("role")
        if not self._match_text_seq("TO"):
            self.raise_error("Role GRANT requires TO")

        principals = self._parse_security_principals("role grantee")
        admin_option = self._match_text_seq("WITH", "ADMIN", "OPTION")
        if self._curr:
            self.raise_error(f"Unexpected role GRANT clause: {self._curr.text}")

        return self.expression(
            vexp.RoleGrant(
                roles=roles,
                principals=principals,
                admin_option=admin_option,
            )
        )

    def _parse_role_revoke(self, admin_option: bool) -> vexp.RoleRevoke:
        roles = self._parse_security_identifiers("role")
        if not self._match(TokenType.FROM):
            self.raise_error("Role REVOKE requires FROM")

        principals = self._parse_security_principals("role grantee")
        cascade = "CASCADE" if self._match_text_seq("CASCADE") else None
        if self._curr:
            self.raise_error(f"Unexpected role REVOKE clause: {self._curr.text}")

        return self.expression(
            vexp.RoleRevoke(
                roles=roles,
                principals=principals,
                admin_option=admin_option,
                cascade=cascade,
            )
        )

    def _parse_authentication_grant(self) -> vexp.AuthenticationGrant:
        authentication = self._parse_security_identifier("authentication method")
        if not self._match_text_seq("TO"):
            self.raise_error("AUTHENTICATION GRANT requires TO")

        principals = self._parse_security_principals("authentication grantee")
        if self._curr:
            self.raise_error(f"Unexpected AUTHENTICATION GRANT clause: {self._curr.text}")
        return self.expression(vexp.AuthenticationGrant(this=authentication, principals=principals))

    def _parse_authentication_revoke(self) -> vexp.AuthenticationRevoke:
        authentication = self._parse_security_identifier("authentication method")
        if not self._match(TokenType.FROM):
            self.raise_error("AUTHENTICATION REVOKE requires FROM")

        principals = self._parse_security_principals("authentication grantee")
        if self._curr:
            self.raise_error(f"Unexpected AUTHENTICATION REVOKE clause: {self._curr.text}")
        return self.expression(
            vexp.AuthenticationRevoke(this=authentication, principals=principals)
        )

    def _parse_security_identifier(self, label: str) -> exp.Identifier:
        if self._curr.token_type == TokenType.STRING or self._match_texts(
            {"CASCADE", "FOR", "FROM", "ON", "RESTRICT", "TO", "WITH"},
            advance=False,
        ):
            self.raise_error(f"Expected {label}")

        identifier = self._parse_id_var(any_token=True)
        if not isinstance(identifier, exp.Identifier):
            self.raise_error(f"Expected {label}")
        assert isinstance(identifier, exp.Identifier)
        return identifier

    def _parse_security_identifiers(self, label: str) -> list[exp.Identifier]:
        identifiers = [self._parse_security_identifier(label)]
        while self._match(TokenType.COMMA):
            identifiers.append(self._parse_security_identifier(label))
        return identifiers

    def _parse_security_principals(self, label: str) -> list[exp.GrantPrincipal]:
        return [
            self.expression(exp.GrantPrincipal(this=identifier))
            for identifier in self._parse_security_identifiers(label)
        ]

    def _parse_security_privileges(self, grant: bool) -> list[exp.GrantPrivilege]:
        if self._match_text_seq("ALL"):
            privileges_keyword = self._match_text_seq("PRIVILEGES")
            extend = self._match_text_seq("EXTEND")
            if extend and not grant:
                self.raise_error("EXTEND is only valid in GRANT ALL")
            if self._match(TokenType.COMMA, advance=False):
                self.raise_error("ALL cannot be combined with explicit privileges")

            if extend:
                return [
                    self.expression(
                        vexp.ExtendedGrantPrivilege(
                            this=exp.var("ALL"),
                            privileges=privileges_keyword,
                            extend=True,
                        )
                    )
                ]

            privilege_name = "ALL PRIVILEGES" if privileges_keyword else "ALL"
            return [self.expression(exp.GrantPrivilege(this=exp.var(privilege_name)))]

        privileges: list[exp.GrantPrivilege] = []
        while True:
            if not self._curr or self._curr.token_type in self.PRIVILEGE_FOLLOW_TOKENS:
                self.raise_error("Expected a privilege name")
            privilege = t.cast(exp.GrantPrivilege, self._parse_grant_privilege())
            words = set(privilege.name.upper().split())
            if "ALL" in words:
                self.raise_error("ALL cannot be combined with explicit privileges")
            if "EXTEND" in words:
                self.raise_error("EXTEND is only valid after GRANT ALL [PRIVILEGES]")
            privileges.append(privilege)
            if not self._match(TokenType.COMMA):
                break
        return privileges

    def _parse_security_privilege_target(self) -> vexp.VerticaPrivilegeTarget:
        if self._match_text_seq("ALL"):
            if not self._match_texts({"FUNCTIONS", "SEQUENCES", "TABLES"}):
                self.raise_error("Expected FUNCTIONS, SEQUENCES, or TABLES after ON ALL")
            plural_kind = self._prev.text.upper()
            if not self._match_text_seq("IN", "SCHEMA"):
                self.raise_error("ALL object targets require IN SCHEMA")
            schemas = self._parse_security_named_targets("schema")
            return self.expression(
                vexp.VerticaPrivilegeTarget(
                    kind=plural_kind.removesuffix("S"),
                    expressions=schemas,
                    all_in_schema=True,
                )
            )

        if self._match_text_seq("RESOURCE", "POOL"):
            pools = self._parse_security_named_targets("resource pool")
            subcluster = None
            current_subcluster = False
            if self._match_text_seq("FOR"):
                if self._match_text_seq("CURRENT", "SUBCLUSTER"):
                    current_subcluster = True
                elif self._match_text_seq("SUBCLUSTER"):
                    subcluster = self._parse_security_identifier("subcluster")
                else:
                    self.raise_error("Expected SUBCLUSTER or CURRENT SUBCLUSTER after FOR")
            return self.expression(
                vexp.VerticaPrivilegeTarget(
                    kind="RESOURCE POOL",
                    expressions=pools,
                    subcluster=subcluster,
                    current_subcluster=current_subcluster,
                )
            )

        if self._match_text_seq("LOCATION"):
            path = self._parse_string()
            if not isinstance(path, exp.Literal) or not path.is_string:
                self.raise_error("LOCATION privilege target requires a string path")
            node = (
                self._parse_security_identifier("location node")
                if self._match(TokenType.ON)
                else None
            )
            return self.expression(
                vexp.VerticaPrivilegeTarget(
                    kind="LOCATION",
                    expressions=[path],
                    node=node,
                )
            )

        if self._match_text_seq("ROUTING", "RULE") or self._match_text_seq("WORKLOAD"):
            workload = self._parse_security_identifier("workload")
            if self._match(TokenType.DOT, advance=False):
                self.raise_error("WORKLOAD privilege names cannot be schema-qualified")
            return self.expression(
                vexp.VerticaPrivilegeTarget(
                    kind="WORKLOAD",
                    expressions=[self.expression(exp.Table(this=workload))],
                )
            )

        routine_kind = self._parse_security_routine_kind()
        if routine_kind:
            signatures = [self._parse_security_routine_signature()]
            while self._match(TokenType.COMMA):
                signatures.append(self._parse_security_routine_signature())
            return self.expression(
                vexp.VerticaPrivilegeTarget(kind=routine_kind, expressions=signatures)
            )

        if self._match_text_seq("TLS", "CONFIGURATION"):
            kind = "TLS CONFIGURATION"
        elif self._match_text_seq("DATA", "LOADER"):
            kind = "DATA LOADER"
        elif self._match_texts(self.SECURITY_NAMED_TARGET_KINDS):
            kind = self._prev.text.upper()
        else:
            kind = ""

        targets = self._parse_security_named_targets("privilege target")
        return self.expression(vexp.VerticaPrivilegeTarget(kind=kind, expressions=targets))

    def _parse_security_named_target(self, label: str) -> exp.Expr:
        if self._match_texts({"FOR", "FROM", "TO", "WITH"}, advance=False):
            self.raise_error(f"Expected {label}")
        target = self._parse_table_parts(schema=True)
        if not isinstance(target, (exp.Table, exp.Dot)):
            self.raise_error(f"Expected {label}")
        assert isinstance(target, (exp.Table, exp.Dot))
        return target

    def _parse_security_named_targets(self, label: str, multiple: bool = True) -> list[exp.Expr]:
        targets = [self._parse_security_named_target(label)]
        while multiple and self._match(TokenType.COMMA):
            targets.append(self._parse_security_named_target(label))
        return targets

    def _parse_security_routine_kind(self) -> str | None:
        for kind in self.SECURITY_ROUTINE_KINDS:
            if self._match_text_seq(*kind.split()):
                return kind
        return None

    def _parse_security_routine_signature(self) -> vexp.RoutineSignature:
        name = self._parse_security_named_target("routine name")
        if not self._match(TokenType.L_PAREN):
            self.raise_error("Routine privilege targets require an argument signature")

        arguments: list[exp.Expr] = []
        if not self._match(TokenType.R_PAREN):
            arguments.append(self._parse_security_routine_argument())
            while self._match(TokenType.COMMA):
                arguments.append(self._parse_security_routine_argument())
            self._match_r_paren()

        return self.expression(vexp.RoutineSignature(this=name, expressions=arguments))

    def _parse_security_routine_argument(self) -> exp.Expr:
        unnamed = self._try_parse(self._parse_unnamed_security_routine_argument)
        if unnamed:
            return unnamed

        name = self._parse_security_identifier("routine argument name")
        data_type = self._parse_types()
        if not isinstance(data_type, exp.DataType):
            self.raise_error("Expected a routine argument type")
        if self._curr.token_type not in {TokenType.COMMA, TokenType.R_PAREN}:
            self.raise_error("Unexpected tokens after routine argument type")
        assert isinstance(data_type, exp.DataType)
        return self.expression(exp.ColumnDef(this=name, kind=data_type))

    def _parse_unnamed_security_routine_argument(self) -> exp.DataType:
        data_type = self._parse_types()
        if not isinstance(data_type, exp.DataType):
            self.raise_error("Expected a routine argument type")
        if self._curr.token_type not in {TokenType.COMMA, TokenType.R_PAREN}:
            self.raise_error("Routine argument has a name")
        assert isinstance(data_type, exp.DataType)
        return data_type

    def _validate_security_privileges(
        self,
        privileges: list[exp.GrantPrivilege],
        target: vexp.VerticaPrivilegeTarget,
        grant: bool,
    ) -> None:
        kind = target.args.get("kind") or "TABLE"
        assert isinstance(kind, str)
        is_all = len(privileges) == 1 and privileges[0].name.upper().startswith("ALL")

        if (
            any(isinstance(privilege, vexp.ExtendedGrantPrivilege) for privilege in privileges)
            and kind in self.SECURITY_EXTEND_DISALLOWED
        ):
            self.raise_error(f"{kind} privileges do not support EXTEND")

        if is_all:
            if kind == "WORKLOAD" or (grant and kind == "RESOURCE POOL"):
                self.raise_error(f"{kind} does not support GRANT ALL")
            return

        allowed = self.SECURITY_EXACT_PRIVILEGES.get(kind)
        if allowed is None:
            return
        if kind == "WORKLOAD" and len(privileges) != 1:
            self.raise_error("WORKLOAD requires exactly one USAGE privilege")
        for privilege in privileges:
            if privilege.name.upper() not in allowed or privilege.expressions:
                self.raise_error(f"Invalid {kind} privilege: {privilege.name}")

    def _canonical_security_target(
        self, target: vexp.VerticaPrivilegeTarget
    ) -> tuple[str | None, exp.Expr]:
        kind_value = target.args.get("kind")
        kind = kind_value if isinstance(kind_value, str) and kind_value else None
        custom_kinds = {*self.SECURITY_ROUTINE_KINDS, "LOCATION", "WORKLOAD"}
        if (
            len(target.expressions) != 1
            or target.args.get("all_in_schema")
            or target.args.get("subcluster")
            or target.args.get("current_subcluster")
            or target.args.get("node")
            or kind in custom_kinds
        ):
            return None, target
        return kind, target.expressions[0]

    def _parse_function_arguments_with_parameters(
        self, alias: bool
    ) -> tuple[list[exp.Expr], list[exp.PropertyEQ], exp.Var | None]:
        """Parse arguments plus one of Vertica's trailing function modifiers."""

        args: list[exp.Expr] = []
        if self._curr.token_type != TokenType.R_PAREN and not self._match_text_seq(
            "USING", "PARAMETERS", advance=False
        ):
            args = self._parse_function_args(alias)

        parameters: list[exp.PropertyEQ] = []
        if self._match_text_seq("USING", "PARAMETERS"):
            while True:
                name = self._parse_id_var(any_token=True)
                if not isinstance(name, exp.Identifier) or not self._match(TokenType.EQ):
                    self.raise_error("Expected parameter=value after USING PARAMETERS")

                value = self._parse_disjunction()
                if value is None:
                    self.raise_error("Expected a value after USING PARAMETERS name=")

                parameters.append(self.expression(exp.PropertyEQ(this=name, expression=value)))
                if not self._match(TokenType.COMMA):
                    break

        string_unit = None if parameters else self._parse_string_unit()
        return args, parameters, string_unit

    def _parse_string_unit(self) -> exp.Var | None:
        """Parse ``USING CHARACTERS|OCTETS`` without accepting unknown units."""

        if not self._match_text_seq("USING"):
            return None

        if self._match_texts(("CHARACTERS", "OCTETS")):
            return self.expression(exp.var(self._prev.text.upper()))

        self.raise_error("Expected CHARACTERS or OCTETS after USING")
        return None

    def _parse_string_unit_function(self, function: exp.Expr, name: str) -> exp.Expr:
        """Attach a string-unit modifier to a specialized function parser."""

        unit = self._parse_string_unit()
        if unit is None:
            return function
        return self.expression(vexp.StringUnit(this=function, unit=unit, name=exp.var(name)))

    def _parse_function_call(
        self,
        functions: dict[str, t.Callable[..., exp.Expr]] | None = None,
        anonymous: bool = False,
        optional_parens: bool = True,
        any_token: bool = False,
    ) -> exp.Expr | None:
        """Parse a function call, retaining a generic USING PARAMETERS clause.

        This is intentionally kept aligned with SQLGlot 30.13's implementation;
        the only semantic addition is parsing and wrapping ``USING PARAMETERS``
        before window-clause handling.
        """

        if not self._curr:
            return None

        comments = self._curr.comments
        prev = self._prev
        token = self._curr
        token_type = self._curr.token_type
        this: str | exp.Expr = self._curr.text
        upper = self._curr.text.upper()

        after_dot = prev.token_type == TokenType.DOT
        parser = self.NO_PAREN_FUNCTION_PARSERS.get(upper)
        if (
            optional_parens
            and parser
            and token_type not in self.INVALID_FUNC_NAME_TOKENS
            and not after_dot
        ):
            self._advance()
            return self._parse_window(parser(self))

        if self._next.token_type != TokenType.L_PAREN:
            if optional_parens and token_type in self.NO_PAREN_FUNCTIONS and not after_dot:
                self._advance()
                return self.expression(t.cast(exp.Expr, self.NO_PAREN_FUNCTIONS[token_type]()))
            return None

        if any_token:
            if token_type in self.RESERVED_TOKENS:
                return None
        elif token_type not in self.FUNC_TOKENS:
            return None

        self._advance(2)

        parameters: list[exp.PropertyEQ] = []
        string_unit = None
        parser = self.FUNCTION_PARSERS.get(upper)
        if parser and not anonymous:
            result = parser(self)
        else:
            subquery_predicate = self.SUBQUERY_PREDICATES.get(token_type)
            if subquery_predicate:
                predicate_expression = None
                if self._curr.token_type in self.SUBQUERY_TOKENS:
                    predicate_expression = self._parse_select()
                    self._match_r_paren()
                elif prev and prev.token_type in (TokenType.LIKE, TokenType.ILIKE):
                    self._advance(-1)
                    predicate_expression = self._parse_bitwise()

                if predicate_expression:
                    return self.expression(
                        subquery_predicate(this=predicate_expression), comments=comments
                    )

            functions = functions or self.FUNCTIONS
            function = functions.get(upper)
            known_function = function and not anonymous

            alias = not known_function or upper in self.FUNCTIONS_WITH_ALIASED_ARGS
            args, parameters, string_unit = self._parse_function_arguments_with_parameters(alias)

            post_func_comments = self._curr.comments if self._curr else None
            if (
                known_function
                and post_func_comments
                and any(
                    comment.lstrip().startswith(exp.SQLGLOT_ANONYMOUS)
                    for comment in post_func_comments
                )
            ):
                known_function = False

            if alias and known_function:
                args = self._kv_to_prop_eq(args)

            if known_function:
                func_builder = t.cast(t.Callable[..., exp.Expr], function)
                try:
                    func = func_builder(args)
                except TypeError:
                    func = func_builder(args, dialect=self.dialect)

                func = self.validate_expression(func, args)
                if self.dialect.PRESERVE_ORIGINAL_NAMES:
                    func.meta["name"] = this
                result = func
            else:
                if token_type == TokenType.IDENTIFIER:
                    this = exp.Identifier(this=this, quoted=True).update_positions(token)
                result = self.expression(exp.Anonymous(this=this, expressions=args))

            result = result.update_positions(token)
            if parameters:
                result = self.expression(
                    vexp.UsingParameters(this=result, parameters=parameters)
                ).update_positions(token)
            elif string_unit:
                result = self.expression(
                    vexp.StringUnit(
                        this=result,
                        unit=string_unit,
                        name=exp.var(upper),
                    )
                ).update_positions(token)

        if isinstance(result, exp.Expr):
            result.add_comments(comments)

        if parser:
            self._match(TokenType.R_PAREN, expression=result)
        else:
            self._match_r_paren(result)
        return self._parse_window(result)

    def _parse_window_partition_mode(self) -> exp.Var | None:
        """Parse Vertica's execution-oriented window partition modes."""

        if not self._match(TokenType.PARTITION):
            return None

        if self._match_texts(("BEST", "NODES")) or self._match(TokenType.ROW):
            return self.expression(exp.var(self._prev.text.upper()))

        if self._match(TokenType.LEFT):
            if not self._match(TokenType.JOIN):
                self.raise_error("Expected JOIN after PARTITION LEFT")
            return self.expression(exp.var("LEFT JOIN"))

        self.raise_error("Expected BEST, NODES, ROW, or LEFT JOIN after PARTITION")
        return self.expression(exp.var(""))

    def _parse_window(self, this: exp.Expr | None, alias: bool = False) -> exp.Expr | None:
        """Parse a window, including Vertica's special partition modes.

        This follows SQLGlot 30.13's window parser. The only AST extension is
        :class:`VerticaWindow` when the grammar contains ``PARTITION BEST``,
        ``NODES``, ``ROW``, or ``LEFT JOIN``.
        """

        func = this
        comments = func.comments if isinstance(func, exp.Expr) else None

        if self._match_text_seq("WITHIN", "GROUP"):
            order = self._parse_wrapped(self._parse_order)
            this = self.expression(exp.WithinGroup(this=this, expression=order))

        if self._match_pair(TokenType.FILTER, TokenType.L_PAREN):
            self._match(TokenType.WHERE)
            this = self.expression(
                exp.Filter(this=this, expression=self._parse_where(skip_where_token=True))
            )
            self._match_r_paren()

        if isinstance(this, exp.AggFunc):
            ignore_respect = this.find(exp.IgnoreNulls, exp.RespectNulls)
            if ignore_respect:
                ignore_respect.replace(ignore_respect.this)
                this = self.expression(ignore_respect.__class__(this=this))

        this = self._parse_respect_or_ignore_nulls(this)

        if alias:
            over = None
            self._match(TokenType.ALIAS)
        elif not self._match_set(self.WINDOW_BEFORE_PAREN_TOKENS):
            return this
        else:
            over = self._prev.text.upper()

        if comments and isinstance(func, exp.Expr):
            func.pop_comments()

        if not self._match(TokenType.L_PAREN):
            return self.expression(
                exp.Window(this=this, alias=self._parse_id_var(False), over=over),
                comments=comments,
            )

        window_alias = (
            None
            if self._curr.token_type == TokenType.PARTITION
            else self._parse_id_var(
                any_token=False,
                tokens=self.WINDOW_ALIAS_TOKENS,
            )
        )

        first: bool | None = True if self._match(TokenType.FIRST) else None
        if self._match_text_seq("LAST"):
            first = False

        partition_mode = self._parse_window_partition_mode()
        if partition_mode:
            partition: list[exp.Expr] = []
            order = self._parse_order()
        else:
            partition, order = self._parse_partition_and_order()

        kind = (
            self._match_set((TokenType.ROWS, TokenType.RANGE)) or self._match_text_seq("GROUPS")
        ) and self._prev.text

        if kind:
            self._match(TokenType.BETWEEN)
            start = self._parse_window_spec()
            end = self._parse_window_spec() if self._match(TokenType.AND) else {}
            exclude = (
                self._parse_var_from_options(self.WINDOW_EXCLUDE_OPTIONS)
                if self._match_text_seq("EXCLUDE")
                else None
            )
            spec = self.expression(
                exp.WindowSpec(
                    kind=kind,
                    start=start["value"],
                    start_side=start["side"],
                    end=end.get("value"),
                    end_side=end.get("side"),
                    exclude=exclude,
                )
            )
        else:
            spec = None

        self._match_r_paren()

        window_args = {
            "this": this,
            "partition_by": partition,
            "order": order,
            "spec": spec,
            "alias": window_alias,
            "over": over,
            "first": first,
        }
        window_expression = (
            vexp.VerticaWindow(partition_mode=partition_mode, **window_args)
            if partition_mode
            else exp.Window(**window_args)
        )
        window = self.expression(
            window_expression,
            comments=comments,
        )

        if self._match_set(self.WINDOW_BEFORE_PAREN_TOKENS, advance=False):
            return self._parse_window(window, alias=alias)

        return window

    def _parse_sysdate(self) -> vexp.StatementTimestamp:
        if self._match(TokenType.L_PAREN):
            self._match_r_paren()
        return self.expression(vexp.StatementTimestamp())

    def _parse_vertica_listagg(self) -> vexp.ListAgg:
        this = self._parse_disjunction()
        if not this:
            self.raise_error("LISTAGG requires an aggregate expression")

        # Retain the conventional two-argument form for SQLGlot interoperability,
        # while representing Vertica's documented USING PARAMETERS form explicitly.
        separator = None
        if self._match(TokenType.COMMA):
            separator = self._parse_disjunction()
            if not separator:
                self.raise_error("Expected a LISTAGG separator after comma")

        parameters: list[exp.EQ] = []
        if self._match_text_seq("USING", "PARAMETERS"):
            while True:
                name = self._parse_id_var(any_token=True)
                if not name or not self._match(TokenType.EQ):
                    self.raise_error("Expected parameter=value after LISTAGG USING PARAMETERS")

                value = self._parse_disjunction()
                if not value:
                    self.raise_error("Expected a value for LISTAGG parameter")
                parameters.append(self.expression(exp.EQ(this=name, expression=value)))

                if not self._match(TokenType.COMMA):
                    break

        aggregate = self.expression(exp.GroupConcat(this=this, separator=separator))
        return self.expression(vexp.ListAgg(this=aggregate, parameters=parameters))

    def _parse_unary(self) -> exp.Expr | None:
        index = self._index
        this = super()._parse_unary()
        while this is not None and self._curr and self._curr.text == "!":
            self._advance()
            this = self.expression(exp.Factorial(this=this))
        return self._lift_trailing_directed_comments(this, index)

    def _parse_type(
        self, parse_interval: bool = True, fallback_to_identifier: bool = False
    ) -> exp.Expr | None:
        index = self._index
        expression = super()._parse_type(
            parse_interval=parse_interval,
            fallback_to_identifier=fallback_to_identifier,
        )
        return self._lift_trailing_directed_comments(expression, index)

    def _lift_trailing_directed_comments(
        self, expression: exp.Expr | None, token_index: int
    ) -> exp.Expr | None:
        if expression is None or self._index <= token_index:
            return expression

        trailing_token = self._tokens[self._index - 1]
        markers: list[str] = [
            comment
            for comment in trailing_token.comments
            if isinstance(comment, DirectedPostfixComment)
        ]
        if not markers:
            return expression

        marker_set = set(markers)
        for node in expression.walk():
            if node.comments:
                node.comments = [
                    comment for comment in node.comments if comment not in marker_set
                ] or None
        expression.add_comments(markers)
        return expression

    def _parse_alias(self, this: exp.Expr | None, explicit: bool = False) -> exp.Expr | None:
        if this is not None and any(
            isinstance(comment, DirectedPostfixComment) for comment in this.comments or ()
        ):
            holder = exp.Paren(this=this)
            self._structure_directed_constant_hints(holder)
            this = holder.this.pop()

        alias = super()._parse_alias(this, explicit=explicit)
        if (
            isinstance(alias, exp.Alias)
            and isinstance(alias.this, exp.Struct)
            and self._match(TokenType.L_PAREN, advance=False)
        ):
            columns = self._parse_wrapped_csv(lambda: self._parse_id_var(any_token=True))
            if not columns:
                self.raise_error("ROW alias field list cannot be empty")
            return self.expression(
                vexp.RowAlias(
                    this=alias.this,
                    alias=alias.args.get("alias"),
                    columns=columns,
                ),
                comments=alias.pop_comments(),
            )
        return alias

    def _parse_interval_precision(self) -> exp.Literal | None:
        if not self._match(TokenType.L_PAREN):
            return None

        precision = self._parse_number()
        if not isinstance(precision, exp.Literal) or not precision.is_int:
            self.raise_error("Interval precision must be an integer from 0 through 6")
        self._match_r_paren()

        assert isinstance(precision, exp.Literal)
        if not 0 <= int(precision.this) <= 6:
            self.raise_error("Interval precision must be an integer from 0 through 6")
        return precision

    def _parse_interval_unit(self) -> exp.Expr | None:
        unit_name = self._curr.text.upper()
        if unit_name not in self.INTERVAL_QUALIFIER_ENDS:
            return None

        self._advance()
        precision = self._parse_interval_precision()
        if precision is not None and unit_name != "SECOND":
            self.raise_error("Only SECOND can specify interval qualifier precision")

        unit: exp.Expr = (
            self.expression(exp.Second(this=precision))
            if precision is not None
            else self.expression(exp.var(unit_name))
        )
        if not self._match_text_seq("TO"):
            return unit

        end_name = self._curr.text.upper()
        if end_name not in self.INTERVAL_QUALIFIER_ENDS[unit_name]:
            self.raise_error(f"Invalid interval qualifier {unit_name} TO {end_name}")

        self._advance()
        end_precision = self._parse_interval_precision()
        if end_precision is not None and end_name != "SECOND":
            self.raise_error("Only SECOND can specify interval qualifier precision")
        end: exp.Expr = (
            self.expression(exp.Second(this=end_precision))
            if end_precision is not None
            else self.expression(exp.var(end_name))
        )
        return self.expression(exp.IntervalSpan(this=unit, expression=end))

    def _parse_interval(self, require_interval: bool = True) -> exp.Add | exp.Interval | None:
        index = self._index
        intervalym = self._curr.text.upper() == "INTERVALYM"
        if require_interval:
            if self._curr.token_type != TokenType.INTERVAL:
                return None
            self._advance()

        precision = None if intervalym else self._parse_interval_precision()
        this = self._parse_primary() if self._curr.token_type == TokenType.STRING else None
        if this is None:
            self._retreat(index)
            return None

        if intervalym:
            unit: exp.Expr | None = self.expression(
                exp.IntervalSpan(this=exp.var("YEAR"), expression=exp.var("MONTH"))
            )
        else:
            unit = self._parse_interval_unit()

        if precision is not None:
            return self.expression(vexp.VerticaInterval(this=this, unit=unit, precision=precision))
        return self.expression(exp.Interval(this=this, unit=unit))

    def _parse_copy(self) -> exp.Copy | exp.Command:
        """Parse COPY without degrading recognized Vertica syntax to Command."""

        hint = self._parse_hint()

        target = self._parse_table_parts(schema=True)
        if not target:
            self.raise_error("COPY requires a target table")
        assert target is not None

        definition = self._parse_copy_definition(context="copy")
        return self.expression(
            vexp.VerticaCopy(
                this=target,
                hint=hint,
                expressions=definition.args.get("expressions"),
                column_options=definition.args.get("column_options"),
                source=definition.args.get("source"),
                format=definition.args.get("format"),
                params=definition.args.get("params"),
                no_commit=definition.args.get("no_commit"),
            )
        )

    def _parse_copy_definition(
        self, context: t.Literal["copy", "external", "flexible"]
    ) -> vexp.ExternalCopyDefinition:
        """Parse the target-independent portion shared by COPY and external tables."""

        external = context != "copy"
        flexible = context == "flexible"

        has_columns = self._match(TokenType.L_PAREN, advance=False)
        columns = (
            self._parse_wrapped_csv(lambda: self._parse_copy_column(allow_transform=True))
            if has_columns
            else []
        )
        if has_columns and not columns:
            label = "Flexible COPY" if flexible else "COPY target"
            self.raise_error(f"{label} column lists cannot be empty")
        self._validate_copy_columns(columns, column_options=False)

        column_options: list[vexp.CopyColumn] = []
        if self._match_text_seq("COLUMN", "OPTION"):
            if flexible:
                self.raise_error("Flexible external tables do not support COLUMN OPTION")
            column_options = self._parse_wrapped_csv(
                lambda: self._parse_copy_column(allow_transform=False)
            )
            if not column_options:
                self.raise_error("COLUMN OPTION lists cannot be empty")
            self._validate_copy_columns(column_options, column_options=True)

        has_from = self._match(TokenType.FROM)
        if not has_from and not (
            context == "external"
            and (
                self._match_text_seq("WITH", "SOURCE", advance=False)
                or self._match_text_seq("SOURCE", advance=False)
            )
        ):
            self.raise_error("COPY requires FROM or a user-defined SOURCE")

        source = self._parse_copy_source()
        source_format = None if isinstance(source, vexp.CopyUDL) else self._parse_copy_format()

        params: list[exp.CopyParameter] = []
        no_commit = False
        while self._curr:
            if self._match_text_seq("NO", "COMMIT"):
                if external:
                    self.raise_error("External table COPY definitions do not support NO COMMIT")
                no_commit = True
                break

            parameter = self._parse_vertica_copy_parameter()
            if not parameter:
                self.raise_error(f"Unsupported COPY clause starting at {self._curr.text!r}")
            assert parameter is not None
            params.append(parameter)

        if self._curr:
            self.raise_error("NO COMMIT must be the final COPY clause")

        self._validate_copy_parameters(
            params,
            source=source,
            source_format=source_format,
            context=context,
            columns=columns,
        )
        parameter_order = (
            self.FLEXIBLE_COPY_PARAMETER_ORDER
            if flexible
            else self.EXTERNAL_COPY_PARAMETER_ORDER
            if external
            else self.COPY_PARAMETER_ORDER
        )
        params.sort(key=lambda parameter: parameter_order.get(parameter.name, 999))
        definition_type = vexp.FlexibleCopyDefinition if flexible else vexp.ExternalCopyDefinition
        return self.expression(
            definition_type(
                expressions=columns,
                column_options=column_options,
                source=source,
                format=source_format,
                params=params,
                no_commit=no_commit,
            )
        )

    def _validate_copy_parameters(
        self,
        params: list[exp.CopyParameter],
        source: exp.Expr,
        source_format: vexp.CopyFormat | None,
        context: t.Literal["copy", "external", "flexible"],
        columns: list[vexp.CopyColumn],
    ) -> None:
        """Reject contradictory, repeated, and out-of-order COPY options."""

        external = context != "copy"
        flexible = context == "flexible"

        names = [parameter.name for parameter in params]
        repeated = {name for name in names if names.count(name) > 1}
        if repeated:
            self.raise_error(f"COPY parameter cannot be repeated: {min(repeated)}")

        exclusive_groups = (
            {"ESCAPE AS", "NO ESCAPE"},
            {"REJECTED DATA", "REJECTED DATA AS TABLE"},
            {"AUTO", "DIRECT", "TRICKLE"},
        )
        for group in exclusive_groups:
            present = group.intersection(names)
            if len(present) > 1:
                self.raise_error(
                    f"COPY parameters are mutually exclusive: {', '.join(sorted(present))}"
                )

        if "EXCEPTIONS" in names and "REJECTED DATA AS TABLE" in names:
            self.raise_error("EXCEPTIONS cannot be combined with REJECTED DATA AS TABLE")

        parameter_order = (
            self.FLEXIBLE_COPY_PARAMETER_ORDER
            if flexible
            else self.EXTERNAL_COPY_PARAMETER_ORDER
            if external
            else self.COPY_PARAMETER_ORDER
        )
        if external:
            unsupported = set(names).difference(parameter_order)
            if unsupported:
                self.raise_error(
                    "External table COPY definition does not support: "
                    f"{', '.join(sorted(unsupported))}"
                )
            if isinstance(source, vexp.CopyStdin) or (
                isinstance(source, vexp.CopyFiles) and source.args.get("local")
            ):
                self.raise_error("External table COPY definitions do not support LOCAL or STDIN")

        if flexible:
            if isinstance(source, vexp.CopyFromVertica):
                self.raise_error("Flexible external tables do not support FROM VERTICA")

            if columns:
                raw_columns = [
                    column
                    for column in columns
                    if column.name.lower() == "__raw__"
                    and not column.args.get("expression")
                    and not any(
                        parameter.name == "FILLER" for parameter in column.args.get("params") or []
                    )
                ]
                if not raw_columns:
                    self.raise_error("Flexible COPY column lists require a plain __raw__ column")

            if isinstance(source, vexp.CopyFiles):
                if source.args.get("partition_by"):
                    self.raise_error("Flexible external tables do not support PARTITION COLUMNS")
                if any(
                    isinstance(copy_file.args.get("on"), vexp.CopyNodeSelection)
                    and copy_file.args["on"].args.get("kind") == "EACH"
                    for copy_file in source.expressions
                ):
                    self.raise_error("Flexible external tables do not support ON EACH NODE")
                if source_format is not None:
                    self.raise_error(
                        "Flexible external table files require a compatible PARSER, "
                        "not a built-in COPY format"
                    )
                if "PARSER" not in names:
                    self.raise_error("Flexible external table files require a compatible PARSER")
            elif isinstance(source, vexp.CopyUDL):
                if not source.args.get("parser"):
                    self.raise_error("Flexible external table UDL pipelines require a PARSER")

        positions = [parameter_order.get(name, 999) for name in names]
        if positions != sorted(positions):
            self.raise_error("COPY parameters are not in Vertica clause order")

        format_name = source_format.name.upper() if source_format else ""
        if format_name in {"ORC", "PARQUET"}:
            incompatible = {"ERROR TOLERANCE", "SKIP", "PARSER"}.intersection(names)
            if incompatible:
                self.raise_error(
                    f"{format_name} does not support: {', '.join(sorted(incompatible))}"
                )

        if format_name == "ORC" and isinstance(source, vexp.CopyFiles):
            for copy_file in source.expressions:
                compression = copy_file.args.get("compression")
                if isinstance(compression, exp.Expr) and compression.name.upper() != "UNCOMPRESSED":
                    self.raise_error("ORC does not support compressed COPY source files")

        if isinstance(source, vexp.CopyUDL) and "PARSER" in names:
            self.raise_error("A UDL source cannot also specify a trailing PARSER")

    def _validate_copy_columns(self, columns: list[vexp.CopyColumn], column_options: bool) -> None:
        if not columns:
            return

        if column_options:
            names = [column.name.lower() for column in columns]
            repeated = {name for name in names if names.count(name) > 1}
            if repeated:
                self.raise_error(f"COLUMN OPTION cannot repeat column: {min(repeated)}")
            return

        if any(column.args.get("expression") for column in columns) and not any(
            not column.args.get("expression") for column in columns
        ):
            self.raise_error("COPY transformations require at least one parsed or FILLER column")

    def _parse_copy_column(self, allow_transform: bool) -> vexp.CopyColumn | None:
        name = self._parse_id_var(any_token=True)
        if not name:
            return None

        transformation = None
        if self._match(TokenType.ALIAS):
            if not allow_transform:
                self.raise_error("COLUMN OPTION does not support AS transformations")
            transformation = self._parse_disjunction()
            if not transformation:
                self.raise_error("Expected an expression after COPY column AS")

        params: list[exp.CopyParameter] = []
        while parameter := self._parse_copy_column_parameter(allow_filler=allow_transform):
            params.append(parameter)

        parameter_names = [parameter.name for parameter in params]
        repeated = {name for name in parameter_names if parameter_names.count(name) > 1}
        if repeated:
            self.raise_error(f"COPY column parameter cannot be repeated: {min(repeated)}")

        names = set(parameter_names)
        if "ESCAPE AS" in names and "NO ESCAPE" in names:
            self.raise_error("COPY column cannot specify both ESCAPE and NO ESCAPE")

        positions = [self.COPY_COLUMN_PARAMETER_ORDER[name] for name in parameter_names]
        if positions != sorted(positions):
            self.raise_error("COPY column parameters are not in Vertica clause order")

        if transformation and "FILLER" in names:
            self.raise_error("A COPY column cannot be both a transformation and FILLER")
        if transformation and "FORMAT" in names:
            self.raise_error("A computed COPY column cannot specify FORMAT")

        filler = next((parameter for parameter in params if parameter.name == "FILLER"), None)
        filler_type = filler.args.get("expression") if filler else None
        if isinstance(filler_type, exp.DataType) and filler_type.this in {
            exp.DType.ARRAY,
            exp.DType.MAP,
            exp.DType.SET,
            exp.DType.STRUCT,
        }:
            self.raise_error("COPY FILLER columns cannot use complex data types")

        return self.expression(vexp.CopyColumn(this=name, expression=transformation, params=params))

    def _parse_copy_column_parameter(self, allow_filler: bool) -> exp.CopyParameter | None:
        name = None
        value = None

        if self._match_text_seq("DELIMITER"):
            self._match(TokenType.ALIAS)
            name, value = "DELIMITER", self._parse_string()
        elif self._match_text_seq("ENCLOSED"):
            self._match_text_seq("BY")
            name, value = "ENCLOSED BY", self._parse_string()
        elif self._match_text_seq("ENFORCELENGTH"):
            name = "ENFORCELENGTH"
        elif self._match_text_seq("ESCAPE"):
            self._match(TokenType.ALIAS)
            name, value = "ESCAPE AS", self._parse_string()
        elif self._match_text_seq("NO", "ESCAPE"):
            name = "NO ESCAPE"
        elif self._match_text_seq("FILLER"):
            if not allow_filler:
                self.raise_error("COLUMN OPTION does not support FILLER")
            name, value = "FILLER", self._parse_types(schema=True)
        elif self._match_text_seq("FORMAT"):
            name, value = "FORMAT", self._parse_string()
        elif self._match(TokenType.NULL):
            self._match(TokenType.ALIAS)
            name, value = "NULL AS", self._parse_string()
        elif self._match_text_seq("TRIM"):
            name, value = "TRIM", self._parse_string()
        else:
            return None

        if name not in ("ENFORCELENGTH", "NO ESCAPE") and not value:
            self.raise_error(f"COPY column parameter {name} requires a value")
        return self.expression(exp.CopyParameter(this=exp.var(name), expression=value))

    def _parse_copy_source(self) -> exp.Expr:
        if self._match_text_seq("WITH", "SOURCE") or self._match_text_seq("SOURCE"):
            source_function = self._parse_copy_load_function()
            filters: list[vexp.CopyLoadFunction] = []
            while self._match_text_seq("WITH", "FILTER") or self._match_text_seq("FILTER"):
                filters.append(self._parse_copy_load_function())
            parser = (
                self._parse_copy_load_function()
                if self._match_text_seq("WITH", "PARSER") or self._match_text_seq("PARSER")
                else None
            )
            return self.expression(
                vexp.CopyUDL(this=source_function, filters=filters, parser=parser)
            )

        if self._match_text_seq("VERTICA"):
            table = self._parse_table_parts(schema=True)
            if not table:
                self.raise_error("Expected a source table after FROM VERTICA")
            assert table is not None
            has_columns = self._match(TokenType.L_PAREN, advance=False)
            columns = (
                self._parse_wrapped_csv(lambda: self._parse_id_var(any_token=True))
                if has_columns
                else []
            )
            if has_columns and not columns:
                self.raise_error("FROM VERTICA column lists cannot be empty")
            return self.expression(vexp.CopyFromVertica(this=table, expressions=columns))

        local = self._match_text_seq("LOCAL")
        if self._match_text_seq("STDIN"):
            return self.expression(
                vexp.CopyStdin(local=local, compression=self._parse_copy_compression())
            )

        files = [self._parse_copy_file(local=local)]
        while self._match(TokenType.COMMA):
            files.append(self._parse_copy_file(local=local))

        partition_by: list[exp.Expr] = []
        if self._match_text_seq("PARTITION", "COLUMNS"):
            if local:
                self.raise_error("LOCAL COPY sources do not support PARTITION COLUMNS")
            partition_by = self._parse_csv(lambda: self._parse_id_var(any_token=True))
            if not partition_by:
                self.raise_error("PARTITION COLUMNS requires at least one column")

        return self.expression(
            vexp.CopyFiles(expressions=files, local=local, partition_by=partition_by)
        )

    def _parse_copy_file(self, local: bool) -> vexp.CopyFile:
        path = self._parse_file_location()
        if not path:
            self.raise_error("Expected a COPY source path")
        assert path is not None

        node = None
        if not local and self._match(TokenType.ON):
            node = self._parse_copy_node_selection()

        return self.expression(
            vexp.CopyFile(
                this=path,
                on=node,
                compression=self._parse_copy_compression(),
            )
        )

    def _parse_copy_node_selection(self) -> vexp.CopyNodeSelection:
        if self._match_text_seq("ANY", "NODE"):
            return self.expression(vexp.CopyNodeSelection(kind="ANY"))
        if self._match_text_seq("EACH", "NODE"):
            return self.expression(vexp.CopyNodeSelection(kind="EACH"))
        if self._match(TokenType.L_PAREN):
            nodes = self._parse_csv(lambda: self._parse_id_var(any_token=True))
            self._match_r_paren()
            if not nodes:
                self.raise_error("COPY node lists cannot be empty")
            return self.expression(vexp.CopyNodeSelection(kind="SET", expressions=nodes))

        node = self._parse_id_var(any_token=True)
        if not node:
            self.raise_error("Expected a node selection after ON")
        return self.expression(vexp.CopyNodeSelection(kind="NAME", this=node))

    def _parse_copy_compression(self) -> exp.Var | None:
        if self._match_texts(self.COPY_COMPRESSIONS):
            return exp.var(self._prev.text.upper())
        return None

    def _parse_copy_format(self) -> vexp.CopyFormat | None:
        if self._match_text_seq("NATIVE"):
            name = "NATIVE VARCHAR" if self._match(TokenType.VARCHAR) else "NATIVE"
            return self.expression(vexp.CopyFormat(this=exp.var(name)))
        if self._match_text_seq("FIXEDWIDTH"):
            if not self._match_text_seq("COLSIZES"):
                self.raise_error("FIXEDWIDTH requires COLSIZES")
            sizes = self._parse_wrapped_csv(self._parse_number)
            return self.expression(vexp.CopyFormat(this=exp.var("FIXEDWIDTH"), expressions=sizes))
        if self._match_texts(("ORC", "PARQUET")):
            name = self._prev.text.upper()
            parameters = (
                self._parse_wrapped_csv(self._parse_copy_format_parameter)
                if self._match(TokenType.L_PAREN, advance=False)
                else []
            )
            parameter_names = [parameter.this.name.upper() for parameter in parameters]
            repeated = {
                parameter_name
                for parameter_name in parameter_names
                if parameter_names.count(parameter_name) > 1
            }
            if repeated:
                self.raise_error(f"{name} parameter cannot be repeated: {min(repeated)}")

            unsupported = set(parameter_names).difference(self.COPY_FORMAT_PARAMETERS[name])
            if unsupported:
                self.raise_error(f"Unsupported {name} parameter: {', '.join(sorted(unsupported))}")
            return self.expression(vexp.CopyFormat(this=exp.var(name), expressions=parameters))
        return None

    def _parse_copy_format_parameter(self) -> exp.EQ | None:
        name = self._parse_id_var(any_token=True)
        if not name:
            return None
        if not self._match(TokenType.EQ):
            self.raise_error("ORC and PARQUET parameters require name=value")

        value = self._parse_disjunction()
        if not value:
            self.raise_error("ORC and PARQUET parameters require a value")
        return self.expression(exp.EQ(this=name, expression=value))

    def _parse_copy_load_function(self) -> vexp.CopyLoadFunction:
        name = self._parse_id_var(any_token=True)
        if not name:
            self.raise_error("Expected a COPY load function")
        assert name is not None
        arguments = (
            self._parse_wrapped_csv(self._parse_equality)
            if self._match(TokenType.L_PAREN, advance=False)
            else []
        )
        return self.expression(vexp.CopyLoadFunction(this=name, expressions=arguments))

    def _parse_vertica_copy_parameter(self) -> exp.CopyParameter | None:
        name = None
        value = None
        values: list[exp.Expr] | None = None

        if self._match_text_seq("ABORT", "ON", "ERROR"):
            name = "ABORT ON ERROR"
        elif self._match_text_seq("DELIMITER"):
            self._match(TokenType.ALIAS)
            name, value = "DELIMITER", self._parse_string()
        elif self._match_text_seq("ENCLOSED"):
            self._match_text_seq("BY")
            name, value = "ENCLOSED BY", self._parse_string()
        elif self._match_text_seq("ENFORCELENGTH"):
            name = "ENFORCELENGTH"
        elif self._match_text_seq("ERROR", "TOLERANCE"):
            name = "ERROR TOLERANCE"
        elif self._match_text_seq("ESCAPE"):
            self._match(TokenType.ALIAS)
            name, value = "ESCAPE AS", self._parse_string()
        elif self._match_text_seq("NO", "ESCAPE"):
            name = "NO ESCAPE"
        elif self._match_text_seq("EXCEPTIONS"):
            name, values = "EXCEPTIONS", self._parse_copy_output_targets()
        elif self._match_text_seq("WITH", "FILTER") or self._match_text_seq("FILTER"):
            name, value = "FILTER", self._parse_copy_load_function()
        elif self._match(TokenType.NULL):
            self._match(TokenType.ALIAS)
            name, value = "NULL AS", self._parse_string()
        elif self._match_text_seq("RECORD", "TERMINATOR"):
            name = "RECORD TERMINATOR"
            value = self._parse_string()
            if value is None and self._curr.token_type == TokenType.BYTE_STRING:
                value = self._parse_primary()
        elif self._match_text_seq("REJECTED", "DATA"):
            if self._match_text_seq("AS", "TABLE"):
                name, value = "REJECTED DATA AS TABLE", self._parse_table_parts(schema=True)
            else:
                name, values = "REJECTED DATA", self._parse_copy_output_targets()
        elif self._match_text_seq("REJECTMAX"):
            name, value = "REJECTMAX", self._parse_number()
        elif self._match_text_seq("SKIP"):
            name = "SKIP BYTES" if self._match_text_seq("BYTES") else "SKIP"
            value = self._parse_number()
        elif self._match_text_seq("STREAM", "NAME"):
            name, value = "STREAM NAME", self._parse_string()
        elif self._match_text_seq("TRAILING", "NULLCOLS"):
            name = "TRAILING NULLCOLS"
        elif self._match_text_seq("TRIM"):
            name, value = "TRIM", self._parse_string()
        elif self._match_texts(
            (
                "COLLECTIONDELIMITER",
                "COLLECTIONOPEN",
                "COLLECTIONCLOSE",
                "COLLECTIONNULLELEMENT",
                "COLLECTIONENCLOSE",
            )
        ):
            name, value = self._prev.text.upper(), self._parse_string()
        elif self._match_text_seq("WITH", "PARSER") or self._match_text_seq("PARSER"):
            name, value = "PARSER", self._parse_copy_load_function()
        elif self._match_texts(("AUTO", "DIRECT", "TRICKLE")):
            name = self._prev.text.upper()
        else:
            return None

        if (
            name
            not in {
                "ABORT ON ERROR",
                "ENFORCELENGTH",
                "ERROR TOLERANCE",
                "NO ESCAPE",
                "TRAILING NULLCOLS",
                "AUTO",
                "DIRECT",
                "TRICKLE",
                "EXCEPTIONS",
                "REJECTED DATA",
            }
            and not value
        ):
            self.raise_error(f"COPY parameter {name} requires a value")

        return self.expression(
            exp.CopyParameter(this=exp.var(name), expression=value, expressions=values)
        )

    def _parse_copy_output_targets(self) -> list[exp.Expr]:
        targets: list[exp.Expr] = [self._parse_copy_output_target()]
        while self._match(TokenType.COMMA):
            targets.append(self._parse_copy_output_target())
        return targets

    def _parse_copy_output_target(self) -> vexp.CopyOutputTarget:
        path = self._parse_string()
        if not path:
            self.raise_error("Expected a path for COPY output")
        assert path is not None
        has_on = self._match(TokenType.ON)
        node = self._parse_id_var(any_token=True) if has_on else None
        if has_on and not node:
            self.raise_error("Expected a node after COPY output ON")
        return self.expression(vexp.CopyOutputTarget(this=path, node=node))

    def _parse_struct_types(self, type_required: bool = False) -> exp.Expr | None:
        # SET and ROW are statement/control tokens in SQLGlot, not members of
        # its generic TYPE_TOKENS. In a Vertica ROW field, however, they can be
        # the next field's type and must not be mistaken for a missing type.
        if self._next.token_type in (TokenType.SET, TokenType.ROW):
            this = self._parse_id_var()
            self._match(TokenType.COLON)
            return self._parse_column_def(this)

        return super()._parse_struct_types(type_required=type_required)

    def _parse_types(
        self,
        check_func: bool = False,
        schema: bool = False,
        allow_identifiers: bool = True,
        with_collation: bool = False,
    ) -> exp.Expr | None:
        """Parse Vertica's prefix-style native collection and row types.

        Vertica declares collections as ``ARRAY[element_type, bound]`` and
        ``SET[element_type, bound]``. SQLGlot's PostgreSQL parser interprets
        square brackets as postfix array dimensions, so these forms need to be
        recognized before delegating to the inherited type parser.
        """

        if self._curr.token_type == TokenType.INTERVAL:
            self._advance()
            precision = self._parse_interval_precision()
            unit = self._parse_interval_unit()
            return self.expression(
                exp.DataType(
                    this=exp.DType.INTERVAL,
                    expressions=[unit] if unit is not None else None,
                    values=[precision] if precision is not None else None,
                )
            )

        collection_type = {
            TokenType.ARRAY: exp.DType.ARRAY,
            TokenType.SET: exp.DType.SET,
        }.get(self._curr.token_type)

        if not check_func and collection_type and self._next.token_type == TokenType.L_BRACKET:
            self._advance()
            self._advance()
            element_type = self._parse_types(
                check_func=check_func,
                schema=schema,
                allow_identifiers=allow_identifiers,
                with_collation=True,
            )
            if not element_type:
                self.raise_error("Expected an element type in collection declaration")
            assert element_type is not None

            bounds: list[exp.Expr] | None = None
            if self._match(TokenType.COMMA):
                bound = self._parse_disjunction()
                if not bound:
                    self.raise_error("Expected a maximum size after collection type")
                assert bound is not None
                bounds = [bound]

            if not self._match(TokenType.R_BRACKET):
                self.raise_error("Expected ] after collection type")

            max_size = False
            if bounds is None and self._match(TokenType.L_PAREN):
                bound = self._parse_disjunction()
                if not bound:
                    self.raise_error("Expected a maximum binary size for collection type")
                assert bound is not None
                bounds = [bound]
                max_size = True
                self._match_r_paren()

            return self.expression(
                exp.DataType(
                    this=collection_type,
                    expressions=[element_type],
                    values=bounds,
                    kind=exp.var("MAX_SIZE") if max_size else None,
                    nested=True,
                )
            )

        if (
            not check_func
            and self._curr.token_type == TokenType.ROW
            and self._next.token_type == TokenType.L_PAREN
        ):
            self._advance()
            self._advance()
            fields = self._parse_csv(lambda: self._parse_struct_types(type_required=True))
            if not fields:
                self.raise_error("Expected at least one field in ROW type")
            self._match_r_paren()
            return self.expression(
                exp.DataType(this=exp.DType.STRUCT, expressions=fields, nested=True)
            )

        return super()._parse_types(
            check_func=check_func,
            schema=schema,
            allow_identifiers=allow_identifiers,
            with_collation=with_collation,
        )

    def _reject_prefixed_routing_rule(self, statement: str, words: list[str]) -> None:
        for index, word in enumerate(words[:-1]):
            if word == "ROUTING" and words[index + 1] == "RULE":
                if index:
                    self.raise_error(f"{statement} ROUTING RULE does not support modifiers")
                return
            if word in self.ROUTING_RULE_OBJECT_BOUNDARIES:
                return

    def _reject_prefixed_load_balance_group(self, statement: str, words: list[str]) -> None:
        compound_starts = {
            boundary.split(" ", 1)[0] for boundary in self.LOAD_BALANCE_GROUP_COMPOUND_BOUNDARIES
        }
        for index, word in enumerate(words):
            if words[index : index + 3] == ["LOAD", "BALANCE", "GROUP"]:
                if index:
                    self.raise_error(f"{statement} LOAD BALANCE GROUP does not support modifiers")
                return
            if " ".join(words[index : index + 2]) in self.LOAD_BALANCE_GROUP_COMPOUND_BOUNDARIES:
                return
            if word in self.ROUTING_RULE_OBJECT_BOUNDARIES and word not in compound_starts | {
                "LOAD"
            }:
                return

    def _reject_prefixed_network_address(self, statement: str, words: list[str]) -> None:
        compound_starts = {
            boundary.split(" ", 1)[0] for boundary in self.NETWORK_ADDRESS_COMPOUND_BOUNDARIES
        }
        for index, word in enumerate(words):
            if words[index : index + 2] == ["NETWORK", "ADDRESS"]:
                if index:
                    self._raise_network_address_error(
                        f"{statement} NETWORK ADDRESS does not support modifiers"
                    )
                return
            if any(
                words[index : index + len(boundary.split())] == boundary.split()
                for boundary in self.NETWORK_ADDRESS_COMPOUND_BOUNDARIES
            ):
                return
            if word in self.ROUTING_RULE_OBJECT_BOUNDARIES and word not in compound_starts:
                return

    def _raise_network_address_error(self, message: str) -> None:
        self.raise_error(message)
        if self.error_level == ErrorLevel.RAISE:
            self.check_errors()

    def _match_network_object(self, kind: str, *, advance: bool = True) -> bool:
        matched = (
            self._curr.token_type == TokenType.VAR
            and self._curr.text.upper() == "NETWORK"
            and self._next.token_type == TokenType.VAR
            and self._next.text.upper() == kind
        )
        if matched and advance:
            self._advance()
            self._advance()
        return matched

    def _reject_prefixed_user(self, statement: str, words: list[str]) -> None:
        index = self._user_prefix_length(statement, words)
        if index >= len(words) or words[index] != "USER":
            return
        token = self._tokens[self._index + index]
        if token.token_type != TokenType.VAR or not token.text.isascii():
            self._raise_user_error(
                f"{statement} USER requires the unquoted ASCII USER object keyword"
            )
        if index:
            self._raise_user_error(f"{statement} USER does not support modifiers")

    def _reject_prefixed_profile(self, statement: str, words: list[str]) -> None:
        index = self._user_prefix_length(statement, words)
        if index >= len(words) or words[index] != "PROFILE":
            return
        token = self._tokens[self._index + index]
        if token.token_type != TokenType.VAR or not token.text.isascii():
            self._raise_profile_error(
                f"{statement} PROFILE requires the unquoted ASCII PROFILE object keyword"
            )
        if index:
            self._raise_profile_error(f"{statement} PROFILE does not support modifiers")

    def _reject_sensitive_user_statement(self, statement: str, words: list[str]) -> None:
        index = self._user_prefix_length(statement, words)
        if index >= len(words) or words[index] != "USER":
            return

        tokens = self._tokens[self._index :]
        after_user = tokens[index + 1 :]
        if not after_user:
            return
        if any(token.token_type in self.USER_SENSITIVE_LITERAL_TOKENS for token in after_user):
            raise ParseError("Unsupported secret-bearing USER clause")
        if statement == "DROP":
            position = 0
            if self._tokens_are_user_keywords(after_user, "IF", "EXISTS"):
                position = 2
            if position < len(after_user):
                position += 1
            while position < len(after_user) and after_user[position].token_type == TokenType.COMMA:
                position += 2
            if self._tokens_are_user_keywords(after_user[position:], "CASCADE"):
                position += 1
            unsupported_tail = after_user[position:]
        else:
            tail = after_user[1:]
            account_state = self._tokens_are_user_keywords(
                tail, "ACCOUNT", "LOCK"
            ) or self._tokens_are_user_keywords(tail, "ACCOUNT", "UNLOCK")
            password_expire = self._tokens_are_user_keywords(tail, "PASSWORD", "EXPIRE")
            if statement == "ALTER" and self._tokens_are_user_keywords(tail, "RENAME", "TO"):
                supported_length = min(3, len(tail))
            elif account_state or password_expire:
                supported_length = 2
            else:
                supported_length = 0
            unsupported_tail = tail[supported_length:]

        sensitive_keyword = any(
            self._tokens_are_user_keywords(unsupported_tail[token_index:], "IDENTIFIED", "BY")
            or self._tokens_are_user_keywords(unsupported_tail[token_index:], "TOTPSECRET")
            or (
                self._tokens_are_user_keywords(unsupported_tail[token_index:], "PASSWORD")
                and not self._tokens_are_user_keywords(
                    unsupported_tail[token_index:], "PASSWORD", "EXPIRE"
                )
            )
            for token_index in range(len(unsupported_tail))
        )
        if sensitive_keyword:
            raise ParseError("Unsupported secret-bearing USER clause")

    def _user_prefix_length(self, statement: str, words: list[str]) -> int:
        index = 0
        while index < len(words):
            sequence = next(
                (
                    prefix
                    for prefix in self.USER_PREFIX_SEQUENCES[statement]
                    if words[index : index + len(prefix)] == list(prefix)
                ),
                None,
            )
            if sequence:
                index += len(sequence)
            elif words[index] in self.USER_PREFIX_WORDS[statement]:
                index += 1
            else:
                break
        return index

    def _raise_user_error(self, message: str) -> None:
        self.raise_error(message)
        if self.error_level == ErrorLevel.RAISE:
            self.check_errors()
        if self.error_level in {ErrorLevel.IGNORE, ErrorLevel.WARN}:
            raise ParseError(message)

    def _raise_profile_error(self, message: str) -> None:
        self.raise_error(message)
        if self.error_level == ErrorLevel.RAISE:
            self.check_errors()
        if self.error_level in {ErrorLevel.IGNORE, ErrorLevel.WARN}:
            raise ParseError(message)

    def _match_user_object(self, *, advance: bool = True) -> bool:
        matched = (
            self._curr.token_type == TokenType.VAR
            and self._curr.text.isascii()
            and self._curr.text.upper() == "USER"
        )
        if matched and advance:
            self._advance()
        return matched

    def _match_profile_object(self, *, advance: bool = True) -> bool:
        matched = (
            self._curr.token_type == TokenType.VAR
            and self._curr.text.isascii()
            and self._curr.text.upper() == "PROFILE"
        )
        if matched and advance:
            self._advance()
        return matched

    def _match_profile_var(self, word: str, *, advance: bool = True) -> bool:
        token_types = {
            "DEFAULT": TokenType.DEFAULT,
            "EXISTS": TokenType.EXISTS,
            "LIMIT": TokenType.LIMIT,
            "RENAME": TokenType.RENAME,
        }
        matched = (
            self._curr.token_type == token_types.get(word, TokenType.VAR)
            and self._curr.text.isascii()
            and self._curr.text.upper() == word
        )
        if matched and advance:
            self._advance()
        return matched

    def _match_user_keywords(self, *words: str, advance: bool = True) -> bool:
        tokens = self._tokens[self._index : self._index + len(words)]
        matched = self._tokens_are_user_keywords(tokens, *words)
        if matched and advance:
            for _ in words:
                self._advance()
        return matched

    def _tokens_are_user_keywords(self, tokens: list[Token], *words: str) -> bool:
        return len(tokens) >= len(words) and all(
            token.text.isascii()
            and token.text.upper() == word
            and token.token_type == self.USER_KEYWORD_TOKEN_TYPES[word]
            for token, word in zip(tokens[: len(words)], words)
        )

    def _parse_create(  # type: ignore[override]
        self,
    ) -> exp.Create | vexp.CreateDirectedQuery | exp.Command:
        words = [token.text.upper() for token in self._tokens[self._index :]]
        self._reject_sensitive_user_statement("CREATE", words)
        self._reject_prefixed_routing_rule("CREATE", words)
        self._reject_prefixed_load_balance_group("CREATE", words)
        self._reject_prefixed_network_address("CREATE", words)
        self._reject_prefixed_profile("CREATE", words)
        self._reject_prefixed_user("CREATE", words)
        unsupported_directed_prefixes = (
            ("IF", "NOT", "EXISTS", "DIRECTED", "QUERY"),
            ("TEMPORARY", "DIRECTED", "QUERY"),
            ("GLOBAL", "TEMPORARY", "DIRECTED", "QUERY"),
            ("LOCAL", "TEMPORARY", "DIRECTED", "QUERY"),
            ("MATERIALIZED", "DIRECTED", "QUERY"),
        )
        if any(words[: len(prefix)] == list(prefix) for prefix in unsupported_directed_prefixes):
            self.raise_error("CREATE DIRECTED QUERY does not support CREATE modifiers")

        index = self._index
        replace = self._match_pair(TokenType.OR, TokenType.REPLACE)

        if self._match_text_seq("DIRECTED"):
            if not self._match_text_seq("QUERY"):
                self.raise_error("CREATE DIRECTED must be followed by QUERY")
            if replace:
                self.raise_error("CREATE OR REPLACE DIRECTED QUERY is not supported")
            return self._parse_create_directed_query()

        udx_kind = self._parse_user_defined_extension_kind("CREATE")
        if udx_kind:
            if udx_kind == "FUNCTION" and not self._is_factory_function_ahead():
                self._retreat(index)
                return super()._parse_create()
            return self._parse_create_user_defined_extension(kind=udx_kind, replace=replace)
        if self._match_text_seq("LIBRARY"):
            return self._parse_create_library(replace=replace)

        if self._match(TokenType.LOAD):
            if not self._match_text_seq("BALANCE", "GROUP"):
                self.raise_error("CREATE LOAD must be followed by BALANCE GROUP")
            return self._parse_create_load_balance_group(replace=replace)
        if self._match_network_object("ADDRESS"):
            return self._parse_create_network_address(replace=replace)
        if self._curr.text.upper() == "NETWORK" and not self._match_network_object(
            "INTERFACE", advance=False
        ):
            self._raise_network_address_error("CREATE NETWORK must be followed by ADDRESS")
        if self._match_profile_object():
            return self._parse_create_profile(replace=replace)
        if self._curr.text.upper() == "PROFILE":
            self._raise_profile_error("CREATE PROFILE requires the unquoted PROFILE object kind")
        if self._match_user_object():
            return self._parse_create_user(replace=replace)
        if self._curr.text.upper() == "USER":
            self._raise_user_error("CREATE USER requires the unquoted USER object kind")
        if self._match_text_seq("ROLE"):
            return self._parse_create_role(replace=replace)
        if self._match_text_seq("RESOURCE", "POOL"):
            return self._parse_create_resource_pool(replace=replace)
        if self._match_text_seq("ROUTING", "RULE"):
            return self._parse_create_routing_rule(replace=replace)
        if self._match_text_seq("ROUTING", advance=False):
            self.raise_error("CREATE ROUTING must be followed by RULE")

        if self._match_texts(("FLEX", "FLEXIBLE")):
            if not self._match_text_seq("EXTERNAL"):
                self._retreat(index)
                return super()._parse_create()
            if not self._match(TokenType.TABLE):
                self.raise_error("FLEXIBLE EXTERNAL must be followed by TABLE")
            if replace:
                self.raise_error("CREATE OR REPLACE FLEXIBLE EXTERNAL TABLE is not supported")
            return self._parse_create_flexible_external_table()

        if self._match_text_seq("EXTERNAL"):
            if not self._match(TokenType.TABLE):
                self.raise_error("EXTERNAL must be followed by TABLE")
            if replace:
                self.raise_error("CREATE OR REPLACE EXTERNAL TABLE is not supported")
            if self._is_iceberg_external_table_ahead():
                return self._parse_create_iceberg_external_table()
            return self._parse_create_external_table()

        if self._match(TokenType.PROCEDURE):
            if not self._is_external_procedure_ahead():
                self._retreat(index)
                return super()._parse_create()
            if replace:
                self.raise_error("CREATE OR REPLACE external PROCEDURE is not supported")
            return self._parse_create_external_procedure()

        if self._match(TokenType.PROJECTION):
            return self._parse_create_projection(replace=replace)
        if self._match(TokenType.SEQUENCE):
            return self._parse_create_sequence(replace=replace)
        if self._match(TokenType.SCHEMA):
            return self._parse_create_schema(replace=replace)
        if self._match(TokenType.VIEW):
            return self._parse_create_view(replace=replace)

        scope = None
        if self._match_texts(("GLOBAL", "LOCAL")):
            scope = self._prev.text.upper()

        temporary = self._match(TokenType.TEMPORARY)
        if scope and not temporary:
            if self._match(TokenType.TABLE, advance=False):
                self.raise_error("GLOBAL or LOCAL table scope requires TEMPORARY")
            self._retreat(index)
            return super()._parse_create()

        if temporary:
            if not self._match(TokenType.TABLE):
                self._retreat(index)
                return super()._parse_create()
        elif not self._match(TokenType.TABLE):
            self._retreat(index)
            return super()._parse_create()

        if replace:
            self.raise_error("CREATE OR REPLACE TABLE is not supported by Vertica")

        return self._parse_create_table(temporary=temporary, scope=scope)

    def _parse_create_directed_query(self) -> vexp.CreateDirectedQuery:
        if not self._match_texts(("OPT", "OPTIMIZER", "CUSTOM")):
            self.raise_error("CREATE DIRECTED QUERY requires OPT, OPTIMIZER, or CUSTOM")
        mode = self._prev.text.upper()
        name = self._parse_directed_query_name("CREATE DIRECTED QUERY")

        comment = None
        if self._match_text_seq("COMMENT"):
            comment = self._parse_string()
            if not isinstance(comment, exp.Literal) or not comment.is_string:
                self.raise_error("CREATE DIRECTED QUERY COMMENT requires a string literal")
            if isinstance(comment, exp.Literal) and len(comment.this) > 128:
                self.raise_error("CREATE DIRECTED QUERY COMMENT cannot exceed 128 characters")

        optimizer_version = None
        if self._match_text_seq("OPTVER"):
            if mode != "CUSTOM":
                self.raise_error("OPTVER is only valid for a CUSTOM directed query export")
            optimizer_version = self._parse_string()
            if not isinstance(optimizer_version, exp.Literal) or not optimizer_version.is_string:
                self.raise_error("CREATE DIRECTED QUERY OPTVER requires a string literal")

        plan_date = None
        if self._match_text_seq("PSDATE"):
            if mode != "CUSTOM":
                self.raise_error("PSDATE is only valid for a CUSTOM directed query export")
            plan_date = self._parse_string()
            if not isinstance(plan_date, exp.Literal) or not plan_date.is_string:
                self.raise_error("CREATE DIRECTED QUERY PSDATE requires a string literal")

        query = self._parse_directed_query_input("CREATE DIRECTED QUERY")
        if self._curr:
            self.raise_error(f"Unexpected CREATE DIRECTED QUERY clause at {self._curr.text!r}")

        return self.expression(
            vexp.CreateDirectedQuery(
                this=name,
                mode=exp.var(mode),
                expression=query,
                comment=comment,
                optimizer_version=optimizer_version,
                plan_date=plan_date,
            )
        )

    def _parse_user_defined_extension_kind(self, statement: str) -> str | None:
        for prefix in ("AGGREGATE", "ANALYTIC", "TRANSFORM"):
            if self._match_text_seq(prefix):
                if not self._match(TokenType.FUNCTION):
                    self.raise_error(f"{statement} {prefix} requires FUNCTION")
                return f"{prefix} FUNCTION"

        for kind in ("FUNCTION", "FILTER", "PARSER", "SOURCE"):
            if self._match_text_seq(kind):
                return kind
        return None

    def _is_factory_function_ahead(self) -> bool:
        """Distinguish a bodyless UDx from the separate SQL-function grammar."""

        signature = False
        depth = 0
        tokens = self._tokens[self._index :]
        for position, token in enumerate(tokens):
            if token.token_type == TokenType.L_PAREN:
                if depth == 0:
                    signature = True
                depth += 1
                continue
            if token.token_type == TokenType.R_PAREN and depth:
                depth -= 1
                continue
            if depth or token.token_type != TokenType.ALIAS:
                continue

            if not signature:
                return True

            following = tokens[position + 1 :]
            if not following:
                return False
            first = following[0]
            return (
                first.token_type not in self.TEXT_MATCH_EXCLUDED_TOKENS
                and first.text.upper() in {"LANGUAGE", "NAME", "LIBRARY", "FENCED", "NOT"}
            )

        return not signature

    def _parse_create_user_defined_extension(
        self, kind: str, replace: bool
    ) -> vexp.CreateUserDefinedExtension:
        exists = bool(self._parse_exists(not_=True))
        if replace and exists:
            self.raise_error("OR REPLACE and IF NOT EXISTS are mutually exclusive")

        name = self._parse_catalog_object_name(f"CREATE {kind}")
        if self._match(TokenType.L_PAREN, advance=False):
            self.raise_error(f"Factory-backed {kind} names do not accept an argument signature")
        if not self._match(TokenType.ALIAS):
            self.raise_error(f"CREATE {kind} requires AS")

        language = None
        if self._match_text_seq("LANGUAGE"):
            language = self._parse_user_defined_extension_language(kind)

        if not self._match_text_seq("NAME"):
            self.raise_error(f"CREATE {kind} requires NAME after AS")
        factory = self._parse_string()
        if not isinstance(factory, exp.Literal) or not factory.is_string:
            self.raise_error(f"CREATE {kind} factory NAME must be a string")

        if not self._match_text_seq("LIBRARY"):
            self.raise_error(f"CREATE {kind} requires LIBRARY after NAME")
        library = self._parse_catalog_object_name(f"CREATE {kind} LIBRARY")

        fenced: bool | None = None
        if self._match_text_seq("FENCED"):
            fenced = True
        elif self._match_text_seq("NOT"):
            if not self._match_text_seq("FENCED"):
                self.raise_error(f"CREATE {kind} NOT must be followed by FENCED")
            fenced = False

        self._validate_user_defined_extension_mode(kind, language, fenced)
        if self._curr:
            self.raise_error(f"Unexpected CREATE {kind} clause at {self._curr.text!r}")

        return self.expression(
            vexp.CreateUserDefinedExtension(
                this=name,
                kind=kind,
                exists=exists,
                replace=replace,
                expression=self.expression(
                    vexp.UDxFactorySpec(
                        language=language,
                        factory=factory,
                        library=library,
                        fenced=fenced,
                    )
                ),
            )
        )

    def _parse_user_defined_extension_language(self, kind: str) -> exp.Literal:
        language = self._parse_string()
        if not isinstance(language, exp.Literal) or not language.is_string:
            self.raise_error(f"CREATE {kind} LANGUAGE must be a string")
        assert isinstance(language, exp.Literal)

        normalized = language.this.upper()
        canonical = self.USER_DEFINED_EXTENSION_LANGUAGE_NAMES.get(normalized)
        if canonical is None or normalized not in self.USER_DEFINED_EXTENSION_LANGUAGES[kind]:
            self.raise_error(f"Unsupported CREATE {kind} language: {language.this}")
        assert canonical is not None
        return self.expression(exp.Literal.string(canonical))

    def _validate_user_defined_extension_mode(
        self, kind: str, language: exp.Literal | None, fenced: bool | None
    ) -> None:
        language_name = language.this.upper() if language else "C++"
        if kind == "AGGREGATE FUNCTION" and fenced is True:
            self.raise_error("Vertica aggregate functions cannot run FENCED")
        if language_name != "C++" and fenced is False:
            self.raise_error(f"Vertica {language_name} UDxs cannot run NOT FENCED")

    def _parse_create_library(self, replace: bool) -> vexp.CreateLibrary:
        if self._match_text_seq("IF", advance=False):
            self.raise_error("CREATE LIBRARY does not support IF NOT EXISTS")

        name = self._parse_catalog_object_name("CREATE LIBRARY")
        if not self._match(TokenType.ALIAS):
            self.raise_error("CREATE LIBRARY requires AS path")
        path = self._parse_string()
        if not isinstance(path, exp.Literal) or not path.is_string:
            self.raise_error("CREATE LIBRARY path must be a string")

        depends = None
        if self._match_text_seq("DEPENDS"):
            depends = self._parse_string()
            if not isinstance(depends, exp.Literal) or not depends.is_string:
                self.raise_error("CREATE LIBRARY DEPENDS must be a string")

        language = None
        if self._match_text_seq("LANGUAGE"):
            language = self._parse_user_defined_extension_language("LIBRARY")

        if self._curr:
            self.raise_error(f"Unexpected CREATE LIBRARY clause at {self._curr.text!r}")

        return self.expression(
            vexp.CreateLibrary(
                this=name,
                kind="LIBRARY",
                replace=replace,
                path=path,
                depends=depends,
                language=language,
            )
        )

    def _parse_catalog_object_name(self, label: str) -> exp.Table:
        name = self._parse_table_parts(schema=True)
        if not isinstance(name, exp.Table) or not isinstance(name.args.get("this"), exp.Identifier):
            self.raise_error(f"{label} requires at most a database, schema, and object name")
        assert isinstance(name, exp.Table)
        if any(
            part is not None and not isinstance(part, exp.Identifier)
            for part in (name.args.get("db"), name.args.get("catalog"))
        ):
            self.raise_error(f"{label} requires at most a database, schema, and object name")
        return name

    def _is_iceberg_external_table_ahead(self) -> bool:
        words = [token.text.upper() for token in self._tokens[self._index :]]
        return any(
            words[position : position + 3] == ["STORED", "BY", "ICEBERG"]
            for position in range(len(words) - 2)
        )

    def _is_external_procedure_ahead(self) -> bool:
        tokens = self._tokens[self._index :]
        depth = 0
        signature_closed = False
        for position, token in enumerate(tokens):
            if token.token_type == TokenType.L_PAREN:
                depth += 1
                continue
            if token.token_type == TokenType.R_PAREN:
                if depth:
                    depth -= 1
                    signature_closed = signature_closed or depth == 0
                continue
            if depth:
                continue

            following = tokens[position + 1 :]
            if token.token_type == TokenType.ALIAS:
                if following and following[0].token_type == TokenType.STRING:
                    return True
                continue

            if not signature_closed or token.token_type in self.TEXT_MATCH_EXCLUDED_TOKENS:
                continue

            if (
                token.text.upper() == "LANGUAGE"
                and following
                and following[0].text.upper() == "EXTERNAL"
            ):
                return True
            if token.text.upper() == "USER":
                return True
        return False

    def _parse_create_iceberg_external_table(self) -> vexp.CreateIcebergExternalTable:
        if self._parse_exists(not_=True):
            self.raise_error("Iceberg external tables do not support IF NOT EXISTS")

        table = self._parse_table_parts(schema=True)
        if not table:
            self.raise_error("CREATE EXTERNAL TABLE ICEBERG requires a table name")
        assert table is not None

        if self._match(TokenType.L_PAREN, advance=False):
            self.raise_error(
                "Iceberg external tables read their schema from metadata and do not accept "
                "ordinary column definitions"
            )
        if not self._match_text_seq("STORED", "BY", "ICEBERG", "LOCATION"):
            self.raise_error("Iceberg external tables require STORED BY ICEBERG LOCATION")

        location = self._parse_string()
        if not isinstance(location, exp.Literal) or not location.is_string:
            self.raise_error("Iceberg LOCATION must be a string")

        values: dict[str, exp.Expr] = {}
        column_types: list[vexp.IcebergColumnType] = []
        seen: set[str] = set()
        previous_order = 0
        while self._curr:
            if self._match_text_seq("COLUMN", "TYPES"):
                clause = "COLUMN TYPES"
                value: exp.Expr | None = None
            elif self._match_texts(("GLUE_DB", "GLUE_TABLE", "HMS_DB", "HMS_TABLE", "REST_AUTH")):
                clause = self._prev.text.upper()
                value = self._parse_string()
                if not isinstance(value, exp.Literal) or not value.is_string:
                    self.raise_error(f"Iceberg {clause} must be a string")
            else:
                self.raise_error(f"Unsupported Iceberg clause starting at {self._curr.text!r}")

            if clause in seen:
                self.raise_error(f"Iceberg clause cannot be repeated: {clause}")
            order = self.ICEBERG_CLAUSE_ORDER[clause]
            if order < previous_order:
                self.raise_error("Iceberg clauses are not in Vertica clause order")
            seen.add(clause)
            previous_order = order

            if clause == "COLUMN TYPES":
                column_types = self._parse_iceberg_column_types()
            else:
                assert value is not None
                values[clause.lower()] = value

        has_glue = "GLUE_DB" in seen or "GLUE_TABLE" in seen
        has_hms = "HMS_DB" in seen or "HMS_TABLE" in seen
        has_rest = "REST_AUTH" in seen
        if has_glue and not {"GLUE_DB", "GLUE_TABLE"}.issubset(seen):
            self.raise_error("Iceberg GLUE_DB and GLUE_TABLE must be specified together")
        if has_hms and not {"HMS_DB", "HMS_TABLE"}.issubset(seen):
            self.raise_error("Iceberg HMS_DB and HMS_TABLE must be specified together")
        if sum((has_glue, has_hms, has_rest)) > 1:
            self.raise_error("Iceberg Glue, HMS, and REST catalog modes are mutually exclusive")

        spec = self.expression(
            vexp.IcebergExternalTableSpec(
                location=location,
                glue_db=values.get("glue_db"),
                glue_table=values.get("glue_table"),
                hms_db=values.get("hms_db"),
                hms_table=values.get("hms_table"),
                rest_auth=values.get("rest_auth"),
                column_types=column_types,
            )
        )
        return self.expression(
            vexp.CreateIcebergExternalTable(
                this=table,
                kind="TABLE",
                expression=spec,
            )
        )

    def _parse_iceberg_column_types(self) -> list[vexp.IcebergColumnType]:
        if not self._match(TokenType.L_PAREN):
            self.raise_error("Iceberg COLUMN TYPES requires parenthesized overrides")
        if self._match(TokenType.R_PAREN):
            self.raise_error("Iceberg COLUMN TYPES requires at least one override")

        overrides: list[vexp.IcebergColumnType] = []
        while True:
            overrides.append(self._parse_iceberg_column_type())
            if not self._match(TokenType.COMMA):
                break
            if self._match(TokenType.R_PAREN, advance=False):
                self.raise_error("Iceberg COLUMN TYPES does not allow a trailing comma")
        self._match_r_paren()

        names = [override.name.lower() for override in overrides]
        repeated = {name for name in names if names.count(name) > 1}
        if repeated:
            self.raise_error(f"Iceberg COLUMN TYPES cannot repeat column: {min(repeated)}")
        return overrides

    def _parse_iceberg_column_type(self) -> vexp.IcebergColumnType:
        name = self._parse_id_var(any_token=True)
        if not name:
            self.raise_error("Expected an Iceberg COLUMN TYPES column name")
        kind = self._parse_types(schema=True)
        if not isinstance(kind, exp.DataType):
            self.raise_error("Expected an Iceberg COLUMN TYPES data type")
        assert name is not None and isinstance(kind, exp.DataType)

        if self._curr.token_type not in {TokenType.COMMA, TokenType.R_PAREN}:
            self.raise_error(
                "Iceberg COLUMN TYPES does not support defaults, constraints, or properties"
            )
        self._validate_iceberg_override_type(kind)
        return self.expression(vexp.IcebergColumnType(this=name, kind=kind))

    def _validate_iceberg_override_type(self, kind: exp.DataType) -> None:
        if kind.this in self.ICEBERG_SIZED_TYPES:
            if len(kind.expressions) != 1 or not self._is_positive_integer_type_size(
                kind.expressions[0]
            ):
                self.raise_error(
                    "Iceberg VARCHAR and VARBINARY overrides require one positive length"
                )
            return

        if kind.this == exp.DType.ARRAY:
            if len(kind.args.get("values") or []) != 1 or not self._is_positive_integer_type_size(
                kind.args["values"][0]
            ):
                self.raise_error("Iceberg ARRAY overrides require one positive bound or size")
            if len(kind.expressions) != 1 or not isinstance(kind.expressions[0], exp.DataType):
                self.raise_error("Iceberg ARRAY overrides require an element type")
            self._validate_iceberg_array_element_type(kind.expressions[0])
            return

        if kind.this == exp.DType.STRUCT:
            self._validate_iceberg_row_override(kind)
            return

        self.raise_error(
            "Iceberg COLUMN TYPES only supports sized VARCHAR/VARBINARY, bounded ARRAY, "
            "or eligible ROW fields"
        )

    def _validate_iceberg_row_override(self, kind: exp.DataType) -> None:
        fields = kind.expressions
        if not fields or not all(isinstance(field, exp.ColumnDef) for field in fields):
            self.raise_error("Iceberg ROW overrides require named fields")

        names: list[str] = []
        for field in fields:
            assert isinstance(field, exp.ColumnDef)
            if field.args.get("constraints"):
                self.raise_error("Iceberg ROW overrides do not support defaults or constraints")
            field_type = field.args.get("kind")
            if not isinstance(field_type, exp.DataType):
                self.raise_error("Iceberg ROW override fields require data types")
            assert isinstance(field_type, exp.DataType)
            names.append(field.name.lower())
            self._validate_iceberg_override_type(field_type)

        repeated = {name for name in names if names.count(name) > 1}
        if repeated:
            self.raise_error(f"Iceberg ROW overrides cannot repeat field: {min(repeated)}")

    def _validate_iceberg_array_element_type(self, kind: exp.DataType) -> None:
        if kind.this in {exp.DType.LONGTEXT, exp.DType.LONGBLOB}:
            self.raise_error("Vertica ARRAY types cannot contain LONG values")
        if kind.this == exp.DType.STRUCT:
            fields = kind.expressions
            if not fields or not all(isinstance(field, exp.ColumnDef) for field in fields):
                self.raise_error("Iceberg ARRAY ROW elements require named fields")
            for field in fields:
                assert isinstance(field, exp.ColumnDef)
                if field.args.get("constraints"):
                    self.raise_error(
                        "Iceberg ARRAY element types do not support defaults or constraints"
                    )
                field_type = field.args.get("kind")
                if not isinstance(field_type, exp.DataType):
                    self.raise_error("Iceberg ARRAY ROW fields require data types")
                assert isinstance(field_type, exp.DataType)
                self._validate_iceberg_array_element_type(field_type)
        elif kind.this == exp.DType.ARRAY:
            if len(kind.expressions) != 1 or not isinstance(kind.expressions[0], exp.DataType):
                self.raise_error("Nested Iceberg ARRAY types require an element type")
            self._validate_iceberg_array_element_type(kind.expressions[0])

    @staticmethod
    def _is_positive_integer_type_size(expression: exp.Expr) -> bool:
        if isinstance(expression, exp.DataTypeParam):
            expression = expression.this
        if not isinstance(expression, exp.Literal) or expression.is_string:
            return False
        value = expression.to_py()
        return type(value) is int and value > 0

    def _parse_create_flexible_external_table(self) -> vexp.CreateFlexibleExternalTable:
        exists = self._parse_exists(not_=True)
        table = self._parse_table_parts(schema=True)
        if not table:
            self.raise_error("CREATE FLEXIBLE EXTERNAL TABLE requires a table name")
        assert table is not None

        if not self._match(TokenType.L_PAREN, advance=False):
            self.raise_error("CREATE FLEXIBLE EXTERNAL TABLE requires a column-list parentheses")
        target = self._parse_schema(this=table)
        if not isinstance(target, exp.Schema):
            self.raise_error("Expected flexible external table column definitions")
        assert isinstance(target, exp.Schema)
        if any(
            not isinstance(item, exp.ColumnDef) or not item.args.get("kind")
            for item in target.expressions
        ):
            self.raise_error(
                "Flexible external table parentheses accept only typed column definitions"
            )

        privileges = self._parse_inherited_privileges_property()
        if not self._match(TokenType.ALIAS) or not self._match(TokenType.COPY):
            self.raise_error("CREATE FLEXIBLE EXTERNAL TABLE requires AS COPY")
        definition = self._parse_copy_definition(context="flexible")

        return self.expression(
            vexp.CreateFlexibleExternalTable(
                this=target,
                kind="TABLE",
                exists=exists,
                expression=definition,
                properties=(
                    self.expression(exp.Properties(expressions=[privileges]))
                    if privileges
                    else None
                ),
            )
        )

    def _parse_create_external_table(self) -> vexp.CreateExternalTable:
        exists = self._parse_exists(not_=True)
        table = self._parse_table_parts(schema=True)
        if not table:
            self.raise_error("CREATE EXTERNAL TABLE requires a table name")
        assert table is not None

        target: exp.Expr = table
        if self._match(TokenType.L_PAREN, advance=False):
            parsed_schema = self._parse_schema(this=table)
            if not isinstance(parsed_schema, exp.Schema):
                self.raise_error("Expected external table column definitions")
            assert isinstance(parsed_schema, exp.Schema)
            if not parsed_schema.expressions:
                self.raise_error("CREATE EXTERNAL TABLE column definitions cannot be empty")
            for item in parsed_schema.expressions:
                if not isinstance(item, exp.ColumnDef) or not item.kind:
                    self.raise_error("CREATE EXTERNAL TABLE columns require data types")
            target = parsed_schema

        privileges = self._parse_inherited_privileges_property()
        if not self._match(TokenType.ALIAS) or not self._match(TokenType.COPY):
            self.raise_error("CREATE EXTERNAL TABLE requires AS COPY")

        definition = self._parse_copy_definition(context="external")
        if not isinstance(target, exp.Schema) and not isinstance(
            definition.args.get("source"), vexp.CopyUDL
        ):
            self.raise_error(
                "CREATE EXTERNAL TABLE requires column definitions unless it uses a UDL source"
            )

        return self.expression(
            vexp.CreateExternalTable(
                this=target,
                kind="TABLE",
                exists=exists,
                expression=definition,
                properties=(
                    self.expression(exp.Properties(expressions=[privileges]))
                    if privileges
                    else None
                ),
            )
        )

    def _parse_create_external_procedure(self) -> vexp.CreateExternalProcedure:
        exists = self._parse_exists(not_=True)
        signature = self._parse_external_procedure_signature()

        if not self._match(TokenType.ALIAS):
            self.raise_error("External PROCEDURE requires AS executable")
        executable = self._parse_string()
        if not isinstance(executable, exp.Literal) or not executable.is_string:
            self.raise_error("External PROCEDURE executable must be a string")

        if not self._match_text_seq("LANGUAGE"):
            self.raise_error("External PROCEDURE requires LANGUAGE 'EXTERNAL'")
        language = self._parse_string()
        if (
            not isinstance(language, exp.Literal)
            or not language.is_string
            or language.this.upper() != "EXTERNAL"
        ):
            self.raise_error("External PROCEDURE LANGUAGE must be the string 'EXTERNAL'")

        if not self._match_text_seq("USER"):
            self.raise_error("External PROCEDURE requires USER after LANGUAGE 'EXTERNAL'")
        os_user = self._parse_string()
        if not isinstance(os_user, exp.Literal) or not os_user.is_string:
            self.raise_error("External PROCEDURE USER must be a string")

        if self._curr:
            self.raise_error(f"Unexpected external PROCEDURE clause at {self._curr.text!r}")

        return self.expression(
            vexp.CreateExternalProcedure(
                this=signature,
                kind="PROCEDURE",
                exists=exists,
                executable=executable,
                os_user=os_user,
            )
        )

    def _parse_external_procedure_signature(self) -> vexp.ExternalProcedureSignature:
        name = self._parse_table_parts(schema=True)
        if not name:
            self.raise_error("PROCEDURE requires a name")
        if not self._match(TokenType.L_PAREN):
            self.raise_error("External PROCEDURE requires a parenthesized argument signature")

        parameters: list[vexp.ExternalProcedureParameter] = []
        if not self._match(TokenType.R_PAREN):
            while True:
                parameters.append(self._parse_external_procedure_parameter())
                if not self._match(TokenType.COMMA):
                    break
            self._match_r_paren()

        names = [parameter.name.lower() for parameter in parameters if parameter.name]
        repeated = {name for name in names if names.count(name) > 1}
        if repeated:
            self.raise_error(f"External PROCEDURE argument cannot be repeated: {min(repeated)}")

        return self.expression(vexp.ExternalProcedureSignature(this=name, expressions=parameters))

    def _parse_external_procedure_parameter(self) -> vexp.ExternalProcedureParameter:
        parameter_name = None
        if not self._external_procedure_type_ahead():
            parameter_name = self._parse_id_var(any_token=True)
            if not parameter_name:
                self.raise_error("Expected an external PROCEDURE argument name or type")

        kind = self._parse_external_procedure_type()
        if self._curr.token_type not in {TokenType.COMMA, TokenType.R_PAREN}:
            self.raise_error("Unexpected tokens after external PROCEDURE argument type")
        return self.expression(vexp.ExternalProcedureParameter(this=parameter_name, kind=kind))

    def _external_procedure_type_ahead(self) -> bool:
        name = self._curr.text.upper()
        if name == "DOUBLE" and self._next.text.upper() == "PRECISION":
            name = "DOUBLE PRECISION"
        return name in self.EXTERNAL_PROCEDURE_TYPES

    def _parse_external_procedure_type(self) -> exp.DataType:
        if not self._external_procedure_type_ahead():
            self.raise_error("Unsupported external PROCEDURE argument type")

        kind = self._parse_types(schema=True)
        if not isinstance(kind, exp.DataType):
            self.raise_error("Expected an external PROCEDURE argument type")
        assert isinstance(kind, exp.DataType)
        if kind.expressions or kind.args.get("values"):
            self.raise_error("External PROCEDURE argument types do not accept parameters")
        return kind

    def _parse_create_role(self, replace: bool) -> exp.Create:
        if replace:
            self.raise_error("CREATE OR REPLACE ROLE is not supported by Vertica")
        if self._match_text_seq("IF", "NOT", "EXISTS", advance=False):
            self.raise_error("CREATE ROLE does not support IF NOT EXISTS")

        role = self._parse_lifecycle_identifier("CREATE ROLE")
        if self._curr:
            self.raise_error(f"Unexpected CREATE ROLE clause at {self._curr.text!r}")
        return self.expression(exp.Create(this=role, kind="ROLE"))

    def _parse_create_user(self, replace: bool) -> vexp.CreateUser:
        if replace:
            self._raise_user_error("CREATE OR REPLACE USER is not supported by Vertica")
        if self._match_user_keywords("IF", "NOT", "EXISTS", advance=False):
            self._raise_user_error("CREATE USER does not support IF NOT EXISTS")

        user = self._parse_user_identifier("CREATE USER")
        action = None
        if self._match_user_keywords("ACCOUNT"):
            if self._match_user_keywords("LOCK"):
                state = "LOCK"
            elif self._match_user_keywords("UNLOCK"):
                state = "UNLOCK"
            else:
                self._raise_user_error("CREATE USER ACCOUNT requires LOCK or UNLOCK")
                state = ""
            action = self.expression(vexp.UserAction(this=exp.var(f"ACCOUNT {state}")))
        elif self._match_user_keywords("PASSWORD"):
            if not self._match_user_keywords("EXPIRE"):
                self._raise_user_error("CREATE USER PASSWORD requires EXPIRE")
            action = self.expression(vexp.UserAction(this=exp.var("PASSWORD EXPIRE")))

        if self._curr:
            self._raise_user_error(f"Unsupported CREATE USER clause at {self._curr.text!r}")
        return self.expression(
            vexp.CreateUser(
                this=user,
                kind="USER",
                action=action,
            )
        )

    def _parse_create_profile(self, replace: bool) -> vexp.CreateProfile:
        if replace:
            self._raise_profile_error("CREATE OR REPLACE PROFILE is not supported by Vertica")
        if self._match_profile_var("IF", advance=False):
            self._raise_profile_error("CREATE PROFILE does not support IF NOT EXISTS")

        profile = self._parse_profile_identifier("CREATE PROFILE")
        if not self._match_profile_var("LIMIT"):
            self._raise_profile_error("CREATE PROFILE requires LIMIT")
        limit = self._parse_profile_limit(alter=False)
        return self.expression(vexp.CreateProfile(this=profile, kind="PROFILE", limit=limit))

    def _parse_profile_identifier(
        self, statement: str, *, allow_default: bool = False
    ) -> exp.Identifier:
        if allow_default and self._match_profile_var("DEFAULT"):
            return self.expression(exp.Identifier(this="DEFAULT", quoted=False))
        identifier = self._parse_user_identifier(statement)
        if identifier.name.upper() == "DEFAULT":
            self._raise_profile_error(f"{statement} cannot use the DEFAULT profile")
        return identifier

    def _parse_profile_limit(self, *, alter: bool) -> vexp.ProfileLimit:
        parameters: list[vexp.ProfileParameter] = []
        seen: set[str] = set()

        while self._curr:
            if self._match(TokenType.COMMA):
                self._raise_profile_error("PROFILE parameters are separated by spaces, not commas")
            if self._curr.token_type != TokenType.VAR or not self._curr.text.isascii():
                self._raise_profile_error(
                    f"Unsupported PROFILE parameter starting at {self._curr.text!r}"
                )
            name = self._curr.text.upper()
            if name not in self.PROFILE_PARAMETERS:
                self._raise_profile_error(f"Unsupported PROFILE parameter {name}")
            self._advance()
            if name in seen:
                self._raise_profile_error(f"Duplicate PROFILE parameter {name}")
            seen.add(name)
            value = self._parse_profile_value(name=name, alter=alter)
            parameters.append(
                self.expression(vexp.ProfileParameter(this=exp.var(name), expression=value))
            )

        if not parameters:
            self._raise_profile_error("PROFILE LIMIT requires at least one parameter")
        self._validate_profile_maximum(parameters)
        return self.expression(vexp.ProfileLimit(expressions=parameters))

    def _parse_profile_value(self, *, name: str, alter: bool) -> exp.Expr:
        if self._match_profile_var("UNLIMITED"):
            return self.expression(exp.var("UNLIMITED"))
        if self._match_profile_var("DEFAULT"):
            if not alter:
                self._raise_profile_error("CREATE PROFILE does not accept explicit DEFAULT values")
            return self.expression(exp.var("DEFAULT"))
        if not self._curr or self._curr.token_type != TokenType.NUMBER:
            self._raise_profile_error(f"PROFILE {name} requires an unsigned integer or UNLIMITED")
        raw = self._curr.text
        if not raw.isascii() or not raw.isdigit():
            self._raise_profile_error(f"PROFILE {name} requires an unsigned integer")
        self._advance()
        if name in self.PROFILE_POSITIVE_PARAMETERS and self._profile_digits_less(raw, "1"):
            self._raise_profile_error(f"PROFILE {name} must be at least 1")
        if name == "PASSWORD_MAX_LENGTH":
            if self._profile_digits_less(raw, "8"):
                self._raise_profile_error("PROFILE PASSWORD_MAX_LENGTH must be at least 8")
            if self._profile_digits_less("512", raw):
                self._raise_profile_error("PROFILE PASSWORD_MAX_LENGTH must be at most 512")
        return self.expression(exp.Literal.number(raw))

    @staticmethod
    def _profile_digits_less(left: str, right: str) -> bool:
        left_normalized = left.lstrip("0") or "0"
        right_normalized = right.lstrip("0") or "0"
        return (len(left_normalized), left_normalized) < (
            len(right_normalized),
            right_normalized,
        )

    def _validate_profile_maximum(self, parameters: list[vexp.ProfileParameter]) -> None:
        values = {parameter.name.upper(): parameter.expression for parameter in parameters}
        maximum = values.get("PASSWORD_MAX_LENGTH")
        if not isinstance(maximum, exp.Literal) or maximum.is_string or not maximum.this.isdigit():
            return
        for name in self.PROFILE_CHARACTER_MINIMUM_PARAMETERS:
            value = values.get(name)
            if (
                isinstance(value, exp.Literal)
                and not value.is_string
                and value.this.isdigit()
                and self._profile_digits_less(maximum.this, value.this)
            ):
                self._raise_profile_error(
                    f"PROFILE {name} cannot exceed explicit PASSWORD_MAX_LENGTH"
                )

    def _parse_create_resource_pool(self, replace: bool) -> vexp.CreateResourcePool:
        if replace:
            self.raise_error("CREATE OR REPLACE RESOURCE POOL is not supported by Vertica")
        if self._match_text_seq("IF", "NOT", "EXISTS", advance=False):
            self.raise_error("CREATE RESOURCE POOL does not support IF NOT EXISTS")

        pool = self._parse_lifecycle_identifier("CREATE RESOURCE POOL")
        subcluster = self._parse_resource_pool_subcluster()
        parameters = self._parse_resource_pool_parameters(pool=pool, alter=False)
        properties = self.expression(exp.Properties(expressions=parameters)) if parameters else None
        return self.expression(
            vexp.CreateResourcePool(
                this=pool,
                kind="RESOURCE POOL",
                properties=properties,
                subcluster=subcluster,
            )
        )

    def _parse_create_load_balance_group(self, replace: bool) -> vexp.CreateLoadBalanceGroup:
        if replace:
            self.raise_error("CREATE OR REPLACE LOAD BALANCE GROUP is not supported by Vertica")
        if self._match_text_seq("IF", "NOT", "EXISTS", advance=False):
            self.raise_error("CREATE LOAD BALANCE GROUP does not support IF NOT EXISTS")

        name = self._parse_connection_policy_identifier("CREATE LOAD BALANCE GROUP")
        if not self._match(TokenType.WITH):
            self.raise_error("CREATE LOAD BALANCE GROUP requires WITH")

        member_kind = self._parse_load_balance_group_member_kind("CREATE LOAD BALANCE GROUP WITH")
        members = self._parse_load_balance_group_members(member_kind, create=True)

        filter_value: exp.Literal | None = None
        if member_kind == "ADDRESS":
            if self._match_text_seq("FILTER"):
                self.raise_error("ADDRESS load balance groups do not support FILTER")
        else:
            if not self._match_text_seq("FILTER"):
                self.raise_error(f"{member_kind} load balance groups require FILTER")
            filter_value = self._parse_load_balance_group_string(
                f"{member_kind} load balance group FILTER"
            )

        policy: exp.Literal | None = None
        if self._match_text_seq("POLICY"):
            policy = self._parse_load_balance_group_string("LOAD BALANCE GROUP POLICY")
            if policy.this.upper() not in self.LOAD_BALANCE_GROUP_POLICIES:
                self.raise_error("LOAD BALANCE GROUP POLICY must be ROUNDROBIN, RANDOM, or NONE")

        if self._curr:
            self.raise_error(f"Unexpected CREATE LOAD BALANCE GROUP clause at {self._curr.text!r}")

        spec = self.expression(
            vexp.LoadBalanceGroupSpec(
                this=exp.var(member_kind),
                expressions=members,
                filter=filter_value,
                policy=policy,
            )
        )
        return self.expression(
            vexp.CreateLoadBalanceGroup(
                this=name,
                kind="LOAD BALANCE GROUP",
                spec=spec,
            )
        )

    def _parse_create_network_address(self, replace: bool) -> vexp.CreateNetworkAddress:
        if replace:
            self._raise_network_address_error(
                "CREATE OR REPLACE NETWORK ADDRESS is not supported by Vertica"
            )
        if self._match_text_seq("IF", "NOT", "EXISTS", advance=False):
            self._raise_network_address_error(
                "CREATE NETWORK ADDRESS does not support IF NOT EXISTS"
            )

        name = self._parse_connection_policy_identifier("CREATE NETWORK ADDRESS")
        if not self._match(TokenType.ON):
            self._raise_network_address_error("CREATE NETWORK ADDRESS requires ON")
        node = self._parse_connection_policy_identifier("CREATE NETWORK ADDRESS ON")
        if not self._match(TokenType.WITH):
            self._raise_network_address_error("CREATE NETWORK ADDRESS requires WITH")
        address = self._parse_connection_policy_string("CREATE NETWORK ADDRESS WITH")

        port = None
        if self._match_text_seq("PORT"):
            port = self._parse_network_address_port("CREATE NETWORK ADDRESS PORT")

        state = None
        if self._match_texts(("ENABLED", "DISABLED")):
            state = exp.var(self._prev.text.upper())

        if self._curr:
            self._raise_network_address_error(
                f"Unexpected CREATE NETWORK ADDRESS clause at {self._curr.text!r}"
            )

        spec = self.expression(
            vexp.NetworkAddressSpec(
                this=address,
                node=node,
                port=port,
                state=state,
            )
        )
        return self.expression(
            vexp.CreateNetworkAddress(
                this=name,
                kind="NETWORK ADDRESS",
                spec=spec,
            )
        )

    def _parse_load_balance_group_member_kind(self, label: str) -> str:
        if self._match_text_seq("ADDRESS"):
            return "ADDRESS"
        if self._match_text_seq("FAULT", "GROUP"):
            return "FAULT GROUP"
        if self._match_text_seq("SUBCLUSTER"):
            return "SUBCLUSTER"
        self.raise_error(f"{label} requires ADDRESS, FAULT GROUP, or SUBCLUSTER")
        return ""

    def _parse_load_balance_group_members(
        self, member_kind: str, *, create: bool = False
    ) -> list[exp.Identifier]:
        label = f"LOAD BALANCE GROUP {member_kind} member"
        members: list[exp.Identifier] = []
        while True:
            if not self._curr or (create and self._is_load_balance_group_clause_ahead(member_kind)):
                self.raise_error(f"{label} list cannot be empty")
            members.append(self._parse_connection_policy_identifier(label))
            if not self._match(TokenType.COMMA):
                break
            if not self._curr or (create and self._is_load_balance_group_clause_ahead(member_kind)):
                self.raise_error(f"Expected {label} after each comma")
        return members

    def _is_load_balance_group_clause_ahead(self, member_kind: str) -> bool:
        if (
            self._curr.token_type == TokenType.IDENTIFIER
            or self._next.token_type != TokenType.STRING
        ):
            return False
        clause = self._curr.text.upper()
        return clause == ("POLICY" if member_kind == "ADDRESS" else "FILTER")

    def _parse_load_balance_group_string(self, label: str) -> exp.Literal:
        return self._parse_connection_policy_string(label)

    def _parse_connection_policy_string(self, label: str) -> exp.Literal:
        value = self._parse_string()
        if not isinstance(value, exp.Literal) or not value.is_string:
            self.raise_error(f"{label} requires a quoted string literal")
            if self._curr:
                self._advance()
            return self.expression(exp.Literal.string(""))
        return value

    def _parse_network_address_port(self, label: str) -> exp.Literal:
        token = self._curr
        if (
            not token
            or token.token_type != TokenType.NUMBER
            or not token.text.isascii()
            or not token.text.isdigit()
        ):
            self._raise_network_address_error(f"{label} requires a nonnegative integer")
            if self._curr:
                self._advance()
            return self.expression(exp.Literal(this="0", is_string=False))
        port = self._parse_number()
        if not isinstance(port, exp.Literal):
            self._raise_network_address_error(f"{label} requires a nonnegative integer")
            return self.expression(exp.Literal(this="0", is_string=False))
        return port

    def _parse_create_routing_rule(self, replace: bool) -> vexp.CreateRoutingRule:
        if replace:
            self.raise_error("CREATE OR REPLACE ROUTING RULE is not supported by Vertica")
        if self._match_text_seq("IF", "NOT", "EXISTS", advance=False):
            self.raise_error("CREATE ROUTING RULE does not support IF NOT EXISTS")

        name: exp.Identifier | None = None
        unnamed_workload = self._match_text_seq("ROUTE", "WORKLOAD", advance=False)
        if unnamed_workload:
            self._match_text_seq("ROUTE")
        else:
            name = self._parse_connection_policy_identifier("CREATE ROUTING RULE")
            if not self._match_text_seq("ROUTE"):
                self.raise_error("CREATE ROUTING RULE requires ROUTE")

        source: exp.Expr | None
        if self._match_text_seq("WORKLOAD"):
            source = self._parse_connection_policy_identifier("CREATE ROUTING RULE ROUTE WORKLOAD")
            if not self._match_text_seq("TO", "SUBCLUSTER"):
                self.raise_error("Workload routing rules require TO SUBCLUSTER")
            destinations = self._parse_connection_policy_identifiers("routing subcluster")
            priority = None
            if self._match_text_seq("PRIORITY"):
                priority = self._parse_routing_rule_priority()
            mode = "WORKLOAD"
        else:
            if name is None:
                self.raise_error("Classic routing rules require a rule name")
            source = self._parse_string()
            if not isinstance(source, exp.Literal) or not source.is_string:
                self.raise_error("Classic routing rules require a quoted address range")
            if not self._match_text_seq("TO"):
                self.raise_error("Classic routing rules require TO")
            destinations = [self._parse_connection_policy_identifier("classic routing rule group")]
            priority = None
            mode = "ADDRESS"

        if self._curr:
            self.raise_error(f"Unexpected CREATE ROUTING RULE clause at {self._curr.text!r}")

        route = self.expression(
            vexp.RoutingRuleSpec(
                mode=exp.var(mode),
                this=source,
                expressions=destinations,
                priority=priority,
            )
        )
        return self.expression(vexp.CreateRoutingRule(this=name, kind="ROUTING RULE", route=route))

    def _parse_connection_policy_identifiers(self, label: str) -> list[exp.Identifier]:
        identifiers = [self._parse_connection_policy_identifier(label)]
        while self._match(TokenType.COMMA):
            if not self._curr:
                self.raise_error(f"Expected {label} after each comma")
            identifiers.append(self._parse_connection_policy_identifier(label))
        return identifiers

    def _parse_connection_policy_identifier(self, statement: str) -> exp.Identifier:
        if (
            not self._curr
            or self._curr.token_type not in self.ID_VAR_TOKENS
            or self._curr.token_type
            in {
                TokenType.DEFAULT,
                TokenType.FALSE,
                TokenType.NULL,
                TokenType.TRUE,
            }
        ):
            self.raise_error(f"{statement} requires an identifier")
            if self._curr:
                self._advance()
            return self.expression(exp.Identifier(this="", quoted=True))
        identifier = self._parse_id_var(any_token=False)
        if not isinstance(identifier, exp.Identifier):
            self.raise_error(f"{statement} requires an identifier")
            return self.expression(exp.Identifier(this="", quoted=True))
        if not isinstance(identifier.this, str) or not identifier.this:
            self.raise_error(f"{statement} requires a nonempty identifier")
        elif not identifier.quoted and not self._is_connection_policy_identifier(identifier.this):
            self.raise_error(f"{statement} requires a valid unquoted identifier")
        if self._match(TokenType.DOT, advance=False):
            self.raise_error(f"{statement} names cannot be schema-qualified")
        return identifier

    @staticmethod
    def _is_connection_policy_identifier(name: str) -> bool:
        return (
            bool(name)
            and (name[0] == "_" or (name[0].isascii() and name[0].isalpha()))
            and all(
                character in {"_", "$"}
                or (character.isascii() and character.isdigit())
                or character.isalpha()
                for character in name[1:]
            )
        )

    def _parse_routing_rule_priority(self) -> exp.Literal:
        if self._match(TokenType.DASH, advance=False):
            self.raise_error("ROUTING RULE PRIORITY must be a nonnegative integer")
        self._match(TokenType.PLUS)
        priority = self._parse_number()
        if not priority or not priority.is_int:
            self.raise_error("ROUTING RULE PRIORITY must be a nonnegative integer")
        assert isinstance(priority, exp.Literal)
        return priority

    def _parse_routing_rule_target(self, statement: str) -> vexp.RoutingRuleTarget:
        workload = self._match_text_seq("FOR", "WORKLOAD")
        if not workload and self._match(TokenType.FOR, advance=False):
            self.raise_error(f"{statement} FOR must be followed by WORKLOAD")
        target = self._parse_connection_policy_identifier(statement)
        return self.expression(vexp.RoutingRuleTarget(this=target, workload=workload))

    def _parse_alter_load_balance_group(self) -> vexp.AlterLoadBalanceGroup:
        target = self._parse_connection_policy_identifier("ALTER LOAD BALANCE GROUP")

        if self._match_text_seq("RENAME"):
            if not self._match_text_seq("TO"):
                self.raise_error("ALTER LOAD BALANCE GROUP RENAME requires TO")
            action: exp.Expr = self.expression(
                exp.AlterRename(
                    this=self._parse_connection_policy_identifier("ALTER LOAD BALANCE GROUP RENAME")
                )
            )
        elif self._match_text_seq("SET"):
            action = self._parse_set_load_balance_group_action()
        elif self._match_texts(("ADD", "DROP")):
            verb = self._prev.text.upper()
            member_kind = self._parse_load_balance_group_member_kind(
                f"ALTER LOAD BALANCE GROUP {verb}"
            )
            action = self.expression(
                vexp.LoadBalanceGroupAction(
                    this=exp.var(verb),
                    member_kind=exp.var(member_kind),
                    expressions=self._parse_load_balance_group_members(member_kind),
                )
            )
        else:
            self.raise_error("ALTER LOAD BALANCE GROUP requires a supported action")

        if self._curr:
            self.raise_error(f"Unexpected ALTER LOAD BALANCE GROUP clause at {self._curr.text!r}")
        return self.expression(
            vexp.AlterLoadBalanceGroup(
                this=target,
                kind="LOAD BALANCE GROUP",
                actions=[action],
            )
        )

    def _parse_set_load_balance_group_action(self) -> vexp.LoadBalanceGroupAction:
        if self._match_text_seq("FILTER"):
            property_name = "FILTER"
        elif self._match_text_seq("POLICY"):
            property_name = "POLICY"
        else:
            self.raise_error("ALTER LOAD BALANCE GROUP SET requires FILTER or POLICY")
            property_name = ""

        if not self._match_text_seq("TO"):
            self.raise_error(f"ALTER LOAD BALANCE GROUP SET {property_name} requires TO")
        value = self._parse_load_balance_group_string(
            f"ALTER LOAD BALANCE GROUP SET {property_name}"
        )
        if property_name == "POLICY" and value.this.upper() not in self.LOAD_BALANCE_GROUP_POLICIES:
            self.raise_error("LOAD BALANCE GROUP POLICY must be ROUNDROBIN, RANDOM, or NONE")
        return self.expression(
            vexp.LoadBalanceGroupAction(
                this=exp.var(f"SET {property_name}"),
                expression=value,
            )
        )

    def _parse_alter_network_address(self) -> vexp.AlterNetworkAddress:
        target = self._parse_connection_policy_identifier("ALTER NETWORK ADDRESS")
        action: exp.Expr = self.expression(vexp.NetworkAddressAction(this=exp.Var(this="")))

        if self._match_text_seq("RENAME"):
            if not self._match_text_seq("TO"):
                self._raise_network_address_error("ALTER NETWORK ADDRESS RENAME requires TO")
            action = self.expression(
                exp.AlterRename(
                    this=self._parse_connection_policy_identifier("ALTER NETWORK ADDRESS RENAME")
                )
            )
        elif self._match_text_seq("SET"):
            if not self._match_text_seq("TO"):
                self._raise_network_address_error("ALTER NETWORK ADDRESS SET requires TO")
            address = self._parse_connection_policy_string("ALTER NETWORK ADDRESS SET TO")
            port = None
            if self._match_text_seq("PORT"):
                port = self._parse_network_address_port("ALTER NETWORK ADDRESS PORT")
            action = self.expression(
                vexp.NetworkAddressAction(
                    this=exp.var("SET"),
                    expression=address,
                    port=port,
                )
            )
        elif self._match_texts(("ENABLE", "DISABLE")):
            action = self.expression(
                vexp.NetworkAddressAction(this=exp.var(self._prev.text.upper()))
            )
        else:
            self._raise_network_address_error("ALTER NETWORK ADDRESS requires a supported action")

        if self._curr:
            self._raise_network_address_error(
                f"Unexpected ALTER NETWORK ADDRESS clause at {self._curr.text!r}"
            )
        return self.expression(
            vexp.AlterNetworkAddress(
                this=target,
                kind="NETWORK ADDRESS",
                actions=[action],
            )
        )

    def _parse_alter_routing_rule(self) -> vexp.AlterRoutingRule:
        target = self._parse_routing_rule_target("ALTER ROUTING RULE")

        if self._match_text_seq("RENAME"):
            if not self._match_text_seq("TO"):
                self.raise_error("ALTER ROUTING RULE RENAME requires TO")
            action: exp.Expr = self.expression(
                exp.AlterRename(
                    this=self._parse_connection_policy_identifier("ALTER ROUTING RULE RENAME")
                )
            )
        elif self._match_text_seq("SET"):
            action = self._parse_set_routing_rule_action()
        elif self._match_texts(("ADD", "REMOVE")):
            verb = self._prev.text.upper()
            if not self._match_text_seq("SUBCLUSTER"):
                self.raise_error(f"ALTER ROUTING RULE {verb} requires SUBCLUSTER")
            action = self.expression(
                vexp.RoutingRuleAction(
                    this=exp.var(f"{verb} SUBCLUSTER"),
                    expressions=self._parse_connection_policy_identifiers("routing subcluster"),
                )
            )
        else:
            self.raise_error("ALTER ROUTING RULE requires a supported action")

        if self._curr:
            self.raise_error(f"Unexpected ALTER ROUTING RULE clause at {self._curr.text!r}")
        return self.expression(
            vexp.AlterRoutingRule(this=target, kind="ROUTING RULE", actions=[action])
        )

    def _parse_set_routing_rule_action(self) -> vexp.RoutingRuleAction:
        if not self._match_texts(("ROUTE", "GROUP", "WORKLOAD", "SUBCLUSTER", "PRIORITY")):
            self.raise_error("ALTER ROUTING RULE SET requires a supported property")
        property_name = self._prev.text.upper()
        if not self._match_text_seq("TO"):
            self.raise_error(f"ALTER ROUTING RULE SET {property_name} requires TO")

        if property_name == "ROUTE":
            value = self._parse_string()
            if not isinstance(value, exp.Literal) or not value.is_string:
                self.raise_error("ALTER ROUTING RULE SET ROUTE requires a quoted address range")
            return self.expression(
                vexp.RoutingRuleAction(this=exp.var("SET ROUTE"), expression=value)
            )
        if property_name == "SUBCLUSTER":
            return self.expression(
                vexp.RoutingRuleAction(
                    this=exp.var("SET SUBCLUSTER"),
                    expressions=self._parse_connection_policy_identifiers("routing subcluster"),
                )
            )
        if property_name == "PRIORITY":
            return self.expression(
                vexp.RoutingRuleAction(
                    this=exp.var("SET PRIORITY"),
                    expression=self._parse_routing_rule_priority(),
                )
            )

        value = self._parse_connection_policy_identifier(f"ALTER ROUTING RULE SET {property_name}")
        return self.expression(
            vexp.RoutingRuleAction(this=exp.var(f"SET {property_name}"), expression=value)
        )

    def _parse_drop_load_balance_group(self, exists: bool) -> vexp.DropLoadBalanceGroup:
        if exists:
            self.raise_error("DROP LOAD BALANCE GROUP IF EXISTS must follow LOAD BALANCE GROUP")
        if_exists = bool(self._parse_exists())
        target = self._parse_connection_policy_identifier("DROP LOAD BALANCE GROUP")
        if self._match(TokenType.COMMA, advance=False):
            self.raise_error("DROP LOAD BALANCE GROUP accepts exactly one target")
        cascade = self._match_text_seq("CASCADE")
        if self._match_text_seq("RESTRICT", advance=False):
            self.raise_error("DROP LOAD BALANCE GROUP does not support RESTRICT")
        if self._curr:
            self.raise_error(f"Unexpected DROP LOAD BALANCE GROUP clause at {self._curr.text!r}")
        return self.expression(
            vexp.DropLoadBalanceGroup(
                this=target,
                kind="LOAD BALANCE GROUP",
                exists=if_exists,
                cascade=cascade,
            )
        )

    def _parse_drop_network_address(self, exists: bool) -> vexp.DropNetworkAddress:
        if exists:
            self._raise_network_address_error(
                "DROP NETWORK ADDRESS IF EXISTS must follow NETWORK ADDRESS"
            )
        if_exists = bool(self._parse_exists())
        target = self._parse_connection_policy_identifier("DROP NETWORK ADDRESS")
        if self._match(TokenType.COMMA, advance=False):
            self._raise_network_address_error("DROP NETWORK ADDRESS accepts exactly one target")
        cascade = self._match_text_seq("CASCADE")
        if self._match_text_seq("RESTRICT", advance=False):
            self._raise_network_address_error("DROP NETWORK ADDRESS does not support RESTRICT")
        if self._curr:
            self._raise_network_address_error(
                f"Unexpected DROP NETWORK ADDRESS clause at {self._curr.text!r}"
            )
        return self.expression(
            vexp.DropNetworkAddress(
                this=target,
                kind="NETWORK ADDRESS",
                exists=if_exists,
                cascade=cascade,
            )
        )

    def _parse_drop_routing_rule(self, exists: bool) -> vexp.DropRoutingRule:
        if exists:
            self.raise_error("DROP ROUTING RULE IF EXISTS must follow ROUTING RULE")
        if_exists = bool(self._parse_exists())
        target = self._parse_routing_rule_target("DROP ROUTING RULE")
        if self._match(TokenType.COMMA, advance=False):
            self.raise_error("DROP ROUTING RULE accepts exactly one target")
        if self._match_texts(("CASCADE", "RESTRICT"), advance=False):
            self.raise_error("DROP ROUTING RULE does not support CASCADE or RESTRICT")
        if self._curr:
            self.raise_error(f"Unexpected DROP ROUTING RULE clause at {self._curr.text!r}")
        return self.expression(
            vexp.DropRoutingRule(this=target, kind="ROUTING RULE", exists=if_exists)
        )

    def _parse_alter_role(self) -> exp.Alter:
        role = self._parse_lifecycle_identifier("ALTER ROLE")
        if not self._match_text_seq("RENAME"):
            self.raise_error("ALTER ROLE requires RENAME TO")
        if not self._match_text_seq("TO"):
            self.raise_error("ALTER ROLE RENAME requires TO")
        new_name = self._parse_lifecycle_identifier("ALTER ROLE RENAME TO")
        if self._curr:
            self.raise_error(f"Unexpected ALTER ROLE clause at {self._curr.text!r}")

        return self.expression(
            exp.Alter(
                this=role,
                kind="ROLE",
                actions=[self.expression(exp.AlterRename(this=new_name))],
            )
        )

    def _parse_alter_user(self) -> vexp.AlterUser:
        user = self._parse_user_identifier("ALTER USER")
        action: exp.Expr = self.expression(vexp.UserAction(this=exp.Var(this="")))

        if self._match_user_keywords("RENAME"):
            if not self._match_user_keywords("TO"):
                self._raise_user_error("ALTER USER RENAME requires TO")
            action = self.expression(
                exp.AlterRename(this=self._parse_user_identifier("ALTER USER RENAME TO"))
            )
        elif self._match_user_keywords("ACCOUNT"):
            if self._match_user_keywords("LOCK"):
                state = "LOCK"
            elif self._match_user_keywords("UNLOCK"):
                state = "UNLOCK"
            else:
                self._raise_user_error("ALTER USER ACCOUNT requires LOCK or UNLOCK")
                state = ""
            action = self.expression(vexp.UserAction(this=exp.var(f"ACCOUNT {state}")))
        elif self._match_user_keywords("PASSWORD"):
            if not self._match_user_keywords("EXPIRE"):
                self._raise_user_error("ALTER USER PASSWORD requires EXPIRE")
            action = self.expression(vexp.UserAction(this=exp.var("PASSWORD EXPIRE")))
        else:
            self._raise_user_error("ALTER USER requires a supported action")

        if self._curr:
            self._raise_user_error(f"Unsupported ALTER USER clause at {self._curr.text!r}")
        return self.expression(
            vexp.AlterUser(
                this=user,
                kind="USER",
                actions=[action],
            )
        )

    def _parse_alter_profile(self) -> vexp.AlterProfile:
        profile = self._parse_profile_identifier("ALTER PROFILE", allow_default=True)

        if self._match_profile_var("LIMIT"):
            action: exp.Expr = self._parse_profile_limit(alter=True)
        elif self._match_profile_var("RENAME"):
            if profile.name.upper() == "DEFAULT":
                self._raise_profile_error("ALTER PROFILE cannot rename the DEFAULT profile")
            if not self._match_profile_var("TO"):
                self._raise_profile_error("ALTER PROFILE RENAME requires TO")
            action = self.expression(
                exp.AlterRename(this=self._parse_profile_identifier("ALTER PROFILE RENAME TO"))
            )
            if self._curr:
                self._raise_profile_error(f"Unexpected ALTER PROFILE clause at {self._curr.text!r}")
        else:
            self._raise_profile_error("ALTER PROFILE requires LIMIT or RENAME TO")
            action = self.expression(vexp.ProfileLimit(expressions=[]))

        return self.expression(vexp.AlterProfile(this=profile, kind="PROFILE", actions=[action]))

    def _parse_alter_resource_pool(self) -> vexp.AlterResourcePool:
        pool = self._parse_lifecycle_identifier("ALTER RESOURCE POOL")
        subcluster = self._parse_resource_pool_subcluster()
        parameters = self._parse_resource_pool_parameters(pool=pool, alter=True)
        if not parameters:
            self.raise_error("ALTER RESOURCE POOL requires at least one parameter")

        return self.expression(
            vexp.AlterResourcePool(
                this=pool,
                kind="RESOURCE POOL",
                actions=parameters,
                subcluster=subcluster,
            )
        )

    def _parse_lifecycle_identifier(self, statement: str) -> exp.Identifier:
        identifier = self._parse_id_var()
        if not isinstance(identifier, exp.Identifier):
            self.raise_error(f"{statement} requires an unqualified name")
        assert isinstance(identifier, exp.Identifier)
        if self._match(TokenType.DOT, advance=False):
            self.raise_error(f"{statement} names cannot be schema-qualified")
        return identifier

    def _parse_resource_pool_subcluster(self) -> vexp.ResourcePoolSubcluster | None:
        if not self._match(TokenType.FOR):
            return None

        if self._match_text_seq("CURRENT"):
            if not self._match_text_seq("SUBCLUSTER"):
                self.raise_error("RESOURCE POOL FOR CURRENT requires SUBCLUSTER")
            return self.expression(vexp.ResourcePoolSubcluster(current=True))

        if not self._match_text_seq("SUBCLUSTER"):
            self.raise_error("RESOURCE POOL FOR requires SUBCLUSTER or CURRENT SUBCLUSTER")
        name = self._parse_lifecycle_identifier("RESOURCE POOL FOR SUBCLUSTER")
        return self.expression(vexp.ResourcePoolSubcluster(this=name))

    def _parse_resource_pool_parameters(
        self, pool: exp.Identifier, alter: bool
    ) -> list[vexp.ResourcePoolParameter]:
        parameters: list[vexp.ResourcePoolParameter] = []
        seen: set[str] = set()

        while self._curr:
            if self._match(TokenType.COMMA):
                self.raise_error("RESOURCE POOL parameters are separated by spaces, not commas")
            if self._match(TokenType.FOR, advance=False):
                self.raise_error("RESOURCE POOL subcluster selector must precede parameters")

            parameter = self._parse_resource_pool_parameter(pool=pool, alter=alter)
            if not parameter:
                self.raise_error(
                    f"Unsupported RESOURCE POOL parameter starting at {self._curr.text!r}"
                )
            assert parameter is not None
            name = parameter.name.upper()
            if name in seen:
                self.raise_error(f"Duplicate RESOURCE POOL parameter {name}")
            seen.add(name)
            parameters.append(parameter)

        affinity_set = "CPUAFFINITYSET" in seen
        affinity_mode = "CPUAFFINITYMODE" in seen
        if affinity_set != affinity_mode:
            self.raise_error(
                "RESOURCE POOL CPUAFFINITYSET and CPUAFFINITYMODE must be set together"
            )

        if affinity_set and affinity_mode:
            by_name = {parameter.name.upper(): parameter for parameter in parameters}
            mode = by_name["CPUAFFINITYMODE"].args.get("value")
            affinity = by_name["CPUAFFINITYSET"].args.get("value")
            if self._resource_pool_keyword_name(mode) == "ANY" and self._resource_pool_keyword_name(
                affinity
            ) not in {"DEFAULT", "NONE"}:
                self.raise_error("RESOURCE POOL CPUAFFINITYMODE ANY requires CPUAFFINITYSET NONE")

        return parameters

    def _parse_resource_pool_parameter(
        self, pool: exp.Identifier, alter: bool
    ) -> vexp.ResourcePoolParameter | None:
        if self._match_text_seq("CASCADE"):
            if not self._match_text_seq("TO"):
                self.raise_error("RESOURCE POOL CASCADE requires TO")
            name = "CASCADE TO"
        elif self._match_texts(self.RESOURCE_POOL_PARAMETERS - {"CASCADE TO"}):
            name = self._prev.text.upper()
        else:
            return None

        value = self._parse_resource_pool_parameter_value(name=name, pool=pool, alter=alter)
        return self.expression(vexp.ResourcePoolParameter(this=exp.var(name), value=value))

    def _parse_resource_pool_parameter_value(
        self, name: str, pool: exp.Identifier, alter: bool
    ) -> exp.Expr:
        if self._match(TokenType.DEFAULT):
            if not alter:
                self.raise_error("RESOURCE POOL DEFAULT values are only valid in ALTER")
            return self._resource_pool_keyword("DEFAULT")

        if name == "CASCADE TO":
            return self._parse_lifecycle_identifier("RESOURCE POOL CASCADE TO")
        if name == "CPUAFFINITYMODE":
            return self._parse_resource_pool_enum(name, {"ANY", "EXCLUSIVE", "SHARED"})
        if name == "CPUAFFINITYSET":
            if self._match_text_seq("NONE"):
                return self._resource_pool_keyword("NONE")
            value = self._parse_resource_pool_string(name)
            if not re.fullmatch(r"(?:\d+(?:,\d+)*|\d+-\d+|\d+%)", value.this):
                self.raise_error(
                    "RESOURCE POOL CPUAFFINITYSET requires a quoted CPU list, range, or percentage"
                )
            return value
        if name == "EXECUTIONPARALLELISM":
            if self._match_text_seq("AUTO"):
                return self._resource_pool_keyword("AUTO")
            return self._parse_resource_pool_integer(name, minimum=0)
        if name == "MAXCONCURRENCY":
            if self._match_text_seq("NONE"):
                return self._resource_pool_keyword("NONE")
            return self._parse_resource_pool_integer(name, minimum=0)
        if name in {"MAXMEMORYSIZE", "MAXQUERYMEMORYSIZE"}:
            if self._match_text_seq("NONE"):
                return self._resource_pool_keyword("NONE")
            return self._parse_resource_pool_memory(name)
        if name == "MEMORYSIZE":
            return self._parse_resource_pool_memory(name)
        if name == "PLANNEDCONCURRENCY":
            if self._match_text_seq("AUTO"):
                return self._resource_pool_keyword("AUTO")
            return self._parse_resource_pool_integer(name, minimum=1)
        if name == "PRIORITY":
            if self._match_text_seq("HOLD"):
                return self._resource_pool_keyword("HOLD")
            priority_limit = (
                110
                if alter
                and not pool.quoted
                and pool.name.upper() in self.RESOURCE_POOL_EXTENDED_PRIORITY_NAMES
                else 100
            )
            return self._parse_resource_pool_integer(
                name, minimum=-priority_limit, maximum=priority_limit
            )
        if name == "QUEUETIMEOUT":
            if self._curr.token_type == TokenType.STRING:
                value = self._parse_resource_pool_string(name)
                if value.this.upper() == "NONE":
                    return self._resource_pool_keyword("NONE", quoted=True)
                return value
            return self._parse_resource_pool_integer(name, minimum=0)
        if name == "RUNTIMECAP":
            if self._match_text_seq("NONE"):
                return self._resource_pool_keyword("NONE")
            return self._parse_resource_pool_string(name)
        if name == "RUNTIMEPRIORITY":
            return self._parse_resource_pool_enum(name, {"HIGH", "LOW", "MEDIUM"})
        if name == "RUNTIMEPRIORITYTHRESHOLD":
            return self._parse_resource_pool_integer(name, minimum=0)
        if name == "SINGLEINITIATOR":
            if self._match(TokenType.TRUE):
                return self.expression(exp.Boolean(this=True))
            if self._match(TokenType.FALSE):
                return self.expression(exp.Boolean(this=False))
            self.raise_error("RESOURCE POOL SINGLEINITIATOR requires TRUE or FALSE")

        raise AssertionError(f"Unhandled RESOURCE POOL parameter: {name}")

    def _parse_resource_pool_enum(self, name: str, values: set[str]) -> exp.Expr:
        if not self._match_texts(values):
            self.raise_error(f"RESOURCE POOL {name} requires one of {', '.join(sorted(values))}")
        return self._resource_pool_keyword(self._prev.text.upper())

    def _parse_resource_pool_memory(self, name: str) -> exp.Literal:
        value = self._parse_resource_pool_string(name)
        if not re.fullmatch(r"\d+(?:%|[KMGT])", value.this, flags=re.IGNORECASE):
            self.raise_error(
                f"RESOURCE POOL {name} requires a quoted integer percentage or K/M/G/T size"
            )
        return value

    def _parse_resource_pool_string(self, name: str) -> exp.Literal:
        value = self._parse_string()
        if not isinstance(value, exp.Literal) or not value.is_string:
            self.raise_error(f"RESOURCE POOL {name} requires a string literal")
        assert isinstance(value, exp.Literal)
        return value

    def _parse_resource_pool_integer(
        self, name: str, minimum: int | None = None, maximum: int | None = None
    ) -> exp.Expr:
        negative = self._match(TokenType.DASH)
        if not negative:
            self._match(TokenType.PLUS)
        number = self._parse_number()
        if not number or not number.is_int:
            self.raise_error(f"RESOURCE POOL {name} requires an integer")
        assert number is not None

        numeric_value = int(number.this) * (-1 if negative else 1)
        if minimum is not None and numeric_value < minimum:
            self.raise_error(f"RESOURCE POOL {name} must be at least {minimum}")
        if maximum is not None and numeric_value > maximum:
            self.raise_error(f"RESOURCE POOL {name} must be at most {maximum}")

        return self.expression(exp.Neg(this=number)) if negative else number

    def _resource_pool_keyword(self, name: str, quoted: bool = False) -> exp.Expr:
        return self.expression(vexp.ResourcePoolKeyword(this=exp.var(name), quoted=quoted))

    @staticmethod
    def _resource_pool_keyword_name(expression: exp.Expr | None) -> str | None:
        return expression.name.upper() if isinstance(expression, vexp.ResourcePoolKeyword) else None

    def _parse_create_sequence(self, replace: bool) -> exp.Create:
        if replace:
            self.raise_error("CREATE OR REPLACE SEQUENCE is not supported by Vertica")

        exists = self._parse_exists(not_=True)
        sequence = self._parse_table_parts(schema=True)
        options = self._parse_vertica_sequence_options(alter=False)

        if self._curr:
            self.raise_error(
                f"Unexpected or out-of-order CREATE SEQUENCE clause at {self._curr.text!r}"
            )

        return self.expression(
            exp.Create(
                this=sequence,
                kind="SEQUENCE",
                exists=exists,
                properties=(
                    self.expression(exp.Properties(expressions=[options])) if options else None
                ),
            )
        )

    def _parse_create_schema(self, replace: bool) -> exp.Create:
        if replace:
            self.raise_error("CREATE OR REPLACE SCHEMA is not supported by Vertica")

        exists = self._parse_exists(not_=True)
        schema = self._parse_table_parts(schema=True, is_db_reference=True)
        properties: list[exp.Expr] = []

        if self._match_text_seq("AUTHORIZATION"):
            owner = self._parse_id_var()
            if not owner:
                self.raise_error("CREATE SCHEMA AUTHORIZATION requires a user name")
            properties.append(self.expression(vexp.SchemaAuthorizationProperty(this=owner)))

        if self._match(TokenType.DEFAULT):
            privileges = self._parse_inherited_privileges_property()
            if not privileges:
                self.raise_error("CREATE SCHEMA DEFAULT requires INCLUDE or EXCLUDE PRIVILEGES")
            assert privileges is not None
            properties.append(
                self.expression(vexp.DefaultInheritedPrivilegesProperty(**privileges.args))
            )

        quota = self._parse_disk_quota_property()
        if quota:
            properties.append(quota)

        if self._curr:
            self.raise_error(
                f"Unexpected or out-of-order CREATE SCHEMA clause at {self._curr.text!r}"
            )

        return self.expression(
            exp.Create(
                this=schema,
                kind="SCHEMA",
                exists=exists,
                properties=(
                    self.expression(exp.Properties(expressions=properties)) if properties else None
                ),
            )
        )

    def _parse_create_view(self, replace: bool) -> exp.Create:
        view = self._parse_table_parts(schema=True)
        assert view is not None
        target: exp.Expr = view
        if self._match(TokenType.L_PAREN, advance=False):
            parsed_schema = self._parse_schema(this=view)
            assert parsed_schema is not None
            target = parsed_schema
            if not target.expressions or any(
                not isinstance(column, exp.Identifier) for column in target.expressions
            ):
                self.raise_error("CREATE VIEW column lists require one or more column names")

        privileges = self._parse_inherited_privileges_property()
        if not self._match(TokenType.ALIAS):
            self.raise_error("CREATE VIEW requires AS followed by a query")

        query = self._parse_ddl_select()
        if not query:
            self.raise_error("CREATE VIEW requires a SELECT query")

        if self._curr:
            self.raise_error(f"Unexpected CREATE VIEW clause at {self._curr.text!r}")

        return self.expression(
            exp.Create(
                this=target,
                kind="VIEW",
                expression=query,
                replace=replace,
                properties=(
                    self.expression(exp.Properties(expressions=[privileges]))
                    if privileges
                    else None
                ),
            )
        )

    def _parse_vertica_sequence_options(self, alter: bool) -> exp.SequenceProperties | None:
        sequence = self.expression(exp.SequenceProperties())
        options: list[exp.Expr] = []
        seen: set[str] = set()
        last_rank = 0
        parsed_any = False

        while self._curr:
            slot: str | None = None
            rank = 0
            value: exp.Expr | None = None
            option: str | None = None

            if self._match_text_seq("INCREMENT"):
                self._match_text_seq("BY")
                slot, rank = "increment", 1
                value = self._parse_sequence_integer("INCREMENT")
            elif self._match_text_seq("NO", "MINVALUE"):
                slot, rank, option = "minvalue", 2, "NO MINVALUE"
            elif self._match_text_seq("MINVALUE"):
                slot, rank = "minvalue", 2
                value = self._parse_sequence_integer("MINVALUE")
            elif self._match_text_seq("NO", "MAXVALUE"):
                slot, rank, option = "maxvalue", 3, "NO MAXVALUE"
            elif self._match_text_seq("MAXVALUE"):
                slot, rank = "maxvalue", 3
                value = self._parse_sequence_integer("MAXVALUE")
            elif alter and self._match_text_seq("RESTART"):
                self._match(TokenType.WITH)
                slot, rank = "start", 4
                value = self._parse_sequence_integer("RESTART")
            elif not alter and (self._match(TokenType.START_WITH) or self._match_text_seq("START")):
                if self._prev.token_type != TokenType.START_WITH:
                    self._match(TokenType.WITH)
                slot, rank = "start", 4
                value = self._parse_sequence_integer("START")
            elif self._match_text_seq("NO", "CACHE"):
                slot, rank, option = "cache", 5, "NO CACHE"
            elif self._match_text_seq("CACHE"):
                slot, rank = "cache", 5
                value = self._parse_sequence_integer("CACHE")
            elif self._match_text_seq("NO", "CYCLE"):
                slot, rank, option = "cycle", 6, "NO CYCLE"
            elif self._match_text_seq("CYCLE"):
                slot, rank, option = "cycle", 6, "CYCLE"
            else:
                break

            assert slot is not None
            if slot in seen:
                self.raise_error(f"Duplicate or conflicting SEQUENCE {slot.upper()} clause")
            if rank < last_rank:
                self.raise_error(f"Out-of-order SEQUENCE clause {slot.upper()}")

            seen.add(slot)
            last_rank = rank
            parsed_any = True
            if option:
                options.append(exp.var(option))
            else:
                sequence.set(slot, value)

        sequence.set("options", options or None)
        return sequence if parsed_any else None

    def _parse_sequence_integer(self, clause: str) -> exp.Expr:
        negative = self._match(TokenType.DASH)
        if not negative:
            self._match(TokenType.PLUS)

        number = self._parse_number()
        if not number or not number.is_int:
            self.raise_error(f"SEQUENCE {clause} requires an integer")
        assert number is not None

        return self.expression(exp.Neg(this=number)) if negative else number

    def _parse_alter(self) -> exp.Alter | exp.Command:
        index = self._index
        words = [token.text.upper() for token in self._tokens[self._index :]]
        self._reject_sensitive_user_statement("ALTER", words)
        self._reject_prefixed_routing_rule("ALTER", words)
        self._reject_prefixed_load_balance_group("ALTER", words)
        self._reject_prefixed_network_address("ALTER", words)
        self._reject_prefixed_profile("ALTER", words)
        self._reject_prefixed_user("ALTER", words)
        if self._curr.token_type == TokenType.TABLE and self._has_mixed_reorganize_action():
            self.raise_error(
                "Mixed ALTER TABLE REORGANIZE action lists are not yet represented semantically"
            )
        if self._match_text_seq("ROLE"):
            return self._parse_alter_role()
        if self._match(TokenType.LOAD):
            if not self._match_text_seq("BALANCE", "GROUP"):
                self.raise_error("ALTER LOAD must be followed by BALANCE GROUP")
            return self._parse_alter_load_balance_group()
        if self._match_network_object("ADDRESS"):
            return self._parse_alter_network_address()
        if self._curr.text.upper() == "NETWORK" and not self._match_network_object(
            "INTERFACE", advance=False
        ):
            self._raise_network_address_error("ALTER NETWORK must be followed by ADDRESS")
        if self._match_profile_object():
            return self._parse_alter_profile()
        if self._curr.text.upper() == "PROFILE":
            self._raise_profile_error("ALTER PROFILE requires the unquoted PROFILE object kind")
        if self._match_user_object():
            return self._parse_alter_user()
        if self._curr.text.upper() == "USER":
            self._raise_user_error("ALTER USER requires the unquoted USER object kind")
        if self._match_text_seq("RESOURCE", "POOL"):
            return self._parse_alter_resource_pool()
        if self._match_text_seq("ROUTING", "RULE"):
            return self._parse_alter_routing_rule()
        if self._match_text_seq("ROUTING", advance=False):
            self.raise_error("ALTER ROUTING must be followed by RULE")
        if self._match(TokenType.SEQUENCE):
            return self._parse_alter_sequence()
        if self._match(TokenType.TABLE):
            if self._match_text_seq("REORGANIZE", advance=False) and not self._next:
                self.raise_error("ALTER TABLE REORGANIZE requires a table name")

            table = self._parse_table_parts(schema=True)
            if isinstance(table, exp.Table) and (
                self._match(TokenType.PARTITION_BY, advance=False)
                or self._match_text_seq("REORGANIZE", advance=False)
            ):
                return self._parse_alter_table_partitioning(table)
        self._retreat(index)
        return super()._parse_alter()

    def _has_mixed_reorganize_action(self) -> bool:
        """Detect REORGANIZE only when it starts a later top-level ALTER action."""

        depth = 0
        action_boundary = False
        opening = {TokenType.L_PAREN, TokenType.L_BRACKET, TokenType.L_BRACE}
        closing = {TokenType.R_PAREN, TokenType.R_BRACKET, TokenType.R_BRACE}
        for token in self._tokens[self._index + 1 :]:
            if token.token_type in opening:
                depth += 1
            elif token.token_type in closing:
                depth = max(0, depth - 1)
            elif depth == 0 and token.token_type == TokenType.COMMA:
                action_boundary = True
            elif depth == 0:
                if action_boundary and token.text.upper() == "REORGANIZE":
                    return True
                action_boundary = False
        return False

    def _parse_alter_table_partitioning(
        self, table: exp.Table
    ) -> vexp.AlterTablePartition | vexp.ReorganizeTable:
        if self._match(TokenType.PARTITION_BY):
            partition_expression = self._parse_disjunction()
            if not partition_expression:
                self.raise_error("ALTER TABLE PARTITION BY requires an expression")

            group_expression = None
            if self._match(TokenType.GROUP_BY):
                group_expression = self._parse_disjunction()
                if not group_expression:
                    self.raise_error("ALTER TABLE partition GROUP BY requires an expression")

            active_partition_count = None
            if self._match(TokenType.SET):
                if not self._match_text_seq("ACTIVEPARTITIONCOUNT"):
                    self.raise_error(
                        "ALTER TABLE partition SET must be followed by ACTIVEPARTITIONCOUNT"
                    )
                active_partition_count = self._parse_number()
                if not active_partition_count or not active_partition_count.is_int:
                    self.raise_error("SET ACTIVEPARTITIONCOUNT requires an integer")
            elif self._match_text_seq("ACTIVEPARTITIONCOUNT", advance=False):
                self.raise_error("ALTER TABLE requires SET before ACTIVEPARTITIONCOUNT")

            partition = self.expression(
                vexp.TablePartitionProperty(
                    this=partition_expression,
                    group=group_expression,
                    active_partition_count=active_partition_count,
                )
            )
            reorganize = self._match_text_seq("REORGANIZE")
            if self._curr:
                self.raise_error(f"Unexpected ALTER TABLE partition clause at {self._curr.text!r}")
            return self.expression(
                vexp.AlterTablePartition(
                    this=table,
                    kind="TABLE",
                    partition=partition,
                    reorganize=reorganize,
                )
            )

        if not self._match_text_seq("REORGANIZE"):
            self.raise_error("ALTER TABLE reorganization requires REORGANIZE")
        if self._curr:
            self.raise_error(f"Unexpected ALTER TABLE REORGANIZE clause at {self._curr.text!r}")
        return self.expression(
            vexp.ReorganizeTable(
                this=table,
                kind="TABLE",
                actions=[exp.var("REORGANIZE")],
            )
        )

    def _parse_alter_sequence(self) -> exp.Alter:
        sequence = self._parse_table_parts(schema=True)
        action: exp.Expr | None = None

        if self._match_text_seq("RENAME"):
            if not self._match_text_seq("TO"):
                self.raise_error("ALTER SEQUENCE RENAME requires TO")
            name = self._parse_id_var()
            if not name:
                self.raise_error("ALTER SEQUENCE RENAME TO requires a new name")
            action = self.expression(exp.AlterRename(this=name))
        elif self._match_text_seq("SET", "SCHEMA"):
            self._match_text_seq("TO")
            schema = self._parse_id_var()
            if not schema:
                self.raise_error("ALTER SEQUENCE SET SCHEMA requires a schema name")
            action = self.expression(vexp.SequenceSetSchemaAction(this=schema))
        elif self._match_text_seq("OWNER"):
            if not self._match_text_seq("TO"):
                self.raise_error("ALTER SEQUENCE OWNER requires TO")
            owner = self._parse_id_var()
            if not owner:
                self.raise_error("ALTER SEQUENCE OWNER TO requires an owner name")
            action = self.expression(vexp.SequenceOwnerToAction(this=owner))
        else:
            action = self._parse_vertica_sequence_options(alter=True)
            if not action:
                self.raise_error("ALTER SEQUENCE requires behavior options or one metadata action")
            if self._match_texts(("RENAME", "SET", "OWNER"), advance=False):
                self.raise_error(
                    "ALTER SEQUENCE cannot combine behavior options with metadata actions"
                )

        if self._curr:
            self.raise_error(f"Unexpected ALTER SEQUENCE clause at {self._curr.text!r}")

        assert action is not None
        return self.expression(exp.Alter(this=sequence, kind="SEQUENCE", actions=[action]))

    def _parse_create_table(self, temporary: bool, scope: str | None) -> exp.Create:
        exists = self._parse_exists(not_=True)
        table = self._parse_table_parts(schema=True)
        if not table:
            self.raise_error("CREATE TABLE requires a table name")
        assert table is not None

        properties: list[exp.Expr] = []
        if scope == "GLOBAL":
            properties.append(self.expression(exp.GlobalProperty()))
        elif scope == "LOCAL":
            properties.append(self.expression(vexp.LocalProperty()))
        if temporary:
            properties.append(self.expression(exp.TemporaryProperty()))

        if self._match_text_seq("LIKE"):
            if temporary:
                self.raise_error("CREATE TEMPORARY TABLE does not support LIKE")
            return self._parse_create_table_like(
                table=table,
                exists=exists,
                properties=properties,
            )

        if self._match(TokenType.L_PAREN, advance=False):
            schema_index = self._index
            schema = self._try_parse(lambda: self._parse_schema(this=table))
            if isinstance(schema, exp.Schema) and any(
                isinstance(item, exp.ColumnDef) for item in schema.expressions
            ):
                return self._parse_create_table_definition(
                    schema=schema,
                    exists=exists,
                    temporary=temporary,
                    scope=scope,
                    properties=properties,
                )

            self._retreat(schema_index)
            columns = self._parse_ctas_column_name_list()
        else:
            columns = []

        return self._parse_create_table_ctas(
            table=table,
            columns=columns,
            exists=exists,
            temporary=temporary,
            scope=scope,
            properties=properties,
        )

    def _parse_create_table_definition(
        self,
        schema: exp.Schema,
        exists: bool | None,
        temporary: bool,
        scope: str | None,
        properties: list[exp.Expr],
    ) -> exp.Create:
        """Parse a persistent or temporary table from column definitions."""

        if not schema.expressions:
            self.raise_error("CREATE TABLE requires at least one column definition")

        for item in schema.expressions:
            if isinstance(item, exp.ColumnDef) and not item.kind:
                self.raise_error("CREATE TABLE column definitions require data types")
            if isinstance(
                item,
                (exp.Identifier, vexp.GroupedProjectionColumns, vexp.ProjectionColumn),
            ):
                self.raise_error("CREATE TABLE column definitions require data types")

        on_commit = self._parse_on_commit_property() if temporary else None
        if on_commit:
            properties.append(on_commit)

        no_projection = False
        if temporary and self._match_text_seq("NO", "PROJECTION"):
            no_projection = True
            properties.append(self.expression(vexp.NoProjectionProperty()))

        order = self._parse_table_order()
        if order:
            properties.append(order)

        segmentation = self._parse_projection_segmentation()
        if segmentation:
            self._validate_table_segmentation(segmentation)
            properties.append(self.expression(vexp.TableSegmentationProperty(this=segmentation)))

        ksafe = None
        if self._match_text_seq("KSAFE"):
            safety = self._parse_number()
            if safety is not None and not safety.is_int:
                self.raise_error("KSAFE requires an integer safety level")
            ksafe = self.expression(vexp.KsafeProperty(this=safety))
            properties.append(ksafe)

        if no_projection and (order or segmentation or ksafe):
            self.raise_error(
                "NO PROJECTION cannot be combined with ORDER BY, segmentation, or KSAFE"
            )

        partition = None if temporary else self._parse_table_partition_property()
        if partition:
            properties.append(partition)

        privileges = self._parse_inherited_privileges_property()
        if privileges:
            properties.append(privileges)

        quota = self._parse_disk_quota_property()
        if quota:
            if scope == "LOCAL":
                self.raise_error("LOCAL temporary tables cannot specify DISK_QUOTA")
            properties.append(quota)

        if self._curr:
            self.raise_error(
                f"Unexpected or out-of-order CREATE TABLE clause starting at {self._curr.text!r}"
            )

        return self.expression(
            exp.Create(
                this=schema,
                kind="TABLE",
                exists=exists,
                properties=(
                    self.expression(exp.Properties(expressions=properties)) if properties else None
                ),
            )
        )

    def _parse_create_table_ctas(
        self,
        table: exp.Expr,
        columns: list[exp.Expr],
        exists: bool | None,
        temporary: bool,
        scope: str | None,
        properties: list[exp.Expr],
    ) -> exp.Create:
        """Parse CREATE TABLE AS with Vertica's pre- and post-query clauses."""

        if scope:
            self.raise_error("GLOBAL or LOCAL scope is not supported for temporary CTAS")

        if temporary:
            on_commit = self._parse_on_commit_property()
            if on_commit:
                properties.append(on_commit)
        else:
            privileges = self._parse_inherited_privileges_property()
            if privileges:
                properties.append(privileges)

        as_token = self._curr
        if not self._match(TokenType.ALIAS):
            self.raise_error("CREATE TABLE AS requires AS followed by a query")

        hint = self._parse_ctas_hint(as_token.comments)
        if hint:
            properties.append(hint)

        epoch = self._parse_at_epoch_property()
        if epoch:
            properties.append(epoch)

        query = self._parse_ddl_select()
        if not query:
            self.raise_error("CREATE TABLE AS requires a SELECT query")
        assert query is not None

        if self._match_text_seq("ENCODED", "BY"):
            if columns:
                self.raise_error("CTAS column-name lists and ENCODED BY are mutually exclusive")
            encoded_columns = self._parse_csv(
                lambda: self._parse_ctas_column(require_physical_design=True)
            )
            if not encoded_columns:
                self.raise_error("ENCODED BY requires at least one column reference")
            properties.append(self.expression(vexp.EncodedByProperty(expressions=encoded_columns)))

        segmentation = self._parse_projection_segmentation()
        if segmentation:
            if temporary:
                self.raise_error("Temporary CTAS does not support a segmentation clause")
            self._validate_table_segmentation(segmentation)
            properties.append(self.expression(vexp.CtasSegmentationProperty(this=segmentation)))

        quota = self._parse_disk_quota_property(ctas=True)
        if quota:
            properties.append(quota)

        if self._curr:
            self.raise_error(
                f"Unexpected or out-of-order CREATE TABLE AS clause starting at {self._curr.text!r}"
            )

        target: exp.Expr = (
            self.expression(exp.Schema(this=table, expressions=columns)) if columns else table
        )
        return self.expression(
            exp.Create(
                this=target,
                kind="TABLE",
                expression=query,
                exists=exists,
                properties=(
                    self.expression(exp.Properties(expressions=properties)) if properties else None
                ),
            )
        )

    def _parse_create_table_like(
        self,
        table: exp.Expr,
        exists: bool | None,
        properties: list[exp.Expr],
    ) -> exp.Create:
        source = self._parse_table_parts(schema=True)
        if not source:
            self.raise_error("CREATE TABLE LIKE requires a source table")
        assert source is not None

        options: list[exp.Expr] = []
        if self._match_texts(("INCLUDING", "EXCLUDING")):
            action = self._prev.text.upper()
            if not self._match_text_seq("PROJECTIONS"):
                self.raise_error(f"{action} must be followed by PROJECTIONS")
            options.append(
                self.expression(exp.Property(this=exp.var(action), value=exp.var("PROJECTIONS")))
            )
            if self._match_texts(("INCLUDING", "EXCLUDING"), advance=False):
                self.raise_error("CREATE TABLE LIKE accepts only one projection-copy option")

        properties.append(self.expression(exp.LikeProperty(this=source, expressions=options)))

        privileges = self._parse_inherited_privileges_property()
        if privileges:
            properties.append(privileges)

        quota = self._parse_disk_quota_property()
        if quota:
            properties.append(quota)

        if self._curr:
            self.raise_error(
                "Unexpected or out-of-order CREATE TABLE LIKE clause "
                f"starting at {self._curr.text!r}"
            )

        return self.expression(
            exp.Create(
                this=table,
                kind="TABLE",
                exists=exists,
                properties=self.expression(exp.Properties(expressions=properties)),
            )
        )

    def _parse_ctas_column_name_list(self) -> list[exp.Expr]:
        if not self._match(TokenType.L_PAREN):
            return []

        columns = self._parse_csv(lambda: self._parse_ctas_column(require_physical_design=False))
        if not columns:
            self.raise_error("CTAS column-name list cannot be empty")
        self._match_r_paren()
        return columns

    def _parse_ctas_column(self, require_physical_design: bool) -> exp.Expr | None:
        if self._match_text_seq("GROUPED"):
            grouped = self._parse_wrapped_csv(lambda: self._parse_id_var())
            if len(grouped) < 2:
                self.raise_error("GROUPED requires at least two column references")
            return self.expression(vexp.GroupedProjectionColumns(expressions=grouped))

        column = self._parse_id_var()
        if not column:
            return None

        encoding = None
        if self._match_text_seq("ENCODING"):
            encoding = self._parse_var(any_token=True)
            if not encoding:
                self.raise_error("ENCODING requires an encoding type")

        access_rank = None
        if self._match_text_seq("ACCESSRANK"):
            access_rank = self._parse_number()
            if not access_rank or not access_rank.is_int:
                self.raise_error("ACCESSRANK requires an integer")

        if require_physical_design and not encoding and not access_rank:
            self.raise_error("ENCODED BY column references require ENCODING or ACCESSRANK")

        if encoding or access_rank:
            return self.expression(
                vexp.ProjectionColumn(
                    this=column,
                    encoding=encoding,
                    access_rank=access_rank,
                )
            )
        return column

    def _parse_on_commit_property(self) -> exp.OnCommitProperty | None:
        if not self._match(TokenType.ON):
            return None
        if not self._match(TokenType.COMMIT):
            self.raise_error("Expected COMMIT after ON in temporary table definition")

        if self._match_text_seq("PRESERVE"):
            delete = False
        elif self._match(TokenType.DELETE):
            delete = True
        else:
            self.raise_error("ON COMMIT requires DELETE or PRESERVE")
        if not self._match(TokenType.ROWS):
            self.raise_error("ON COMMIT requires ROWS")
        return self.expression(exp.OnCommitProperty(delete=delete))

    def _parse_ctas_hint(self, comments: list[str]) -> vexp.CtasHintProperty | None:
        hints, ordinary_comments = self._extract_optimizer_hints(comments, self.CTAS_HINT_NAMES)
        comments[:] = ordinary_comments
        if not hints:
            return None

        hint_expressions = [
            directive for optimizer_hint in hints for directive in optimizer_hint.expressions
        ]
        return self.expression(vexp.CtasHintProperty(this=exp.Hint(expressions=hint_expressions)))

    def _parse_at_epoch_property(self) -> vexp.AtEpochProperty | None:
        if not self._match_text_seq("AT"):
            return None

        value: exp.Expr | None
        if self._match_text_seq("EPOCH"):
            if self._match_text_seq("LATEST"):
                value = exp.var("LATEST")
            else:
                value = self._parse_number()
                if not value or not value.is_int:
                    self.raise_error("AT EPOCH requires LATEST or an integer")
            kind = exp.var("EPOCH")
        elif self._match_text_seq("TIME"):
            value = self._parse_string()
            if not value:
                self.raise_error("AT TIME requires a quoted timestamp")
            kind = exp.var("TIME")
        else:
            self.raise_error("AT requires EPOCH or TIME")

        assert value is not None
        return self.expression(vexp.AtEpochProperty(this=value, kind=kind))

    def _parse_disk_quota_property(self, ctas: bool = False) -> vexp.DiskQuotaProperty | None:
        if not self._match_text_seq("DISK_QUOTA"):
            return None
        quota = self._parse_string()
        if not quota:
            self.raise_error("DISK_QUOTA requires a quoted quota")
        property_type = vexp.CtasDiskQuotaProperty if ctas else vexp.DiskQuotaProperty
        return self.expression(property_type(this=quota))

    def _validate_table_segmentation(self, segmentation: vexp.ProjectionSegmentation) -> None:
        if (
            not segmentation.args.get("all_nodes")
            or segmentation.args.get("nodes")
            or segmentation.args.get("offset") is not None
        ):
            self.raise_error("CREATE TABLE segmentation requires ALL NODES and forbids OFFSET")

    def _parse_table_order(self) -> exp.Order | None:
        if not self._match(TokenType.ORDER_BY):
            return None

        columns: list[exp.Expr] = []
        while True:
            column = self._parse_id_var()
            if not column:
                self.raise_error("CREATE TABLE ORDER BY requires a column name")
            assert column is not None
            if self._match_set((TokenType.ASC, TokenType.DESC), advance=False):
                self.raise_error("CREATE TABLE ORDER BY does not support ASC or DESC")
            columns.append(column)
            if not self._match(TokenType.COMMA):
                break

        return self.expression(exp.Order(expressions=columns))

    def _parse_table_partition_property(self) -> vexp.TablePartitionProperty | None:
        if not self._match(TokenType.PARTITION_BY):
            return None

        partition_expression = self._parse_disjunction()
        if not partition_expression:
            self.raise_error("PARTITION BY requires an expression")

        group_expression = None
        if self._match(TokenType.GROUP_BY):
            group_expression = self._parse_disjunction()
            if not group_expression:
                self.raise_error("Partition GROUP BY requires an expression")

        active_partition_count = None
        if self._match_text_seq("ACTIVEPARTITIONCOUNT"):
            active_partition_count = self._parse_number()
            if not active_partition_count or not active_partition_count.is_int:
                self.raise_error("ACTIVEPARTITIONCOUNT requires an integer")

        return self.expression(
            vexp.TablePartitionProperty(
                this=partition_expression,
                group=group_expression,
                active_partition_count=active_partition_count,
            )
        )

    def _parse_inherited_privileges_property(
        self,
    ) -> vexp.InheritedPrivilegesProperty | None:
        if not self._match_texts(("INCLUDE", "EXCLUDE")):
            return None

        include = self._prev.text.upper() == "INCLUDE"
        schema = self._match(TokenType.SCHEMA)
        if not self._match_text_seq("PRIVILEGES"):
            self.raise_error("Expected PRIVILEGES after INCLUDE or EXCLUDE")

        return self.expression(vexp.InheritedPrivilegesProperty(include=include, schema=schema))

    def _parse_encoding_column_constraint(self) -> exp.EncodeColumnConstraint:
        encoding = self._parse_var(any_token=True)
        if not encoding:
            self.raise_error("ENCODING requires an encoding type")
        return self.expression(exp.EncodeColumnConstraint(this=encoding))

    def _parse_access_rank_column_constraint(self) -> vexp.AccessRankColumnConstraint:
        access_rank = self._parse_number()
        if not access_rank or not access_rank.is_int:
            self.raise_error("ACCESSRANK requires an integer")
        return self.expression(vexp.AccessRankColumnConstraint(this=access_rank))

    @t.overload
    def _parse_query_modifiers(self, this: E) -> E: ...

    @t.overload
    def _parse_query_modifiers(self, this: None) -> None: ...

    def _parse_query_modifiers(self, this: E | None) -> E | None:
        this = super()._parse_query_modifiers(this)
        if not this or not self._match_text_seq("TIMESERIES"):
            return this

        if this.args.get("timeseries"):
            self.raise_error("Found multiple TIMESERIES clauses")

        timeseries = self._parse_timeseries()
        this.set("timeseries", timeseries)
        this = super()._parse_query_modifiers(this)

        if not isinstance(this, exp.Select):
            self.raise_error("TIMESERIES requires a SELECT query")
            return this

        result = self.expression(
            vexp.TimeseriesSelect(**this.args),
            comments=this.pop_comments(),
        )
        result.meta.update(this.meta)
        self._rewrite_timeseries_slice_refs(result, timeseries.this.name)
        return t.cast("E", result)

    def _rewrite_timeseries_slice_refs(self, query: vexp.TimeseriesSelect, slice_name: str) -> None:
        """Mark references to the synthetic slice column in this SELECT scope.

        Vertica creates the slice column after reading the source rows. Keeping
        it as an ordinary unqualified Column makes SQLGlot's qualifier look for
        it in the source schema. Only projections and the outer ORDER BY can
        resolve the generated name; source predicates and the TIMESERIES window
        continue to use ordinary input columns.
        """

        targets: list[exp.Expr] = list(query.expressions)
        order = query.args.get("order")
        if isinstance(order, exp.Order):
            targets.append(order)

        for target in targets:
            for column in list(target.find_all(exp.Column)):
                if (
                    len(column.parts) == 1
                    and column.name == slice_name
                    and column.find_ancestor(exp.Select) is query
                ):
                    replacement = self.expression(
                        vexp.TimeseriesSlice(this=column.this.copy()),
                        comments=column.pop_comments(),
                    )
                    replacement.meta.update(column.meta)
                    column.replace(replacement)

    def _parse_timeseries(self) -> vexp.Timeseries:
        slice_name = self._parse_id_var()
        if not slice_name or not self._match(TokenType.ALIAS):
            self.raise_error("Expected slice-name AS in TIMESERIES clause")

        slice_interval = self._parse_bitwise()
        if not slice_interval or not self._match(TokenType.OVER):
            self.raise_error("Expected a slice interval followed by OVER")

        if not self._match(TokenType.L_PAREN):
            self.raise_error("Expected ( after TIMESERIES OVER")

        partition_by: list[exp.Expr] = []
        if self._match(TokenType.PARTITION_BY):
            partition_by = self._parse_csv(self._parse_expression)

        if not self._match(TokenType.ORDER_BY, advance=False):
            self.raise_error("TIMESERIES requires ORDER BY")
        order = self._parse_order()
        self._match_r_paren()

        return self.expression(
            vexp.Timeseries(
                this=slice_name,
                expression=slice_interval,
                partition_by=partition_by,
                order=order,
            )
        )

    def _parse_interpolate_predicate(self, this: exp.Expr) -> vexp.Interpolate:
        direction = (
            exp.var(self._prev.text.upper()) if self._match_texts(("PREVIOUS", "NEXT")) else None
        )
        if not direction or not self._match_text_seq("VALUE"):
            self.raise_error("Expected PREVIOUS VALUE or NEXT VALUE after INTERPOLATE")

        expression = self._parse_bitwise()
        if not expression:
            self.raise_error("Expected a column after INTERPOLATE direction")

        return self.expression(
            vexp.Interpolate(this=this, expression=expression, direction=direction)
        )

    def _parse_limit(
        self,
        this: exp.Expr | None = None,
        top: bool = False,
        skip_limit_token: bool = False,
    ) -> exp.Expr | None:
        limit = super()._parse_limit(this=this, top=top, skip_limit_token=skip_limit_token)
        if top or not isinstance(limit, exp.Limit) or not self._match(TokenType.OVER):
            return limit

        if limit.args.get("offset") or limit.args.get("limit_options"):
            self.raise_error("Partitioned LIMIT does not support offset or limit options")
        if not self._match(TokenType.L_PAREN):
            self.raise_error("Expected ( after LIMIT ... OVER")

        partition_by, order = self._parse_partition_and_order()
        if not partition_by:
            self.raise_error("Partitioned LIMIT requires PARTITION BY")
        if not order:
            self.raise_error("Partitioned LIMIT requires ORDER BY")
        self._match_r_paren()

        return self.expression(
            vexp.PartitionedLimit(
                expression=limit.expression,
                partition_by=partition_by,
                order=order,
            ),
            comments=limit.comments,
        )

    def _parse_vertica_match(self) -> vexp.Match:
        if not self._match(TokenType.MATCH_RECOGNIZE):
            self.raise_error("Expected MATCH")
        if not self._match(TokenType.L_PAREN):
            self.raise_error("Expected ( after MATCH")

        partition_by = self._parse_partition_by()
        order = self._parse_order()

        definitions: list[vexp.MatchDefinition] = []
        if self._match_text_seq("DEFINE"):
            while True:
                name = self._parse_id_var()
                if not name or not self._match(TokenType.ALIAS):
                    self.raise_error("Expected event-name AS in MATCH DEFINE")
                condition = self._parse_disjunction()
                if not condition:
                    self.raise_error("Expected event predicate in MATCH DEFINE")
                definitions.append(
                    self.expression(vexp.MatchDefinition(this=name, expression=condition))
                )
                if not self._match(TokenType.COMMA):
                    break

        if not self._match_text_seq("PATTERN"):
            self.raise_error("MATCH requires PATTERN")
        pattern_name = self._parse_id_var()
        if not pattern_name or not self._match(TokenType.ALIAS):
            self.raise_error("Expected pattern-name AS in MATCH PATTERN")
        pattern = self._parse_match_pattern_text()

        rows_match = None
        if self._match(TokenType.ROWS):
            if not self._match_text_seq("MATCH"):
                self.raise_error("Expected MATCH after ROWS")
            if self._match_text_seq("FIRST", "EVENT"):
                rows_match = exp.var("FIRST EVENT")
            elif self._match_text_seq("ALL", "EVENTS"):
                rows_match = exp.var("ALL EVENTS")
            else:
                self.raise_error("Expected FIRST EVENT or ALL EVENTS after ROWS MATCH")

        self._match_r_paren()
        return self.expression(
            vexp.Match(
                partition_by=partition_by,
                order=order,
                definitions=definitions,
                pattern_name=pattern_name,
                pattern=pattern,
                rows_match=rows_match,
            )
        )

    def _parse_match_pattern_text(self) -> exp.Var:
        if not self._match(TokenType.L_PAREN):
            self.raise_error("Expected ( around MATCH pattern")
        if not self._curr:
            self.raise_error("Expected MATCH pattern")

        depth = 1
        start = self._curr
        end = self._curr
        while self._curr and depth:
            if self._curr.token_type == TokenType.L_PAREN:
                depth += 1
            elif self._curr.token_type == TokenType.R_PAREN:
                depth -= 1
                if depth == 0:
                    break
            end = self._curr
            self._advance()

        if depth:
            self.raise_error("Expected ) after MATCH pattern")
        self._advance()
        return exp.var(self._find_sql(start, end))

    def _parse_drop_role(self, exists: bool) -> exp.Drop:
        if_exists = exists or bool(self._parse_exists())
        roles = [self._parse_lifecycle_identifier("DROP ROLE")]
        while self._match(TokenType.COMMA):
            if not self._curr:
                self.raise_error("DROP ROLE requires a name after each comma")
            roles.append(self._parse_lifecycle_identifier("DROP ROLE"))

        cascade = self._match_text_seq("CASCADE")
        if self._match_text_seq("RESTRICT", advance=False):
            self.raise_error("Vertica DROP ROLE does not support RESTRICT")
        if self._curr:
            self.raise_error(f"Unexpected DROP ROLE clause at {self._curr.text!r}")

        expression_type: type[exp.Drop] = vexp.DropRoles if len(roles) > 1 else exp.Drop
        return self.expression(
            expression_type(
                this=roles[0],
                expressions=roles[1:] or None,
                kind="ROLE",
                exists=if_exists,
                cascade=cascade,
            )
        )

    def _parse_drop_user(self, exists: bool) -> vexp.DropUsers:
        if exists:
            self._raise_user_error("DROP USER IF EXISTS must follow USER")
        if_exists = self._match_user_keywords("IF", "EXISTS")
        users = [self._parse_user_identifier("DROP USER")]
        while self._match(TokenType.COMMA):
            if not self._curr:
                self._raise_user_error("DROP USER requires a name after each comma")
            users.append(self._parse_user_identifier("DROP USER"))

        cascade = self._match_user_keywords("CASCADE")
        if self._match_user_keywords("RESTRICT", advance=False):
            self._raise_user_error("DROP USER does not support RESTRICT")
        if self._curr:
            self._raise_user_error(f"Unsupported DROP USER clause at {self._curr.text!r}")

        return self.expression(
            vexp.DropUsers(
                this=users[0],
                expressions=users[1:] or None,
                kind="USER",
                exists=if_exists,
                cascade=cascade,
            )
        )

    def _parse_drop_profile(self, exists: bool) -> vexp.DropProfiles:
        if exists:
            self._raise_profile_error("DROP PROFILE IF EXISTS must follow PROFILE")
        if_exists = self._match_profile_var("IF")
        if if_exists and not self._match_profile_var("EXISTS"):
            self._raise_profile_error("DROP PROFILE IF must be followed by EXISTS")

        profiles = [self._parse_profile_identifier("DROP PROFILE")]
        while self._match(TokenType.COMMA):
            if not self._curr:
                self._raise_profile_error("DROP PROFILE requires a name after each comma")
            profiles.append(self._parse_profile_identifier("DROP PROFILE"))

        cascade = self._match_profile_var("CASCADE")
        if self._curr:
            self._raise_profile_error(f"Unexpected DROP PROFILE clause at {self._curr.text!r}")
        return self.expression(
            vexp.DropProfiles(
                this=profiles[0],
                expressions=profiles[1:] or None,
                kind="PROFILE",
                exists=if_exists,
                cascade=cascade,
            )
        )

    def _parse_user_identifier(self, statement: str) -> exp.Identifier:
        identifier = self._parse_connection_policy_identifier(statement)
        if not isinstance(identifier.this, str) or not identifier.this:
            self._raise_user_error(f"{statement} requires a nonempty identifier")
        elif not identifier.quoted and not self._is_connection_policy_identifier(identifier.this):
            self._raise_user_error(f"{statement} requires a valid unquoted identifier")
        else:
            try:
                size = len(identifier.this.encode("utf-8"))
            except UnicodeEncodeError:
                self._raise_user_error(f"{statement} names must be valid UTF-8")
            else:
                if size > 128:
                    self._raise_user_error(f"{statement} names cannot exceed 128 UTF-8 bytes")
        return identifier

    def _parse_drop_resource_pool(self, exists: bool) -> vexp.DropResourcePool:
        if exists or self._match_text_seq("IF", "EXISTS", advance=False):
            self.raise_error("DROP RESOURCE POOL does not support IF EXISTS")

        pool = self._parse_lifecycle_identifier("DROP RESOURCE POOL")
        subcluster = self._parse_resource_pool_subcluster()
        if self._match(TokenType.COMMA, advance=False):
            self.raise_error("DROP RESOURCE POOL accepts exactly one pool")
        if self._match_texts(("CASCADE", "RESTRICT"), advance=False):
            self.raise_error("DROP RESOURCE POOL does not support CASCADE or RESTRICT")
        if self._curr:
            self.raise_error(f"Unexpected DROP RESOURCE POOL clause at {self._curr.text!r}")

        return self.expression(
            vexp.DropResourcePool(
                this=pool,
                kind="RESOURCE POOL",
                subcluster=subcluster,
            )
        )

    def _parse_drop_user_defined_extension(
        self, kind: str, exists: bool
    ) -> vexp.DropUserDefinedExtension:
        if_exists = exists or bool(self._parse_exists())
        if if_exists and kind in self.USER_DEFINED_LOAD_FUNCTION_KINDS:
            self.raise_error(f"DROP {kind} does not support IF EXISTS")

        signature = self._parse_user_defined_extension_signature(kind)
        if kind in self.USER_DEFINED_LOAD_FUNCTION_KINDS and signature.expressions:
            self.raise_error(f"DROP {kind} requires an empty argument signature")

        if self._match_texts(("CASCADE", "RESTRICT"), advance=False):
            self.raise_error(f"DROP {kind} does not support CASCADE or RESTRICT")
        if self._curr:
            self.raise_error(f"Unexpected DROP {kind} clause at {self._curr.text!r}")

        return self.expression(
            vexp.DropUserDefinedExtension(
                this=signature,
                kind=kind,
                exists=if_exists,
            )
        )

    def _parse_user_defined_extension_signature(self, kind: str) -> vexp.RoutineSignature:
        name = self._parse_catalog_object_name(f"DROP {kind}")
        if not self._match(TokenType.L_PAREN):
            self.raise_error(f"DROP {kind} requires an argument signature")

        arguments: list[exp.Expr] = []
        if not self._match(TokenType.R_PAREN):
            arguments.append(self._parse_security_routine_argument())
            while self._match(TokenType.COMMA):
                arguments.append(self._parse_security_routine_argument())
            self._match_r_paren()

        return self.expression(vexp.RoutineSignature(this=name, expressions=arguments))

    def _parse_drop_library(self, exists: bool) -> vexp.DropLibrary:
        if_exists = exists or bool(self._parse_exists())
        library = self._parse_catalog_object_name("DROP LIBRARY")
        cascade = self._match_text_seq("CASCADE")
        if self._match_text_seq("RESTRICT", advance=False):
            self.raise_error("DROP LIBRARY does not support RESTRICT")
        if self._curr:
            self.raise_error(f"Unexpected DROP LIBRARY clause at {self._curr.text!r}")

        return self.expression(
            vexp.DropLibrary(
                this=library,
                kind="LIBRARY",
                exists=if_exists,
                cascade=cascade,
            )
        )

    def _parse_drop(  # type: ignore[override]
        self, exists: bool = False
    ) -> exp.Drop | vexp.DirectedQueryAction | exp.Command:
        words = [token.text.upper() for token in self._tokens[self._index :]]
        self._reject_sensitive_user_statement("DROP", words)
        self._reject_prefixed_routing_rule("DROP", words)
        self._reject_prefixed_load_balance_group("DROP", words)
        self._reject_prefixed_network_address("DROP", words)
        self._reject_prefixed_profile("DROP", words)
        self._reject_prefixed_user("DROP", words)
        lookahead = words[:3]
        if lookahead == ["IF", "EXISTS", "DIRECTED"]:
            self.raise_error("DROP DIRECTED QUERY does not support IF EXISTS")
        if lookahead[:2] == ["TEMPORARY", "DIRECTED"]:
            self.raise_error("DROP DIRECTED QUERY does not support TEMPORARY")

        if self._match_text_seq("DIRECTED"):
            if not self._match_text_seq("QUERY"):
                self.raise_error("DROP DIRECTED must be followed by QUERY")
            if exists or self._match_text_seq("IF", advance=False):
                self.raise_error("DROP DIRECTED QUERY does not support IF EXISTS")
            return self._parse_directed_query_action("DROP")

        udx_kind = self._parse_user_defined_extension_kind("DROP")
        if udx_kind:
            return self._parse_drop_user_defined_extension(kind=udx_kind, exists=exists)
        if self._match_text_seq("LIBRARY"):
            return self._parse_drop_library(exists=exists)

        if self._match(TokenType.LOAD):
            if not self._match_text_seq("BALANCE", "GROUP"):
                self.raise_error("DROP LOAD must be followed by BALANCE GROUP")
            return self._parse_drop_load_balance_group(exists=exists)
        if self._match_network_object("ADDRESS"):
            return self._parse_drop_network_address(exists=exists)
        if self._curr.text.upper() == "NETWORK" and not self._match_network_object(
            "INTERFACE", advance=False
        ):
            self._raise_network_address_error("DROP NETWORK must be followed by ADDRESS")
        if self._match_profile_object():
            return self._parse_drop_profile(exists=exists)
        if self._curr.text.upper() == "PROFILE":
            self._raise_profile_error("DROP PROFILE requires the unquoted PROFILE object kind")
        if self._match_user_object():
            return self._parse_drop_user(exists=exists)
        if self._curr.text.upper() == "USER":
            self._raise_user_error("DROP USER requires the unquoted USER object kind")
        if self._match_text_seq("ROLE"):
            return self._parse_drop_role(exists=exists)
        if self._match_text_seq("RESOURCE", "POOL"):
            return self._parse_drop_resource_pool(exists=exists)
        if self._match_text_seq("ROUTING", "RULE"):
            return self._parse_drop_routing_rule(exists=exists)
        if self._match_text_seq("ROUTING", advance=False):
            self.raise_error("DROP ROUTING must be followed by RULE")

        if self._match(TokenType.PROCEDURE):
            if_exists = exists or self._parse_exists()
            signature = self._parse_external_procedure_signature()

            if self._match_texts(("CASCADE", "RESTRICT"), advance=False):
                self.raise_error(
                    "Vertica external DROP PROCEDURE does not support CASCADE or RESTRICT"
                )
            if self._curr:
                self.raise_error(
                    f"Unexpected external DROP PROCEDURE clause at {self._curr.text!r}"
                )

            return self.expression(
                vexp.DropExternalProcedure(
                    this=signature,
                    kind="PROCEDURE",
                    exists=if_exists,
                )
            )

        if self._match(TokenType.SEQUENCE):
            if_exists = exists or self._parse_exists()
            sequences = [self._parse_table_parts(schema=True)]
            while self._match(TokenType.COMMA):
                if not self._curr:
                    self.raise_error("DROP SEQUENCE requires a name after each comma")
                sequences.append(self._parse_table_parts(schema=True))

            if self._match_texts(("CASCADE", "RESTRICT"), advance=False):
                self.raise_error("Vertica DROP SEQUENCE does not support CASCADE or RESTRICT")
            if self._curr:
                self.raise_error(f"Unexpected DROP SEQUENCE clause at {self._curr.text!r}")

            return self.expression(
                exp.Drop(
                    this=sequences[0],
                    expressions=sequences[1:] or None,
                    kind="SEQUENCE",
                    exists=if_exists,
                )
            )

        if not self._match(TokenType.PROJECTION):
            return super()._parse_drop(exists=exists)

        if_exists = exists or self._parse_exists()
        this = self._parse_table_parts(schema=True)
        cascade = self._match_text_seq("CASCADE")
        restrict = not cascade and self._match_text_seq("RESTRICT")

        return self.expression(
            exp.Drop(
                this=this,
                kind="PROJECTION",
                exists=if_exists,
                cascade=cascade,
                restrict=restrict,
            )
        )

    def _parse_create_projection(self, replace: bool = False) -> vexp.CreateProjection:
        exists = self._parse_exists(not_=True)
        this = self._parse_table_parts(schema=True)

        columns = (
            self._parse_wrapped_csv(self._parse_projection_column)
            if self._match(TokenType.L_PAREN, advance=False)
            else []
        )

        if not self._match(TokenType.ALIAS):
            self.raise_error("Expected AS after projection name")

        query = self._parse_ddl_select()
        if not query:
            self.raise_error("Expected SELECT query in projection definition")
        assert query is not None

        order = query.args.get("order")
        if order:
            query.set("order", None)

        segmentation = self._parse_projection_segmentation()
        ksafe = self._parse_number() if self._match_text_seq("KSAFE") else None

        return self.expression(
            vexp.CreateProjection(
                this=this,
                expression=query,
                columns=columns,
                order=order,
                segmentation=segmentation,
                ksafe=ksafe,
                kind="PROJECTION",
                exists=exists,
                replace=replace,
            )
        )

    def _parse_projection_column(self) -> exp.Expr | None:
        if self._match_text_seq("GROUPED"):
            return self.expression(
                vexp.GroupedProjectionColumns(
                    expressions=self._parse_wrapped_csv(self._parse_projection_column)
                )
            )

        this = self._parse_id_var()
        if not this:
            return None

        encoding = None
        access_rank = None
        if self._match_text_seq("ENCODING"):
            encoding = self._parse_var(any_token=True)
        if self._match_text_seq("ACCESSRANK"):
            access_rank = self._parse_number()

        return self.expression(
            vexp.ProjectionColumn(
                this=this,
                encoding=encoding,
                access_rank=access_rank,
            )
        )

    def _parse_projection_segmentation(self) -> vexp.ProjectionSegmentation | None:
        segmented: bool
        this = None

        if self._match_text_seq("SEGMENTED"):
            segmented = True
            if not self._match_text_seq("BY"):
                self.raise_error("Expected BY after SEGMENTED")
            # Physical segmentation expressions do not permit SQL aliases. Using
            # the expression parser here would consume `ALL NODES` as alias text.
            this = self._parse_bitwise()
        elif self._match_text_seq("UNSEGMENTED"):
            segmented = False
        else:
            return None

        all_nodes = False
        nodes: list[exp.Expr] = []
        if self._match(TokenType.ALL):
            if not self._match_text_seq("NODES"):
                self.raise_error("Expected NODES after ALL")
            all_nodes = True
        elif self._match_text_seq("NODES"):
            nodes = self._parse_csv(lambda: self._parse_id_var())

        offset = self._parse_number() if self._match(TokenType.OFFSET) else None
        return self.expression(
            vexp.ProjectionSegmentation(
                this=this,
                segmented=segmented,
                all_nodes=all_nodes,
                nodes=nodes,
                offset=offset,
            )
        )
