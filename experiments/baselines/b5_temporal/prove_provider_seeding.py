"""Rule 13 for the per-run provider seed, on the fault stream, both directions.

**What was wrong.** ``RunProvider.start`` rewrote ``ledger_path`` and nothing
else, so all 120 runs of the 2026-09-08 session ran a provider seeded
``20260908``. ``MockLegacyAPI`` draws its three fault decisions from one
``random.Random(config.seed)`` per process, so every run replayed one fault
stream and three of the four cells produced a single distinct outcome across
thirty runs.

**Why this proves it on the fault stream and not on the outcome.** A seed that
varies in the driver but never reaches the provider produces exactly the
symptom it is supposed to cure -- identical faults -- and an outcome-level check
would be satisfied by any incidental variation from elsewhere (a retry that
happened to land differently, one extra provider call). The signature read here
is the provider's own record of *its* decisions, in
``ground_truth.run.jsonl``, which is the only place the fault stream is visible
independently of what the engine did with it.

**Branch A -- different seeds must give different fault streams.** N providers,
N seeds, N distinct signatures. This is the branch the defect fails.

**Branch B -- the same seed must give the same fault stream, exactly.** A
generator that merely varies is not enough: the run must be reproducible from
its own recorded seed, or the seed in the record does not determine the run and
nothing can be replayed from it. This is the branch that would catch a
"fix" that seeded from the clock.

Neither branch starts Temporal or a worker. The provider is driven directly with
plain HTTP, because the question is about the provider's generator and nothing
else. Exit 0 means both branches were observed.

**The first version of this proof failed branch B, and the defect was in the
proof.** Its signature digested the *client-observed* HTTP statuses alongside
the provider's records. Those depend on whether this script's socket timeout
fires before the provider's simulated timeout returns 504, which is a race
against wall-clock and not a function of any seed: two runs at seed 20260908
differed at exactly one request, where one saw ``504`` and the other saw the
client-side sentinel ``0``. The provider's own decisions were **byte-identical**
across those two runs.

That is recorded rather than quietly corrected because it is the third time this
session that checking code was held to a lower standard than the code it checks,
and because a proof that fails for its own reasons is indistinguishable, to a
reader, from the repair not working. The signature is now what this docstring
always claimed it was: **the provider's own record, and nothing observed from
outside it.**
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mock_api.supervisor import render_config  # noqa: E402

OUT = Path("/var/tmp/b5-seed-proof")
TEMPLATE = Path("/var/tmp/b5-probe/mock-api.yaml")
PORT = 8099
REQUESTS_PER_PROVIDER = 24

#: Long enough that the client never gives up before the provider has decided.
#: The signature no longer contains anything the client observed, but a client
#: that abandoned a request early could still leave the provider mid-write.
CLIENT_TIMEOUT_S = 90


def _post(url: str, reference: str) -> tuple[int, str]:
    body = json.dumps({
        "connector_operation": "post_ledger_entry",
        "target": f"t-{reference}",
        "operation_version": "1",
        "public_fields": [
            {"name": "target", "value": f"t-{reference}"},
            {"name": "action", "value": "post"},
            {"name": "amount_minor", "value": 100},
        ],
    }).encode()
    request = urllib.request.Request(
        f"{url}/v1/endpoints/ledger_postings/mutations", data=body,
        headers={"Content-Type": "application/json",
                 "X-Aep-Client-Reference": reference},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=CLIENT_TIMEOUT_S) as response:
            return response.status, ""
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception as exc:                                   # noqa: BLE001
        return 0, type(exc).__name__


def fault_signature(run_dir: Path, seed: int, label: str) -> str | None:
    """Start one provider at ``seed``, drive it, and digest its fault stream.

    The delay fault is overridden to zero: the stream under test is which
    requests are failed, not how long each took, and a 2 s constant delay would
    make the proof take twenty minutes to say the same thing.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    config_path = run_dir / "mock-api.yaml"
    ledger = run_dir / "ground_truth.sqlite3"
    render_config(
        TEMPLATE, config_path, ledger_path=ledger, seed=seed,
        fault_overrides={"delay": {"distribution": "constant", "seconds": 0.0}},
    )

    process = subprocess.Popen(
        [sys.executable, "-m", "experiments.mock_api",
         "--config", str(config_path), "--host", "127.0.0.1", "--port", str(PORT)],
        stdout=subprocess.DEVNULL,
        stderr=open(run_dir / "provider.err", "ab"),
    )
    url = f"http://127.0.0.1:{PORT}"
    try:
        deadline = time.monotonic() + 60
        ready = False
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"{url}/v1/health", timeout=3) as r:
                    if r.status == 200:
                        ready = True
                        break
            except Exception:                                  # noqa: BLE001
                time.sleep(0.3)
        if not ready:
            print(f"  {label}: provider never became healthy", flush=True)
            return None

        # Driven only to make the provider decide. Nothing observed here enters
        # the signature -- see the module docstring on why the first version's
        # branch B failed for its own reasons.
        for index in range(REQUESTS_PER_PROVIDER):
            _post(url, f"{label}-e{index}")
    finally:
        process.kill()
        try:
            process.wait(timeout=10)
        except Exception:                                      # noqa: BLE001
            pass

    # The provider's OWN record, and nothing observed from outside it.
    #
    # A request the provider faulted leaves no applied-mutation record, so the
    # ordered set of client references that DID apply is the fault stream's
    # visible shadow -- and it is written by the provider, after its own
    # decision, with no dependence on what any client saw or how long it waited.
    # ``at_ms`` and ``config_digest`` are deliberately excluded: the first is a
    # clock, and the second is constant across seeds by construction.
    log = run_dir / "ground_truth.run.jsonl"
    decisions = []
    if log.exists():
        for line in log.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            if "client_reference" in entry:
                decisions.append((entry.get("client_reference"),
                                  entry.get("delivery_index"),
                                  entry.get("endpoint")))
            elif entry.get("event") and "status" in entry:
                decisions.append(("__final__", entry.get("status"),
                                  entry.get("reason")))
    payload = repr(decisions)
    (run_dir / "signature-input.txt").write_text(payload, encoding="utf-8")
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def main() -> int:
    if not TEMPLATE.exists():
        print(f"no template at {TEMPLATE}", flush=True)
        return 4
    OUT.mkdir(parents=True, exist_ok=True)

    print("=== branch A: different seeds must give different fault streams ===",
          flush=True)
    seeds = [20260908, 20260909, 20260910, 20260911, 20260912]
    a_signatures = {}
    for seed in seeds:
        sig = fault_signature(OUT / f"a-{seed}", seed, f"a{seed}")
        a_signatures[seed] = sig
        print(f"  seed {seed} -> {sig}", flush=True)
    values = [s for s in a_signatures.values() if s]
    a_ok = len(values) == len(seeds) and len(set(values)) == len(seeds)
    print(f"  {len(set(values))} distinct signature(s) from {len(seeds)} seeds",
          flush=True)
    print(f"  BRANCH A: {a_ok}", flush=True)

    print("\n=== branch B: the same seed must reproduce its stream exactly ===",
          flush=True)
    repeat = fault_signature(OUT / "b-repeat", seeds[0], f"a{seeds[0]}")
    original = a_signatures[seeds[0]]
    b_ok = repeat is not None and repeat == original
    print(f"  seed {seeds[0]} first  -> {original}", flush=True)
    print(f"  seed {seeds[0]} repeat -> {repeat}", flush=True)
    print(f"  BRANCH B: {b_ok}", flush=True)

    print("\n=== rule 13 ===", flush=True)
    print(f"  A: seeds that differ produce streams that differ : {a_ok}",
          flush=True)
    print(f"  B: a seed reproduces its own stream exactly      : {b_ok}",
          flush=True)
    (OUT / "summary.json").write_text(
        json.dumps({"branch_a": {str(k): v for k, v in a_signatures.items()},
                    "branch_a_ok": a_ok, "repeat": repeat,
                    "original": original, "branch_b_ok": b_ok},
                   indent=2, sort_keys=True),
        encoding="utf-8",
    )
    satisfied = a_ok and b_ok
    print(f"  BOTH BRANCHES OBSERVED: {satisfied}", flush=True)
    return 0 if satisfied else 1


if __name__ == "__main__":
    raise SystemExit(main())
