# The filesystem hypothesis for the prevention result's between-session spread

**Phase 12, step 3. 2026-09-03.** A standalone document, because the next phase
builds on it directly.

**Nothing was collected. No frozen cell was re-analysed. `\UnwantedPrevented` was
not touched.** Every count below is read out of an existing
`redis-kill-ablation.csv` exactly as `scripts/paper_tables.py` reads it.

Instruments: `scripts/filesystem_fingerprint.py`,
`scripts/prevention_session_crosstab.py`. Raw:
`reports/raw/phase12-filesystem-fingerprint.{txt,json}`,
`reports/raw/phase12-prevention-crosstab.{txt,json}`.

---

## The hypothesis, as issued

> The 4–20/30 spread in AEP-full's unwanted-applied count across the five
> sessions, which Phase 9C recorded as over-dispersion 5.37 and left
> unexplained, is partly or wholly explained by the `results_root` filesystem
> differing between sessions.

Its mechanism is specific and plausible. `EventLog.emit` does
`json.dumps` + `write` + **`flush()`** — a real syscall — and Phase 8.1 §E.3
measured it on both of this host's filesystems:

| filesystem | median | p95 | max |
|---|---|---|---|
| ext4 (WSL native) | **5.4 µs** | 11.3 µs | 212.5 µs |
| drvfs (`/mnt/…`, 9p onto NTFS) | **229.7 µs** | 371.9 µs | 2 276.8 µs |

**~40×**, paid once per record, inside the runs. AEP-full dispatches **iff**
`WAITAOF` returns before the kill lands, so anything that systematically shifts
the worker's timing shifts where a session sits in that race.

---

## 1. Determining each session's filesystem

`docs/28-storage-backing-recovery.md` left the four 2026-08-21 sessions
**UNDETERMINED**: no `environment` block, no absolute path in any artifact, and
an inode event on 2026-09-01 that removed the `ctime` evidence. The prompt asked
what evidence would determine them and whether it still exists.

**It does, and it is the collections' own event logs.**

If the append costs 5 µs on one filesystem and 230 µs on the other, then the gap
between two `monotonic_ns` stamps written back-to-back carries that cost. Over
tens of thousands of pairs the *low quantiles* of the inter-record gap
distribution are dominated by the emit. That is a measurement **made by the
collection, at collection time** — `docs/28` class 2, the only class able to
determine anything where no field was recorded.

### Calibrated before use, on a control the project already owns

Phase 10 collected the same cell twice on the same day, on the same host, with
the same harness — once on ext4 and once on drvfs — and **every run config in
both arms records its filesystem**. Positive and negative control, free.

```
arm                           runs     gaps       p01       p05       p10    median
ext4  ext4-2026-09-02           18     4505      13.8      57.7      72.8    4919.3
ext4  ext4-2026-09-02-arbb30    30     7160      42.4      57.2      72.4    8813.0
drvfs replication-drvfs         18     4374     102.5     214.0     285.7    4160.3
drvfs replication-drvfs-arbb30  30     7159     204.6     282.8     348.5   15461.0

SEPARATED AT ROOT LEVEL: every ext4 root's pooled p05 is below 57.7 us and
every drvfs root's is above 214.0 us. Threshold 135.8 us.
  Run level does NOT separate: ext4 runs reach 110.2 us and drvfs runs start at
  104.9 us. So this classifies a COLLECTION, never a run.
```

**The run-level limit is stated because it is real.** Individual runs overlap;
only pooled over a collection does the signal separate. Every verdict below is
therefore about a collection, and the fingerprint cannot be used to classify a
single run.

### Validated on five roots it never saw

The five Phase-8.4 collections record their filesystem in their own
`environment` blocks, and were not used to set the threshold:

```
root                                      runs      p01      p05    verdict       known  agrees?
matrix (432, incl. the paper's kill cell)  432     16.1     38.8       ext4           -
b2-2026-08-21 (P9C s0)                      60    345.0    472.7      drvfs           -
b2-s1-2026-08-21 (P9C s1)                   60    270.8    397.2      drvfs           -
b2-s2-2026-08-21 (P9C s2)                   60    270.9    392.2      drvfs           -
b2-s3-2026-08-21 (P9C s3)                   60    278.8    386.5      drvfs           -
b2-paired-s1-2026-08-28                    120     59.5    109.8       ext4        ext4  YES
b2-paired-v2-s1-2026-08-28                 120     54.4     90.3       ext4        ext4  YES
b2-paired-v2-s2-2026-08-28                 120     51.3     94.0       ext4        ext4  YES
b2-paired-v2-s3-2026-08-28                 120     54.0     94.5       ext4        ext4  YES
b2-paired-v2-s4-2026-08-28                 120     47.2     78.8       ext4        ext4  YES
fsync-always                                 6     46.3     54.0       ext4           -

Held-out validation: 5/5 roots whose filesystem IS recorded are classified
correctly by a threshold calibrated only on the Phase 10 pair.
```

**The four unknown sessions come out `drvfs`, at 386–473 µs — 2.8–3.5× the
threshold and above even the drvfs calibration.** The comparison that carries
the most weight is `b2-paired-*` against `b2-*-2026-08-21`: **same regime, same
cell shape, same fault** — 79–110 µs against 386–473 µs, a factor of four.

Date and harness version are controlled about as well as retrospective evidence
allows: ext4 collections from **four different dates** (2026-08-06, 08-07,
08-28, 09-02) with different harness versions all land at 38–110 µs. Only the
08-21 roots land at 386–473 µs.

### Confidence, and why it is not DETERMINED

| root | before | after | basis |
|---|---|---|---|
| `matrix` | INFERRED ext4 | **INFERRED ext4**, now corroborated | traceback + ctime + fingerprint 38.8 µs |
| `b2-2026-08-21` | **UNDETERMINED** | **INFERRED drvfs** | fingerprint 472.7 µs |
| `b2-s1-2026-08-21` | **UNDETERMINED** | **INFERRED drvfs** | fingerprint 397.2 µs |
| `b2-s2-2026-08-21` | **UNDETERMINED** | **INFERRED drvfs** | fingerprint 392.2 µs |
| `b2-s3-2026-08-21` | **UNDETERMINED** | **INFERRED drvfs** | fingerprint 386.5 µs |

**INFERRED, not DETERMINED**, and the rule is `docs/28`'s: an inference is never
promoted, however good. This one passes through a calibrated classifier and
carries three residual confounds — collection date, harness version and host
load are not held fixed, and the 08-21 values sit *above* the drvfs calibration
rather than on it, which the classifier does not explain.

It does, independently, agree with what
`reports/phase-report-8-1-0-2026-08-27.md:296-299` asserted without sourcing —
and which Phase 11 recorded as finding F3 for exactly that reason. Two
independent routes to the same answer, one of them now a measurement.

---

## 2. The cross-tabulation

`redis-kill-preack` × `NO_READBACK`, the cell the prevention result is about.
`AEP` and `B3` are `executions_with_an_applied_effect` out of 30.

| session | fs | AEP | B3 | B3−AEP | kill latency ms (n / median) | append p05 µs |
|---|---|---|---|---|---|---|
| `matrix` (the paper's cell) | **ext4** | **10**/30 | 28/30 | 18 | not recorded | 38.8 |
| `b2-2026-08-21` (P9C s0) | **drvfs** | **20**/30 | 28/30 | 8 | not recorded | 472.7 |
| `b2-s1-2026-08-21` (P9C s1) | **drvfs** | **12**/30 | 28/30 | 16 | not recorded | 397.2 |
| `b2-s2-2026-08-21` (P9C s2) | **drvfs** | **4**/30 | 28/30 | 24 | not recorded | 392.2 |
| `b2-s3-2026-08-21` (P9C s3) | **drvfs** | **7**/30 | 28/30 | 21 | not recorded | 386.5 |
| `b2-paired-s1-2026-08-28` | **ext4** | **13**/30 | 28/30 | 15 | 120 / 1138.8 | 109.8 |
| `b2-paired-v2-s1-2026-08-28` | **ext4** | **18**/30 | 28/30 | 10 | 120 / 1046.7 | 90.3 |
| `b2-paired-v2-s2-2026-08-28` | **ext4** | **18**/30 | 28/30 | 10 | 120 / 1096.4 | 94.0 |
| `b2-paired-v2-s3-2026-08-28` | **ext4** | **10**/30 | 28/30 | 18 | 120 / 1053.5 | 94.5 |
| `b2-paired-v2-s4-2026-08-28` | **ext4** | **12**/30 | 28/30 | 16 | 120 / 976.8 | 78.8 |

Two things to note before the verdict.

**B3 is 28/30 in every one of the ten sessions.** The arm with no barrier is
invariant across both filesystems, both fault regimes' hosts, four weeks and two
container runtimes. That is a strong internal control: whatever moves AEP-full's
count is acting through the barrier, not through the harness, the provider or the
oracle.

**Kill latency is recorded for the five Phase-8.4 sessions and for none of the
others.** `redis_kill_latency_ms` was added to `per-execution.csv` after the
earlier collections were frozen. Its absence is "not recorded", never "zero" —
so the latency column cannot enter any comparison spanning both groups.

---

## 3. Do the filesystems vary? **Yes.**

**Four sessions drvfs, six ext4.** The hypothesis is not dead from a lack of
variation, and the step does not stop here.

## 4. Does the variation align with the count variation? **No.**

```
drvfs  n=4  values [4, 7, 12, 20]              range  4-20  median  9.5
ext4   n=6  values [10, 10, 12, 13, 18, 18]    range 10-18  median 12.5

ranges OVERLAP: drvfs 4-20 against ext4 10-18
```

* The drvfs range **contains** the ext4 range entirely.
* The medians differ by **3 points** against within-group spreads of **16**
  (drvfs) and **8** (ext4).
* The direction is **opposite** to the naive prediction: the slower filesystem
  has the *lower* median count.
* **The spread survives inside the ext4 group, where the filesystem is constant
  and DETERMINED from recorded fields.** Six sessions, all ext4, still range
  10–18. Whatever produces the between-session spread is present when the
  filesystem is held fixed.

That last point is the one that matters, and it does not depend on the
fingerprint being right. Even if every `drvfs` verdict in §1 were wrong, the
ext4 group alone — five of whose six memberships are recorded rather than
inferred — spans 10–18 out of 30.

### Verdict

> **The filesystem varies across the prevention sessions, and the variation does
> not align with the counts. The hypothesis is not refuted, but it is demoted:
> the filesystem cannot be the whole explanation, and on this evidence it is not
> visibly part of one.**

Stated with its n: **4 sessions against 6.** Four sessions on one side cannot
establish a cause and nine cannot refute one; this is an observation about
alignment, not a test, and no causal claim is made in either direction.

**What this saves the next phase.** A designed test built around the filesystem
would be built around the wrong variable. The better-supported mechanism is the
one Phase 8.1 already established **at run level**: runs that applied an effect
had **+194.1 ms** higher kill latency (permutation p = 0.00005, 20 000
relabellings, seed 4242), with B3 as a null control at −12.1 ms, p = 0.76. The
session-level ordering is *not* monotone in latency — Phase 8.1's own Spearman
fell from 1.000 over four sessions to 0.700 over five — and the five Phase-8.4
sessions here repeat that: latency medians 976.8 → 1138.8 ms map to counts
12, 18, 10, 18, 13, in no order at all.

---

## 5. What a designed test would need

Design is the next phase's; these are the constraints this step establishes.

1. **Manipulate the filesystem, do not observe it.** Every session here confounds
   filesystem with date, harness version and host load. The manipulation is
   cheap — the same cell, alternating `results_root` between `/root/...` and
   `/mnt/d/...`, interleaved at run level so the arm is orthogonal to position by
   construction, which is the amendment-1 device Phase 8.5 already validated.
2. **Power it against the observed spread, not against a hoped-for effect.** The
   within-ext4 spread is 10–18/30 across six sessions. A design that cannot
   resolve a difference smaller than that resolves nothing. Phase 10's ±15 pp
   stipulated margin and its half-width rule are the precedent, including the
   rule that an underpowered result is reported as *inconclusive*, in those words.
3. **Record the fault-landing latency per run** — `redis_kill_latency_ms` now
   exists, and the mechanism is a race, so the covariate must be measured on
   both arms rather than reconstructed afterwards as Phase 8.1 had to.
4. **Take the append cost as a manipulation check.** `filesystem_fingerprint.py`
   should be run on the new collection and must reproduce the ~4× separation. A
   filesystem arm whose append costs do not differ has not manipulated anything.
5. **Note what has changed since these sessions.** All ten were collected under
   Docker Desktop or on its kill-latency envelope; Phase 10 measured the native
   runtime at **317 ms median against 961.8 ms**, ~3× narrower. The race window
   the whole mechanism turns on is materially different now, so a new collection
   is not comparable to these ten and must not be pooled with them.

---

## 6. One correction to the prompt's premise, recorded not applied silently

The prompt names the five sessions as *"the original `b2-2026-08-21` cell and the
four `b2-paired-v2-*` replications"*. The 4–20/30 spread it refers to is not that
set. It is the set in `reports/phase-report-8-1-0-2026-08-27.md:294-299` —
**the 2026-08-07 cell inside `matrix`, plus the four `b2-*-2026-08-21`
sessions** — whose counts are 10, 20, 12, 4, 7. The `b2-paired-v2-*`
collections are Phase 8.4's later paired replications, with counts 18, 18, 10, 12.

Rather than pick one reading, **all ten sessions are tabulated above**, which is
what makes §4 answerable at all: the prompt's grouping has five ext4 sessions
and one unknown, and could not have shown that the spread survives with the
filesystem held fixed.
