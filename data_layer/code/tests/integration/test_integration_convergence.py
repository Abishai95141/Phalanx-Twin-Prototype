"""A3: step-halving convergence of the truth plant on a minimal integrated segment (480 Hz vs 240 Hz truth).

The core runs the truth loop at the fixed 240 Hz grid (AD-35, ``TRUTH_HZ``), so the step-halving study is done
on the **plant modules** of the integrated loop (M06 airframe, M07 engine, M09 utilities): their inputs as the
integrated System delivered them (every connection, delays included) are recorded at 240 Hz, then each module
is re-integrated from the same initial state at 240 Hz (must reproduce the integrated outputs bitwise: the
replay is exact), at 480 Hz and at 960 Hz with the inputs held per 240 Hz frame (zero-order hold, as the loop
holds them). M07 at 480/960 Hz uses the same model with ``dt`` and the fuel transport-delay length in ticks
scaled (the delay in seconds is unchanged; the delay line starts in equilibrium at the trim). Its
discrete-process timers count ticks; none fires in this segment (no AB, surge or flame event).

Segment: the run-up of the first gate sortie (window start ``RUNUP``: engine at post-start idle, aircraft
parked; PLA to MIL at t = 0): the engine accelerates and the aircraft starts to roll. 3 s (720 steps), n = 1.

**Criterion, per output port, reported per channel class.** The 240 Hz truth-step error is estimated as
max |y(240) - y(960)| over the segment. Tolerance: one recorder count of the dictionary channel that records
the port (``Dictionary.eu_to_si`` of its ``recorder_lsb``: the step error is then invisible in recorded data;
for the attitude quaternion half the INS pitch count, |dq| = |dtheta| / 2); ports no channel records: 1e-3 of
the port's peak magnitude in the segment. Convergence: where the step error is resolvable (e(240,480) above
1 % of the tolerance), it must fall when the step halves, e(480,960) < e(240,480). Below that the differences
are rounding-level (M06 integrates RK4 with ground sub-steps; its kinematic differences are 1e-8 of scale).

Measured (W2.1a, n = 1 segment): every class is within tolerance and convergent except **M07 N1, T5 and
thrust**, whose 240 Hz errors are 1.16 and 2.87 recorder counts and 1.34x the 1e-3 relative tolerance (10.9 N
of 8.1 kN) in the acceleration. Order 1, from M07's fuel transport-delay line: it holds the metered flow once
per 240 Hz tick and the combustor reads that staircase for every sub-step of the tick. Re-integrated without
the delay line, the engine errors fall by 3-4 orders (e(240,480): N1 0.33 -> 6e-5 rad/s, T5 0.94 -> 0.002 K,
thrust 7.2 -> 0.009 N). Strict xfail, reported to W2.1b (interpolate the delay line within the tick).
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from phalanx.integration.plans import gate_sorties
from phalanx.integration.system import SortieSpec, build_sortie_system

pytestmark = pytest.mark.integration
N = 720
RESOLVABLE = 0.01  # of the tolerance
REL_UNRECORDED = 1e-3  # of the port's peak magnitude
#: module -> port -> (channel class, recording channel or None, divisor of the channel's SI count)
PORTS = {
    "af": {
        "vel_ned": ("kinematics: velocity", "NAV.INS.VN", 1.0),
        "alt": ("kinematics: position", "NAV.INS.ALT", 1.0),
        "quat": ("kinematics: attitude", "NAV.INS.PITCH", 2.0),
        "omega_body": ("kinematics: rates", "NAV.INS.BODY_RATES.P_NB", 1.0),
        "f_spec_body": ("kinematics: specific force", "NAV.INS.ACCEL.X", 1.0),
    },
    "eng": {
        "n1": ("engine: spool speeds", "ENG.N1.V", 1.0),
        "n2": ("engine: spool speeds", "ENG.N2.V", 1.0),
        "t5": ("engine: temperatures", "ENG.T5", 1.0),
        "t3": ("engine: temperatures", None, 1.0),
        "ps3": ("engine: pressures", "ENG.PS3.V", 1.0),
        "wf": ("engine: flows", "ENG.WFM", 1.0),
        "thrust": ("engine: thrust", None, 1.0),
    },
    "util": {
        "hyd_p": ("utilities: pressures", "HYD.SYS1.P", 1.0),
        "fuel_mass": ("utilities: fuel", "FUEL.QTY.TANK.F1", 1.0),
        "hyd_t": ("utilities: temperatures", "HYD.SYS1.T", 1.0),
        "mass": ("utilities: mass properties", None, 1.0),
    },
}
#: the measured M07 transport-delay items (strict xfail; W2.1b)
M07_DELAY_LINE = ("eng.n1", "eng.t5", "eng.thrust")
M07_REASON = (
    "W2.1a measured: M07's fuel transport-delay line is held per 240 Hz tick (first order in dt): N1, T5 and "
    "thrust 240 Hz truth-step errors 1.16, 2.87 and 1.34 tolerances in the run-up; without the delay line "
    "3-4 orders smaller. W2.1b: interpolate the delay line within the tick"
)


def _inputs_seen(ss, w0, tr, mid: str) -> dict[str, np.ndarray]:
    """Input sequences of ``mid`` as the System delivered them (delayed edges: previous step's output)."""
    out = {}
    for c in ss.connections:
        dm, dp = c.dst.rsplit(".", 1)
        if dm != mid:
            continue
        seq = tr.ports[c.src]
        if c.delayed:
            seq = np.concatenate([np.asarray(w0.held[c.src])[None], seq[:-1]])
        out[dp] = seq
    return out


def _engine_at(mod, rate: int):
    """M07 with the truth step 1/rate (transport delay length in ticks scaled to keep its seconds)."""
    from phalanx.engine.kernel import engine_kernel

    m = mod.model
    f = rate // 240
    return replace(m, dt=m.dt / f, n_delay=m.n_delay * f), engine_kernel


def _replay(ss, mid: str, state0, inputs: dict[str, np.ndarray], rate: int):
    """Outputs of ``mid`` re-integrated at ``rate`` Hz with ZOH inputs; sampled at the 240 Hz instants."""
    mod = ss.modules[mid]
    f = rate // 240
    ins = {k: np.repeat(v, f, axis=0) for k, v in inputs.items()}
    n = next(iter(ins.values())).shape[0]
    t = (np.arange(n, dtype=np.int64) * 1_000_000_000) // rate
    if mid != "eng":
        _st, out = mod.step_block(state0, ins, t, 1.0 / rate)
        return {k: np.asarray(v)[f - 1 :: f] for k, v in out.items()}
    from phalanx.engine.layout import I_BUFPOS
    from phalanx.engine.module import _ports_from

    model, kern = _engine_at(mod, rate)
    buf0 = np.asarray(state0["buf"])
    assert np.all(buf0 == buf0[:, :1]), "the delay line must start in equilibrium"
    buf = np.repeat(buf0, f, axis=1)
    i0 = np.array(state0["i"], copy=True)
    i0[:, I_BUFPOS] = 0
    u, ui = mod._pack(ins, n)
    z = np.zeros((mod.n_engines, n + 1))
    _f, _i, _b, y, yi, _ = kern(state0["f"], i0, buf, model.p, model.tables, u, ui, z, model.dt, model.n_sub,
                                model.n_delay, False)  # fmt: skip
    out = _ports_from(y, yi, None)
    return {k: np.asarray(v)[f - 1 :: f] for k, v in out.items()}


@pytest.fixture(scope="module")
def study():
    """Per port: (class, e(240,480), e(480,960), e(240,960), tolerance, replay exact)."""
    ss = build_sortie_system(
        SortieSpec(plan=gate_sorties()[0], scenario="gate", root=0xA5, start_phase="RUNUP", fused=True)
    )
    w0 = ss.system.inject(ss.start(), ss.bootstrap_events())
    _, tr = ss.system.run(w0, N, record=ss.system.output_ports())
    d = ss.dictionary
    rows = {}
    for mid, ports in PORTS.items():
        ins = _inputs_seen(ss, w0, tr, mid)
        state0 = w0.states[mid]
        y = {r: _replay(ss, mid, state0, ins, r) for r in (240, 480, 960)}
        for p, (cls, cid, div) in ports.items():
            name = f"{mid}.{p}"
            a, b, c = (np.asarray(y[r][p], dtype=np.float64) for r in (240, 480, 960))
            got = np.ascontiguousarray(tr.ports[name])
            r240 = np.ascontiguousarray(y[240][p]).reshape(got.shape)
            exact = r240.dtype == got.dtype and r240.tobytes() == got.tobytes()
            if cid is None:
                tol = REL_UNRECORDED * float(np.max(np.abs(a)))
            else:
                lsb = float(d.channel(cid)["recorder_lsb"])
                tol = float(d.eu_to_si(cid, lsb) - d.eu_to_si(cid, 0.0)) / div
            e12, e24, e14 = (float(np.max(np.abs(u - v))) for u, v in ((a, b), (b, c), (a, c)))
            rows[name] = (cls, e12, e24, e14, tol, exact)
    lines = [f"{'port':16s} {'class':28s} {'e(240,480)':>10s} {'e(480,960)':>10s} {'e(240,960)':>10s} "
             f"{'tolerance':>10s} {'counts':>7s} {'order':>6s}"]  # fmt: skip
    for name, (cls, e12, e24, e14, tol, _x) in sorted(rows.items(), key=lambda kv: kv[1][0]):
        order = np.log2(e12 / e24) if e12 > 0 and e24 > 0 else float("nan")
        lines.append(f"{name:16s} {cls:28s} {e12:10.3e} {e24:10.3e} {e14:10.3e} {tol:10.3e} {e14 / tol:7.3f} "
                     f"{order:6.2f}")  # fmt: skip
    print("\nA3 step halving, run-up segment, n = 1 (720 steps at 240 Hz)\n" + "\n".join(lines))
    return rows


def test_replay_at_240_hz_is_the_integrated_run(study):
    bad = [name for name, row in study.items() if not row[5]]
    assert bad == [], bad


def test_truth_step_error_within_one_recorder_count(study):
    over = {
        name: (e14, tol)
        for name, (_c, _e12, _e24, e14, tol, _x) in study.items()
        if name not in M07_DELAY_LINE and e14 > tol
    }
    assert over == {}, over


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=M07_REASON)
def test_m07_transport_delay_error_within_one_recorder_count(study):
    counts = {name: study[name][3] / study[name][4] for name in M07_DELAY_LINE}
    over = {name: c for name, c in counts.items() if c > 1.0}
    assert over == {}, over


def test_error_falls_when_the_step_halves_where_resolvable(study):
    resolvable = {name: row for name, row in study.items() if row[1] > RESOLVABLE * row[4]}
    assert resolvable, "no port has a resolvable step error: the study would test nothing"
    bad = {name: (e12, e24) for name, (_c, e12, e24, _e14, _t, _x) in resolvable.items() if not e24 < e12}
    assert bad == {}, bad
