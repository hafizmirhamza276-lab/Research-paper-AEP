# shellcheck shell=bash
# The guard that makes `docs/25` R16 a mechanism rather than a sentence.
#
# R16 says a test must not execute a collection script. That rule is advisory:
# nothing stops the next parametrised test doing exactly what phase 19's did.
# These functions are what stops it, and they work by removing the two
# properties that made the accident possible.
#
#   1. A COMPILED-IN DEFAULT results root. `fsync_always_benchmark.sh` had
#      `RESULTS_ROOT="experiments/results/fsync-always"` -- a frozen, published
#      directory -- so a bare invocation, or a test invocation with no
#      environment set, aimed at it. `wsl_launch_matrix.sh` still defaults to
#      the frozen 432-run `matrix` root the same way. A caller that has not
#      said where results go has not decided where results go, and guessing on
#      their behalf is how published data gets written into.
#
#   2. AN UNGUARDED DELETE. The same script's clean path was
#      `rm -rf "${RESULTS_ROOT}"` with the switch defaulting to ON. Sixty
#      executions went, and survived only because a copy existed elsewhere
#      that nothing in this repository knew about.
#
# The marker below is rule 9's shape, moved from Redis to the filesystem. The
# harness refuses to touch a Redis that has not advertised `aep:test-instance-
# marker`, because it deletes keys and kills processes there. A directory that
# is about to be recursively deleted has to opt in the same way: by containing
# a file that says so. Frozen results will never contain one, which is the
# entire point -- the guard cannot be satisfied by accident.

AEP_SCRATCH_MARKER=".aep-scratch-results-root"

# aep_require_explicit_results_root VARNAME
#
# Exit 2 if the named variable is unset or empty. No default is supplied, ever.
aep_require_explicit_results_root() {
  local name="$1"
  local value="${!name-}"
  if [ -z "${value}" ]; then
    echo "REFUSING: ${name} is not set." >&2
    echo "          This script has no default results root, deliberately:" >&2
    echo "          the defaults it used to have pointed at frozen, published" >&2
    echo "          directories (docs/25 R16). Name the root explicitly, and" >&2
    echo "          make it a new dated directory." >&2
    return 2
  fi
  return 0
}

# aep_refuse_nonempty_results_root PATH
#
# Exit 3 if PATH exists and has anything in it. A collection appends to its own
# output; it never joins someone else's.
aep_refuse_nonempty_results_root() {
  local root="$1"
  if [ -e "${root}" ] && [ -n "$(ls -A "${root}" 2>/dev/null)" ]; then
    echo "REFUSING: ${root} already exists and is not empty." >&2
    echo "          This script does not write into a populated results root" >&2
    echo "          and does not delete one. Point it at a new dated" >&2
    echo "          directory (docs/26 rule 2: frozen results are immutable)." >&2
    return 3
  fi
  return 0
}

# aep_mark_results_root_scratch PATH
#
# Opt PATH in to deletion. Only a caller that created the directory for a test
# should ever call this, and it is the only way aep_guarded_rm_results can
# succeed.
aep_mark_results_root_scratch() {
  local root="$1"
  mkdir -p "${root}" || return 1
  {
    echo "This directory is scratch. scripts/lib/results_root_guard.sh will"
    echo "delete it recursively on request because this file exists."
    echo "No frozen or published results root may ever contain this file."
  } > "${root}/${AEP_SCRATCH_MARKER}"
}

# aep_guarded_rm_results PATH
#
# Recursively delete PATH -- but only if it has advertised that it is scratch.
# Exit 4 otherwise. This is the function that would have refused phase 19.
aep_guarded_rm_results() {
  local root="$1"
  if [ -z "${root}" ] || [ "${root}" = "/" ]; then
    echo "REFUSING: refusing to delete '${root}'." >&2
    return 4
  fi
  if [ ! -e "${root}" ]; then
    return 0
  fi
  if [ ! -f "${root}/${AEP_SCRATCH_MARKER}" ]; then
    echo "REFUSING: ${root} has no ${AEP_SCRATCH_MARKER}, so it has not" >&2
    echo "          declared itself disposable. Not deleting it." >&2
    echo "          This is rule 9's marker, applied to a directory: the" >&2
    echo "          thing about to be destroyed has to opt in first. A" >&2
    echo "          frozen results root never will." >&2
    return 4
  fi
  rm -rf -- "${root}"
}
