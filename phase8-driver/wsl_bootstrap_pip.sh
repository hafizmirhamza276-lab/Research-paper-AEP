#!/usr/bin/env bash
# Bootstrap pip into WSL WITHOUT sudo.
#
# sudo is authorised for this narrowly, but the password is already sitting in
# plaintext in two session transcripts and rotation is still pending, so every
# additional use adds to a documented exposure. get-pip.py installs into the
# user site-packages and needs no privilege at all. If it works, the sudo
# authorisation goes unused, which is the better outcome.
#
# Installs ONLY pip here. Declared dependencies are added one at a time
# afterwards, each in response to a specific ImportError.
set -u

echo "=== preconditions ==="
echo "python3: $(python3 --version 2>&1)"
for c in curl wget; do
    printf '  %-6s %s\n' "$c" "$(command -v $c || echo 'not present')"
done

TMP=/tmp/getpip
rm -rf "$TMP"; mkdir -p "$TMP"

echo
echo "=== fetching get-pip.py ==="
if command -v curl >/dev/null 2>&1; then
    curl -fsSL -o "$TMP/get-pip.py" https://bootstrap.pypa.io/get-pip.py \
        || { echo "FETCH FAILED (curl)"; exit 1; }
elif command -v wget >/dev/null 2>&1; then
    wget -qO "$TMP/get-pip.py" https://bootstrap.pypa.io/get-pip.py \
        || { echo "FETCH FAILED (wget)"; exit 1; }
else
    echo "no curl or wget -- cannot bootstrap without sudo"
    exit 1
fi
echo "  got $(wc -c < "$TMP/get-pip.py") bytes"

echo
echo "=== installing pip into the user site (no sudo) ==="
python3 "$TMP/get-pip.py" --user --break-system-packages 2>&1 | tail -4

echo
echo "=== result ==="
python3 -m pip --version 2>&1 | head -2
rm -rf "$TMP"
