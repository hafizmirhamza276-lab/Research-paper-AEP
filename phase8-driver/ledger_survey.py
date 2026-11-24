#!/usr/bin/env python3
"""Survey (a): is the ledger empty in every result root?

Motivation. `ground_truth.sqlite3` in Phase 8.4's roots is a bare 4096-byte page
-- one SQLite page, header only -- with the ledger's actual contents sitting in
an uncheckpointed `-wal` beside it. Any archive that copies only `*.sqlite3`, or
that opens a ledger and lets SQLite checkpoint on close, publishes empty
databases. This establishes how widely that shape holds, including for
`b2-2026-08-21`, whose numbers are in the manuscript.

**No ledger is opened, for reading or writing.** This uses `os.stat` and nothing
else -- no `sqlite3` import, no file handle on any database. Opening a WAL-mode
database is itself a mutating act: SQLite may checkpoint and truncate the WAL on
connect or close, which would destroy exactly the evidence being surveyed.

Mtimes and sizes of every `-wal` and `-shm` are captured before and after the
walk and compared, so "nothing was opened" is demonstrated rather than asserted.

Read-only. Usage: ledger_survey.py <results dir>
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PAGE = 4096


def stamp(results: Path) -> dict[str, tuple[int, int]]:
    """(size, mtime_ns) for every WAL and SHM under the tree."""
    out = {}
    for p in results.rglob("ground_truth.sqlite3-*"):
        try:
            st = p.stat()
        except OSError:
            continue
        out[str(p)] = (st.st_size, st.st_mtime_ns)
    return out


def main(argv: list[str]) -> int:
    results = Path(argv[0]).resolve()
    before = stamp(results)

    roots = sorted(p for p in results.iterdir() if p.is_dir())
    rows = []
    for root in roots:
        n_db = n_bare = n_wal = n_shm = 0
        wal_bytes = db_bytes = 0
        nonbare = []
        bare_empty_wal = 0
        for db in sorted(root.rglob("ground_truth.sqlite3")):
            n_db += 1
            size = db.stat().st_size
            db_bytes += size
            wal = db.with_name(db.name + "-wal")
            shm = db.with_name(db.name + "-shm")
            wsize = wal.stat().st_size if wal.exists() else 0
            if wal.exists():
                n_wal += 1
                wal_bytes += wsize
            if shm.exists():
                n_shm += 1
            if size == PAGE:
                n_bare += 1
                if wsize == 0:
                    bare_empty_wal += 1
            else:
                nonbare.append((db.parent.name, size))
        rows.append(
            {
                "root": root.name,
                "db": n_db,
                "bare": n_bare,
                "wal": n_wal,
                "shm": n_shm,
                "bare_nonempty_wal": n_bare - bare_empty_wal,
                "bare_empty_wal": bare_empty_wal,
                "db_bytes": db_bytes,
                "wal_bytes": wal_bytes,
                "nonbare": nonbare,
            }
        )

    w = max(len(r["root"]) for r in rows) + 2
    print(f"\n{'root':<{w}}{'dbs':>6}{'bare 4096':>11}{'-wal':>7}{'-shm':>7}"
          f"{'BARE+WAL':>10}{'db MB':>9}{'wal MB':>9}")
    print("-" * (w + 59))
    for r in rows:
        print(
            f"{r['root']:<{w}}{r['db']:>6}{r['bare']:>11}{r['wal']:>7}{r['shm']:>7}"
            f"{r['bare_nonempty_wal']:>10}"
            f"{r['db_bytes']/1e6:>9.2f}{r['wal_bytes']/1e6:>9.2f}"
        )
    tot = {k: sum(r[k] for r in rows) for k in
           ("db", "bare", "wal", "shm", "bare_nonempty_wal", "db_bytes", "wal_bytes")}
    print("-" * (w + 59))
    print(
        f"{'TOTAL':<{w}}{tot['db']:>6}{tot['bare']:>11}{tot['wal']:>7}{tot['shm']:>7}"
        f"{tot['bare_nonempty_wal']:>10}"
        f"{tot['db_bytes']/1e6:>9.2f}{tot['wal_bytes']/1e6:>9.2f}"
    )

    print("\nBARE+WAL = ground_truth.sqlite3 is exactly one 4096-byte page AND its")
    print("-wal is non-empty: the database file holds no data and the ledger is")
    print("entirely in the uncheckpointed WAL.")

    odd = [(r["root"], r["nonbare"]) for r in rows if r["nonbare"]]
    if odd:
        print("\nDatabases NOT a bare page (size in bytes):")
        for root, items in odd:
            for run, size in items[:5]:
                print(f"  {root}/{run}: {size}")
            if len(items) > 5:
                print(f"  ... and {len(items) - 5} more in {root}")
    else:
        print("\nEvery ground_truth.sqlite3 found is exactly one 4096-byte page.")

    after = stamp(results)
    print("\n--- proof that no ledger was opened ---")
    print(f"WAL/SHM files stamped before : {len(before)}")
    print(f"WAL/SHM files stamped after  : {len(after)}")
    changed = [k for k in before if k in after and before[k] != after[k]]
    vanished = [k for k in before if k not in after]
    appeared = [k for k in after if k not in before]
    print(f"size or mtime changed        : {len(changed)}")
    print(f"vanished / appeared          : {len(vanished)} / {len(appeared)}")
    if changed or vanished or appeared:
        for k in (changed + vanished + appeared)[:10]:
            print(f"  !! {k}")
        return 2
    print("UNCHANGED: no -wal or -shm size or mtime moved during the survey.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
