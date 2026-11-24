# Phase 8.5 step 1 — all four v2 sessions are interleaved, and k = 4 stands

**A claim I made in the 8.5 plan was wrong.** I wrote that "session 1 is
cell-major (pre-amendment-1)", which would have dropped k to 3. It is false. It
came from conflating two different roots whose names differ by three characters,
and it was asserted from memory rather than derived — the fourth such substitution
in this phase.

Established here from two independent sources that agree.

---

## 1. The confusion, named precisely

Two roots exist, and only one of them is cell-major:

| root | design | status |
|---|---|---|
| `b2-paired-s1-2026-08-28` | **cell-major** | the superseded first attempt |
| `b2-paired-v2-s1-2026-08-28` | **interleaved** | session 1 of the k = 4 set |

The `v2` prefix *is* the amendment. Every root in the pre-registered set carries
it because the set was re-collected after amendment 1 landed. Reading
`b2-paired-s1` as "session 1" is the error.

## 2. Evidence A — the order the runs actually executed in

From each session's own `matrix-progress.jsonl`, which is written in execution
order. The diagnostic is the number of `cell_key` changes between consecutive
runs: with 4 cells and 30 repetitions, interleaved gives ~90 and cell-major gives
~3. Two orders of magnitude apart, so no threshold needs tuning.

| root | runs | `cell_key` changes | longest same-cell run | verdict |
|---|---|---|---|---|
| `b2-paired-s1` | 120 | **3** | **30** | **CELL-MAJOR** |
| `b2-paired-v2-s1` | 120 | **119** | **1** | **INTERLEAVED** |
| `b2-paired-v2-s2` | 122 | 121 | 1 | **INTERLEAVED** |
| `b2-paired-v2-s3` | 120 | 119 | 1 | **INTERLEAVED** |
| `b2-paired-v2-s4` | 120 | 119 | 1 | **INTERLEAVED** |

The first eight `(repetition, cell_key)` pairs show it directly. `b2-paired-s1`
runs repetitions 0–7 inside one cell. Every v2 session cycles all four cells
inside repetition 0, then all four inside repetition 1.

## 3. Evidence B — the harness each session recorded, and its sort key

`run-config.json` `environment.harness_version.commit`, read from each root, then
the sort key retrieved from that commit:

| root | harness commit | `plan.runs.sort` key at that commit |
|---|---|---|
| `b2-paired-s1` | `16abc997` | `(tier, cell_key, repetition)` — cell-major |
| `b2-paired-v2-s1` | `f29f3aee` | `(tier, repetition, cell_key)` — **interleaved** |
| `b2-paired-v2-s2` | `0f0ee8f3` | `(tier, repetition, cell_key)` — **interleaved** |
| `b2-paired-v2-s3` | `3df6df2b` | `(tier, repetition, cell_key)` — **interleaved** |
| `b2-paired-v2-s4` | `3df6df2b` | `(tier, repetition, cell_key)` — **interleaved** |

Amendment 1's change landed in `5b601d0`, "interleave at run level, because arm
and drift are collinear". All four v2 sessions ran at or after it.

**The two sources agree exactly**, and their agreement is the point: an observed
order that contradicted the recorded harness would itself have been a finding.
All 120 `run-config.json` files are present in each root; one was read per
session because every run in a session shares a harness version, and that is
stated rather than assumed by reading all 120.

## 4. Conclusion for 8.5

**k = 4. All four sessions are run-level interleaved and eligible to pool on this
criterion.** No session is dropped, and the plan's §2 and §3 stand as written.

**B9's asymmetry is confirmed, not weakened.** The frozen set 8.1 analysed is
cell-major and cannot be fixed; Phase 8.4's four sessions are protected by
construction. B9 remains a re-analysis obligation and 8.5 does not inherit it.

**Arm and run position are orthogonal by construction in all four sessions**, so
the arm contrast cannot absorb within-session drift. This does *not* make position
irrelevant to the outcome — the covariate is latency and latency drifts — which is
why the plan fits with and without run position and reports both.

## 5. Uniformity, checked while the configs were open

All five roots report `redis_storage_backing.mount_type = volume` and
`results_root_filesystem.is_drvfs = false`, type `ext2/ext3`, device `/dev/sdf`,
`harness_version.dirty = false`. **The four v2 sessions are uniform in storage
backing and filesystem**, which is the §9-finding-2 axis. They are *not* uniform
in instrumentation — s1 has no container precondition or fault census, and s1 and
s2 have no foreign-load series — and 8.5 must not present them as though they
were.

## 6. One count that will mislead anyone reading the progress file

`b2-paired-v2-s2`'s `matrix-progress.jsonl` holds **122 records** while its
manifest reports **120 completed runs** and it has **120** run directories. The
two extra records are the two `FaultInjectionError` attempts that were refilled
via `--resume`; the refills reused the same directories.

**Anyone deriving a run count from that file will get 122 for session 2 and 120
for every other session.** The authoritative count is the manifest and the
directory count. This is recorded because `matrix-progress.jsonl` is otherwise
the right file to read (R2, B14) and this is the one place it must not be used
naively.
