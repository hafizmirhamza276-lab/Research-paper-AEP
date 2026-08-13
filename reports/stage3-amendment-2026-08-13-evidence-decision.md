# Stage 3 amendment — 2026-08-13 — the evidence decision

**Append-only.** This file records a decision and the findings behind it. It
does not modify `reports/stage3-pre-run-protocol-2026-08-12.md` or
`reports/stage3-experiment-plan-2026-08-12.json`; both remain byte-identical to
their frozen hashes (`8b0c3f00…2ce864` and `b5e4a39f…8afd7f9a`, verified during
this audit).

**Raised by:** Prompt 2 of `docs/STAGE3_OFFICE_ROADMAP_AND_PROMPTS.md`, the
evidence-decision step.

---

## 1. What the roadmap assumed, and what is actually on disk

The roadmap records, as of 2026-08-12, that "the original raw evidence behind
the committed aggregates was not recovered" — 432 runs, 3,780 executions, 126
cells, and the historical `results/voided/` evidence, all treated as absent.

A search of the authorized locations on 2026-08-13 found that this is not
quite right. In
`D:/personal/AEP/Research-paper-AEP/experiments/results/matrix`:

| | |
|---|---|
| Run directories present | **84** |
| Runs described by `MANIFEST.csv` | 432 |
| Fraction present | **19.4%** |
| Cells with at least one run | 28 of 126 |
| Cells complete at 3/3 repetitions | **28** |
| Run IDs also present in `analysis/per-execution.csv` | 84 of 84 |
| Run IDs on disk but absent from the analysis | **0** |
| `results/voided/` evidence | **absent everywhere** |
| Per-run SHA-256 digests | **none exist** |

Each surviving directory carries the full raw record — `events.jsonl`,
`events-runner.jsonl`, `events-recovery.jsonl`, `ground_truth.sqlite3` with its
WAL, the mock-API config and log, and the recovery logs.

Two qualifications matter more than the count.

**These 84 cannot be verified byte-for-byte against anything.** The committed
`SHA256SUMS` covers seventeen files, and all seventeen are analysis outputs or
manifests. No digest of any raw run was ever recorded, so the strongest
statement available about the survivors is that they are internally consistent
and that re-deriving the analysis from them reproduces their rows. That is
worth something. It is not provenance.

**The frozen plan binds to a manifest digest that no longer resolves.**
`reports/stage3-experiment-plan-2026-08-12.json` records
`collection_source_manifest_sha256 = 989b87f3…1fd38f3`. The `MANIFEST.csv`
present in every authorized location hashes to `f3f3d2e0…f16877e`, and neither
CRLF-normalising it, LF-normalising it, stripping the trailing newline, nor
reading it out of the git object store reproduces the recorded value. The
frozen plan is not edited to fix this — it is frozen, and this amendment is
where the discrepancy is recorded instead. It should be treated as a known
weakness in that plan's binding, not as evidence that the manifest was
tampered with.

## 2. The decision

**The office collection is a new replication dataset covering all 126 cells.**
It is not a recovery of the historical raw dataset and must never be described
as one, in the manuscript or anywhere else.

**The 84 surviving runs are retained as corroboration only.** They are
read-only. They are cross-checked against the replication once it is frozen,
and they are never pooled into it, never counted in a denominator, and never
substituted for a cell the replication collects.

The rejected alternative is worth naming: reusing the 28 complete cells and
recollecting only the other 98 would save roughly two hours and would produce a
dataset assembled from two collection epochs on two hosts. Every table drawing
on it would then owe the reader that disclosure, permanently, to save two hours
once. The cost is not worth the footnote.

## 3. The replication plan

Generated at `reports/stage3-replication-plan-2026-08-13.json`.

| | |
|---|---|
| Schema | `aep.stage3.replication-plan/1` |
| Dataset version | `stage3-2026-08-13-replication-1` |
| Cells | 126 |
| Runs | 432 |
| Plan SHA-256 | `e416f076fcbcbf1d92d56a754fa48b9973d9c354de5acdbc186b4d7f5f4a643c` |
| Bound Git SHA | `151450bb685ac241d17fd4580c149f7d70d58956` |
| Git tree clean | **true** |
| Result root | `/var/tmp/aep-stage3-2026-08-13/replication` |
| Matrix seed | **20260806 — the historical seed, deliberately** |
| Seed namespace | `aep.matrix/1` (frozen) |
| Matrix definition | `aep.matrix-definition/2` |

**On the seed choice.** A fresh seed would have been the reflexive answer and
the wrong one. The 84 survivors are being kept precisely so the replication can
be checked against them, and that check is only interpretable if both drove the
same workload and the same fault stream. With the historical seeds, a
divergence between the two is attributable to the environment. With fresh
seeds, workload and environment are confounded and the corroboration set
answers nothing.

**One caveat on the binding.** The plan records `git_tree_clean: false`,
because the Prompt 2 fixes are deliberately left uncommitted. A plan bound to a
dirty tree binds to a tree nobody else can reconstruct. **The plan must be
regenerated, and its SHA-256 re-recorded here, once those changes are
committed** — before any run is collected against it.

**Closed, 2026-08-13.** The Prompt 2 changes are committed as
`151450b`, the plan has been regenerated against that commit, and the
SHA-256 in the table above is the regenerated one (it supersedes
`834bf00b…`, which was bound to the uncommitted tree and must not be
used). The plan now records `git_tree_clean: true`, evaluated with its own
output path and these amendments excluded — the scope is stated in the
plan's `git_tree_clean_scope` field, and excludes nothing under
`experiments/`, `scripts/` or `tests/`. The roadmap has no step that
performs this commit, and the deviation taken is recorded in
`reports/stage3-amendment-2026-08-13-collection-tree-binding.md`.

## 4. What this amendment does not decide

- Whether the 98 cells without surviving raw evidence differ in any way from
  the 28 that have it. Nothing here inspects that, and the replication is not
  designed to answer it.
- What happens if the replication and the corroboration set disagree. Prompt 6
  requires the discrepancy be reported and investigated rather than resolved by
  preferring the more favourable dataset; that rule stands and this amendment
  does not soften it.
- The absent `results/voided/` evidence. It is gone, no copy was found, and no
  replication can recreate a void that arose from a specific infrastructure
  failure. The manuscript's account of the one voided run (§VI-E) therefore
  rests on the narrative record alone from here on, and should say so.
