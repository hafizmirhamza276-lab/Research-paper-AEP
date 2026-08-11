"""Verify that every bibliography entry the manuscript cites actually exists.

`PAPER_ROADMAP.md` §5's Phase 4 prompt says "verify each BibTeX entry exists;
do not fabricate", and this session's amendment F4 escalates a fabricated
reference to a D4-level halt. Prose cannot discharge that; a lookup can.

The check is deliberately dumb: for each query, ask DBLP's public search API
and print every hit verbatim, so a human (or the session report) can compare
the printed authors/venue/year/DOI against what `paper/refs.bib` claims. It
does not attempt to decide correctness itself -- a matcher that scored its own
homework would be exactly the failure mode being guarded against.

Usage:
    python scripts/verify_refs.py                # the manuscript's whole list
    python scripts/verify_refs.py "some title"   # one ad-hoc query
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request

#: One query per bibliography entry that has a DBLP-indexed publication.
#: Non-indexed sources (vendor documentation, RFCs, software releases) are
#: verified by fetching the live URL instead and are listed in
#: ``NON_DBLP_SOURCES`` for the record.
QUERIES: tuple[str, ...] = (
    "Leases Efficient Fault-Tolerant Mechanism Distributed File Cache Consistency",
    "Sagas Garcia-Molina Salem",
    "Chubby lock service for loosely-coupled distributed systems",
    "ARIES transaction recovery method supporting fine-granularity locking",
    "On optimistic methods for concurrency control Kung Robinson",
    "Impossibility of distributed consensus with one faulty process",
    "In Search of an Understandable Consensus Algorithm Raft",
    "Life beyond Distributed Transactions an apostate's opinion",
    "Idempotence is not a medical condition Helland",
    "Fault-tolerant and transactional stateful serverless workflows",
    "ExoFlow universal workflow system exactly-once",
    "Durable functions semantics for stateful serverless",
    "Boki stateful serverless computing with shared logs",
    "Notes on Data Base Operating Systems Gray",
    "ReAct synergizing reasoning and acting in language models",
    "AIOS LLM agent operating system",
    "Toolformer language models can teach themselves to use tools",
    "Unreliable failure detectors for reliable distributed systems",
    "Realizing the Fault-Tolerance Promise of Cloud Storage Using Locks with Intent",
    "All File Systems Are Not Created Equal crash consistent applications",
    "Torturing Databases for Fun and Profit",
    "Finding Crash-Consistency Bugs with Bounded Black-Box Crash Testing",
    "ACRFence Preventing Semantic Rollback Attacks Agent Checkpoint Restore",
)

#: Sources with no DBLP record. Each must be verified by fetching the URL and
#: recording the access date in the manuscript, as `B4_SEMANTICS.md` already
#: does for the Temporal documentation it quotes.
NON_DBLP_SOURCES: tuple[tuple[str, str], ...] = (
    ("Temporal retry policies", "https://docs.temporal.io/encyclopedia/retry-policies"),
    ("Temporal activity execution", "https://docs.temporal.io/activity-execution"),
    ("Redis WAITAOF command", "https://redis.io/docs/latest/commands/waitaof/"),
    ("Redis persistence (appendfsync)", "https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/"),
    ("Redis distributed locks / Redlock", "https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/"),
    ("Kleppmann, How to do distributed locking", "https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html"),
    ("Verified Tool Calls", "https://arxiv.org/abs/2608.02645"),
    ("LogAct", "https://arxiv.org/abs/2604.07988"),
    ("Sovereign Execution Broker", "https://arxiv.org/abs/2606.20520"),
    ("IETF Idempotency-Key draft 07", "https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header-07"),
    ("Transactional Outbox pattern", "https://microservices.io/patterns/data/transactional-outbox.html"),
)

API = "https://dblp.org/search/publ/api"


def query(term: str, *, hits: int = 4) -> None:
    url = f"{API}?format=json&h={hits}&q={urllib.parse.quote(term)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.load(response)
    except Exception as error:  # noqa: BLE001 - the failure must be visible
        print(f"!! LOOKUP FAILED  {term}\n   {error}\n")
        return

    found = payload.get("result", {}).get("hits", {}).get("hit", [])
    print(f"### {term}   ({len(found)} hit(s))")
    for hit in found:
        info = hit["info"]
        authors = info.get("authors", {}).get("author", [])
        if isinstance(authors, dict):
            authors = [authors]
        names = ", ".join(
            a["text"] if isinstance(a, dict) else str(a) for a in authors
        )
        print(f"  title:   {info.get('title')}")
        print(f"  authors: {names}")
        print(
            f"  venue:   {info.get('venue')} "
            f"vol={info.get('volume', '-')} no={info.get('number', '-')} "
            f"year={info.get('year')} pp={info.get('pages', '-')} "
            f"type={info.get('type')}"
        )
        print(f"  doi:     {info.get('doi', '-')}")
        print(f"  ee:      {info.get('ee', '-')}")
        print()
    print()


def main(argv: list[str]) -> int:
    terms = argv[1:] or list(QUERIES)
    for index, term in enumerate(terms):
        query(term)
        if index + 1 < len(terms):
            time.sleep(8)  # DBLP returns 429 without this
    if not argv[1:]:
        print("=" * 70)
        print("Sources with no DBLP record -- verify by fetching the URL:")
        for name, url in NON_DBLP_SOURCES:
            print(f"  {name:<44} {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
