"""Build the raw evidence archive: every run directory the paper's numbers rest on.

Why this exists
---------------
`ARTIFACT.md` §5 records that the 432 raw run directories, `results/voided/` and
the Phase-8/9/10 collections "are not committed and no working DOI or archive
URL exists". They exist on exactly one host. Phase 10 then established that this
host is degrading on four independent surfaces. Those two facts together are the
reason this script was written before anything else in Phase 11: if the host is
lost, no later phase is possible.

What it guarantees
------------------
* **Read-only.** It opens every source file for reading and writes nothing
  outside `--output`. `--verify-sources-unchanged` re-digests the sources
  afterwards and compares them against the manifest, so "nothing under a raw run
  directory was modified" is proved rather than asserted.
* **Deterministic.** Entries are emitted in sorted path order; `uid`/`gid` are
  zeroed and `uname`/`gname` emptied; modes are normalised to 0644/0755; the
  gzip member header carries `mtime=0`. Re-running against an unchanged source
  tree produces byte-identical output.
* **mtimes are preserved, deliberately.** They are not noise here: Phase 11
  step 3 recovers each collection's storage backing partly from file timestamps
  against known collection windows, and `docs/24-revision-backlog.md` B15 already
  turns on mtime evidence. Normalising them would destroy evidence in order to
  buy a determinism the sorted-entry rule already provides.

What it does not do
-------------------
It does not upload, tag, or mint a DOI. That is WS-2.2 and the next phase.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from dataclasses import dataclass, field
from pathlib import Path

#: Read in 1 MiB blocks; the largest single artefact in the corpus is a few MB.
_BLOCK = 1024 * 1024

#: Normalised permissions. The source trees carry a mix of 0777 (drvfs, which
#: cannot represent Unix modes) and 0644/0755 (ext4). Neither is evidence.
_FILE_MODE = 0o644
_DIR_MODE = 0o755


@dataclass(frozen=True)
class Root:
    """One collection root to archive.

    `label` is the archive-internal directory name. It is chosen here rather
    than taken from the source path, because two source paths carry the same
    collection name (`b2-s2-2026-08-21` exists twice) and because a name is not
    evidence of anything -- `note` carries what is actually known.
    """

    label: str
    source: str
    #: The tracked analysis directory this root's raw runs produced, if any.
    #: `None` means no tracked file in the repository was derived from it.
    tracked_analysis: str | None
    note: str


#: Every raw run directory on this host, from the Phase 11 survey
#: (`reports/raw/phase11-raw-survey.txt`). Phase 10's storage-backing
#: enumeration was the starting list; what it missed is marked below.
ROOTS: tuple[Root, ...] = (
    Root(
        label="matrix",
        source="/root/aep/experiments/results/matrix",
        tracked_analysis="experiments/results/matrix/analysis",
        note=(
            "The evaluation. 432 runs / 3780 executions / 126 cells; every "
            "outcome rate in the manuscript is computed from this root's "
            "analysis products. The working clone also holds 84 run "
            "directories under the same name; they are an OLDER and INCOMPLETE "
            "snapshot (no per-worker attempt logs, and one run at a pre-E5 "
            "config schema) and are excluded -- see EXCLUDED below."
        ),
    ),
    Root(
        label="fsync-always",
        source="/root/aep/experiments/results/fsync-always",
        tracked_analysis="experiments/results/fsync-always/analysis",
        note=(
            "The appendfsync=always arm. Source of every 'always' latency and "
            "throughput number and of the barrier-cost decomposition."
        ),
    ),
    Root(
        label="voided",
        source="/root/aep/experiments/results/voided",
        tracked_analysis=None,
        note=(
            "results/voided/. One run, excluded from the evaluation for oracle "
            "disagreement, with its README.md explanation. ARTIFACT.md 5 "
            "requires the published archive to contain it."
        ),
    ),
    Root(
        label="b2-2026-08-21",
        source=(
            "/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/"
            "b2-2026-08-21"
        ),
        tracked_analysis="experiments/results/b2-2026-08-21/analysis",
        note="Phase 9C prevention replication, session 0.",
    ),
    Root(
        label="b2-s1-2026-08-21",
        source=(
            "/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/"
            "b2-s1-2026-08-21"
        ),
        tracked_analysis="experiments/results/b2-s1-2026-08-21/analysis",
        note="Phase 9C prevention replication, session 1.",
    ),
    Root(
        label="b2-s2-2026-08-21",
        source=(
            "/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/"
            "b2-s2-2026-08-21"
        ),
        tracked_analysis="experiments/results/b2-s2-2026-08-21/analysis",
        note=(
            "Phase 9C prevention replication, session 2. /root/phase82-verify/"
            "b2-s2 is a byte-identical copy of this root and is excluded as a "
            "duplicate, not dropped as unwanted."
        ),
    ),
    Root(
        label="b2-s3-2026-08-21",
        source=(
            "/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/"
            "b2-s3-2026-08-21"
        ),
        tracked_analysis="experiments/results/b2-s3-2026-08-21/analysis",
        note="Phase 9C prevention replication, session 3.",
    ),
    Root(
        label="b2-paired-s1-2026-08-28",
        source="/root/aep-phase8/experiments/results/b2-paired-s1-2026-08-28",
        tracked_analysis="experiments/results/b2-paired-s1-2026-08-28/analysis",
        note="Phase 8.4 paired prevention collection, session 1 (v1 design).",
    ),
    Root(
        label="b2-paired-v2-s1-2026-08-28",
        source="/root/aep-phase8/experiments/results/b2-paired-v2-s1-2026-08-28",
        tracked_analysis="experiments/results/b2-paired-v2-s1-2026-08-28/analysis",
        note="Phase 8.4 paired prevention collection, v2 session 1.",
    ),
    Root(
        label="b2-paired-v2-s2-2026-08-28",
        source="/root/aep-phase8/experiments/results/b2-paired-v2-s2-2026-08-28",
        tracked_analysis="experiments/results/b2-paired-v2-s2-2026-08-28/analysis",
        note="Phase 8.4 paired prevention collection, v2 session 2.",
    ),
    Root(
        label="b2-paired-v2-s3-2026-08-28",
        source="/root/aep-phase8/experiments/results/b2-paired-v2-s3-2026-08-28",
        tracked_analysis="experiments/results/b2-paired-v2-s3-2026-08-28/analysis",
        note="Phase 8.4 paired prevention collection, v2 session 3.",
    ),
    Root(
        label="b2-paired-v2-s4-2026-08-28",
        source="/root/aep-phase8/experiments/results/b2-paired-v2-s4-2026-08-28",
        tracked_analysis="experiments/results/b2-paired-v2-s4-2026-08-28/analysis",
        note="Phase 8.4 paired prevention collection, v2 session 4.",
    ),
    Root(
        label="b2-paired-v2-s2-aborted-2026-08-28",
        source=(
            "/root/aep-phase8/experiments/results/"
            "b2-paired-v2-s2-aborted-2026-08-28"
        ),
        tracked_analysis=(
            "experiments/results/b2-paired-v2-s2-aborted-2026-08-28/analysis"
        ),
        note=(
            "Aborted v2 session 2. Its own run-config.json records "
            "results_root=b2-paired-v2-s2-2026-08-28; the directory was renamed "
            "after collection. The recorded field is the truthful one."
        ),
    ),
    Root(
        label="b2-paired-v2-s2-operator-aborted-2026-08-28",
        source=(
            "/root/aep-phase8/experiments/results/"
            "b2-paired-v2-s2-operator-aborted-2026-08-28"
        ),
        tracked_analysis=None,
        note=(
            "Operator-aborted v2 session 2, 16 runs. No analysis product of it "
            "is tracked, so no manuscript number depends on it -- but it is a "
            "real collection on the real instrument and is archived so the "
            "record of what was discarded is as complete as the record of what "
            "was kept."
        ),
    ),
    Root(
        label="phase10-replication-ext4-2026-09-02",
        source="/root/aep-phase10/ext4-2026-09-02",
        tracked_analysis=(
            "experiments/results/phase10-replication-ext4-2026-09-02/analysis"
        ),
        note=(
            "Phase 10 runtime-confound replication, ext4 arm, matched (18 runs). "
            "Collected here, on the distro's own ext4, and copied into the "
            "repository afterwards; the copy is excluded as a duplicate."
        ),
    ),
    Root(
        label="phase10-replication-ext4-arbb30-2026-09-02",
        source="/root/aep-phase10/ext4-2026-09-02-arbb30",
        tracked_analysis=(
            "experiments/results/phase10-replication-ext4-arbb30-2026-09-02/"
            "analysis"
        ),
        note="Phase 10 ext4 arm, powered cell (30 runs).",
    ),
    Root(
        label="phase10-replication-drvfs-2026-09-02",
        source=(
            "/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/"
            "phase10-replication-drvfs-2026-09-02"
        ),
        tracked_analysis=(
            "experiments/results/phase10-replication-drvfs-2026-09-02/analysis"
        ),
        note="Phase 10 drvfs arm, matched (18 runs). Collected in the repo tree.",
    ),
    Root(
        label="phase10-replication-drvfs-arbb30-2026-09-02",
        source=(
            "/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/"
            "phase10-replication-drvfs-arbb30-2026-09-02"
        ),
        tracked_analysis=(
            "experiments/results/phase10-replication-drvfs-arbb30-2026-09-02/"
            "analysis"
        ),
        note="Phase 10 drvfs arm, powered cell (30 runs).",
    ),
    Root(
        label="phase10-VOIDED-ext4-wrong-runtime",
        source="/root/aep-phase10/VOIDED/ext4-2026-09-02-VOID-wrong-runtime",
        tracked_analysis=None,
        note=(
            "VOIDED. Collected against Docker Desktop's Redis while the native "
            "container sat in state 'created'; never committed. Archived "
            "because the Phase 10 report cites it for the same-day "
            "Docker-Desktop-served clock-divergence comparison, and because a "
            "voided collection is evidence about the instrument."
        ),
    ),
    Root(
        label="phase10-VOIDED-ext4-arbb30-wrong-runtime",
        source=(
            "/root/aep-phase10/VOIDED/ext4-2026-09-02-arbb30-VOID-wrong-runtime"
        ),
        tracked_analysis=None,
        note="VOIDED, same incident, powered cell (23 runs written before the stop).",
    ),
)



#: The 2026-09-03 archive covered twenty roots from three trees. Phase 34's
#: inventory found five referenced trees outside it, and three of those back
#: claims the manuscript makes. This is that gap, built as a SEPARATE
#: archive with its own manifest so the original is never reopened and its
#: digest still verifies over exactly the bytes it always covered.
#:
#: Voided collections are included, on the precedent the original set: a
#: voided collection is evidence about the instrument.
EXTENSION_ROOTS: tuple[Root, ...] = (
    Root(
        label="ws4-writeloss-s1-2026-09-07-a5",
        source="/root/aep-phase14/writeloss-s1-2026-09-07-a5",
        tracked_analysis="reports/raw/ws4-writeloss-s1-2026-09-07",
        note=(
            "WS-4's host-level write-loss protocol cell. Section VI-C's "
            "numbers come from this root's analysis products, and the "
            "manuscript's write-loss macros name it by path. "
        ),
    ),
    Root(
        label="ws4-writeloss-s1-2026-09-07-a5-voided-1",
        source="/root/aep-phase14/writeloss-s1-2026-09-07-a5-voided-1",
        tracked_analysis=None,
        note=(
            "The voided first attempt of the same cell, retained because a "
            "voided collection is evidence about the instrument. "
        ),
    ),
    Root(
        label="ws6-b5-s1-2026-09-08-attempt3",
        source="/root/aep-ws6/b5-s1-2026-09-08-attempt3",
        tracked_analysis="reports/raw/ws6-b5-s1-2026-09-08-attempt3",
        note=(
            "WS-6's real-Temporal baseline. Section VI-A's B5 comparison and "
            "every B5 macro come from this root. "
        ),
    ),
    Root(
        label="ws6-b5-s1-2026-09-08-attempt2",
        source="/root/aep-ws6/b5-s1-2026-09-08-attempt2",
        tracked_analysis=None,
        note=(
            "The second attempt, superseded by attempt 3 and retained as "
            "evidence about the instrument. "
        ),
    ),
    Root(
        label="ws6-b5-s1-2026-09-08-VOIDED-attempt1",
        source="/root/aep-ws6/VOIDED-b5-s1-2026-09-08-attempt1",
        tracked_analysis=None,
        note=(
            "The voided first attempt; its own phase report explains why. "
        ),
    ),
    Root(
        label="phase13-armA-s1-2026-09-03",
        source="/root/aep-phase13/armA-s1-2026-09-03",
        tracked_analysis="experiments/results/phase13-armA-s1-2026-09-03/analysis",
        note=(
            "Controlled-fault prevention replication, session 1. The "
            "replication interval quoted in the threats section is computed "
            "across the three armA sessions. "
        ),
    ),
    Root(
        label="phase13-armA-s2-2026-09-03",
        source="/root/aep-phase13/armA-s2-2026-09-03",
        tracked_analysis="experiments/results/phase13-armA-s2-2026-09-03/analysis",
        note=(
            "Session 2 of the same replication. "
        ),
    ),
    Root(
        label="phase13-armA-s3-2026-09-03",
        source="/root/aep-phase13/armA-s3-2026-09-03",
        tracked_analysis="experiments/results/phase13-armA-s3-2026-09-03/analysis",
        note=(
            "Session 3 of the same replication. "
        ),
    ),
    Root(
        label="phase13-armA-s3-VOIDED-killed-at-152",
        source="/root/aep-phase13/VOIDED/armA-s3-2026-09-03-VOID-killed-at-152",
        tracked_analysis=None,
        note=(
            "The voided session 3 attempt, stopped at run 152. "
        ),
    ),
    Root(
        label="phase13-inflight-s1-2026-09-04",
        source="/root/aep-phase13/inflight-s1-2026-09-04",
        tracked_analysis="experiments/results/phase13-inflight-s1-2026-09-04/analysis",
        note=(
            "The in-flight kill variant, session 1; docs/31 rests on it. "
        ),
    ),
    Root(
        label="phase13-inflight-s2-2026-09-04",
        source="/root/aep-phase13/inflight-s2-2026-09-04",
        tracked_analysis="experiments/results/phase13-inflight-s2-2026-09-04/analysis",
        note=(
            "The in-flight kill variant, session 2. "
        ),
    ),
)


#: Phase 54's THIRD part: the roots neither earlier archive reached.
#:
#: Why a third part and not a rebuild. The 2026-09-03 and 2026-09-15 archives
#: are verified and their digests are already stated in `CITATION.cff`,
#: `ARTIFACT.md`, `README.md` and `docs/29` 1. Rebuilding would change those
#: digests and falsify every one of those statements. Adding a part changes
#: nothing that already exists.
#:
#: How the gap happened, so the list below is read with the right suspicion:
#: `build()` used to hard-code the module-global `EXCLUDED` into every part's
#: metadata, so the extension declared the 2026-09-03 exclusions and said
#: nothing about what IT did not reach. Five of the roots below supply
#: eighteen manuscript macros between them and were absent from both parts
#: while the metadata looked complete.
#:
#: Sources are the repository working tree, not `/root`: these collections were
#: run in place. `run-config.json` in `t1-p0-everysec` records
#: `results_root: /mnt/d/personal/AEP/Research-paper-AEP/experiments/results/
#: ws5-2026-09-10/t1-p0-everysec`, so the tree below IS the collection, not a
#: copy of one.
_REPO = "/mnt/d/personal/AEP/Research-paper-AEP"

PART3_ROOTS: tuple[Root, ...] = (
    Root(
        label="ws5-2026-09-10-t1-p0-everysec",
        source=f"{_REPO}/experiments/results/ws5-2026-09-10/t1-p0-everysec",
        tracked_analysis=(
            "experiments/results/ws5-2026-09-10/t1-p0-everysec/analysis"
        ),
        note=(
            "WS-5's 15-run crash-free everysec arm. Supplies NINE macros, "
            "including BarrierCostFifteen (1,939.7 ms) with its interval and "
            "both ProtocolMinusBarrier triples -- RQ3's headline, which the "
            "external audit of 2026-09-23 recomputed and matched. Absent from "
            "both earlier parts."
        ),
    ),
    Root(
        label="ws5-2026-09-10-t2-p30",
        source=f"{_REPO}/experiments/results/ws5-2026-09-10/t2-p30",
        tracked_analysis="experiments/results/ws5-2026-09-10/t2-p30/analysis",
        note=(
            "The 30% crash-probability regime. Supplies PthirtyComparisons, "
            "PthirtyRuns and PthirtyExecutions."
        ),
    ),
    Root(
        label="ws5-2026-09-10-t2-keying",
        source=f"{_REPO}/experiments/results/ws5-2026-09-10/t2-keying",
        tracked_analysis="experiments/results/ws5-2026-09-10/t2-keying/analysis",
        note=(
            "The alternative read-back keying sensitivity cell. Supplies "
            "KeyingAmbiguityOracle, the 9.33 pp miss against a 5 pp margin "
            "that the manuscript reports as a negative result."
        ),
    ),
    Root(
        label="ws5-2026-09-10-t1-incomplete",
        source=f"{_REPO}/experiments/results/ws5-2026-09-10/t1-incomplete",
        tracked_analysis=(
            "experiments/results/ws5-2026-09-10/t1-incomplete/analysis"
        ),
        note=(
            "The incomplete sibling of t1-p0-everysec. No macro derives from "
            "it. Archived because a discarded collection is evidence about "
            "the instrument, which is the same rule under which the voided "
            "and aborted roots of the first two parts were kept."
        ),
    ),
    Root(
        label="fsync-always-2026-09-14",
        source=f"{_REPO}/experiments/results/fsync-always-2026-09-14",
        tracked_analysis="experiments/results/fsync-always-2026-09-14/analysis",
        note=(
            "The 45-run appendfsync=always arm. Supplies FIVE macros: "
            "BarrierCostAlwaysFortyFive with its interval, and both "
            "AlwaysFortyFive medians. Distinct from the six-run "
            "`fsync-always` root in the 2026-09-03 part, which the "
            "manuscript also cites -- the two are different collections and "
            "Section 6.4 quotes both."
        ),
    ),
    Root(
        label="phase40-stage-10-interactive-2026-09-21",
        source=f"{_REPO}/reports/raw/phase40-stage-10-interactive-2026-09-21",
        tracked_analysis=None,
        note=(
            "Phase 40 stage 10 on the interactive loop. Committed text "
            "evidence; the live collection is outside the repository."
        ),
    ),
    Root(
        label="phase40-stage-30-2026-09-21",
        source=f"{_REPO}/reports/raw/phase40-stage-30-2026-09-21",
        tracked_analysis=None,
        note="Phase 40 stage 30, the first collection under amendment 6.",
    ),
    Root(
        label="phase40-stage-100-2026-09-22",
        source=f"{_REPO}/reports/raw/phase40-stage-100-2026-09-22",
        tracked_analysis=None,
        note=(
            "Phase 40 stage 100 -- the stage that FAILED and closed the "
            "workstream by author decision. No manuscript text depends on it "
            "and none is owed; the closure's restriction is on the "
            "MANIFEST, not on the archive, and its 9 names "
            "reports/raw/phase40-*/ as preserved evidence."
        ),
    ),
    Root(
        label="b2-s4-2026-09-14-ABORTED-order-mismatch",
        source=(
            f"{_REPO}/experiments/results/"
            "b2-s4-2026-09-14-ABORTED-order-mismatch"
        ),
        tracked_analysis=None,
        note=(
            "ABORTED at 19 of 60 runs and NOT a session. Stopped deliberately "
            "on 2026-09-14 when the collection order was found interleaved "
            "while the four existing class-sweep sessions are cell-major -- a "
            "structural difference that would have been pooled into one paired "
            "sign test. Its own ABORTED.md says it must never be counted as a "
            "session and phase report 22 gives the account. NO analysis "
            "directory, and no manuscript number derives from it. Archived on "
            "the precedent it cites, b2-paired-v2-s2-aborted-2026-08-28, that "
            "an aborted collection is evidence about the instrument -- that "
            "precedent is in the 2026-09-03 part, and until 2026-09-25 this "
            "root was in none of the three AND untracked, so it existed on "
            "exactly one disk. Found by auditing what a clean clone carries."
        ),
    ),
)


#: Added when phase 53 lands. Kept separate so that building the part before
#: the collection finishes is impossible by construction rather than by
#: remembering.
PHASE53_ROOT = Root(
    label="abd-immediate-2026-09-24",
    source=f"{_REPO}/experiments/results/abd-immediate-2026-09-24",
    tracked_analysis="experiments/results/abd-immediate-2026-09-24/analysis",
    note=(
        "Phase 53: after_barrier_before_dispatch re-collected for the five "
        "baselines with SIGKILL_IMMEDIATE, because the mapping in "
        "experiments/baselines/crash_points.py delivered the original cell by "
        "the deferred watchdog. Its pre-registration 5 requires that it be "
        "reported as its own session with its own macros and NOT pooled with "
        "the matrix, so the manuscript cites it and the archive must carry it."
    ),
)


@dataclass(frozen=True)
class Excluded:
    path: str
    reason: str


#: Every other directory on this host that holds a `run-config.json`, with why
#: it is not in the archive. The acceptance criterion is that no raw run
#: directory is silently absent.
EXCLUDED: tuple[Excluded, ...] = (
    Excluded(
        "/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/matrix",
        "84 runs. An OLDER, INCOMPLETE copy of the archived `matrix` root: it "
        "lacks the ten per-worker attempt logs each run carries in "
        "/root/aep, and b4_durable_workflow-after_barrier_before_dispatch-"
        "payments-11d6b7e1-r2 there has no summary.json, a shorter "
        "ground_truth.run.jsonl and a run-config.json predating the "
        "redis_kill_point/suspend_disabled_declared keys (config_digest "
        "bda9f386... against 284e6fb6... in the archived tree). Superseded, "
        "not lost.",
    ),
    Excluded(
        "/root/phase82-verify/b2-s2",
        "60 runs. Byte-identical copy of experiments/results/b2-s2-2026-08-21 "
        "(60/60 run identities match), made during Phase 8.2 verification.",
    ),
    Excluded(
        "/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/"
        "phase10-replication-ext4-2026-09-02",
        "18 runs. Byte-identical copy of the archived /root/aep-phase10/"
        "ext4-2026-09-02 (18/18 run identities match).",
    ),
    Excluded(
        "/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/"
        "phase10-replication-ext4-arbb30-2026-09-02",
        "30 runs. Byte-identical copy of the archived /root/aep-phase10/"
        "ext4-2026-09-02-arbb30 (30/30 run identities match).",
    ),
    Excluded(
        "/root/aep/experiments/results/smoke",
        "6 runs. `make reproduce-smoke` liveness check. Two executions per "
        "cell cannot estimate a rate; no tracked analysis product and no "
        "manuscript number derives from it.",
    ),
    Excluded(
        "/root/aep/experiments/results/matrix-smoke",
        "6 runs. Same: a smoke run of the matrix orchestrator.",
    ),
    Excluded(
        "/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/smoke",
        "6 runs. Same, in the working clone.",
    ),
    Excluded(
        "/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/selfcheck-c5",
        "1 run. Harness self-check; no tracked analysis product.",
    ),
    Excluded(
        "/mnt/d/personal/AEP/Research-paper-AEP/.scratch/reproduce/smoke",
        "7 runs. Transient output of the last `make reproduce-smoke`; "
        "regenerated by that target on every invocation.",
    ),
    Excluded(
        "/root/aep-5b/repo/.scratch/reproduce/smoke",
        "7 runs. Same, in the /root/aep-5b clone.",
    ),
)


#: What the 2026-09-15 extension did not reach, which its own metadata should
#: have said and did not. Recorded here so the record is corrected even though
#: that archive is never reopened: part 3 carries these roots, and part 3's
#: metadata names them as the extension's omission rather than pretending the
#: gap never existed.
EXTENSION_OMITTED: tuple[Excluded, ...] = (
    Excluded(
        "/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/"
        "ws5-2026-09-10",
        "FOUR roots (t1-p0-everysec, t1-incomplete, t2-p30, t2-keying). "
        "MISSED, not declined: the 2026-09-15 extension emitted the "
        "2026-09-03 exclusion list verbatim and declared nothing about its "
        "own coverage. Thirteen manuscript macros derive from these roots. "
        "Carried by the 2026-09-24 part.",
    ),
    Excluded(
        "/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/"
        "fsync-always-2026-09-14",
        "MISSED, same cause. Five manuscript macros derive from it. Carried "
        "by the 2026-09-24 part.",
    ),
)


#: What the 2026-09-24 part itself does not reach. This is the list the two
#: earlier parts each needed and neither had.
PART3_EXCLUDED: tuple[Excluded, ...] = EXCLUDED + EXTENSION_OMITTED + (
    Excluded(
        "/mnt/d/personal/AEP/Research-paper-AEP/reports/raw/"
        "INCIDENT-fsync-always-destroyed-2026-09-14",
        "NOT a collection and deliberately not archived. Quarantined debris "
        "from the 2026-09-14 incident in which a collection script's "
        "default-on clean path deleted the appendfsync=always raw runs; the "
        "runs themselves were recovered from the 2026-09-03 archive and are "
        "in it. No manuscript number derives from the debris, and depositing "
        "a partial copy of runs the record already carries in full would put "
        "two versions of the same evidence under one DOI. The incident is "
        "reported in reports/incident-fsync-always-raw-destroyed-2026-09-14.md "
        "and in the manuscript's Section 9.",
    ),
    Excluded(
        "/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/"
        "stage3-replication-2026-08-13",
        "Stage-3 replication, 2026-08-13, recovered onto main in phase 29's "
        "branch reconciliation. Predates rule 5 and no manuscript macro "
        "derives from it -- check_archive_covers_macros.py confirms zero "
        "provenance comments name it. Left out pending an explicit author "
        "decision rather than archived by default; see "
        "reports/zenodo-deposit-plan-2026-09-24.md 2.",
    ),
    Excluded(
        "/mnt/d/personal/AEP/Research-paper-AEP/experiments/results/"
        "abd-immediate-2026-09-24",
        "PHASE 53, IN FLIGHT AT BUILD TIME. Must be added before deposit: "
        "its pre-registration 5 commits the manuscript to macros computed "
        "from it. This line is the reason a part built today is a REHEARSAL "
        "and not the deposit.",
    ),
    Excluded(
        "/mnt/d/personal/AEP/Research-paper-AEP/reports/raw/"
        "phase40-deployment-2026-09-18",
        "WITHHELD PENDING REDACTION. deployment-show.json carries "
        "`createdBy` and `lastModifiedBy` naming a THIRD PARTY's corporate "
        "e-mail address. Depositing it would publish another person's "
        "personal data under this DOI, and the 2026-09-03 part's own "
        "description states that archive contains no e-mail addresses -- a "
        "standard this part must meet too. The subscription/tenant id in the "
        "same file was already redacted by hand when it was committed; these "
        "two fields were missed. The root is otherwise exactly the evidence "
        "for amendment 1 and should be re-added once the two values are "
        "replaced, at which point this part is rebuilt and its digests "
        "change. Nothing depends on those two fields: amendment 1's finding "
        "is that `model` reports the alias `gpt-5.6-luna` rather than a "
        "version-pinned snapshot, which is a different key in the same file.",
    ),
)


def digest_file(path: Path) -> tuple[str, int]:
    """sha256 and byte length, streaming."""
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            block = handle.read(_BLOCK)
            if not block:
                break
            size += len(block)
            h.update(block)
    return h.hexdigest(), size


def walk_root(root: Root) -> list[tuple[str, Path]]:
    """(archive-relative path, source path) for every regular file, sorted.

    Symlinks are not followed and are reported rather than dereferenced; none
    exist in these trees today, and silently resolving one would put a file in
    the archive under a name it does not have.
    """
    base = Path(root.source)
    entries: list[tuple[str, Path]] = []
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            source = Path(dirpath) / name
            if source.is_symlink():
                raise RuntimeError(
                    f"symlink in a raw run tree, refusing to guess: {source}"
                )
            entries.append((f"{root.label}/{source.relative_to(base).as_posix()}", source))
    entries.sort(key=lambda item: item[0])
    return entries


def _filesystem_of(path: str) -> dict[str, str]:
    """Mount entry backing `path`, from /proc/mounts. Longest prefix wins."""
    best: dict[str, str] = {}
    target = os.path.abspath(path)
    try:
        lines = Path("/proc/mounts").read_text(encoding="utf-8").splitlines()
    except OSError:
        return best
    for line in lines:
        fields = line.split()
        if len(fields) < 4:
            continue
        point = fields[1]
        if target == point or target.startswith(point.rstrip("/") + "/"):
            if len(point) >= len(best.get("mount_point", "")):
                best = {
                    "device": fields[0],
                    "mount_point": point,
                    "type": fields[2],
                    "options": fields[3],
                }
    return best


@dataclass
class RootReport:
    label: str
    source: str
    tracked_analysis: str | None
    note: str
    files: int = 0
    bytes: int = 0
    runs: int = 0
    filesystem: dict[str, str] = field(default_factory=dict)


def build(
    output: Path,
    roots: tuple[Root, ...],
    *,
    compress: bool,
    excluded: tuple[Excluded, ...] = EXCLUDED,
    phase: int = 11,
) -> dict:
    """Build one archive part.

    ``excluded`` is a PARAMETER and not the module global it used to read.
    That was the defect: every part emitted the 2026-09-03 exclusion list
    verbatim, so the extension's ``ARCHIVE-METADATA.json`` declared nothing
    about the roots *it* did not reach. Five roots supplying eighteen
    manuscript macros were therefore missed rather than declined, and the
    metadata's own acceptance criterion -- "no raw run directory is silently
    absent" -- was not met by a file that looked like it was.
    ``scripts/check_archive_covers_macros.py`` is the guard; this is the cause.
    """
    output.mkdir(parents=True, exist_ok=True)
    tar_path = output / "aep-raw-evidence.tar"
    manifest_path = output / "MANIFEST.sha256"
    metadata_path = output / "ARCHIVE-METADATA.json"

    reports: list[RootReport] = []
    plan: list[tuple[str, Path]] = []
    for root in roots:
        source = Path(root.source)
        if not source.is_dir():
            raise SystemExit(f"missing source root: {root.source}")
        entries = walk_root(root)
        report = RootReport(
            label=root.label,
            source=root.source,
            tracked_analysis=root.tracked_analysis,
            note=root.note,
            files=len(entries),
            runs=sum(1 for name, _ in entries if name.endswith("/run-config.json")),
            filesystem=_filesystem_of(root.source),
        )
        reports.append(report)
        plan.extend(entries)
        print(f"  {root.label:44s} {report.runs:4d} runs  {len(entries):6d} files")

    plan.sort(key=lambda item: item[0])

    # Metadata is written before the manifest so the manifest covers it. It
    # deliberately carries no wall-clock stamp: a timestamp inside the archive
    # would make two builds of the same evidence differ.
    metadata = {
        "archive": "aep-raw-evidence",
        "produced_by": "scripts/build_raw_archive.py",
        "phase": phase,
        "host": os.uname().nodename,
        "kernel": os.uname().release,
        "repository_head": _git_head(),
        "roots": [
            {
                "label": r.label,
                "source_path": r.source,
                "source_filesystem": r.filesystem,
                "tracked_analysis": r.tracked_analysis,
                "runs": r.runs,
                "files": r.files,
                "note": r.note,
            }
            for r in reports
        ],
        "excluded": [{"path": e.path, "reason": e.reason} for e in excluded],
        "determinism": (
            "Entries sorted by archive path; uid/gid zeroed, uname/gname "
            "emptied, modes normalised to 0644/0755, gzip member mtime=0. "
            "File mtimes are PRESERVED from the source because they are "
            "evidence for the storage-backing recovery, not noise."
        ),
    }
    metadata_bytes = json.dumps(metadata, indent=2, sort_keys=True).encode() + b"\n"
    metadata_path.write_bytes(metadata_bytes)
    plan.append(("ARCHIVE-METADATA.json", metadata_path))
    plan.sort(key=lambda item: item[0])

    manifest_lines: list[str] = []
    total_bytes = 0
    by_label = {r.label: r for r in reports}

    with tarfile.open(tar_path, "w", format=tarfile.PAX_FORMAT) as tar:
        for archive_name, source in plan:
            sha, size = digest_file(source)
            manifest_lines.append(f"{sha}  {archive_name}")
            total_bytes += size
            label = archive_name.split("/", 1)[0]
            if label in by_label:
                by_label[label].bytes += size
            info = tarfile.TarInfo(name=archive_name)
            info.size = size
            info.mtime = int(source.stat().st_mtime)
            info.mode = _FILE_MODE
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.type = tarfile.REGTYPE
            with source.open("rb") as handle:
                tar.addfile(info, handle)

    manifest_bytes = ("\n".join(manifest_lines) + "\n").encode()
    manifest_path.write_bytes(manifest_bytes)
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    tar_digest, tar_size = digest_file(tar_path)

    result = {
        "manifest": str(manifest_path),
        "manifest_sha256": manifest_digest,
        "manifest_entries": len(manifest_lines),
        "tar": str(tar_path),
        "tar_sha256": tar_digest,
        "tar_bytes": tar_size,
        "payload_bytes": total_bytes,
        "roots": [
            {
                "label": r.label,
                "source": r.source,
                "runs": r.runs,
                "files": r.files,
                "bytes": r.bytes,
                "filesystem": r.filesystem.get("type"),
                "device": r.filesystem.get("device"),
                "tracked_analysis": r.tracked_analysis,
            }
            for r in reports
        ],
        "excluded": [{"path": e.path, "reason": e.reason} for e in excluded],
    }

    if compress:
        gz_path = output / "aep-raw-evidence.tar.gz"
        # mtime=0 in the gzip header: otherwise every build differs in eight
        # bytes and no digest of the .gz means anything.
        with tar_path.open("rb") as src, gz_path.open("wb") as raw:
            with gzip.GzipFile(
                filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0
            ) as gz:
                shutil.copyfileobj(src, gz, _BLOCK)
        gz_digest, gz_size = digest_file(gz_path)
        result["tar_gz"] = str(gz_path)
        result["tar_gz_sha256"] = gz_digest
        result["tar_gz_bytes"] = gz_size

    return result


def _git_head() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parent.parent,
            check=False,
        )
        return out.stdout.strip() or None
    except OSError:
        return None


def verify_sources_unchanged(manifest_path: Path, roots: tuple[Root, ...]) -> int:
    """Re-digest every source file and compare against the manifest.

    This is the proof that the archive build did not modify a raw run
    directory. It reads the manifest rather than a second in-memory copy, so a
    bug that corrupted both would have to corrupt them identically.
    """
    by_source = {root.label: Path(root.source) for root in roots}
    recorded: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        sha, _, name = line.partition("  ")
        recorded[name] = sha

    changed: list[str] = []
    missing: list[str] = []
    checked = 0
    for name, sha in sorted(recorded.items()):
        if "/" not in name:
            continue  # ARCHIVE-METADATA.json lives in the output, not a source
        label, rest = name.split("/", 1)
        base = by_source.get(label)
        if base is None:
            continue
        source = base / rest
        if not source.exists():
            missing.append(name)
            continue
        actual, _ = digest_file(source)
        checked += 1
        if actual != sha:
            changed.append(f"{name}: manifest {sha} now {actual}")

    print(f"re-digested {checked} source files against {manifest_path}")
    if missing:
        print(f"MISSING FROM SOURCE ({len(missing)}):")
        for name in missing[:50]:
            print(f"  {name}")
    if changed:
        print(f"CHANGED SINCE THE MANIFEST ({len(changed)}):")
        for line in changed[:50]:
            print(f"  {line}")
    if not missing and not changed:
        print("UNCHANGED: every source file still digests to its manifest value.")
        return 0
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output",
        default="/root/aep-raw-archive",
        help="where the tar, manifest and metadata are written",
    )
    parser.add_argument(
        "--no-compress", action="store_true", help="skip the deterministic .tar.gz"
    )
    parser.add_argument(
        "--verify-sources-unchanged",
        action="store_true",
        help="re-digest the sources against an existing MANIFEST.sha256 and exit",
    )
    parser.add_argument(
        "--extension",
        action="store_true",
        help=(
            "build the phase 35 EXTENSION archive -- the roots the "
            "2026-09-03 archive did not cover -- instead of the original "
            "set. The original is never reopened, so its manifest digest "
            "still verifies over exactly the bytes it always covered."
        ),
    )
    parser.add_argument(
        "--part3",
        action="store_true",
        help=(
            "build the phase 54 THIRD part -- the roots neither earlier "
            "archive reached, including the five that supply eighteen "
            "manuscript macros. Neither earlier part is reopened, so their "
            "manifest digests still verify over exactly the bytes they "
            "always covered."
        ),
    )
    parser.add_argument(
        "--with-phase53",
        action="store_true",
        help=(
            "include experiments/results/abd-immediate-2026-09-24 in the "
            "--part3 build. Refuses unless the collection looks complete, "
            "because a part built over a half-finished collection would "
            "carry a manifest nobody can reproduce."
        ),
    )
    parser.add_argument("--json", default=None, help="write the build report here")
    arguments = parser.parse_args(argv)

    output = Path(arguments.output)

    if arguments.verify_sources_unchanged:
        return verify_sources_unchanged(output / "MANIFEST.sha256", ROOTS)

    if arguments.part3:
        roots = PART3_ROOTS
        excluded = PART3_EXCLUDED
        phase = 54
        if arguments.with_phase53:
            # Refuse rather than archive a collection still being written. The
            # pre-registration expects 45 runs; anything short of that means
            # the manifest would cover a tree that changes after it is signed.
            source = Path(PHASE53_ROOT.source)
            runs = (
                sum(1 for _ in source.glob("*/run-config.json"))
                if source.is_dir()
                else 0
            )
            if runs < 45:
                raise SystemExit(
                    f"--with-phase53: {PHASE53_ROOT.source} has {runs} runs "
                    "with a run-config.json, expected 45. The collection is "
                    "still in flight; a manifest built over it would not "
                    "reproduce. Wait for it to finish."
                )
            roots = roots + (PHASE53_ROOT,)
            excluded = tuple(
                e for e in excluded
                if "abd-immediate-2026-09-24" not in e.path
            )
    elif arguments.extension:
        roots, excluded, phase = EXTENSION_ROOTS, EXCLUDED, 35
    else:
        roots, excluded, phase = ROOTS, EXCLUDED, 11

    started = time.monotonic()
    print(f"archiving {len(roots)} collection roots into {output}")
    result = build(
        output, roots, compress=not arguments.no_compress,
        excluded=excluded, phase=phase,
    )
    result["build_seconds"] = round(time.monotonic() - started, 1)

    print()
    print(f"manifest entries : {result['manifest_entries']}")
    print(f"payload bytes    : {result['payload_bytes']:,}")
    print(f"tar bytes        : {result['tar_bytes']:,}")
    if "tar_gz_bytes" in result:
        print(f"tar.gz bytes     : {result['tar_gz_bytes']:,}")
        print(f"tar.gz sha256    : {result['tar_gz_sha256']}")
    print(f"tar sha256       : {result['tar_sha256']}")
    print(f"MANIFEST sha256  : {result['manifest_sha256']}")

    if arguments.json:
        Path(arguments.json).write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
