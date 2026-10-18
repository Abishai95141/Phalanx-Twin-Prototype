"""W2.2 M12 avionics: radar altimeter (AD-51; A-W2.2-8).

Physics under test: slant range to the nearest ground inside the beam (height while the tilt is inside the
beam half-angle, h / cos(tilt - half-angle) beyond), loss of track (NO_COMPUTED_DATA, value held) beyond the
tracking tilt or above the maximum height, per-unit installation scale and zero errors keyed by the unit
serial, and a terrain/vegetation height process indexed by along-track distance (the texture belongs to the
place flown over: the same ground gives the same terrain at any speed and in any fork). Sample sizes: one
unit, 1-20 s at 240 Hz per test; deterministic.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.rng import KeyPath
from phalanx.dictionary.params import load_params
from phalanx.sensors.avionics import radalt as R
from phalanx.sensors.avionics.config import build_avionics_config


def _fixture():
    name = "w22_avionics_fixture"
    if name not in sys.modules:
        p = Path(__file__).resolve().parents[1] / "integration" / "test_w22_avionics_fixture.py"
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


FX = _fixture()
CFG = build_avionics_config()
DT = FX.DT


def _no_terrain_cfg():
    params = load_params("M12_AVIONICS")
    params["radalt"] = params["radalt"].replace(terrain_sigma=0.0)
    return build_avionics_config(params=params)


def _truth(n: int, hag: float, roll_deg: float = 0.0, speed: float = 0.0) -> np.ndarray:
    """(n, 7) radar-altimeter truth [hag, q, vn, ve]: constant height, roll and ground speed (north)."""
    q = FX._axis_quat(np.full(n, math.radians(roll_deg)), 0)
    tr = np.zeros((n, 7))
    tr[:, 0] = hag
    tr[:, 1:5] = q
    tr[:, 5] = speed
    return tr


def _kernel(cfg, truth, scale=0.0, offset=0.0, zcell=None, state=None):
    f, i = state if state is not None else R.radalt_initial_state(scale, offset)
    n = truth.shape[0]
    z = np.zeros(R.cells_needed(DT, n, cfg.radalt_p[R.P_CELL])) if zcell is None else zcell
    return R.radalt_kernel(f, i, cfg.radalt_p, np.ascontiguousarray(truth), np.full(n, 28.0), z, DT)


@pytest.mark.unit
@pytest.mark.parametrize("roll_deg", [0.0, 20.0, 45.0, 55.0])
def test_beam_geometry_and_installation_errors(roll_deg):
    """Flat ground (terrain sigma 0), 300 m, a unit with scale +1 % and zero +0.5 m, 1 s (10 tracker time
    constants): inside the 30 deg half-angle the reading is (1 + s) h + o; beyond it the return comes from the
    beam edge, (1 + s) h / cos(tilt - 30 deg) + o."""
    cfg = _no_terrain_cfg()
    _f, _i, out, ssm, _pw, tru = _kernel(cfg, _truth(240, 300.0, roll_deg), scale=0.01, offset=0.5)
    half = math.degrees(cfg.radalt_p[R.P_BEAM_HALF])
    slant = 300.0 / math.cos(math.radians(max(0.0, roll_deg - half)))
    assert out[-1] == pytest.approx(1.01 * slant + 0.5, abs=1e-3)
    assert np.all(ssm == R.SSM_NORMAL) and np.all(tru == 300.0)


@pytest.mark.unit
def test_loss_of_track_holds_the_value_with_no_computed_data():
    """1 s at 300 m, then 1 s at 65 deg roll (beyond the 60 deg tracking limit), then 1 s at 2,000 m (above
    5,000 ft), then 1 s back at 300 m level: NCD with the last tracked value held, then NORMAL tracking."""
    cfg = _no_terrain_cfg()
    tr = np.concatenate(
        [_truth(240, 300.0), _truth(240, 300.0, 65.0), _truth(240, 2000.0), _truth(240, 300.0)]
    )
    _, _, out, ssm, _, _ = _kernel(cfg, tr)
    assert np.all(ssm[:240] == R.SSM_NORMAL)
    assert np.all(ssm[240:720] == R.SSM_NCD)
    assert np.all(out[240:720] == out[239])
    assert np.all(ssm[720:] == R.SSM_NORMAL) and out[-1] == pytest.approx(300.0, abs=1e-3)


@pytest.mark.unit
def test_terrain_belongs_to_the_place_flown_over():
    """The terrain height under the beam is drawn per 10 m along-track cell: flying the same 1,500 m at
    100 m/s and at 250 m/s visits the same cells with the same terrain heights (frame-by-frame kernel calls,
    n = 1 unit); the terrain varies (sigma 1 m, correlation 100 m) and the reading follows it."""
    m = FX.make_module()
    k_cells = 200
    zcell = m.stream("radalt_terrain", sensor="RADALT").draws(0, k_cells)
    seen = {}
    for speed in (100.0, 250.0):
        n = int(1500.0 / speed * 240)
        state = R.radalt_initial_state(0.0, 0.0)
        cells = {}
        for _k in range(n):
            i_cell = int(state[1][R.I_CELL])
            f, i, *_ = R.radalt_kernel(
                state[0],
                state[1],
                CFG.radalt_p,
                _truth(1, 300.0, speed=speed),
                np.full(1, 28.0),
                zcell[i_cell:],
                DT,
            )
            state = (f, i)
            cells[int(i[R.I_CELL])] = float(f[R.F_TERRAIN])
        seen[speed] = cells
    common = sorted(set(seen[100.0]) & set(seen[250.0]))
    assert len(common) >= 140
    assert all(seen[100.0][c] == seen[250.0][c] for c in common)
    h = np.array([seen[100.0][c] for c in common])
    assert 0.2 < np.std(h) < 3.0  # sigma 1 m process over 1.5 correlation lengths
    lag1 = np.corrcoef(h[1:], h[:-1])[0, 1]
    assert lag1 == pytest.approx(math.exp(-10.0 / 100.0), abs=0.15)  # cell / correlation length


@pytest.mark.unit
def test_installation_errors_are_keyed_by_the_unit_serial():
    """Scale and zero errors are drawn once per installed unit (scenario, serial): the same serial gives the
    same errors in another sortie and on another tail; another serial gives other errors."""

    def errs(sortie, tail, serial):
        ident = KeyPath.of(scenario="W22", tail=tail, sortie=sortie)
        m = FX.make_module(identity=ident, config=CFG, lru_serials={"RADALT": serial})
        s = m.init(m.params, m.keys)
        return (float(s["radalt_f"][R.F_SCALE]), float(s["radalt_f"][R.F_OFFSET]))

    a = errs("SRT0001", "KH2001", "RA-0007")
    assert a == errs("SRT0002", "KH2001", "RA-0007") == errs("SRT0009", "KH2002", "RA-0007")
    assert a != errs("SRT0001", "KH2001", "RA-0008")
    assert a[0] != 0.0 and a[1] != 0.0
