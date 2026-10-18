"""MF4d (E1-MF): realised usage gates, with explicit targets and the exact W2.1 harness entry point.

E1 found the realised Nz / engine-cycle gate stubs had no target and imported
`phalanx.integration.telemetry_fleet_run`, which no brief creates, so the tripwire could never fire. They now
name one entry point, which the W2.1 brief tells W2.1 to implement (`HARNESS`):

    phalanx.integration.realised_usage.realised_fleet_stats(
        fleet: phalanx.scenario.config.FleetScenario,
        start: datetime.date,
        days: int,
        *,
        scenario: str,            # RNG scenario key (the plan-level gates use "gate")
        root: int,                # root seed
        max_sorties: int | None,  # fly only the first n planned sorties (sample size), in plan order
    ) -> phalanx.scenario.gates.FleetStats

It flies the M02 plan in telemetry mode through the W2.1 truth loop (M02-M14) and returns the fleet
statistics computed from the **realised** counts (M14 `usage.counters`: LUI Type III, TAC; the Nz
level-crossing counters on the realised `af.nz`), in the plan-level `FleetStats` form (same gates).

Targets (`docs/behavioural_targets.md`, "Tejas usage gates"; the plan-level bands of `scenario.gates`):
- Nz spectrum within +/-30 % of the F-16 operational curve [TRANSFER: AGARD R-815 via report §4]: 5 g
  7,000 and 7 g 1,300 exceedances per 1,000 h. The 9 g point (10 per 1,000 h) needs ~10^4 FH: not tested.
- Type III cycles 5 +/- 2 per FH; TAC 2.2-3.3 per FH.

Sample (stated before running; W2.1 runs it): the first n = 48 planned sorties of the two-squadron fleet from
2026-01-05 under scenario key 'gate' (about 40 FH). Nz: the 7 g rate (1.3/FH) gives ~52 counts, a Poisson
relative SE of ~14 %, so the +/-30 % band is about 2 SE; the 5 g rate gives ~280 counts (SE ~6 %). Cycles:
with a per-flight CV of ~0.5 the relative SE of a per-FH rate is ~0.5/sqrt(48) = 7 %, inside the TAC band's
+/-20 % and Type III's +/-40 %.

W2.1a built the harness (`test_realised_usage_harness_is_built` now passes in `make check`). The gate tests
(`slow`, `make test`) are strict xfails on the two specific blockers the harness raises instead of returning
plan values (W2.1a report, measured on the first gate sorties):
- `SortieAborted`: the integrated aircraft does not complete a sortie yet (measured on the diverse gate
  sorties after the W2.2 merge and the W2.1a take-off fixes). The take-off, climb-out and cruise fly; a 4 g
  MIL turn primitive overshoots its heading and reverses into a departure (M04 guidance, A-W2.1-10; M05/M06
  departure resistance), and on three of four sorties the idle-to-MIL take-off acceleration runs down on
  M08's acceleration schedule (M07/M08, W2.1b);
- `ObservedUsageUnavailable`: M14's LUI counters need `ENG.PLA.V`, which no module produces (M08
  `RECORDED_MISSING`).
Any other error (or a failed gate) is a test failure; the markers go when the blockers are fixed.
"""

from __future__ import annotations

import datetime as dt
import importlib
import inspect
import sys
from pathlib import Path

import pytest

from phalanx.scenario.config import load_fleet_scenario
from phalanx.scenario.gates import F16_NZ_PER_1000H, PLAN_GATES

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ("phalanx.integration.realised_usage", "realised_fleet_stats")
FLEET = ROOT / "configs" / "scenarios" / "tejas_two_squadrons.yaml"
START = dt.date(2026, 1, 5)
N_SORTIES = 48
#: docs/behavioural_targets.md "Tejas usage gates" (explicit here, so a later change of the plan-level bands
#: does not silently move the realised targets)
TARGETS = {
    "nz5_per_1000h": (0.7 * 7000.0, 1.3 * 7000.0),
    "nz7_per_1000h": (0.7 * 1300.0, 1.3 * 1300.0),
    "type3_per_fh": (3.0, 7.0),
    "tac_per_fh": (2.2, 3.3),
}
REASON = (
    "W2.1a measured: the integrated aircraft does not complete a sortie (SortieAborted: a MIL turn primitive "
    "overshoots its heading and departs, M04 A-W2.1-10 with M05/M06 departure resistance; the idle-to-MIL "
    "take-off acceleration runs down on M08's acceleration schedule, M07/M08 W2.1b) and M14's LUI counters "
    "lack ENG.PLA.V (ObservedUsageUnavailable; M08 RECORDED_MISSING)"
)


def _blockers():
    from phalanx.integration.realised_usage import ObservedUsageUnavailable
    from phalanx.integration.sortie import SortieAborted

    return (SortieAborted, ObservedUsageUnavailable)


class HarnessMissing(ImportError):
    """The W2.1 realised-usage entry point does not exist yet (and nothing else went wrong)."""


def harness():
    """The entry point, or HarnessMissing if (only) the entry point is absent."""
    mod, name = HARNESS
    try:
        m = importlib.import_module(mod)
    except ModuleNotFoundError as e:
        if e.name in ("phalanx.integration", mod):
            raise HarnessMissing(f"{mod} does not exist") from e
        raise  # the harness exists but one of its own imports is missing: a real failure
    if not hasattr(m, name):
        raise HarnessMissing(f"{mod}.{name} does not exist")
    return getattr(m, name)


def _realised():
    run = harness()
    return run(load_fleet_scenario(FLEET), START, 60, scenario="gate", root=0xA5, max_sorties=N_SORTIES)


@pytest.mark.unit
def test_targets_are_the_behavioural_targets():
    """The realised targets equal the plan-level gates and the F-16 curve they come from."""
    assert F16_NZ_PER_1000H[5.0] == 7000.0 and F16_NZ_PER_1000H[7.0] == 1300.0
    for k, band in TARGETS.items():
        assert PLAN_GATES[k] == pytest.approx(band), k


@pytest.mark.unit
def test_harness_guard_is_scoped_to_the_missing_entry_point(monkeypatch):
    """Negative control for the xfail scope: HarnessMissing only for an absent module or function; a harness
    whose own import fails on another missing module raises that real error (the test then fails)."""
    me = sys.modules[__name__]
    assert callable(harness())  # W2.1a built it
    monkeypatch.setattr(me, "HARNESS", ("phalanx.no_such_package", "realised_fleet_stats"))
    with pytest.raises(HarnessMissing):  # the module does not exist
        harness()
    monkeypatch.setattr(me, "HARNESS", ("phalanx.scenario.gates", "realised_fleet_stats"))
    with pytest.raises(HarnessMissing):  # the module exists, the function does not
        harness()
    monkeypatch.setattr(me, "HARNESS", HARNESS)

    def broken_import(
        name,
    ):  # TEST FIXTURE at the importlib boundary: the harness's own dependency is missing
        raise ModuleNotFoundError(f"No module named {name + '_dependency'!r}", name=name + "_dependency")

    monkeypatch.setattr(importlib, "import_module", broken_import)
    with pytest.raises(ModuleNotFoundError) as e:
        harness()
    assert not isinstance(e.value, HarnessMissing)


@pytest.mark.statistical
def test_realised_usage_harness_is_built():
    """Tripwire in `make check`: the entry point exists with the agreed keyword-only arguments."""
    params = inspect.signature(harness()).parameters
    assert list(params)[:3] == ["fleet", "start", "days"]
    assert {"scenario", "root", "max_sorties"} <= set(params)


@pytest.mark.statistical
@pytest.mark.slow
@pytest.mark.xfail(strict=True, raises=_blockers(), reason=REASON)
def test_realised_nz_exceedance_spectrum_within_30pct_of_f16():
    """Realised 5 g and 7 g exceedances per 1,000 FH within +/-30 % of the F-16 curve (n = 48 sorties)."""
    st = _realised()
    assert st.n_sorties == N_SORTIES
    for k in ("nz5_per_1000h", "nz7_per_1000h"):
        lo, hi = TARGETS[k]
        assert lo <= getattr(st, k) <= hi, (k, getattr(st, k), TARGETS[k])


@pytest.mark.statistical
@pytest.mark.slow
@pytest.mark.xfail(strict=True, raises=_blockers(), reason=REASON)
def test_realised_engine_cycle_gates():
    """Realised Type III cycles 5 +/- 2 per FH and TAC 2.2-3.3 per FH (n = 48 sorties)."""
    st = _realised()
    assert st.n_sorties == N_SORTIES
    for k in ("type3_per_fh", "tac_per_fh"):
        lo, hi = TARGETS[k]
        assert lo <= getattr(st, k) <= hi, (k, getattr(st, k), TARGETS[k])
