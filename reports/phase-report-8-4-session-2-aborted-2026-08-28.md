# Phase 8.4 — the first session-2 attempt was aborted, and why it does not pool

**This record is committed before the partial root is analysed.** That ordering
is the point of the document: the reason this collection is excluded is fixed
and verifiable in the history *before* any number it produced exists in a
readable form.

---

## 1. What happened

A session-2 collection was started into
`experiments/results/b2-paired-v2-s2-2026-08-28` on the ext4 clone at
`/root/aep-phase8`. It reached **25 of 120 runs** and stopped at 14:15 PKT when
the `Ubuntu-24.04` WSL distro shut down underneath it. The distro was found in
the `Stopped` state at 14:18; the last artefact written was
`aep_full-none-payments-5e34a267-r6/events-recovery.jsonl` at 14:15:22.

The root is retained, renamed to `b2-paired-v2-s2-aborted-2026-08-28`, frozen
and tracked. Its `run-config.json` files record the pre-rename path
`experiments/results/b2-paired-v2-s2-2026-08-28`; the directory was renamed
after collection so that the k = 4 set could keep sequential names, and nothing
inside the runs was altered.

## 2. Why it does not pool — the structural argument, not the discipline one

The weak version of this argument is "the outcome columns were never looked at".
That is a claim about conduct, it cannot be checked by anyone reading the
repository later, and this project does not rest on that kind of claim anywhere
else.

The version that holds:

1. **The cause is exogenous.** The collection was ended by the WSL virtual
   machine stopping. That is a property of the host, not of the runs — nothing
   the 25 runs produced is any part of the reason.
2. **No registered stop condition fired.** Plan §6 enumerates the conditions
   under which a session stops mid-run: a HALT from §3.4, a §3.3 invariant
   exception, a canary mismatch, a large `uptime_after_seconds`, host load
   outside 0.10–2.49, a kill-latency median outside the 859–1216 ms envelope, an
   unclean tree at session start, or wall time above threshold. **None of them
   was reached.** The session did not stop because a check fired; it stopped
   because the machine did.
3. **The handling was pre-registered.** Plan §6 already states what a stopped
   session gets: "finish the run in flight, freeze what exists, report the
   partial session, and **do not** fold it into the k = 4 set." This record
   applies a rule written before the phase began; it does not invent one.

The distinction between (2) and a registered stop is what makes this different
from dropping a session. Amendment 1 drew the same line for the superseded
design: not pooling a session because the *design* changed is a different act
from removing one because of its *results*, and it is established from something
other than the outcome. Here it is established from the host.

**A 25-run fragment could not have entered the k = 4 set in any case.** k = 4
was derived in plan §6 from the primary estimand's MDE at 30 runs per arm per
session; a fragment with 7 repetitions of one cell is not a session under that
derivation, whatever it contains.

## 3. The foreign container is no longer a hypothesis

A container named `komserv-pg-race-fa618582` — unrelated to this project — was
found running in the Docker Desktop VM alongside the two `compose.phase2.yml`
fixtures when the distro was restarted.

9C §6 named the Docker Desktop VM's own load as the gap the harness cannot see:
the daemon runs in a VM whose load no field in `run-config.json` records.
Amendment 1 time-boxed a hunt for the drift's cause and did not find it, but
ruled out resource accumulation, AOF growth, docker churn and leaks, and ended
by naming the same invisible VM load as what remained.

This is the **third independent direction** the same gap has been reached from —
9C's provenance analysis, amendment 1's elimination hunt, and now a directly
observed foreign container competing for the VM during a Phase 8 collection.
**It has stopped being a hypothesis and should be written up in 8.6 as an
established limitation of the instrument**, not as a candidate explanation.

`experiments/harness/provenance.py:209`'s `container_state` covers the AEP Redis
container only, so foreign load reaches no artefact in the run root. Sessions
2–4 therefore carry a new per-session `container-precondition.json` that records
every container by name before and after the clean, running or not.

## 4. What sessions 2–4 do differently

- **A per-session container precondition.** Foreign containers are recorded by
  name and stopped. The two compose fixtures are **not** touched: they are part
  of the run, and recreating them per session would make session 1 differ from
  sessions 2–4 by construction — the exact defect the interleaving redesign
  existed to remove.
- **The collection is detached** (`setsid`), so it is not a child of the
  `wsl.exe` process that launched it. That is the most likely proximate cause of
  the abort: the launching host process died and took the process tree with it.
- **A Windows-side keepalive** holds the distro open, covering the other
  candidate cause independently, since the above is a diagnosis rather than a
  demonstration.
- **Per-session commit** is retained, so a further failure costs one session
  rather than three.

**`C:\Users\<user>\.wslconfig` was written with `vmIdleTimeout=-1` but was NOT
applied, and was in effect for none of sessions 1–4.** Applying it requires
`wsl --shutdown`, which would restart Docker Desktop's VM against a
digest-pinned image and a live compose stack minutes before a four-hour run.
The setting is staged for a later reboot. This is recorded because if anyone
runs `wsl --shutdown` mid-collection, the remaining sessions would continue
under a different VM configuration — an undeclared change of collection
conditions, which is precisely the class of defect this phase keeps catching.

## 5. Unchanged

k = 4 and the no-extension commitment; the primary, both secondaries and the
integrity check; every amendment through amendment 3. Sessions 2, 3 and 4 are
collected on the registered design with no further deviation.
