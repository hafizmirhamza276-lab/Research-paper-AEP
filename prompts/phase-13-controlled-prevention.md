# Phase 13 — WS-3: make the prevention result a property of the protocol, not of docker kill latency

The prompt below is recorded **verbatim**, before any other work in this phase,
per `docs/26-journal-readiness-direction.md` §3 rule 4.

---

## Read first
- docs/26-journal-readiness-direction.md §4 WS-3 in full, and §2 finding A3
- reports/phase-report-12-filesystem-hypothesis-<date>.md (the demotion, and what survives inside the six ext4 sessions)
- reports/phase-report-8-1-0-2026-08-27.md §F (kill latency +194.1 ms, permutation p = 0.00005; B3 control -12.1 ms at p = 0.76)
- reports/phase-report-9c-result-2026-08-21.md (over-dispersion 5.37)
- reports/phase-report-10-* "Fault delivery latency, both runtimes" (the native vs shim distributions this phase builds on)
- paper/sections/06-evaluation.tex §VI-C2 and paper/sections/08-threats.tex §A(e)
- experiments/run_matrix.py REGIME_REDIS_KILL_PREACK and its endpoints list (line ~249)

## Context
Phase 12 removed the filesystem as the explanation for the 10-18/30 spread in AEP-full's unwanted-applied count: the six ext4 sessions hold the filesystem constant and the spread survives. What remains is the mechanism Phase 8.1 measured directly — AEP-full dispatches if and only if WAITAOF returns before the kill lands, so the effect size is a draw from the fault injector's landing-latency distribution rather than a property of the protocol.

The paper currently concedes this (§VIII-A(e): "a reader should therefore treat 18 as one draw from that distribution and not as a property of AEP"). That concession is what makes the barrier's only measured benefit — and therefore contribution C2, the most novel mechanism in the paper — the thinnest claim in it. This phase replaces the race with a controlled fault, so the result becomes deterministic and attributable.

## Step 1 — Choose the fault mechanism by measurement, not by argument
Candidate mechanisms, and the property that matters is a landing time that is both small and tightly distributed relative to a WAITAOF round trip:
(a) SIGSTOP the Redis container (docker pause) at the instrumented point, then kill — pause is synchronous and should land in milliseconds;
(b) drop the Redis port with nftables/iptables after the intent CAS returns, so WAITAOF cannot return, then kill;
(c) tc netem delay on the Redis socket so the kill deterministically wins the race.
Also consider any mechanism you judge better; justify it.

For each candidate: measure the landing latency 100 times on the native runtime, using the same instrumentation as Phase 10's kill-latency measurement so the numbers are comparable to the 419-992 ms already in the paper. Report n, min, median, p95, max, and the spread. Then choose, and state the criterion the choice was made on.

Important: (b) and (c) do not merely control the race — they change what fault is being injected. (b) is a partition, not a crash; the paper's failure model F2 already covers partitions and treats them differently from F3. Say explicitly which failure-model class your chosen mechanism instantiates, and whether §III's failure model needs a new row or an amended one. If the chosen mechanism is not a Redis crash, do not describe the result as a Redis-kill result.

## Step 2 — Implement as a NEW regime, leave the existing one untouched
Add REGIME_REDIS_KILL_PREACK_CONTROLLED (or a name matching the mechanism chosen). Do not modify REGIME_REDIS_KILL_PREACK — the existing frozen cells must remain comparable.
Note the constraint recorded in PAPER_ROADMAP.md: REGIME_REDIS_KILL_PREACK.endpoints excludes some endpoints, which is why POS_ONLY was previously unreachable without a code change. The new regime must reach all three capability classes; state what you changed to allow that and confirm it changes nothing about the old regime.
Every run must record the fault landing latency, per Phase 10's addition.

## Step 3 — Pre-register, commit, and push before any data exists
reports/phase-report-13-prediction-<date>.md:
- Prediction: under the controlled fault, AEP-full's unwanted-applied rate approaches 0 and B3's approaches 1, in all three capability classes; and the between-session spread that was 10-18/30 under the uncontrolled fault collapses.
- State the spread you would need to observe to call the control successful, and the spread at which you would call it failed. Both in advance. This is the criterion Phase 9C lacked.
- Design: 3 sessions per capability class, 30 runs per arm per session, run-level interleaved between AEP-full and B3, all on ext4 on the native runtime.
- Unit of analysis: the run; session-clustered intervals; state the exact analysis command.
- State in advance what result would mean the control mechanism itself failed (e.g. AEP-full still spread widely, or B3 no longer at ceiling) as distinct from the protocol behaving unexpectedly.
- Either outcome is acceptable and will be reported as it came out.

## Step 4 — Collect and analyse
Collect into a new dated results root on ext4. Also collect the in-flight Redis-kill variant that the paper predicts will tie (§VIII-C(f) names it as implemented but never collected) — a predicted tie that is inferred is an assumption, not evidence.
Verify before collecting: scripts/verify_measurement_host.py exits 0, suspend declared, clock check within tolerance. Phase 11 found the clock degradation is episodic rather than a state — so check it, do not assume it.

## Step 5 — Rewrite §VI-C2, and only §VI-C2
Lead with the controlled result. Keep the original docker kill cell as the uncontrolled replication that agrees in direction. Remove the language that presents the magnitude as unknowable, but only to the extent the new data actually supports removing it — if the controlled fault does not collapse the spread, say so and keep the concession.
Add the controlled row to Table IX. Regenerate all macros; never hand-edit paper/generated/**.
Then state, in the report and not yet in the manuscript, what this implies for §VIII-A(e) and for contribution C2 — I will decide the contribution framing separately.

## Bounds
- In scope: experiments/ (new regime, harness instrumentation), scripts/, docs/ (new), reports/ (new), prompts/, paper/sections/06-evaluation.tex, paper/generated/** by regeneration only, new dated results roots.
- Out of scope: existing results roots, REGIME_REDIS_KILL_PREACK itself, all other manuscript sections, aep_core/** unless the new regime genuinely requires it — and if it does, stop and report before changing it, because a change to aep_core invalidates the comparability of every frozen cell.

## Acceptance criteria
- Fault mechanism chosen on measured landing-latency distributions, all candidates reported.
- The mechanism's failure-model class stated explicitly, and §III checked for whether it needs amending.
- Controlled cells for AEP-full and B3 across all three capability classes, >= 3 sessions each, run-level interleaved.
- In-flight variant collected.
- Pre-registration commit pushed before the first data commit; both hashes and times in the report.
- All gates green on the final commit; every new number carries a provenance comment naming its CSV cell.
- Existing results roots byte-unchanged.

## Report
reports/phase-report-13-controlled-prevention-<date>.md: Asked / Mechanism selection with all candidate distributions / Failure-model classification / Pre-registration ordering / Results, per class, with session-clustered intervals / Did the spread collapse — against the pre-registered criterion / What this implies for §VIII-A(e) and C2 / Not done and why / Findings outside scope.

Reply in chat in at most 6 lines: the mechanism chosen and its landing latency, the controlled rates per capability class, and whether the spread collapsed against the pre-registered criterion.

---

# Notes recorded with the prompt, not applied silently

No correction or amendment had been issued by the operator at the time this file
was committed. This section exists so that its absence is explicit.

Two constraints inherited from earlier phases bear directly on this one and were
decided elsewhere:

1. **`aep_core/**` is out of bounds and the prompt says to stop and report if
   the new regime requires touching it.** That is stronger than the usual
   scope rule and is the reason it is repeated here: a change to `aep_core`
   invalidates the comparability of all 432 frozen runs, whose `config_digest`
   values were computed against it.

2. **Phase 11 established that this host's wall-clock divergence is episodic,
   not a state** — one 2.5-hour window on 2026-09-02 across 1 458 runs, absent
   before and after. Step 4's instruction to *check* rather than assume follows
   from that, and the E5 drop rate of any collection made here is a first-class
   number, not a footnote.
