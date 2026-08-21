"""Verify that every bibliography entry the manuscript cites actually exists.

`PAPER_ROADMAP.md` §5's Phase 4 prompt says "verify each BibTeX entry exists;
do not fabricate". Prose cannot discharge that; a lookup can -- but only if the
lookup can *fail*.

**What changed, and why.** The previous version of this script could not fail.
``main()`` ended in an unconditional ``return 0``, a failed lookup only printed
a line, and nothing tied its query list to `paper/refs.bib`. Phase 6's audit
measured the consequence: **14 of 23 lookups failed with HTTP 503/500 and the
script still exited 0**, while `09-artifact.tex` pointed readers at that sweep
as the assurance that every entry was verified. Three further drifts had
accumulated between the hand-written source list and `refs.bib` -- two URLs
swept at addresses no entry used, and one entry never swept at all.

**The design that prevents both.** `paper/refs.bib` is the single source of
truth. Nothing is hand-maintained here:

* every entry is assigned exactly one verification route, derived from its own
  fields -- a URL to fetch, a DOI to resolve, or a title to search on DBLP;
* an entry with **no** route is a failure, not a silent omission, so a citation
  can never be added without also becoming checkable;
* every route reports RESOLVED / ZERO_HITS / FAILED, and **any** non-resolved
  result makes the process exit non-zero.

Deriving the DBLP queries also fixes the rate limiting that caused the observed
false pass: only entries with neither a DOI nor a URL need a title search, which
is 7 of 34 rather than 23, so the sweep no longer hammers the API.

Usage::

    python scripts/verify_refs.py              # full sweep; non-zero on any failure
    python scripts/verify_refs.py --offline    # route coverage only, no network
    python scripts/verify_refs.py --allow-transient 2
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BIB = ROOT / "paper" / "refs.bib"
DBLP_API = "https://dblp.org/search/publ/api"
DOI_RESOLVER = "https://doi.org/"
USER_AGENT = "aep-verify-refs/2 (+bibliography verification)"

RESOLVED, ZERO_HITS, FAILED = "RESOLVED", "ZERO_HITS", "FAILED"

_BACKSLASH = chr(92)
_URL_FIELD = re.compile(
    r"howpublished\s*=\s*\{" + re.escape(_BACKSLASH) + r"url\{([^}]+)\}\}"
    r"|(?<![a-z])url\s*=\s*\{([^}]+)\}",
    re.IGNORECASE,
)
_DOI_FIELD = re.compile(r"(?<![a-z])doi\s*=\s*\{([^}]+)\}", re.IGNORECASE)
_TITLE_FIELD = re.compile(r"(?<![a-z])title\s*=\s*\{(.*?)\}\s*,\s*\n", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class Entry:
    key: str
    kind: str
    title: str
    url: str | None
    doi: str | None

    @property
    def route(self) -> str:
        if self.url:
            return "url"
        if self.doi:
            return "doi"
        if self.title:
            return "dblp"
        return "none"


def _strip_comments(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("%"))


def parse_bib(path: Path = DEFAULT_BIB) -> list[Entry]:
    """Every entry in `refs.bib`, with the fields that decide its route.

    Deliberately a small brace-matching reader rather than a BibTeX parser: the
    only thing that must be exactly right is which entry owns which field, and
    a dependency-free reader keeps this script runnable anywhere.
    """
    body = _strip_comments(path.read_text(encoding="utf-8"))
    entries: list[Entry] = []
    for match in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", body):
        open_brace = body.index("{", match.start())
        index, depth = open_brace + 1, 1
        while index < len(body) and depth:
            if body[index] == "{":
                depth += 1
            elif body[index] == "}":
                depth -= 1
            index += 1
        block = body[open_brace:index]

        url_match = _URL_FIELD.search(block)
        url = (url_match.group(1) or url_match.group(2)) if url_match else None
        doi_match = _DOI_FIELD.search(block)
        title_match = _TITLE_FIELD.search(block)
        title = " ".join(title_match.group(1).split()) if title_match else ""
        title = title.replace("{", "").replace("}", "")

        entries.append(
            Entry(
                key=match.group(2),
                kind=match.group(1).lower(),
                title=title,
                url=url.strip() if url else None,
                doi=doi_match.group(1).strip() if doi_match else None,
            )
        )
    return entries


def routes(entries: Iterable[Entry]) -> dict[str, list[Entry]]:
    grouped: dict[str, list[Entry]] = {"url": [], "doi": [], "dblp": [], "none": []}
    for entry in entries:
        grouped[entry.route].append(entry)
    return grouped


def _fetch(url: str, *, timeout: int = 30, accept: str | None = None) -> tuple[str, str]:
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return RESOLVED, "HTTP %s" % response.status
    except urllib.error.HTTPError as error:
        return FAILED, "HTTP %s" % error.code
    except Exception as error:  # noqa: BLE001 - the failure must be visible AND counted
        return FAILED, str(error)


def _fetch_with_retry(
    url: str, *, attempts: int = 3, pause: float = 5.0, accept: str | None = None
) -> tuple[str, str]:
    """Retry transient server-side failures before counting one.

    A 429 or 5xx is the API saying "not now", which is different from a dead
    link, and conflating the two is what let the previous version report a
    healthy bibliography as broken and a broken sweep as healthy.
    """
    status, detail = FAILED, "not attempted"
    for attempt in range(attempts):
        status, detail = _fetch(url, accept=accept)
        if status == RESOLVED:
            return status, detail
        transient = any(code in detail for code in ("429", "500", "502", "503", "504"))
        if not transient or attempt == attempts - 1:
            return status, detail
        time.sleep(pause * (attempt + 1))
    return status, detail


def check_url(entry: Entry) -> tuple[str, str]:
    return _fetch_with_retry(entry.url or "")


def check_doi(entry: Entry) -> tuple[str, str]:
    """Resolve a DOI at the registry, not at the publisher's landing page.

    Fetching ``https://doi.org/<doi>`` follows the redirect to the publisher,
    and several publishers -- ACM among them -- answer non-browser agents with
    **HTTP 403**. That is the publisher's bot policy, not a broken DOI, and
    counting it as a failure would make this gate cry wolf on nine valid
    entries. Asking for ``application/citeproc+json`` is answered by the DOI
    registration agency itself, which is the machine-readable route and the
    one that actually establishes the DOI exists.
    """
    doi = (entry.doi or "").strip()
    return _fetch_with_retry(
        DOI_RESOLVER + urllib.parse.quote(doi, safe="/:"),
        accept="application/citeproc+json, application/vnd.citationstyles.csl+json",
    )


def check_dblp(entry: Entry, *, hits: int = 4, verbose: bool = True) -> tuple[str, str]:
    url = "%s?format=json&h=%d&q=%s" % (DBLP_API, hits, urllib.parse.quote(entry.title))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    payload = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
            break
        except Exception as error:  # noqa: BLE001
            if attempt == 2:
                return FAILED, str(error)
            time.sleep(8 * (attempt + 1))
    found = (payload or {}).get("result", {}).get("hits", {}).get("hit", [])
    if verbose:
        print("### %s   (%d hit(s))" % (entry.title, len(found)))
        for hit in found:
            info = hit["info"]
            authors = info.get("authors", {}).get("author", [])
            if isinstance(authors, dict):
                authors = [authors]
            names = ", ".join(a["text"] if isinstance(a, dict) else str(a) for a in authors)
            print("  title:   %s" % info.get("title"))
            print("  authors: %s" % names)
            print(
                "  venue:   %s vol=%s no=%s year=%s pp=%s type=%s"
                % (
                    info.get("venue"), info.get("volume", "-"), info.get("number", "-"),
                    info.get("year"), info.get("pages", "-"), info.get("type"),
                )
            )
            print("  doi:     %s" % info.get("doi", "-"))
            print()
    return (RESOLVED, "%d hit(s)" % len(found)) if found else (ZERO_HITS, "0 hits")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify every refs.bib entry resolves.")
    parser.add_argument("--bib", type=Path, default=DEFAULT_BIB)
    parser.add_argument("--offline", action="store_true",
                        help="check route coverage only; make no network calls")
    parser.add_argument("--allow-transient", type=int, default=0, metavar="N",
                        help="tolerate up to N non-resolved lookups (default 0)")
    parser.add_argument("--quiet", action="store_true", help="suppress DBLP hit metadata")
    arguments = parser.parse_args(argv)

    entries = parse_bib(arguments.bib)
    grouped = routes(entries)

    print("=" * 70)
    print("verify_refs.py -- every entry in %s" % arguments.bib.name)
    print("=" * 70)
    print("entries: %d   url: %d   doi: %d   dblp: %d   UNROUTED: %d"
          % (len(entries), len(grouped["url"]), len(grouped["doi"]),
             len(grouped["dblp"]), len(grouped["none"])))
    print()

    failures: list[str] = []

    # An entry with no verification route is a defect in itself: it is a citation
    # that no sweep can ever check. This is offline and deterministic.
    for entry in grouped["none"]:
        failures.append("%s: no url, no doi and no title -- nothing can verify it" % entry.key)
        print("  UNROUTED  %s" % entry.key)

    if arguments.offline:
        print()
        print("-" * 70)
        print("offline: route coverage only, %d unrouted" % len(grouped["none"]))
        if failures:
            print("\nDO NOT TRUST THE BIBLIOGRAPHY:")
            for failure in failures:
                print("  - %s" % failure)
            return 1
        return 0

    checks = (
        [(e, check_url, "url ") for e in grouped["url"]]
        + [(e, check_doi, "doi ") for e in grouped["doi"]]
        + [(e, lambda e_: check_dblp(e_, verbose=not arguments.quiet), "dblp") for e in grouped["dblp"]]
    )
    resolved = 0
    for index, (entry, check, label) in enumerate(checks):
        status, detail = check(entry)
        if status == RESOLVED:
            resolved += 1
        else:
            failures.append("%s (%s): %s -- %s" % (entry.key, label.strip(), status, detail))
        print("  %-8s %-4s %-34s %s" % (status, label, entry.key, detail))
        if label == "dblp" and index + 1 < len(checks):
            time.sleep(8)  # DBLP rate-limits without this

    print()
    print("-" * 70)
    print("%d resolved, %d not resolved, of %d entries" % (resolved, len(failures), len(entries)))
    if len(failures) > arguments.allow_transient:
        print("\nDO NOT TRUST THE BIBLIOGRAPHY:")
        for failure in failures:
            print("  - %s" % failure)
        return 1
    if failures:
        print("(%d tolerated by --allow-transient %d)" % (len(failures), arguments.allow_transient))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
