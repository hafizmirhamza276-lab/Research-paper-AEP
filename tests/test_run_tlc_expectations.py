"""Exercise ``scripts/run_tlc.sh``'s verdict logic on the branches that fail.

The CI job added in WS-7 task 7.2 is worth exactly as much as this file. Nine
of the fifteen configurations exist to produce counterexamples, and the only
thing standing between "nine assumptions were shown to be load-bearing" and
"nine configurations were run and nobody looked" is the runner's willingness to
exit non-zero when a configuration that must fail does not.

``docs/26`` §3 rule 13: *"Before a check is treated as evidence, exercise the
branch on which it fails and confirm it does."*

These tests drive the runner with a stub ``java`` on ``PATH`` rather than real
TLC. That is deliberate: what is under test is the expectation comparison and
the exit status, not TLC, and a real run would make the failing branches slow
and would not exercise "a config that should fail passed" at all -- because no
committed configuration does that.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_tlc.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="run_tlc.sh needs bash"
)

PASS_OUTPUT = """\
TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)
Model checking completed. No error has been found.
1234 states generated, 567 distinct states found, 0 states left on queue.
The depth of the complete state graph search is 22.
"""

FAIL_TEMPLATE = """\
TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)
Error: Invariant {name} is violated.
Error: The behavior up to this point is:
State 1: <Initial predicate>
99 states generated, 42 distinct states found, 7 states left on queue.
The depth of the complete state graph search is 8.
"""


@pytest.fixture
def harness(tmp_path):
    """A fake repository root with one configuration and a stub ``java``."""
    formal = tmp_path / "formal" / "configs"
    formal.mkdir(parents=True)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy(RUNNER, scripts / "run_tlc.sh")
    (tmp_path / "formal" / "AEP.tla").write_text("---- MODULE AEP ----\n====\n")

    bindir = tmp_path / "bin"
    bindir.mkdir()
    jar = tmp_path / "tla2tools.jar"
    jar.write_text("not really a jar")

    def _make(expect_line: str, stdout: str, *, name: str = "demo") -> dict:
        cfg = formal / f"{name}.cfg"
        cfg.write_text(
            expect_line
            + "\nSPECIFICATION FairSpec\n\nCONSTANTS\n    MaxVersion = 5\n"
            "    Workers = {w1, w2}\n\nINVARIANTS\n    TypeOK\n",
            encoding="utf-8",
            newline="\n",
        )
        # The stub ignores its arguments and prints a canned TLC transcript.
        # `-version`-style probes in the runner's banner get the same text,
        # which is harmless.
        stub = bindir / "java"
        stub.write_text(
            "#!/usr/bin/env bash\ncat <<'TLCEOF'\n" + stdout + "TLCEOF\n",
            encoding="utf-8",
            newline="\n",
        )
        stub.chmod(0o755)
        return {"root": tmp_path, "jar": jar, "bindir": bindir, "name": name}

    return _make


def run(harness_info, extra_env=None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PATH"] = f"{harness_info['bindir']}{os.pathsep}" + env["PATH"]
    env["TLA_TOOLS"] = str(harness_info["jar"])
    env["TLC_LOGDIR"] = str(harness_info["root"] / "logs")
    env["TLC_TIMEOUT"] = "60"
    env.update(extra_env or {})
    return subprocess.run(
        ["bash", str(harness_info["root"] / "scripts" / "run_tlc.sh")],
        capture_output=True, text=True, env=env, cwd=harness_info["root"],
    )


# --------------------------------------------------------------------------
# The two agreeing cases.
# --------------------------------------------------------------------------


def test_a_config_that_must_pass_and_does_is_green(harness):
    info = harness(r"\* EXPECT: pass", PASS_OUTPUT)
    result = run(info)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
    assert "matched their declared expectation" in result.stdout


def test_a_config_that_must_fail_and_does_is_green(harness):
    info = harness(r"\* EXPECT: fail NoLostEffect",
                   FAIL_TEMPLATE.format(name="NoLostEffect"))
    result = run(info)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


# --------------------------------------------------------------------------
# The branches the CI job depends on.
# --------------------------------------------------------------------------


def test_a_config_that_must_fail_but_passes_goes_red(harness):
    """The failure mode this whole job exists to catch.

    An assumption stops being load-bearing -- or the model stops modelling the
    thing that depended on it -- and the configuration quietly starts passing.
    Nothing about the output looks wrong; it says "No error has been found",
    which is what the other six configurations say.
    """
    info = harness(r"\* EXPECT: fail NoLostEffect", PASS_OUTPUT)
    result = run(info)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "UNEXPECTED" in result.stdout
    assert "did not match their declared expectation" in result.stdout


def test_a_config_that_fails_for_the_wrong_reason_goes_red(harness):
    """Failing is not enough; it has to fail for the declared reason.

    This is not hypothetical. ``untruthful-endpoint`` was committed expecting
    ``NoUndetectedDuplicate`` and actually breaks ``NoLostEffect`` first, seven
    steps earlier. Without this branch the expectation would have stayed wrong
    and the README would have described a counterexample nobody had produced.
    """
    info = harness(r"\* EXPECT: fail NoUndetectedDuplicate",
                   FAIL_TEMPLATE.format(name="NoLostEffect"))
    result = run(info)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "WRONG-REASON" in result.stdout


def test_a_config_that_must_pass_but_fails_goes_red(harness):
    info = harness(r"\* EXPECT: pass", FAIL_TEMPLATE.format(name="NoLostEffect"))
    result = run(info)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "UNEXPECTED" in result.stdout


def test_a_config_with_no_expectation_is_fatal(harness):
    """A config that declares nothing must not be silently treated as passing."""
    info = harness(r"\* just a comment", PASS_OUTPUT)
    result = run(info)
    assert result.returncode == 2
    assert "no EXPECT line" in result.stderr


def test_a_crashed_tlc_is_not_read_as_a_pass(harness):
    """TLC dying is not a model-checking result.

    This happened during WS-7: two concurrent runs shared a states directory
    and one died with an IOException. It must not read as either outcome.
    """
    info = harness(r"\* EXPECT: pass",
                   "Exception in thread \"main\" java.io.IOException: boom\n")
    result = run(info)
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_a_carriage_return_in_the_expectation_still_matches(harness):
    """These configs are edited on Windows as well as Linux.

    A trailing CR silently turned an exact match into WRONG-REASON once
    already, which reads as a real disagreement between the model and its
    documentation.
    """
    info = harness("\\* EXPECT: fail NoLostEffect\r",
                   FAIL_TEMPLATE.format(name="NoLostEffect"))
    result = run(info)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WRONG-REASON" not in result.stdout


# --------------------------------------------------------------------------
# The bound overrides, which the CI job and the by-hand sweep both rely on.
# --------------------------------------------------------------------------


def test_the_version_bound_override_is_applied(harness):
    info = harness(r"\* EXPECT: pass", PASS_OUTPUT)
    result = run(info, {"TLC_MAX_VERSION": "3"})
    assert result.returncode == 0, result.stdout + result.stderr
    derived = (info["root"] / "logs" / "demo.bounded.cfg").read_text()
    assert "MaxVersion = 3" in derived


def test_the_worker_set_override_is_applied(harness):
    info = harness(r"\* EXPECT: pass", PASS_OUTPUT)
    result = run(info, {"TLC_WORKER_SET": "{w1, w2, w3}"})
    assert result.returncode == 0, result.stdout + result.stderr
    derived = (info["root"] / "logs" / "demo.bounded.cfg").read_text()
    assert "{w1, w2, w3}" in derived


def test_an_override_that_matches_nothing_is_fatal(harness):
    """A silent no-op substitution would report a bound it never used.

    That is exactly what happened to a hand-written three-worker probe here:
    the sed matched nothing, the run used two workers, and the only clue was
    that the state count came back identical to the two-worker run.
    """
    info = harness(r"\* EXPECT: pass", PASS_OUTPUT)
    cfg = info["root"] / "formal" / "configs" / "demo.cfg"
    cfg.write_text(
        cfg.read_text(encoding="utf-8").replace("MaxVersion = 5", "Versions = 5"),
        encoding="utf-8", newline="\n",
    )
    result = run(info, {"TLC_MAX_VERSION": "3"})
    assert result.returncode == 2
    assert "could not set MaxVersion" in result.stderr
