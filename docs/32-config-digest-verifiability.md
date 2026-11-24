# Every run's configuration verifies against its own digest

**Phase 13, 2026-09-03.** Instrument: `scripts/audit_config_digests.py`. Raw:
`reports/raw/phase13-config-digest-generations.{txt,json}`,
`reports/raw/phase13-digest-gate-proof.txt`.

**All 432 runs of the frozen evaluation verify.** This document is how that was
established, and what it does and does not license.

---

## 1. The question

Each run records a `config_digest`: a SHA-256 over every `RunConfig` field that
could change a number (`experiments/harness/config.py`, `run_id`,
`results_root` and the derived `resolved_crash_point` excluded). It exists so
that a run's recorded configuration can be shown to be the one it was collected
under.

Re-reading the frozen collections through `run_config_from_mapping` found **150
of the 432 `matrix` runs failing that check**, all missing the same four fields:
`redis_kill_point`, `redis_kill_delay_ms`, `redis_kill_executions` and
`suspend_disabled_declared`.

That is *consistent with* schema evolution — `RunConfig` grew and the digest is
computed over the current field set — but "consistent with" is not "explained
by", and the two possibilities are very far apart:

| | meaning |
|---|---|
| **explained by schema evolution** | the stored digest is exactly what that run's own generation would produce. Nothing was altered; the verifier was asking the wrong question. |
| **anything else** | a stored digest matching *no* generation means the recorded configuration and its digest disagree for a reason this repository cannot account for. |

**Determining which was the whole point.** It was not assumed.

## 2. Method: reconstruct the field sets, do not recompute the digests

`scripts/audit_config_digests.py`:

1. reads every historical version of `experiments/harness/config.py` from git;
2. extracts `RunConfig`'s field names **with `ast`, not a regex** — an
   `AnnAssign` walk over the class body. A regex over `name: type` would miss
   fields introduced by a conditional or inherited, and a wrong field set here
   would silently produce a wrong verdict;
3. for each run and each generation, rebuilds the body **from the values the run
   actually recorded**, restricted to that generation's fields, and recomputes
   the digest with the project's own function;
4. asks whether any generation reproduces the **stored** digest exactly.

> **It never writes a digest.** Recomputing and storing one would destroy the
> only property a digest has: that it was computed before anyone had a reason to
> want a particular answer. No stored byte was altered, and the raw trees were
> re-verified against `MANIFEST.sha256` afterwards — 26 299 files, unchanged.

## 3. Result: three generations, zero unexplained

```
RunConfig field-set generations found in git history: 3
  e67efd1f 2026-08-27   42 fields  <- current
  9154d85a 2026-08-06   38 fields
  2fefe5e5 2026-08-05   35 fields

verdicts
    288  VERIFIES AGAINST THE CURRENT SCHEMA
    150  EXPLAINED BY SCHEMA GENERATION

by root
  b2-2026-08-21                        {'current': 60}
  b2-paired-v2-s1-2026-08-28           {'current': 120}
  fsync-always                         {'current': 6}
  matrix                               {'EXPLAINED BY SCHEMA GENERATION': 150, 'current': 282}

failures explained, by the generation that reproduces them
    150  9154d85a

NONE UNEXPLAINED
```

**All 150 are reproduced exactly by generation `9154d85a`** — the 38-field
schema of 2026-08-06, which is when those runs were collected. The 282 `matrix`
runs that verify against today's schema are the ones collected after the E1 and
E5 fields existed. Every other root verifies against the current schema
throughout.

> **Every stored digest in the corpus is reproduced by the field set in force
> when its run was collected. None is unexplained.** That is positive evidence
> that no configuration was altered after collection — evidence that is stronger
> for having survived a schema the project evolved twice mid-evaluation, because
> an altered field would have had to match a historical generation it was never
> written under.

**An ambiguity check, because the argument needs one.** If two generations could
both reproduce a run's digest, a field could be altered and still be "explained"
by a generation that did not contain it. The audit reports that case as
`AMBIGUOUS` and exits non-zero. It does not occur: the generations differ by
fields present in every document that carries them.

## 4. The gate, and both failure modes demonstrated

A check whose failure has never been seen has not been tested. Both modes the
check will be claimed to catch were induced on **copies**, against the real
corpus (`reports/raw/phase13-digest-gate-proof.txt`):

| case | induced | result |
|---|---|---|
| **0. the real thing** | — | `NONE UNEXPLAINED`, 12 examined, **exit 0** |
| **(a) a stored digest matching no generation** | `config_digest` set to 64 zeroes | `UNEXPLAINED (1)`, **exit 1** |
| **(b) contents altered, digest left untouched** | `durability_timeout_ms` 2000 → 2001 | `UNEXPLAINED (1)`, **exit 1** |
| **(c) nothing to check** | an empty root | `GATE FAILED: examined 0 run configs`, **exit 2** |

(b) is the one that matters, and the field was chosen deliberately: the barrier
timeout is the quantity the entire prevention result turns on. (c) exists
because a digest check that silently examines nothing reports a clean pass,
which is the one outcome it must never produce — hence `--require-runs`.

The clean copies were unchanged before and after, and the real trees still
verify against the archive manifest.

### Where the gate lives, and why not in CI

It runs as **step 5 of `scripts/verify_published_archive.py`**, over the
unpacked archive, with `--require-runs 1000`.

It is deliberately **not** a CI job over the tracked roots. The raw run
directories are gitignored, so a CI job would find **zero** `run-config.json`
files and report a clean pass over nothing — the definition of decoration, and
the reason the archive-verification job was already deferred rather than added
empty. The archive is the only place the check has anything to check, and it is
where a reviewer meets it.

## 5. What this proves, and what it does not

Repeated in `ARTIFACT.md` §5, where a reviewer running the check will meet it.

**It proves** that each run's recorded configuration is the one its digest was
computed over, under the field set in force at collection time. A field altered
afterwards is caught; a digest matching no generation is caught.

**It is a tamper check, not a correctness check.** It says nothing about whether
the configuration was the right one, whether the fault it names was actually
delivered, or whether the run measured what it intended to. Those are the jobs
of the fault-injection census, the run-level oracle reconciliation, and the
per-cell run counts in `MANIFEST.csv`. In exactly the way
`scripts/validate_citations.py` proves citation *ranges* are valid and not that
the semantics are right, this proves the configuration is *unaltered* and not
that it was *correct*.

**What independently corroborates the configurations beyond the digest**, and
matters because no single check should carry this alone:

* the **ground-truth ledger** is written by the mock provider in a separate
  process and reconciled per run, so a run whose configuration did not describe
  what it did would disagree with its own oracle;
* **`MANIFEST.csv`** records run counts per cell keyed the way the paper quotes
  them, produced by `scripts/freeze_results.py` through the same `load_run` the
  analysis uses, so the counts and the CSVs cannot disagree;
* the **fault-injection census** in the Phase-8.4 roots records what was
  actually injected rather than what was configured.

## 6. The one consequence for future work

`RunConfig._body()` iterates every dataclass field into the digest, so **adding
a field changes the digest of every run ever collected**. Generation-aware
verification absorbs that — a future generation is one more entry in the history
the audit already walks — but it means a new field is a schema event, not a
free change, and anything that only needs to be *recorded* belongs in the
`environment` block, which `echo()` writes and the digest excludes. That is the
route Phase 8.2 used for `results_root_filesystem`, Phase 10 for
`docker_kill_latency`, and Phase 13 for `redis_fault_mechanism`.
