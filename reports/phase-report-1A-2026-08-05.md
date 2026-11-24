# Phase report — 1A (Formal model)

**Date:** 2026-08-05
**Repository:** Research-paper-AEP (cloned this session from
`https://github.com/hafizmirhamza276-lab/Research-paper-AEP.git`, single commit
`91c8324 Initial import of AEP research paper project`)
**Executed by:** Claude Code session, effort level "max"

---

## A. Phase attempted and roadmap section reference

**Phase 1A — Formal model.**

- Roadmap section: `PAPER_ROADMAP.md` §1 ("The contribution statement"),
  specifically the fenced block "### Claude Code prompt — Phase 1A" at
  `PAPER_ROADMAP.md:41-50`, plus the surrounding requirements at
  `PAPER_ROADMAP.md:30-39` (contribution statement, properties P1–P3, and the
  non-claims requirement).
- Order-of-operations row: `PAPER_ROADMAP.md:153` ("1A Formal model | docs/22 |
  2–3 days").
- Deliverable required by the prompt: `docs/22-formal-model.md`.

No later phase was started. No CI, lockfile, packaging change, harness,
baseline, or manuscript work was performed (Phases 2A, 2B, 3, 4).

---

## B. Files created/modified

| File | Status | Purpose |
|---|---|---|
| `docs/22-formal-model.md` | **Created** (the Phase 1A deliverable) | System model, failure model, formal statements of P1/P2/P3 with per-property enforcement maps and declared residual windows, non-claims table, enforcement-gap list, evidence index. 202 distinct `file:line` citations across 18 files. |
| `reports/phase-report-1A-2026-08-05.md` | **Created** (this file) | The session report required by the task instructions. Creates the `reports/` directory. |

**Not created or modified by this phase, but changed in the working tree:**

| Path | Note |
|---|---|
| `.ai/track.md` | Written automatically by the installed SDLC plugin hook on each Write/Edit. Not an intentional deliverable of this phase. Content is a timestamped tool-activity log. |
| `PAPER_ROADMAP.md` | Present as an untracked file before this session's work began; supplied by the user, not authored here. |

No file under `src/`, `tests/`, `redis/`, `docs/01`–`docs/21`,
`pyproject.toml`, or `compose.phase2.yml` was modified. `git status --short`
at the end of the session (raw output in section C, CMD 10) shows exactly
`?? .ai/`, `?? PAPER_ROADMAP.md`, `?? docs/22-formal-model.md` — the report
file was written after that command.

---

## C. Raw command outputs

All commands were run from `D:/personal/AEP/Research-paper-AEP` in Git Bash on
Windows 11. Exit codes are echoed explicitly. `grep` exit code `1` means "no
match found", which for CMD 2–5 is the asserted result.

### CMD 0 — clone and baseline

```
$ git clone https://github.com/hafizmirhamza276-lab/Research-paper-AEP.git
Cloning into 'Research-paper-AEP'...

$ git log --oneline -3
91c8324 Initial import of AEP research paper project
```

### CMD 1–8 — consolidated evidence checks

```
$ cd "D:/personal/AEP/Research-paper-AEP" && set +e
### CMD 1: environment
Python 3.11.9
exit=0
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'pydantic'
exit=1
Docker version 29.4.3, build 055a478
exit=0

### CMD 2: no daemon entrypoint in src/
exit=1
### CMD 3: no console_scripts in pyproject.toml
exit=1
### CMD 4: ARGV[7] never used by the intent CAS Lua
exit=1
### CMD 5: POSITIVE_ONLY_READBACK absent from src/
exit=1
### CMD 6: capability read by duck typing + string literals
232:                getattr(config.connector, "reconciliation_capability", None),
236:            if capability == "NO_READBACK":
293:            elif result == "NOT_APPLIED" and capability == "AUTHORITATIVE_READBACK":
exit=0
### CMD 7: scan_once / run_forever have no exception handling
    async def scan_once(self) -> list[RecoveryResult]:
        """Perform one cursor-based SCAN pass with bounded concurrency."""

        now = await self.store.redis_time()
        candidates: list[tuple[str, str]] = []
        async for key in self.store.redis.scan_iter(
            match="aep:state:*", count=self.scan_count
        ):
            execution_id = key.removeprefix("aep:state:")
            state = await self.store.get_execution(execution_id)
            if state is None:
                continue
            for intent in state.intent_ledger.values():
                if self._eligible(intent, now):
                    candidates.append((execution_id, intent.intent_id))

        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def bounded(execution_id: str, intent_id: str):
            async with semaphore:
                return await self.recover_intent(execution_id, intent_id)

        results = await asyncio.gather(
            *(bounded(execution_id, intent_id) for execution_id, intent_id in candidates)
        )
        return [result for result in results if result is not None]
        while not stop.is_set():
            started = time.monotonic()
            await self.scan_once()
            elapsed = time.monotonic() - started
exit=0
### CMD 8: production dispatch gate
        # connector composition. Only an explicit test-only composition may
        # exercise dispatch; there is no feature flag that bypasses validation.
        if not self.allow_test_dispatch:
            raise WriteAheadWorkflowError(
                "production non-idempotent dispatch is disabled"
            )
        if not getattr(self.binding_service.vault, "test_only", False):
            raise WriteAheadWorkflowError(
                "test dispatch requires the explicit test-only request vault"
            )
        if not getattr(self.connector, "test_only", False):
            raise WriteAheadWorkflowError(
                "test dispatch requires an explicit test-only connector"
            )
exit=0
```

### CMD 9 — property anchor line numbers (used for the P1/P2/P3 citations)

```
$ grep -n "<P1/P2/P3 anchors>" src/core/*.py
--- P1 anchors ---
375:if redis.call('GET', KEYS[2]) ~= ARGV[2] then return -3 end
389:if not expected or current.version ~= expected or
390:   candidate.version ~= expected + 1 then return -1 end
581:redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[8])
585:_INTENT_CAS_SCRIPT = build_lua_state_validation_script(_INTENT_CAS_SCRIPT_BODY)
660:        self._intent_cas = redis_client.register_script(_INTENT_CAS_SCRIPT)
--- base CAS anchors ---
202:if redis.call("GET", KEYS[2]) ~= ARGV[4] then return -3 end
244:    if decoded.version ~= expected_version or incoming_version ~= expected_version + 1 then
266:redis.call("SET", KEYS[1], ARGV[1], "EX", ARGV[5])
421:        self._cas = self.redis.register_script(_CAS_SCRIPT)
--- P2 anchors ---
src/core/durability.py:192:                "WAITAOF", 1, 0, timeout_ms
src/core/durability.py:206:        return local_fsyncs >= 1
src/core/intent_workflow.py:310:            async with self.store.pinned_connection() as connection:
src/core/intent_workflow.py:332:                    await self._confirm_barrier(connection)
src/core/intent_workflow.py:351:                            await self._confirm_barrier(connection)
src/core/intent_workflow.py:382:                    async with self.store.pinned_connection() as connection:
src/core/intent_workflow.py:394:                        await self._confirm_barrier(connection)
src/core/intent_workflow.py:445:                response = await self.connector.mutate(
src/core/intent_workflow.py:490:            async with self.store.pinned_connection() as connection:
src/core/intent_workflow.py:510:                await self._confirm_barrier(connection)
--- P3 anchors ---
src/core/intent_workflow.py:57:    max_reconciliation_attempts: int = 8
src/core/intent_workflow.py:58:    max_reconciliation_duration_seconds: float = 24 * 60 * 60
src/core/intent_workflow.py:86:        if self.max_reconciliation_attempts <= 0:
src/core/intent_workflow.py:87:            raise ValueError("max_reconciliation_attempts must be positive")
src/core/intent_workflow.py:88:        if self.max_reconciliation_duration_seconds <= 0:
src/core/intent_workflow.py:90:                "max_reconciliation_duration_seconds must be positive"
src/core/intent_workflow.py:166:            policy.max_reconciliation_duration_seconds
src/core/intent_recovery.py:73:                config.policy.max_reconciliation_duration_seconds
src/core/intent_recovery.py:309:                exhausted = (
src/core/intent_recovery.py:310:                    attempts >= config.policy.max_reconciliation_attempts
src/core/intent_recovery.py:313:                    + config.policy.max_reconciliation_duration_seconds
src/core/intent_recovery.py:317:                    reason = "reconciliation-attempt-or-duration-limit"
exit=0
```

```
$ grep -n "return -7 end|return -6 end|risk_acceptance_id|unresolved_by_step" src/core/intents.py
475:    if current.status == 'PAUSED' then return -7 end
487:           record.status == 'PERMANENTLY_AMBIGUOUS' then return -7 end
496:    if has_value(new_record.risk_acceptance_id) then return -6 end
579:if next(unresolved_by_step) ~= nil and ttl < tonumber(ARGV[9]) then return -5 end
607:if type(intent.canonical_request_binding) ~= 'string' then return -6 end
613:if binding.request_binding_digest ~= ARGV[5] then return -7 end
```

```
$ grep -n "Executive verdict|...|fails closed" docs/07-phase2-gap-audit.md
15:## Executive verdict
17:Phase 2 is a useful fail-closed prototype, but it does **not** satisfy the
33:- recovery discovery is concurrency-bounded but not memory-bounded;
42:> Ambiguity, corruption, and contention are detectable; the system fails closed.
--- hld/design anchors ---
docs/01-hld.md:48:- **Single self-hosted instance**, no master-replica, no Sentinel, no Cluster mode.
docs/06-phase2-design.md:249:and repeat the preflight. Any other failure forbids dispatch. A scheduling gap
```

### CMD 10 — citation validator over the deliverable

Script run via `python - <<'PY' ... PY` (stdin; no file written to the repo).
It extracts every backticked `path:line` / `path:a-b` citation from
`docs/22-formal-model.md`, checks the file exists, and checks the range is
within the file's line count.

```
distinct citations checked: 202
distinct files cited: 18
  PAPER_ROADMAP.md: 169 lines
  compose.phase2.yml: 21 lines
  docs/01-hld.md: 460 lines
  docs/02-tech-design.md: 1289 lines
  docs/06-phase2-design.md: 440 lines
  docs/07-phase2-gap-audit.md: 661 lines
  redis/phase2.conf: 14 lines
  src/core/durability.py: 206 lines
  src/core/intent_recovery.py: 401 lines
  src/core/intent_workflow.py: 522 lines
  src/core/intents.py: 1069 lines
  src/core/locks.py: 432 lines
  src/core/request_binding.py: 1505 lines
  src/core/request_vault.py: 316 lines
  src/core/state_codec.py: 428 lines
  src/core/storage.py: 837 lines
  tests/mock_connector.py: 667 lines
  tests/test_phase2_waitaof_integration.py: 279 lines
invalid citations: 0
exit=0
```

**Scope of this check:** it proves no citation points outside a file's line
range. It does **not** prove semantic correctness of a citation. Semantic
correctness rests on my having opened and read every cited file in full during
this session (`src/core/*.py` — all 12 modules; `docs/01-hld.md`,
`docs/02-tech-design.md`, `docs/06-phase2-design.md`; `tests/conftest.py`,
`tests/mock_connector.py`; `redis/phase2.conf`, `compose.phase2.yml`,
`pyproject.toml`) plus the targeted greps above.

### Working-tree state

```
$ git status --short
?? .ai/
?? PAPER_ROADMAP.md
?? docs/22-formal-model.md
exit=0
```

### Commands NOT run, and why

- **`pytest` (the full suite) was not run.** The environment has Python 3.11.9;
  `pyproject.toml:9` requires `>=3.13`, and the runtime dependencies are not
  installed (CMD 1: `ModuleNotFoundError: No module named 'pydantic'`,
  exit=1). Installing a Python 3.13 toolchain and a lockfile is explicitly
  Phase 2A work (`PAPER_ROADMAP.md:58-63`), which Rule 1 forbids me from
  starting.
- **No Redis container was started**, no `docker compose -f compose.phase2.yml
  up`, no `WAITAOF` probe. Docker is available (CMD 1, exit=0) but running the
  integration suite is Phase 2A/2B work.
- **Consequently this report makes no claim whatsoever about test counts, pass
  rates, or coverage.** The "218 passing tests" figure quoted in
  `PAPER_ROADMAP.md:14` was **not** verified by this session and must not be
  treated as verified.

---

## D. Requirement checklist

Requirements are taken verbatim from the Phase 1A prompt block
(`PAPER_ROADMAP.md:42-50`) and from §1 (`PAPER_ROADMAP.md:30-39`).

| # | Requirement (source) | Status | Evidence |
|---|---|---|---|
| R0 | "Read `docs/01-hld.md`, `docs/02-tech-design.md`, `docs/06-phase2-design.md`, and `src/core/*.py`" (`:43`) | **DONE** | All four read in full this session: `docs/01-hld.md` (460 lines), `docs/02-tech-design.md` (1289), `docs/06-phase2-design.md` (440), and all 12 modules in `src/core/` (5,845 lines total, per `wc -l src/core/*.py`). Citations to all of them appear in `docs/22-formal-model.md` and are range-validated (CMD 10). |
| R1 | Write `docs/22-formal-model.md` (`:44`) | **DONE** | `docs/22-formal-model.md` created; see section B. |
| R1a | System model: **processes** (`:45`) | **DONE** | `docs/22-formal-model.md` §1.1, principal table citing `src/core/intent_workflow.py:118-522`, `src/core/intent_recovery.py:44-401`, `src/core/intents.py:644-1069`. Includes the finding that no supervisor/entrypoint exists (CMD 2, CMD 3, both exit=1). |
| R1b | System model: **single Redis 7.2 instance with AOF** (`:45`) | **DONE** | §1.2, citing `redis/phase2.conf:11-12` (`appendonly yes` / `appendfsync everysec`), `compose.phase2.yml:5` (digest-pinned `redis:7.2.5-alpine`), `docs/01-hld.md:48`; keyspace table citing `src/core/intents.py:938`, `src/core/storage.py:501`, `src/core/locks.py:149-152`, `src/core/storage.py:784-822`. |
| R1c | System model: **network** (`:45`) | **DONE** | §1.3: connection pinning requirement and its call sites (`src/core/intents.py:663-668`; `src/core/intent_workflow.py:310,382,490`; `src/core/intent_recovery.py:209,370`), and the typed-failure mapping for transport faults. |
| R1d | System model: **clocks, no synchrony assumption beyond lease TTLs** (`:45`) | **DONE** | §1.4 time-source table: Redis `TIME` (`src/core/intents.py:670-673`), Redis expiry/`PTTL` (`src/core/locks.py:152`, `src/core/intents.py:598-599`), process-local `monotonic` (`src/core/locks.py:350-357,406-420`; `src/core/request_binding.py:1191,1241`). Includes the verified finding that the client wall-clock argument `ARGV[7]` (`src/core/intents.py:948`) is never read by the Lua (CMD 4, exit=1), i.e. no client wall clock enters the authoritative write path. |
| R1e | System model: **external legacy API with response classes `AUTHORITATIVE_READBACK` / `POSITIVE_ONLY_READBACK` / `NO_READBACK`** (`:45`) | **DONE, with a material honest finding** | §1.5. Design contract cited at `docs/06-phase2-design.md:345-369`. The document records that the enum exists **only** in `tests/mock_connector.py:41-46`, that `src/core/` compares bare string literals via `getattr` (`src/core/intent_recovery.py:231-236`, `:293`, CMD 6), and that `POSITIVE_ONLY_READBACK` appears nowhere in `src/` (CMD 5, exit=1). |
| R2a | Failure model: **worker crash (SIGKILL) at any instruction boundary** | **DONE for the model; the repo's realisation is PARTIAL and labelled as such** | §2 F1: 22 named crash points (`tests/mock_connector.py:67-129`) and every hook call site enumerated. Explicitly states that crashes are simulated **in-process** (`CrashStyle`, `SimulatedProcessCrash` at `tests/mock_connector.py:132-137,167-179`) and that **no OS-level `SIGKILL` of a separate process exists in the repository**, deferring that to Phase 2B (`PAPER_ROADMAP.md:87`). |
| R2b | Failure model: **network partition worker↔Redis** | **DONE for the model; NOT SIMULATED in the repo, and said so** | §2 F2, with the typed-failure citations and the note that no proxy/`tc netem`/toxiproxy exists (Phase 2B, `PAPER_ROADMAP.md:112`). |
| R2c | Failure model: **Redis restart with AOF replay** | **DONE for the model; NOT TESTED in the repo, and said so** | §2 F3, citing `redis/phase2.conf:12`, `docs/02-tech-design.md:1214-1216`, `src/core/durability.py:181-206`; includes the derived finding that lock keys are **not** covered by the barrier (`src/core/locks.py:119-240`), which becomes residual R1-3. |
| R2d | Failure model: **delayed/duplicated external responses** | **DONE for the model; duplicate-response mode absent from the harness, and said so** | §2 F4, citing `tests/mock_connector.py:36-38,151-161,483-493,597-599` and `src/core/intent_workflow.py:478-487`. |
| R2e | Failure model: **worker pause (GC/VM stall) past lease expiry** | **DONE** | §2 F5: preflight (`src/core/intents.py:597-613`), heartbeat cancellation and caps (`src/core/locks.py:364-375,394-404,406-420`), CAS rejection, plus the irreducible residual quoted from `docs/06-phase2-design.md:249-252`. |
| R3 | **P1 stated formally, mapped to the exact Lua/code path, with declared residual window** | **DONE** | §3.1: enforcement table (`src/core/intents.py:375`, `:387-390`, `:581`; `src/core/storage.py:202`, `:244`, `:266`; registration `:660`/`:421`; invocation `:936-956`/`:505-514`; typed rejections `:967-976`/`:527-546`), plus residuals R1-1 … R1-6. |
| R4 | **P2 stated formally, mapped to the exact Lua/code path, with declared residual window** | **DONE** | §3.2: ordering A (`src/core/intent_workflow.py:264,270-274,286-307,310-332,362-375,400-438,445`), barrier B (`src/core/durability.py:142-169,181-206`), runner classification C (`:449-487`), recovery classification table D (`src/core/intent_recovery.py:236-336`), no-replay E (`src/core/intents.py:59-90,439-451,475,485-487,497-499,880-885`), no-loss F (`src/core/intents.py:563-578,532-539`). Assumptions A1–A4 and residuals R2-1 … R2-7 stated explicitly. |
| R5 | **P3 stated formally, mapped to the exact Lua/code path, with declared residual window** | **DONE** | §3.3: budgets (`src/core/intent_workflow.py:57-58,86-91,105-111`), termination test quoted from `src/core/intent_recovery.py:309-318`, monotone attempt counting re-checked in Lua (`src/core/intents.py:546-553`), ejection (`src/core/intent_recovery.py:89-96`; `src/core/intents.py:880-885,475,485-487`), retention floor (`src/core/intent_workflow.py:165-172`; `src/core/intent_recovery.py:71-79`), residuals R3-1 … R3-6. |
| R6 | **Table of non-claims with the reason each is out of scope** (`:48`) | **DONE** | §4: 12 rows (NC-1 … NC-12), each with a citation. Covers the four the roadmap names explicitly at `PAPER_ROADMAP.md:39` — no exactly-once (NC-1), no split-brain immunity (NC-3), no HA/consensus (NC-3), single-Redis trust domain (NC-4) — plus eight more grounded in `docs/06-phase2-design.md:387-413`. |
| R7 | **"Do not overstate."** (`:49`) | **DONE, and enforced structurally** | §0 rule 2 and §5 ("Enforcement gaps: designed but not enforced in `src/core/`") list six gaps with citations. Every property carries explicit assumptions and residual windows; §1.6 and residual R2-7 label the write-ahead ordering as *path discipline*, not an invariant. §1.7 records that dispatch is disabled outside a test-only composition (CMD 8). |
| R8 | **"Every property must cite the enforcing file:line."** (`:49`) | **DONE** | 202 distinct citations, 0 out of range (CMD 10). |
| R9 | Properties stated **as given in `PAPER_ROADMAP.md` §1** (`:47`) | **DONE** | §3.0 maps the roadmap's CONFIRMED / REFUTED / PERMANENTLY_AMBIGUOUS vocabulary (`PAPER_ROADMAP.md:36`) onto the code's `FIRED_CONFIRMED` / `FAILED_CONFIRMED` / `PERMANENTLY_AMBIGUOUS` (`src/core/intents.py:47-52`). |

**No requirement of this phase is NOT DONE or BLOCKED.**

---

## E. Deviations from the roadmap

1. **Two sections were added beyond the four the prompt requires.**
   `docs/22-formal-model.md` §5 ("Enforcement gaps") and §6 ("Evidence index").
   Rationale: §5 is required by Rule 5 of the session instructions ("If the
   code does not enforce a property, write that it does not") and separating it
   from the per-property residual windows keeps the distinction between
   *inherent protocol limits* (residuals) and *implementation debt* (gaps).
   §6 exists so the promised independent re-audit has a single index to work
   from. Neither section changes or softens any required content.

2. **The roadmap's phrase "ejects to operator escalation" (P3,
   `PAPER_ROADMAP.md:37`) was narrowed rather than restated.** The code has no
   alerting or incident path; it only reaches a terminal automated state and
   sets the execution to `PAUSED`. The document states this in §3.3 (R3-4) and
   §5.4 rather than repeating the roadmap's wording, because repeating it
   verbatim would overstate the implementation.

3. **The formalisation is structured prose with explicit predicates, not TLA+
   or another machine-checkable notation.** *This is a design decision the
   roadmap left open.* Alternatives considered: (a) a TLA+ module; (b)
   Alloy; (c) Hoare-style pre/post-conditions per function. Chosen (d)
   structured prose + assumption lists + residual-window lists. Rationale:
   `PAPER_ROADMAP.md:123` schedules formal-methods work as Phase 3A, and Rule 1
   forbids starting a later phase; producing a half-checked TLA+ spec now would
   invite exactly the overclaiming Rule 5 warns about. The prose model is
   written so a Phase 3A spec can be derived mechanically from §3.

4. **Test files were read and cited, although the prompt names only
   `src/core/*.py` and three design docs.** `tests/mock_connector.py` had to be
   read because the three reconciliation response classes the prompt requires
   me to model exist *only* there (CMD 5). Citing it is necessary to state
   where the contract actually lives. `tests/conftest.py` and
   `tests/test_phase2_waitaof_integration.py` were read for the environment and
   marker facts in §2 F3.

5. **A `reports/` directory was created.** Required by the session
   instructions; it did not exist in the cloned repository.

---

## F. Known weaknesses, shortcuts, and what a hostile reviewer would attack

This section is deliberately adversarial against my own output.

**F1. The model describes a system that cannot currently run in production
mode at all.** `WriteAheadRunner.validate_startup` hard-fails unless the
composition is test-only (`src/core/intent_workflow.py:188-199`, CMD 8): a
test-only in-memory vault (`src/core/request_vault.py:191-195`) and a
`test_only` connector are mandatory. A reviewer is entitled to ask what P1–P3
mean for a protocol whose only executable configuration is a test harness.
The honest answer, which the paper must give: the *mechanisms* (Lua CAS,
WAITAOF barrier, transition table) are real and are what the evaluation will
measure; the *deployment* is not. I stated this in §1.7 but it deserves to be
a threats-to-validity paragraph, not a footnote.

**F2. P2 and P3 are conditional, and one of the conditions is currently
violated by a real defect.** `scan_once` has no exception handling: a
`StateCorruptionError` from `get_execution` (`src/core/intent_recovery.py:107`;
raised at `src/core/intents.py:686-693`), or any exception from
`recover_intent` inside `asyncio.gather` called without
`return_exceptions=True` (`:120-122`), propagates out of `run_forever`
(`:138`), whose call is unguarded (CMD 7). One poisoned execution — or one
intent whose `connector` string has no registered config (`:184-188`) —
terminates reconciliation for the **entire keyspace**. A hostile reviewer will
find this in ten minutes and will say the "fail-closed liveness bound" is
unenforced in the failure mode that matters most. I did not fix it: it is a
`src/` change, which Rule 6 places outside Phase 1A. It is written up as §5.3
and as assumption A2 / residual R3-1, and is escalated in section G.

**F3. "Every external side effect is preceded by a durably-acknowledged
write-ahead intent" is not an invariant of the system; it is a property of one
function.** It holds along `WriteAheadRunner.execute`. Nothing prevents a
different caller from composing `RequestBindingService.verify` with a connector
directly, and nothing makes the WAITAOF acknowledgement a *precondition* of
minting dispatch authority — the capability object
(`src/core/request_binding.py:1489-1503`) is derived from the persisted
binding, not from the fsync acknowledgement. Additionally, single-use
enforcement depends on the connector calling `consume_verified_dispatch`
(`tests/mock_connector.py:412-422`); a connector that ignores it can call the
provider anyway. I labelled this "path discipline" (§1.6, R2-7) rather than
claiming an invariant, but a reviewer may still regard the roadmap's
contribution statement (`PAPER_ROADMAP.md:32`) as stronger than the code.

**F4. The three response classes are a test-only construct.** `src/core/`
never validates a capability declaration; `POSITIVE_ONLY_READBACK` is not
referenced anywhere in `src/` (CMD 5). The correct behaviour for a
positive-only connector emerges as a *fall-through* on
`src/core/intent_recovery.py:293` rather than from a checked contract. A
reviewer can reasonably say the paper's response-class taxonomy is currently a
property of the mock, not of the protocol implementation.

**F5. P1 is a statement about one Redis timeline and is not robust to AOF
rewind.** Lock keys are ordinary writes with no fsync barrier
(`src/core/locks.py:119-240`), so an AOF rewind (F3) can restore a lease whose
release was lost while also rewinding `version`. A worker that was correctly
fenced before a restart can satisfy both CAS conjuncts afterwards. I recorded
this as R1-3. It is an argued consequence of the code and configuration, **not
something I reproduced** — no Redis restart test exists and I ran none. A
reviewer should treat R1-3 as a reasoned hypothesis pending a Phase 2B
experiment, and I have not marked it as demonstrated.

**F6. P1 constrains two code paths, not the datastore.** Redis runs with
`protected-mode no`, no ACL (`redis/phase2.conf:3-4`); confinement is a
loopback port mapping (`compose.phase2.yml:9`). "Only the CAS may write
`aep:state:*`" is a documentation rule (`docs/02-tech-design.md:1156`). Any
process reaching the socket voids P1 (R1-1, NC-4).

**F7. Fail-closed becomes fail-forgotten after the retention window.** A
`PERMANENTLY_AMBIGUOUS` intent receives no further writes, so the state key
expires at the TTL set by its last write (`src/core/intents.py:581`). The
31-day floor at `src/core/intents.py:579` only applies while an `ABOUT_TO_FIRE`
or `FIRED_UNCONFIRMED` intent exists, and `PERMANENTLY_AMBIGUOUS` is not in
`UNRESOLVED_INTENT_STATUSES` (`:55-57`). Absent operator action, the escalated
record is deleted by Redis. Recorded as R3-5. I have **not** empirically
confirmed expiry behaviour; it follows from reading the Lua `SET ... EX` and
the status set.

**F8. Nothing in this phase was executed.** No test ran, no Redis started, no
Lua was evaluated. Every claim in `docs/22-formal-model.md` is a claim about
*source text I read*, not about *observed behaviour*. The citation validator
(CMD 10) checks only that line ranges exist. If a Lua branch is unreachable in
practice, or if `redis-py`'s `register_script` behaves differently than the
code assumes, this document would not catch it. Phase 2B is what turns these
into empirical claims.

**F9. Coverage of `src/core/request_binding.py` is shallow.** It is the largest
module (1,505 lines) and I read it in full, but the formal model treats the
binding/commitment machinery as a black box with three properties
(unforgeable, single-use, re-verified). I did not model the HMAC commitment
construction, the canonical-JSON subset, or the vault AAD, and I make no
security claim about them. A security-focused reviewer would find the model
thin here. This is a deliberate scope choice — those are confidentiality
properties, not the ambiguity properties P1–P3 — but it is a gap.

**F10. Line numbers are brittle.** All 202 citations are keyed to the current
single-commit tree. Any edit to `src/core/` invalidates them silently. There is
no anchor mechanism (e.g. citing symbol names alongside lines) and no CI check
that re-runs the validator.

---

## G. Open questions needing a human/architect decision

1. **Is the recovery-loop fault-isolation defect (F2/§5.3) a Phase 2A bug fix,
   a separate hotfix, or an intentional finding to publish?** It materially
   weakens P3. Options: (a) fix now, before any experiment, so the harness
   measures the intended protocol; (b) fix in Phase 2A alongside CI; (c) leave
   it and report the pre-fix behaviour as a motivating result. My conservative
   recommendation is (a) — a fault-injection harness that trips this defect
   will produce results that describe a bug, not the protocol — but this is
   your call, and Rule 1/6 stopped me from touching `src/`.

2. **Should the three reconciliation response classes be promoted from
   `tests/mock_connector.py` into `src/core/` as a validated declaration
   (enum + registry + startup validation)?** Until then, the paper's taxonomy
   is a mock-level construct (F4). This is a `src/` change and therefore
   outside Phase 1A.

3. **What is the paper's stance on the test-only dispatch gate (F1)?** Either
   (a) present AEP as a research prototype and say so in the abstract, or
   (b) build a minimally credible non-test composition before evaluation. This
   choice changes what Phase 2B must build.

4. **Should P3's "ejects to operator escalation" be implemented (an alert
   hook) or should the property be permanently restated as "reaches a terminal
   automated state and pauses the execution"?** I chose the latter wording for
   the model; changing the code would change the property statement.

5. **Retention semantics for escalated records (F7).** Should
   `PERMANENTLY_AMBIGUOUS` be added to the set that forces the 31-day TTL
   floor, or should escalation be exported to durable storage outside Redis?
   As written, fail-closed evidence is garbage-collected.

6. **Is R1-3 (AOF rewind can un-fence a lease) worth a dedicated Phase 2B
   experiment?** It is currently a reasoned hypothesis. If it reproduces, it is
   a genuinely publishable result about single-instance lease + CAS designs; if
   it does not, the model should be corrected.

7. **Formalisation depth.** Do you want Phase 3A to produce a TLA+ spec of the
   transition table and P1/P2, or is the structured-prose model plus the
   Phase 2B empirical matrix sufficient for the target venue? This affects how
   §3 should be refactored.

---

## H. Recommended next phase and its prerequisites

**Recommended next phase: 2A — "Make the artifact evaluation-grade"**
(`PAPER_ROADMAP.md:54-75`).

Rationale: Phase 2B (the harness, `PAPER_ROADMAP.md:79-117`) is the heart of
the paper, but every number it produces is worthless without a reproducible,
non-lying environment. This session established that the environment cannot
currently run the suite at all (CMD 1), which is precisely the Phase 2A
problem.

**Prerequisites before starting 2A:**

1. **Python 3.13 toolchain.** Present: 3.11.9 (CMD 1). `pyproject.toml:9`
   requires `>=3.13`. Needed for any test execution.
2. **Runtime dependencies installed** (`redis`, `pydantic`, `cryptography`) and
   dev extras (`pytest`, `pytest-asyncio`, `fakeredis[lua]`) —
   `pyproject.toml:10-21`. Currently absent (CMD 1, exit=1).
3. **Redis 7.2 with AOF reachable.** Docker is available (CMD 1, exit=0);
   `compose.phase2.yml` pins the image by digest and publishes
   `127.0.0.1:6381`. Tests select the backend from `REDIS_URL` and require
   DB 15 unless overridden (`tests/conftest.py:37-58`, `:105-139`).
4. **A decision on open question G.1** (fix the recovery fault-isolation defect
   now or later), because Phase 2A's CI gate will otherwise codify the current
   behaviour.
5. **Baseline test inventory.** Phase 2A must record the *actual* raw pytest
   summary. The "218 tests" figure in `PAPER_ROADMAP.md:14` is unverified by
   this session and should be treated as a claim to be checked, not a
   established fact.

**Explicitly deferred to 2B** (do not attempt in 2A): separate-process
`SIGKILL` injection, `docker pause`/`restart`, toxiproxy partitions, and the
mock legacy API with a ground-truth ledger — i.e. the empirical evidence that
would turn residuals R1-3, R2-1, R2-3 and R3-1 from reasoned claims into
measurements.
