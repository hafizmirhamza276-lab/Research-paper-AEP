# Read-back keying: what a provider can look a past mutation up *by*

**Status:** locked measurement decision (Phase 2B Session 2, amendment C1).
**Implemented in:** `experiments/mock_api/config.py` (`ReadbackKeying`),
`experiments/mock_api/service.py` (`_readback_applications`),
`experiments/mock_api/client.py` (`readback_identity_resolver`).
**Pinned by:** `experiments/mock_api/tests/test_readback_keying.py`,
`experiments/mock_api/tests/test_readback_client.py`.

---

## The paragraph to quote in the methodology section

> Reconciliation after an ambiguous outcome requires the provider to answer
> "did you apply this?". *What the provider is able to look the mutation up
> by* is not a property of the protocol under test; it is a property of the
> legacy endpoint being modelled, and it materially changes what an
> undisciplined caller can learn. We therefore make it an explicit per-run
> configuration with two values, and report every headline result under the
> first. **CALLER_REFERENCE**: the provider indexes past mutations by the
> opaque reference the caller supplied with the request. Finding one's own
> past effect then requires having minted a stable identifier for it *before*
> the ambiguity arose — which is precisely the discipline AEP has and a naive
> retry loop does not. **ORACLE_FINGERPRINT**: the provider indexes past
> mutations by their content, using the ground-truth oracle's own identity
> function (Definition 1). Any caller able to describe the mutation can then
> find it, so a baseline with no idempotency discipline is granted a working
> read-back. The second is strictly more generous than any legacy endpoint we
> are aware of, and it cannot distinguish two intended mutations with
> identical content; it exists so that the baselines' numbers can be shown not
> to be artefacts of the first choice. Both are implemented, both are echoed
> into every run's result log together with the configuration digest they
> contribute to, and no result is quoted without saying which produced it.

---

## Why the decision had to be made now

`reports/phase-report-2b-session1-2026-08-05.md` §F5 recorded the problem and
§G1 asked the question:

> The read-back path is keyed on the client reference, which is AEP's own
> fingerprint. […] A baseline that mints a fresh reference per attempt (B0,
> naive retry) will read back `NOT_APPLIED` for a mutation that *was* applied.
> That is arguably the correct model of a system with no idempotency
> discipline, but it is a modelling decision inside the measurement apparatus
> and it will affect B0's numbers.

The session-1 recommendation was to settle it before the baselines exist,
because retrofitting a second key after a matrix has run means re-running the
matrix. Amendment C1 settles it: **both**, as a per-run configuration, with
`CALLER_REFERENCE` primary.

## The two keyings, precisely

| | `CALLER_REFERENCE` (primary) | `ORACLE_FINGERPRINT` (sensitivity) |
|---|---|---|
| Provider indexes by | the `X-AEP-Client-Reference` header the request carried | `F(r)` — Definition 1 in `experiments/mock_api/fingerprint.py` |
| Caller must have retained | a stable identifier minted before dispatch | a description of the mutation it made |
| A fresh reference per attempt | finds nothing | finds the effect |
| Two distinct executions, identical content | told apart | **conflated** |
| Models | a legacy endpoint that echoes client references | a legacy endpoint that can search its own history by content |

Three properties are enforced in code rather than described:

1. **The keying is a property of the run, not of the request.** The connector
   sends both things it legitimately knows — the reference it minted, and a
   description of the mutation — and the *service* consults whichever its
   configuration names, ignoring the other even when it is present and
   correct. Both directions of that ignoring are asserted by test. A connector
   that branched on the keying would make the system under test behave
   differently depending on how it was being measured, which is the one thing
   an apparatus must never cause; a source gate asserts the connector never
   names a keying at all.

2. **The capability contract outranks the keying.** A `NO_READBACK` endpoint
   refuses under both keyings; a `POSITIVE_ONLY_READBACK` endpoint never
   asserts `NOT_APPLIED` under either. `PERMITTED_READBACK_RESULTS` is checked
   before the keying is consulted.

3. **A read-back never re-transmits protected material.** The identity
   descriptor carries exactly the keys `F(r)` reads — `connector_operation`,
   `operation_version`, `target`, `public_fields` — and nothing else.

## The hazard, stated rather than buried

`ORACLE_FINGERPRINT` cannot distinguish two mutations that denote the same
thing. Two genuinely distinct executions charging the same account the same
amount share one fingerprint, so a caller asking about the second is told about
the first — and once both have applied, the read-back returns `CONFLICT`. This
is asserted by
`test_oracle_fingerprint_conflates_two_distinct_executions_of_equal_content`,
and it is why the variant is a sensitivity analysis and not the primary model.

The evaluation workload sidesteps it by giving every execution its own target
(`experiments/harness/workload.py`), which also keeps the ground truth's
duplicate groups measuring *duplicated effects on one intended mutation* rather
than two intended mutations that looked alike. That is a property of the
workload, not of the keying, and it must be restated wherever a workload with
colliding content is used.

## What this costs, and what it buys

Under `CALLER_REFERENCE` the naive-retry baseline (B0) will read back
`NOT_APPLIED` for mutations it did apply, and will therefore duplicate. A
reviewer is entitled to ask whether that result is an artefact of the
apparatus. The answer is a second column: the same matrix under
`ORACLE_FINGERPRINT`, where B0 is handed the best read-back any provider could
offer. If B0 still duplicates, the result is about B0. If it does not, the
result is about the read-back key, and the paper says so.

Both keyings contribute to `MockApiConfig.config_digest`, so a run collected
under one can never be attributed to the other.

## Residual limitations

* Under `ORACLE_FINGERPRINT` the caller must retain enough to describe its
  request. In this harness that is free, because the workload derives every
  request deterministically from its execution id. A real caller would need a
  request store, and one that lost it would be back to `CALLER_REFERENCE`.
* Neither keying models a provider that answers *approximately* — fuzzy
  matching on amount and timestamp, which is what a human reconciliation desk
  actually does. That is a third model, unimplemented, and out of scope.
* `F(r)`'s identity projection is per-endpoint configuration. An endpoint
  configured with too narrow a projection makes `ORACLE_FINGERPRINT` more
  conflating still. Session 1 §F13 records this; it is inherited here.
