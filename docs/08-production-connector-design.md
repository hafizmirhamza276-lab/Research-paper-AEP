# AEP production connector contract

**Status:** Proposed design; not implemented  
**Date:** 2026-07-28  
**Design baseline:** `docs/06-phase2-design.md`  
**Gap baseline:** P2-004, P2-006, P2-009, and P2-010 in
`docs/07-phase2-gap-audit.md`  
**Scope:** The request, dispatch, response-evidence, and reconciliation
boundary for one non-idempotent external mutation  
**Normative terms:** MUST, MUST NOT, SHOULD, and MAY are requirements in the
RFC 2119 sense.

This document is a contract for a future implementation. It does not authorize
production dispatch. The current `ExternalMutationConnector.mutate` signature
and current Redis deployment do not meet this contract.

## 1. Purpose and governing guarantee

The connector boundary must bind an intent to the exact immutable mutation
semantics that the connector is permitted to send, without placing credentials,
payment data, or unnecessary personally identifiable information (PII) in
Redis, logs, exceptions, quarantine records, metrics, or ordinary operator
views.

The governing guarantee remains:

> Ambiguity, corruption, and contention are detectable; the system fails closed.

This contract does not make a Redis write and a provider mutation one atomic
transaction. It does not assume provider-side idempotency and does not claim
exactly-once external effects, absolute atomicity, split-brain prevention, or
guaranteed duplicate prevention. Automatic transport retries for a
non-idempotent mutation remain forbidden.

## 2. Security and protocol invariants

The future implementation MUST enforce all of the following:

1. AEP, not its caller, computes the persisted request fingerprint.
2. The request fingerprint binds a versioned connector operation, endpoint
   profile, redacted target, public mutation fields, and protected commitments
   to sensitive mutation fields. A separate request-binding digest binds that
   semantic fingerprint to the immutable material locator, intent, correlation
   ID, descriptor, and retention deadlines.
3. Raw credentials, authentication tokens, payment data, and unnecessary PII
   never enter the intent ledger or any data derived mechanically from it.
4. The sensitive request object is create-once. It cannot be updated in place
   before or after `ABOUT_TO_FIRE`.
5. The connector verifies the persisted binding immediately before opening a
   provider transport. A missing object, stale version, failed integrity check,
   or fingerprint mismatch forbids transmission.
6. The connector obtains its provider endpoint and credential scope from its
   startup-validated descriptor, not from caller-controlled request fields.
7. The runner makes one application-level call to `mutate`. The connector and
   its HTTP/client stack perform no automatic mutation retry.
8. Recovery calls only `read_back`; it never receives a dispatch capability
   and never calls `mutate`.
9. Unclassified, malformed, contradictory, timed-out, or possibly transmitted
   outcomes are ambiguous by default.
10. A new attempt after permanent ambiguity requires a separately authenticated
    and authorized risk decision bound to the exact proposed new attempt.

## 3. What “exact request” means

The exact intended request is the immutable, wire-neutral mutation semantics,
not every byte of a provider protocol exchange.

The semantic request includes the operation, destination account/profile,
logical target, amounts and currencies, resource identifiers, mutation options,
and any sensitive business values whose change could alter the external
effect. It excludes authentication tokens, TLS session state, request
signatures, transport timestamps, generated nonces, and protocol framing.

Those excluded values are transport material. They MAY be created just in time,
but the following facts remain bound to the request:

- the credential profile and, when policy requires it, its immutable version;
- the endpoint profile and provider account/principal;
- the connector contract, request schema, canonicalization, and wire-codec
  versions; and
- the policy that controls correlation metadata, signing, and dynamic headers.

A connector MUST implement a deterministic, versioned transformation from the
semantic request to provider fields except for the declared transport material.
Any field not explicitly declared transport material is part of the mutation
semantics and MUST be frozen before `ABOUT_TO_FIRE`.

This distinction permits ordinary credential rotation without changing a
payment amount or recipient, while preventing a caller from substituting a
different provider account, target, or payload after write-ahead preparation.

## 4. Immutable request model

### 4.1 Full mutation request envelope

`MutationRequestEnvelope` is a frozen, typed value produced by the registered
connector's `prepare` method. It is held only in protected memory and in the
encrypted request vault recommended in Section 6. It MUST NOT implement a raw
`repr`, unrestricted `model_dump`, or generic JSON serialization path.

| Field | Contract |
|---|---|
| `envelope_schema` | Exact identifier such as `aep.mutation-request/1`; immutable. |
| `connector_operation` | Globally unique, versioned operation ID; immutable. |
| `connector_contract_version` | Exact connector behavior contract used for preparation, classification, and reconciliation. |
| `request_schema_version` | Exact semantic request schema. |
| `canonicalization_version` | Exact canonicalization and fingerprint rules. |
| `wire_codec_version` | Exact semantic-to-provider transformation version. |
| `endpoint_profile_id` | Opaque registry-owned destination profile; no caller-supplied URL or hostname. |
| `credential_binding` | Opaque secret-manager profile and optional pinned version; never a credential value. |
| `target` | Redacted logical target safe for the intent ledger and incidents. |
| `public_fields` | Strictly typed mutation fields approved as non-sensitive. |
| `sensitive_fields` | Exact sensitive mutation values; vault/memory only. |
| `reconciliation_fields` | Minimum fields required for read-only lookup; separately access-controlled. |
| `intent_id` | Preallocated UUIDv4 to prevent the object being reused by another intent. |
| `correlation_id` | Preallocated AEP UUIDv4; provider metadata only, not an idempotency guarantee. |
| `created_at` | Trusted server time from the preparation service. |
| `dispatch_material_not_after` | Time after which the vault refuses dispatch-material access. |

The model MUST reject unknown fields. It MUST use immutable collections and
defensive copies so mutation of caller-owned dictionaries, lists, byte arrays,
or domain objects cannot change the prepared request.

The global serialized cleartext limit for one full envelope is 1 MiB. Every
connector operation MUST declare a smaller maximum when possible. Inputs over
the declared limit fail before an intent is created. Streaming uploads and
large documents require a separate content-addressed object contract; they
MUST NOT be embedded in this envelope by default.

### 4.2 Persisted request binding

Redis stores only `PersistedRequestBinding`, as an immutable part of the intent
record:

| Field | Contract |
|---|---|
| `request_material_ref` | Opaque, unguessable reference to a create-once vault object. No tenant, customer, account, URL, or business meaning is encoded in it. |
| `request_material_version` | Exact immutable vault-object version; initially `1`. |
| `request_fingerprint` | Lowercase SHA-256 hex digest computed as specified in Section 5. |
| `request_binding_digest` | Lowercase SHA-256 hex digest binding the semantic fingerprint to this exact vault object and intent, as specified in Section 5.5. |
| `connector_operation` | Must equal the intent's versioned connector name. |
| `connector_contract_version` | Exact contract descriptor version. |
| `request_schema_version` | Exact semantic request schema. |
| `canonicalization_version` | Exact canonicalization rules. |
| `wire_codec_version` | Exact provider mapping. |
| `endpoint_profile_id` | Opaque, redacted registry identifier. |
| `credential_binding_id` | Opaque credential profile identifier; never a secret path containing customer data. |
| `target` | Same redacted target stored by the intent. |
| `commitment_scheme` | Versioned sensitive-value commitment scheme and key version. |
| `reconciliation_material_ref` | Optional separate opaque reference accessible to the recovery identity. |
| `dispatch_material_not_after` | Vault access deadline; safe timestamp only. |
| `reconciliation_material_not_after` | Retention deadline for the minimized reconciliation capsule. |

The canonical form of this binding MUST be at most 16 KiB. `public_fields`
within its fingerprint manifest MUST be at most 8 KiB. An individual safe
string MUST be at most 512 UTF-8 bytes unless a connector declares a smaller
limit. Connector names, schema identifiers, rule identifiers, target values,
and external references MUST use explicit character allowlists and lengths.

The current `IntentRecord` does not contain this complete binding. A future
implementation must extend the typed schema and the Lua immutable-field checks;
it MUST NOT hide these fields in `context_data` or store raw request material in
`intent_ledger`.

### 4.3 Prepared mutation handle

`PreparedMutation` combines:

- the frozen full envelope;
- the safe persisted binding;
- an integrity-verified vault lease/capability scoped to the connector identity
  and preallocated `intent_id`; and
- an explicit redacted rendering safe for diagnostics.

It is not a durable replay token. If the worker dies after `ABOUT_TO_FIRE`, a
new worker MUST NOT use the vault reference to dispatch. Recovery may access
only the separate reconciliation capsule under its read-only identity.

## 5. Canonical serialization and fingerprint

### 5.1 Canonical semantic request document

The fingerprint input is a secret-free `SemanticRequestManifest`, not the full
cleartext envelope. It MUST contain:

- a domain separator: `AEP_REQUEST_FINGERPRINT_V1`;
- connector operation, contract, request-schema, canonicalization, wire-codec,
  redactor/evidence, and commitment-scheme versions;
- endpoint and credential binding profiles;
- the redacted target;
- all approved public semantic fields;
- a field-path-keyed commitment for every sensitive semantic field;
- credential binding identity/version, never credential bytes; and
- the declared dynamic transport-field policy.

The semantic manifest excludes `intent_id`, `correlation_id`, vault locators,
retention deadlines, preparation timestamps, and other attempt-specific
metadata. Therefore, two attempts with identical mutation semantics under the
same connector contract, security profiles, and commitment-key version produce
the same `request_fingerprint`. Attempt and storage binding is provided by
Section 5.5.

Omitting a field from the manifest is permitted only when the connector
descriptor declares it transport-only and demonstrates that it cannot change
the external mutation semantics.

### 5.2 Normalization rules

Before canonical serialization, the connector-owned schema validator MUST:

1. reject duplicate object keys and unknown fields;
2. require Unicode strings to already be NFC and reject non-NFC input rather
   than silently normalizing it;
3. represent monetary values as an integer minor-unit string plus an ISO
   currency code, never a binary float;
4. forbid NaN, positive infinity, and negative infinity;
5. represent timestamps in one declared UTC format or as integer epoch units;
6. represent binary data as unpadded base64url;
7. use lowercase canonical UUID strings;
8. distinguish an omitted field from explicit `null` according to the request
   schema; and
9. preserve array order when order is semantic and sort set-like collections
   according to their declared schema rule before serialization.

The normalized semantic manifest is serialized with RFC 8785 JSON Canonicalization
Scheme (JCS) to UTF-8 without a byte-order mark. Each canonicalization version
MUST publish golden input, canonical-byte, and digest vectors. A connector
cannot be registered without passing those vectors in the deployment runtime.

### 5.3 Sensitive-value commitments

Raw or directly hashed sensitive values MUST NOT appear in the manifest.
Payment data and many PII values have small enough domains for an ordinary
SHA-256 digest to permit offline guessing.

For every sensitive semantic field, the request vault computes:

```text
commitment = HMAC-SHA-256(
    K_commit_version,
    UTF8("AEP_SENSITIVE_FIELD_V1") || 0x00 ||
    UTF8(connector_operation) || 0x00 ||
    UTF8(field_path) || 0x00 ||
    canonical_sensitive_value
)
```

`K_commit_version` is a KMS-protected commitment key separate from the
encryption data key. The manifest contains only the lowercase commitment and
key version. The connector never logs either the cleartext value or the key.
The key version remains available for verification until the corresponding
request bindings expire.

Authentication credentials are not treated as semantic sensitive fields.
Their opaque binding ID and required version are included instead. If a
provider account or credential scope can change the destination or effect, that
identity is semantic and MUST be bound explicitly.

### 5.4 SHA-256 generation

The persisted fingerprint is exactly:

```text
request_fingerprint = lowercase_hex(
    SHA-256(UTF8(JCS(SemanticRequestManifest)))
)
```

AEP computes it from the connector's validated manifest. A public runner API
MUST NOT accept a caller-computed fingerprint. The connector recomputes it
after resolving vault material and compares it in constant time with the value
in the durable `ABOUT_TO_FIRE` record immediately before transport creation.

The fingerprint proves equality to the committed request under the stated
trust assumptions. It is not a digital signature and does not make a malicious
or compromised connector trustworthy.

### 5.5 Attempt-specific request-binding digest

The immutable vault object must also be bound to the exact attempt. AEP creates
a secret-free `AttemptRequestBindingManifest` containing:

- domain separator `AEP_ATTEMPT_REQUEST_BINDING_V1`;
- `request_fingerprint`;
- request and reconciliation material references and immutable versions;
- `execution_id`, `step_id`, `intent_id`, and `correlation_id`;
- connector descriptor digest;
- endpoint and credential binding IDs;
- redacted target; and
- dispatch and reconciliation material deadlines.

It is normalized under the same JSON rules and serialized with JCS. The
persisted digest is:

```text
request_binding_digest = lowercase_hex(
    SHA-256(UTF8(JCS(AttemptRequestBindingManifest)))
)
```

The Lua create-intent path persists both hashes and treats every binding input
as immutable. Preflight and the connector verify both in constant time. The
request fingerprint supports semantic comparison across attempts; the binding
digest detects locator, intent, descriptor, and deadline substitution.

## 6. Request-storage approaches

### 6.1 Comparison

| Approach | Security properties | Recoverability | Operational cost | Assessment |
|---|---|---|---|---|
| Encrypt the full request inside the Redis intent | One CAS can bind ciphertext and intent, but ciphertext, key metadata, and regulated-data copies propagate to Redis AOF, backups, quarantine, memory snapshots, and broad Redis/operator access. Every state rewrite copies it. | High while Redis and KMS survive; catastrophic Redis loss still loses both intent and request. | Low additional infrastructure, high data-governance and key-rotation burden. | Rejected as the default. Encryption does not make Redis an appropriate payment/PII vault. |
| Store an opaque reference to an AEP-owned create-once encrypted request vault | Redis contains only a safe locator, versions, deadlines, commitments, and fingerprint. Vault ACLs, encryption, audit, and retention are purpose-specific. The binding is independently verifiable. | Full request is available to the original dispatch identity until its short deadline; a minimized capsule is available to recovery. Vault loss or denial fails closed. | Requires a highly available vault, KMS integration, access auditing, retention jobs, and startup probes. | **Recommended.** Best separation of duties and consistent behavior across connectors. |
| Store a connector-owned request locator | Sensitive data can remain in an existing PCI/PII-controlled connector domain. AEP sees only a locator and commitments. Security depends on each connector proving create-once immutability, access separation, and retention. | Potentially excellent for a mature domain service; inconsistent or unavailable connector storage can strand recovery. | Duplicated integration and audit burden; higher risk of locator/version drift and confused-deputy behavior. | Allowed only by explicit security exception and the same conformance tests as the AEP vault. Not the default. |
| Keep only a frozen in-memory request | Smallest persisted sensitive-data footprint and simplest dispatch path. | No request recovery after process loss. This is safe for mutation because replay is forbidden, but read-back may become impossible unless it needs only persisted safe evidence. | Low infrastructure cost; poor forensic and reconciliation support. | Allowed only for operations whose declared reconciliation requires no sensitive context and whose policy accepts immediate permanent ambiguity when memory is lost. |

### 6.2 Recommendation

Use an opaque reference to an AEP-owned, create-once encrypted request vault.
Redis stores only `PersistedRequestBinding`; it does not store the encrypted
payload itself.

This choice deliberately trades added vault/KMS availability and operational
complexity for:

- a narrow Redis and log data boundary;
- uniform immutability and verification across connectors;
- independent access policies for dispatch and reconciliation;
- auditable material reads;
- short retention and crypto-erasure of full dispatch material; and
- preservation of the request binding even after sensitive material is erased.

The recoverability tradeoff is explicit: vault unavailability can prevent the
one original dispatch or a later read-back. AEP fails closed in either case. It
does not copy sensitive data into Redis to improve availability and does not
replay a mutation after a worker crash.

### 6.3 Required vault properties

The selected vault MUST provide:

- unguessable 128-bit-or-stronger opaque object references;
- create-if-absent semantics and immutable object version `1`; no update API;
- envelope encryption using a reviewed AEAD construction and KMS-managed keys;
- authenticated associated data binding object reference, connector operation,
  contract/schema versions, `intent_id`, creation time, and content length;
- independent authorization for preparation, original dispatch, read-only
  reconciliation, security administration, and retention deletion;
- no list/search API for connector workers;
- access audit records that contain only safe IDs and outcomes;
- explicit maximum object size, creation rate, and read rate;
- integrity verification before decrypting or returning material;
- a tombstone after expiry/crypto-erasure so “never existed,” “expired,” and
  “integrity failure” remain distinguishable; and
- startup probes for KMS access, create-once enforcement, TTL policy, audit
  delivery, and identity separation.

Vault writes happen before `ABOUT_TO_FIRE` and are internal preparation, not an
external provider mutation. Failed or stale intent CAS operations may leave
orphan vault objects; a retention job may remove only objects that have no
durable intent binding and have passed a conservative orphan grace period.

### 6.4 Material separation and retention

The vault stores two cryptographically and authorizationally separated
sections:

1. **Dispatch material:** the complete semantic request. Only the original
   connector dispatch identity can read it, only for the matching
   `intent_id`/fingerprint, and only until `dispatch_material_not_after`.
2. **Reconciliation capsule:** the minimum fields needed for the declared
   read-only query. Only the recovery connector identity can read it. It does
   not contain provider mutation credentials and cannot be passed to `mutate`.

The dispatch deadline MUST cover the maximum validated interval from vault
creation through preflight and the single client call. After that deadline,
full dispatch material is crypto-erased even if the intent is ambiguous,
because AEP will not replay it. A connector requiring longer retention must
justify it as a regulated-data policy exception; “possible retry” is not a
valid reason.

The reconciliation capsule is retained through the maximum reconciliation age
plus operator-retention window, unless a stricter legal limit forces earlier
deletion. If legal retention is shorter than the safety window, the connector
cannot declare read-back that depends on that material; it must declare a less
capable mode and may reach `PERMANENTLY_AMBIGUOUS` sooner.

After terminal resolution and required audit retention, the capsule is
crypto-erased. The safe Redis binding and vault tombstone follow the execution
retention policy. Deletion of an individual intent record remains forbidden.

## 7. Preparation and substitution protection

The future runner sequence is:

1. Resolve the versioned connector descriptor from the startup-validated
   registry. Caller input cannot choose a connector object, endpoint URL,
   credential, canonicalizer, or response table directly.
2. Acquire the execution lease and re-read the latest execution state.
3. Check normal attempt eligibility and the global ambiguity fence. If this is
   a proposed risk override, reject the normal runner path and require the
   privileged workflow described in Section 16; do not yet treat an approval
   as valid for a request whose fingerprint has not been computed.
4. Preallocate immutable `intent_id` and `correlation_id` values.
5. Call the connector's side-effect-free `prepare` method. It validates and
   defensively copies input, stores the full envelope and reconciliation capsule
   in the vault, and returns `PreparedMutation`.
6. AEP independently validates the returned safe binding, recomputes the
   fingerprint, and rejects unknown versions, fields, or sizes. For a proposed
   risk override, the privileged workflow now obtains and verifies a grant
   bound to this exact old intent, new intent ID, new request fingerprint, and
   request-binding digest.
7. In the `NONE -> ABOUT_TO_FIRE` Lua CAS, persist the complete safe binding,
   request fingerprint, request-binding digest, IDs, connector descriptor
   digest, and risk decision if any. The Lua script treats every binding field
   as immutable.
8. Confirm the approved same-connection local durability barrier.
9. Run the existing atomic token/TTL/version/status preflight, extended to
   verify the stored request-binding digest and selected connector descriptor
   digest.
10. Resolve the vault object under the original dispatch identity. Verify the
    object version, AEAD integrity, `intent_id`, correlation ID, connector and
    schema versions, endpoint/credential bindings, sensitive commitments,
    recomputed request fingerprint, and recomputed request-binding digest
    against the freshly read durable intent.
11. Only after every check succeeds may the connector open the provider
    transport and make its one mutation call.
12. Classify and durably record redacted response evidence. Do not persist the
    raw request, raw provider body, credentials, or sensitive headers.

The same `PreparedMutation` object MAY be retained in memory between steps 5
and 11, but the connector still performs the durable-binding comparison in
step 10. In-memory identity alone is not sufficient evidence after an await,
configuration reload, or dependency call.

The vault reference cannot be swapped without changing the request-binding
digest. A different sensitive value cannot be substituted without failing its
keyed commitment. A different endpoint, credential scope, connector build, request
schema, or wire codec cannot be substituted without failing a bound version or
profile comparison.

No mechanism can prove that deliberately malicious connector code sent the
validated request rather than different bytes. Production connector code,
build provenance, deployment identity, and provider-facing integration tests
remain trusted controls in the threat model.

## 8. Connector interfaces

The types below are pseudocode defining the required shape. They are not an
implementation prescription.

```python
class ProductionMutationConnector(Protocol):
    descriptor: ConnectorDescriptor

    async def prepare(
        self,
        *,
        intent_id: UUID,
        correlation_id: UUID,
        request: ConnectorRequestInput,
        principal: AuthenticatedPrincipal,
    ) -> PreparedMutation: ...

    async def mutate(
        self,
        *,
        prepared: PreparedMutation,
        dispatch: DispatchContext,
        client_timeout: float,
    ) -> MutationEvidence: ...
```

`prepare` MUST be side-effect-free with respect to the external provider. It
may validate policy, resolve internal records, read a secret manager, and
create the immutable internal vault object. It MUST NOT reserve, authorize,
charge, send, submit, or otherwise invoke a provider mutation.

`DispatchContext` contains only:

- `execution_id`, `step_id`, `intent_id`, and `correlation_id`;
- the freshly read durable `PersistedRequestBinding`;
- `prepared_state_version` and the preflight result;
- a monotonic client deadline and timeout;
- the exact registry descriptor digest; and
- a non-serializable authorization proving this is the original runner path.

`mutate` MUST:

- accept no target URL, credential value, amount, recipient, or mutable payload
  outside `PreparedMutation`;
- verify `PreparedMutation.binding == dispatch.persisted_binding` before any
  provider bytes may be sent;
- obtain credentials just in time under the descriptor's credential binding;
- add the bound AEP correlation ID when the provider supports metadata;
- disable HTTP/client retries, redirect following, and transparent failover
  unless each behavior is proven not to repeat or redirect the mutation;
- enforce the client timeout itself, in addition to the runner deadline;
- return one typed evidence variant; and
- expose no hidden “mutation applied” truth that the real caller could not know.

### 8.1 Read-back protocols

Reconciliation is a distinct, read-only interface:

```python
class AuthoritativeReadbackConnector(ProductionMutationConnector, Protocol):
    async def read_back(
        self,
        *,
        context: ReconciliationContext,
        readback_timeout: float,
    ) -> ReconciliationEvidence: ...


class PositiveOnlyReadbackConnector(ProductionMutationConnector, Protocol):
    async def read_back(
        self,
        *,
        context: ReconciliationContext,
        readback_timeout: float,
    ) -> ReconciliationEvidence: ...


class NoReadbackConnector(ProductionMutationConnector, Protocol):
    # No read_back method is registered or invoked.
    ...
```

`ReconciliationContext` includes safe intent identity and timing, redacted
target, request fingerprint, correlation ID, external reference if known,
reconciliation capsule reference, prior redacted observations, and attempt
count. It contains no dispatch authorization and no full request. The recovery
service identity cannot read dispatch material or obtain provider mutation
credentials.

`read_back` MUST use a provider read/query operation that is independently
classified as non-mutating. Redirects or SDK behavior that can turn it into a
write are forbidden. A timeout, connector exception, or schema mismatch is
operationally unknown; it never proves non-application.

## 9. Mutation response evidence

`MutationEvidence` is a sealed union with exactly three variants:

| Variant | Required proof | State mapping |
|---|---|---|
| `AppliedEvidence` | A connector allowlisted response rule proves the requested effect exists and matches the bound request. | `FIRED_CONFIRMED` |
| `NoEffectEvidence` | A connector allowlisted rule proves the provider rejected or failed the request before applying any effect. Generic status families are insufficient. | `FAILED_CONFIRMED` |
| `AmbiguousMutationEvidence` | Transmission may have occurred, proof is incomplete, response is malformed/unclassified, or evidence conflicts. | `FIRED_UNCONFIRMED` |

Every variant contains a typed `classification_rule_id`, descriptor version,
redacted provider result code, observation time, transmission phase, and safe
evidence commitment. `AppliedEvidence` may contain a validated redacted external
reference. `NoEffectEvidence` must identify the exact allowlisted no-effect
rule. `AmbiguousMutationEvidence` may contain only safe transport and error
classes.

Raw provider bodies, headers, URLs with query strings, credentials, stack-local
request objects, PANs, bank details, names, addresses, email addresses, and
unapproved provider identifiers MUST NOT appear in an evidence object.

The connector descriptor contains a complete response-classification table:

| Table field | Requirement |
|---|---|
| `rule_id` | Stable and unique within the contract version. |
| `provider_condition` | Exact typed condition, not only a status-code family. |
| `transmission_assumption` | Before transmission, possible transmission, or response received. |
| `evidence_variant` | Applied, no effect, or ambiguous. |
| `justification` | Provider contract/review evidence for the conclusion. |
| `safe_extractors` | Allowlisted redacted fields and limits. |
| `test_vectors` | Positive, negative, malformed, and conflict cases. |

Rules must be disjoint. Anything matching no rule, more than one incompatible
rule, or a rule whose required field is absent maps to ambiguity. An HTTP 5xx,
connection loss, timeout, cancellation after possible transmission, malformed
success body, or conflicting reference is ambiguous unless stronger
connector-specific evidence conclusively proves otherwise.

A local `NoDispatchEvidence` is owned by AEP, not returned as provider success
or failure. It is valid only when AEP proves the connector transport was never
entered and can durably persist that fact while it still owns the lease.

## 10. Reconciliation evidence and capability

Each exact connector operation version declares one and only one capability:

| Capability | Legal results | Negative semantics |
|---|---|---|
| `AUTHORITATIVE_READBACK` | `APPLIED`, `NOT_APPLIED`, `UNKNOWN`, `CONFLICT` | `NOT_APPLIED` is legal only after the declared settlement horizon and only when the query proves absence for this exact request/target. |
| `POSITIVE_ONLY_READBACK` | `APPLIED`, `UNKNOWN`, `CONFLICT` | Absence or “not found” always maps to `UNKNOWN`. |
| `NO_READBACK` | No automated query | Recovery durably moves the orphaned intent to permanent ambiguity and raises a critical incident. |

`ReconciliationEvidence` is a sealed union:

- `AppliedReadbackEvidence`: one unique match whose semantic binding or
  authoritative provider reference matches the intent;
- `NotAppliedReadbackEvidence`: an authoritative, horizon-qualified proof of
  absence;
- `UnknownReadbackEvidence`: no conclusive proof, eventual-consistency absence,
  timeout, safe operational error, or incomplete query;
- `ConflictReadbackEvidence`: multiple possible matches or contradictory
  evidence.

The state mappings remain those in `docs/06-phase2-design.md` Section 8.3.
Recovery never repeats the mutation. An unclassified read-back result or
capability violation becomes conflict/permanent ambiguity, not confirmed
failure.

The descriptor MUST identify the read-back query keys. Preference order is:

1. provider external reference known from a response;
2. provider-supported correlation metadata plus exact target/profile;
3. a connector-defined immutable provider-side lookup key; and
4. a minimized reconciliation capsule search with explicit collision handling.

The AEP correlation ID is evidence only. This contract does not treat it as a
provider idempotency key or assume the provider enforces uniqueness.

## 11. Settlement horizon

Each connector operation declares finite, non-negative timing values:

- `client_timeout_seconds`;
- `buffer_margin_seconds`, at least 15 seconds;
- `provider_settlement_lag_seconds`;
- `negative_authority_after_seconds`, only for authoritative read-back;
- `readback_timeout_seconds`;
- maximum reconciliation attempts and duration; and
- backoff base and cap.

Booleans, NaN, infinities, negative values, and values over registry policy caps
are invalid. Startup rejects them.

The first automatic read-back is not eligible before:

```text
reconcile_after =
    prepared_at
    + client_timeout_seconds
    + buffer_margin_seconds
    + provider_settlement_lag_seconds
```

For authoritative negative evidence, the connector must additionally require:

```text
observation_time >= prepared_at + negative_authority_after_seconds
```

The effective negative horizon is the later of those two times. Before it,
“not found” is `UNKNOWN`. If the provider cannot publish a defensible bounded
negative horizon, the connector MUST declare `POSITIVE_ONLY_READBACK` or
`NO_READBACK`; configuration optimism cannot make absence authoritative.

Settlement values are part of the versioned connector descriptor and the
intent's immutable timing record. A deployment may increase a future
connector version's horizon, but it cannot shorten the horizon of an existing
intent. If later provider guidance invalidates an old negative rule, unresolved
old intents fail closed to `UNKNOWN` or `PERMANENTLY_AMBIGUOUS`.

## 12. Secret and PII handling

### 12.1 Classification

Every request and response schema field is classified at design time as one of:

- `PUBLIC_SAFE`: approved for the safe binding and structured telemetry;
- `REDACTED_IDENTIFIER`: transformed to an opaque/pseudonymous bounded value;
- `SENSITIVE_SEMANTIC`: encrypted in the vault and represented by a keyed
  commitment in the fingerprint manifest;
- `SECRET_AUTH`: stored only in the secret manager and referenced by an opaque
  credential binding; or
- `FORBIDDEN`: not accepted or retained by AEP.

Unclassified fields are `FORBIDDEN`. A connector cannot move a field to a less
restrictive class without a new reviewed contract version.

### 12.2 Redaction rules

Redaction is allowlist-based, not regular-expression cleanup after logging.
Connector code constructs safe telemetry and evidence objects explicitly. Raw
request/response objects are never passed to a logger, exception formatter,
tracer, metric label, incident hook, or generic serializer.

The following controls are mandatory:

- secret-bearing types have a constant redacted `repr` and prohibit string
  coercion;
- logs use structured safe fields and reject unknown keys;
- exception messages contain only stable error classes and safe IDs;
- traces disable request/response body capture and sensitive headers;
- metric labels never contain target, locator, external reference, PII, or
  high-cardinality request identifiers;
- Redis quarantine sanitizes typed Phase 2 records or encrypts forensic payloads
  under a separately authorized security identity; it must not copy raw vault
  material;
- provider external references are validated, bounded, and redacted before
  persistence;
- incident payloads contain only execution ID, intent ID, redacted target,
  fingerprint, safe timestamps, rule IDs, and redacted evidence; and
- secret/PII canaries are tested across Redis, poison records, logs, traces,
  exceptions, metrics, alerts, model dumps, and vault audit events.

A SHA-256 fingerprint, HMAC commitment, or opaque locator may still be treated
as regulated metadata under an organization's policy. Access and retention
must therefore remain least-privilege even though the values do not expose
cleartext.

## 13. Connector registry and startup validation

Production code obtains connectors only from an immutable registry constructed
and validated before scheduling traffic. No lazy `getattr` capability discovery
is permitted on a live ambiguous intent.

### 13.1 Connector descriptor

Each descriptor contains:

- unique versioned connector operation ID;
- contract, request schema, canonicalization, wire-codec, redactor,
  commitment-scheme, and evidence-schema versions;
- implementation build/provenance digest;
- endpoint and credential profile IDs and allowed account/principal bindings;
- request field classification and size schema;
- vault namespace, retention, and access identities;
- complete mutation response-classification table;
- one reconciliation capability and complete result table;
- query key scheme and collision behavior;
- settlement, timeout, lease, retry-disabled, and reconciliation policy;
- supported risk-acceptance policy class;
- safe telemetry schema; and
- declared compatibility window for unresolved historical intents.

The canonical descriptor is hashed. Its digest is persisted with each intent so
runtime configuration drift is detectable.

### 13.2 Mandatory startup checks

Startup MUST reject the entire production dispatch service if any enabled
connector fails any check below:

1. Operation IDs and versions are syntactically valid and globally unique.
2. The runtime implementation and descriptor build digest match.
3. `prepare` and `mutate` have the exact typed interfaces. `read_back` presence
   and result variants match the declared capability.
4. Request schemas reject unknown fields, unsafe numbers, oversized values, and
   unclassified fields.
5. Canonicalization and fingerprint golden vectors match byte-for-byte.
6. Sensitive commitment vectors match under the configured KMS key version.
7. Response and read-back tables are complete, disjoint, and ambiguity-default.
8. No-effect and authoritative-negative rules have reviewed evidence and test
   vectors.
9. Settlement, timeout, lease, and retention values are finite, bounded, and
   internally consistent.
10. HTTP/client retries and redirect behavior are disabled for mutation calls.
11. Endpoint profiles are allowlisted and cannot be overridden by request data.
12. Credential profiles exist, are scoped to the expected provider principal,
    and do not expose secret values to AEP logs or Redis.
13. Vault/KMS create, immutable-read, tamper detection, expiry, tombstone, ACL,
    and audit probes succeed under the appropriate distinct identities.
14. Redaction canaries are absent from every declared telemetry sink.
15. Every connector version referenced by an unresolved retained intent remains
    registered for read-only recovery, or startup enters a global fail-closed
    operator state.
16. The production durability barrier and all other Phase 2 Section 11 gates
    pass. A fake barrier is rejected.

The registry is all-or-nothing by default. An explicitly isolated connector may
be disabled only if the scheduler can prove no active or unresolved intent
depends on it. Missing recovery support for an existing intent is a critical
incident, not a reason to discard the intent.

## 14. Schema and version compatibility

The contract has independent versions because they change for different
reasons:

| Version | Compatibility rule |
|---|---|
| Envelope schema | Governs the AEP vault object shape. Unknown major versions fail closed. |
| Connector contract | Governs operation semantics, classification, and reconciliation. Existing intents stay pinned to the exact version. |
| Request schema | Governs semantic fields and classification. Incompatible change requires a new version and new fingerprint. |
| Canonicalization | Governs normalized bytes. Any byte-affecting change requires a new version. |
| Wire codec | Governs provider mapping. A semantic mapping change requires a new version. |
| Redactor/evidence schema | Governs what may be persisted or emitted. A less restrictive change requires security review and a new version. |
| Commitment scheme/key version | Governs sensitive binding verification. Verification support remains until all dependent bindings expire. |

No request, binding, vault object, or intent is migrated in place after
`ABOUT_TO_FIRE`. Before intent creation, preparation may be discarded and
repeated under a newer version. After intent creation, any change requires a
new intent and must first satisfy normal retry or risk-acceptance policy.

Read-only compatibility adapters MAY interpret an old reconciliation capsule,
but they must be registered under the old descriptor and produce the old typed
evidence semantics. They cannot silently “upgrade” an old intent to a new
classification rule or shorter settlement horizon.

If an old descriptor, key version, or schema cannot be loaded, the system
surfaces a critical operator incident and retains the intent as ambiguous. It
does not guess, downgrade validation, or call a newer mutation implementation.

## 15. Missing material and fingerprint mismatch

The response depends on when the defect is observed:

| Observation point | Required behavior |
|---|---|
| Before `ABOUT_TO_FIRE` | Abort preparation. Do not create an intent or call the provider. The orphan-vault retention policy may clean up any unbound object later. |
| After `ABOUT_TO_FIRE`, before connector transport is entered | Forbid transmission. If the worker still owns the lease and can durably prove local no-dispatch, transition to `FAILED_CONFIRMED` with a safe local reason. Otherwise leave `ABOUT_TO_FIRE` for conservative recovery. |
| During connector setup, with proof no provider bytes were sent | Same local no-dispatch handling; never retry under the same intent. |
| After transport may have started | Treat as ambiguous and durably record `FIRED_UNCONFIRMED` when possible. Never infer non-application. |
| During read-back | Record an operationally unknown observation and retry within policy, or move to permanent ambiguity when material is irrecoverable or limits are reached. Never mutate. |

A missing object with a valid expiry tombstone is distinguishable from a vault
integrity failure. Expiry before a permitted original dispatch is an
operational/configuration defect. It still fails closed.

A fingerprint, AEAD, commitment, version, intent-ID, descriptor-digest, or
endpoint/credential binding mismatch is corruption or substitution evidence,
not an ordinary provider failure. The implementation MUST:

1. send zero provider bytes if still before transport;
2. fence the execution and preserve the original intent;
3. raise a typed corruption/security signal;
4. create a sanitized or separately encrypted forensic record;
5. alert the operator and contribute to the systemic circuit breaker; and
6. never “repair,” overwrite, re-fingerprint, or substitute a different request
   for the existing intent.

The raw mismatching material must not be placed in the alert or Redis
quarantine record.

## 16. Risk acceptance after permanent ambiguity

`PERMANENTLY_AMBIGUOUS` never becomes implicit permission to retry. Normal
runner entry remains rejected while any execution-wide ambiguity fence exists.

A new attempt is permitted only through a separate privileged workflow that
verifies an authenticated `RiskAcceptanceDecision`. A raw caller-provided
`risk_acceptance_id` string is not authentication and is insufficient.

The decision MUST bind:

- decision ID, issuing service, authentication assurance, and issue/expiry
  times;
- authorized operator identity and role; policy may require a second approver;
- execution ID, step ID, old permanently ambiguous intent ID, and its request
  fingerprint;
- preallocated new intent ID, exact proposed new request fingerprint, and
  request-binding digest;
- connector operation, target, and endpoint/provider principal;
- ticket and evidence references, duplicate-effect impact, reason, and scope;
- whether the old intent is retained as permanently ambiguous or was separately
  resolved by conclusive evidence; and
- a nonce and cryptographic signature or equivalent unforgeable service grant.

The privileged creation CAS MUST atomically consume or validate a one-time grant
and persist the full safe decision reference with the new `ABOUT_TO_FIRE`
intent. It must reject expiry, reuse, wrong old/new intent, wrong fingerprint,
wrong target, stale execution version, or missing authorization. Normal intent
creation cannot accept this grant type.

The old intent is never deleted, reset, or reused. The new attempt has a new
intent ID and incremented attempt number. The top-level execution remains
explicitly controlled by the operator workflow; creating the new intent cannot
silently clear unrelated ambiguity fences.

An accepted decision acknowledges that the new mutation may duplicate an old
effect. The audit makes that risk explicit; it does not guarantee duplicate
prevention.

## 17. Threat model

### 17.1 Threats addressed

This contract is designed to detect or contain:

- caller mutation of request objects after preparation;
- substitution of a vault locator, sensitive value, target, endpoint,
  credential scope, connector version, or wire codec;
- Redis readers, backups, quarantine, or log collectors exposing raw request
  secrets/PII;
- low-entropy PII guessing against an ordinary request hash;
- stale workers and stale connector configurations;
- connector SDK automatic retries, redirects, and failover behavior;
- response misclassification, malformed responses, and conflicting evidence;
- a recovery worker accidentally receiving mutation credentials or a dispatch
  method;
- missing request/reconciliation material;
- schema downgrade and silent in-place migration; and
- unauthenticated attempts after permanent ambiguity.

### 17.2 Trust assumptions

The following remain trusted and require separate operational controls:

- the reviewed connector implementation and build/deployment provenance;
- the request vault, KMS, secret manager, and identity provider;
- descriptor approval and registry deployment;
- the provider documentation used to justify definitive classifications and
  settlement horizons; and
- the single-Redis topology and approved local durability configuration within
  their documented limits.

A compromised connector can intentionally send different provider bytes after
validation. A compromised vault/KMS principal can expose request material. A
lying or inconsistent provider can leave outcomes ambiguous. This design makes
those conditions observable where evidence permits; it cannot eliminate them.

### 17.3 Out-of-scope guarantees

This design does not provide:

- a distributed transaction between Redis, the vault, and the provider;
- provider-side recall after request transmission;
- provider idempotency where none exists;
- exactly-once delivery or execution;
- HA, consensus, or split-brain prevention;
- recovery after catastrophic loss of both authoritative state and its storage;
- authoritative negative read-back from an eventually consistent provider; or
- guaranteed alert delivery atomically with the Redis transition.

## 18. Alternatives considered and rejected details

### 18.1 Encrypted payload in Redis

This appears attractive because the ciphertext can be committed in the same
state CAS as `ABOUT_TO_FIRE`. It is rejected as the default because the
complete encrypted regulated payload would be copied into AOF, snapshots,
backups, replicas, poison records, and every rewritten state value. Redis
operators and backup workflows would become part of the payment/PII trust
boundary, and crypto-erasure would be difficult once backups exist. The local
CAS still would not be atomic with a provider mutation or protect against
catastrophic Redis loss.

### 18.2 Connector-owned locator

This can be a strong option when an existing payment or identity service
already owns a compliant immutable command vault. It is not the default because
each connector would otherwise define different immutability, ACL, audit,
retention, failure, and tombstone semantics. A connector-owned locator is
acceptable only when it implements this document's binding manifest,
commitments, create-once versioning, dispatch/recovery identity separation,
startup checks, and failure behavior. Merely pointing to a mutable database row
is prohibited.

### 18.3 In-memory only

An in-memory frozen envelope has the smallest storage exposure and is safe
against replay after a crash because AEP must not replay. It is insufficient as
the general contract because many connectors need sensitive, minimized lookup
context during reconciliation, and operators need to distinguish material
expiry from corruption. It remains an opt-in mode only for operations that can
reconcile from safe persisted identifiers or explicitly declare no read-back.

### 18.4 Store only a public hash and reconstruct later

Reconstructing from a business database or caller input is rejected. The source
record may change, credentials may rotate across principals, serialization code
may upgrade, and deleted data may be unavailable. Equality of a caller-supplied
hash cannot prove the reconstructed request is the request bound before
dispatch. The exact semantic snapshot must be immutable before
`ABOUT_TO_FIRE`.

## 19. Implementation and acceptance gate

Implementation must proceed test-first. No production connector should be
written until regression tests specify this contract. At minimum, future tests
must prove:

1. mutation of every caller-owned input after `prepare` cannot change the
   dispatched semantic request;
2. AEP, not the caller, computes canonical bytes and the SHA-256 fingerprint;
3. golden vectors are stable across supported runtimes;
4. locator, version, target, public field, sensitive value, endpoint,
   credential scope, connector version, and wire-codec substitutions all fail
   before provider transmission;
5. a sensitive-value change fails its keyed commitment without exposing the
   value;
6. raw secret/PII canaries are absent from Redis DB 15, `aep:*` poison records,
   logs, traces, exceptions, metrics, alerts, and model dumps;
7. vault missing, expired, denied, corrupted, wrong-version, and KMS-down cases
   follow Section 15 and produce zero mutation calls when observed before
   transmission;
8. response-table rules are complete/disjoint and every unknown defaults to
   ambiguity;
9. every reconciliation capability rejects illegal evidence, especially early
   or non-authoritative negative results;
10. recovery can read only its minimized capsule and has no mutation method,
    credentials, or replay path;
11. registry startup rejects every missing/incompatible declaration and fake
    durability;
12. old connector versions remain usable for read-only recovery without
    changing old semantics;
13. risk acceptance rejects forgery, expiry, reuse, stale versions, wrong
    fingerprints, and unrelated ambiguity; and
14. each crash boundary proves hidden provider truth, caller-visible evidence,
    durable state, read-back behavior, and unchanged mutation-call count after
    recovery.

Redis-backed tests may delete only `aep:*` keys in dedicated DB 15 and must
never use `FLUSHALL`. Real production enablement additionally requires the
Redis 7.2+ AOF/same-connection durability integration and every Section 11 gate
from `docs/06-phase2-design.md`.

Until those tests and gates pass, production non-idempotent dispatch remains
disabled. Passing the gate would establish only the bounded guarantee at the
start of this document, not any of the out-of-scope guarantees in Section 17.3.
