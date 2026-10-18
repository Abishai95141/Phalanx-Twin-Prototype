"""M11 events into the real M05 (AD-47) and M09 (AD-44), and M10's ``health.utility`` read by M09.

- ``fcs.channel_fault`` / ``fcs.actuator_fault`` from M11 set and clear the DFCC fault words in M05.
- The AIB cascade template T.CONTAM_LAW (water-contaminated servicing + cold soak -> strut extension
  failure -> false WoW -> FCS ground law): M11 realises the graph edges in the template's windows and sends
  ``fcs.wow_fault`` for both main legs; M05 then selects the GROUND law in flight by its own logic (the last
  edge is a physics edge, so M11 emits nothing for it).
- ``util.fault`` from M11 (generator diode, backup failure, fire-loop short, and their clears) drives M09.
- M10's ``health.utility`` follows M09's ``HEALTH_INDEX``: brake wear passes through as M09's sortie-start
  wear, and a pump at its wear limit leaks more, so M09's compensated pump strokes further.

TEST FIXTURES: the M05 helpers of ``test_fcs_voting`` (synthetic constant flight inputs) and the M09 helpers
of ``test_utilities_support`` (input block); a ``Recorder`` stands in for M05/M09 inside the M11 system.
Sample: one scripted fault or cascade per check (deterministic; the cascade latency draws are fixed)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from test_fcs_voting import base_inputs, make, run

from phalanx.core.events import Event
from phalanx.core.module import ModuleBase, ParamSet
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.dictionary import load_dictionary
from phalanx.faults import FaultConfig, FaultInjector, load_catalogue, load_fault_params, load_graph
from phalanx.fcs.layout import I_CHFLT, I_JAM, I_SERVO, LAW_GROUND, LAW_SCHEDULED, SUBSYSTEMS
from phalanx.health import HealthConfig, HealthModule, load_health_params, sensor_bias_channels
from phalanx.health.layout import AIRFRAME_NAMES
from phalanx.utilities import layout as UL

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
from test_utilities_support import inputs as m09_inputs
from test_utilities_support import module as m09_module
from test_utilities_support import run as m09_run

pytestmark = pytest.mark.integration
D = load_dictionary()
SEC = 10**9
TAIL = "T1"


class Recorder(ModuleBase):  # TEST FIXTURE (module boundary): records the events addressed to it
    version = "0.0.1"
    rate = None

    def __init__(self, id):
        super().__init__(id, ParamSet("rec", {}))
        self.log: list[tuple[int, Event]] = []

    def init(self, params, keys):
        return {}

    def on_event(self, state, event, t):
        self.log.append((int(t), event))
        return state, []


def m11_events(orders, until_s: float, *, physics=False):
    recs = {k: Recorder(k) for k in ("fcs", "util")}
    cfg = FaultConfig(
        load_catalogue(),
        load_graph(),
        {"fcs": "fcs", "utilities": "util"},
        ("IN20-0001",),
        sensor_bias_channels(D),
        realise_physics_edges=physics,
        stochastic=False,
        tail_no=TAIL,
    )
    f = FaultInjector("m11", load_fault_params(), config=cfg, identity={"tail": TAIL})
    sysm = System(
        [f, *recs.values()], [], rng=RngService(5, StreamRegistry()), identity=KeyPath.of(scenario="S")
    )
    w = sysm.inject(sysm.start(), orders)
    w, _ = sysm.run(w, int(until_s * 240) + 2)
    return {k: r.log for k, r in recs.items()}, w.states["m11"], f


def inject(t_s, mode, **kw):
    return Event(round(t_s * SEC), "faults.inject", "m11", {"mode": mode, **kw})


# ---------------------------------------------------------------------------------------------- M05
def test_channel_and_actuator_faults_drive_m05():
    logs, _st11, _ = m11_events(
        [
            inject(1.0, "FM.FCS.CHANNEL_DROPOUT"),
            inject(1.0, "FM.FCS.SERVO_COIL"),
            inject(1.0, "FM.FCS.ACTUATOR_JAM"),
        ],
        8.0,
    )
    kinds = [e.kind for _, e in logs["fcs"]]
    assert kinds == ["fcs.channel_fault", "fcs.actuator_fault", "fcs.actuator_fault", "fcs.channel_fault"]
    mod = make()
    st = mod.init(mod.params, None)
    on = logs["fcs"][:3]
    for t, ev in on:
        st, out = mod.on_event(st, ev, t)
        assert out == [] and int(np.asarray(ev.payload["active"]))
    ch, servo, jam = (ev.payload for _, ev in on)
    c, sub = int(ch["channel"]), int(ch["subsystem"])
    assert sub == SUBSYSTEMS.index("WATCHDOG") and int(st["i"][I_CHFLT + c]) == 1 << sub
    assert int(st["i"][I_SERVO + int(servo["surface"])]) == 1 << int(servo["channel"])
    assert int(st["i"][I_JAM + int(jam["surface"])]) == 1
    t_clr, clr = logs["fcs"][3]  # the 5 s transient clears: channel fault inactive
    assert (t_clr - on[0][0]) == 5 * SEC and not int(np.asarray(clr.payload["active"]))
    st, _ = mod.on_event(st, clr, t_clr)
    assert int(st["i"][I_CHFLT + c]) == 0


def test_contamination_cascade_reaches_m05_ground_law():
    """T.CONTAM_LAW: the false WoW arrives inside the template window (1,800-3,001 s after the contaminated
    servicing manifests, cold soak given), and M05 selects GROUND law in flight from it."""
    logs, _st11, f = m11_events([inject(10.0, "FM.HYD.WATER_CONTAMINATION", cold_soak=1.0)], 3100.0)
    wow = [(t, e) for t, e in logs["fcs"] if e.kind == "fcs.wow_fault"]
    assert sorted(int(e.payload["leg"]) for _, e in wow) == [1, 2]
    dt = (wow[0][0] - 10 * SEC) / SEC
    lo, hi = f.config.graph.templates["T.CONTAM_LAW"].windows_s["lg.false_wow"]
    assert lo <= dt <= hi
    mod = make()  # in flight, SCHEDULED law
    st = mod.init(mod.params, None)
    st, out = run(mod, st, base_inputs(30))
    assert out["law_state"][-1] == LAW_SCHEDULED
    for t, ev in wow:
        st, _ = mod.on_event(st, ev, t)
    st, out = run(mod, st, base_inputs(30), 30)
    assert out["law_state"][-1] == LAW_GROUND
    # without the cold-soak condition the AND gate holds: no false WoW
    logs2, _, _ = m11_events([inject(10.0, "FM.HYD.WATER_CONTAMINATION")], 3100.0)
    assert not [e for _, e in logs2["fcs"] if e.kind == "fcs.wow_fault"]


# ---------------------------------------------------------------------------------------------- M09
def test_util_fault_events_drive_m09():
    logs, _, _ = m11_events(
        [
            inject(1.0, "FM.ELEC.GEN_DIODE", severity=1.0, covered=True),
            inject(1.0, "FM.ELEC.BACKUP_FAIL"),
            inject(1.0, "FM.FIRE.LOOP_SHORT"),
            Event(3 * SEC, "faults.clear", "m11", {"instance": 0}),
            Event(3 * SEC, "faults.clear", "m11", {"instance": 2}),
        ],
        4.0,
    )
    modes = [str(e.payload["mode"]) for _, e in logs["util"]]
    assert modes == ["gen_fail", "bk_fail", "fire_loop_short", "gen_restore", "fire_loop_ok"]
    assert all(str(e.payload["tail"]) == TAIL and e.kind == "util.fault" for _, e in logs["util"])
    m, st = m09_module()
    seen = []
    for t, ev in logs["util"]:
        st, _ = m.on_event(st, Event(t, "util.fault", "util", {"mode": str(ev.payload["mode"])}), t)
        i = st["i"]
        seen.append((int(i[UL.I_GEN_FAULT]), int(i[UL.I_BK_FAULT]), int(i[UL.I_FIRE_DET])))
    assert seen == [(1, 0, 0), (1, 1, 0), (1, 1, 2), (0, 1, 2), (0, 1, 0)]


def test_m09_reads_m10_utility_vector():
    """M10's 23-entry vector in M09's index map: brake wear passes through as M09's sortie-start wear, and a
    pump at its wear limit (excess leakage 0.75) makes M09's compensated pump stroke further."""
    h = HealthModule("m10", load_health_params(), config=HealthConfig(("E1",), sensor_bias_channels(D)))
    sysm = System([h], [], rng=RngService(9, StreamRegistry()), identity=KeyPath.of(scenario="S", tail=TAIL))
    st10 = dict(sysm.start().states["m10"])
    air = np.array(st10["air"], copy=True)
    air[AIRFRAME_NAMES.index("brake_wear_l")] = 0.3
    air[AIRFRAME_NAMES.index("hyd1_pump_wear")] = 1.0
    st10["air"] = air
    hv = h.utility_vector(st10)
    assert hv.shape == (UL.N_HEALTH,)
    assert hv[UL.H_BRAKE_WEAR] == 0.3 and hv[UL.H_PUMP_LEAK] == pytest.approx(0.75)
    m, st = m09_module()
    st_h, _out_h = m09_run(m, st, m09_inputs(2400, health=np.zeros(UL.N_HEALTH), demand=2.0e-4))
    st_w, out_w = m09_run(m, st, m09_inputs(2400, health=hv, demand=2.0e-4))
    assert out_w["brake_wear"][-1][0] == pytest.approx(0.3)
    assert m.truth_view(st_w, hv)["hyd_swash"][0] > m.truth_view(st_h)["hyd_swash"][0]
