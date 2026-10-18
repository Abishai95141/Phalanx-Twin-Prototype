"""A7: "controller saw = recorded" in the integrated loop (W1_interfaces.md §3; AD-38, AD-42).

For every in-loop lane of the FADEC (21 channels, FADEC clock 60 Hz) and the DFCC (89 channels incl. the ADC
air data, DFCC clock 80 Hz), the SI value the controller's input port carried at each acquisition sample
equals ``Dictionary.eu_to_si`` of the CIR value the M13 recorder wrote for the same channel and absolute
sample index, **bitwise**; and the sample indices and instants agree. The recorder runs outside the scheduler
on the M12 trace (PD-W2.1a-2), so this is the end-to-end check that both entry points of M13 share one path.

Sample: the first gate sortie from post-start idle, 5 s (n = 1; about 300 FADEC and 400 DFCC samples per
channel, 37,000 compared values). A negative control perturbs one recorded value by one ulp and shows the
comparison fails.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.acquisition.module import lane_port
from phalanx.integration.plans import gate_sorties
from phalanx.integration.sortie import SortieRunner
from phalanx.integration.system import SortieSpec, build_sortie_system

pytestmark = pytest.mark.integration
SECONDS = 5


@pytest.fixture(scope="module")
def run():
    ss = build_sortie_system(SortieSpec(plan=gate_sorties()[0], scenario="gate", root=0xA5, fused=True))
    lanes = {mid: ss.modules[mid].acq.channels for mid in ("acq_fadec", "acq_dfcc")}
    ports = []
    for mid, chans in lanes.items():
        for cid in chans:
            p = lane_port(cid)
            ports += [f"{mid}.{p}", f"{mid}.{p}_t", f"{mid}.{p}_n", f"{mid}.{p}_first"]
    chans = [c for cs in lanes.values() for c in cs]
    r = SortieRunner(ss, cir_channels=chans, feed_monitor=False, keep_cir=True, record=ports)
    st = r.begin()
    st, outs = r.run(st, SECONDS * 240)
    return ss, lanes, outs


def _lane_samples(outs, mid: str, cid: str):
    p = lane_port(cid)
    idx, ts, vs = [], [], []
    for c in outs:
        P = c.trace.ports
        v, t, n, first = P[f"{mid}.{p}"], P[f"{mid}.{p}_t"], P[f"{mid}.{p}_n"], P[f"{mid}.{p}_first"]
        for k in range(n.shape[0]):
            for s in range(int(n[k])):
                idx.append(int(first[k]) + s)
                ts.append(int(t[k, s]))
                vs.append(float(v[k, s]))
    return np.array(idx, np.int64), np.array(ts, np.int64), np.array(vs)


def _cir_samples(ss, outs, cid: str):
    loc = ss.dictionary.contract_location(cid)
    idx, ts, vs = [], [], []
    for c in outs:
        tab = c.cir.table
        pid = np.array(tab.column("param_id").to_pylist())
        lane = np.array([x or "" for x in tab.column("lane").to_pylist()])
        sel = (pid == loc["param_id"]) & (lane == (loc["lane"] or ""))
        idx.append(tab.column("sample_index").to_numpy()[sel])
        ts.append(tab.column("t_sample").to_numpy()[sel] - ss.epoch_utc_ns)
        vs.append(tab.column("value").to_numpy()[sel])
    return np.concatenate(idx), np.concatenate(ts), np.concatenate(vs)


def test_controller_lane_values_equal_recorded_cir_bitwise(run):
    ss, lanes, outs = run
    n_cmp = 0
    for mid, chans in lanes.items():
        for cid in chans:
            li, lt, lv = _lane_samples(outs, mid, cid)
            ci, ct, cv = _cir_samples(ss, outs, cid)
            assert li.size > 0 and np.array_equal(li, ci), cid
            assert np.array_equal(lt, ct), cid
            si = np.asarray(ss.dictionary.eu_to_si(cid, cv), dtype=np.float64)
            assert lv.tobytes() == si.tobytes(), (cid, np.flatnonzero(lv != si)[:5])
            n_cmp += li.size
    # FADEC lanes: 21 + ENG.AB_LIT (UV flame detector) + ENG.FUEL_INLET_T since the W2.2 merges
    assert len(lanes["acq_fadec"]) == 23 and len(lanes["acq_dfcc"]) == 89
    assert n_cmp > 30_000


def test_negative_control_one_ulp_is_detected(run):
    ss, lanes, outs = run
    cid = lanes["acq_fadec"][0]
    _li, _lt, lv = _lane_samples(outs, "acq_fadec", cid)
    _ci, _ct, cv = _cir_samples(ss, outs, cid)
    cv = cv.copy()
    cv[len(cv) // 2] = np.nextafter(cv[len(cv) // 2], np.inf)
    si = np.asarray(ss.dictionary.eu_to_si(cid, cv), dtype=np.float64)
    assert lv.tobytes() != si.tobytes()
