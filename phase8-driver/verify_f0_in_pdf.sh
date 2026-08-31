#!/usr/bin/env bash
# Verify F.0 at both edited sites by reading the BUILT PDF, not the source.
#
# The source can satisfy F.0 and the PDF still not, if a macro resolves to
# something unexpected, a float moves the precision clause away from the claim,
# or a \newcommand silently expands to nothing. Reading the source would check
# my own intent; reading the PDF checks what a reviewer sees.
#
# Builds from the artifact-free copy (see build_clean_copy.sh for why) with the
# cleanup trap removed, so the scratch PDF survives for text extraction.
#
# A script file rather than an inline `wsl bash -lc`, per B18.
set -u
R=/mnt/d/personal/AEP/Research-paper-AEP
DEST=/tmp/editpaper

rm -rf "$DEST"; mkdir -p "$DEST"
cp -r "$R/paper" "$DEST/paper" || exit 1
rm -f "$DEST"/paper/main.aux "$DEST"/paper/main.bbl "$DEST"/paper/main.blg \
      "$DEST"/paper/main.log "$DEST"/paper/main.out

# The copy must live one directory below the repo root: build_paper.sh derives
# ROOT from "$(dirname "${BASH_SOURCE[0]}")/..", so a copy in /tmp resolves
# ROOT=/ and puts the scratch tree at /.scratch. phase8-driver/ satisfies it.
KEEP="$R/phase8-driver/.build_keep.sh"
sed 's/^trap cleanup EXIT$/# trap disabled: keep scratch for PDF inspection/' \
    "$R/scripts/build_paper.sh" > "$KEEP"
grep -q 'trap disabled' "$KEEP" || { echo "SED MISS"; exit 1; }

rm -rf "$R/.scratch/paper-build"
cd "$R" || exit 1
AEP_PAPER_DIR="$DEST/paper" bash "$KEEP" > /tmp/keepbuild.txt 2>&1
echo "build exit: $?"
grep -oE 'Output written on main.pdf \([0-9]+ pages' /tmp/keepbuild.txt

BD="$(find "$R/.scratch/paper-build" -maxdepth 1 -mindepth 1 -type d | head -1)"
echo "scratch: ${BD:-NONE}"
[ -z "${BD:-}" ] && { echo "no scratch dir"; exit 1; }
[ -f "$BD/main.pdf" ] || { echo "no PDF in scratch"; exit 1; }

command -v pdftotext >/dev/null 2>&1 || { echo "pdftotext MISSING"; exit 1; }
pdftotext -layout "$BD/main.pdf" /tmp/main.txt || exit 1
cp "$BD/main.pdf" /tmp/built-main.pdf
echo "extracted $(wc -l < /tmp/main.txt) lines of PDF text"

echo
echo "############ SITE 1 as rendered (08-threats limitations list) ############"
grep -n -A24 'prevention result rests on one cell' /tmp/main.txt | head -34

echo
echo "############ SITE 2 as rendered (06-evaluation prevention scope) ############"
grep -n -B2 -A8 'scope of this prevention result' /tmp/main.txt | head -18

echo
echo "############ every Class macro value, as it appears in the PDF ############"
for v in '+0.0' '-10.0' '+23.3' '+36.7' '+12.5' '33.9' '-21.4' '+46.4'; do
    printf '%-8s occurrences: %s\n' "$v" "$(grep -o -- "$v" /tmp/main.txt | wc -l)"
done

echo
echo "############ unexpanded macro residue (would show as literal text) ############"
grep -n 'Class\(Sessions\|RunsPerArm\|Pp\)' /tmp/main.txt | head || echo "  none -- all macros expanded"
