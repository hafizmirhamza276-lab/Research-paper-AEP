"""The bibliography sweep's ability to FAIL, pinned.

Phase 6 measured `verify_refs.py` exiting 0 after 14 of its 23 lookups failed.
The defect was structural -- ``main()`` ended in an unconditional ``return 0``
-- and it survived two audits and two commits because nothing exercised the
script at all: no test, no CI job, no Makefile target.

These tests pin the two properties that failure mode needs:

1. a non-resolved lookup produces a **non-zero exit**, and
2. the sweep list is **derived from `refs.bib`**, is **non-empty**, and has the
   **count it is expected to have**.

Point 2's last two clauses are not redundant. A derivation that silently yielded
an empty list would satisfy a set-equality assertion against a mis-parsed
`refs.bib`, sweep nothing, and exit 0 -- the same hollow success one level up.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts import verify_refs

BACKSLASH = chr(92)

# Counts measured from paper/refs.bib on 2026-08-21. They are asserted rather
# than derived so that adding a citation fails this test loudly instead of
# being tracked silently -- a new entry must be routed deliberately.
EXPECTED_TOTAL = 34
EXPECTED_URL = 13
EXPECTED_DOI = 14
EXPECTED_DBLP = 7


@pytest.fixture(scope="module")
def entries():
    return verify_refs.parse_bib()


@pytest.fixture(scope="module")
def grouped(entries):
    return verify_refs.routes(entries)


# --------------------------------------------------------------------------
# 1. the derivation is real: non-empty, correctly sized, and matches refs.bib
# --------------------------------------------------------------------------


def test_derived_sweep_list_is_not_empty(grouped):
    """An empty derivation would pass set-equality and verify nothing."""
    assert grouped["url"], "no URL-bearing entries derived from refs.bib"
    assert grouped["doi"], "no DOI-bearing entries derived from refs.bib"
    assert grouped["dblp"], "no title-only entries derived from refs.bib"


def test_route_counts_are_exactly_as_expected(entries, grouped):
    assert len(entries) == EXPECTED_TOTAL
    assert len(grouped["url"]) == EXPECTED_URL
    assert len(grouped["doi"]) == EXPECTED_DOI
    assert len(grouped["dblp"]) == EXPECTED_DBLP
    assert (
        len(grouped["url"]) + len(grouped["doi"])
        + len(grouped["dblp"]) + len(grouped["none"]) == len(entries)
    ), "every entry must land in exactly one route"


def test_derived_urls_match_refs_bib_exactly(grouped):
    """The sweep list is refs.bib's URL set -- not a hand-maintained copy.

    This is the assertion that would have caught all three drifts Phase 6 found:
    two URLs swept at addresses no entry used, and one entry never swept.
    """
    raw = Path(verify_refs.DEFAULT_BIB).read_text(encoding="utf-8")
    raw = "\n".join(l for l in raw.splitlines() if not l.lstrip().startswith("%"))
    in_bib = set(
        re.findall(
            r"howpublished\s*=\s*\{" + re.escape(BACKSLASH) + r"url\{([^}]+)\}\}", raw
        )
    ) | set(re.findall(r"(?<![a-z])url\s*=\s*\{([^}]+)\}", raw))
    derived = {e.url for e in grouped["url"]}
    assert derived == {u.strip() for u in in_bib}


def test_every_entry_has_a_verification_route(grouped):
    """A citation that nothing can check is a defect, not an omission."""
    assert grouped["none"] == [], "unrouted entries: %s" % [e.key for e in grouped["none"]]


# --------------------------------------------------------------------------
# 2. the sweep can fail
# --------------------------------------------------------------------------


def test_failed_lookup_produces_non_zero_exit(monkeypatch, capsys):
    monkeypatch.setattr(verify_refs, "check_url",
                        lambda e: (verify_refs.FAILED, "HTTP 404"))
    monkeypatch.setattr(verify_refs, "check_doi",
                        lambda e: (verify_refs.RESOLVED, "HTTP 200"))
    monkeypatch.setattr(verify_refs, "check_dblp",
                        lambda e, **k: (verify_refs.RESOLVED, "1 hit(s)"))
    monkeypatch.setattr(verify_refs.time, "sleep", lambda *_: None)
    assert verify_refs.main([]) == 1
    assert "DO NOT TRUST THE BIBLIOGRAPHY" in capsys.readouterr().out


def test_zero_hits_produces_non_zero_exit(monkeypatch):
    monkeypatch.setattr(verify_refs, "check_url",
                        lambda e: (verify_refs.RESOLVED, "HTTP 200"))
    monkeypatch.setattr(verify_refs, "check_doi",
                        lambda e: (verify_refs.RESOLVED, "HTTP 200"))
    monkeypatch.setattr(verify_refs, "check_dblp",
                        lambda e, **k: (verify_refs.ZERO_HITS, "0 hits"))
    monkeypatch.setattr(verify_refs.time, "sleep", lambda *_: None)
    assert verify_refs.main([]) == 1


def test_all_resolved_exits_zero(monkeypatch):
    for name in ("check_url", "check_doi"):
        monkeypatch.setattr(verify_refs, name, lambda e: (verify_refs.RESOLVED, "HTTP 200"))
    monkeypatch.setattr(verify_refs, "check_dblp",
                        lambda e, **k: (verify_refs.RESOLVED, "2 hit(s)"))
    monkeypatch.setattr(verify_refs.time, "sleep", lambda *_: None)
    assert verify_refs.main([]) == 0


def test_allow_transient_tolerates_exactly_its_budget(monkeypatch):
    calls = {"n": 0}

    def one_failure(entry):
        calls["n"] += 1
        return (verify_refs.FAILED, "HTTP 503") if calls["n"] == 1 else (verify_refs.RESOLVED, "HTTP 200")

    monkeypatch.setattr(verify_refs, "check_url", one_failure)
    monkeypatch.setattr(verify_refs, "check_doi", lambda e: (verify_refs.RESOLVED, "HTTP 200"))
    monkeypatch.setattr(verify_refs, "check_dblp", lambda e, **k: (verify_refs.RESOLVED, "1 hit(s)"))
    monkeypatch.setattr(verify_refs.time, "sleep", lambda *_: None)
    assert verify_refs.main(["--allow-transient", "1"]) == 0
    calls["n"] = 0
    assert verify_refs.main(["--allow-transient", "0"]) == 1


def test_offline_mode_makes_no_network_call(monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("--offline must not touch the network")

    monkeypatch.setattr(verify_refs.urllib.request, "urlopen", explode)
    assert verify_refs.main(["--offline"]) == 0
