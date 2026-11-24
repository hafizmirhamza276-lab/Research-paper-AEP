# Amendment 1 — the deployment reports an alias, not a snapshot

**Amends `prompts/phase-40-agent-reachability.md`.** The pre-registration is
not edited. Its preamble says amendments are expected and will be recorded as
amendments, and that "a pre-registration quietly adjusted before it was ever
committed" is the thing to avoid. This is the record.

Written before the 10-call stage runs. Four calls exist at the time of writing,
all configuration probes, costing **USD 0.00016620** in total.

---

## 1. What was fixed, and what the first live calls found

The author's fixed decisions included **"snapshot pinned, not an alias"**.

`POST https://kps-rnd-foundry.cognitiveservices.azure.com/openai/responses`
returns:

```json
"model": "gpt-5.6-luna"
```

That is the **deployment name**. It carries no version. Azure AI Foundry echoes
the deployment, not the underlying model build, and there is no other field in
the payload that carries one.

**So the response cannot verify which model version served a call.** Not "does
not by default" — cannot. No configuration change makes it.

## 2. The pin, and where its evidence lives

The version is readable from the control plane even though the data plane will
not report it:

| | |
|---|---|
| model | `gpt-5.6-luna` |
| **version** | **`2026-07-09`** |
| deployment type (sku) | **`GlobalStandard`** |
| account kind | `AIServices` |
| region | `eastus2` |
| RAI policy | `Microsoft.DefaultV2` |
| `capabilities.responses` | `true` |

**The pin is therefore: version `2026-07-09`, deployment `gpt-5.6-luna`, plus
the collection date.** Recorded here because the response cannot carry it.

This is weaker than a response-side check, and the difference should be stated
plainly: it is an observation made once, out of band, not a property asserted
on every call. A call made an hour after the observation is covered by it only
by assumption.

**The evidence is archived, not asserted.**
`reports/raw/phase40-deployment-2026-09-18/` holds the machine-readable source:

* `deployment-show.json` — `az cognitiveservices account deployment show`,
  carrying `model.version`, `sku.name` and `versionUpgradeOption`
* `account-show.json` — the account kind, primary endpoint and custom subdomain

Subscription id, tenant id and the creator's identity are redacted; everything
the claim rests on is intact. ARM output rather than a screenshot because it is
machine-readable, diffable, and re-runnable by a reviewer with access.

The portal shows the same version (`Foundry > Models > Deployments >
gpt-5.6-luna`, detail pane `v:2026-07-09`), which is where it was first seen.

## 3. Auto-upgrade is ON, and this is the serious part

```
"versionUpgradeOption": "OnceNewDefaultVersionAvailable"
```

**The deployment will move to a new model version by itself, when Microsoft
designates a new default.** Nobody has to do anything for the pin in §2 to stop
being true.

This was checked rather than assumed, and it came back the unfavourable way.
The consequences, stated rather than softened:

* `2026-07-09` is what served the collection **as observed at collection
  time**. It is not a guarantee about any later call.
* An upgrade would leave **no trace whatsoever in the collected data.** The
  transcripts would be identical in shape and the `model` field would still say
  `gpt-5.6-luna`. There is no artefact, anywhere, that would reveal it.
* Re-running this collection later may silently run a different model. Any
  re-run must capture `deployment-show.json` again and compare, because that is
  the only thing that can tell.

**Setting `versionUpgradeOption` to `NoAutoUpgrade` would materially strengthen
the pin.** It is not done here: it is a change to a shared Azure resource in a
project that is not this paper's, and that is the author's decision to make,
not this amendment's. If it is done before the collection, this amendment
should be superseded by one recording the change and its date.

**Decided 2026-09-18: auto-upgrade was found ON and is left ON.** The exposure
stands exactly as recorded above — the collection is covered by a pin that is
true as observed and carries no guarantee for any later call, and §6's sentence
about the paper is written on that basis rather than in anticipation of a
stronger one.

## 4. The endpoint the collection uses

The portal shows a project endpoint at
`https://kps-rnd-foundry.services.ai.azure.com/`, while the collection calls
`https://kps-rnd-foundry.cognitiveservices.azure.com/`. They resolve to the
same deployment: ARM reports a single `AIServices` account with
`customSubDomainName: kps-rnd-foundry`, and all of
`cognitiveservices.azure.com`, `services.ai.azure.com` and `openai.azure.com`
are surfaces of that one account. There is one `gpt-5.6-luna` deployment
resource beneath it. Confirmed from `account-show.json`, at no cost — no call
was needed.

They are not interchangeable in what they *serve*, though.
`services.ai.azure.com` is listed against the AI Foundry and Model Inference
APIs, which expose `/models/...`, not the OpenAI `/openai/responses` route.

**The collection uses
`https://kps-rnd-foundry.cognitiveservices.azure.com/openai/responses?api-version=2025-04-01-preview`**
— ARM's `properties.endpoint` for the account, and the route empirically shown
to serve a real inference.

The route was itself a finding and is recorded in commit `511603a`: the
per-deployment path `/openai/deployments/{name}/responses` 404s here at both
`2025-01-01-preview` and `2025-04-01-preview`. Holding the path fixed and
moving only the version is what established that the route, not the version,
was the problem.

## 5. What changes in the code

**The response-side snapshot check is removed**, with its own test.

`AEP_PLANNER_SNAPSHOT` is **not** set to the alias under any wording. Setting it
to `gpt-5.6-luna` would make `SnapshotMismatch` unraisable: it would pass on
every call and could never fail. **A check that cannot fail is worse than no
check**, because in the record it reads as verification that happened. It is
removed, and its absence is stated here.

What replaces it is recording rather than checking. Every transcript entry
carries both:

* `snapshot` — the ARM-read version, `2026-07-09`, **recorded, not verified**;
* `served_model` — what the response actually said, `gpt-5.6-luna`, so the
  archive shows on its face that the API reported an alias.

A reviewer can see the gap instead of having to know about it.

## 6. What the paper must now say

**The model behind this deployment could have changed between collection and
publication without leaving any record in the data**, and with auto-upgrade
enabled that is a live possibility rather than a theoretical one. Nothing in
the transcripts would show it. A reader cannot tell from the archive whether
two calls a month apart were served by the same model build.

This is a limitation of the hosted dependency, not of the protocol. Nothing
about AEP, the harness, the oracle or the matrix is weakened by it; the
uncertainty is entirely on the side of the caller used to demonstrate
reachability.

`docs/33` §3.2 is what keeps it survivable, and it was written for exactly this:

> a hosted API is "a remote, versioned, silently-updated dependency with no
> digest, no pin, and no guarantee that the same prompt returns the same
> completion tomorrow… **No number that reaches the manuscript may come from
> it.**"

That rule stands and is now load-bearing rather than precautionary.

It sharpens one sentence. The claim is that these failure modes were reachable
**by a real LLM caller, through a named deployment, on a stated date** — not by
a named model version. Any prose must give the deployment and the date, must
point at the archived transcripts and at
`reports/raw/phase40-deployment-2026-09-18/`, and **must not name a model
version as though the data evidenced it.** If the version is mentioned at all
it must be attributed to the control-plane reading, with its date, and
accompanied by the fact that auto-upgrade was enabled.

## 7. What is unchanged

Everything else. §1's design, §1.1's harness-assigned target, §2's metric and
its prohibition on rates, §3's five controls and their numbers, §4's
`PLANNER_FILTERED`, §6's staging, §7's provider-dependence prose, §8's failure
definitions, §9's stop rule.

`reasoning.effort=low` is **confirmed accepted and applied**: 71 reasoning
tokens were returned in `output_tokens_details` on the resolving call, which
only appears when the reasoning path ran. §3's `max_tokens` of 1 024 and the
2 000-token input bound are unchanged.

One thing worth recording for §4: the deployment's RAI policy is
`Microsoft.DefaultV2`, so content filtering is on, and `PLANNER_FILTERED` is a
class that can genuinely occur rather than a defensive placeholder.
