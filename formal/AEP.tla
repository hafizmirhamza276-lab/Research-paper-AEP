-------------------------------- MODULE AEP --------------------------------
(***************************************************************************)
(* A TLA+ model of the Ambiguity-Explicit Protocol (AEP).                   *)
(*                                                                          *)
(* WS-7 (docs/26-journal-readiness-direction.md:208-215).                    *)
(*                                                                          *)
(* WHAT THIS MODEL IS DERIVED FROM.  The state machine, the guards on every  *)
(* write, the creation fence, the recovery classification table and the      *)
(* dispatch-authorization chain are transcribed from the implementation --   *)
(* `aep_core/core/intents.py`, `aep_core/core/intent_workflow.py`,           *)
(* `aep_core/core/intent_recovery.py`, `aep_core/core/connector_contract.py` *)
(* and `aep_core/core/durability.py` -- and NOT from section IV of the       *)
(* manuscript.  Where the two disagree, `formal/README.md` section 6 records *)
(* the disagreement as a finding.  `scripts/check_tla_transitions.py`        *)
(* mechanically re-checks that LegalTransitions below equals                 *)
(* `LEGAL_INTENT_TRANSITIONS` in the code, so this module cannot drift from  *)
(* the transition table without failing a gate.                             *)
(*                                                                          *)
(* THE ENDPOINT IS NOT COOPERATIVE.  This is the modelling decision the      *)
(* paper's claim rests on, so it is made explicitly and in one place:        *)
(*                                                                          *)
(*   1. The endpoint is never given an intent identifier, a nonce or an      *)
(*      idempotency key.  `Transmit` below reads NOTHING from the ledger.    *)
(*      It therefore cannot deduplicate, and a second dispatch produces a    *)
(*      second, independent effect.  This is what "cannot be enrolled"       *)
(*      means: no modelled action lets AEP change the endpoint's behaviour.  *)
(*                                                                          *)
(*   2. Whether an effect is applied is chosen adversarially (`Transmit`),   *)
(*      not derived from anything the caller did.                           *)
(*                                                                          *)
(*   3. The evidence the caller sees is chosen from `AllowedEvidence`, and   *)
(*      "AMBIGUOUS" is available on EVERY path -- so no caller can ever      *)
(*      distinguish "the effect did not happen" from "the effect happened    *)
(*      and the answer was lost".  That indistinguishability is the whole    *)
(*      problem; a model that let the caller tell them apart would prove     *)
(*      something the paper does not claim.                                  *)
(*                                                                          *)
(*   4. The god-view variable `effect` records what really happened at the   *)
(*      endpoint.  It is read by exactly two things: the `Transmit` action   *)
(*      that writes it, and the invariants.  It is NEVER read by a guard     *)
(*      on any protocol action.  `scripts/check_tla_transitions.py` enforces *)
(*      this syntactically -- see `--check-oracle`.                          *)
(*                                                                          *)
(* ASSUMPTION SWITCHES.  Five CONSTANTS turn stated assumptions on and off.  *)
(* Each is FALSE in some configuration, and every property that depends on   *)
(* it is expected to FAIL there with a counterexample.  A model checker run  *)
(* only in the configuration where everything passes establishes nothing     *)
(* about which assumptions are load-bearing -- the same shape as a gate that *)
(* cannot fail (docs/26 section 3 rule 13).                                  *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

CONSTANTS
    Workers,          \* worker identities; the lock value is the worker id
    IntentIds,        \* bound on intents minted for the modelled step
    MaxVersion,       \* bound on the fencing counter
    MaxAttempts,      \* P3 reconciliation attempt budget
    Capability,       \* the connector's declared reconciliation capability
    BarrierEnabled,   \* FALSE models B3 (experiments/baselines/b3_no_barrier.py)
    TruthfulFsync,    \* FALSE models WS-4: WAITAOF succeeds, the write is dropped
    SingleTimeline,   \* FALSE enables Restart, the AOF rewind of R1-3
    TruthfulEndpoint, \* FALSE models docs/22 section 5.1 / R2-4
    OperatorEnabled,  \* TRUE enables the unauthenticated operator of section 5.3
    ReconcileDelayCovers \* FALSE models the F5 scheduling gap; see below

(***************************************************************************)
(* Intent statuses.  `aep_core/core/intents.py:53-63`.                      *)
(***************************************************************************)
NONE_STATE == "NONE"
ATF        == "ABOUT_TO_FIRE"
FU         == "FIRED_UNCONFIRMED"
FC         == "FIRED_CONFIRMED"
FAC        == "FAILED_CONFIRMED"
PA         == "PERMANENTLY_AMBIGUOUS"

Statuses  == {NONE_STATE, ATF, FU, FC, FAC, PA}
Unresolved == {ATF, FU}            \* UNRESOLVED_INTENT_STATUSES

(***************************************************************************)
(* The exhaustive transition table.  Transcribed from                       *)
(* `LEGAL_INTENT_TRANSITIONS` (`aep_core/core/intents.py:65-96`) and its    *)
(* Lua re-implementation (`:449-461`), which are byte-for-byte the same ten *)
(* edges.  `scripts/check_tla_transitions.py` fails if this set and the     *)
(* Python one ever differ.                                                  *)
(*                                                                          *)
(* Note what is NOT here: no edge back into ABOUT_TO_FIRE, which is what    *)
(* "never silently re-dispatched" means; and no direct                      *)
(* ABOUT_TO_FIRE -> PERMANENTLY_AMBIGUOUS edge, so escalation must pass     *)
(* through FIRED_UNCONFIRMED via the recovery claim.                        *)
(***************************************************************************)
LegalTransitions ==
    { <<NONE_STATE, ATF>>,
      <<ATF, FC>>, <<ATF, FAC>>, <<ATF, FU>>,
      <<FU, FU>>, <<FU, FC>>, <<FU, FAC>>, <<FU, PA>>,
      <<PA, FC>>, <<PA, FAC>> }

(***************************************************************************)
(* Worker program locations.  These are the points between which the        *)
(* implementation's 22 named crash points fall                              *)
(* (`tests/mock_connector.py:59`); `Crash` below is enabled at every one of *)
(* them, which is strictly more adversarial than the six the harness        *)
(* injects at.                                                              *)
(***************************************************************************)
IDLE     == "IDLE"        \* no lease, no local context
PREPARED == "PREPARED"    \* lease held; request prepared and vaulted
INTENT   == "INTENT"      \* NONE -> ABOUT_TO_FIRE CAS committed
ACKED    == "ACKED"       \* the durability barrier answered
AUTHZ    == "AUTHZ"       \* dispatch authorization written to Redis
READY    == "READY"       \* preflight passed; capability minted
INFLIGHT == "INFLIGHT"    \* bytes sent; an effect may exist
ANSWERED == "ANSWERED"    \* evidence in hand, not yet persisted

Locations == {IDLE, PREPARED, INTENT, ACKED, AUTHZ, READY, INFLIGHT, ANSWERED}

NoLock   == "none"
NoIntent == "none"
NoEv     == "none"

Evidence == {"SUCCESS", "FAILURE", "AMBIGUOUS"}
Readback == {"APPLIED", "NOT_APPLIED", "UNKNOWN", "CONFLICT"}

Capabilities == {"AUTHORITATIVE_READBACK", "POSITIVE_ONLY_READBACK",
                 "NO_READBACK", "UNDECLARED"}

(* The dispatch-authorization key value.  Kept a record in every case,      *)
(* including "absent", so that the comparison the preflight makes is        *)
(* record-to-record.  `aep_core/core/intents.py:1186`: an absent            *)
(* authorization defaults to a value that cannot match, so it fails closed. *)
(* NoAuth is exactly that unmatchable default.                              *)
AuthValues == [w: Workers \cup {NoLock},
               i: IntentIds \cup {NoIntent},
               v: 0..MaxVersion]

NoAuth == [w |-> NoLock, i |-> NoIntent, v |-> 0]

StoreType == [ version : 0..MaxVersion,
               lock    : Workers \cup {NoLock},
               status  : [IntentIds -> Statuses],
               tries   : [IntentIds -> 0..MaxAttempts],
               auth    : AuthValues ]

CtxType == [ i : IntentIds \cup {NoIntent},
             v : 0..MaxVersion,
             ev: Evidence \cup {NoEv} ]

VARIABLES
    store,   \* committed Redis state: what a reader sees now
    disk,    \* the fsynced prefix: what survives a restart
    minted,  \* intent ids ever created.  Models UUID freshness: NOT rewound
             \* by Restart, because a crashed Redis does not un-draw a UUID.
    effect,  \* GOD VIEW.  effect[i] = the endpoint really applied intent i.
             \* Never read by a protocol guard; see the header, point 4.
    pc,      \* worker program location
    ctx      \* worker local context (lost on crash)

vars == <<store, disk, minted, effect, pc, ctx>>

(***************************************************************************)
(* Derived predicates.                                                      *)
(***************************************************************************)
EffectCount == Cardinality({i \in IntentIds : effect[i]})

Terminal == {FC, FAC, PA}

(* The creation fence, `aep_core/core/intents.py:485,495-497,507-509`.  A    *)
(* new intent is refused if ANY intent in the ledger is ABOUT_TO_FIRE,       *)
(* FIRED_UNCONFIRMED or PERMANENTLY_AMBIGUOUS (Lua `-7`), and the latest     *)
(* attempt for the step must be FAILED_CONFIRMED (Lua `-6`).  For the single *)
(* modelled step those two collapse to: every intent minted so far is        *)
(* FAILED_CONFIRMED.  This is the reason AEP never automatically retries     *)
(* after an ambiguity -- and therefore why an undetected duplicate needs a   *)
(* FAILED_CONFIRMED that was wrong.                                          *)
CreationFenceOpen ==
    \A j \in IntentIds : (j \in minted) => store.status[j] = FAC

(* Fsync.  The barrier writes the whole committed state to the durable       *)
(* prefix.  Two switches suppress it, for two different real mechanisms:     *)
(*   BarrierEnabled = FALSE  -- B3: no WAITAOF round trip is issued at all.  *)
(*   TruthfulFsync  = FALSE  -- WS-4: WAITAOF IS issued and reports success, *)
(*                              and the kernel discards the write anyway.    *)
(* Both leave `disk` behind, which is exactly why the two are               *)
(* indistinguishable to the protocol.  See README section 6, finding F3.     *)
Fsync(s) == IF BarrierEnabled /\ TruthfulFsync THEN s ELSE disk

TypeOK ==
    /\ store \in StoreType
    /\ disk  \in StoreType
    /\ minted \subseteq IntentIds
    /\ effect \in [IntentIds -> BOOLEAN]
    /\ pc \in [Workers -> Locations]
    /\ ctx \in [Workers -> CtxType]

Init ==
    /\ store = [ version |-> 0, lock |-> NoLock,
                 status |-> [i \in IntentIds |-> NONE_STATE],
                 tries  |-> [i \in IntentIds |-> 0],
                 auth   |-> NoAuth ]
    /\ disk = store
    /\ minted = {}
    /\ effect = [i \in IntentIds |-> FALSE]
    /\ pc = [w \in Workers |-> IDLE]
    /\ ctx = [w \in Workers |-> [i |-> NoIntent, v |-> 0, ev |-> NoEv]]

-----------------------------------------------------------------------------
(***************************************************************************)
(* THE RUNNER.  `WriteAheadRunner.execute`,                                 *)
(* `aep_core/core/intent_workflow.py:363-659`, in the order the code runs.  *)
(***************************************************************************)

(* Steps 1-3 of section IV: acquire the lease, require existing state,      *)
(* prepare and vault the request BEFORE any intent exists.  The vault and   *)
(* the binding digest are abstracted away (README section 5, exclusion 1).  *)
(* The lock is an ordinary SET and is deliberately not barriered            *)
(* (`aep_core/core/locks.py:149-152`, docs/22 F3.2), so `disk` is unchanged *)
(* -- this is the mechanism R1-3 turns on.                                  *)
AcquireLease(w) ==
    /\ pc[w] = IDLE
    /\ store.lock = NoLock
    /\ store' = [store EXCEPT !.lock = w]
    /\ pc' = [pc EXCEPT ![w] = PREPARED]
    /\ ctx' = [ctx EXCEPT ![w] = [i |-> NoIntent, v |-> store.version, ev |-> NoEv]]
    /\ UNCHANGED <<disk, minted, effect>>

(* Step 4a: the NONE -> ABOUT_TO_FIRE fenced CAS.  Both P1 conjuncts appear *)
(* as guards because that is how the Lua enforces them, atomically and in   *)
(* one invocation (`aep_core/core/intents.py:385` token, `:399-400` exact   *)
(* expected-version).                                                       *)
CreateIntent(w) ==
    /\ pc[w] = PREPARED
    /\ store.version < MaxVersion
    /\ \E i \in IntentIds :
        /\ i \notin minted
        /\ store.status[i] = NONE_STATE
        /\ CreationFenceOpen
        /\ store.lock = w                    \* (a) live-token check
        /\ store.version = ctx[w].v          \* (b) exact expected-version CAS
        /\ store' = [store EXCEPT !.version = store.version + 1,
                                  !.status[i] = ATF]
        /\ minted' = minted \cup {i}
        /\ ctx' = [ctx EXCEPT ![w] = [i |-> i, v |-> store.version + 1, ev |-> NoEv]]
    /\ pc' = [pc EXCEPT ![w] = INTENT]
    /\ UNCHANGED <<disk, effect>>

(* Step 4b: the durability barrier on the same pinned connection.           *)
(* `RealWaitAofDurabilityBarrier.confirm_durable` returns local_fsyncs >= 1 *)
(* (`aep_core/core/durability.py:318-332`).                                 *)
Barrier(w) ==
    /\ pc[w] = INTENT
    /\ disk' = Fsync(store)
    /\ pc' = [pc EXCEPT ![w] = ACKED]
    /\ UNCHANGED <<store, minted, effect, ctx>>

(* The barrier answered no (or raised).  No provider bytes have been sent,  *)
(* so if ownership remains the runner makes one fenced attempt to record    *)
(* FAILED_CONFIRMED with evidence LOCAL_NO_DISPATCH                         *)
(* (`aep_core/core/intent_workflow.py:454-476`).  This is the path that     *)
(* produces the measured prevention result of section VI.                   *)
BarrierFails(w) ==
    /\ BarrierEnabled
    /\ pc[w] = INTENT
    /\ pc' = [pc EXCEPT ![w] = IDLE]
    /\ IF /\ store.lock = w
          /\ store.version = ctx[w].v
          /\ store.status[ctx[w].i] = ATF
          /\ store.version < MaxVersion
       THEN /\ store' = [store EXCEPT !.version = store.version + 1,
                                      !.status[ctx[w].i] = FAC]
            /\ disk' = Fsync(store')
       ELSE \* ownership lost: leave ABOUT_TO_FIRE for recovery
            UNCHANGED <<store, disk>>
    /\ ctx' = [ctx EXCEPT ![w] = [i |-> NoIntent, v |-> 0, ev |-> NoEv]]
    /\ UNCHANGED <<minted, effect>>

(* Step 5: convert the acknowledgement into a Redis-visible authorization.  *)
(* `_DISPATCH_AUTHORIZATION_SCRIPT`, `aep_core/core/intents.py:649-675`.    *)
(* The authorization key is an ordinary SET with a TTL and is NOT           *)
(* barriered, which docs/22 R2-7 declares; hence `disk` is unchanged.       *)
(*                                                                          *)
(* MODELLED AS AN ASSUMPTION, NOT CHECKED: that reaching this action        *)
(* implies a real fsync happened.  In the implementation that link is an    *)
(* in-process Python object guard (DurabilityAck: non-constructible,        *)
(* single-use, scope-bound), and R2-7 states plainly that it is a           *)
(* control-flow guard under trusted-code assumptions rather than a proof.   *)
(* See README section 5, exclusion 2.                                       *)
Authorize(w) ==
    /\ pc[w] = ACKED
    /\ store.lock = w
    /\ store.version = ctx[w].v
    /\ store.status[ctx[w].i] = ATF
    /\ store' = [store EXCEPT !.auth = [w |-> w, i |-> ctx[w].i, v |-> ctx[w].v]]
    /\ pc' = [pc EXCEPT ![w] = AUTHZ]
    /\ UNCHANGED <<disk, minted, effect, ctx>>

(* Step 6: the atomic pre-dispatch preflight, `_PREFLIGHT_SCRIPT_BODY`,     *)
(* `aep_core/core/intents.py:608-641`.  It re-checks lease, lease TTL,      *)
(* version, status, binding and -- line `:639` -- the authorization value.  *)
(* An absent authorization defaults to a value that cannot match, so it     *)
(* fails closed (`:1186`).                                                  *)
PreflightOk(w) ==
    /\ store.lock = w
    /\ store.version = ctx[w].v
    /\ store.status[ctx[w].i] = ATF
    /\ store.auth = [w |-> w, i |-> ctx[w].i, v |-> ctx[w].v]

Preflight(w) ==
    /\ pc[w] = AUTHZ
    /\ PreflightOk(w)
    /\ pc' = [pc EXCEPT ![w] = READY]
    /\ UNCHANGED <<store, disk, minted, effect, ctx>>

(* The preflight rejected.  `aep_core/core/intent_workflow.py:505-526`: a   *)
(* failed preflight is definitive only if this worker still owns the lease, *)
(* in which case it persists FAILED_CONFIRMED with reason                   *)
(* "pre-dispatch-preflight-failure"; otherwise it raises and leaves the     *)
(* intent for recovery.  This is a SECOND no-dispatch path to               *)
(* FAILED_CONFIRMED that section IV does not mention -- README section 6,   *)
(* finding F2.                                                              *)
PreflightRejects(w) ==
    /\ pc[w] = AUTHZ
    /\ ~PreflightOk(w)
    /\ pc' = [pc EXCEPT ![w] = IDLE]
    /\ IF /\ store.lock = w
          /\ store.version = ctx[w].v
          /\ store.status[ctx[w].i] = ATF
          /\ store.version < MaxVersion
       THEN /\ store' = [store EXCEPT !.version = store.version + 1,
                                      !.status[ctx[w].i] = FAC]
            /\ disk' = Fsync(store')
       ELSE UNCHANGED <<store, disk>>
    /\ ctx' = [ctx EXCEPT ![w] = [i |-> NoIntent, v |-> 0, ev |-> NoEv]]
    /\ UNCHANGED <<minted, effect>>

(* Steps 7-8: mint the single-use capability and call the connector.        *)
(*                                                                          *)
(* THE NON-COOPERATIVE ENDPOINT.  Note what this action does not do.  It    *)
(* does not read `store`.  It does not read `minted`.  It does not consult  *)
(* any earlier effect.  The endpoint is therefore incapable of              *)
(* deduplicating: if this action runs twice, two effects exist.  Nothing    *)
(* AEP can send changes that, which is the sense in which the endpoint      *)
(* cannot be enrolled in the protocol.                                       *)
Transmit(w) ==
    /\ pc[w] = READY
    /\ \E applied \in BOOLEAN :
         effect' = [effect EXCEPT ![ctx[w].i] = applied]
    /\ pc' = [pc EXCEPT ![w] = INFLIGHT]
    /\ UNCHANGED <<store, disk, minted, ctx>>

(* The evidence the caller may see.  "AMBIGUOUS" is in every set, so the    *)
(* caller can never rely on receiving a definitive answer.  When            *)
(* TruthfulEndpoint is FALSE the evidence is unconstrained by what actually *)
(* happened -- docs/22 section 5.1 and R2-4: FIRED_CONFIRMED and            *)
(* FAILED_CONFIRMED come from declared evidence with no independent         *)
(* verification.                                                             *)
AllowedEvidence(i) ==
    IF TruthfulEndpoint
    THEN IF effect[i] THEN {"SUCCESS", "AMBIGUOUS"} ELSE {"FAILURE", "AMBIGUOUS"}
    ELSE Evidence

Receive(w) ==
    /\ pc[w] = INFLIGHT
    /\ \E ev \in AllowedEvidence(ctx[w].i) :
         ctx' = [ctx EXCEPT ![w].ev = ev]
    /\ pc' = [pc EXCEPT ![w] = ANSWERED]
    /\ UNCHANGED <<store, disk, minted, effect>>

(* Classification at the runner, `aep_core/core/intent_workflow.py:578-616`: *)
(* declared success -> FIRED_CONFIRMED, declared failure -> FAILED_CONFIRMED,*)
(* everything else INCLUDING every exception -> FIRED_UNCONFIRMED.          *)
(* Ambiguity is the default, not a special case.                            *)
RunnerTarget(ev) ==
    CASE ev = "SUCCESS" -> FC
      [] ev = "FAILURE" -> FAC
      [] OTHER          -> FU

Resolve(w) ==
    /\ pc[w] = ANSWERED
    /\ store.lock = w
    /\ store.version = ctx[w].v
    /\ store.status[ctx[w].i] = ATF
    /\ store.version < MaxVersion
    /\ LET tgt == RunnerTarget(ctx[w].ev) IN
         /\ store' = [store EXCEPT !.version = store.version + 1,
                                   !.status[ctx[w].i] = tgt]
         /\ disk' = Fsync(store')
    /\ pc' = [pc EXCEPT ![w] = IDLE]
    /\ ctx' = [ctx EXCEPT ![w] = [i |-> NoIntent, v |-> 0, ev |-> NoEv]]
    /\ UNCHANGED <<minted, effect>>

(* The resolution CAS was refused -- the lease was lost or the version      *)
(* moved.  The worker cannot persist its own outcome; the intent is left    *)
(* ABOUT_TO_FIRE for recovery.  This is the case docs/06-phase2-design      *)
(* :333-337 is about.                                                       *)
ResolveRejected(w) ==
    /\ pc[w] = ANSWERED
    /\ ~( /\ store.lock = w
          /\ store.version = ctx[w].v
          /\ store.status[ctx[w].i] = ATF
          /\ store.version < MaxVersion )
    /\ pc' = [pc EXCEPT ![w] = IDLE]
    /\ ctx' = [ctx EXCEPT ![w] = [i |-> NoIntent, v |-> 0, ev |-> NoEv]]
    /\ UNCHANGED <<store, disk, minted, effect>>

-----------------------------------------------------------------------------
(***************************************************************************)
(* FAULTS.  F1-F5 of docs/22 section 2 / section III of the manuscript.     *)
(***************************************************************************)

(* F1 -- worker crash at any instruction boundary.  Local context is lost;  *)
(* the lease is NOT released, because a killed process runs no `finally`.   *)
Crash(w) ==
    /\ pc[w] # IDLE
    /\ pc' = [pc EXCEPT ![w] = IDLE]
    /\ ctx' = [ctx EXCEPT ![w] = [i |-> NoIntent, v |-> 0, ev |-> NoEv]]
    /\ UNCHANGED <<store, disk, minted, effect>>

(* F5 -- the lease expires, or is released.  Modelled as possible at any    *)
(* moment, which is strictly more adversarial than the real TTL budget      *)
(* T_client <= T_lock - Buffer_Margin.  README section 5, exclusion 3.      *)
LeaseExpires ==
    /\ store.lock # NoLock
    /\ store' = [store EXCEPT !.lock = NoLock]
    /\ UNCHANGED <<disk, minted, effect, pc, ctx>>

(* The `appendfsync everysec` background flush: the durable prefix advances *)
(* on its own, without anyone asking.  Together with Restart this gives the *)
(* prefix semantics of an append-only file -- a write is lost only if it    *)
(* falls after the last flush.                                             *)
BackgroundFsync ==
    /\ disk' = store
    /\ UNCHANGED <<store, minted, effect, pc, ctx>>

(* F3 -- Redis restarts and replays the AOF.  Enabled only when             *)
(* SingleTimeline is FALSE.  P1 is a statement about ONE monotonic Redis    *)
(* timeline (docs/22 R1-3); this action is what removing that assumption    *)
(* looks like.  `minted` is deliberately not rewound: a crashed Redis does  *)
(* not cause a UUID to be drawn twice.                                     *)
Restart ==
    /\ ~SingleTimeline
    /\ store' = disk
    /\ UNCHANGED <<disk, minted, effect, pc, ctx>>

-----------------------------------------------------------------------------
(***************************************************************************)
(* THE RECOVERY SERVICE.  `IntentRecoveryService.recover_intent`,           *)
(* `aep_core/core/intent_recovery.py:379-521`.                              *)
(*                                                                          *)
(* Each recovery write is modelled as one atomic action that takes the      *)
(* lease and gives it back.  That abstraction is sound here because every   *)
(* recovery write is independently fenced by the same CAS and separately    *)
(* barriered, and recovery is read-only with respect to the endpoint: a     *)
(* crash between two recovery writes is observationally identical to simply *)
(* not performing the later one, which the model already allows.  README    *)
(* section 5, exclusion 5, states this and what it costs.                   *)
(***************************************************************************)

(* A stale ABOUT_TO_FIRE is first CLAIMED by a durable CAS to               *)
(* FIRED_UNCONFIRMED with reason "orphaned-about-to-fire"                   *)
(* (`aep_core/core/intent_recovery.py:379-396`).  This advances the version *)
(* and consumes the lease, which is what stops a late original worker from  *)
(* persisting its own resolution.                                          *)
(* THE ONE REAL-TIME ASSUMPTION IN THE MODEL, MADE EXPLICIT.                *)
(*                                                                          *)
(* An intent is eligible for recovery only once `now >= reconcile_after`    *)
(* (`aep_core/core/intent_recovery.py:150-151`), and reconcile_after is set *)
(* at creation to `prepared_at + client_timeout + buffer_margin +           *)
(* settlement_lag` (`aep_core/core/intents.py:836-841`).  That delay exists *)
(* to cover the creating worker's whole dispatch window, so recovery cannot *)
(* claim an intent whose worker may still be about to transmit.             *)
(*                                                                          *)
(* This model is untimed, so the delay cannot be expressed as a duration.   *)
(* `InFlightAt` expresses what the delay BUYS instead: no live worker is    *)
(* still holding that intent short of a resolution.  Setting                *)
(* ReconcileDelayCovers to FALSE removes the assumption, and TLC then       *)
(* produces the scheduling gap the design already declares --               *)
(* `docs/06-phase2-design.md:249-252`, docs/22 F5 -- as a concrete lost     *)
(* effect.  README section 4, run 7.                                        *)
InFlightAt(i) ==
    \E w \in Workers :
        /\ ctx[w].i = i
        /\ pc[w] \in {INTENT, ACKED, AUTHZ, READY, INFLIGHT, ANSWERED}

RecoveryClaim ==
    /\ store.lock = NoLock
    /\ store.version < MaxVersion
    /\ \E i \in IntentIds :
        /\ store.status[i] = ATF
        /\ ReconcileDelayCovers => ~InFlightAt(i)
        /\ store' = [store EXCEPT !.version = store.version + 1,
                                  !.status[i] = FU,
                                  !.tries[i] = 0]
    /\ disk' = Fsync(store')
    /\ UNCHANGED <<minted, effect, pc, ctx>>

(* What a read-back may return.  A truthful AUTHORITATIVE endpoint can      *)
(* prove absence; a truthful POSITIVE_ONLY endpoint cannot, and NOT_APPLIED *)
(* from one is a connector DEFECT -- which the code names rather than       *)
(* letting it fall through (`connector_contract.py:218-224`).  It is kept   *)
(* reachable in every configuration precisely so that named branch is       *)
(* exercised rather than assumed (docs/26 section 3 rule 13).  UNKNOWN is   *)
(* always reachable: `intent_recovery.py:459-460` swallows a read-back that *)
(* raises into UNKNOWN, so it consumes budget rather than asserting.        *)
AllowedReadback(i) ==
    IF TruthfulEndpoint
    THEN (IF effect[i] THEN {"APPLIED"} ELSE {"NOT_APPLIED"})
         \cup {"UNKNOWN", "CONFLICT"}
         \cup (IF Capability = "POSITIVE_ONLY_READBACK" THEN {"NOT_APPLIED"} ELSE {})
    ELSE Readback

(* The classification table, `classify_readback`                            *)
(* (`aep_core/core/connector_contract.py:171-240`) composed with the        *)
(* recovery budget test (`intent_recovery.py:478-487`).  Total: every       *)
(* (capability, result) pair has an explicit outcome.  This is              *)
(* Table `tab:classification` in section IV.                                *)
ClassifiedTarget(i, r) ==
    CASE r = "APPLIED"     -> FC
      [] r = "CONFLICT"    -> PA
      [] r = "NOT_APPLIED" -> IF Capability = "AUTHORITATIVE_READBACK" THEN FAC ELSE PA
      [] OTHER             -> IF store.tries[i] + 1 >= MaxAttempts THEN PA ELSE FU

(* A connector whose capability is undeclared or unrecognised, and a        *)
(* NO_READBACK connector, are both escalated WITHOUT any query at all       *)
(* (`intent_recovery.py:403-437`).  Declared ambiguity by design, not by    *)
(* failure -- the two bold rows of Table `tab:classification`.              *)
RecoveryEscalateNoQuery ==
    /\ Capability \in {"NO_READBACK", "UNDECLARED"}
    /\ store.lock = NoLock
    /\ store.version < MaxVersion
    /\ \E i \in IntentIds :
        /\ store.status[i] = FU
        /\ store' = [store EXCEPT !.version = store.version + 1, !.status[i] = PA]
    /\ disk' = Fsync(store')
    /\ UNCHANGED <<minted, effect, pc, ctx>>

RecoveryReadback ==
    /\ Capability \in {"AUTHORITATIVE_READBACK", "POSITIVE_ONLY_READBACK"}
    /\ store.lock = NoLock
    /\ store.version < MaxVersion
    /\ \E i \in IntentIds :
        /\ store.status[i] = FU
        /\ store.tries[i] < MaxAttempts
        /\ \E r \in AllowedReadback(i) :
             LET tgt == ClassifiedTarget(i, r) IN
             store' = [store EXCEPT !.version = store.version + 1,
                                    !.status[i] = tgt,
                                    !.tries[i] = IF r = "UNKNOWN"
                                                 THEN store.tries[i] + 1
                                                 ELSE store.tries[i]]
    /\ disk' = Fsync(store')
    /\ UNCHANGED <<minted, effect, pc, ctx>>

(* The operator edges out of PERMANENTLY_AMBIGUOUS                          *)
(* (`aep_core/core/intents.py:87-94`).  docs/22 section 5.3: the operator   *)
(* is UNAUTHENTICATED -- `actor` is validated only as a bounded safe        *)
(* identifier -- so any caller holding the lease and the current version    *)
(* can drive this edge.  Nothing in the protocol checks that the operator's *)
(* assertion is true.  Off in the protocol-only configurations.             *)
OperatorResolve ==
    /\ OperatorEnabled
    /\ store.lock = NoLock
    /\ store.version < MaxVersion
    /\ \E i \in IntentIds :
        /\ store.status[i] = PA
        /\ \E tgt \in {FC, FAC} :
             store' = [store EXCEPT !.version = store.version + 1, !.status[i] = tgt]
    /\ disk' = Fsync(store')
    /\ UNCHANGED <<minted, effect, pc, ctx>>

-----------------------------------------------------------------------------
Next ==
    \/ \E w \in Workers :
         \/ AcquireLease(w) \/ CreateIntent(w) \/ Barrier(w) \/ BarrierFails(w)
         \/ Authorize(w)    \/ Preflight(w)    \/ PreflightRejects(w)
         \/ Transmit(w)     \/ Receive(w)      \/ Resolve(w) \/ ResolveRejected(w)
         \/ Crash(w)
    \/ LeaseExpires \/ BackgroundFsync \/ Restart
    \/ RecoveryClaim \/ RecoveryReadback \/ RecoveryEscalateNoQuery
    \/ OperatorResolve

Spec == Init /\ [][Next]_vars

(* Fairness for the liveness property only.                                 *)
(*                                                                          *)
(* The recovery actions get STRONG fairness, and the reason is assumption   *)
(* A3 rather than convenience.  Recovery competes for the same lease as     *)
(* every worker (`aep_core/core/intent_recovery.py:321-333`), so it is      *)
(* enabled only in states where the lock is free -- infinitely often, but   *)
(* not continuously.  Weak fairness says nothing about an action that keeps *)
(* being disabled, so under WF a behaviour in which workers take the lease  *)
(* forever starves recovery, and TLC reports it.  That behaviour is exactly *)
(* what A3 ("the lease is eventually obtainable") assumes away, and         *)
(* docs/22 R3-3 records that lease contention does not consume the P3       *)
(* budget, so nothing in the code bounds it either.  SF is therefore the    *)
(* honest encoding of an assumption the implementation genuinely makes and  *)
(* does not enforce.  README section 5, exclusion 4.                        *)
(*                                                                          *)
(* WF on LeaseExpires is the TTL: a lease held by a dead worker does expire.*)
(*                                                                          *)
(* WF on WorkerStep says a worker that has begun an attempt eventually      *)
(* finishes it, abandons it, or dies -- it does not stall in the middle for *)
(* ever.  Crash is a disjunct precisely so that the condition is            *)
(* satisfiable at every location, which makes this an assumption about      *)
(* SCHEDULING rather than about the worker succeeding.                      *)
(*                                                                          *)
(* Without it, `InFlightAt` lets one indefinitely stalled worker block      *)
(* recovery for ever, and TLC finds that.  In the real system it cannot     *)
(* happen, because eligibility is a wall-clock test against reconcile_after *)
(* and an indefinitely stalled worker is exactly what F5 assumes: after the *)
(* delay elapses recovery proceeds whether the worker has stalled or not.   *)
(* This clause and `ReconcileDelayCovers` are two halves of the same        *)
(* real-time assumption, and both are listed as such in README section 5.   *)
WorkerStep(w) ==
    \/ CreateIntent(w) \/ Barrier(w) \/ BarrierFails(w) \/ Authorize(w)
    \/ Preflight(w) \/ PreflightRejects(w) \/ Transmit(w) \/ Receive(w)
    \/ Resolve(w) \/ ResolveRejected(w) \/ Crash(w)

FairSpec ==
    /\ Spec
    /\ SF_vars(RecoveryClaim)
    /\ SF_vars(RecoveryReadback)
    /\ SF_vars(RecoveryEscalateNoQuery)
    /\ WF_vars(LeaseExpires)
    /\ \A w \in Workers : WF_vars(WorkerStep(w))

-----------------------------------------------------------------------------
(***************************************************************************)
(* PROPERTIES.                                                              *)
(*                                                                          *)
(* Which are checked in which configuration, and which are EXPECTED to fail *)
(* where, is in `formal/README.md` section 4 and encoded in                  *)
(* `formal/configs/*.cfg`.                                                   *)
(***************************************************************************)

(*-- P1: fenced state -------------------------------------------------------*)

(* P1's core is that there is one monotonic timeline.  Stated as an action  *)
(* property so that a rewind is a violation rather than a silent reset.     *)
P1_VersionMonotone == [][store'.version >= store.version]_vars

Rank(s) ==
    CASE s = NONE_STATE -> 0
      [] s = ATF        -> 1
      [] s = FU         -> 2
      [] OTHER          -> 3

(* "No committed state write can be superseded and then RESURRECTED by a    *)
(* stale writer."  A resurrection is a status moving backwards.             *)
P1_NoStatusRegression ==
    [][\A i \in IntentIds : Rank(store'.status[i]) >= Rank(store.status[i])]_vars

(*-- P2: detectable ambiguity ----------------------------------------------*)

(* Every status change follows a declared edge.  The transition table is    *)
(* re-checked inside the atomic Lua script, not only by the caller.         *)
P2_LegalEdgesOnly ==
    [][\A i \in IntentIds :
         store'.status[i] # store.status[i]
            => <<store.status[i], store'.status[i]>> \in LegalTransitions]_vars

(* "Never silently re-dispatched": there is no edge back into               *)
(* ABOUT_TO_FIRE.  A fresh intent is a different intent id, which the       *)
(* creation fence gates.                                                    *)
P2_NoReentry ==
    [][\A i \in IntentIds :
         store'.status[i] = ATF => store.status[i] \in {NONE_STATE, ATF}]_vars

(* "Never silently dropped", the safety half: at most one intent for the    *)
(* step is unresolved at a time, so no attempt can be forgotten by being    *)
(* overtaken (`aep_core/core/intents.py:573-599`).                          *)
P2_AtMostOneUnresolved ==
    Cardinality({i \in IntentIds : store.status[i] \in Unresolved}) <= 1

(* The liveness half.  A durable ABOUT_TO_FIRE is eventually assigned one   *)
(* of the three automated terminal states.  This is the property that needs *)
(* assumptions A1-A3 -- see FairSpec.                                        *)
(*                                                                          *)
(* THE DISJUNCT IS A MODELLING ARTIFACT AND WEAKENS THE CLAIM.  `version`   *)
(* is bounded by MaxVersion so that the state space is finite, and every    *)
(* action that resolves an intent consumes a version.  A behaviour that     *)
(* exhausts the budget therefore deadlocks for a reason belonging to the    *)
(* model, not to the protocol, and without the disjunct TLC reports that    *)
(* artifact as a liveness violation.  What this property establishes is     *)
(* consequently narrower than it looks: no reachable state leaves a durable *)
(* intent unresolved for a reason internal to the protocol, WITHIN the      *)
(* version budget.  It is not a proof of termination in an unbounded run.   *)
(* README section 5, exclusion 6.                                           *)
P2_EventuallyResolved ==
    \A i \in IntentIds :
        (disk.status[i] = ATF)
            ~> (store.status[i] \in Terminal \/ store.version = MaxVersion)

(* NON-VACUITY.  `P2_EventuallyResolved` is an implication, so it passes     *)
(* trivially in any configuration where its antecedent is unreachable -- a   *)
(* durable ABOUT_TO_FIRE never existing would make the liveness result       *)
(* meaningless while reporting success, which is the exact shape of a gate   *)
(* that cannot fail.                                                         *)
(*                                                                          *)
(* This is not a property of the protocol.  It is an invariant that MUST BE  *)
(* VIOLATED, and its counterexample is a witness that a durable              *)
(* ABOUT_TO_FIRE is reachable.  The `vacuity-*` configurations check it and  *)
(* declare `EXPECT: fail`; if one of them ever passes, the corresponding     *)
(* liveness result has stopped meaning anything and run_tlc.sh says so.      *)
NoDurableIntentExists == \A i \in IntentIds : disk.status[i] # ATF

(*-- P3: fail-closed bound --------------------------------------------------*)

P3_BoundedAttempts ==
    /\ \A i \in IntentIds : store.tries[i] <= MaxAttempts
    /\ \A i \in IntentIds : store.status[i] = FU => store.tries[i] < MaxAttempts

(*-- The trilemma -----------------------------------------------------------*)
(* The paper's claim is that a non-idempotent endpoint forces a choice      *)
(* among three outcomes, and that AEP always takes the third.  These two    *)
(* invariants say the first two never happen; declared ambiguity is what is *)
(* left, and it is not a violation.                                         *)

(* An UNDETECTED duplicate: more than one effect exists for the step and    *)
(* the ledger does not say so.  If any intent is PERMANENTLY_AMBIGUOUS the  *)
(* duplicate has been declared, which is the permitted horn.                *)
NoUndetectedDuplicate ==
    EffectCount >= 2 => \E i \in IntentIds : store.status[i] = PA

(* A LOST effect: the endpoint applied it and the ledger either denies it   *)
(* (FAILED_CONFIRMED) or has no record of it at all (NONE -- the record was *)
(* written and then lost).  ATF and FU are permitted here because they are  *)
(* transient; that they do not persist is P2_EventuallyResolved's job, and  *)
(* the two properties are only meaningful together.                         *)
NoLostEffect ==
    \A i \in IntentIds : effect[i] => store.status[i] \notin {NONE_STATE, FAC}

Trilemma == NoUndetectedDuplicate /\ NoLostEffect

=============================================================================
