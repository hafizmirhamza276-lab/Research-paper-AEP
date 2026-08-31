#!/usr/bin/env bash
# Read the two changed kill-latency sites out of the built PDF, as rendered.
set -u
cd /tmp/b9paper/paper || exit 1
pdftotext main.pdf - 2>/dev/null | tr '\n' ' ' | tr -s ' ' > /tmp/b9paper/flat.txt

echo "=== undefined-control-sequence lines in the log ==="
grep -n "Undefined control sequence" main.log || echo "  none"

echo
echo "=== eval site ==="
grep -o "The variation has a candidate cause.\{0,1900\}" /tmp/b9paper/flat.txt

echo
echo "=== threats site ==="
grep -o "function of the host.s kill-latency distribution.\{0,500\}" /tmp/b9paper/flat.txt

echo
echo "=== any surviving withdrawn p-value string ==="
grep -o "4.0[^ ]*10.9" /tmp/b9paper/flat.txt || echo "  none"
