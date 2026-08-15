# Dialect architecture

This package targets OpenText Analytics Database (Vertica) 26.2 and a single
tested SQLGlot minor release at a time. SQLGlot's public plugin entry point is
stable, but parser and generator subclass APIs can change between minor
versions; the runtime dependency is therefore bounded to `>=30.13.0,<30.14.0`.

## AST policy

The parser uses SQLGlot's canonical expressions whenever they represent the
same semantics. This keeps optimizers, lineage, qualification, and
cross-dialect generation useful. A Vertica-specific expression is introduced
only when mapping to a canonical node would discard syntax or change meaning.

Custom nodes should subclass the closest canonical expression when one exists.
For example, a partitioned top-k clause is still a kind of `exp.Limit`, and a
Vertica bulk load is still a kind of `exp.Copy`. This makes generic tree
visitors and optimizer checks see the node.

That rule has one safety exception: a canonical subclass is not used when its
generic generator fallback would invent valid-looking but nonexistent SQL.
`SetLiteral` and the statement-timestamp nodes therefore use plain custom
expressions. `ListAgg` wraps a canonical `exp.GroupConcat` child, preserving
aggregate discovery and column traversal without allowing a foreign generator
to emit a fictitious `LIST_AGG` call.

Function syntax follows the same wrapper pattern. `UsingParameters` and
`StringUnit` retain the parsed function as `this` and store ordered parameter
or unit children separately. Source-sensitive calls such as Vertica `EXPLODE`,
one-argument `ARRAY_LENGTH`, extended `INSTR`, modifier-bearing `REGEXP_LIKE`,
and one-argument `TO_CHAR` wrap their closest canonical child. Optimizers can
still discover operands, predicates, lambdas, and aggregates, while foreign
generators fail on the outer Vertica node instead of silently changing a call's
meaning. Special execution partitions similarly use `VerticaWindow`, an
`exp.Window` subclass whose `partition_mode` is explicit and serialized.

The following invariants apply to every custom node:

1. Every semantic argument is declared in `arg_types`.
2. The Vertica generator has an explicit transform.
3. Parse/generate/reparse produces an equivalent tree.
4. Unsupported cross-dialect generation raises instead of silently deleting
   the construct, unless an explicit semantic lowering is documented and
   tested.
5. Public class names are treated as serialized-AST compatibility surface.

The same distinction applies to external loading. Executable `COPY` remains an
`exp.Copy` subclass, while the reusable body inside `CREATE EXTERNAL TABLE` is
an `ExternalCopyDefinition`: a targetless node that shares structured source,
format, column, and parameter children without pretending to be an executable
statement missing its target. External-table parsing applies a narrower
context allowlist, so `LOCAL`, `STDIN`, stream/load modes, rejected-data tables,
collection options, and `NO COMMIT` cannot leak through COPY grammar reuse.
`FlexibleCopyDefinition` narrows that context again: file and UDL inputs must
carry a parser, built-in formats are excluded, and an explicit COPY column
list must preserve `__raw__`. Iceberg tables do not reuse COPY at all; an
`IcebergExternalTableSpec` models their location, mutually exclusive catalog
modes, authentication payload, and metadata-bound type overrides.

Role lifecycle DDL stays canonical where the SQLGlot tree is lossless:
`CREATE ROLE`, rename, and single-target `DROP ROLE` use `exp.Create`,
`exp.Alter`, and `exp.Drop`. A comma-separated role drop uses `DropRoles` so a
foreign generator cannot silently emit only one target. Resource-pool roots
subclass their corresponding canonical statement classes, but retain explicit
Vertica transforms because ordered typed parameters and subcluster selectors
have no lossless canonical property representation.

Factory-backed UDxs use a shared `CreateUserDefinedExtension` root and
`UDxFactorySpec`: the catalog name remains canonical, while language, factory,
library, and fenced mode remain an ordered atomic unit that cannot leak as a
foreign `Command`. UDx drops reuse the neutral `RoutineSignature` child already
used by privilege targets, but `DropUserDefinedExtension` alone validates the
family-specific empty/named/typed signature rules. This keeps security grants
and external-procedure signatures unchanged. Library lifecycle uses separate
CREATE/DROP roots for the same foreign-generation guarantee.

Directed-query statements use atomic custom roots because SQLGlot has no
canonical SAVE/GET/CREATE/activation lifecycle. Their input SELECTs and WHERE
filters remain ordinary traversable query children. `DirectedConstantHint`
similarly wraps the complete annotated value and propagates its child's type;
the directive and optional pairing index are typed children rather than
comment text. Table partition changes and standalone reorganization subclass
`exp.Alter`, retain a real table target and partition-property child, and fail
closed for mixed action lists until SQLGlot has a lossless general multi-action
ALTER representation.

SQLGlot's type-annotation dispatch is exact-class based. Every custom scalar
subclass consequently has an explicit entry in `Vertica.EXPRESSION_METADATA`;
inheriting from a typed canonical node is not enough.

## Optimizer safety

`TIMESERIES` is query-defining rather than a disposable SELECT argument. A
query carrying the clause is represented as `TimeseriesSelect`, an
`exp.Select` subclass. Generic optimizer rules still recognize its query
scope, while a foreign generator that does not know Vertica fails atomically
instead of returning a query with the clause removed. References to the
generated slice column are `TimeseriesSlice` nodes, not source `exp.Column`
nodes; this lets schema qualification succeed when the source table correctly
does not contain the synthetic name and gives the slice an explicit
`TIMESTAMP` type.

`ENABLE_WITH_CLAUSE_MATERIALIZATION` uses a serialized
`MaterializedWithMarker` on each marked CTE query. This is a deliberate
SQLGlot 30.13.x invariant:

- `eliminate_subqueries` can reconstruct the surrounding `exp.With`, but it
  retains the existing CTE query subtree and therefore the marker;
- `merge_subqueries` treats a SELECT with query options as unmergeable, so a
  marked CTE is not inlined;
- the Vertica generator suppresses the internal option and reconstructs the
  single clause-level hint from the marker.

This is why the dependency remains minor-version bounded. Optimizer upgrades
must rerun the marker, scope, serialized-tree, and foreign-generation contract
tests before the SQLGlot bound is advanced.

## Parser policy

Recognized Vertica syntax is parsed structurally. A malformed or unsupported
remainder of a recognized statement raises `ParseError`; it must not silently
degrade the whole statement to `exp.Command`. Opaque command preservation is
reserved for administrative statement families that are explicitly marked
`Preserved` in the coverage matrix.

Contextual words are parsed contextually wherever possible. Vertica uses many
ordinary-looking words as clause starters, so globally reserving them can break
valid column and table names.

The parser performs syntax-level validation, such as mutually exclusive COPY
options and required clause components. Restrictions that require catalog
types, server configuration, or semantic analysis are documented as
server-side restrictions and represented in a separate negative corpus rather
than guessed by the grammar.

SQLGlot 30.13 strips the `/*+` opener before storing a hint comment. Directed
constant annotations therefore use a small pure-Python `TokenizerCore`
subclass that tags real postfix plus-comments with private `str` subclasses.
This preserves unforgeable lexical provenance without changing SQLGlot's
public token/comment shape: ordinary `/*:c*/`, line comments, and even text
that resembles an internal marker remain ordinary comments. A misplaced tag
is rejected before statement parsing can consume or relocate it, and a
statement-level marker-count invariant prevents a supported postfix annotation
from disappearing in a parser path. This internal-core dependency is covered
by the same minor-version bound and must be re-audited when SQLGlot changes.

## Generator policy

Generated SQL is canonical Vertica syntax, not necessarily character-for-
character input preservation. Optional noise words and synonyms may be
normalized, but generation must preserve semantics and Vertica's required
clause order. Pretty and compact output both reparse to the same AST.

## Test policy

Each semantic feature requires:

- at least one positive AST assertion;
- compact generation and reparse equivalence;
- pretty generation and reparse equivalence for statement-level syntax;
- negative cases for required, conflicting, or misordered clauses;
- cross-dialect assertions when a canonical lowering exists;
- an explicit unsupported-generation assertion otherwise.

Package discovery is tested in a fresh interpreter that imports only SQLGlot,
so metaclass self-registration cannot mask a broken entry point. Release
verification also builds a wheel and installs it into an isolated environment.

## Runtime variants

The supported runtime is pure-Python SQLGlot. SQLGlot documents that custom
dialect subclassing may not work with the optional compiled `sqlglot[c]`
runtime, so that variant is not claimed as supported unless its own CI job and
plugin-discovery tests are added.
