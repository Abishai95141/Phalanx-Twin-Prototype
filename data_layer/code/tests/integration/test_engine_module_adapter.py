"""MF4a (E1-MF): the M07 module adapter. `EngineModule` ports equal the kernel driven by *name*.

E1 mutants that survived: m02 (M07 reads the `env.w_engine` columns reversed) and m19 (M07 publishes
`eng.t5` in degC on a K port). Every existing M07 test drove the kernel through `sim.input_block` /
`simulate` (by name) or fed the module zeros in most `w_engine` columns, so the adapter that packs ports into
the kernel input vector (`EngineModule._pack`) and unpacks the kernel outputs into ports (`_ports_from`) was
never compared with anything.

Here the module is driven with inputs that differ in **every column** of `w_engine` and `health` (distinct
value and frequency per column and per engine) and in every other input port, and its ports are compared,
bitwise, with:

1. the same kernel driven through `sim.simulate` from inputs built **by name**: each `env.w_engine` column j
   goes to the kernel input `w_<M03 ENGINE_CHANNELS[j]>` (the producer's names; catalogue note AD-32/AD-46),
   each `health.engine` column j to `h_<M10 ENGINE_DELTAS[j]>`, and the other ports to the kernel input of the
   same meaning (W1_interfaces.md M07, M08 `vg_cmd` = [IGV, VSV]);
2. the kernel's own station diagnostics (`record_aux`: t2, t25, t3, t5, p2, ps3, p5, w2, fn, ...), which are
   computed before the output row is assembled, so a unit or index slip in the output assembly is caught even
   when the reference shares it.

Negative controls in the test itself: the by-name reference built with the columns reversed (m02's packing)
and a degC t5 (m19) both differ from the module, so each comparison can fail.

Sample: one window of 120 ticks (0.5 s) from the design steady state, n_engines 1 and 2 (the minimum that
shows per-engine packing); AB off (no light-off draw), so the module needs no RNG binding.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.engine.design import build_engine_model
from phalanx.engine.layout import NUI, U_NAMES, U_WFM_D, UI_ABEN, UI_IGN, Y_NAMES, YI_AB, YI_FLAME, A
from phalanx.engine.module import EngineModule
from phalanx.engine.sim import simulate, state_from_x
from phalanx.environment.disturbances import ENGINE_CHANNELS, N_W_ENGINE
from phalanx.health.layout import ENGINE_DELTAS

pytestmark = pytest.mark.integration
L = 120
DT = 1.0 / 240.0
T_NS = (np.arange(L, dtype=np.int64) * 10**9) // 240
#: kernel input of each scalar/per-engine port (W1_interfaces.md M07 inputs); vg_cmd is [IGV, VSV]
PORT_INPUT = {
    "wf_cmd": "wf_cmd",
    "wf_ab_cmd": "wf_ab_cmd",
    "a8_cmd": "a8_cmd",
    "t_s": "t_s",
    "p_s": "p_s",
    "q_spec": "q_spec",
    "mach": "mach",
    "bleed_extract": "bleed_extract",
    "pto_power": "pto_power",
    "fuel_inlet_t": "t_fuel",
}
#: port -> kernel station diagnostic that must equal it (the output row is assembled from these)
AUX_OF = {
    "t2": "t2",
    "t25": "t25",
    "t3": "t3",
    "t5": "t5",
    "p2": "p2",
    "ps3": "ps3",
    "p5": "p5",
    "w2": "w2",
    "thrust": "fn",
    "oil_p": "oil_p",
    "bleed_t3": "t3",
}


@pytest.fixture(scope="module")
def model():
    return build_engine_model()


def _inputs(eng: EngineModule) -> dict[str, np.ndarray]:
    """Port inputs over the window: every column and engine distinct (value and frequency)."""
    e = eng.n_engines
    u0 = eng._init_u
    ts = T_NS * 1e-9
    k = np.arange(e)[None, :]

    def wave(base, amp, f):
        return base + amp * np.sin(2 * np.pi * f * ts[:, None] + 0.3 * k)

    w = np.zeros((L, e, N_W_ENGINE))
    for j in range(N_W_ENGINE):  # distinct sign, size and frequency per column, offset per engine
        w[:, :, j] = (-1) ** j * 0.002 * (j + 1) * (1.0 + 0.5 * k) + 0.001 * np.sin(
            2 * np.pi * (3 + 2 * j) * ts
        )[:, None]
    h = np.zeros((L, e, len(ENGINE_DELTAS)))
    for j in range(len(ENGINE_DELTAS)):
        h[:, :, j] = -0.001 * (j + 1) * (1.0 + 0.25 * k)
    return {
        "wf_cmd": wave(u0[U_NAMES.index("wf_cmd")], 0.03, 1.1),
        "wf_ab_cmd": np.zeros((L, e)),
        "a8_cmd": wave(u0[U_NAMES.index("a8_cmd")], 0.002, 0.7),
        "vg_cmd": np.stack(
            [
                wave(u0[U_NAMES.index("vg_igv_cmd")], 0.01, 0.9),
                wave(u0[U_NAMES.index("vg_vsv_cmd")], -0.02, 1.7),
            ],
            axis=-1,
        ),
        "ignition": np.zeros((L, e), np.int64),
        "ab_enable": np.zeros((L, e), np.int64),
        "t_s": 288.15 + 1.5 * np.sin(2 * np.pi * 0.5 * ts),
        "p_s": 101325.0 - 300.0 * np.sin(2 * np.pi * 0.3 * ts),
        "q_spec": np.full(L, 0.003),
        "mach": 0.05 + 0.02 * ts,
        "w_engine": w,
        "bleed_extract": wave(0.25, 0.05, 2.3),
        "pto_power": wave(15e3, 3e3, 1.9),
        "fuel_inlet_t": wave(u0[U_NAMES.index("t_fuel")], 2.0, 0.4),
        "health": h,
    }


def _by_name(eng: EngineModule, ins: dict, *, w_order=None, h_order=None) -> tuple[np.ndarray, np.ndarray]:
    """Kernel inputs (L, E, NU) built by NAME from the ports (the reference of the adapter)."""
    e = eng.n_engines
    u = np.broadcast_to(eng._init_u, (L, e, len(U_NAMES))).copy()
    for port, name in PORT_INPUT.items():
        v = np.asarray(ins[port], float)
        u[:, :, U_NAMES.index(name)] = v if v.ndim == 2 else v[:, None]
    u[:, :, U_NAMES.index("vg_igv_cmd")] = ins["vg_cmd"][..., 0]
    u[:, :, U_NAMES.index("vg_vsv_cmd")] = ins["vg_cmd"][..., 1]
    cols = ENGINE_CHANNELS[:N_W_ENGINE] if w_order is None else w_order
    for j, name in enumerate(cols):  # column j of env.w_engine is M03's channel j
        u[:, :, U_NAMES.index(f"w_{name}")] = ins["w_engine"][:, :, j]
    for j, name in enumerate(ENGINE_DELTAS if h_order is None else h_order):  # M10's column j
        u[:, :, U_NAMES.index(f"h_{name}")] = ins["health"][:, :, j]
    ui = np.zeros((L, e, NUI), np.int64)
    ui[:, :, UI_IGN] = ins["ignition"]
    ui[:, :, UI_ABEN] = ins["ab_enable"]
    return u, ui


def _module_run(eng: EngineModule, ins: dict):
    st = eng.init(eng.params, None)
    return eng.step_block(st, ins, T_NS, DT)[1]


def _reference(model, eng: EngineModule, u, ui):
    st = state_from_x(model, eng._init_x, n_engines=eng.n_engines, w_fm=eng._init_u[U_WFM_D])
    return simulate(model, st, u, ui, record_aux=True)


def _compare(out: dict, r) -> list[str]:
    bad = []
    for name in (*(n for n in Y_NAMES if not n.startswith("vib_")),):
        if not np.array_equal(out[name], r.y[:, :, Y_NAMES.index(name)]):
            bad.append(name)
    vib = r.y[:, :, [Y_NAMES.index(n) for n in ("vib_n1", "vib_n2", "vib_bb")]]
    if not np.array_equal(out["vib_src"], vib):
        bad.append("vib_src")
    if not np.array_equal(out["ab_state"], r.yi[:, :, YI_AB]):
        bad.append("ab_state")
    if not np.array_equal(out["flame_state"], r.yi[:, :, YI_FLAME]):
        bad.append("flame_state")
    return bad


@pytest.mark.parametrize("n_engines", [1, 2])
def test_module_ports_equal_the_kernel_driven_by_name(model, n_engines):
    """Every M07 output port equals the by-name kernel output bitwise, with distinct per-column disturbances
    and health deltas (kills m02-class packing slips and m19-class unpacking slips)."""
    eng = EngineModule("eng", model, n_engines=n_engines)
    ins = _inputs(eng)
    assert {p.name for p in eng.ports_in} == set(ins)
    out = _module_run(eng, ins)
    ref = _reference(model, eng, *_by_name(eng, ins))
    assert _compare(out, ref) == []
    # the window exercises the columns: each one moves the outputs (otherwise a permutation could hide)
    assert np.ptp(out["n2"]) > 0 and np.ptp(out["t5"]) > 0


@pytest.mark.parametrize("n_engines", [1, 2])
def test_station_ports_equal_the_kernel_diagnostics(model, n_engines):
    """Station ports carry the kernel's own station values (SI): t5 is the T56 station temperature in K, etc.
    The diagnostics are computed before the output row is assembled, so this catches an assembly slip that a
    shared reference would also carry."""
    eng = EngineModule("eng", model, n_engines=n_engines)
    ins = _inputs(eng)
    out = _module_run(eng, ins)
    ref = _reference(model, eng, *_by_name(eng, ins))
    for port, aux in AUX_OF.items():
        np.testing.assert_array_equal(out[port], ref.aux[:, :, A[aux]], err_msg=port)
    assert np.all(out["t5"] > out["t2"]) and np.all(out["t5"] > 600.0)  # a running engine's T56, in K


def test_comparisons_fail_on_m02_and_m19_shaped_slips(model):
    """Negative control: a reference with the env.w_engine (or health) columns reversed, as m02 packed them,
    and a t5 shifted to degC, as m19 published it, each differ from the module ports."""
    eng = EngineModule("eng", model, n_engines=2)
    ins = _inputs(eng)
    out = _module_run(eng, ins)
    rev_w = tuple(reversed(ENGINE_CHANNELS[:N_W_ENGINE]))
    ref_w = _reference(model, eng, *_by_name(eng, ins, w_order=rev_w))
    assert {"n1", "n2", "t5", "wf"} <= set(_compare(out, ref_w))
    ref_h = _reference(model, eng, *_by_name(eng, ins, h_order=tuple(reversed(ENGINE_DELTAS))))
    assert {"n1", "n2", "t5"} <= set(_compare(out, ref_h))
    degc = dict(out, t5=out["t5"] - 273.15)
    ref = _reference(model, eng, *_by_name(eng, ins))
    assert _compare(degc, ref) == ["t5"]
    assert not np.array_equal(degc["t5"], ref.aux[:, :, A["t5"]])
