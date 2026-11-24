# TSE is single-anonymous: everything that serves the anonymous variant, and what removing it would cost — 2026-09-24

**Nothing is removed.** No file was deleted, no gate disabled, no build run.
This is an inventory and a costing.

**Repository state:** `179f0f7` plus this session's prereg-order fix.

**The premise.** IEEE Transactions on Software Engineering does not offer
double-anonymous review; author names and affiliations belong in the submitted
manuscript (`reports/tse-venue-2026-09-24.md` §1, IEEE Computer Society author
guidance, retrieved 2026-09-24). The anonymous variant was built to serve a
review model this journal does not run.

**The headline, stated before the inventory so it is not buried:**
**do not remove it.** §5 gives the reason, and it is not sentiment — the
anonymous build is the only mechanism in this repository that can detect an
identity leak at all, and two of its four checks catch classes of leak that no
other gate looks for.

---

## 1. The manuscript source

| location | what it does |
|---|---|
| `paper/main.tex:114-118` | `\newif\ifanonymous`; `\ifdefined\ANONYMOUS \anonymoustrue\fi`. The flag is set from the pdflatex command line, never in the file, so neither build can forget to set it |
| `paper/main.tex:150-178` | The anonymous branch: `\artifactavail` → *"available via the submission system"*, `\archiveavail` → same, `\authorname` → *"Anonymous Author(s)"*, `\authorcontact` → empty, `\aidisclosure` → the stripped disclosure, and a `\hypersetup` that empties six DocInfo keys |
| `paper/main.tex:179-227` | The named branch: GitHub URL, `Hamza Khan`, the FAST-NUCES `\thanks` footnote, e-mail, ORCID, the full AI disclosure, and the RESERVED-DOI sentence |
| `paper/supplementary.tex:54-80` | The same apparatus mirrored, with its own DocInfo wipe and its own `Anonymous Author(s)` byline |

**Net:** about **29 source lines in `main.tex`** and **23 in `supplementary.tex`**
are branch scaffolding. The named branch's content is not scaffolding — it is
the byline, the affiliation, the ORCID, the artifact URL and the disclosure,
all of which the submitted paper needs.

---

## 2. The build system

`scripts/build_paper.sh` — **11 references.** The anonymous path is not a
separate script; it is a flag:

- `:24, :40-42` — `--anonymous` sets `ANON=1` and `JOB="${DOC}-anon"`.
- `:64` — the anonymous invocation adds `\pdfsuppressptexinfo=-1
  \pdfinfoomitdate=1 \pdftrailerid{}\def\ANONYMOUS{}`. Those three pdfTeX
  primitives are what strip `/PTEX.FileName`, `/CreationDate` and the trailer
  ID — the metadata channels an anonymised PDF usually leaks through.
- `:266-280` — the repository-path check runs on **every** variant, with the
  comment that a repository path *"is wrong in all four, and it is an anonymity
  risk in exactly the two"*.
- `:325-336` — per-variant provenance stamps.

**The build order matters and is a real constraint.** `build_paper.sh` treats
`main.tex` as a source for the supplementary staleness check, so the documented
order is supplementaries first, then the mains — four invocations
(`reports/audit-pack.md` §9, `ARTIFACT.md:127-128`). Dropping the anonymous
variants takes that from **four builds to two**.

`scripts/paper_provenance.py` — **12 references.** Two of the four stamp names
(`ANON_STAMP_NAME`, `SUPP_ANON_STAMP_NAME`) and about 14 filename entries in the
promote/clean lists exist only for the anonymous jobs. The module comment at
`:42-48` records *why* the stamps are separate: one shared stamp would let a
rebuilt `main.pdf` silently vouch for a stale `main-anon.pdf`, *"which is
exactly how main-anon.pdf sat three days"* out of date once.

**Artifacts on disk:** `paper/main-anon.pdf` (411 KB),
`paper/supplementary-anon.pdf` (208 KB), `paper/.build-provenance-anon.json`,
`paper/.build-provenance-supp-anon.json`.

---

## 3. The gates

| gate | anonymous role | removable? |
|---|---|---|
| `check_paper_numbers.py::check_anonymous_build` (`:505-642`, ~133 lines) | **Four named checks:** *anonymous build exists*, *anonymous build is not stale*, *anonymous build leaks no absolute build path*, *anonymous build DocInfo is clean*, plus *anonymous build carries no byline* | This is the whole of the anonymity enforcement |
| `prove_anonymous_gate.sh` (92 lines) | Proves those checks can fail, by rebuilding the PDF with the primitives and `\ANONYMOUS` removed, observing three content checks fire, then appending to `08-threats.tex` to fire the staleness check, then restoring | Exists only to justify the above |
| `check_no_repo_paths.py` (`:48-49`) | `BUILDS` is all four PDFs. Its docstring says a personal path *"is an anonymity risk as"* well as wrong | **Keep** — the check is not about anonymity; it would just drop to two PDFs |
| `check_american_spelling.py` (`:57-58`) | Same: `BUILDS` is all four | **Keep**, drops to two PDFs |
| `scan_archive_for_leakage.py` | 13 leak categories, **8 flagged `anonymity_only=True`** | See §5 — this is the one that argues hardest for keeping the variant |
| `tests/test_build_paper_safety.py`, `tests/test_no_repo_paths.py` | One reference each | Trivial |

**The named-check count moves.** `check_paper_numbers.py` currently reports 43
checks. Removing the anonymous build removes five named checks (the four in the
table plus the byline check), so the expected line in `audit-pack.md` §9 and
`ARTIFACT.md` would become **38**, and every phase report quoting *"43 passed"*
becomes a record of a different program.

---

## 4. What removal would involve, and what it would save

### The work

| step | scope |
|---|---|
| 1 | Delete the `\ifanonymous` branch in `paper/main.tex` (~29 lines) and `paper/supplementary.tex` (~23 lines), promoting the `\else` bodies to unconditional |
| 2 | Remove `--anonymous` from `build_paper.sh` (~11 sites, including the pdfTeX primitive line) |
| 3 | Remove the two anon stamp constants and ~14 filename entries from `paper_provenance.py` |
| 4 | Delete `check_anonymous_build` (~133 lines) and its call site at `check_paper_numbers.py:967` |
| 5 | Delete `scripts/prove_anonymous_gate.sh` (92 lines) |
| 6 | Shrink `BUILDS` to two in `check_no_repo_paths.py` and `check_american_spelling.py` |
| 7 | Delete `paper/main-anon.pdf`, `paper/supplementary-anon.pdf` and the two anon stamps |
| 8 | Update `ARTIFACT.md:127-128`, `README.md:201`, `audit-pack.md` §9, and the expected-counts line everywhere it appears |
| 9 | Decide what `scan_archive_for_leakage.py` does with its 8 `anonymity_only` categories — see §5 |

Roughly **250 lines removed** across seven files, plus four documentation sites.

### The savings

| saving | size |
|---|---|
| Build time | **Two builds instead of four.** The largest concrete saving; every `main.tex` edit currently invalidates all four |
| Gate surface | ~225 lines (`check_anonymous_build` + `prove_anonymous_gate.sh`) |
| Repository | ~620 KB of tracked PDFs and two stamps |
| A documented hazard | `prove_anonymous_gate.sh` appends to `paper/sections/08-threats.tex` and restores with `git checkout --`. Running it with uncommitted edits to that file **destroys them**, and it has happened once (`reports/phase-report-49` §7). That hazard disappears with the script |
| Cognitive load | The four-build order, the "commit 08-threats.tex before running the gate" rule, and the separate-stamps reasoning all go away |

### What it would **not** save

- The named build's content. The byline, ORCID, affiliation, artifact URL and
  full AI disclosure are all in the `\else` branch and are what the submitted
  paper needs.
- `check_no_repo_paths.py` and `check_american_spelling.py`. Both are about
  correctness first; anonymity is a secondary justification in their
  docstrings.
- The camera-ready checklist items. `reports/camera-ready-checklist.md` lists
  the artifact's *"for agents"* description and its *Agent Execution Protocol*
  heading as things to fix. Those were deferred because they were *"invisible to
  a double-anonymous reviewer"* — under single-anonymous review they are visible
  from day one, so removing the anonymous build makes that list **more** urgent,
  not less. Corrected in `reports/audit-pack.md` §7.5 this session.

---

## 4a. One more place, and it changes a decision rather than a build

`paper/arxiv-metadata.md` is tracked, is under `paper/`, and carries **eight**
references. Two passages are reasoning, not scaffolding, and both are premised
on double-anonymous review:

**(a) The DOI-withholding rationale** (`:83-88`):

> *"**In the anonymous build the DOI is withheld**, exactly as the GitHub URL
> is: a Zenodo record names its depositor, so citing it under double-anonymous
> review defeats the anonymisation."*

The mechanism is right and the premise is wrong. Under single-anonymous review
there is nothing to defeat: the named build carries the author, the ORCID and
the artifact URL already, so a resolving DOI adds no identifying information a
TSE reviewer does not have. **This removes an argument for withholding the DOI
and therefore removes a reason to delay the deposit** — which is the open
submission blocker and the thing that would close `claims-to-review` entry 3
(`reports/claims-to-review.md` §3, this session). Worth flagging to whoever
schedules the Zenodo publication.

**(b) The arXiv-versus-TSE ordering decision** (`:152-155`):

> *"a public arXiv preprint and an anonymised TSE submission cannot both be
> served by the same PDF, and posting the preprint first is what makes the
> anonymised submission moot. **Decide the ordering, then pick the build.**"*

**That decision is now moot in the other direction.** There is no anonymised
submission to be made moot, so posting an arXiv preprint before submitting to
TSE costs nothing on anonymity grounds. The ordering question does not
disappear — IEEE's preprint policy and the venue's own rules still govern — but
the specific tension this checklist item was written to resolve has dissolved.

**Both are under `paper/` and were not edited.** They are recorded here because
they are decisions in flight, not scaffolding to delete.

---

## 5. Why the recommendation is to keep it anyway

**The anonymous build is the only identity-leak detector in the repository, and
it works by construction rather than by a list of forbidden strings.**

Three arguments, strongest last.

1. **It is a differential test.** `check_anonymous_build` does not scan for
   known-bad strings; it builds the same source two ways and asserts the second
   lacks what the first has (`:625-634`): an *"Anonymous"* byline is present,
   the public byline is absent verbatim, and the ORCID and DOI found in the
   public build do not survive. A string-list check finds the leaks you thought
   of. A differential check finds the ones you did not — including any new
   identifying macro someone adds to `main.tex` next month, which would be
   caught the first time the two builds are compared.

2. **Two of its checks cover channels nothing else looks at.** *DocInfo is
   clean* and *leaks no absolute build path* are about PDF metadata and
   `/PTEX.FileName`, not about rendered text. No other gate in this repository
   reads either. `/PTEX.FileName` in particular records the absolute path of
   every included file — on this host that is a Windows path containing the
   author's user name, and it appears in **no rendered page**, so
   `check_no_repo_paths.py` cannot see it. Remove the anonymous build and that
   channel becomes unmonitored in the build that *is* submitted, because
   nothing then checks `main.pdf`'s DocInfo at all.

3. **The deposit scanner depends on the concept.** `scan_archive_for_leakage.py`
   classifies 13 leak categories and flags **8** of them `anonymity_only=True`,
   with its module docstring naming the anonymous build as the thing those
   categories serve. The Zenodo deposit is the open submission blocker
   (`audit-pack.md` §7.4), and it is the artifact a reviewer will open. If the
   anonymous build goes, someone has to decide whether those 8 categories are
   now noise — and the honest answer is that they are not, because a reviewer
   following a DOI to a deposit full of `/home/<name>/` paths learns the same
   thing either way.

**Cost of keeping it:** two extra builds per manuscript change, ~620 KB of
tracked PDFs, and one documented foot-gun in `prove_anonymous_gate.sh`.

**Recommendation.** Keep the variant and stop treating it as a deliverable.
Concretely:

- **Relabel, do not remove.** The anonymous build is a **leak check**, not a
  submission artifact. `ARTIFACT.md:127-128` and `README.md:201` should say so,
  and `audit-pack.md`'s header now does.
- **Fix the false premise in the source comment.** `paper/main.tex:161-166`
  reasons from *"TSE is double-anonymous, so the submitted article is this
  build"* to conclude that the AI-disclosure requirement attaches to the
  anonymous branch. The conclusion is right for the wrong reason: the
  requirement attaches to whichever article is submitted, which under
  single-anonymous review is the **named** build. The anonymous branch's
  disclosure gap still needs the fix in
  `reports/ai-disclosure-2026-09-24.md` §6.1, because it is the deliverable for
  any double-anonymous venue this paper is redirected to.
- **Keep the four-build order documented** as a build cost, not a submission
  step.
- **Revisit only if TSE rejects and the next venue is also single-anonymous.**
  At that point the cost/benefit is worth recomputing; today the benefit is a
  leak channel nothing else watches.

**If the decision goes the other way** and the variant is removed, the one
non-negotiable replacement is a check on `main.pdf`'s DocInfo and
`/PTEX.FileName`. Losing the anonymous build without that is a net reduction in
what the repository verifies about the PDF it actually submits.

---

## 6. Summary

| question | answer |
|---|---|
| Where is the anonymous variant served? | `main.tex` (~29 lines), `supplementary.tex` (~23), `build_paper.sh` (11 sites), `paper_provenance.py` (2 stamps + ~14 filenames), `check_paper_numbers.py` (~133 lines, 5 named checks), `prove_anonymous_gate.sh` (92 lines), two PDFs, two stamps, 2 docs, 2 tests, plus `paper/arxiv-metadata.md` (§4a — reasoning, not scaffolding) |
| Anything that changes a *decision* rather than a build? | Yes, two. The DOI-withholding rationale loses its basis, which removes a reason to delay the Zenodo deposit; and the arXiv-preprint-versus-anonymised-submission ordering question dissolves. §4a |
| What would removal involve? | ~250 lines across 7 files, 4 documentation sites, and a decision about 8 leak categories in `scan_archive_for_leakage.py` |
| What would it save? | Two builds instead of four, ~225 lines of gate, ~620 KB, and one documented destructive foot-gun |
| What would it cost? | The only differential identity-leak check in the repository, and the only check on PDF DocInfo and `/PTEX.FileName` — a channel invisible to every text-based gate |
| Recommendation | **Keep it, relabel it as a leak check rather than a deliverable.** Remove nothing |

**Nothing in this session changed the manuscript, the build system or the
gates, other than the prereg-order table fix that was explicitly requested.**
