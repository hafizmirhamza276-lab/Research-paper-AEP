# Claims to review

**This file changes no manuscript text.** It collects places where a claim may
be factually wrong, or may sit awkwardly beside a claim made elsewhere in the
paper, so that the independent audit has them in one list. Entries are raised
during the prose passes, which are language-only and may not resolve them.

**A prose pass never resolves an entry here.** If a rewrite would settle a
question of fact by choosing different words, the wording stays as close to the
original as possible and the question is recorded below instead.

| status | meaning |
|---|---|
| **open** | raised, not investigated |
| **checked** | investigated and found not to be a problem, with the reason |
| **resolved** | the manuscript was changed by an author decision, with the commit |

---

## 1. §I says the uncertainty is *never* in the accounts; the evidence for that is scoped to what was measured

**Status: open.** Raised 2026-09-22 during the §I prose pass, under the author's
ruling that the original absolute be restored rather than softened by a language
edit.

### The absolute

`paper/sections/01-introduction.tex`, closing the trilemma discussion:

> What a designer can choose is where the uncertainty is allowed to surface.
> AEP places it in a durable state that an operator can see, and **never in the
> accounts**.

This was the original wording. A draft of the §I rewrite had weakened it to
*"and keeps it out of the accounts"*; the author ruled that a language pass must
not weaken a claim, so *never* is restored and the question is recorded here.

### The scoped statements it sits beside

**C3, in the same section**, states the same property with a scope condition:

> AEP records no undetected duplicate and no lost effect **in any cell
> measured**, and the baselines without a pre-dispatch record duplicate in most
> crashed executions.

**`paper/sections/08-threats.tex`**, *The detection finding has no referent
outside this artifact*:

> Nothing external to this artifact establishes that a pre-dispatch record
> without an fsync barrier suffices for detection: the proposition is supported
> by two systems we wrote, measured by a harness we wrote, against a provider we
> wrote.

**`paper/sections/06-evaluation.tex`**, `sec:eval-writeloss-cell`, on the
write-loss regime:

> `WAITAOF` returned success for every durability acknowledgement requested
> after the device had stopped accepting writes […] The barrier withholds
> dispatch on a *failed or absent* acknowledgement; it was handed a successful
> one and dispatched, behaving exactly as specified on an input that was false.

and, a little later, that the result *"bounds the guarantee to storage that
reports its own failures and says nothing about storage that does not."*

### The question for the audit

*Never* is a claim about the protocol. *In any cell measured* is a claim about
the collection. They are compatible if *never* is read as a statement of what
the protocol is designed to do, and in tension if a reader takes it as a
statement about what was observed to happen. The write-loss regime is the case
worth checking: there, AEP dispatched on an acknowledgement that was false, so
an effect was applied while the durability of its own record could not be
established.

Three things a reader might want settled, none of which a prose pass can decide:

1. Is *never* intended as a design property or as an empirical one?
2. Under the write-loss regime, could an applied effect have reached the
   accounts with no durable record accounting for it? `summary.json` reports
   `lost_effect` at zero throughout, so the answer may be no, in which case this
   entry closes as **checked**.
3. If *never* is meant empirically, should §I carry the same scope condition C3
   already carries?

**No text is changed by this entry.**
