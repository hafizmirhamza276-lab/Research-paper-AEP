"""The service can be started the way the roadmap says it can.

PAPER_ROADMAP.md section 3.1(1) asks for a docker-compose entry. These checks
are cheap cross-file agreement, not a substitute for building the image: the
build and a full request/read-back/oracle round trip against the running
container are recorded in the Session 1 report. What they catch is drift --
a renamed configuration file, a Dockerfile that stops installing the
``experiments`` extra, a compose entry pointing at a path that no longer
exists -- none of which any import would notice.
"""

from __future__ import annotations

from pathlib import Path

import yaml

MODULE_DIRECTORY = Path(__file__).resolve().parent.parent
COMPOSE = MODULE_DIRECTORY / "compose.mock-api.yml"
DOCKERFILE = MODULE_DIRECTORY / "Dockerfile"


def compose_document() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_the_compose_entry_exists_and_parses():
    document = compose_document()

    assert set(document["services"]) == {"mock-legacy-api"}


def test_the_compose_entry_builds_from_the_repository_root():
    """The service imports aep_core, so the package has to be in context."""
    build = compose_document()["services"]["mock-legacy-api"]["build"]

    assert build["context"] == "../.."
    assert (
        MODULE_DIRECTORY.parents[1] / build["dockerfile"]
    ).is_file(), f"compose points at a missing {build['dockerfile']}"


def test_the_compose_entry_mounts_a_configuration_that_exists():
    volumes = compose_document()["services"]["mock-legacy-api"]["volumes"]
    host_paths = [entry.split(":")[0] for entry in volumes if entry.startswith(".")]

    assert host_paths, "no configuration is mounted, so the image default wins"
    for relative in host_paths:
        assert (MODULE_DIRECTORY / relative).is_file(), relative


def test_the_compose_entry_publishes_only_on_loopback():
    """A fault-injecting service must not be reachable from the network."""
    ports = compose_document()["services"]["mock-legacy-api"]["ports"]

    assert all(str(port).startswith("127.0.0.1:") for port in ports), ports


def test_the_compose_entry_keeps_results_outside_the_container():
    volumes = compose_document()["services"]["mock-legacy-api"]["volumes"]

    assert any("/app/experiments/results" in entry for entry in volumes), (
        "the ground-truth ledger would be destroyed with the container"
    )


def test_the_image_installs_from_the_lockfile():
    """An image resolving its own dependencies is a different environment."""
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "uv sync --frozen" in dockerfile
    assert "--extra experiments" in dockerfile


def test_the_image_is_built_on_the_pinned_interpreter():
    recorded = (
        MODULE_DIRECTORY.parents[1] / ".python-version"
    ).read_text(encoding="utf-8").strip()
    major_minor = ".".join(recorded.split(".")[:2])

    assert f"FROM python:{major_minor}" in DOCKERFILE.read_text(encoding="utf-8")
