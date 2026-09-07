# Two loose ends from `561be06`: the `numbers.tex` freeze, and the anonymous build

No new work. Both items are settled on evidence below.

---

# 1. The `numbers.tex` freeze does **not** apply on `main` in phase 14

`561be06` staged `paper/generated/numbers.tex` and reported the conflict rather
than resolving it. Resolving it here.

## What `CLAUDE.md` actually says

It is **untracked** (`git ls-files --error-unmatch CLAUDE.md` → *did not match*),
986 bytes, mtime **2026-08-13**. It is also not in `.gitignore` or
`.git/info/exclude`.

Its content is not prose. It is a **shell command aimed at a different working
copy**:

```
wsl --cd /root/aep-stage3 -- bash -lc "cat >> CLAUDE.md <<'EOF'
## Stage 3 commit protocol
...
EOF
echo CLAUDE.md >> .git/info/exclude"
```

So the file in this repo's root is a *transcript of a command intended to write a
`CLAUDE.md` into `/root/aep-stage3`*, saved here by accident. The rule it carries
was authored for that tree, not this one.

The rules themselves are explicitly branch-scoped:

* *"Push to origin `stage3-prep-office-20260812` only. **Never push to main.**"*
* *"Never stage `paper/generated/numbers.tex` … frozen at Stage 2 baseline
  `c2fffa6`."*
* every rule is prefixed *"After each Prompt N in
  `docs/STAGE3_OFFICE_ROADMAP_AND_PROMPTS.md`"*.

A protocol that forbids pushing to `main` at all cannot be the protocol governing
work on `main`.

## What `c2fffa6` is

```
c2fffa61961228de8466b12939ef1c578506e7ba
Wed Aug 12 00:56:58 2026 +0500   hamza276
Close Stage 2 verification and typesetting
```

On `main`. The Stage 3 branch `stage3-prep-office-20260812` is named for the
following day, and `CLAUDE.md` was written the day after that (2026-08-13).

## Has anything on `main` staged `numbers.tex` since?

**Yes — fourteen commits**, thirteen of them before `561be06`:

```
561be06 74ea31f 1da1dc1 c25dfd0 f40a486 ebc7d1f 9545ccb
891f1ca a36c12b 749ceea 40516c7 5b601d0 e67efd1 1191f1b
```

They span phases 8 through 14 and include commits whose whole purpose was
regenerating macros (`ebc7d1f` retiring pooled kill-latency macros; `1191f1b`
putting `UnwantedPrevented` in the paper with numbers).

## Verdict

**The freeze was scoped to the Stage 3 protocol on
`stage3-prep-office-20260812` and has not been in force on `main`.** It is not
this repo's rule to reinterpret and it is not being reinterpreted: it is being
read as written, and as written it governs another branch in another working
copy.

**`561be06` does not need revising.** Had the freeze applied, revising it would
have meant reverting `paper/generated/numbers.tex` and `paper/main.pdf` to their
`1d13868` blobs while keeping `08-threats.tex` and the report — which would leave
`check_paper_numbers.py` failing on `numbers.tex` exactly as it already failed at
`HEAD` before this pass.

## The drift, verified rather than repeated

Claim under test: *`\HarnessLoc` 23,946 → 24,493 across 94 → 95 files, no
experimental number moved, all five generated tables byte-identical.*

Byte-identity of the five tables, `git diff 1d13868 561be06`:

| file | result |
|---|---|
| `table-ablation.tex` | IDENTICAL |
| `table-ambiguity-by-crashpoint.tex` | IDENTICAL |
| `table-deployment-choice.tex` | IDENTICAL |
| `table-latency.tex` | IDENTICAL |
| `table-outcomes.tex` | IDENTICAL |

The **entire** diff of `numbers.tex` over the same range is four lines:

```
-% 94 files; regenerated on every run of this script
-\newcommand{\HarnessLoc}{23\,946}
+% 95 files; regenerated on every run of this script
+\newcommand{\HarnessLoc}{24\,493}
```

Exactly one `\newcommand` changed. `\CoreLoc` is unchanged at `6\,862`
(it appears in the diff only as context), which is the right result: WS-4 touched
`experiments/` and never `aep_core/`.

Cause, established not assumed. `paper_tables.py:2710` counts `*.py` under
`experiments/`, excluding `__pycache__`. Exactly one such file was added between
`numbers.tex`'s previous regeneration (`74ea31f`) and `561be06`:

```
experiments/harness/write_loss.py        364 lines
```

That is the WS-4 drop injector, and it accounts for the 94 → 95 file count. The
remaining ≈183 of the 547 added lines come from growth in existing harness files
(`runner.py`, `redis_kill.py`, `run_matrix.py`) — all WS-4 instrument changes.

**`\HarnessLoc` is a source-line count, not a measurement.** No experimental
quantity moved.

---

# 2. `paper/main-anon.pdf` rebuilt and checked

## Correction to what `561be06`'s report said

I described the stale anon PDF as carrying **the old title**. It did not. The
stale build (2026-09-04 17:59) already had the current title —
*"Declared Ambiguity: Fail-Closed Execution for Non-Idempotent Legacy APIs
Without Idempotency Keys"* — because it postdates the Option A retitle. It was
stale **only** with respect to §VIII, which changed on 2026-09-07. The rebuild
was still needed; the reason given was wrong.

## Rebuild

`bash scripts/build_paper.sh --anonymous` → **rc=0**, *"build clean (main-anon);
verified artifacts promoted atomically"*, 22 pages, 0 undefined references, 0
`\todoitem` markers. The new §VIII paragraph is present in the anonymous text
(the string *"durability signal above it is not trustworthy"* appears once).

## What was checked, and what was found

Needles taken from what the repo actually carries — the public `main.pdf` title
page and the git remote — not from a guessed list.

**Text, all 22 pages** (`pdftotext`), count per needle:

| needle | count | | needle | count |
|---|---|---|---|---|
| `Hamza` / `hamza` | 0 / 0 | | `github` / `gitlab` | 0 / 0 |
| `Khan` / `khan` | 0 / 0 | | `Research-paper-AEP` | 0 |
| `mirhamza` / `hafizmirhamza` | 0 / 0 | | `orcid` / `ORCID` | 0 / 0 |
| `Komatsu` / `komatsu` | 0 / 0 | | `Acknowledgment(e)` | 0 / 0 |
| `@` | 0 | | | |

The only capitalised near-match anywhere is `Mironov`, a **cited author** in the
bibliography (`V. Venkat, I. Mironov, …, "LogAct"`). No author-like `Khan` or
`Hamza` anywhere in the document.

**Title page**, public versus anonymous — the only difference is the byline:

```
main.pdf        …Without Idempotency Keys / Hamza Khan
main-anon.pdf   …Without Idempotency Keys / Anonymous Author(s)
```

**URLs** in the anonymous text — all ten are third-party references
(`redis.io`, `docs.temporal.io`, `datatracker.ietf.org`, `usenix.org`,
`microservices.io`). **No repository URL, no personal or institutional domain.**

**PDF metadata** (`pdfinfo` and a raw object scan): `/Author()`, `/Title()`,
`/Subject()`, `/Creator()`, `/Producer()`, `/Keywords()` — **all empty**. No XMP
metadata stream. No JavaScript, not encrypted.

**Raw object scan** (`strings`, which catches what `pdftotext` cannot):
`Hamza` 0, `Khan` 0, `komatsu` 0, `github` 0, `hafizmirhamza` 0.

### Finding: absolute build paths are embedded in the PDF objects

Not caught by any of the above, because it is in neither the text layer nor
DocInfo:

```
/PTEX.FileName (/mnt/d/personal/AEP/Research-paper-AEP/paper/figures/figure-1-undetected-vs-ambiguity.pdf)
/PTEX.FileName (/mnt/d/personal/AEP/Research-paper-AEP/paper/figures/figure-2-duplicates-by-crash-point.pdf)
```

`pdftex` records the source path of every included PDF figure. This does not
contain the author's name, but it **does contain the repository name**, and
`Research-paper-AEP` resolves by search to
`github.com/hafizmirhamza276-lab/Research-paper-AEP`. Under a double-blind
standard, a searchable string that resolves to the author's account is a
deanonymiser.

**It is pre-existing and was not introduced by this rebuild.** The same two
strings are in the previous anon PDF (read from `git show HEAD:`) and in the
public `main.pdf`.

**Not fixed here** — this pass is "no new work", and the fix is a change to
`scripts/build_paper.sh`.

### Minor, recorded not fixed

`/CreationDate` and `/ModDate` carry `+05'00'`. A timezone is a weak locality
hint, not an identifier. Noted for completeness.

---

# 3. Finding: `check_paper_numbers.py` does not cover the anonymous variant

Nothing would have caught this drift. The build-provenance check runs only when
`build_dir == paper`, and it verifies `paper/main.pdf` against the sources; the
bibliography and undefined-reference checks read `main.bbl`/`main.blg`/`main.log`
— the **public** build's artefacts. `main-anon.pdf` is never inspected, so an
anonymous PDF may lag the sources indefinitely while the checker reports
19 passed, 0 failed.

That is precisely how `main-anon.pdf` came to sit three days behind §VIII.

**Not fixed here**, as instructed. The fix would extend the provenance check to
the anonymous artefact and add the anonymity assertions above as gates, so the
leak class is caught by the checker rather than by someone remembering to look.

---

# 4. Both findings closed (added after the above, same day)

## 4.1 The `/PTEX.FileName` leak: mechanism, and why this route

Four routes were considered and the first three tested on this toolchain
(pdfTeX 3.141592653-2.6-1.40.25, TeX Live 2023):

| route | result |
|---|---|
| **`\pdfsuppressptexinfo=-1`** | **works** — suppresses `/PTEX.FileName`, `/PTEX.PageNumber`, `/PTEX.InfoDict` at source |
| **`\pdfinfoomitdate=1`** | **works** — omits `/CreationDate` and `/ModDate` entirely, taking the `+05'00'` with them |
| relative figure paths | **rejected** — `TEXINPUTS` resolves figures through an absolute `${PAPER}//`, and pdfTeX records the path it *resolved*, so the absolute form is what lands regardless |
| post-process strip | **rejected** — would have to rewrite PDF objects and shift the xref table, risking corruption of the very artefact it protects, and needs a tool the build does not currently require |

Verified on a minimal document before touching the build: baseline had
`/PTEX.FileName` ×1 and `/CreationDate (D:20260907163703+05'00')`; with the
primitives both went to **0**, and the figure still rendered.

`\pdftrailerid{}` was added alongside them — it removes the last per-build
varying identifier and costs nothing.

**They live in `build_paper.sh`'s anonymous `TEXINPUT` string, not in
`main.tex`.** That is the whole reason for the choice: the public build is
untouched *by construction* rather than by a conditional someone could get
wrong. The public PDF is not anonymous and does not need to be.

**Result after rebuild** (`main-anon.pdf`, 22 pages, byline still
`Anonymous Author(s)`, figures still rendering):

| string | before | after |
|---|---|---|
| `/PTEX.FileName` | 2 | **0** |
| `Research-paper-AEP` | 2 | **0** |
| `/mnt/d/personal/…` | 2 | **0** |
| `/CreationDate` | 1 | **0** |
| `/ModDate` | 1 | **0** |

And the public build is confirmed unchanged: `main.pdf` still carries
`/PTEX.FileName` ×2 and `/CreationDate` ×1, exactly as before.

## 4.2 The checker now inspects the anonymous build

`main-anon.pdf` had no provenance stamp at all — `build_paper.sh` wrote one only
for the public build, which is why nothing could tell it was stale. It now gets
its own, `.build-provenance-anon.json`. A **separate** file, deliberately: with
one shared stamp, rebuilding `main.pdf` would silently vouch for a
`main-anon.pdf` nobody had rebuilt, which is the exact failure being closed.

Four new checks in `check_paper_numbers.py`, all against the promoted artefact
rather than a staged one:

1. **not stale** — `paper_provenance.verify(paper, ANON_STAMP_NAME)`
2. **no absolute build path** — `/PTEX.FileName`, the build root, and the repo
   directory name, scanned in raw bytes
3. **DocInfo clean** — `Author`/`Title`/`Subject`/`Keywords`/`Creator`/`Producer`
   present-but-empty, and no `/CreationDate` or `/ModDate`
4. **no byline** — `Anonymous` present, and the public byline absent

**Every needle is derived, never hard-coded.** The build path comes from `ROOT`;
the byline is located *structurally* in `main.pdf` (the line before `Abstract`)
and compared. Writing the author's name into a public repository to check that it
is absent would reintroduce, in the checker, the leak the checker exists to
prevent.

`pdftotext` is required for the byline check because the text layer is
compressed. If it is missing the check **fails closed** — *"I could not look"*
and *"I looked and it is clean"* must never render the same.

## 4.3 Rule 13: the gate was proved able to fail

`scripts/prove_anonymous_gate.sh`. It backs up the good artefacts, reintroduces
each leak, and restores.

**Leak reintroduced** — rebuilt with no primitives and no `\ANONYMOUS`
(`/PTEX.FileName` ×2, `/CreationDate` ×1, byline `Hamza Khan`):

```
PASS  anonymous build is not stale
FAIL  anonymous build leaks no absolute build path
        /PTEX.FileName present; build path '/mnt/d/personal/AEP/Research-paper-AEP';
        build path 'Research-paper-AEP'
FAIL  anonymous build DocInfo is clean
        Creator, Producer, CreationDate/ModDate present
FAIL  anonymous build carries no byline
        no 'Anonymous' byline on page 1; public byline appears verbatim
```

**Staleness, proved separately** — good PDF restored, one source modified:

```
FAIL  anonymous build is not stale
        build artifacts predate the current sources: 1 changed (sections/08-threats.tex)
```

**Restored** — source reverted (0 modifications), artefacts replaced, checker
back to **23 passed, 0 failed**.

All four checks fire on the leak they exist to catch. None is decoration.

## 4.4 The scanner defect, recorded as `docs/25` R13

`grep -c` prints `0` **and exits 1** on no match, so `C=$(grep -c … || echo 0)`
appended a second line: `C` became `"0\n0"`, every `[ "$C" != "0" ]` was true,
and **all sixteen clean needles rendered as hits** on the first anonymity script.

That run was noisy rather than dangerous — the direction was false-positive. One
refactor away (`[ "$C" = "0" ]` for "clean") it reports **clean for everything**,
and a scan that always says clean is precisely what a deanonymised PDF ships
behind.

A second instance appeared in the replacement, in the opposite direction: the
DocInfo regex `(.+?)` with `re.S` ran past its own `)` and closed on the next
key's, so `/Author()/Title()` reported both as populated. It failed on a PDF
verified clean by hand ten minutes earlier, which is the only reason it was
caught rather than "fixed" in the PDF. Repaired with `[^)]+`.

Recorded as **R13** in `docs/25`, cross-referenced to R1 (the `pgrep`/`pkill`
self-match), R2 and R3 — same class: a tool reporting confidently about something
it never measured. Anything that scans for leaks and cannot tell zero from one is
worse than no scan.

## 4.5 A third defect, found *by* the new check

The first public build after wiring the check in failed:

```
- anonymous build is not stale: build artifacts predate the current sources:
  1 added (.provenance.stage.699)
```

`build_paper.sh` stages its promoted artefacts **inside** `paper/` as
`.<job>.<ext>.stage.<pid>` and `.provenance.stage.<pid>`, so they exist under
`paper/` for the duration of a build. `source_digests()` excluded only the names
in `ARTIFACT_NAMES`, so it counted the build's own scaffolding as a **source** —
and the check failed on it.

This was latent, not introduced: the public provenance check only ever ran with
`build_dir == paper`, which is never true *during* a build. The anonymous check
always runs against `paper/`, so it was the first caller to see the staging files
at all.

Fixed in `paper_provenance.py` with a `^\..+\.stage\.\d+$` exclusion, and the
staleness gate was re-proved afterwards to confirm the exclusion was not too
broad: a modified `sections/08-threats.tex` is still reported as
`1 changed`.

## 4.6 Final state

| | |
|---|---|
| `check_paper_numbers.py` | **23 passed, 0 failed** |
| `main-anon.pdf` | `/PTEX.FileName` 0, repo name 0, `/CreationDate` 0 |
| `main.pdf` | `/PTEX.FileName` 2, repo name 2, `/CreationDate` 1 — **unchanged** |
| both builds | `build clean … promoted atomically` |
