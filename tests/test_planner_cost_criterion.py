"""C4' -- and the known-positives that prove it can fail.

``prompts/phase-40-amendment-5-cost-criterion-2026-09-21.md`` §4.5: ``docs/25``
R2 applies to a criterion as much as to a probe. **A criterion that has never
been shown to fail is not evidence that anything passed** -- which is exactly
how C4-as-written survived two stages before anyone noticed it could not be
satisfied at all.

So each limb here has an injected fault it must catch, beside the clean case it
must accept.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "check_planner_cost", ROOT / "scripts" / "check_planner_cost.py"
)
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)

#: The archived live collections. Outside the repository, like every other
#: agent-mode collection, so absence is a skip rather than a failure.
ARCHIVES = [
    Path("/mnt/d/personal/AEP/stub-results/phase40-live-10call-2026-09-18"),
    Path("/mnt/d/personal/AEP/stub-results/phase40-live-10call-retry-2026-09-18"),
    Path("D:/personal/AEP/stub-results/phase40-live-10call-2026-09-18"),
    Path("D:/personal/AEP/stub-results/phase40-live-10call-retry-2026-09-18"),
]

IN_PER_M = 0.20
OUT_PER_M = 1.20
PER_CALL_CEILING = 0.0016288


def usd(prompt_tokens: int, completion: int, reasoning: int) -> float:
    return (
        prompt_tokens * IN_PER_M + (completion + reasoning) * OUT_PER_M
    ) / 1_000_000


def build(tmp_path: Path, calls, *, caps=True, budget_usd=None,
          settle_scale=1.0) -> Path:
    """A minimal but structurally real collection.

    ``calls`` is a list of ``(prompt_tokens, completion_tokens,
    reasoning_tokens)``. One run, because every limb is per-call or per-total
    and a second run adds nothing but noise.
    """
    root = tmp_path / "collection"
    run = root / "run-a"
    run.mkdir(parents=True)

    transcript = []
    journal = []
    total = 0.0
    reservation = usd(2000, 1024, 0)
    for index, (prompt_tokens, completion, reasoning) in enumerate(calls):
        cost = usd(prompt_tokens, completion, reasoning)
        total += cost
        transcript.append({
            "schema_version": "aep.agent.transcript/3",
            "run_id": "run-a",
            "worker_index": 0,
            "step_index": index,
            "attempt": 1,
            "timestamp": "2026-09-21T00:00:00.000Z",
            "prompt": "p",
            "completion": "c",
            "model": "m",
            "snapshot": "2026-07-09",
            "deployment": "d",
            "api_version": "v",
            "reasoning_effort": "low",
            "sampling": {"reasoning_effort": "low"},
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion,
                "reasoning_tokens": reasoning,
            },
            "served_model": "m",
            "outcome": "OK",
        })
        key = f"run-a:0:{index}:1"
        journal.append({"calls": 1, "key": key, "run_id": "run-a",
                        "usd": reservation})
        journal.append({"calls": 0, "key": f"{key}:settle", "run_id": "run-a",
                        "usd": (cost - reservation) * settle_scale})

    (run / "planner-transcript.jsonl").write_text(
        "".join(json.dumps(e, sort_keys=True) + "\n" for e in transcript),
        encoding="utf-8",
    )
    (root / "planner-cumulative.jsonl").write_text(
        "".join(json.dumps(e, sort_keys=True) + "\n" for e in journal),
        encoding="utf-8",
    )
    (run / "planner-budget.json").write_text(
        json.dumps({
            "run_id": "run-a",
            "calls": len(calls),
            "usd": round(total if budget_usd is None else budget_usd, 8),
            "prompt_tokens": sum(c[0] for c in calls),
            "output_tokens": sum(c[1] + c[2] for c in calls),
            "voided": None,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if caps:
        (root / "planner-caps.json").write_text(
            json.dumps({
                "schema_version": "aep.planner.caps/1",
                "in_force": {"per_run_calls": 28, "per_collection_calls": 10,
                             "max_output_tokens": 1024,
                             "max_prompt_tokens": 2000,
                             "per_collection_usd": 20.0},
                "price": {"input_per_million": IN_PER_M,
                          "output_per_million": OUT_PER_M},
                "price_source": {"url": "https://example.invalid/pricing",
                                 "retrieved": "2026-09-17"},
                "per_call_ceiling_usd": PER_CALL_CEILING,
            }, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return root


def failures(findings) -> list[str]:
    return [label for status, label, _ in findings.rows if status == "FAIL"]


# -- the clean case ---------------------------------------------------------

def test_a_healthy_collection_passes_every_limb(tmp_path):
    """The shape of a real stage: short prompts, modest outputs."""
    root = build(tmp_path, [(330, 40, 20), (356, 53, 55)])
    assert failures(checker.check_collection(root)) == []


def test_the_archived_live_collections_pass(tmp_path):
    """C4' must be satisfiable by real data, not only by fixtures.

    This is the other half of the known-positive argument: a criterion nothing
    has ever passed is as suspect as one nothing has ever failed.
    """
    present = [p for p in ARCHIVES if p.is_dir()]
    if not present:
        pytest.skip("archived collections live outside the repository")
    for root in present:
        assert failures(checker.check_collection(root)) == [], root


# -- C4'(a) -----------------------------------------------------------------

def test_a_call_over_the_per_call_ceiling_is_caught(tmp_path):
    """4 000 prompt tokens with output at the cap: 0.0020288 > 0.0016288.

    Reachable, not hypothetical: ``max_prompt_tokens`` is never enforced on the
    outbound request (amendment 5 §4.1), so a prompt this size is dispatched,
    billed and recorded with nothing else objecting.
    """
    assert usd(4000, 1024, 0) > PER_CALL_CEILING
    root = build(tmp_path, [(4000, 1024, 0)])
    caught = failures(checker.check_collection(root))
    assert any("per-call ceiling" in label for label in caught), caught


def test_the_cost_limb_alone_would_miss_a_prompt_overrun(tmp_path):
    """Why (a) needs a token bound as well as a cost bound.

    The ceiling is 0.0004 of input against 0.0012288 of output, so **output
    dominates it**: 4 000 prompt tokens with a small output costs 0.000872 and
    sits comfortably under 0.0016288. The cost bound alone does not notice a
    prompt at twice its cap, and would not until about 8 144 tokens.

    This is the hole the first draft of the criterion had. It is pinned here so
    that removing the token limb fails a test rather than quietly restoring it.
    """
    assert usd(4000, 40, 20) < PER_CALL_CEILING
    root = build(tmp_path, [(4000, 40, 20)])
    caught = failures(checker.check_collection(root))
    assert not any("per-call ceiling" in label for label in caught)
    assert any("token bounds" in label for label in caught), caught


def test_one_token_over_the_prompt_cap_is_caught(tmp_path):
    """2 001 tokens, costing a third of the ceiling, must still fail."""
    root = build(tmp_path, [(2001, 40, 20)])
    assert any("token bounds" in label
               for label in failures(checker.check_collection(root)))


def test_the_ceiling_limb_is_not_merely_generous(tmp_path):
    """One token over must fail, or the bound is decorative."""
    over = build(tmp_path / "over", [(2000, 1024, 1)])
    caught = failures(checker.check_collection(over))
    assert any("per-call ceiling" in label for label in caught), caught
    exact = build(tmp_path / "exact", [(2000, 1024, 0)])
    assert failures(checker.check_collection(exact)) == []


# -- C4'(b) -----------------------------------------------------------------

def test_a_recorded_cost_that_omits_reasoning_tokens_is_caught(tmp_path):
    """The drift the independent recomputation exists for.

    If ``Usage.output`` ever stopped adding reasoning tokens, every bill would
    be understated and no other check in the harness would see it -- on one
    recorded live call reasoning tokens were four times the visible completion.
    Here the budget is written as though they were free.
    """
    calls = [(330, 40, 200)]
    root = build(tmp_path, calls, budget_usd=usd(330, 40, 0))
    caught = failures(checker.check_collection(root))
    assert any("C4'(b)" in label and "planner-budget" in label
               for label in caught), caught


def test_a_price_source_without_a_date_is_caught(tmp_path):
    root = build(tmp_path, [(330, 40, 20)])
    body = json.loads((root / "planner-caps.json").read_text(encoding="utf-8"))
    body["price_source"] = {"url": "https://example.invalid/pricing"}
    (root / "planner-caps.json").write_text(
        json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    caught = failures(checker.check_collection(root))
    assert any("cites a source and a date" in label for label in caught), caught


def test_a_blank_price_source_is_caught(tmp_path):
    root = build(tmp_path, [(330, 40, 20)])
    body = json.loads((root / "planner-caps.json").read_text(encoding="utf-8"))
    body["price_source"] = {}
    (root / "planner-caps.json").write_text(
        json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    assert any("cites a source and a date" in label
               for label in failures(checker.check_collection(root)))


def test_the_repository_itself_cites_a_dated_price_source():
    """C4'(b)'s first limb, against the constant rather than a fixture."""
    from experiments.harness.planner import PRICE_SOURCE

    assert PRICE_SOURCE.get("url", "").startswith("https://")
    assert PRICE_SOURCE.get("retrieved")
    # A date, not a word like "recently".
    year, month, day = PRICE_SOURCE["retrieved"].split("-")
    assert len(year) == 4 and len(month) == 2 and len(day) == 2


def test_the_recomputation_does_not_call_price_usd():
    """Amendment 5 §4.2: comparing the code with itself proves nothing.

    Checked as source, because the whole value of the limb is that it survives
    a change to ``Price.usd`` -- and a checker that called it would not.
    """
    source = (ROOT / "scripts" / "check_planner_cost.py").read_text(
        encoding="utf-8"
    )
    body = source[source.index("def recompute_usd"):
                  source.index("def read_jsonl")]
    assert "Price(" not in body
    assert ".usd(" not in body


# -- C4'(c) -----------------------------------------------------------------

def test_a_positive_settle_is_caught(tmp_path):
    """The fault that makes every other spending control in §3 unsound.

    A settle above zero means the call cost more than its reservation, so the
    reservation was not an upper bound, so the cumulative counter under-counts
    and the USD ceiling can be crossed without the cap ever firing.
    """
    root = build(tmp_path, [(330, 40, 20)], settle_scale=-1.0)
    caught = failures(checker.check_collection(root))
    assert any("C4'(c)" in label for label in caught), caught


def test_limb_c_reads_the_journal_not_the_transcript(tmp_path):
    """(a) and (c) must fail independently, or one of them is redundant.

    A journal whose settles are positive while every transcript entry is small
    is exactly the case where the two records disagree, and it is the reason
    amendment 5 §4.4 keeps both limbs.
    """
    root = build(tmp_path, [(330, 40, 20)], settle_scale=-1.0)
    caught = failures(checker.check_collection(root))
    assert any("C4'(c)" in label for label in caught)
    assert not any("C4'(a)" in label for label in caught)


def test_limb_a_and_limb_c_share_a_threshold_and_that_is_recorded(tmp_path):
    """An honest limitation, pinned so it is not forgotten.

    The reservation is priced at exactly ``max_prompt x max_output``, which is
    also the per-call ceiling -- so (c) fires at the same cost as (a)'s cost
    bound, never earlier. A prompt overrun with a small output breaches
    NEITHER cost check. It is caught only by (a)'s token bound, which is the
    reason that limb exists.
    """
    root = build(tmp_path, [(4000, 40, 20)])
    caught = failures(checker.check_collection(root))
    assert not any("per-call ceiling" in label for label in caught)
    assert not any("C4'(c)" in label for label in caught)
    assert any("token bounds" in label for label in caught)
