"""``python -m experiments.harness`` -- run one fault-injection experiment."""

from __future__ import annotations

import sys

from experiments.harness.runner import main

if __name__ == "__main__":  # pragma: no cover - process entry point
    sys.exit(main())
