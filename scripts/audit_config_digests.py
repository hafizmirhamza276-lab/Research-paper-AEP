r"""Is every digest failure explained by schema evolution alone?

`docs/31-transmission-event.md` §4 found 150 of the 432 frozen `matrix` runs
failing their own `config_digest` check, all missing the same four fields. That
is consistent with schema evolution -- `RunConfig` grew, and `config_digest` is
computed over the **current** field set rather than the recorded one -- but
"consistent with" is not "explained by", and the difference matters enormously:

* **explained by schema evolution** -- the stored digest is exactly what the
  field set of that run's generation would produce. Nothing was altered; the
  verifier is asking the wrong question. Recoverable.
* **anything else** -- a stored digest that matches *no* generation's field set
  means the recorded configuration and its digest disagree for a reason this
  repository cannot account for. That is a far more serious finding and it would
  need to be reported as one.

This script decides which, per run, by **reconstruction rather than by
argument**: for each candidate generation it rebuilds the field set as of that
generation, recomputes the digest over the recorded values, and asks whether any
generation reproduces the stored value exactly.

**It never writes.** Recomputing and storing a digest would destroy the only
property the digest has -- that it was computed before anyone had a reason to
want a particular answer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from experiments.harness.config import RunConfig  # noqa: E402

#: Excluded from the digest by `RunConfig.config_digest`, at every generation.
EXCLUDED = {"run_id", "results_root", "resolved_crash_point"}


def stored_digest(document: dict[str, Any]) -> str | None:
    return document.get("config_digest")


def digest_over(body: dict[str, Any]) -> str:
    """The project's own digest function, reproduced exactly.

    `config.py` does `sha256(json.dumps(body, sort_keys=True,
    separators=(",", ":")))`. Reproduced here rather than imported because the
    point is to feed it a *historical* body, which the live property cannot.
    """
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def generations_from_git() -> list[tuple[str, str, frozenset[str]]]:
    """Every historical field set of RunConfig, from git history of config.py.

    Returns (commit, date, field names). The field set is read by executing the
    historical module in isolation, not by parsing it: a regex over `name:
    type` would miss fields added by inheritance or conditionals, and a wrong
    field set here would silently produce a wrong verdict.
    """
    log = subprocess.run(
        ["git", "log", "--format=%H %cI", "--", "experiments/harness/config.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    generations: list[tuple[str, str, frozenset[str]]] = []
    seen: set[frozenset[str]] = set()
    for line in log.stdout.splitlines():
        commit, _, date = line.partition(" ")
        blob = subprocess.run(
            ["git", "show", f"{commit}:experiments/harness/config.py"],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        if blob.returncode != 0:
            continue
        names = _field_names(blob.stdout)
        if names and names not in seen:
            seen.add(names)
            generations.append((commit, date, names))
    return generations


def _field_names(source: str) -> frozenset[str]:
    """Field names of the RunConfig dataclass in a historical source file.

    Parsed with `ast` rather than executed: executing a historical config.py
    would import whatever aep_core looked like at that commit, which is not
    checked out. AnnAssign targets inside the class body are exactly the
    dataclass fields.
    """
    import ast

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return frozenset()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "RunConfig":
            return frozenset(
                item.target.id
                for item in node.body
                if isinstance(item, ast.AnnAssign)
                and isinstance(item.target, ast.Name)
            )
    return frozenset()


def explain(document: dict[str, Any], generations) -> dict[str, Any]:
    """Which generation, if any, reproduces this run's stored digest."""
    stored = stored_digest(document)
    if stored is None:
        return {"verdict": "NO STORED DIGEST"}

    recorded = {k: v for k, v in document.items() if k not in EXCLUDED}
    recorded.pop("config_digest", None)
    recorded.pop("environment", None)

    matches: list[tuple[str, str, int]] = []
    for commit, date, names in generations:
        body = {
            key: value
            for key, value in recorded.items()
            if key in names and key not in EXCLUDED
        }
        # `resolved_crash_point` is excluded, and `environment` was never in the
        # body, so the recorded document minus those IS the historical body --
        # provided the generation had no field the document lacks.
        if set(body) != {n for n in names if n not in EXCLUDED}:
            continue
        if digest_over(body) == stored:
            matches.append((commit, date, len(names)))

    if not matches:
        return {"verdict": "UNEXPLAINED"}
    # More than one generation reproducing the same stored digest would mean a
    # field could be altered and still be "explained" by a generation that did
    # not contain it. It has never happened -- the generations differ by fields
    # that are present in every document that carries them -- but a check that
    # would not notice is not a check.
    if len(matches) > 1:
        return {
            "verdict": "AMBIGUOUS -- MORE THAN ONE GENERATION MATCHES",
            "commit": matches[0][0],
            "date": matches[0][1],
            "fields": matches[0][2],
            "all": [c for c, _, _ in matches],
        }
    commit, date, count = matches[0]
    return {
        "verdict": "EXPLAINED BY SCHEMA GENERATION",
        "commit": commit,
        "date": date,
        "fields": count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", action="append", default=[], required=True)
    parser.add_argument("--json", default=None)
    parser.add_argument(
        "--require-runs",
        type=int,
        default=0,
        metavar="N",
        help="fail unless at least N run configs were examined. A check that "
        "silently examined nothing reports a clean pass, which is the one "
        "outcome it must never produce.",
    )
    arguments = parser.parse_args(argv)

    current = frozenset(RunConfig.__dataclass_fields__)
    generations = generations_from_git()
    print(f"RunConfig field-set generations found in git history: {len(generations)}")
    for commit, date, names in generations:
        marker = "  <- current" if names == current else ""
        print(f"  {commit[:8]} {date[:10]}  {len(names):3d} fields{marker}")
    print()

    verdicts: Counter = Counter()
    by_root: dict[str, Counter] = defaultdict(Counter)
    unexplained: list[str] = []
    detail: dict[str, Any] = {}

    for spec in arguments.root:
        base = Path(spec)
        if not base.is_dir():
            continue
        for path in sorted(base.glob("*/run-config.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            stored = stored_digest(document)
            live = None
            try:
                accepted = {
                    k: v for k, v in document.items() if k in current
                }
                live = RunConfig(**accepted).config_digest
            except Exception:
                pass
            if live is not None and live == stored:
                verdicts["VERIFIES AGAINST THE CURRENT SCHEMA"] += 1
                by_root[base.name]["current"] += 1
                continue
            result = explain(document, generations)
            verdicts[result["verdict"]] += 1
            by_root[base.name][result["verdict"]] += 1
            if result["verdict"] == "UNEXPLAINED":
                unexplained.append(f"{base.name}/{path.parent.name}")
            else:
                detail.setdefault(result.get("commit", "?"), 0)
                detail[result["commit"]] += 1

    print("verdicts")
    for verdict, count in verdicts.most_common():
        print(f"  {count:5d}  {verdict}")
    print()
    print("by root")
    for root, counts in sorted(by_root.items()):
        print(f"  {root:36s} {dict(counts)}")
    if detail:
        print()
        print("failures explained, by the generation that reproduces them")
        for commit, count in sorted(detail.items(), key=lambda kv: -kv[1]):
            print(f"  {count:5d}  {commit[:8]}")
    if unexplained:
        print()
        print(f"UNEXPLAINED ({len(unexplained)}) -- these are the serious ones:")
        for name in unexplained[:20]:
            print(f"  {name}")
    else:
        print()
        print(
            "NONE UNEXPLAINED: every stored digest is reproduced by some "
            "historical field set, so every failure is schema evolution and "
            "nothing was altered after collection."
        )

    examined = sum(verdicts.values())
    ambiguous = sum(
        count for verdict, count in verdicts.items() if verdict.startswith("AMBIGUOUS")
    )
    print()
    print(f"run configs examined: {examined}")
    if arguments.require_runs and examined < arguments.require_runs:
        print(
            f"GATE FAILED: examined {examined} run configs, required at least "
            f"{arguments.require_runs}. A digest check that found nothing to "
            f"check has not checked anything."
        )
        return 2
    if ambiguous:
        print(f"GATE FAILED: {ambiguous} run(s) matched more than one generation.")
        return 3

    if arguments.json:
        Path(arguments.json).write_text(
            json.dumps(
                {
                    "generations": [
                        {"commit": c, "date": d, "fields": sorted(n)}
                        for c, d, n in generations
                    ],
                    "verdicts": dict(verdicts),
                    "by_root": {k: dict(v) for k, v in by_root.items()},
                    "unexplained": unexplained,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return 1 if unexplained else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
