"""W1.1 A7 for M04 and closed-loop behaviour on a TEST FIXTURE plant: compiled == reference bitwise (block and
step; whole tree without JIT), snapshot round trip, engine-start logic, take-off/climb/track capture, PLA
bands.

The plant below is a **TEST FIXTURE (not a model)**: a 3-DOF point mass with first-order Nz, roll-rate and
thrust responses, an exponential atmosphere and a first-order N2. It exists only to close M04's loop in W1
(real coupling is W2.1's job) and is never imported by src/.

Sample: one short sortie of key 'pilot' (the shortest flight of 2026-01-06, ~30 min); 2,400-tick windows for
the equality checks.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.module import ModuleBase, ParamSet, Port
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import Connection, System
from phalanx.core.snapshot import restore, snapshot
from phalanx.core.state import Field, StateSchema
from phalanx.core.time import NS_PER_S, RG_240, latest_truth_step
from phalanx.environment.config import load_env_config
from phalanx.pilot import kernel as K
from phalanx.pilot.module import PilotModule, load_pilot_config
from phalanx.scenario import phases as PH
from phalanx.scenario.config import load_fleet_scenario, load_scenario_params
from phalanx.scenario.generator import Planner
from phalanx.scenario.plan import S_ALT, S_PHASE, S_PLA_HI, S_PLA_LO, SortiePlan
from phalanx.scenario.streams import STREAMS

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PCFG = load_pilot_config()
G = 9.80665
N2_100 = float(PCFG.vector[K.P_N2100])
FT_DEG = 180.0 / math.pi


def short_plan(day=dt.date(2026, 1, 6), key="pilot") -> SortiePlan:
    p, env = load_scenario_params(), load_env_config()
    fleet = load_fleet_scenario(ROOT / "configs" / "scenarios" / "tejas_two_squadrons.yaml")
    pl = Planner(p, env, fleet, RngService(0x40, StreamRegistry(STREAMS)).scope(KeyPath.of(scenario=key)))
    slots, _ = pl.plan_day(day)
    plans = [pl.build_sortie(s) for s in slots]
    return min(plans, key=lambda x: x.summary.flight_s)


class PointMassFixture(ModuleBase):
    """TEST FIXTURE (not a model): closes M04's loop in W1 tests (see module docstring)."""

    version = "0"
    rate = RG_240
    ports_in = (
        Port("stick_pitch", "1"),
        Port("stick_roll", "1"),
        Port("pla", "rad", "<f8", (1,)),
        Port("airbrake_cmd", "1", "<i8"),
    )
    ports_out = (
        Port("alt", "m"),
        Port("tas", "m/s"),
        Port("mach", "1"),
        Port("vel_ned", "m/s", "<f8", (3,)),
        Port("quat", "1", "<f8", (4,)),
        Port("omega_body", "rad/s", "<f8", (3,)),
        Port("nz", "1"),
        Port("wow", "1", "<i8", (3,)),
        Port("n2", "rad/s", "<f8", (1,)),
    )
    state_schema = StateSchema("fixture.pointmass", 1, (Field("x", "<f8", (11,)),))
    X_N, X_E, X_H, X_V, X_GAM, X_CHI, X_PHI, X_NZ, X_P, X_T, X_N2 = range(11)

    def __init__(self, field_elev, motoring_t0_ns, id="af", running=False, airborne=None):
        super().__init__(id, ParamSet("fixture", {}))
        self.fe = float(field_elev)
        self.t_mot = int(motoring_t0_ns)
        self.running = bool(running)
        self.airborne = airborne  # None or (alt m, tas m/s, track rad): start in level flight

    def init(self, params, keys):
        x = np.zeros(11)
        x[self.X_H] = self.fe
        if self.running:
            x[self.X_N2] = 0.63 * N2_100
            x[self.X_T] = 6e3
        if self.airborne is not None:
            x[self.X_H], x[self.X_V], x[self.X_CHI] = self.airborne
            x[self.X_NZ] = 1.0
            x[self.X_N2] = 0.9 * N2_100
            x[self.X_T] = 30e3
        return {"x": x}

    def _outs(self, x):
        h, v, gam, chi, phi = x[self.X_H], x[self.X_V], x[self.X_GAM], x[self.X_CHI], x[self.X_PHI]
        a = 340.3 - 0.0039 * (h - 0.0)
        theta = gam + 0.05 * (x[self.X_NZ] if v > 60 else 0.0)
        cr, sr, cp, sp, cy, sy = (
            math.cos(phi / 2),
            math.sin(phi / 2),
            math.cos(theta / 2),
            math.sin(theta / 2),
            math.cos(chi / 2),
            math.sin(chi / 2),
        )
        q = np.array(
            [
                cr * cp * cy + sr * sp * sy,
                sr * cp * cy - cr * sp * sy,
                cr * sp * cy + sr * cp * sy,
                cr * cp * sy - sr * sp * cy,
            ]
        )
        on_ground = h <= self.fe + 1e-6 and gam <= 0.0
        return {
            "alt": np.array(h),
            "tas": np.array(v),
            "mach": np.array(v / a),
            "vel_ned": np.array(
                [v * math.cos(gam) * math.cos(chi), v * math.cos(gam) * math.sin(chi), -v * math.sin(gam)]
            ),
            "quat": q,
            "omega_body": np.array([x[self.X_P], 0.0, 0.0]),
            "nz": np.array(x[self.X_NZ]),
            "wow": np.full(3, 1 if on_ground else 0, dtype=np.int64),
            "n2": np.array([x[self.X_N2]]),
        }

    def initial_outputs(self, state):
        return self._outs(state["x"])

    def step(self, state, inputs, t, dt):
        x = np.array(state["x"], copy=True)
        sp, srl = float(inputs["stick_pitch"]), float(inputs["stick_roll"])
        pla = float(np.asarray(inputs["pla"])[0]) * FT_DEG
        nz_cmd = 1.0 + 7.0 * sp if sp >= 0 else 1.0 + 4.5 * sp
        if x[self.X_H] <= self.fe + 1e-6 and x[self.X_GAM] <= 0.0:
            # on the ground the stick is M05's ground-law direct elevon link (W2.1a rotation, A-W2.1-9):
            # the fixture turns the aft stick into a gentle lift at rotation (1 + stick g), not a g demand
            nz_cmd = 1.0 + max(sp, 0.0)
        rho = 1.225 * math.exp(-(x[self.X_H]) / 9000.0)
        if pla < 10.0:
            t_cmd = 0.0
        elif pla <= 87.0:
            t_cmd = 6e3 + (54e3 - 6e3) * (pla - 18.0) / 69.0
        else:
            t_cmd = 54e3 if pla < 94.0 else 60e3 + 24e3 * (pla - 94.0) / 36.0
        t_cmd *= (rho / 1.225) ** 0.7
        x[self.X_T] += (t_cmd - x[self.X_T]) * dt / 1.0
        n2_t = 0.0 if pla < 10.0 else N2_100 * min(1.0, 0.63 + 0.32 * max(0.0, pla - 18.0) / 69.0)
        if pla < 10.0 and t >= self.t_mot:
            n2_t = 0.3 * N2_100  # starter motoring
        x[self.X_N2] += (n2_t - x[self.X_N2]) * dt / 1.5
        m, s_ref = 10000.0, 38.4
        v = max(x[self.X_V], 1.0)
        q = 0.5 * rho * v * v
        cl = x[self.X_NZ] * m * G / max(q * s_ref, 1.0)
        drag = q * s_ref * (0.02 + 0.15 * cl * cl + (0.03 if int(inputs["airbrake_cmd"]) else 0.0))
        on_ground = x[self.X_H] <= self.fe + 1e-6 and x[self.X_GAM] <= 0.0
        nz_aero = 1.2 * q * s_ref / (m * G)  # CLmax 1.2: the fixture cannot pull more than lift allows
        x[self.X_NZ] += (min(nz_cmd, nz_aero) - x[self.X_NZ]) * dt / 0.25
        x[self.X_P] += (math.radians(200.0) * srl - x[self.X_P]) * dt / 0.15
        if on_ground and not (x[self.X_V] > 85.0 and nz_cmd > 1.05):
            x[self.X_V] = max(
                0.0, x[self.X_V] + (x[self.X_T] - 0.5 * q * s_ref * 0.03 - 0.03 * m * G) / m * dt
            )
            x[self.X_GAM] = 0.0
            x[self.X_PHI] = 0.0
            x[self.X_H] = self.fe
        else:
            gam, phi = x[self.X_GAM], x[self.X_PHI]
            x[self.X_V] = max(20.0, x[self.X_V] + ((x[self.X_T] - drag) / m - G * math.sin(gam)) * dt)
            x[self.X_GAM] += G * (x[self.X_NZ] * math.cos(phi) - math.cos(gam)) / v * dt
            x[self.X_CHI] = (x[self.X_CHI] + G * x[self.X_NZ] * math.sin(phi) / (v * math.cos(gam)) * dt) % (
                2 * math.pi
            )
            x[self.X_PHI] += x[self.X_P] * dt
            x[self.X_H] = max(self.fe, x[self.X_H] + v * math.sin(gam) * dt)
        return {"x": x}, self._outs(x)


def build(
    plan, *, compiled=True, block_len=1024, root=0x41, start_phase=PH.ENGINE_START, lead_s=5.0, ledger=None
):
    """Place the plan on the kernel clock so that ``start_phase`` begins ``lead_s`` after t = 0 (skips the
    engine-off pre-flight in short tests); the fixture starts with the engine running if that phase is later
    than the engine start."""
    phases = list(plan.seg_i[:, S_PHASE])
    t0 = round(lead_s * NS_PER_S) - int(plan.t_off_ns[phases.index(start_phase)])
    motor = t0 + int(plan.t_off_ns[phases.index(PH.ENGINE_START)])
    pil = PilotModule("pilot", PCFG, plan=plan, t_kernel0_ns=t0, compiled=compiled)
    airborne = None
    if start_phase in PH.AIRBORNE:
        j = phases.index(start_phase)
        alt0 = float(plan.seg_f[j, S_ALT])
        airborne = (alt0, float(plan.seg_f[j, 1]) * (340.3 - 0.0039 * alt0), float(plan.seg_f[j, 2]))
    af = PointMassFixture(
        plan.field_elev_m,
        motor,
        running=start_phase not in (PH.PREFLIGHT, PH.ENGINE_START),
        airborne=airborne,
    )
    conns = [
        Connection("pilot.stick_pitch", "af.stick_pitch"),
        Connection("pilot.stick_roll", "af.stick_roll"),
        Connection("pilot.pla", "af.pla"),
        Connection("pilot.airbrake_cmd", "af.airbrake_cmd"),
    ]
    for name in ("alt", "tas", "mach", "vel_ned", "quat", "omega_body", "nz", "wow", "n2"):
        conns.append(
            Connection(f"af.{name}", f"pilot.{name}", delayed=True, note="airframe -> pilot one-frame delay")
        )
    s = System(
        [pil, af],
        conns,
        rng=RngService(root, StreamRegistry(), ledger=ledger),
        identity=KeyPath.of(scenario="pilot", tail=plan.tail, sortie=plan.rng_key),
        block_len=block_len,
    )
    s.t0_plan = t0
    return s


def kernel_times(tr, s):
    """Kernel times (ns) of the trace rows (held values after each step) and the plan origin."""
    n = next(iter(tr.ports.values())).shape[0]
    return (np.arange(tr.k0, tr.k0 + n) + 1) * NS_PER_S / 240 - s.t0_plan


@pytest.fixture(scope="module")
def plan():
    return short_plan()


@pytest.fixture(scope="module")
def departure(plan):
    """Take-off to the end of the outbound transit (~6-8 min of flight). The take-off ends at the gear-up
    (W2.1a, A-W2.1-9), not at its planned instant: the flown plan runs ``shift`` ns from the plan clock
    after it, so the run first goes to the planned end, reads the shift and then ends at the flown one."""
    s = build(plan, start_phase=PH.TAKEOFF)
    phases = list(plan.seg_i[:, S_PHASE])
    t_end = s.t0_plan + int(plan.t_off_ns[phases.index(PH.TRANSIT) + 1])
    w0 = s.start()
    w, _ = s.run(w0, latest_truth_step(t_end) - 240 * 60)  # well after the take-off
    shift = int(np.asarray(w.states["pilot"]["i"])[K.I_SHIFT])
    _, tr = s.run(w0, latest_truth_step(t_end + shift) - 240, record=s.output_ports())
    return s, tr, shift


@pytest.fixture(scope="module")
def start_and_shutdown(plan):
    """Engine start (5 s lead) to 30 s after start, and the last 60 s of the sortie to 10 s after cut-off."""
    s = build(plan)
    _, tr_start = s.run(s.start(), 240 * 40, record=s.output_ports())
    s2 = build(plan, start_phase=PH.SHUTDOWN, lead_s=5.0)
    phases = list(plan.seg_i[:, S_PHASE])
    shut = int(plan.t_off_ns[phases.index(PH.SHUTDOWN)])
    n = latest_truth_step(s2.t0_plan + int(plan.t_end_off_ns) + 10 * NS_PER_S)
    _, tr_end = s2.run(s2.start(), n, record=s2.output_ports())
    return (s, tr_start), (s2, tr_end), shut


def _digest(tr):
    h = hashlib.blake2b(digest_size=16)
    for k in sorted(tr.ports):
        h.update(np.ascontiguousarray(tr.ports[k]).tobytes())
    return h.hexdigest()


@pytest.mark.integration
@pytest.mark.determinism
def test_compiled_equals_reference_and_step_equals_block(plan):
    ref = build(plan, compiled=False, start_phase=PH.TAKEOFF)
    _, tr_ref = ref.run(ref.start(), 9600, mode="step", record=ref.output_ports())
    assert np.ptp(tr_ref.ports["pilot.stick_pitch"]) > 0.05  # rotation and climb exercised
    for bl in (1, 7, 1024):
        s = build(plan, block_len=bl, start_phase=PH.TAKEOFF)
        _, tr = s.run(s.start(), 9600, mode="block", record=s.output_ports())
        assert tr.digest() == tr_ref.digest(), bl


@pytest.mark.integration
@pytest.mark.determinism
def test_whole_call_tree_without_jit_matches_compiled(plan):
    s = build(plan, start_phase=PH.TAKEOFF)
    _, tr = s.run(s.start(), 4800, record=s.output_ports())
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2]);"
        "import test_pilot_module as t; from phalanx.scenario import phases as PH;"
        "p = t.short_plan(); s = t.build(p, start_phase=PH.TAKEOFF);"
        "_, tr = s.run(s.start(), 4800, record=s.output_ports());"
        "print(t._digest(tr))"
    )
    out = subprocess.run(
        [sys.executable, "-I", "-c", code, str(SRC), str(Path(__file__).parent)],
        env=dict(os.environ, NUMBA_DISABLE_JIT="1"),
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == _digest(tr)


@pytest.mark.fork
def test_snapshot_round_trip(plan):
    ref = build(plan, start_phase=PH.TAKEOFF)
    w_ref, _ = ref.run(ref.start(), 9_000)
    s1 = build(plan, start_phase=PH.TAKEOFF)
    w1, _ = s1.run(s1.start(), 4_001)
    s2 = build(plan, start_phase=PH.TAKEOFF)
    w2, _ = s2.run(restore(s2, snapshot(s1, w1)), 9_000 - 4_001)
    assert snapshot(s2, w2) == snapshot(ref, w_ref)


@pytest.mark.integration
def test_engine_start_logic_and_cutoff(plan, start_and_shutdown):
    (s, tr), (s2, tr2), _shut = start_and_shutdown
    t = kernel_times(tr, s)
    start = plan.t_off_ns[list(plan.seg_i[:, S_PHASE]).index(PH.ENGINE_START)]
    n2 = tr.ports["af.n2"][:, 0]
    pla = tr.ports["pilot.pla"][:, 0]
    assert np.all(pla[t < start] == 0.0)
    lit = np.flatnonzero(pla > 0.0)[0]
    assert n2[lit - 2] >= 0.2 * N2_100 * 0.999  # PLA advanced only after N2 reached 20 % (one-frame delay)
    assert pla[-1] == pytest.approx(PCFG.vector[K.P_GI], abs=1e-9)  # at ground idle
    t2 = kernel_times(tr2, s2)
    pla2 = tr2.ports["pilot.pla"][:, 0]
    assert np.all(pla2[t2 > plan.t_end_off_ns + 2 * NS_PER_S] == 0.0)  # cut-off after shutdown
    running = (t2 > t2[0] + 2 * NS_PER_S) & (t2 < plan.t_end_off_ns - 2 * NS_PER_S)
    assert running.any() and np.all(pla2[running] > 0.0)


@pytest.mark.integration
def test_take_off_climb_and_tracking_on_fixture(plan, departure):
    s, tr, shift = departure
    p = tr.ports
    t = kernel_times(tr, s)
    ph = plan.seg_i[:, S_PHASE]
    j_tr = list(ph).index(PH.TRANSIT)
    alt = p["af.alt"]
    assert alt.max() > plan.field_elev_m + 1000.0  # it flew
    target = plan.seg_f[j_tr, S_ALT]
    assert abs(alt[-1] - target) < 0.1 * (target - plan.field_elev_m), (alt[-1], target)
    # heading captured at the end of the transit (track within 10 deg)
    vn, ve = p["af.vel_ned"][-1, 0], p["af.vel_ned"][-1, 1]
    err = (math.atan2(ve, vn) - plan.seg_f[j_tr, 2] + math.pi) % (2 * math.pi) - math.pi
    assert abs(err) < math.radians(10.0)
    # PLA inside each segment's band (+ slew transients of <= 1.5 s after a segment change)
    pla = p["pilot.pla"][:, 0]
    # the flown segment starts: the plan's, moved by the shift after the take-off
    j_to = list(ph).index(PH.TAKEOFF)
    starts = np.asarray(plan.t_off_ns, dtype=np.int64) + np.where(np.arange(plan.n_segments) > j_to, shift, 0)
    j = np.clip(np.searchsorted(starts, t, side="right") - 1, 0, plan.n_segments - 1)
    settled = t - starts[j] > 1.5 * NS_PER_S
    lo, hi = plan.seg_f[j, S_PLA_LO], plan.seg_f[j, S_PLA_HI]
    ok = (pla >= lo - 1e-9) & (pla <= hi + 1e-9)
    assert np.mean(ok[settled]) > 0.99
    ab = p["pilot.ab_select"][:, 0]
    assert np.array_equal(ab == 1, pla >= 94.0 / FT_DEG)
