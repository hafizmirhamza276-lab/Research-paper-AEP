# Phase 54: what was built, what was rehearsed, and the defect the rehearsal found — 2026-09-24

**Nothing was collected.** No results root was created, no device was
provisioned, no manuscript text changed, `scripts/paper_tables.py` untouched,
part 3 not rebuilt.

**Repository state at the start:** `86a5f98`. Pre-registration committed first,
at `8d485c0`, before any of the code below existed.

---

## 1. The pre-registration

`prompts/phase-54-record-loss-restart-2026-09-24.md`, committed at `8d485c0`
**before any code**, with its blob recorded at `711dd40` and the `EXPECTED`
entry added in the same commit as the file.

Eleven sections. The ones that carry weight:

- **§2 — the fault, and why the obvious one is wrong.** `error_writes`, not
  `drop_writes`. `drop_writes` is the lying fsync (`TruthfulFsync = FALSE`),
  which with a restart is `write-loss.cfg`, and that config expects
  `NoLostEffect` to fail **with the barrier enabled**. Both arms lose and the
  cell separates nothing. Recorded because that is the cell the external audit
  proposed.
- **§4 — the prediction, from the model.** B3 loses at least one effect in 300;
  AEP-full loses none. Derived from `b3-no-barrier-restart.cfg` against
  `aof-rewind.cfg`, both committed and blob-pinned.
- **§5 — what each of the four outcomes establishes**, including refutation.
- **§6 — the instrument hazard, with four per-run delivery checks.** A
  both-arms-zero result is **void** unless the table reads back `error_writes`,
  the canary write *failed*, the restart happened, and the canary key is absent
  afterwards.
- **§7 — not pooled with anything**, its own session, its own macros.
- **§10 — what the manuscript may say per outcome**, fixed before the data,
  including that a void cell licenses **no** manuscript sentence.

The gate is green with the entry in place: `check_prereg_order.py` exits 0.

## 2. What was built

Three changes, and deliberately nothing else.

### 2.1 `error_writes` — `experiments/flakey_write_loss.py`

`table()` previously hard-coded `drop_writes` at `:158`. It now resolves the
feature from `MODE_FEATURES` — `pass` → none, `drop` → `drop_writes`,
`error` → `error_writes` — and **raises on an unknown mode** rather than
falling through to `drop`, on the same reasoning as `redis_kill.killer_for`:
a silent fallback would deliver the non-discriminating fault into a run whose
name says otherwise, and the table line in the run log would not contradict it.

**WS-4's tables are byte-identical**, asserted in tests:

```
pass   -> 0 204800 flakey /dev/loop9 0 1 0
drop   -> 0 204800 flakey /dev/loop9 0 0 1 1 drop_writes
error  -> 0 204800 flakey /dev/loop9 0 0 1 1 error_writes
```

### 2.2 The arming path — `experiments/harness/write_loss.py`

`ERROR_FEATURE`; `table_declares_feature(table, feature)` with
`table_declares_drop` delegating to it unchanged; `arm_error_writes`;
`_arm_feature` shared by both, with `arm_drop_writes` delegating so its
behaviour is a refactor and not a revision.

### 2.3 The mechanism — `experiments/harness/redis_kill.py`

`MECHANISM_WRITE_LOSS_RESTART = "write-loss-restart"`, routed by `killer_for`
to a new `error_writes_on_device`, and **deliberately not added to
`NON_KILLING_MECHANISMS`** — so `mechanism_kills_server` returns `True` and the
existing `kill_and_restart` path performs the restart and its uptime
verification.

Verified at the seam:

| | |
|---|---|
| `NON_KILLING_MECHANISMS` | `['write-loss']` — unchanged |
| `write-loss` kills server? | `False` |
| `write-loss-restart` kills server? | **`True`** |
| `killer_for('write-loss')` | `drop_writes_on_device` |
| `killer_for('write-loss-restart')` | `error_writes_on_device` |
| a misspelling | refused, with both valid names in the message |

## 3. The rehearsal

### 3.1 What could not be run, stated plainly

**The end-to-end exercise the instruction asked for could not be run in this
session.** Two hard blockers, both checked rather than assumed:

| | |
|---|---|
| `sudo -n true` | **`a password is required`** — no passwordless sudo |
| docker socket as this user | **`permission denied ... /var/run/docker.sock`** |
| `dm_flakey` module | loaded |
| `dmsetup`, `losetup`, `mkfs.ext4`, `docker` binaries | all present |

So the device half (does the write loss land?) and the Redis half (does
`WAITAOF` fail? does the restart lose the record?) remain **unrehearsed**. They
are the first things to run when the cell is scheduled, and §5 lists them.

A Redis-side proxy was prepared — a throwaway container with its AOF on a 1 MiB
tmpfs, filled until writes fail with `MISCONF`, then killed and restarted —
which would have exercised the honest-failure and restart behaviour without
`dm-flakey`. It could not run for the same docker-permission reason. The script
is kept at `.scratch/length/rehearse_phase54.sh` (untracked) for whoever has
the socket.

### 3.2 What was run, and what it found

The arming path was driven against a **simulated `dmsetup`**, capturing the
exact argv a run would issue. This was chosen because `write_loss.py`'s own
comment says a malformed table *"shipped once and was caught only by running
against a real device — the unit tests mock dmsetup, so they cannot see a
table the kernel would reject."*

**The table is well-formed.** Nine fields, correct grammar, feature count
present before the feature, intervals not both zero:

```
0 204800 flakey /dev/loop9 0 0 1 1 error_writes
```

**And the rehearsal found a real defect, which is why it was worth doing.**

> **`_reload_table` issued a plain `dmsetup suspend`.**

`dmsetup suspend` calls `freeze_bdev()`, which **syncs the filesystem** — the
exact instrument hazard §6 of the pre-registration was written to guard
against. Two arming paths existed in this repository and they disagreed:

| path | suspend argv | used by |
|---|---|---|
| `flakey_write_loss.set_mode` | `suspend --noflush --nolockfs <dev>` | the standalone probe |
| `harness/write_loss._reload_table` | **`suspend <dev>`** | **what a run calls at the fault point** |

The unflagged one is the one a collection would have used. Had phase 54 been
collected against it, the arming step would have flushed the record the cell
exists to lose, **both arms would have read zero, and that is indistinguishable
from the claim being vindicated** — the precise failure mode §6 names.

**Fixed, without touching WS-4.** `_reload_table` grew `flush: bool = True`;
the default reproduces the old argv byte for byte, and `arm_error_writes`
passes `flush=False`. Verified:

```
WS-4 (drop_writes)  suspend argv: ['suspend', 'aep-flakey']
phase 54 (error)    suspend argv: ['suspend', '--noflush', '--nolockfs', 'aep-flakey']
```

This is the answer to *"if the freeze_bdev hazard fires here, say so: better
now than after a full collection."* **It fired, in the code rather than on the
device, and it cost twenty minutes instead of a day.**

## 4. Tests and their known-positives

`tests/test_error_writes_mechanism.py`, **17 tests**. The existing write-loss
suite — `delivery`, `lifecycle`, `verdict`, `wiring` — still passes, **46
tests**, so the refactor moved nothing.

Four known-positives, each verified by reintroducing the defect and confirming
the suite goes red, with the substitution asserted so the check cannot be
vacuous:

| # | defect reintroduced | result |
|---|---|---|
| 1 | `MODE_FEATURES["error"] = "drop_writes"` — the silent fallback | **2 failed**, naming the non-discriminating fault |
| 2 | `MECHANISM_WRITE_LOSS_RESTART` added to `NON_KILLING_MECHANISMS` | **failed**: *"the restart IS the experiment: without it the record stays in memory … and both arms report zero lost effects for a reason that has nothing to do with the barrier"* |
| 3 | `flush=False` dropped from `arm_error_writes` | **failed**: *"a plain suspend, which calls freeze_bdev() and syncs the filesystem … the instrument failure the pre-registration §6 exists to catch"* |
| 4 | WS-4's argv or drop table changed | pinned by two tests; both green with the current code |

Every source file was restored afterwards and `git diff` confirmed clean.

## 5. What still stands between here and the collection

| # | blocker | needs |
|---|---|---|
| **1** | **The rescope must land first.** Phase 54's §10 says the eight unscoped statements in `reports/b1-plan-2026-09-24.md` §1.2 are corrected by the rescope that *precedes* this collection. The other session is doing that; `numbers.tex` is still in motion | the other session |
| **2** | **Root.** `sudo` with a password, for `losetup`, `dmsetup`, `mkfs.ext4` and the mount. Same as WS-4 needed | the author, at a terminal |
| **3** | **Docker socket access** for the Redis container and the kill/restart | the author, or group membership |
| **4** | **The two unrehearsed halves** — that the write loss lands, and that `WAITAOF` fails and the record is absent after the restart. Run the standalone probe's `--selftest` first, then a single throwaway run, before any of the 60 | root + docker |
| **5** | **A results root name and date.** The `EXPECTED` entry is keyed `experiments/results/b1-record-loss-2026-XX-XX`; rename to the real date when scheduled, and re-run `--update-blobs` only if the prediction file itself changes (it must not) | whoever schedules it |

**Time, once 1–3 are available.** Collection is ~1 hour for 60 runs, on WS-4's
precedent. Provisioning and teardown ~10 minutes. Analysis and the phase report
2–3 hours. The build is done.

**The order matters.** Do not collect before the rescope lands: §10 of the
pre-registration ties what the manuscript may say to a rescope that has already
happened, and collecting first would leave the eight unscoped statements
standing while a cell exists that speaks to them.
