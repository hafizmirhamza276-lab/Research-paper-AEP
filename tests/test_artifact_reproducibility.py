"""Tests that the reproducibility claims in the artifact stay consistent.

An artifact-evaluation package makes claims about *the environment*, not just
the code: this Redis image, this Python, this dependency set. Those claims
live in several files that no compiler cross-checks -- compose.phase2.yml,
.github/workflows/ci.yml, pyproject.toml, .python-version, uv.lock. When they
drift, nothing breaks loudly; the artifact just quietly stops describing what
actually ran.

These tests are the cross-check. They are deliberately about *agreement
between declarations*, not about whether any particular version is correct.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

COMPOSE = REPO_ROOT / "compose.phase2.yml"
PYPROJECT = REPO_ROOT / "pyproject.toml"
PYTHON_VERSION_FILE = REPO_ROOT / ".python-version"
LOCKFILE = REPO_ROOT / "uv.lock"
REDIS_CONF = REPO_ROOT / "redis" / "phase2.conf"

#: redis:<tag>@sha256:<64 hex>
PINNED_IMAGE = re.compile(r"(redis:[\w.-]+@sha256:[0-9a-f]{64})")


def workflow_path() -> Path:
    return REPO_ROOT / ".github" / "workflows" / "ci.yml"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ===========================================================================
# The Redis image is pinned, and pinned to the same digest everywhere
# ===========================================================================


def test_compose_pins_redis_by_digest():
    """A tag can be re-pointed; every durability claim rests on this image."""
    matches = PINNED_IMAGE.findall(read(COMPOSE))

    assert matches, "compose.phase2.yml does not pin the Redis image by digest"


def test_the_workflow_pins_redis_by_digest():
    matches = PINNED_IMAGE.findall(read(workflow_path()))

    assert matches, "ci.yml does not pin the Redis image by digest"


def test_compose_and_ci_agree_on_the_redis_image():
    """The digest appears in both files; nothing else forces them to match."""
    compose_images = set(PINNED_IMAGE.findall(read(COMPOSE)))
    workflow_images = set(PINNED_IMAGE.findall(read(workflow_path())))

    assert len(compose_images) == 1, f"expected one image in compose: {compose_images}"
    assert workflow_images == compose_images, (
        "compose.phase2.yml and .github/workflows/ci.yml disagree about the "
        f"Redis image: {compose_images} vs {workflow_images}"
    )


def test_the_pinned_redis_is_a_7_2_release():
    """WAITAOF does not exist before 7.2; the barrier is unevidenced without it."""
    (image,) = set(PINNED_IMAGE.findall(read(COMPOSE)))
    tag = image.split("@")[0].removeprefix("redis:")

    assert tag.startswith("7.2."), f"pinned Redis tag is {tag!r}, expected a 7.2.x"


# ===========================================================================
# Python version declarations agree
# ===========================================================================


def test_the_python_version_file_pins_a_patch_release():
    recorded = read(PYTHON_VERSION_FILE).strip()

    assert re.fullmatch(r"3\.13\.\d+", recorded), (
        f".python-version records {recorded!r}; expected an exact 3.13.x patch "
        "release, since that is what the verified runs used"
    )


def test_requires_python_admits_the_pinned_interpreter():
    recorded = read(PYTHON_VERSION_FILE).strip()
    metadata = tomllib.loads(read(PYPROJECT))
    requires = metadata["project"]["requires-python"]

    major_minor = ".".join(recorded.split(".")[:2])
    assert major_minor in requires, (
        f"requires-python is {requires!r} but .python-version is {recorded!r}"
    )


def test_requires_python_is_upper_bounded():
    """An unbounded range claims support for interpreters never tested."""
    metadata = tomllib.loads(read(PYPROJECT))
    requires = metadata["project"]["requires-python"]

    assert "<" in requires, (
        f"requires-python is {requires!r}; without an upper bound the artifact "
        "claims support for interpreters it has never been run on"
    )


def test_the_lockfile_agrees_with_requires_python():
    lock = tomllib.loads(read(LOCKFILE))

    assert "3.13" in lock["requires-python"], (
        f"uv.lock targets {lock['requires-python']!r}, not 3.13"
    )


# ===========================================================================
# The lockfile actually pins, and covers what the suite imports
# ===========================================================================


def test_every_locked_package_has_an_exact_version():
    lock = tomllib.loads(read(LOCKFILE))

    unpinned = [p["name"] for p in lock["package"] if not p.get("version")]

    assert unpinned == [], f"lockfile entries without a version: {unpinned}"


@pytest.mark.parametrize(
    "package", ["redis", "pydantic", "cryptography", "pytest", "pytest-asyncio", "fakeredis"]
)
def test_the_lockfile_covers_the_runtime_and_test_dependencies(package):
    lock = tomllib.loads(read(LOCKFILE))
    names = {p["name"] for p in lock["package"]}

    assert package in names, f"{package} is missing from uv.lock"


def test_the_project_itself_is_in_the_lockfile_under_its_renamed_package():
    lock = tomllib.loads(read(LOCKFILE))
    names = {p["name"] for p in lock["package"]}

    assert "aep-core" in names


# ===========================================================================
# Packaging points at the renamed package, not the old one
# ===========================================================================


def test_setuptools_discovers_the_renamed_package():
    metadata = tomllib.loads(read(PYPROJECT))
    include = metadata["tool"]["setuptools"]["packages"]["find"]["include"]

    assert include == ["aep_core*"], f"packages.find include is {include!r}"
    assert (REPO_ROOT / "aep_core" / "__init__.py").is_file()
    assert not (REPO_ROOT / "src").exists(), "the old src/ package still exists"


def test_the_coverage_gate_targets_the_renamed_package():
    metadata = tomllib.loads(read(PYPROJECT))

    assert metadata["tool"]["coverage"]["run"]["source"] == ["aep_core"]
    assert metadata["tool"]["coverage"]["report"]["fail_under"] == 90


def test_xfail_strict_is_enabled():
    """Gate (ii): an xfail that starts passing must not be a mere summary note."""
    metadata = tomllib.loads(read(PYPROJECT))

    assert metadata["tool"]["pytest"]["ini_options"]["xfail_strict"] is True


# ===========================================================================
# The CI workflow wires every gate the roadmap requires
# ===========================================================================


@pytest.mark.parametrize(
    ("fragment", "gate"),
    [
        ("scripts/check_pytest_gates.py", "zero-skip / zero-xpass gate"),
        ("--cov-fail-under=90", "coverage gate"),
        ("scripts/validate_citations.py", "citation range gate"),
        ("scripts/verify_redis_semantics.py", "Redis semantics gate"),
    ],
)
def test_the_workflow_invokes_each_gate(fragment, gate):
    assert fragment in read(workflow_path()), f"CI does not run the {gate}"


def test_the_workflow_runs_the_suite_with_ra():
    """Gate (ii) reads the -ra short summary; without it there is nothing to read."""
    assert "-q -ra --strict-markers" in read(workflow_path())


# ===========================================================================
# Redis provisioning: compose everywhere, and nothing deselected
#
# docs/23-ci-hardening-report.md G1. The `test` job used to take Redis from a
# GitHub `services:` block. A service container starts before checkout, so it
# cannot mount redis/phase2.conf and cannot survive `docker restart` with AOF
# intact -- which forced one test to be deselected by name. A deselection is
# the one construct in this workflow that lets a gate go green without the
# work being done, so it is now forbidden outright and both jobs take Redis
# from compose.phase2.yml, the same definition developers run locally.
# ===========================================================================

#: Jobs that must provision Redis themselves. The citations job runs no test
#: that touches Redis, so requiring compose of it would be theatre.
REDIS_DEPENDENT_JOBS = ("test", "waitaof-durability")


def workflow_jobs() -> dict:
    import yaml

    return yaml.safe_load(read(workflow_path()))["jobs"]


def job_script(job: dict) -> str:
    """Every `run:` line of one job, concatenated."""
    return "\n".join(step.get("run", "") for step in job["steps"])


def test_the_workflow_deselects_nothing_anywhere():
    """The only construct that can satisfy a gate without doing the work."""
    workflow = read(workflow_path())

    assert "--deselect" not in workflow, (
        "ci.yml deselects a test by name. A deselected test is invisible to "
        "the zero-skip gate: the job reports green and the summary shows no "
        "skip, yet the test never ran. Run it, or delete it."
    )


@pytest.mark.parametrize("job_name", REDIS_DEPENDENT_JOBS)
def test_every_redis_job_provisions_redis_from_compose(job_name):
    job = workflow_jobs()[job_name]

    assert "services" not in job, (
        f"job {job_name!r} declares a GitHub services: block. A service "
        "container starts before checkout, so it cannot mount "
        "redis/phase2.conf and does not survive docker restart with AOF."
    )
    assert "docker compose -f compose.phase2.yml up" in job_script(job), (
        f"job {job_name!r} does not start Redis from compose.phase2.yml"
    )


@pytest.mark.parametrize("job_name", REDIS_DEPENDENT_JOBS)
def test_every_redis_job_verifies_semantics_without_applying_them(job_name):
    """`--apply` would let CI paper over a compose file that lost AOF.

    A Redis started from redis/phase2.conf must already report the durability
    settings. Applying them at runtime turns a broken compose definition into
    a passing job, which is exactly the failure this report class exists to
    prevent.
    """
    script = job_script(workflow_jobs()[job_name])

    assert "scripts/verify_redis_semantics.py" in script
    assert "--apply" not in script, (
        f"job {job_name!r} applies Redis settings at runtime instead of "
        "asserting that compose.phase2.yml already provides them"
    )


def test_the_full_suite_job_installs_every_extra_the_suite_imports():
    """A collected test whose imports were never installed is not a test.

    pytest collects ``experiments/`` as well as ``tests/``, and those modules
    import fastapi/httpx/pyyaml from the ``experiments`` extra. Syncing only
    ``dev`` would turn the harness suite into a collection error.
    """
    metadata = tomllib.loads(read(PYPROJECT))
    declared = set(metadata["project"]["optional-dependencies"])
    testpaths = metadata["tool"]["pytest"]["ini_options"]["testpaths"]
    script = job_script(workflow_jobs()["test"])

    assert "experiments" in testpaths
    for extra in sorted(declared):
        assert f"--extra {extra}" in script, (
            f"the full-suite job does not install the {extra!r} extra"
        )


def test_the_restart_test_is_collected_by_the_full_suite():
    """The test the old deselection removed is now run by the `test` job."""
    restart_test = "test_intent_and_resolution_survive_controlled_redis_restart"
    integration_file = REPO_ROOT / "tests" / "test_phase2_waitaof_integration.py"

    assert restart_test in read(integration_file)
    # `testpaths` includes the directory holding it, and nothing excludes it.
    metadata = tomllib.loads(read(PYPROJECT))
    assert "tests" in metadata["tool"]["pytest"]["ini_options"]["testpaths"]


def compose_services() -> dict:
    import yaml

    return yaml.safe_load(read(COMPOSE))["services"]


@pytest.mark.parametrize("job_name", REDIS_DEPENDENT_JOBS)
def test_every_redis_job_names_the_container_the_restart_test_restarts(job_name):
    """`docker restart` needs the compose container name, not a service alias.

    Parsed per service rather than by taking the first ``container_name:`` in
    the file: compose.phase2.yml gained a second container in Phase 2B
    Session 2 (toxiproxy), and a positional read would have kept passing while
    silently checking whichever service happened to be declared first.
    """
    job = workflow_jobs()[job_name]
    container = compose_services()["redis-phase2"]["container_name"]

    assert job["env"]["AEP_PHASE2_REDIS_CONTAINER"] == container


# ===========================================================================
# The worker-to-Redis fault surface is declared, not improvised
#
# PAPER_ROADMAP.md 3.1(2) requires a proxy-based partition between worker and
# Redis. A harness that created its proxy over the API at run time could run
# green against a proxy that was never made; declaring it here means a run
# either has the fault surface or fails to start.
# ===========================================================================


def test_compose_declares_the_toxiproxy_fault_surface():
    services = compose_services()

    assert "toxiproxy" in services, (
        "compose.phase2.yml declares no toxiproxy service, so no run can "
        "partition a worker from Redis"
    )


def test_the_toxiproxy_image_is_pinned_by_digest():
    """Same reasoning as the Redis pin: a tag can be re-pointed."""
    image = compose_services()["toxiproxy"]["image"]

    assert re.search(r"@sha256:[0-9a-f]{64}$", image), (
        f"toxiproxy image {image!r} is not pinned by digest"
    )


def test_the_declared_proxy_points_at_the_redis_this_repository_runs():
    """A partition against some other Redis would prove nothing."""
    import json

    proxies = json.loads(read(REPO_ROOT / "redis" / "toxiproxy.json"))
    services = compose_services()
    (proxy,) = proxies

    assert proxy["upstream"].split(":")[0] in services
    assert proxy["upstream"] == "redis-phase2:6379"
    # The listener the proxy binds must be the one compose publishes.
    published = [str(entry) for entry in services["toxiproxy"]["ports"]]
    assert any(proxy["listen"].split(":")[1] in entry for entry in published)


# ===========================================================================
# redis/phase2.conf still declares what the protocol depends on
# ===========================================================================


@pytest.mark.parametrize(
    ("directive", "value"),
    [("appendonly", "yes"), ("appendfsync", "everysec")],
)
def test_phase2_conf_declares_the_durability_settings(directive, value):
    lines = [
        line.strip()
        for line in read(REDIS_CONF).splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    declared = {
        line.split(" ", 1)[0]: line.split(" ", 1)[1].strip('"')
        for line in lines
        if " " in line
    }

    assert declared.get(directive) == value
