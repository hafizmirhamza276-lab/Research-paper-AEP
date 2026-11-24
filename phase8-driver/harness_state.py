#!/usr/bin/env python3
"""What harness commit did each session record, and what was its sort key?

The second half of the interleaving determination. interleave_check.py reads the
order runs actually executed in; this reads what the session says it was running.
Agreement between the two is the point -- an observed order that contradicted the
recorded harness would itself be a finding.

Reads run-config.json from the FIRST run directory of each root. Every run in a
session shares a harness version, so one is enough, and it is stated here rather
than assumed by reading all 120.

Read-only.

Usage: harness_state.py <run root> [<run root> ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    for arg in argv:
        root = Path(arg)
        configs = sorted(root.glob("*/run-config.json"))
        if not configs:
            print(f"{root.name}: no run-config.json found")
            continue

        cfg = json.loads(configs[0].read_text(encoding="utf-8"))
        hv = (cfg.get("environment") or {}).get("harness_version") or {}
        env = cfg.get("environment") or {}

        print(f"{root.name}")
        print(f"  run-config files present   : {len(configs)}")
        print(f"  harness commit             : {hv.get('commit', '?')}")
        print(f"  harness dirty              : {hv.get('dirty', '?')}")
        print(f"  matrix version             : {cfg.get('config_version', '?')}")
        print(f"  redis storage backing      : {(env.get('redis_storage_backing') or {}).get('mount_type', '?')}")
        print(f"  filesystem                 : {env.get('results_root_filesystem', '?')}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
