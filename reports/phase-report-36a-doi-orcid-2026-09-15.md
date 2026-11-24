# Phase 36a — the reserved DOI and the ORCID, recorded accurately

## Asked / Done

Asked: record `10.5281/zenodo.22766567` and the ORCID across README,
`ARTIFACT.md` §5, `docs/29`, `docs/36` and the paper's author block, without any
sentence implying the DOI resolves today; prove the anonymous build does not
leak either.

Done: all of it. **The anonymous PDFs were grepped for ten needles each and
returned zero, with a control proving the test is not passing vacuously.**

The check that asserts it is now permanent, and it caught a false positive of
its own on the first run.

---

## 1. Each document, before and after

### `README.md`

**Before:** *"The raw run archive is **two parts, built and verified but not yet
deposited**, so no DOI exists yet."*

**After:** *"…built and verified, with a Zenodo record reserved under DOI
`10.5281/zenodo.22766567`"*, followed by a block quote that cannot be skimmed
past:

> **The DOI does not resolve yet.** It is *reserved*, not registered: the
> identifier is fixed, the record is still a draft, and the files are not
> uploaded. Clicking it today will not work. It begins resolving when the record
> is published, which `docs/29` is the checklist for.

The phase-35 totals are unchanged (2 790 run directories, 44 794 files across
two archives) and the two declared-outside trees still stand. A second edit
replaced *"until that deposit happens"* with the copy count: **two copies of
each archive, on two filesystems, both on one machine** (step 6).

A new **Author** section carries the ORCID and states that the anonymous build
suppresses it — *"asserted by a test, not assumed"*, which §3 makes true.

### `ARTIFACT.md` §5

**Before:** *"As of 2026-09-03 they are assembled and verified but not uploaded:
no DOI or archive URL exists yet."*

**After:** the same item **edited, not deleted** — two archives, the reserved
identifier, *"the record is a draft and the files are not uploaded, so the DOI
does not resolve yet"*, and what remains: the upload, the post-upload checksum
verification, the publish step.

### `docs/29`

New §0c records the identifier and its state, ticks the two things the
reservation genuinely closes, and leaves four items **open and unticked**:
upload both archives, verify post-upload checksums *each against its own
manifest*, publish, then re-render and tag.

### `docs/36`

The reader table's "raw runs" row now names the reserved DOI, marks it **not yet
resolving**, and points at both archives and both mirrors.

### `paper/main.tex`

The toggle already rendered availability from `\archivedoi` with two states,
PENDING and anything-else. Setting the reserved DOI would have selected the
second — *"deposited at https://doi.org/…"* — which is false today. So it now
has **three**:

```
\newcommand{\archivedoi}{10.5281/zenodo.22766567}
\newcommand{\archivedoistate}{RESERVED}
```

and the RESERVED branch renders *"prepared and verified, with the Zenodo record
reserved under DOI …; the identifier is fixed and begins resolving when the
record is published."* Confirmed in the built PDF: **"deposited at" occurs zero
times.**

The ORCID sits in the non-anonymous branch only, beside the correspondence
footnote, with a comment saying why: it identifies the author as surely as the
name does.

## 2. The anonymity check, and its output

Both anonymous PDFs, ten needles each, across the text layer, the DocInfo
dictionary **and the raw bytes**:

```
--- paper/main-anon.pdf ---            --- paper/supplementary-anon.pdf ---
  ok  0009-0005-9380-2188  0 0 0         ok  0009-0005-9380-2188  0 0 0
  ok  0009-0005            0 0 0         ok  0009-0005            0 0 0
  ok  9380-2188            0 0 0         ok  9380-2188            0 0 0
  ok  Hamza                0 0 0         ok  Hamza                0 0 0
  ok  Khan                 0 0 0         ok  Khan                 0 0 0
  ok  hafizmirhamza276     0 0 0         ok  hafizmirhamza276     0 0 0
  ok  22766567             0 0 0         ok  22766567             0 0 0
  ok  zenodo               0 0 0         ok  zenodo               0 0 0
  ok  10.5281              0 0 0         ok  10.5281              0 0 0
  ok  hafizmirhamza276-lab 0 0 0         ok  hafizmirhamza276-lab 0 0 0
```

**And the control, because a suppression test that passes because the string was
never emitted proves nothing:**

```
main.pdf  0009-0005-9380-2188      1
main.pdf  Hamza Khan               1
main.pdf  22766567                 1
occurrences of "deposited at":     0
```

## 3. The check is now permanent — and it caught its own false positive

`check_anonymous_build` gained a fourth part. Like the byline check beside it,
the needles are **derived, never written into that file**: ORCIDs by shape from
the public PDF, and the archive DOI read from `main.tex`'s `\archivedoi`.

**The first version failed, correctly, on something I had not anticipated:**

```
FAIL  anonymous build carries no byline
      identifier '10.5555/1286831.1286846' survives the anonymous build
```

That is a **cited reference's** DOI, present in both builds by design. Matching
every DOI on the page was too broad — a bibliography entry is not an identifying
string. Narrowed to the archive's DOI specifically. The check also fails if the
public build contains *no* ORCID or DOI at all, so it cannot start passing
because the strings stopped being emitted.

## 4. What is still pending before the DOI is live

1. Upload both archives — `aep-raw-archive` (26 300 files) and
   `aep-raw-archive-ext` (18 494).
2. Verify post-upload checksums against the local manifests, **each archive
   against its own** — `docs/29` §0b warns against inventing a combined manifest
   at upload time.
3. Publish the record. **This is the step that makes the DOI resolve.**
4. Re-render the paper so `\archivedoistate` becomes the deposited form, then
   tag `v1.0.0`.

Until then: two copies of each archive, on two filesystems, **both on one
machine**.

## 5. Raw outputs

```
check_paper_numbers.py   43 passed, 0 failed
validate_citations.py    OK: 371 citations, 0 invalid
builds                   supplementary, supplementary-anon, anon, main -- exit 0
pages                    main 23, supplementary 6
anonymous leak check     20 needles across 2 PDFs -> 0 hits
control                  3 needles in main.pdf -> 3 hits
"deposited at" in main   0
.tex changed             paper/main.tex only, author block and DOI switch
generated/ touched       none
numeric claims changed   0
```
