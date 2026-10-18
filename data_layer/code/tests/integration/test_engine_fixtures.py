"""TEST FIXTURES for the M07 closed-loop tests (labelled; never imported by ``src/``).

The real FADEC is M08 (W1.3b) and the real process-disturbance generator is M03 (W1.1); W2.1 wires them.
These fixtures exist only so M07 can be exercised in closed loop at module level (``_w1_common.md`` §2
"Neighbours"):

- ``FixtureSchedules``: an N2-demand -> nozzle-area schedule (opening towards idle, -400 shape: flight-idle
  A8 about 1.8 x MIL, TM-4240) and the steady fuel-flow feed-forward along that schedule (from M07's own
  steady solver), plus the M07 reference VG schedule evaluated on measured corrected speeds.
- ``GovernorFixture``: a proportional(-integral) N2 governor at 60 Hz (every 4 truth ticks, one-frame delay)
  with optional Wf/PS3 ratio-unit accel/decel limits. It is NOT the IN20 control law.
- ``DisturbanceFixture``: M03-like AD-32 disturbances, ``w = a_c * c(t) + a_u * u_e(t)`` with first-order
  (AR(1)) shaping per channel, aircraft-common and engine-specific parts from keyed core RNG streams.

The tests in this file check that the fixtures do what they claim (so a failing M07 test is not a fixture
bug).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
import pytest

from phalanx.core.rng import KeyPath, RngService, StreamDecl, StreamRegistry, Variate
from phalanx.engine.design import EngineModel, build_engine_model
from phalanx.engine.kernel import deriv_point
from phalanx.engine.layout import N_W_ENGINE, NX, U_A8, U_WF, Y_NAMES
from phalanx.engine.layout import A as AUX
from phalanx.engine.sim import EngineState, input_block, simulate, state_from_x
from phalanx.engine.steady import design_inputs, steady_state, vg_reference

RPM = 60.0 / (2.0 * np.pi)
FRAME = 4  # FADEC frame = 4 truth ticks (60 Hz fixture)
Y = {n: j for j, n in enumerate(Y_NAMES)}


@lru_cache(maxsize=4)
def fixture_model(n_sub: int | None = None) -> EngineModel:
    return build_engine_model(n_sub=n_sub)


@dataclass
class FixtureSchedules:
    """TEST FIXTURE: A8(N2 demand) and the steady fuel feed-forward along it."""

    model: EngineModel
    n2_grid: np.ndarray = field(default_factory=lambda: np.linspace(0.70, 1.0, 13))
    a8_idle_ratio: float = 1.8  # -400 flight idle 400 in2 vs MIL about 220 in2 (TM-4240)

    def __post_init__(self) -> None:
        d = self.model.design.stations
        self.a8_mil, self.wf_mil, self.n2_des = d["a8"], d["wf"], d["n2"]
        wf, xs = [], []
        x = None
        for f in self.n2_grid[::-1]:
            u = design_inputs(self.model)
            u[U_A8] = self.a8(f)
            r = steady_state(self.model, u, x0=x, target=("n2", f * self.n2_des))
            assert r.converged, f"fixture schedule steady state failed at N2 {f:.3f}"
            x = r.x
            wf.append(r.u[U_WF])
            xs.append(r.x)
        self.wf_grid = np.array(wf[::-1])
        self.x_grid = np.array(xs[::-1])

    def a8(self, n2_frac):
        s = np.clip((0.98 - np.asarray(n2_frac, float)) / 0.28, 0.0, 1.0)
        return self.a8_mil * (1.0 + (self.a8_idle_ratio - 1.0) * s)

    def wf_ff(self, n2_frac):
        return np.interp(n2_frac, self.n2_grid, self.wf_grid)

    def x_at(self, n2_frac: float) -> np.ndarray:
        """Steady state at an N2 fraction (exact grid point or a fresh solve)."""
        u = design_inputs(self.model)
        u[U_A8] = self.a8(n2_frac)
        k = int(np.argmin(np.abs(self.n2_grid - n2_frac)))
        r = steady_state(self.model, u, x0=self.x_grid[k], target=("n2", n2_frac * self.n2_des))
        assert r.converged
        return r.x

    def vg(self, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        d = self.model.design.derived
        n1c = y[:, Y["n1"]] * RPM / np.sqrt(y[:, Y["t2"]] / 288.15) / d["n1c_des_rpm"]
        n2c = y[:, Y["n2"]] * RPM / np.sqrt(y[:, Y["t25"]] / 288.15) / d["n2c_des_rpm"]
        v = [vg_reference(self.model, a, b) for a, b in zip(n1c, n2c, strict=True)]
        return np.array([a for a, _ in v]), np.array([b for _, b in v])


@dataclass
class GovernorFixture:
    """TEST FIXTURE: N2 governor (P + optional I), 60 Hz, optional Wf/PS3 accel/decel limits."""

    kp: float = 2.0  # fraction of design wf per fraction of design N2 error
    ki: float = 0.0  # per second
    ru_acc: float | None = None  # accel limit as a multiple of the steady Wf/PS3 at the current N2
    ru_dec: float | None = None
    integ: np.ndarray | None = None

    def command(self, sch: FixtureSchedules, n2_dem, y: np.ndarray, dt_frame: float) -> np.ndarray:
        n2 = y[:, Y["n2"]] / sch.n2_des
        err = np.asarray(n2_dem, float) - n2
        if self.integ is None:
            self.integ = np.zeros_like(n2)
        integ = self.integ + self.ki * err * dt_frame
        wf_free = sch.wf_ff(n2_dem) + sch.wf_mil * (self.kp * err + integ)
        wf = wf_free
        if self.ru_acc is not None or self.ru_dec is not None:
            ps3 = y[:, Y["ps3"]]
            k = np.clip(np.searchsorted(sch.n2_grid, n2), 1, sch.n2_grid.size - 1)
            ru_ss = sch.wf_grid[k] / _ps3_of(sch, k)
            if self.ru_acc is not None:
                wf = np.minimum(wf, self.ru_acc * ru_ss * ps3)
            if self.ru_dec is not None:
                wf = np.maximum(wf, self.ru_dec * ru_ss * ps3)
        wf = np.clip(wf, 0.03 * sch.wf_mil, 1.05 * sch.wf_mil)
        # anti-windup: the integrator only runs while the command is not limited
        self.integ = np.where(wf == wf_free, integ, self.integ)
        return wf


def _ps3_of(sch: FixtureSchedules, k) -> np.ndarray:
    out = []
    for kk in np.atleast_1d(k):
        u = design_inputs(sch.model)
        u[U_A8] = sch.a8(sch.n2_grid[kk])
        u[U_WF] = sch.wf_grid[kk]
        _, aux = deriv_point(sch.x_grid[kk], 0, 1, 0, 0.0, u, sch.model.p, sch.model.tables, -1.0)
        out.append(aux[AUX["ps3"]])
    return np.array(out)


@dataclass
class DisturbanceFixture:
    """TEST FIXTURE: M03-like AD-32/AD-46 process disturbances (n_ticks, n_engines, 5), AR(1)-shaped.

    sigma: per-channel standard deviations [fuel_metering, combustor_eff, inlet_recovery, shaft_load,
    fan_face]
    (a 4-tuple leaves fan_face at 0); common_frac: variance share of the aircraft-common component; f_c:
    shaping corner (Hz)."""

    sigma: tuple[float, ...] = (0.004, 0.003, 0.003, 0.004, 0.004)
    common_frac: float = 0.3
    f_c: float = 2.0
    root: int = 0x5EED_0007

    def series(self, n_ticks: int, n_engines: int, *, tail: str = "T1", sortie: int = 1) -> np.ndarray:
        decls = [
            StreamDecl("test_m03", "w_common", ("scenario", "tail", "sortie"), Variate.NORMAL, 4096, "tests"),
            StreamDecl("test_m03", "w_unit", ("scenario", "tail", "serial", "sortie"), Variate.NORMAL,
            4096, "tests"),
        ]  # fmt: skip
        rng = RngService(self.root, StreamRegistry(decls))
        keys = rng.scope(KeyPath.of(scenario="m07_fixture", tail=tail, sortie=sortie))
        nc = N_W_ENGINE
        c = keys.stream("test_m03", "w_common").draws(0, nc * n_ticks).reshape(n_ticks, nc)
        a = np.exp(-2.0 * np.pi * self.f_c / 240.0)
        b = np.sqrt(1.0 - a * a)
        sig = np.zeros(nc)
        sig[: len(self.sigma)] = self.sigma
        out = np.zeros((n_ticks, n_engines, nc))
        wc, wu = np.sqrt(self.common_frac), np.sqrt(1.0 - self.common_frac)
        cs = _ar1(c, a, b)
        for e in range(n_engines):
            ue = (
                keys.stream("test_m03", "w_unit", serial=f"E{e + 1}")
                .draws(0, nc * n_ticks)
                .reshape(n_ticks, nc)
            )
            out[:, e, :] = sig * (wc * cs + wu * _ar1(ue, a, b))
        return out


def _ar1(z: np.ndarray, a: float, b: float) -> np.ndarray:
    x = np.zeros_like(z)
    acc = np.zeros(z.shape[1])
    for k in range(z.shape[0]):
        acc = a * acc + b * z[k]
        x[k] = acc
    return x


@dataclass
class LoopResult:
    y: np.ndarray  # (L, E, NY)
    yi: np.ndarray
    aux: np.ndarray | None
    wf_cmd: np.ndarray  # (L, E)
    state: EngineState


def run_closed_loop(
    sch: FixtureSchedules,
    gov: GovernorFixture,
    n2_demand,
    n_ticks: int,
    *,
    n_engines: int = 1,
    w_engine: np.ndarray | None = None,
    x0: np.ndarray | None = None,
    record_aux: bool = False,
    state: EngineState | None = None,
    ab_enable=None,
    wf_ab_cmd=None,
    a8_override=None,
) -> LoopResult:
    """Closed loop M07 + TEST FIXTURE governor at 60 Hz. ``n2_demand`` scalar or (L,) fractions of design
    N2."""
    m = sch.model
    dem = np.broadcast_to(np.asarray(n2_demand, float), (n_ticks,))
    if state is None:
        x0 = sch.x_at(float(dem[0])) if x0 is None else x0
        state = state_from_x(m, x0, n_engines=n_engines)
    base = design_inputs(m)
    ys, yis, auxs, wfs = [], [], [], []
    # measured values for the first frame (afterwards: last outputs, one frame old)
    y_last = np.zeros((n_engines, len(Y_NAMES)))
    for e in range(n_engines):
        _, aux0 = deriv_point(state.f[e, :NX], 0, 1, 0, 0.0, base, m.p, m.tables, -1.0)
        y_last[e, Y["n2"]] = state.f[e, 1]
        y_last[e, Y["n1"]] = state.f[e, 0]
        y_last[e, Y["t2"]] = aux0[AUX["t2"]]
        y_last[e, Y["t25"]] = aux0[AUX["t25"]]
        y_last[e, Y["ps3"]] = aux0[AUX["ps3"]]
    for k0 in range(0, n_ticks, FRAME):
        n = min(FRAME, n_ticks - k0)
        d = float(dem[k0])
        wf = gov.command(sch, d, y_last, FRAME / 240.0)
        v1, v2 = sch.vg(y_last)
        a8 = sch.a8(d) if a8_override is None else a8_override
        kw = {
            "wf_cmd": np.broadcast_to(wf, (n, n_engines)),
            "a8_cmd": np.broadcast_to(a8, (n, n_engines)),
            "vg_igv_cmd": np.broadcast_to(v1, (n, n_engines)),
            "vg_vsv_cmd": np.broadcast_to(v2, (n, n_engines)),
        }
        if w_engine is not None:
            kw["w_engine"] = w_engine[k0 : k0 + n]
        if ab_enable is not None:
            kw["ab_enable"] = np.broadcast_to(np.asarray(ab_enable)[k0 : k0 + n, None], (n, n_engines))
            kw["wf_ab_cmd"] = np.broadcast_to(np.asarray(wf_ab_cmd)[k0 : k0 + n, None], (n, n_engines))
        u, ui = input_block(n, n_engines, base, **kw)
        r = simulate(m, state, u, ui, record_aux=record_aux)
        state = r.state
        y_last = r.y[-1]
        ys.append(r.y)
        yis.append(r.yi)
        wfs.append(np.broadcast_to(wf, (n, n_engines)))
        if record_aux:
            auxs.append(r.aux)
    return LoopResult(
        np.concatenate(ys), np.concatenate(yis), np.concatenate(auxs) if record_aux else None,
        np.concatenate(wfs), state,
    )  # fmt: skip


# --------------------------------------------------------------------------------------------- fixture tests


@pytest.fixture(scope="module")
def sch() -> FixtureSchedules:
    return FixtureSchedules(fixture_model())


@pytest.mark.integration
def test_fixture_schedule_is_monotone_with_positive_margins(sch):
    """The fixture operating line (A8 schedule + steady fuel) is monotone in fuel and keeps both margins
    > 0."""
    assert np.all(np.diff(sch.wf_grid) > 0)
    for f, x, wf in zip(sch.n2_grid, sch.x_grid, sch.wf_grid, strict=True):
        u = design_inputs(sch.model)
        u[U_A8] = sch.a8(f)
        u[U_WF] = wf
        _, aux = deriv_point(x, 0, 1, 0, 0.0, u, sch.model.p, sch.model.tables, -1.0)
        assert aux[AUX["sm_fan"]] > 0.0 and aux[AUX["sm_hpc"]] > 0.0, (f, aux[AUX["sm_fan"]])


@pytest.mark.integration
def test_fixture_governor_holds_demand(sch):
    """n = 1 engine, 5 s: the P governor settles near the demand (P-only offset < 1 % N2)."""
    gov = GovernorFixture(kp=2.0)
    r = run_closed_loop(sch, gov, 0.9, 240 * 5)
    n2 = r.y[-240:, 0, Y["n2"]] / sch.n2_des
    assert abs(float(n2.mean()) - 0.9) < 0.01


@pytest.mark.integration
def test_fixture_disturbance_common_share():
    """Cross-engine correlation of the disturbance fixture equals its configured common share (n = 2 engines,
    48,000 ticks; tolerance 0.05 from the AR(1) effective sample size)."""
    w = DisturbanceFixture(common_frac=0.3).series(48_000, 2)
    for ch in range(4):
        r = np.corrcoef(w[:, 0, ch], w[:, 1, ch])[0, 1]
        assert abs(r - 0.3) < 0.05, (ch, r)
