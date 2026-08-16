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

USER lifecycle deliberately has a narrower security boundary. `CreateUser`,
`AlterUser`, and `DropUsers` retain ordinary identifier and rename children,
but explicit Vertica transforms validate the bounded non-secret grammar and
prevent foreign generators from silently discarding account state or secondary
drop targets. Ordered CREATE/ALTER parameter lists combine existing
`UserAction` account lock/unlock and password-expiry markers with typed
`UserParameter` profile and resource-pool assignments, including an optional
subcluster identifier, plus deterministic time/capacity settings. Interval
strings are checked lexically against the documented 20-day or one-year
ceilings; memory and temporary-space strings have finite percentage/unit
shapes; and `MAXCONNECTIONS` retains its explicit database/node scope.
ALTER-only `SECURITY_ALGORITHM` retains one canonical reviewed enum string. No
password, TOTP secret, or other credential value has an AST slot. Names share
the connection-policy lexical rules, additionally
enforce Vertica's 128-byte UTF-8 limit, and use the active Vertica tokenizer's
identifier-token domain rather than a frozen reserved-word list. Profile and
pool existence, pool grants, and assignment effects remain catalog/server
checks. `UserSearchPath` retains either the exact DEFAULT sentinel or an ordered,
nonempty schema list whose entries can carry one namespace qualifier;
`UserDefaultRoles` retains NONE, ALL, an ordered role list, or ALL EXCEPT with
an ordered role list. DEFAULT ROLE remains an isolated ALTER action, and role
names remain unqualified. `UserConfiguration` contains ordered typed parameters
for an isolated SET or CLEAR action. CLEAR is value-free and keeps safe unquoted
ASCII configuration names; SET is restricted to the five depot parameters that
26.2 documents at USER level. Four take only numeric `0` or `1`, while
`DepotOperationsForQuery` takes `ALL`, `FETCHES`, or `NONE`. The optional
`PARAMETER` noise word and quoted/unquoted depot-operation values normalize to
`SET PARAMETER name = value`.

Tokenizable credential-bearing USER clauses are rejected before ordinary
parser errors can retain or log their values, with a fixed sanitized error at
every `ErrorLevel`. This is defense in depth, not a secret-handling API:
SQLGlot tokenization happens before parser hooks, and an upstream tokenizer
error (for example, an unterminated credential string) can include raw input.
Callers must never submit real credentials to this dialect. Literal admission
is clause-aware so documented USER limit strings and the reviewed finite depot
enum can enter the AST while credential literals in `IDENTIFIED BY`, `SALT`,
`REPLACE`, and unreviewed SET paths still fail before ordinary parser
diagnostics. For the reviewed boundary, `UseDepotForReads=0` and
`DepotOperationsForQuery='Fetches'` are accepted and the latter emits
`DepotOperationsForQuery = FETCHES`; Boolean `2`, unknown parameter names, and
unknown/string values are rejected. Arbitrary value-bearing USER configuration
parameters stay outside the semantic contract and fail closed when recognized.

PROFILE lifecycle uses `CreateProfile`, `AlterProfile`, and `DropProfiles`
roots plus ordered `ProfileLimit` and `ProfileParameter` children. The values
are password-policy metadata—unsigned numeric settings or explicit policy
sentinels—not passwords or other credential material. Parser and generator
validate documented deterministic ranges lexically, including arbitrarily
large source digits, and reject only same-statement minimum/maximum conflicts
that can be decided without catalog state. Profile assignment, inherited
effects, ownership, and effects on current passwords remain server concerns.

AUTHENTICATION lifecycle uses atomic `CreateAuthentication`,
`AlterAuthentication`, and `DropAuthentication` roots. `AuthenticationAccess`
retains LOCAL versus HOST, the opaque HOST address string, and the three
distinct TLS states (omitted, TLS, and NO TLS). CREATE flags and every ALTER
structural change remain typed; ALTER accepts exactly one enable/disable,
access, rename, finite method, lexical nonnegative priority, Boolean MFA, or
fallthrough action. METHOD is restricted to the eight 26.2 spellings and
remains a standard string literal. The parser rejects CREATE method/fallthrough
combinations that the primary source declares incompatible; ALTER compatibility
depends on the record's catalog method and remains server-side. Address
validity, grants, priority effects, and runtime matching also remain server
concerns. `AuthenticationSet` owns an ordered nonempty list of typed
`AuthenticationParameter` children, but its static allowlist contains only two
OAuth settings whose complete values are closed by the 26.2 sources:
`validate_type` accepts standard strings `IDP` or `JWT`, and `jit_enabled`
accepts standard strings `yes` or `no`. Input casing normalizes to those exact
spellings; quoted alternatives outside the finite sets, unquoted values,
duplicates, unknown names, and nonstandard literal tokens are rejected.

The parameter audit classifies `bind_password` and `client_secret` as explicit
secrets. LDAP/Ident/Kerberos parameters (`host`, `ldap_continue`, `starttls`,
`binddn_prefix`, `binddn_suffix`, `domain_prefix`, `email_suffix`, `basedn`,
`binddn`, `search_attribute`, `system_users`, and `realm`) and the remaining
OAuth parameters (`groups_claim_name`, `oauth2_jit_authorized_roles`,
`role_group_suffix`, `roles_claim_name`, `client_id`, `discovery_url`,
`introspect_url`, `auth_url`, `token_url`, `scope`, `validate_hostname`,
`jwt_rsa_public_key`, `jwt_ec_public_key`, `jwt_jwks_url`, `jwt_issuer`,
`jwt_user_mapping`, `jwt_accepted_audience_list`, and
`jwt_accepted_scope_list`) accept arbitrary or incompletely documented strings;
they are therefore catalog/unknown for this AST security boundary even when
their intended content is not itself secret. Unknown future names receive the
same classification. A fixed pre-AST sanitizer rejects every excluded name and
every out-of-domain allowlisted value before ordinary parser diagnostics can
retain the payload. For example, `validate_type='JWT'` and
`jit_enabled='no'` are accepted and canonical; `validate_type='OIDC'`,
`validate_hostname='true'`, `client_secret='sentinel'`, and any unknown name
fail with the same sanitized error. This remains defense in depth: callers must
never submit real credentials because tokenization precedes parser hooks.

Executable `PROFILE` uses a separate atomic `ProfileStatement` wrapper whose
required `this` child is the complete profiled statement. SELECT/set-operation
queries and the documented INSERT, UPDATE, DELETE, COPY, and MERGE families
remain canonical or existing Vertica-specific children, so hints, comments,
column/table traversal, optimization, and serialization do not depend on
recovering SQL from opaque text. The wrapper owns only its one batch statement;
DDL, transaction control, VALUES-only queries, and nested PROFILE fail closed.
Foreign dialects reject the wrapper atomically because dropping PROFILE would
change execution behavior.

Workload-routing lifecycle roots likewise subclass canonical CREATE, ALTER,
and DROP nodes while keeping their route specification, name/workload target,
and single ALTER action explicit. Session controls retain a canonical
`SetItem(EQ(Column, value))` child inside `SetSessionRouting`; this keeps the
assignment traversable while preserving Vertica's distinct `WORKLOAD TO` and
`RESOURCE_POOL =` operators. The optimizer may quote the internal left-hand
marker, so generation validates its one-part semantic name rather than its
quoting metadata. `ShowWorkload` is atomic because SQLGlot 30.13 tokenizes SHOW
payloads as opaque command text. Workload privilege targets remain canonical
GRANT/REVOKE roots, but `ON ROUTING RULE` normalizes to the documented
`ON WORKLOAD` target and receives exact USAGE/target/principal validation.

Load-balance-group roots follow the same atomic statement policy. A
`LoadBalanceGroupSpec` keeps its ADDRESS, FAULT GROUP, or SUBCLUSTER members,
optional policy, and required branch-specific filter traversable; a separate
`LoadBalanceGroupAction` represents SET/ADD/DROP without conflating group
membership with routing-rule destinations. Rename stays canonical as
`AlterRename`. Parser and generator share neutral connection-policy identifier
rules, while member existence, current group type, CIDR validity, and dependent
routing rules remain catalog concerns.

Network-address roots complete the connection-policy lifecycle without
conflating it with the deprecated NETWORK INTERFACE family. A
`NetworkAddressSpec` retains the node, opaque address/hostname string, optional
port, and explicitly supplied enabled state; omission remains omission rather
than synthesizing server defaults. `NetworkAddressAction` represents endpoint
replacement and state changes, while rename stays canonical as `AlterRename`.
Identifiers follow Vertica's ASCII-first, Unicode-letter-continuation rules,
and ports are validated lexically as unsigned integers without guessing a
server range or converting arbitrarily large digit strings to Python integers.
Node existence, endpoint ownership, address-family validity, reachability, and
load-balance-group dependency effects remain catalog or server concerns.

Factory-backed UDxs use a shared `CreateUserDefinedExtension` root and
`UDxFactorySpec`: the catalog name remains canonical, while language, factory,
library, and fenced mode remain an ordered atomic unit that cannot leak as a
foreign `Command`. UDx drops reuse the neutral `RoutineSignature` child already
used by privilege targets, but `DropUserDefinedExtension` alone validates the
family-specific empty/named/typed signature rules. This keeps security grants
and external-procedure signatures unchanged. Library lifecycle uses separate
CREATE/DROP roots for the same foreign-generation guarantee.

The documented COMMENT ON family uses one atomic `CommentOn` root. Qualified
catalog objects and columns remain canonical table/column children, routine
targets reuse `RoutineSignature`, and `CommentConstraintTarget` keeps the
constraint name and owning table separate. The comment value is exactly one
standard string literal or `NULL`; the latter preserves comment removal rather
than conflating it with an absent AST child. Catalog ownership/existence and
the server's documented 8192-character truncation remain server concerns.
Foreign dialects reject both the root and the detached constraint target.

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
