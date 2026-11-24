# MockLegacyAPI

The non-idempotent legacy endpoint the AEP evaluation runs against, plus the
ground-truth oracle that says what it actually did.
`PAPER_ROADMAP.md` §3.1(1); built in Phase 2B Session 1
(`reports/phase-report-2b-session1-2026-08-05.md`).

## Why it exists

AEP's headline metric is the *undetected duplicate rate*: external effects that
happened more than once and that the protocol did not flag. Counting those
requires a source of truth the protocol cannot see or influence. This service
is that source: it applies effects, records every one of them durably, and
never lets the caller read the record.

## Layout

| File | What it is |
|---|---|
| `fingerprint.py` | **Definitions 1 and 2** — when two requests are the same mutation, and how two payloads are told apart. Quoted verbatim in the paper. |
| `ledger.py` | **Definition 3** — the SQLite ground-truth ledger, its atomicity and durability claims, and the duplicate-detection query. |
| `config.py` | The YAML fault surface, and the echo that makes a run self-describing. |
| `service.py` | The FastAPI app: mutation, read-back, config, oracle. |
| `client.py` | The AEP-side connector. Ignorant of the oracle by construction. |
| `config.example.yaml` | Reference configuration, one endpoint per response class. |
| `Dockerfile`, `compose.mock-api.yml` | Running it as a service. |

## Running it

```bash
# In-process, no container
uv run --frozen python -m experiments.mock_api \
    --config experiments/mock_api/config.example.yaml

# Or as a container
docker compose -f experiments/mock_api/compose.mock-api.yml up --build -d
curl -s localhost:8099/v1/config | python -m json.tool
docker compose -f experiments/mock_api/compose.mock-api.yml down -v
```

## Routes

| Route | Purpose |
|---|---|
| `POST /v1/endpoints/{name}/mutations` | Apply one mutation. Body is the exact request envelope from `aep_core.core.request_binding.build_exact_request_bytes`. `X-AEP-Client-Reference` is stored opaquely for read-back. |
| `GET /v1/endpoints/{name}/readback` | Read-only reconciliation, within what the endpoint's declared capability may assert. `409` where the capability permits no evidence at all. |
| `GET /v1/config`, `GET /v1/health` | The loaded configuration and its digest. |
| `GET /v1/oracle/{mutations,duplicates,consistency}` | The ground truth. **Nothing under evaluation may call these.** |

## The two boundaries that make the numbers mean something

**The oracle is independent of the system under test.** The fingerprint is
computed by this service from the request as it arrived on the wire, using its
own canonicaliser — not AEP's. AEP's own request fingerprint travels as an
opaque *client reference*, is stored for read-back, and is never an input to
duplicate detection. A protocol therefore cannot reduce its measured duplicate
count by changing how it identifies its own requests.

**The connector is ignorant of the oracle.** `client.py` maps `200` to
definitive success, `4xx` to definitive failure, and *everything else* —
including the injected `5xx` — to ambiguity. This service happens to implement
its injected `5xx` as a refusal before applying, but a real caller cannot know
that, and neither may this one.

## Configuration

Five dimensions, per endpoint, all defaulting to no fault. See
`config.example.yaml` for the annotated form.

| Key | Effect |
|---|---|
| `response_class` | `ReconciliationCapability` member. Parsed by the production contract's own enum; there is no local vocabulary. |
| `identity_fields` | The projection that defines mutation identity (Definition 1). |
| `faults.delay` | `constant` / `uniform` / `exponential`, seeded. |
| `faults.server_error_probability` | Refuse with `503` **before** applying. |
| `faults.timeout_probability` | Apply, then never answer. |
| `faults.duplicate_response_probability` | Apply twice before answering. |

The last two are deliberately complementary: they are the two truths that can
hide behind one ambiguous outcome, and telling them apart is what recovery is
for.

`duplicate_response_probability` is the roadmap's "duplicate-response
probability". A single HTTP exchange cannot deliver two responses to one
request, so the implemented form is a duplicated delivery of the *request*
inside the provider — an at-least-once internal retry. This is an
interpretation of the roadmap's wording and is flagged as one in
`config.py` and in the Session 1 report §E.

## Every run says what it was

`GET /v1/config` and the first line of the run log (`<ledger>.run.jsonl`) both
carry the whole configuration plus a `config_digest` over it. Every subsequent
log record repeats the digest. A result that cannot be attributed to a
configuration is not evidence.

## Tests

`experiments/mock_api/tests/`, collected by the repository's single `pytest`
invocation (`testpaths` in `pyproject.toml`), so the zero-skip and zero-xpass
CI gates cover them.

```bash
REDIS_URL=redis://127.0.0.1:6381/15 AEP_PHASE2_REDIS_INTEGRATION=1 \
    uv run --frozen pytest -q -ra --strict-markers experiments/
```

`test_service_crash_safety.py` starts the service as a real OS process and
SIGKILLs it on each side of the ledger's commit boundary.
`test_evaluation_dispatch.py` needs Redis 7.2 with AOF: it dispatches a real
mutation through a real `WriteAheadRunner` in EVALUATION mode with no test
flags.
