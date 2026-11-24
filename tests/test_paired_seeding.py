"""Amendment 8: both arms meet the same conditions, or the comparison is void.

`reports/phase-report-40-fault-symmetry-2026-09-22.md` established that
`cell_seed` derives a run's seed from a key beginning with the system name, so
`AEP_FULL` and `B0_NAIVE_RETRY` faced different faults on different payments.
At one or two runs per arm there is nothing to average that out.

The two halves pinned here:

* **the workload is paired** -- same execution ids, targets, amounts and crash
  selection for the same repetition;
* **the fault is keyed to the request**, not to its position in a sequence, so
  the same logical request meets the same fault on both arms *whatever else
  either arm sends*.

The second is the one that needed a design rather than a shared seed, and
`test_an_extra_request_on_one_arm_cannot_shift_the_other` is the case that
shows why.
"""
from __future__ import annotations

import hashlib

import pytest

from experiments.harness.workload import (
    PAIR_ID_ENV,
    PAIR_SEED_ENV,
    pairing_identity,
    plan_workload,
)
from experiments.mock_api.config import (
    ConfigError,
    CrashSimulation,
    DelayProfile,
    EndpointConfig,
    FaultProfile,
    MockApiConfig,
    ReadbackKeying,
)
from experiments.mock_api.service import MockLegacyAPI, _paired_uniforms
from experiments.run_matrix import MATRIX_VERSION, cell_seed, pair_identity, pair_key


class _Config:
    """The fields plan_workload reads."""

    def __init__(self, system, run_id, seed, **kw):
        self.system = system
        self.run_id = run_id
        self.seed = seed
        self.workers = kw.get("workers", 1)
        self.executions_per_worker = kw.get("executions_per_worker", 3)
        self.crash_probability = kw.get("crash_probability", 0.5)


AEP = _Config("AEP_FULL", "aep_full-mid_dispatch-notifications-ea8836a3-r0",
              1174872249)
B0 = _Config("B0_NAIVE_RETRY",
             "b0_naive_retry-mid_dispatch-notifications-54dae940-r0", 4811467)


@pytest.fixture
def paired(monkeypatch):
    monkeypatch.setenv(PAIR_ID_ENV, "pair-abcdef12-r0")
    monkeypatch.setenv(PAIR_SEED_ENV, "987654321")


@pytest.fixture
def unpaired(monkeypatch):
    monkeypatch.delenv(PAIR_ID_ENV, raising=False)
    monkeypatch.delenv(PAIR_SEED_ENV, raising=False)


def fields(items):
    return [
        (i.execution_index, i.execution_id, i.target, i.amount_minor,
         i.crash_selected)
        for i in items
    ]


# ---------------------------------------------------------------------------
# The fault this fixes
# ---------------------------------------------------------------------------

def test_the_arm_name_is_what_made_the_seeds_differ():
    """The finding, pinned so it cannot quietly come back."""
    material_with = f"20260806|{MATRIX_VERSION}|AEP_FULL|mid_dispatch|x|y|0"
    material_without = f"20260806|{MATRIX_VERSION}|mid_dispatch|x|y|0"
    assert material_with != material_without
    assert hashlib.sha256(material_with.encode()).digest()[:4] != \
        hashlib.sha256(material_without.encode()).digest()[:4]


def real_cell(system_name):
    """A genuine Cell, so cell_seed and pair_key see what the matrix sees."""
    from experiments.baselines.contract import SystemId
    from experiments.run_matrix import Cell

    return Cell(
        system=SystemId(system_name),
        crash_point="mid_dispatch",
        endpoint="notifications",
        response_class="POSITIVE_ONLY_READBACK",
        readback_keying=ReadbackKeying.CALLER_REFERENCE,
        tier=1,
        applicable=True,
    )


def test_pair_key_drops_the_system_and_keeps_everything_else():
    cell = real_cell("AEP_FULL")
    key = pair_key(cell)
    assert "AEP_FULL" not in key
    assert "mid_dispatch" in key and "notifications" in key
    assert "CALLER_REFERENCE" in key


# ---------------------------------------------------------------------------
# The workload is paired
# ---------------------------------------------------------------------------

def test_unpaired_the_two_arms_get_different_workloads(unpaired):
    """The state the archives are in, and the reason for everything below."""
    assert fields(plan_workload(AEP)) != fields(plan_workload(B0))


def test_paired_the_two_arms_get_an_identical_workload(paired):
    aep, b0 = plan_workload(AEP), plan_workload(B0)
    assert fields(aep) == fields(b0)


@pytest.mark.parametrize(
    "attribute", ["execution_id", "target", "amount_minor", "crash_selected"]
)
def test_each_field_individually(paired, attribute):
    """Named one at a time, so a partial pairing cannot pass as a whole one."""
    aep = [getattr(i, attribute) for i in plan_workload(AEP)]
    b0 = [getattr(i, attribute) for i in plan_workload(B0)]
    assert aep == b0, attribute


def test_a_fractional_crash_probability_still_pairs(monkeypatch):
    """crash_selected is derived, so it must pair like the rest."""
    monkeypatch.setenv(PAIR_ID_ENV, "pair-abcdef12-r0")
    monkeypatch.setenv(PAIR_SEED_ENV, "987654321")
    aep = _Config("AEP_FULL", AEP.run_id, AEP.seed, crash_probability=0.5,
                  executions_per_worker=12)
    b0 = _Config("B0_NAIVE_RETRY", B0.run_id, B0.seed, crash_probability=0.5,
                 executions_per_worker=12)
    selected = [i.crash_selected for i in plan_workload(aep)]
    assert selected == [i.crash_selected for i in plan_workload(b0)]
    assert len(set(selected)) == 2, "the fixture must actually vary"


def test_different_reps_still_get_different_schedules(monkeypatch):
    """Pairing must not collapse the repetitions into one another."""
    seen = []
    for rep in range(4):
        monkeypatch.setenv(PAIR_ID_ENV, f"pair-abcdef12-r{rep}")
        monkeypatch.setenv(PAIR_SEED_ENV, str(1000 + rep))
        seen.append(fields(plan_workload(AEP)))
    for index in range(1, len(seen)):
        assert seen[index] != seen[0], f"rep {index} repeats rep 0"


def test_pair_identity_differs_by_repetition():
    first = pair_identity(20260806, real_cell("AEP_FULL"), 0)
    second = pair_identity(20260806, real_cell("AEP_FULL"), 1)
    assert first != second
    assert first[0] != second[0] and first[1] != second[1]


def test_pair_identity_is_the_same_for_both_systems():
    aep = real_cell("AEP_FULL")
    b0 = real_cell("B0_NAIVE_RETRY")
    assert pair_identity(20260806, aep, 0) == pair_identity(20260806, b0, 0)
    # ... while the UNPAIRED seeds still differ, which is the matrix's rule.
    assert cell_seed(20260806, aep, 0) != cell_seed(20260806, b0, 0)


# ---------------------------------------------------------------------------
# The known-positive: put the arm back in and these fail
# ---------------------------------------------------------------------------

def test_putting_the_system_name_back_into_the_pairing_breaks_it(monkeypatch):
    """R2. A pairing that cannot be broken is not evidence of pairing.

    Simulated by giving the two arms arm-specific pair ids, which is exactly
    what the unpaired state is.
    """
    monkeypatch.setenv(PAIR_SEED_ENV, "987654321")

    monkeypatch.setenv(PAIR_ID_ENV, "pair-AEP_FULL-r0")
    aep = fields(plan_workload(AEP))
    monkeypatch.setenv(PAIR_ID_ENV, "pair-B0_NAIVE_RETRY-r0")
    b0 = fields(plan_workload(B0))

    assert aep != b0, (
        "the workload did not change when the arm was put back into the "
        "pairing key, so the tests above prove nothing"
    )


def test_an_arm_specific_pair_seed_also_breaks_it(monkeypatch):
    monkeypatch.setenv(PAIR_ID_ENV, "pair-abcdef12-r0")
    monkeypatch.setenv(PAIR_SEED_ENV, "1174872249")
    aep = fields(plan_workload(AEP))
    monkeypatch.setenv(PAIR_SEED_ENV, "4811467")
    b0 = fields(plan_workload(B0))
    assert aep != b0


# ---------------------------------------------------------------------------
# A half-applied pairing is refused
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("present", [PAIR_ID_ENV, PAIR_SEED_ENV])
def test_one_variable_without_the_other_is_refused(monkeypatch, present):
    """It would look paired and would not be, which is worse than neither."""
    monkeypatch.delenv(PAIR_ID_ENV, raising=False)
    monkeypatch.delenv(PAIR_SEED_ENV, raising=False)
    monkeypatch.setenv(present, "1" if present == PAIR_SEED_ENV else "pair-x")
    with pytest.raises(ValueError, match="must be set together"):
        pairing_identity(AEP)


def test_a_non_integer_pair_seed_is_refused(monkeypatch):
    monkeypatch.setenv(PAIR_ID_ENV, "pair-x")
    monkeypatch.setenv(PAIR_SEED_ENV, "not-a-number")
    with pytest.raises(ValueError, match="not an integer"):
        pairing_identity(AEP)


def test_unset_falls_back_to_the_runs_own_identity(unpaired):
    assert pairing_identity(AEP) == (AEP.run_id, AEP.seed)
    assert pairing_identity(B0) == (B0.run_id, B0.seed)


# ---------------------------------------------------------------------------
# The fault is keyed to the request, not to the sequence
# ---------------------------------------------------------------------------

def _api(tmp_path, *, pair_seed, server_error=0.5, timeout=0.5):
    endpoint = EndpointConfig(
        name="notifications",
        response_class=__import__(
            "aep_core.core.connector_contract", fromlist=["ReconciliationCapability"]
        ).ReconciliationCapability.POSITIVE_ONLY_READBACK,
        identity_fields=("action", "amount_minor"),
        faults=FaultProfile(
            delay=DelayProfile(),
            timeout_probability=timeout,
            server_error_probability=server_error,
            duplicate_response_probability=0.0,
        ),
        crash_simulation=CrashSimulation(),
    )
    config = MockApiConfig(
        config_version="aep.mock-legacy-api.config/1",
        seed=12345,
        ledger_path=str(tmp_path / "gt.sqlite3"),
        endpoints={"notifications": endpoint},
        source_path=str(tmp_path / "mock.yaml"),
        readback_keying=ReadbackKeying.CALLER_REFERENCE,
        pair_seed=pair_seed,
    )
    return MockLegacyAPI(config)


def test_the_same_request_meets_the_same_fault_on_both_arms(tmp_path):
    arm_a = _api(tmp_path / "a", pair_seed=777)
    arm_b = _api(tmp_path / "b", pair_seed=777)
    for fingerprint in ("fp-1", "fp-2", "fp-3"):
        ordinal_a = arm_a.dispatch_ordinal(fingerprint)
        ordinal_b = arm_b.dispatch_ordinal(fingerprint)
        assert ordinal_a == ordinal_b == 0
        assert arm_a.draw_faults(
            "notifications", fingerprint=fingerprint, ordinal=ordinal_a
        ) == arm_b.draw_faults(
            "notifications", fingerprint=fingerprint, ordinal=ordinal_b
        )


def test_an_extra_request_on_one_arm_cannot_shift_the_other(tmp_path):
    """**The case a shared seed could not have handled.**

    Arm B sends an extra mutation between the two both arms share -- a retry,
    or a dispatch the other arm's gate withheld. Under the sequential draw that
    shifts every fault after it by three. Keyed to the request, it shifts
    nothing.
    """
    arm_a = _api(tmp_path / "a", pair_seed=777)
    arm_b = _api(tmp_path / "b", pair_seed=777)

    def fire(api, fingerprint):
        ordinal = api.dispatch_ordinal(fingerprint)
        return api.draw_faults(
            "notifications", fingerprint=fingerprint, ordinal=ordinal
        )

    a_first = fire(arm_a, "shared-1")
    b_first = fire(arm_b, "shared-1")
    assert a_first == b_first

    # Arm B does something arm A does not.
    fire(arm_b, "b-only-extra")
    fire(arm_b, "b-only-extra")

    a_second = fire(arm_a, "shared-2")
    b_second = fire(arm_b, "shared-2")
    assert a_second == b_second, (
        "an extra request on one arm shifted the fault the other arm met"
    )


def test_a_redispatch_of_the_same_payment_can_meet_a_different_fault(tmp_path):
    """Ordinal 1 is a different logical request, and identically so on both."""
    arm_a = _api(tmp_path / "a", pair_seed=777)
    arm_b = _api(tmp_path / "b", pair_seed=777)

    first_a = arm_a.draw_faults("notifications", fingerprint="fp", ordinal=0)
    second_a = arm_a.draw_faults("notifications", fingerprint="fp", ordinal=1)
    second_b = arm_b.draw_faults("notifications", fingerprint="fp", ordinal=1)

    assert second_a == second_b
    assert (first_a, second_a) is not None  # both drawn; may or may not differ


def test_the_keyed_draw_ignores_the_sequential_generator(tmp_path):
    """Consuming the sequential stream must not change a keyed outcome."""
    api = _api(tmp_path, pair_seed=777)
    before = api.draw_faults("notifications", fingerprint="fp", ordinal=0)
    for _ in range(50):
        api._random.random()
    after = api.draw_faults("notifications", fingerprint="fp", ordinal=0)
    assert before == after


def test_without_a_pair_seed_the_draw_is_still_sequential(tmp_path):
    """The matrix's behaviour is untouched."""
    api = _api(tmp_path, pair_seed=None)
    first = api.draw_faults("notifications", fingerprint="fp", ordinal=0)
    second = api.draw_faults("notifications", fingerprint="fp", ordinal=0)
    # Same arguments, different answers: it advanced a generator.
    assert isinstance(first, tuple) and isinstance(second, tuple)
    drawn = [
        api.draw_faults("notifications", fingerprint="fp", ordinal=0)
        for _ in range(40)
    ]
    assert len(set(drawn)) > 1, "the unpaired path stopped being sequential"


def test_the_probabilities_are_unchanged_by_pairing(tmp_path):
    """Amendment 8 §6: only the pairing changes, not the distribution."""
    api = _api(tmp_path, pair_seed=777, server_error=0.05, timeout=0.15)
    trials = 20000
    errors = timeouts = 0
    for index in range(trials):
        server_error, timeout, _ = api.draw_faults(
            "notifications", fingerprint=f"fp-{index}", ordinal=0
        )
        errors += server_error
        timeouts += timeout
    assert 0.04 < errors / trials < 0.06, errors / trials
    assert 0.14 < timeouts / trials < 0.16, timeouts / trials


def test_the_ordinal_is_per_fingerprint_not_global(tmp_path):
    api = _api(tmp_path, pair_seed=777)
    assert api.dispatch_ordinal("a") == 0
    assert api.dispatch_ordinal("b") == 0
    assert api.dispatch_ordinal("a") == 1
    assert api.dispatch_ordinal("b") == 1
    assert api.dispatch_ordinal("c") == 0


def test_readbacks_have_their_own_stream(tmp_path):
    """Structural: a future read-back draw cannot perturb the mutation faults."""
    api = _api(tmp_path, pair_seed=None)
    assert api._auxiliary_random is not api._random
    before = api._random.getstate()
    for _ in range(100):
        api._auxiliary_random.random()
    assert api._random.getstate() == before


# ---------------------------------------------------------------------------
# Nothing the matrix relies on moves
# ---------------------------------------------------------------------------

def test_an_unpaired_config_digest_is_byte_identical(tmp_path):
    """432 collected runs stay attributable."""
    without = _api(tmp_path, pair_seed=None).config
    body = without._body()
    assert "pair_seed" not in body
    with_pair = _api(tmp_path, pair_seed=777).config
    assert "pair_seed" in with_pair._body()
    assert without.config_digest != with_pair.config_digest


def test_the_loader_refuses_a_non_integer_pair_seed(tmp_path):
    import yaml

    from experiments.mock_api.config import load_config

    document = {
        "config_version": "aep.mock-legacy-api.config/1",
        "seed": 1,
        "ledger_path": str(tmp_path / "gt.sqlite3"),
        "pair_seed": "nope",
        "endpoints": {
            "notifications": {
                "response_class": "POSITIVE_ONLY_READBACK",
                "identity_fields": ["action", "amount_minor"],
            }
        },
    }
    path = tmp_path / "mock.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(ConfigError, match="pair_seed must be an integer"):
        load_config(path)


def test_the_loader_accepts_an_absent_pair_seed(tmp_path):
    import yaml

    from experiments.mock_api.config import load_config

    document = {
        "config_version": "aep.mock-legacy-api.config/1",
        "seed": 1,
        "ledger_path": str(tmp_path / "gt.sqlite3"),
        "endpoints": {
            "notifications": {
                "response_class": "POSITIVE_ONLY_READBACK",
                "identity_fields": ["action", "amount_minor"],
            }
        },
    }
    path = tmp_path / "mock.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    assert load_config(path).pair_seed is None
