# Phase 8.4 — foreign container load was running during session 2, and it is now in an artefact

**Recorded before sessions 3 and 4 have produced any outcome.** This is a
statement about the *conditions* session 2 was collected under. It is
established from a container status string captured at session 3's precondition
and from session 2's own timestamps, and it does not depend on any number either
session produced.

---

## 1. What was found

Session 3's container precondition, at `2026-08-28T16:48:24+05:00`, recorded two
foreign containers running in the Docker Desktop VM alongside the two
`compose.phase2.yml` fixtures:

| container | image | status at 16:48:24 |
|---|---|---|
| `komserv-pg-race-ecd02850` | `postgres:16-alpine` | `Up About an hour` |
| `komserv-pg-race-c4309c8e` | `postgres:16-alpine` | `Up 2 hours` |

Both were stopped by the precondition before session 3 began, and both are
recorded by name in
`experiments/results/b2-paired-v2-s3-2026-08-28/analysis/container-precondition.json`,
which `SHA256SUMS` covers.

## 2. They overlap session 2's collection window

Session 2's own artefacts give the window:

- collection started `2026-08-28T14:45:56+05:00`
- collection ended `2026-08-28T16:05:28+05:00` (4772 s elapsed, from the log)
- refill, freeze and verification finished `16:39:31`

Against the 16:48:24 observation, `Up 2 hours` places that container's start at
roughly `14:48`, and `Up About an hour` at roughly `15:48`. **Both fall inside
session 2's collection window.** Docker's status strings are humanised and
coarse, so these are not precise timestamps; but even read at their loosest,
each container was running for a substantial part of session 2.

**The exact start times can no longer be recovered.** Both containers were
removed between 16:48:24, when the precondition stopped them, and 16:52, when
`docker inspect` was attempted — `no such object`. They are ephemeral. What
survives is the status string captured in the artefact, which is why the
precondition captures the full table rather than only the names it acts on.

## 3. What this does and does not establish

**Established.** Session 2 was collected with foreign container load in the
Docker Desktop VM. This is the load 9C §6 named as the harness's blind spot: the
daemon runs in a VM whose load no field in `run-config.json` records, and
`provenance.py:209`'s `container_state` covers the AEP Redis container only.
Until now that gap was argued from provenance analysis and from amendment 1's
elimination hunt. It is now **observed, timestamped and hashed**.

**Co-occurring, and not to be read as more than that.** Session 2 is also the
session in which:

- the hard kill failed to land twice, at rep0 and rep6, after **0 occurrences in
  Phase 9's 240 runs and 0 in session 1's 120**;
- the AEP-full arm imbalance was **−97.7 ms**, against **+13.0 ms** in session 1
  — roughly seven times larger, opposite in sign, and opposite to its own B3 arm
  (+43.8 ms);
- the drift was **−5.21 ms/run** against session 1's **−1.81**, about three times
  steeper.

**Not established: causation.** Nothing here shows the postgres containers
caused any of those three. The temporal overlap is real and is recorded; the
mechanism is not demonstrated. Stated as a difference that must be adjudicated,
exactly as §9 finding 2 of the plan stated the ext4/drvfs difference — *not* as a
demonstrated cause.

**One mechanism worth naming, and no more than naming.** The container name
`komserv-pg-race` and the pattern of the observation — two containers with
different ages, both removed within minutes — suggest a test suite that creates
and destroys postgres containers repeatedly rather than two static workloads.
Repeated container churn in the same VM is an *intermittent* load, and session
2's non-landing kills were **clustered rather than distributed** (rep0 and rep6
of 0–29, then none). An intermittent competing load and a clustered failure are
consistent with each other. Consistent is not evidence.

## 4. Session 2 is not dropped, and this is not a reason to drop it

No registered stop condition fired during session 2. Its balance check passes
the registered 100 ms threshold at −97.7 ms; §3.4 says failing sessions are
reported individually and no session is dropped, and this one does not even
fail. Amendment 4's ceiling was not exceeded. Every HALT condition is clean.

**Discovering an unrecorded difference in a session's conditions after the fact
is not licence to remove it.** It is licence to report it, which is what this
document does. Session 2 stands as one of the k = 4.

What it does change is the reading at 8.5 and 8.6: the between-session variance
the design blocks on is now known to include, for at least one session, a
competing VM load that no run-level field records.

## 5. What it changes going forward

- **The precondition earns its place.** Session 2's own
  `container-precondition.json` recorded `foreign_running_before: []` — correctly,
  because at `14:45:52` the VM was clean. The load arrived *after* the session
  started. A precondition is a snapshot at t=0 and cannot see that.
- **The gap that remains: nothing samples foreign load during a session.** The
  precondition covers the boundary; `container_state` covers the AEP container
  only. **Filed as B12.**
- Sessions 3 and 4 begin with the VM cleaned, and their preconditions record it.
