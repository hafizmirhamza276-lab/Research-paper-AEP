# Phase 8.4 — the foreign-load sampler stopped, and two gaps in its series

The continuous sampler started for session 3 ran for a further three days after
collection ended. It has been stopped. Recorded here because stopping it ends the
only continuous record of VM load on the collection host, and because taking the
before/after snapshot surfaced something about the series that was not known.

**No session artefact is affected.** Sessions 3 and 4 are frozen, committed, and
verify 18 OK / 0 FAILED. Nothing below changes any of their numbers.

---

## 1. The stop

Stopped by **PID, never by pattern** — `kill 6761`. **R1** exists because
`pkill -f "load_sampler.sh /tmp/ls2"` killed the operator's own shell during
Phase 8.4, and three other pattern-matching constructs failed the same way in the
same day.

Identity was established the same way: by reading `/proc/6761/cmdline` directly,
which gave
`bash /root/phase8-driver/load_sampler.sh /root/phase8-driver/foreign-load-samples.jsonl 60`.

| check | result |
|---|---|
| `kill 6761` | rc 0 |
| `/proc/6761` after | **absent** |
| `/proc` enumerated for any `load_sampler` process | **zero found** |
| orphaned `sleep` child | absent |

The `/proc` enumeration is the authoritative check rather than `ps`. Immediately
after the kill, `ps -p 6761` returned exit 0 with a bare header and no rows, and
a stale `sleep` row still showed a parent PID that no longer existed — a process
table read mid-teardown. `/proc` was unambiguous.

## 2. The JSONL is byte-identical across the stop

| | before | after |
|---|---|---|
| lines | 1414 | **1414** |
| bytes | 193392 | **193392** |
| sha256 | `1c53e15d2ca8325496e894757a75717980d73ef9b38fffa83e2e047665c772d3` | **identical** |
| last record | `2026-08-31T12:10:52+05:00` | identical |

The sampler appends whole lines and was between samples when signalled, so there
is no truncated final record.

## 3. What the snapshot found: the series is not continuous

Sampling spans `2026-08-28T16:55:15` to `2026-08-31T12:10:52`, 1414 samples. It
is **not** 1414 consecutive minutes. Two multi-hour gaps:

| gap | from | to |
|---|---|---|
| **36 h** | 2026-08-29T22:12:29 | 2026-08-31T10:10:44 |
| **7.6 h** | 2026-08-29T12:38:16 | 2026-08-29T20:15:19 |

**Cause: the WSL VM was suspended.** The sampler is a `while true` loop with a
`sleep`; it cannot skip 36 hours while running. When the VM is paused the guest
stops executing, and on resume the loop continues against a clock that has jumped.

**This is why `ps` was misleading about the process's own age.** `ps` reported
`STARTED Sun Aug 30 12:20:15` and `ELAPSED 23:50:39`, which would suggest the
process was *not* the one launched on 28 August. It was: the PID never changed
and the JSONL's first record is `2026-08-28T16:55:15`, seconds after the
launch recorded at 16:55:18. Elapsed time and start time are computed from boot
time, and boot time is not stable across VM suspension. **In a suspendable VM the
append-only file is a more reliable account of a process's history than the
process table is.** An earlier statement that the sampler had been running "~3
days" was right about the process and would have been contradicted by `ps` alone.

### Sessions 3 and 4 are unaffected, and this is checked rather than assumed

Both session windows fall on 28 August — `16:48:39`–`18:07:15` and
`18:07:19`–`19:24:47` — roughly seventeen hours before the earlier gap begins.
Outside the two gaps above, the **largest** interval between consecutive samples
anywhere in the file is **73 s**, and that one occurs on 31 August. Within both
session windows the sampling is regular at its 60 s interval: 72 samples for
session 3, 76 for session 4.

### The defect this exposes

**Nothing detects or records a mid-series gap.** `slice_load.py` counts the
samples that fall inside a window and reports `samples` and a `coverage_note`,
but that note only describes the gap *before* sampling started. A window
containing a two-hour suspension would report a smaller sample count and say
nothing at all about why — and a sparse `foreign_running_seen` would then read as
"the VM was quiet" when the correct reading is "the VM was not observed".

This is **R5**'s requirement — observation added mid-collection must record its
own coverage limits in the artefact — met for the leading gap and unmet for
interior gaps. It is the same shape as **B13b**: an artefact that does not declare
the boundary of what it actually covers.

**Filed as an extension of B12**, whose subject is exactly this instrumentation.
Not fixed here. The remedy is small: the slicer already has every sample's
timestamp, so it can report the largest interior gap in the window alongside the
sample count, and say so when that gap exceeds the interval.

## 4. Consequence of stopping

There is now **no continuous record of foreign VM load** on the collection host.
If Phase 8.5 or any later work collects on this host again, the sampler must be
restarted first, and **R5** applies: whatever it produces must record its own
coverage limits, now including interior gaps.

The three days of post-collection samples are retained in
`/root/phase8-driver/foreign-load-samples.jsonl`. They are not evidence about any
session and are not committed; the two frozen per-session slices already carry
what the sessions need.
