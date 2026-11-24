# `predates_rule` is carrying two meanings, and one of them is a lie — 2026-09-24

**Nothing is changed by this note.** No flag was added. `Cell` has the same
three fields and one boolean it had before. This records a defect in
`scripts/check_prereg_order.py`'s vocabulary, found while adding the phase-40
entries, and sets out what fixing it would look like so that a later session can
take it as a decision rather than a discovery.

**Repository state:** `179f0f7` plus this session's uncommitted prereg-order
fix.

---

## 1. What the flag says it means

`scripts/check_prereg_order.py:59-63`:

```python
    #: Set when the cell predates the rule that would have governed it. Rule 5
    #: was adopted in the phase 8 pre-registration (2026-08-27); a cell
    #: collected before it cannot retroactively acquire one, and pretending
    #: otherwise would be the audit lying about its own subject.
    predates_rule: bool = False
```

That is a precise and defensible claim about **time**: the collection happened
before the rule existed, so the absence of a pre-registration is not a
violation, and manufacturing one afterwards would be worse than admitting the
gap. Three of the five current uses mean exactly this:

| root | collected | rule 5 adopted | genuinely predates? |
|---|---|---|---|
| `experiments/results/matrix` | early August 2026 | 2026-08-27 | **yes** |
| `experiments/results/fsync-always` | 2026-08-07 | 2026-08-27 | **yes** |
| `experiments/results/stage3-replication-2026-08-13` | 2026-08-13 | 2026-08-27 | **yes** |

## 2. What it is also being used to mean

Two of the five uses mean something else entirely — *this root is not a
collection, so the rule does not apply to it at all*:

| root | collected | genuinely predates? | what the note actually says |
|---|---|---|---|
| `reports/raw/INCIDENT-fsync-always-destroyed-2026-09-14` | 2026-09-14 | **no**, by 18 days | *"NOT a collection. Quarantined debris from a failed run"* |
| `reports/raw/phase40-deployment-2026-09-18` | 2026-09-18 | **no**, by 22 days | *"NOT a collection. Two Azure metadata files …"* |

Both are **three weeks after** the rule they are marked as predating. The flag
is false about both of them, and the `note` field is doing the real work of
saying why they are exempt.

The second one is this session's. It follows the convention the INCIDENT entry
set in phase 20 rather than inventing a new one, which is the right call for a
table fix — but it doubles the number of entries where the flag says something
untrue, which is the wrong direction for a check whose whole value is that its
output can be read literally.

## 3. Why this matters more here than it would elsewhere

This is not a naming quibble. Three reasons it is worth fixing:

1. **The output is the artifact.** The gate prints `EXEMPT` for both meanings,
   so a reader of the run cannot tell "collected before the rule existed" from
   "this is not data". Those are different facts about the project, and the same
   distinction the closure report insisted on for a different question — *"a
   workstream abandoned because a rule fired and one abandoned because the author
   chose to stop are different facts about a project."*
2. **It hides a real question.** A root marked `predates_rule` is never asked
   whether it has a pre-registration. If a genuine 2026-09 collection were ever
   added with `predates_rule=True` — by copying one of these two entries, which
   is the obvious way to do it — the check would exempt it silently and the
   `note` would be the only thing standing between the project and a
   post-dated collection. That is precisely the failure this check exists to
   surface.
3. **The docstring is now wrong in the file.** `docs/25` R14's rule, which this
   script cites in its own `DOMAIN` banner, is that a green check means green
   over the domain it can *see*. The field comment states a domain narrower than
   the field's actual use, so the code understates what it is exempting.

## 4. What a proper flag would look like

Four changes, all small, none applied.

**(a) The field.** Add to `Cell` (`scripts/check_prereg_order.py:53-63`):

```python
    #: Set when the root is not a collection at all: incident debris,
    #: instrument metadata, anything discovered by ``discover()`` that no
    #: prediction could have predicted because it is not data. Distinct from
    #: ``predates_rule``, which is a claim about TIME -- that the collection
    #: happened before rule 5 existed. A root that is not data does not
    #: predate anything, and marking it so makes the table say something
    #: false about a date in order to reach the exemption branch.
    not_a_collection: bool = False
```

**(b) The exemption branch** in `audit()`, currently keyed on `cell.predates_rule`
alone, becomes a two-way branch so the verdict column distinguishes them:

```python
        if cell.predates_rule or cell.not_a_collection:
            verdict = "NOT-DATA" if cell.not_a_collection else "EXEMPT"
            rows.append((root, "n/a", "n/a", data_sha[:7], data_date[:10],
                         verdict))
            continue
```

**(c) A guard, which is the part that earns the change.** Without it this is
cosmetics:

```python
        # A root marked as predating rule 5 but committed after it was adopted
        # is either mislabelled or a post-dated collection. Both are findings.
        if cell.predates_rule and not cell.not_a_collection:
            if data_date and data_date[:10] > RULE_5_ADOPTED:
                failures.append(
                    f"{root}: marked predates_rule but its first data commit "
                    f"is {data_date[:10]}, after rule 5 was adopted on "
                    f"{RULE_5_ADOPTED}. Either it is not a collection (set "
                    "not_a_collection) or it was collected without a "
                    "pre-registration."
                )
```

with `RULE_5_ADOPTED = "2026-08-27"` as a module constant, which the field
comment already names in prose but the code does not hold anywhere.

**(d) The two existing entries** move from `predates_rule=True` to
`not_a_collection=True`, and the phase-40 entry's note loses its apology for
borrowing the flag.

**(e) The counters line.** `cells: 35   ok: 30   exempt: 5   failing: 0`
becomes `exempt: 3   not-data: 2`, which is the line an artifact evaluator
actually reads.

## 5. What it would cost, and the one reason to hesitate

**Cost:** about 25 lines across `Cell`, `audit()` and two table entries, plus
`tests/test_prereg_order.py` — which has 11 tests and would want two more: one
that a `not_a_collection` root is exempted and reported as such, and one that
the guard in (c) fires on a `predates_rule` root with a post-adoption data
commit. The counters line is asserted in that file, so it changes there too.

**The hesitation:** this edits a **gate**, and the project's own convention is
that a gate's semantics are the author's call, not a passing session's. The
change also alters the printed output that phase reports quote verbatim, so any
report quoting `exempt: 4` or `exempt: 5` becomes a record of a different
program. That is an argument for doing it deliberately and noting it, not for
leaving it.

**Recommendation:** worth doing, and worth doing with (c) rather than without
it. A rename alone improves the vocabulary and catches nothing; the guard is
what turns the distinction into a check. Until then, the `note` field is the
only thing recording which meaning is intended, and this file is the record that
the ambiguity is known rather than accidental.

---

## 6. State after this session's change

For the avoidance of doubt about what was and was not done:

| root | flag set | meaning intended | flag truthful? |
|---|---|---|---|
| `experiments/results/matrix` | `predates_rule` | predates rule 5 | yes |
| `experiments/results/fsync-always` | `predates_rule` | predates rule 5 | yes |
| `experiments/results/stage3-replication-2026-08-13` | `predates_rule` | predates rule 5 | yes |
| `reports/raw/INCIDENT-fsync-always-destroyed-2026-09-14` | `predates_rule` | not a collection | **no** |
| `reports/raw/phase40-deployment-2026-09-18` | `predates_rule` | not a collection | **no** |

Five exemptions, two of them mislabelled, both saying so in their notes and
both pointing here.
