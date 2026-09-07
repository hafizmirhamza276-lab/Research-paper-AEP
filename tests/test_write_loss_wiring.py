r"""The WS-4 compose wiring, and the refusals that keep it honest.

The instrument in `experiments/harness/write_loss.py` is inert unless Redis is
actually writing through the `dm-flakey` mapping. `compose.phase2.yml` backs
`/data` with the named volume `redis-data`, so a session started the ordinary
way runs against a device that **cannot** drop writes — and the `write-loss-preack`
regime would then report a clean AEP-full result for the wrong reason.

Two invariants are pinned here as static file checks, because both are one
careless edit away from disappearing and neither would fail loudly:

* the base compose still backs `/data` with `redis-data`, so the frozen six are
  unaffected by any of this;
* the override still carries the `${VAR:?...}` guard, without which compose
  substitutes an empty string and silently mounts the wrong thing.

The rest pin `load_and_check`'s refusals. The dangerous case is not a missing
file — it is a path that *exists* and is not the flakey device, because nothing
else in the stack would complain.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.up_write_loss import COMPOSE_PATH_VARIABLE, Refused, load_and_check

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE = REPO_ROOT / "compose.phase2.yml"
OVERRIDE = REPO_ROOT / "compose.write-loss.yml"

DEVICE = "aep-ws4-flakey"
FLAKEY_TABLE = "0 1048576 flakey 7:0 0 1 0 2 error_reads error_writes"


# ===========================================================================
# The two static invariants
# ===========================================================================


def test_the_base_compose_still_backs_data_with_the_named_volume():
    """The frozen six must be untouched by the write-loss wiring."""
    text = BASE.read_text(encoding="utf-8")

    assert "redis-data:/data" in text
    assert COMPOSE_PATH_VARIABLE not in text, (
        "the override belongs in compose.write-loss.yml; the base file must "
        "stay usable with no WS-4 variables set"
    )


def test_the_override_keeps_its_refusal_guard():
    """`${VAR:?message}` is what makes compose exit rather than mount nothing.

    With a plain `${VAR}` compose substitutes an empty string and carries on,
    which is the silent fallback this whole file exists to prevent.
    """
    text = OVERRIDE.read_text(encoding="utf-8")

    assert f"${{{COMPOSE_PATH_VARIABLE}:?" in text
    assert ":/data" in text


def test_the_override_does_not_mount_the_named_volume():
    """Comments may discuss `redis-data`; no directive may mount it.

    Checked over non-comment lines only. The first version of this test scanned
    the whole file and failed on the explanatory comment, which is the wrong
    invariant: what matters is what compose acts on, not what the file says.
    """
    directives = [
        line for line in OVERRIDE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert not any("redis-data" in line for line in directives)
    assert any(f"${{{COMPOSE_PATH_VARIABLE}:?" in line for line in directives)


# ===========================================================================
# The refusals
# ===========================================================================


def write_record(root: Path, **overrides) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    redis_dir = root / "mnt" / "redis"
    redis_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "device": DEVICE,
        "redis_dir": str(redis_dir),
        "self_test": {"valid": True, "reason": "ok"},
    }
    record.update(overrides)
    (root / "write-loss-provision.json").write_text(json.dumps(record), encoding="utf-8")
    return root


def patch_device(monkeypatch, *, table: str | None, backing: str | None) -> None:
    monkeypatch.setattr("scripts.up_write_loss.read_table", lambda device: table)
    monkeypatch.setattr("scripts.up_write_loss.backing_device", lambda path: backing)


def test_a_missing_record_is_refused(tmp_path):
    with pytest.raises(Refused, match="no provision record"):
        load_and_check(tmp_path)


def test_a_failed_self_test_is_refused(tmp_path, monkeypatch):
    patch_device(monkeypatch, table=FLAKEY_TABLE, backing=f"/dev/mapper/{DEVICE}")
    root = write_record(tmp_path, self_test={"valid": False, "reason": "canary SURVIVED"})

    with pytest.raises(Refused, match="self-test did not pass"):
        load_and_check(root)


def test_a_stale_record_naming_a_gone_device_is_refused(tmp_path, monkeypatch):
    patch_device(monkeypatch, table=None, backing=None)
    root = write_record(tmp_path)

    with pytest.raises(Refused, match="no longer exists"):
        load_and_check(root)


def test_a_non_flakey_device_is_refused(tmp_path, monkeypatch):
    patch_device(monkeypatch, table="0 1048576 linear 7:0 0", backing=f"/dev/mapper/{DEVICE}")
    root = write_record(tmp_path)

    with pytest.raises(Refused, match="not a dm-flakey target"):
        load_and_check(root)


def test_the_silent_fallback_is_refused(tmp_path, monkeypatch):
    """**The one that matters.** The path exists and is on the wrong device.

    Redis would start, writes would succeed, the regime would arm a device Redis
    is not using, and every run would look like a clean AEP-full result.
    """
    patch_device(monkeypatch, table=FLAKEY_TABLE, backing="/dev/sdd")
    root = write_record(tmp_path)

    with pytest.raises(Refused, match="silent fallback"):
        load_and_check(root)


def test_a_correctly_provisioned_root_is_accepted(tmp_path, monkeypatch):
    patch_device(monkeypatch, table=FLAKEY_TABLE, backing=f"/dev/mapper/{DEVICE}")
    root = write_record(tmp_path)

    record = load_and_check(root)

    assert record["device"] == DEVICE
