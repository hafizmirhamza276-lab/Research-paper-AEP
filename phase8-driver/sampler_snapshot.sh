#!/usr/bin/env bash
# Read-only snapshot of the foreign-load sampler's JSONL, taken either side of
# stopping the sampler so "the file is intact" is a comparison rather than an
# assertion.
set -u
J=/root/phase8-driver/foreign-load-samples.jsonl
echo "lines      : $(wc -l < "$J")"
echo "bytes      : $(stat -c %s "$J")"
echo "sha256     : $(sha256sum "$J" | cut -d' ' -f1)"
echo "first record t: $(head -1 "$J" | python3 -c 'import json,sys; print(json.load(sys.stdin)["t"])')"
echo "last record  t: $(tail -1 "$J" | python3 -c 'import json,sys; print(json.load(sys.stdin)["t"])')"
echo "--- tail -3 ---"
tail -3 "$J"
echo "--- largest gap between consecutive samples ---"
python3 - "$J" <<'PY'
import json, sys
from datetime import datetime
ts = []
for line in open(sys.argv[1]):
    line = line.strip()
    if not line:
        continue
    try:
        ts.append(datetime.fromisoformat(json.loads(line)["t"]))
    except Exception:
        pass
ts.sort()
gaps = [(b - a, a, b) for a, b in zip(ts, ts[1:])]
gaps.sort(reverse=True)
for g, a, b in gaps[:3]:
    print(f"  {g.total_seconds():>10.0f} s   {a.isoformat()} -> {b.isoformat()}")
print(f"  samples: {len(ts)}  span: {ts[0].isoformat()} -> {ts[-1].isoformat()}")
PY
