"""Vertica dialect definition and tokenizer configuration."""

from __future__ import annotations

import re
import typing as t

from sqlglot import TokenType, exp
from sqlglot.dialects.dialect import NormalizationStrategy
from sqlglot.dialects.postgres import Postgres
from sqlglot.tokenizer_core import TokenizerCore

from sqlglot_vertica import expressions as vexp
from sqlglot_vertica.foreign_properties import patch_foreign_properties_location
from sqlglot_vertica.generator import VerticaGenerator
from sqlglot_vertica.parser import VerticaParser
from sqlglot_vertica.tokens import DirectedPostfixComment, MisplacedDirectedComment

# Foreign dialects must fail atomically on an embedded Vertica-only table
# property instead of raising a raw KeyError; see foreign_properties.py.
patch_foreign_properties_location()


def _annotate_set_literal(annotator: t.Any, expression: vexp.SetLiteral) -> None:
    """Infer SET<element> with SQLGlot's normal common-type coercion."""

    annotator._annotate_by_args(expression, "expressions")
    element_type = expression.type or exp.DType.UNKNOWN.into_expr()
    annotator._set_type(
        expression,
        exp.DataType(
            this=exp.DType.SET,
            expressions=[element_type.copy()],
            nested=True,
        ),
    )


def _annotate_from_this(annotator: t.Any, expression: exp.Expr) -> None:
    """Propagate the type of a semantically transparent wrapper or filter."""

    annotator._annotate_by_args(expression, "this")


def _annotate_to_hex(annotator: t.Any, expression: exp.Expr) -> None:
    """Return binary hex for binary input and VARCHAR for numeric input."""

    this = expression.this
    if isinstance(this, exp.Expr) and this.is_type(
        exp.DType.BINARY,
        exp.DType.VARBINARY,
        exp.DType.BLOB,
        exp.DType.LONGBLOB,
    ):
        annotator._set_type(expression, exp.DType.VARBINARY)
    else:
        annotator._set_type(expression, exp.DType.VARCHAR)


class _VerticaTokenizerCore(TokenizerCore):
    """Retain whether a directed annotation came from a plus comment."""

    _DIRECTED_PREFIX: t.ClassVar[re.Pattern[str]] = re.compile(
        r"^(?::[cv]|IGNORECONST(?:ANT)?)",
        re.IGNORECASE,
    )
    _VALUE_TERMINATORS: t.ClassVar[set[TokenType]] = {
        *VerticaParser.TYPE_TOKENS,
        TokenType.BIT_STRING,
        TokenType.BYTE_STRING,
        TokenType.CURRENT_CATALOG,
        TokenType.CURRENT_DATE,
        TokenType.CURRENT_DATETIME,
        TokenType.CURRENT_ROLE,
        TokenType.CURRENT_SCHEMA,
        TokenType.CURRENT_TIME,
        TokenType.CURRENT_TIMESTAMP,
        TokenType.CURRENT_USER,
        TokenType.CURRENT_USER_ID,
        TokenType.END,
        TokenType.FALSE,
        TokenType.HEX_STRING,
        TokenType.HEREDOC_STRING,
        TokenType.IDENTIFIER,
        TokenType.NATIONAL_STRING,
        TokenType.NULL,
        TokenType.NUMBER,
        TokenType.PARAMETER,
        TokenType.PLACEHOLDER,
        TokenType.RAW_STRING,
        TokenType.R_BRACE,
        TokenType.R_BRACKET,
        TokenType.R_PAREN,
        TokenType.SESSION_PARAMETER,
        TokenType.STRING,
        TokenType.TRUE,
        TokenType.UNICODE_STRING,
        TokenType.VAR,
    }

    def _scan_comment(self, comment_start: str) -> bool:
        pending_count = len(self._comments)
        token_count = len(self.tokens)
        trailing_count = len(self.tokens[-1].comments) if self.tokens else 0
        postfix_value = bool(self.tokens) and (
            self.tokens[-1].token_type in self._VALUE_TERMINATORS
            or (self.tokens[-1].token_type == TokenType.NOT and self.tokens[-1].text == "!")
        )

        matched = super()._scan_comment(comment_start)
        if not matched or comment_start not in {self.hint_start, "/*"}:
            return matched

        stored_comments: list[str] | None = None
        if len(self.tokens) > token_count or (
            self.tokens and len(self.tokens[-1].comments) > trailing_count
        ):
            stored_comments = self.tokens[-1].comments
        elif len(self._comments) > pending_count:
            stored_comments = self._comments
        if not stored_comments:
            return matched

        body = stored_comments[-1]
        if comment_start == "/*":
            plus = re.match(r"^\s*\+\s*(.*)$", body, re.DOTALL)
            if not plus:
                return matched
            body = plus.group(1)

        candidate = body.strip()
        if self._DIRECTED_PREFIX.match(candidate):
            comment_type = DirectedPostfixComment if postfix_value else MisplacedDirectedComment
            marked_comment = comment_type(candidate)
            if postfix_value and stored_comments is self._comments:
                stored_comments.pop()
                self.tokens[-1].comments.append(marked_comment)
            else:
                stored_comments[-1] = marked_comment
        return matched


class Vertica(Postgres):
    """SQLGlot dialect for Vertica / OpenText Analytics Database."""

    NORMALIZATION_STRATEGY = NormalizationStrategy.CASE_INSENSITIVE
    INDEX_OFFSET = 0
    SUPPORTS_USER_DEFINED_TYPES = True
    TYPED_DIVISION = False
    CONCAT_COALESCE = False

    EXPRESSION_METADATA = {  # noqa: RUF012 - SQLGlot declares this as a mutable dialect map
        **Postgres.EXPRESSION_METADATA,
        vexp.DirectedConstantHint: {"annotator": _annotate_from_this},
        vexp.SetLiteral: {"annotator": _annotate_set_literal},
        vexp.RowAlias: Postgres.EXPRESSION_METADATA[exp.Alias].copy(),
        vexp.VerticaInterval: {"returns": exp.DType.INTERVAL},
        vexp.StatementTimestamp: {"returns": exp.DType.TIMESTAMP},
        vexp.StringUnit: {"annotator": _annotate_from_this},
        vexp.UtcStatementTimestamp: {"returns": exp.DType.TIMESTAMP},
        vexp.ListAgg: {"returns": exp.DType.VARCHAR},
        vexp.TimeseriesSlice: {"returns": exp.DType.TIMESTAMP},
        vexp.Interpolate: {"returns": exp.DType.BOOLEAN},
        vexp.UsingParameters: {"annotator": _annotate_from_this},
        vexp.VerticaArrayLength: {"returns": exp.DType.BIGINT},
        vexp.VerticaExplode: {"annotator": _annotate_from_this},
        vexp.VerticaInstr: {"returns": exp.DType.BIGINT},
        vexp.VerticaRegexpLike: {"returns": exp.DType.BOOLEAN},
        vexp.VerticaToChar: {"returns": exp.DType.VARCHAR},
        vexp.VerticaWindow: Postgres.EXPRESSION_METADATA[exp.Window].copy(),
        vexp.UserParameter: {"annotator": _annotate_from_this},
        vexp.UserConfigurationParameter: {"annotator": _annotate_from_this},
        exp.ArrayFilter: {"annotator": _annotate_from_this},
        exp.Hex: {"annotator": _annotate_to_hex},
        exp.Length: {"returns": exp.DType.BIGINT},
        exp.LowerHex: {"annotator": _annotate_to_hex},
        exp.StrPosition: {"returns": exp.DType.BIGINT},
        exp.Stuff: {"returns": exp.DType.VARCHAR},
        exp.ToNumber: {"returns": exp.DType.DOUBLE},
    }

    Parser = VerticaParser
    Generator = VerticaGenerator

    class Tokenizer(Postgres.Tokenizer):
        TOKENS_PRECEDING_HINT: t.ClassVar = {
            *Postgres.Tokenizer.TOKENS_PRECEDING_HINT,
            TokenType.COPY,
            TokenType.DESCRIBE,
            TokenType.MERGE,
        }

        KEYWORDS: t.ClassVar = {
            **Postgres.Tokenizer.KEYWORDS,
            "/*+": TokenType.HINT,
            "!!": TokenType.EXCLAMATION,
            "//": TokenType.DIV,
            "BINARY VARYING": TokenType.VARBINARY,
            "DEFINE": TokenType.POLICY,
            "DISK_QUOTA": TokenType.POLICY,
            "ENCODED": TokenType.POLICY,
            "EXPLAIN": TokenType.DESCRIBE,
            "INTEGER": TokenType.BIGINT,
            "INT": TokenType.BIGINT,
            "INT8": TokenType.BIGINT,
            "INTERVALYM": TokenType.INTERVAL,
            "INTERPOLATE": TokenType.MATCH,
            "KSAFE": TokenType.POLICY,
            "LONG VARCHAR": TokenType.LONGTEXT,
            "LONG VARBINARY": TokenType.LONGBLOB,
            "MATCH": TokenType.MATCH_RECOGNIZE,
            "MINUS": TokenType.EXCEPT,
            "PATTERN": TokenType.POLICY,
            "PROJECTION": TokenType.PROJECTION,
            "REAL": TokenType.DOUBLE,
            "SEGMENTED": TokenType.POLICY,
            "SMALLINT": TokenType.BIGINT,
            "TINYINT": TokenType.BIGINT,
            "TIMESERIES": TokenType.POLICY,
            "UNSEGMENTED": TokenType.POLICY,
        }

        def _init_core(self) -> TokenizerCore:
            return _VerticaTokenizerCore(
                single_tokens=self.SINGLE_TOKENS,
                keywords=self.KEYWORDS,
                quotes=self._QUOTES,
                format_strings=self._FORMAT_STRINGS,
                identifiers=self._IDENTIFIERS,
                comments=self._COMMENTS,
                string_escapes=self._STRING_ESCAPES,
                byte_string_escapes=self._BYTE_STRING_ESCAPES,
                identifier_escapes=self._IDENTIFIER_ESCAPES,
                escape_follow_chars=self._ESCAPE_FOLLOW_CHARS,
                commands=self.COMMANDS,
                command_prefix_tokens=self.COMMAND_PREFIX_TOKENS,
                nested_comments=self.NESTED_COMMENTS,
                hint_start=self.HINT_START,
                tokens_preceding_hint=self.TOKENS_PRECEDING_HINT,
                has_bit_strings=bool(self.BIT_STRINGS),
                has_hex_strings=bool(self.HEX_STRINGS),
                numeric_literals=self.NUMERIC_LITERALS,
                var_single_tokens=self.VAR_SINGLE_TOKENS,
                string_escapes_allowed_in_raw_strings=(self.STRING_ESCAPES_ALLOWED_IN_RAW_STRINGS),
                heredoc_tag_is_identifier=self.HEREDOC_TAG_IS_IDENTIFIER,
                heredoc_string_alternative=self.HEREDOC_STRING_ALTERNATIVE,
                keyword_trie=self._KEYWORD_TRIE,
                numbers_can_be_underscore_separated=(
                    self.dialect.NUMBERS_CAN_BE_UNDERSCORE_SEPARATED
                ),
                numbers_can_have_decimals=self.NUMBERS_CAN_HAVE_DECIMALS,
                identifiers_can_start_with_digit=self.dialect.IDENTIFIERS_CAN_START_WITH_DIGIT,
                unescaped_sequences=self.dialect.UNESCAPED_SEQUENCES,
            )
