# Reproduction entry points for the AEP artifact.
#
# Two targets, and the difference between them is the difference between the
# two things a reader might want to check:
#
#   reproduce-smoke    -- does the harness still run? Provisions Redis, collects
#                         one tier-1 cell for each of the seven systems against
#                         real SIGKILL faults, analyses them, and prints the
#                         outcome rates. ~5 minutes. It produces NEW data; it
#                         says nothing about the paper's numbers.
#
#   reproduce-figures  -- do the paper's generated artifacts still follow from
#                         the frozen results? Regenerates every table, macro and
#                         the state-machine figure and byte-compares them with
#                         what is committed. ~1 minute, no Redis, no Docker.
#
# Neither target writes anywhere inside experiments/results/. The frozen tree is
# evidence: a reproduction script that overwrites it cannot be re-run to check
# its own claim, and the first thing it would destroy is the thing in dispute.
# Both write under .scratch/, which is disposable and already gitignored
# (.gitignore:108), so a reproduction run leaves the working tree clean.

SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c

UV         ?= uv
COMPOSE    ?= compose.phase2.yml
REDIS_URL  ?= redis://127.0.0.1:6381/15
SCRATCH    ?= .scratch/reproduce
SMOKE_ROOT ?= $(SCRATCH)/smoke
FIG_ROOT   ?= $(SCRATCH)/figures

# The frozen results tree the paper's numbers come from. The analysis products
# are tracked (see the tail of .gitignore), so the default works from a clean
# clone. Point this at an unpacked full archive to also regenerate the two
# analysis figures, which need the raw run directories.
ARCHIVE    ?= experiments/results/matrix

.PHONY: help reproduce-smoke reproduce-figures

help:
	@echo "make reproduce-smoke     collect one tier-1 cell per system and analyse it (~5 min, needs Docker)"
	@echo "make reproduce-figures   regenerate the paper's tables from the frozen results and diff them (~1 min)"
	@echo ""
	@echo "Variables: UV=$(UV) REDIS_URL=$(REDIS_URL) ARCHIVE=$(ARCHIVE) SCRATCH=$(SCRATCH)"

# ---------------------------------------------------------------------------
# reproduce-smoke
# ---------------------------------------------------------------------------
# One cell per system, one run each, two executions per run, all at the same
# crash point and endpoint so the seven rows are comparable. Tier 1 is the
# non-payments endpoints (experiments/run_matrix.py:394), which is where the
# declared-ambiguity claim lives.
#
# This is a liveness check on the harness, not a replication of the study: two
# executions per cell cannot estimate a rate. The paper's cells are 150-180
# executions each.
reproduce-smoke:
	@echo "=== reproduce-smoke: environment ==="
	$(UV) sync --frozen --extra dev --extra experiments --extra analysis
	$(UV) run --frozen python -VV
	@echo
	@echo "=== provisioning Redis 7.2 from $(COMPOSE) ==="
	docker compose -f $(COMPOSE) up -d --wait
	trap 'echo; echo "=== tearing down ==="; docker compose -f $(COMPOSE) down -v' EXIT
	@echo
	@echo "=== asserting the live server really provides phase2.conf semantics ==="
	$(UV) run --frozen python scripts/verify_redis_semantics.py --url "$(REDIS_URL)"
	@echo
	@echo "=== marking the instance disposable ==="
	# The harness kills processes holding leases on the instance and deletes
	# the keys it created, so it refuses to run anywhere that has not asserted
	# it is throwaway (README, "Test-instance safety"). The marker is written
	# through `docker compose exec` rather than to $$REDIS_URL deliberately: it
	# marks the container this target created two steps ago and destroys with
	# `down -v` on exit, and cannot mark whatever else REDIS_URL might name.
	docker compose -f $(COMPOSE) exec -T redis-phase2 \
	    redis-cli -n 15 SET aep:test-instance-marker 1
	@echo
	@echo "=== collecting: 7 systems x 1 cell, real SIGKILL ==="
	rm -rf "$(SMOKE_ROOT)"
	mkdir -p "$(SMOKE_ROOT)"
	$(UV) run --frozen python -m experiments.run_matrix \
	    --redis-url "$(REDIS_URL)" \
	    --results-root "$(SMOKE_ROOT)" \
	    --max-tier 1 \
	    --runs-per-cell 1 \
	    --executions-per-run 2 \
	    --endpoint notifications \
	    --crash-point mid_dispatch \
	    --keying CALLER_REFERENCE
	@echo
	@echo "=== analysing ==="
	$(UV) run --frozen python -m experiments.analyze \
	    --results-root "$(SMOKE_ROOT)" \
	    --destination "$(SMOKE_ROOT)/analysis"
	@echo
	@echo "=== outcome rates, one row per system ==="
	$(UV) run --frozen python -c "$$SMOKE_ROWS" "$(SMOKE_ROOT)/analysis/per-cell-metrics.csv"
	@echo
	@echo "reproduce-smoke: OK. New data is under $(SMOKE_ROOT); the frozen tree was not touched."

# Printed rather than diffed on purpose. Two executions per cell is far too few
# to match the paper's rates, so a comparison here would either fail honestly
# every time or be given a tolerance so wide it checked nothing. What this
# shows is that each system still lands in its own corner of the trilemma.
define SMOKE_ROWS
import csv, sys
from collections import defaultdict
METRICS = ("undetected_duplicate_rate", "lost_effect_rate", "known_ambiguity_rate")
rows = list(csv.DictReader(open(sys.argv[1], newline="", encoding="utf-8")))
agg = defaultdict(lambda: defaultdict(lambda: [0, 0]))
for r in rows:
    if r["metric"] not in METRICS:
        continue
    cell = agg[r["system"]][r["metric"]]
    cell[0] += int(r["successes"])
    cell[1] += int(r["total"])
print(f"{'system':38s} {'undet.dup':>11s} {'lost effect':>13s} {'declared amb':>14s}")
print("-" * 79)
for system in sorted(agg):
    out = []
    for metric in METRICS:
        s, t = agg[system][metric]
        out.append(f"{s}/{t}" if t else "-")
    print(f"{system:38s} {out[0]:>11s} {out[1]:>13s} {out[2]:>14s}")
endef
export SMOKE_ROWS

# matplotlib stamps the wall-clock time into every PDF it writes, so a figure
# regenerated from identical data is never byte-identical to the committed one.
# That is a documented tolerance and it is the only one in this file, so it is
# checked rather than asserted: the CreationDate is normalised and the rest of
# the file must then match exactly. A single plotted value that moved shows up
# as bytes outside the timestamp, and fails.
define PDF_COMPARE
import re, sys
from pathlib import Path
STAMP = re.compile(rb"/CreationDate \(D:[^)]*\)")
committed, fresh = Path(sys.argv[1]).read_bytes(), Path(sys.argv[2]).read_bytes()
name = Path(sys.argv[1]).name
raw = sum(1 for a, b in zip(committed, fresh) if a != b) + abs(len(committed) - len(fresh))
if STAMP.sub(b"/CreationDate (D:NORMALISED)", committed) == STAMP.sub(
    b"/CreationDate (D:NORMALISED)", fresh
):
    print(f"  IDENTICAL {name} (apart from {raw} bytes of PDF CreationDate)")
    sys.exit(0)
print(f"  DIFFERS   {name}: {raw} bytes differ, and not only in the timestamp.")
print("            A plotted value moved. This is a finding, not a build error.")
sys.exit(1)
endef
export PDF_COMPARE

# ---------------------------------------------------------------------------
# reproduce-figures
# ---------------------------------------------------------------------------
# Regenerates from the frozen CSVs into a scratch directory and byte-compares
# with what is committed. This is the same comparison
# scripts/check_paper_numbers.py makes; the target exists so a reader can make
# it without reading the gate, and so the verdict is printed as a verdict.
#
# The two analysis figures are regenerated only when ARCHIVE holds the raw run
# directories, because analyze.py reads runs and the tracked archive is the
# analysis products alone. When they are skipped, the target says so rather
# than reporting success over work it did not do.
reproduce-figures:
	@echo "=== reproduce-figures: regenerating from $(ARCHIVE)/analysis ==="
	# The analysis extras are synced up front even though the tables need only
	# the base set: the figure branch below needs matplotlib, and syncing twice
	# in one target uninstalls 31 packages between the two steps.
	$(UV) sync --frozen --extra experiments --extra analysis
	rm -rf "$(FIG_ROOT)"
	mkdir -p "$(FIG_ROOT)/generated"
	$(UV) run --frozen python scripts/paper_tables.py \
	    --analysis "$(ARCHIVE)/analysis" \
	    --fsync-analysis experiments/results/fsync-always/analysis \
	    --flakey experiments/results \
	    --out "$(FIG_ROOT)/generated"
	@echo
	@echo "=== byte-comparing against paper/generated/ ==="
	failed=0
	for fresh in "$(FIG_ROOT)"/generated/*.tex; do
	  name=$$(basename "$$fresh")
	  committed="paper/generated/$$name"
	  if [[ ! -f "$$committed" ]]; then
	    echo "  MISSING   $$name (regenerated but not committed)"
	    failed=$$((failed + 1))
	  elif diff -q <(tr -d '\r' < "$$committed") <(tr -d '\r' < "$$fresh") > /dev/null; then
	    echo "  IDENTICAL $$name"
	  else
	    echo "  DIFFERS   $$name"
	    diff -u <(tr -d '\r' < "$$committed") <(tr -d '\r' < "$$fresh") | head -40 || true
	    failed=$$((failed + 1))
	  fi
	done
	@echo
	@echo "=== the state-machine figure against the implementation ==="
	$(UV) run --frozen python scripts/gen_state_machine.py --check paper/figures/state-machine.tex
	@echo
	@echo "=== the two analysis figures ==="
	if compgen -G "$(ARCHIVE)/*-r0" > /dev/null 2>&1 || compgen -G "$(ARCHIVE)/*-r1" > /dev/null 2>&1; then
	  $(UV) run --frozen python -m experiments.analyze \
	      --results-root "$(ARCHIVE)" \
	      --destination "$(FIG_ROOT)/analysis" > "$(FIG_ROOT)/analyze.log" 2>&1
	  for name in figure-1-undetected-vs-ambiguity.pdf figure-2-duplicates-by-crash-point.pdf; do
	    $(UV) run --frozen python -c "$$PDF_COMPARE" \
	        "paper/figures/$$name" "$(FIG_ROOT)/analysis/$$name" || failed=$$((failed + 1))
	  done
	else
	  echo "  SKIPPED: $(ARCHIVE) holds no run directories, so analyze.py cannot run."
	  echo "           The tracked archive is the analysis products only. Unpack the full"
	  echo "           results archive and re-run with ARCHIVE=<path> to include these."
	fi
	@echo
	if [[ $$failed -ne 0 ]]; then
	  echo "reproduce-figures: $$failed generated file(s) DIFFER from what is committed."
	  echo "That is a finding about the repository, not a build error to paper over."
	  exit 1
	fi
	echo "reproduce-figures: VERDICT -- every committed table and macro file is"
	echo "byte-identical to a fresh regeneration from the frozen CSVs, the"
	echo "state-machine figure matches the implementation, and any analysis figure"
	echo "compared above matched outside its PDF timestamp. Anything reported as"
	echo "SKIPPED was not checked."
