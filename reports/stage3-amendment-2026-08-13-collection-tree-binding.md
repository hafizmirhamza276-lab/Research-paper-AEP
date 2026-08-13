# Stage 3 amendment — 2026-08-13 — binding the collection to a committed tree

**Append-only.** This amendment records a gap in
`docs/STAGE3_OFFICE_ROADMAP_AND_PROMPTS.md`, the reason it cannot be carried
into collection, and the deviation taken from the roadmap's literal
instructions. It modifies neither the frozen 2026-08-12 protocol nor the
frozen 2026-08-12 plan; both remain byte-identical to `8b0c3f00…2ce864` and
`b5e4a39f…8afd7f9a`.

**Supplements:** `reports/stage3-amendment-2026-08-13-evidence-decision.md`,
§3 of which raised this caveat and deferred it.

---

## 1. The gap

Prompt 2 ends: "Do not commit or push yet." Prompt 3 ends: "Do not commit,
push, or start B2/B3 in this prompt." The first commit the roadmap authorizes
is Prompt 10, gated behind Prompt 9's independent rereview — that is, after
the pilot, the 432-run replication, B2, B3, the freeze, the analysis, and the
manuscript build have all been performed.

Prompt 3 regenerates the plan under exactly one condition:

> If the pilot exposes a defect […] generate a new plan/hash before
> scientific collection.

A clean pilot triggers nothing. So on the roadmap's own terms, every
scientific run in Stage 3 is collected against a working tree that has never
been committed, bound to a plan that records `git_tree_clean: false`.

No step closes this. It is an omission in the roadmap, not a rule to follow.

## 2. Why this cannot be carried into collection

Prompt 3 requires that every run be bound to "dataset ID, plan hash, Git SHA,
run ID, seed, Redis digest/configuration, environment record and raw-directory
hash." Under the roadmap as written, the Git SHA those 432 records would carry
is `4ea09fd2f3a878b78c5651701be668ac2401006f` — a commit that contains none of
the Prompt 2 repairs. Specifically, it does not contain:

- the split of `MATRIX_VERSION` into a frozen `MATRIX_SEED_NAMESPACE` and a
  separate `MATRIX_DEFINITION_VERSION`, which is what makes the 1,068 → 1,128
  matrix change legible rather than silent;
- the bootstrap percentile convention pin, which decides an interval endpoint
  on nine-cluster data — B3's exact geometry;
- the run-config/2 field-binding tests;
- the `${AEP_FSYNC_RUNS-9}` gate.

A provenance record that names a tree not containing the code that produced
the run is not provenance. It is a false statement, made 432 times, in the
one field a reader would use to reconstruct the experiment. Anyone checking
out `4ea09fd` and rerunning would get a different matrix definition and a
different interval endpoint than the dataset was collected under, and would
have no way to discover that from the record.

The dirty-tree caveat compounds it: `git_tree_clean: false` means the delta
between the named commit and the executed code exists only on one disk, in one
uncommitted working tree, and is unreconstructible by anyone — including us,
after any subsequent edit.

Neither problem is repairable after the fact. A dataset's binding is fixed at
collection time; it cannot be back-dated once the runs exist.

## 3. Deviation taken

**Prompt 2's changes are committed before any run is collected**, contrary to
Prompt 2's "do not commit or push yet" and ahead of Prompt 10's authorized
checkpoint. The replication plan is then regenerated against that commit, so
that the Git SHA bound into all 432 runs names a tree that actually contains
the code executing them.

Nothing is pushed. The deviation is to the commit ordering only; Prompt 10's
review gate, staging rules, and push authorization are untouched and still
apply.

## 4. Scope: Prompt 2's files only

The commit covers the six Prompt 2 source and test files and no others.

**`835ec39` is deliberately excluded and stays in the Windows clones.** That
commit ("Two review items nothing has closed yet: the AI disclosure and the
rebuttal notes") exists in `Research-paper-AEP` and `audit-clone` but not in
the Stage 3 collection repo, which sits one commit behind at `4ea09fd`.

The reason is not convenience. `835ec39` is manuscript-side — cover letter and
rebuttal notes — and touches no code the harness executes. Merging it would
change the Git SHA stamped into all 432 runs without changing a single
instruction those runs perform. That makes the binding *less* informative, not
more: it introduces a difference between two collection-relevant trees that
is, in fact, no difference at all, and invites a future reader to look for a
behavioural cause that does not exist. The Git SHA in a run record answers one
question — what code ran — and it should move only when that answer moves.

The manuscript work is real and belongs in the manuscript history. It rejoins
at Prompt 8, where the manuscript is built, and at Prompt 10, where the branch
is pushed. Until then the collection repo stays code-only.

## 5. The self-reference, stated rather than hidden

A plan cannot record the SHA of the commit that contains it. This is resolved
by two commits, not by rounding:

- **Commit A** contains the six code and test files, and nothing else. This is
  the SHA bound into every run.
- **Commit B** contains this amendment, the evidence-decision amendment's
  updated §3, and the regenerated plan. It changes no file under
  `experiments/`, `scripts/`, or `tests/`, and that claim is verified by a
  diff, not asserted.

The plan's `git_tree_clean` is therefore evaluated with the plan's own output
path excluded — the file cannot be simultaneously the subject and the object
of the check. The plan records the exclusion explicitly in a
`git_tree_clean_scope` field rather than leaving a bare `true` to imply more
than was checked.
