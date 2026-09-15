#!/usr/bin/env python3
"""Rule 5: a cell's prediction is committed before its first data commit.

``docs/26`` §3 rule 5 requires a pre-registration whose commit predates the data
it predicts, and rule 4 requires the issued prompt to be committed before the
phase's first data commit. Both have been asserted, cell by cell, in individual
phase reports. **Nothing has ever checked them across the whole history at
once**, which is what an artifact evaluator would do.

**The enumeration runs from the DATA, never from the predictions.** Listing
prediction files and confirming each has data would only confirm what exists; a
cell collected with no pre-registration at all would be invisible to it. So
every tracked collection root is discovered from ``git ls-files``, and a root
with no entry in ``EXPECTED`` is a **failure**, not a silent skip. Adding a
collection therefore forces a decision about its pre-registration.

**Both orderings are checked**, because a rebase, a cherry-pick or a clock skew
makes them disagree:

* by **commit date** -- what a reader sees in the log;
* by **ancestry** -- whether the prediction commit is genuinely reachable from
  the data commit, which is the property that survives a rewritten timeline.

``docs/25`` R14, ten instances: a green check means green over the domain it can
see. This one's domain is stated in ``DOMAIN`` below and printed on every run.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: What this check establishes, and what it cannot. Printed every run, because
#: an unstated domain is how ten R14 instances happened.
DOMAIN = """\
COVERS  : the ORDER of commits -- prediction before prompt before first data --
          by date and by ancestry, for every tracked collection root.
DOES NOT: (1) read the prediction's CONTENT, so a file committed early and
          rewritten later still passes here; git history shows the edit but this
          check does not inspect it.
          (2) know when data was COLLECTED, only when it was COMMITTED. A cell
          collected before its prediction and committed after would pass.
          (3) cover untracked collections -- the /root/aep* trees in docs/36 §4.
          Their ordering rests on the phase reports alone."""


@dataclass(frozen=True)
class Cell:
    """A collection root, and the files that pre-register it."""
    prediction: str | None
    prompt: str | None
    note: str = ""
    #: Set when the cell predates the rule that would have governed it. Rule 5
    #: was adopted in the phase 8 pre-registration (2026-08-27); a cell
    #: collected before it cannot retroactively acquire one, and pretending
    #: otherwise would be the audit lying about its own subject.
    predates_rule: bool = False


#: Every tracked collection root. A root missing from this table FAILS.
EXPECTED: dict[str, Cell] = {
    "experiments/results/matrix": Cell(
        None, None, predates_rule=True,
        note="The 432-run evaluation, collected across early August before "
             "rule 5 existed. Its design is recorded in the phase 2B and "
             "session-3 reports, not in a pre-registration.",
    ),
    "experiments/results/fsync-always": Cell(
        None, None, predates_rule=True,
        note="The three-run appendfsync=always cell, collected 2026-08-07 "
             "under amendment F0(iii). Same era as the matrix.",
    ),
    "experiments/results/stage3-replication-2026-08-13": Cell(
        None, None, predates_rule=True,
        note="Stage-3 replication, 2026-08-13, recovered onto main in phase "
             "29's branch reconciliation. Predates rule 5 by two weeks.",
    ),
    "experiments/results/b2-2026-08-21": Cell(
        "reports/phase-report-9-prediction-2026-08-21.md", None,
        note="Phase 9 prevention replication, session 0.",
    ),
    "experiments/results/b2-s1-2026-08-21": Cell(
        "reports/phase-report-9c-prediction-2026-08-21.md", None,
        note="Phase 9C sessions 1-3 share one pre-registration.",
    ),
    "experiments/results/b2-s2-2026-08-21": Cell(
        "reports/phase-report-9c-prediction-2026-08-21.md", None),
    "experiments/results/b2-s3-2026-08-21": Cell(
        "reports/phase-report-9c-prediction-2026-08-21.md", None),
    "experiments/results/b2-paired-s1-2026-08-28": Cell(
        "reports/phase-report-8-prediction-2026-08-27.md", None,
        note="Phase 8.4 paired sessions, v1.",
    ),
    "experiments/results/b2-paired-v2-s1-2026-08-28": Cell(
        "reports/phase-report-8-prediction-amendment-1-2026-08-28.md", None,
        note="v2: re-collected after amendment 1 introduced run-level "
             "interleaving.",
    ),
    "experiments/results/b2-paired-v2-s2-2026-08-28": Cell(
        "reports/phase-report-8-prediction-amendment-1-2026-08-28.md", None),
    "experiments/results/b2-paired-v2-s2-aborted-2026-08-28": Cell(
        "reports/phase-report-8-prediction-amendment-1-2026-08-28.md", None,
        note="Aborted and retained; a voided collection is evidence about the "
             "instrument.",
    ),
    "experiments/results/b2-paired-v2-s3-2026-08-28": Cell(
        "reports/phase-report-8-prediction-amendment-1-2026-08-28.md", None),
    "experiments/results/b2-paired-v2-s4-2026-08-28": Cell(
        "reports/phase-report-8-prediction-amendment-1-2026-08-28.md", None),
    "experiments/results/phase10-replication-drvfs-2026-09-02": Cell(
        "reports/phase-report-10-prediction-2026-09-02.md",
        "prompts/phase-10-wsl2-native-docker.md"),
    "experiments/results/phase10-replication-drvfs-arbb30-2026-09-02": Cell(
        "reports/phase-report-10-prediction-2026-09-02.md",
        "prompts/phase-10-wsl2-native-docker.md"),
    "experiments/results/phase10-replication-ext4-2026-09-02": Cell(
        "reports/phase-report-10-prediction-2026-09-02.md",
        "prompts/phase-10-wsl2-native-docker.md"),
    "experiments/results/phase10-replication-ext4-arbb30-2026-09-02": Cell(
        "reports/phase-report-10-prediction-2026-09-02.md",
        "prompts/phase-10-wsl2-native-docker.md"),
    "experiments/results/phase13-armA-s1-2026-09-03": Cell(
        "reports/phase-report-13-prediction-armA-2026-09-03.md",
        "prompts/phase-13-controlled-prevention.md"),
    "experiments/results/phase13-armA-s2-2026-09-03": Cell(
        "reports/phase-report-13-prediction-armA-2026-09-03.md",
        "prompts/phase-13-controlled-prevention.md"),
    "experiments/results/phase13-armA-s3-2026-09-03": Cell(
        "reports/phase-report-13-prediction-armA-2026-09-03.md",
        "prompts/phase-13-controlled-prevention.md"),
    "experiments/results/phase13-inflight-s1-2026-09-04": Cell(
        "reports/phase-report-13-prediction-inflight-2026-09-04.md",
        "prompts/phase-13-controlled-prevention.md"),
    "experiments/results/phase13-inflight-s2-2026-09-04": Cell(
        "reports/phase-report-13-prediction-inflight-2026-09-04.md",
        "prompts/phase-13-controlled-prevention.md"),
    "reports/raw/ws4-writeloss-s1-2026-09-07": Cell(
        "reports/phase-report-ws4-prediction-2026-09-04.md",
        "prompts/phase-14-write-loss.md"),
    "reports/raw/ws6-b5-s1-2026-09-08": Cell(
        "reports/phase-report-ws6-prediction-2026-09-07.md",
        "prompts/phase-15-b5-temporal.md",
        note="Attempts 1 and 2.",
    ),
    "reports/raw/ws6-b5-s1-2026-09-08-attempt3": Cell(
        "reports/phase-report-ws6-prediction-corrected-2026-09-08.md",
        "prompts/phase-15-b5-temporal.md",
        note="Attempt 3, under the corrected pre-registration.",
    ),
    "experiments/results/ws5-2026-09-10/t1-p0-everysec": Cell(
        "reports/phase-report-ws5-prediction-2026-09-10.md", None),
    "experiments/results/ws5-2026-09-10/t1-incomplete": Cell(
        "reports/phase-report-ws5-prediction-2026-09-10.md", None),
    "experiments/results/ws5-2026-09-10/t2-p30": Cell(
        "reports/phase-report-ws5-prediction-2026-09-10.md", None),
    "experiments/results/ws5-2026-09-10/t2-keying": Cell(
        "reports/phase-report-ws5-prediction-2026-09-10.md", None),
    "experiments/results/fsync-always-2026-09-14": Cell(
        "reports/phase-report-ws5-prediction-amendment-3-2026-09-14.md",
        "prompts/phase-21-ws5-always-launch.md",
        note="The 45-run always arm. Amendment 3 pinned the lower-mode "
             "threshold before a single run existed.",
    ),
    "reports/raw/INCIDENT-fsync-always-destroyed-2026-09-14": Cell(
        None, None, predates_rule=True,
        note="NOT a collection. Quarantined debris from a failed run, "
             "retained as incident evidence (phase 20 §6).",
    ),
}


def git(*args: str, repo: Path = ROOT) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True)
    return done.stdout.strip()


def first_commit(path: str, repo: Path = ROOT) -> tuple[str, str]:
    """(sha, iso date) of the earliest commit touching `path`."""
    # --all, so a file committed on an unmerged branch is FOUND and then
    # rejected by the ancestry check with a precise message, rather than
    # reported as "not in the history" for a file a reader can plainly see.
    out = git("log", "--all", "--reverse", "--format=%H|%cI", "--", path,
              repo=repo)
    if not out:
        return ("", "")
    sha, _, date = out.splitlines()[0].partition("|")
    return (sha, date)


def is_ancestor(a: str, b: str, repo: Path = ROOT) -> bool:
    if not a or not b:
        return False
    done = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", a, b],
        capture_output=True)
    return done.returncode == 0


def discover(repo: Path = ROOT) -> set[str]:
    """Collection roots, from the tracked data."""
    roots: set[str] = set()
    for f in git("ls-files", repo=repo).splitlines():
        parts = f.split("/")
        if f.startswith("experiments/results/") and len(parts) > 3:
            if parts[2] == "ws5-2026-09-10" and len(parts) > 4:
                roots.add("/".join(parts[:4]))
            else:
                roots.add("/".join(parts[:3]))
        elif f.startswith("reports/raw/") and len(parts) > 3:
            roots.add("/".join(parts[:3]))
    return roots


def audit(repo: Path = ROOT, expected: dict[str, Cell] | None = None) -> int:
    table = EXPECTED if expected is None else expected
    found = discover(repo)
    failures: list[str] = []
    rows: list[tuple[str, ...]] = []

    for root in sorted(found):
        cell = table.get(root)
        if cell is None:
            failures.append(
                f"{root}: tracked collection with no entry in EXPECTED. "
                "Either it is pre-registered and the table must say where, or "
                "it was collected without a pre-registration -- which is the "
                "finding this check exists to surface."
            )
            rows.append((root, "UNMAPPED", "", "", "", "FAIL"))
            continue

        data_sha, data_date = first_commit(root, repo)
        if cell.predates_rule:
            rows.append((root, "n/a", "n/a", data_sha[:7], data_date[:10],
                         "EXEMPT"))
            continue

        verdict = "ok"
        pre_sha = pre_date = pro_sha = pro_date = ""
        for label, rel in (("prediction", cell.prediction),
                           ("prompt", cell.prompt)):
            if rel is None:
                continue
            sha, date = first_commit(rel, repo)
            if label == "prediction":
                pre_sha, pre_date = sha, date
            else:
                pro_sha, pro_date = sha, date
            if not sha:
                failures.append(f"{root}: {label} {rel} is not in the history")
                verdict = "FAIL"
                continue
            if date > data_date:
                failures.append(
                    f"{root}: {label} committed {date[:10]} AFTER first data "
                    f"{data_date[:10]}"
                )
                verdict = "FAIL"
            if not is_ancestor(sha, data_sha, repo):
                failures.append(
                    f"{root}: {label} {sha[:7]} is not an ancestor of the "
                    f"first data commit {data_sha[:7]}"
                )
                verdict = "FAIL"
        rows.append((root, pre_sha[:7] or "-", pre_date[:10] or "-",
                     data_sha[:7], data_date[:10], verdict))

    print("=" * 100)
    print("RULE 5 / RULE 4 ORDER AUDIT")
    print("=" * 100)
    print(DOMAIN)
    print()
    print("%-52s %-9s %-11s %-9s %-11s %s"
          % ("collection root", "pred", "pred date", "data", "data date", "verdict"))
    print("-" * 100)
    for row in rows:
        print("%-52s %-9s %-11s %-9s %-11s %s" % row)
    print()
    print(f"cells: {len(rows)}   "
          f"ok: {sum(1 for r in rows if r[-1] == 'ok')}   "
          f"exempt: {sum(1 for r in rows if r[-1] == 'EXEMPT')}   "
          f"failing: {sum(1 for r in rows if r[-1] == 'FAIL')}")
    if failures:
        print()
        print("FAILURES")
        for f in failures:
            print("  - " + f)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    return audit(args.repo)


if __name__ == "__main__":
    sys.exit(main())
