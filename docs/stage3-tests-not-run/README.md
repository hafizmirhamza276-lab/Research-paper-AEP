# Stage 3 tests, preserved but not run

**These seven files are not part of the suite and do not pass against today's
harness.** They are kept here because deleting
`origin/stage3-prep-office-20260812` destroyed the only other copy, and
discarding authored work is not reversible. They are in `docs/` deliberately:
`pyproject.toml` sets `testpaths = ["tests", "experiments"]`, so nothing here is
collected and the zero-skip gate is unaffected.

## Why they do not pass

Six cannot import at all. They expect an API that the branch's
`experiments/run_matrix.py` had on 13 August and that main's has never grown:

| file | missing symbol |
|---|---|
| `test_stage3_cell_selection.py` | `load_cell_selection` |
| `test_stage3_collection_safety.py` | `archive_voided_attempt` |
| `test_stage3_matrix_definition.py` | `MATRIX_DEFINITION_SHAPES` |
| `test_stage3_analysis_provenance.py` | (same family) |
| `test_stage3_bootstrap_convention.py` | (same family) |
| `test_stage3_provenance_binding.py` | (same family) |

The seventh, `test_fsync_stage3_safety.py`, imports fine and fails all thirteen
of its tests. It exercises a `scripts/fsync_always_benchmark.sh` that validates
run counts, refuses a destructive clean path, and locks an interleaved resume
plan. Main's version of that script predates those features — it is the 7 August
version, untouched since, while the branch's is 13 August with `+62/-11`.

## What reviving them would cost

Not a port of seven files. The six import failures are a request for the
branch's August harness API, and main has 259 commits of evolution on top of the
merge base (`c2fffa6`, 12 August). Adopting that API wholesale is the
destruction the recovery commit existed to avoid.

The seventh is different and is worth its own task: **the branch's
`fsync_always_benchmark.sh` has three safety properties main's lacks**, and
porting those forward — rather than overwriting main's script with the August
one — would make this test pass on its own merits. That is a real piece of work
somebody chose to do and main never received.

## Provenance

Extracted from `origin/stage3-prep-office-20260812` at `5b0e521`
(2026-08-17) before that branch was deleted. The recovery commit records the
full file-by-file comparison.

They can be dropped in one command if they are not wanted:
`git rm -r docs/stage3-tests-not-run`.
