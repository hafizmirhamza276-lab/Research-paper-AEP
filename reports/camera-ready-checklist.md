# Camera-ready checklist

**Started 2026-09-23 by author decision**, on the occasion of the T2 retitle.

**What belongs here.** Things that are **invisible to a double-anonymous
reviewer** and therefore cannot be caught by the submission gates, but that
would be wrong, stale or embarrassing once the paper is de-anonymised and the
artifact is public. The anonymous build strips the author, the contact, the
ORCID and every artifact URL, so anything reachable only through those is
outside the reviewers' view and outside `prove_anonymous_gate.sh`'s.

**What does not belong here.** Submission blockers, which are visible now and
are tracked in `PAPER_ROADMAP.md` and the session handoffs. The Zenodo deposit
is the live example: `\archivedoistate` is `RESERVED`, the DOI does not
resolve, and a reviewer *can* see that — it is a blocker, not a camera-ready
item. It appears in §4 below only because the same edit closes both.

| status | meaning |
|---|---|
| **open** | recorded, not done |
| **done** | done, with the commit |

---

## 1. The artifact still carries the framing the paper dropped

**Status: open.** Recorded 2026-09-23, deliberately not fixed.

### 1.1 `pyproject.toml:8`

```toml
description = "Agent Execution Protocol — fail-closed execution for agents
               calling non-idempotent legacy APIs"
```

Two problems in one line.

* **It expands AEP**, and the manuscript decided on 2026-09-23 not to
  (`reports/phase-report-51` §5, author decision E3). The paper introduces AEP
  as a bare name at `01-introduction.tex:65`; the package metadata expands the
  same letters differently and publicly.
* **It says the protocol is "for agents"**, which is the Option B framing
  `241292e` removed from the manuscript on **2026-09-04**. `docs/33` §0's
  banner: autonomous agents are *"the motivating deployment context in §I and
  §II rather than the subject."* The package description makes them the
  subject.

**Why it is invisible now:** the anonymous build renders
`\artifactavail` as *"available via the submission system"*, so no reviewer
reaches the repository. **Why it matters at camera-ready:** the non-anonymous
build prints the URL, and the one-line description is the first thing a reader
sees on the package page.

### 1.2 `README.md:1`

```markdown
# Agent Execution Protocol (AEP)
```

Same expansion problem, in the artifact's most-read line. The title beneath it
was updated to T2 in `67092b2`; this heading was not, because it is the
repository's name rather than the paper's.

### 1.3 What to decide, not just what to change

These two are the artifact's identity, not the paper's, and renaming a public
repository is a different act from retitling a manuscript. **Three options, for
the camera-ready decision:**

1. **Change both to match E3** — drop the expansion, describe the protocol
   without naming a caller class.
2. **Change only the "for agents" clause**, keeping the expansion as the
   repository's own name, and add a line to `README.md` saying the paper uses
   AEP as a bare name.
3. **Leave both and disclose**, with a sentence in `README.md` explaining that
   the repository predates the 2026-09-04 reframing.

**Recommendation: 1.** The reason the manuscript gives for not expanding is
that no expansion is accurate, and that reason does not stop at the repository
boundary.

---

## 2. Identity, restored on purpose

**Status: open — these are correct as they stand and must be *verified*, not
changed.**

Everything below lives in `main.tex`'s `\else` (non-anonymous) branch and is
absent from the anonymous one. At camera-ready the non-anonymous build is the
one submitted, so each becomes reviewer-visible for the first time.

| item | location | check |
|---|---|---|
| author name | `main.tex:185` region, `\authorname` | spelled and ordered as the author wants it in the IEEE record |
| affiliation and contact | `\authorcontact` | current at the time of publication, not at the time of writing |
| ORCID | `main.tex:199` | `0009-0005-9380-2188` resolves and is the right person |
| artifact URL | `\artifacturl`, `\artifactavail` | resolves, and the repository is public |
| archive availability | `\archiveavail` | see §4 |

**The AI disclosure differs between the two builds and that is deliberate.**
The anonymous one (`main.tex:167`) says *"generative AI coding and drafting
assistants"* without naming vendors; the non-anonymous one (`main.tex:203`)
names Anthropic's Claude and OpenAI's Codex, and points at commit trailers and
`.claude/agents/` for model identifiers. **At camera-ready the full one is what
prints. Confirm it is still accurate** — it claims the identifiers are recorded
in the artifact, which has to remain true.

---

## 3. Records that keep the old title, and should

**Status: open — a note, not an edit.**

`docs/26-journal-readiness-direction.md`, `docs/29-archive-deposit.md` and
several files under `reports/` quote *"Declared Ambiguity: Fail-Closed
Execution for Non-Idempotent Legacy APIs Without Idempotency Keys"*, and
`reports/phase-report-51` quotes both that and the pre-2026-09-04 title.

**They are dated records of decisions, not current statements, and rewriting
them would falsify the record.** `67092b2` left them alone on purpose.

**The camera-ready action is a one-line note, not a sweep:** if the artifact is
published with these files in it, a reader may meet three titles. A dated line
at the top of `docs/26` and `docs/29` saying which title is current, and
pointing at `reports/phase-report-51`, costs nothing and prevents the
confusion.

`ARTIFACT.md` was a genuine miss rather than a record — it carried the
**pre-2026-09-04** title in a file describing the *current* artifact, for
nineteen days. Fixed in `67092b2`.

---

## 4. The Zenodo deposit — a submission blocker that closes here too

**Status: open. This is the live submission blocker and is tracked elsewhere;
it appears here because one edit closes both.**

`main.tex:145` is `\newcommand{\archivedoistate}{RESERVED}`. A reserved Zenodo
DOI is minted but does not resolve until the record is published, so
`\archiveavail` renders the honest *"not yet deposited"* sentence and a
reviewer cannot verify the evidence.

`main.tex:135-139` records that **inserting the real DOI is a one-line edit
there and nowhere else** — every rendering derives from it and no section file
contains a DOI string. The deposit procedure is `docs/29-archive-deposit.md`:
one record, six files, date-suffixed, manual web upload.

**Camera-ready check:** `\archivedoistate` is no longer `RESERVED`, and
`10.5281/zenodo.22766567` resolves to a published record whose contents match
the two `MANIFEST.sha256` files.

---

## 5. How to use this file

Work it top to bottom **after acceptance and before the camera-ready
deadline**, not before: §2 in particular is verification of things that are
deliberately absent from every build a reviewer sees, and there is nothing to
check until the non-anonymous build is the one being submitted.

Add to it whenever a session finds something that the anonymous build hides.
That is the test for belonging here: **would the submission gates catch it?**
If yes, it is a blocker and belongs in the roadmap. If no, it belongs here.
