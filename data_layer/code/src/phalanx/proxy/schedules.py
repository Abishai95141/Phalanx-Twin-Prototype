"""M08 proxy schedules derived from the proxy engine (W2.4a; AD-50 "harmonise ru_ff/ru_ref with M07").

The Tejas M08 ratio-unit schedules were FIXTURE-MATCHED (A-W1.3b-7). For the proxy they are computed from the
``separate_fixed`` M07 model itself (its SLS ISA steady operating line, by continuation in corrected core
speed), so the controller's feed-forward and reference lines are consistent with the plant it governs:

- ``ru_ref``: steady Wf/PS3 [lb/h/psi] against N2/sqrt(theta1) (fraction of 100 % N2): the accel/decel
  reference;
- ``ru_ff``: steady Wf/PS3 against N2/sqrt(theta25): the governor feed-forward at the demanded speed;
- ``n2c_pla``: the corrected-core-speed demand N2/sqrt(theta25) against PLA. Its *shape* is the MEASURED
  round-2 relation (frozen M-A f: PLA -> corrected fuel, g: corrected fuel -> N2/sqrt(theta2); an existing
  result, not a new fit) evaluated at the **ground** condition M 0, delta = theta = 1 (W2.4a-2: the lever
  governs the proxy engines on the ground, the A/T in flight; M08's demand is PLA-only, so the measured
  Mach, delta and theta terms of f cannot enter in flight, A-W2.4a-14), carried into the theta25 correction
  through the model's own T25/T2 at that corrected speed;
- ``cvg``: the HPC stator schedule in M08's axis, equal to M07's reference schedule (A-W1.3a-12 convention).

``derive_tables`` is deterministic; ``tests/unit/test_proxy_config.py`` regenerates the committed CSVs and
requires equality, so the tables cannot drift from the model they were derived from.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import numpy as np
from scipy.interpolate import PchipInterpolator

from phalanx.engine.layout import U_WF, X_N1, X_N2
from phalanx.engine.steady import design_inputs, steady_state

LBH_PER_KGS = 3600.0 / 0.45359237
PSI = 6894.757293168361
RPM_PER_RADS = 60.0 / (2.0 * np.pi)


@dataclass(frozen=True)
class OperatingLine:
    """SLS ISA steady operating line of the proxy engine, from design down in corrected core speed."""

    n2c1: np.ndarray  # N2/sqrt(theta1) as a fraction of 100 % N2 (theta1 = 1 at SLS)
    n2c25: np.ndarray  # N2/sqrt(theta25) as a fraction of 100 % N2
    n1c: np.ndarray  # N1 fraction of 100 % N1
    ru: np.ndarray  # Wf/PS3 [lb/h/psi]
    wf: np.ndarray  # kg/s
    t5: np.ndarray  # K


def operating_line(model, fracs=None) -> OperatingLine:
    """Steady SLS points at corrected core speeds ``fracs`` (fractions of the design N2), by 1 %
    continuation."""
    fracs = np.round(np.arange(1.0, 0.445, -0.01), 4) if fracs is None else np.asarray(fracs)
    d = model.design.derived
    n1_100 = float(model.params.value("n1_100pct"))
    n2_100 = float(model.params.value("n2_100pct"))
    u0 = design_inputs(model)
    s = steady_state(model, u0)
    rows = []
    for f in fracs:
        s = steady_state(model, u0, x0=s.x, target=("n2", float(f) * d["n2_des"]))
        if not s.converged:
            raise RuntimeError(f"proxy operating line did not converge at {f}")
        a = s.aux_dict()
        n2 = s.x[X_N2]
        rows.append(
            (
                n2 / n2_100,
                n2 / np.sqrt(a["t25"] / 288.15) / n2_100,
                s.x[X_N1] / n1_100,
                s.u[U_WF] * LBH_PER_KGS / (a["ps3"] / PSI),
                s.u[U_WF],
                a["t5"],
            )
        )
    r = np.array(rows)
    return OperatingLine(*(r[:, j].copy() for j in range(6)))


def _monotone_pchip(xk, yk):
    """Monotone PCHIP with linear end extrapolation (the round-2 ``MonoMap`` convention)."""
    xk = np.asarray(xk, float)
    yk = np.asarray(yk, float)
    P = PchipInterpolator(xk, yk)
    dP = P.derivative()

    def f(z):
        z = np.asarray(z, float)
        out = P(np.clip(z, xk[0], xk[-1]))
        out = np.where(z < xk[0], yk[0] + dP(xk[0]) * (z - xk[0]), out)
        return np.where(z > xk[-1], yk[-1] + dP(xk[-1]) * (z - xk[-1]), out)

    return f


#: reference condition of the PLA-only demand (W2.4a-2: the ground, where the lever governs)
DEMAND_MACH = 0.0


def measured_n2c_of_pla(
    frozen_ma_json: str | os.PathLike[str], pla_deg: np.ndarray, mach: float = DEMAND_MACH
) -> np.ndarray:
    """Round-2 MEASURED steady relation N2/sqrt(theta2) [fraction] = g(f(PLA) + cM (M - 0.5)) at delta = theta
    = 1 (the f map's delta and theta terms vanish there)."""
    d = json.loads(open(frozen_ma_json).read())["readable"]["FFN2"]
    f = _monotone_pchip(d["f_knots_x"], d["f_knots_y"])
    g = _monotone_pchip(d["g_knots_x"], d["g_knots_y"])
    wd = np.asarray(f(np.asarray(pla_deg, float))) + float(d["cM"]) * (float(mach) - 0.5)
    return np.asarray(g(wd)) / 100.0


def derive_tables(model, frozen_ma_json: str | os.PathLike[str]) -> dict[str, np.ndarray]:
    """All M08 proxy tables (name -> array) from the proxy M07 model and the round-2 frozen M-A."""
    ol = operating_line(model)
    o = np.argsort(ol.n2c1)
    n2c1, n2c25, ru = ol.n2c1[o], ol.n2c25[o], ol.ru[o]
    # PLA demand: the measured N2/sqrt(theta2) at the f-map knots, carried to theta25 through the model
    d = json.loads(open(frozen_ma_json).read())["readable"]["FFN2"]
    pla_k = np.asarray(d["f_knots_x"], float)
    n2c2_k = measured_n2c_of_pla(frozen_ma_json, pla_k)
    n2c25_k = np.interp(n2c2_k, n2c1, n2c25)
    if np.any(np.diff(n2c25_k) < 0):
        raise ValueError("the carried demand is not monotone in PLA")
    # flat extensions below the idle knot (lever below idle) and above the top knot (to the end of the lever)
    pla = np.concatenate([[0.0], pla_k, [120.0]])
    dem = np.concatenate([[n2c25_k[0]], n2c25_k, [n2c25_k[-1]]])
    # strictly increasing breakpoints are required (the first knots of f are flat: keep both, demand
    # non-decreasing)
    # CVG: M07 reference schedule (fraction of design N2c25) expressed on M08's axis (fraction of 100 % N2)
    dd = model.design.derived
    n2_100_rpm = float(model.params.value("n2_100pct")) * RPM_PER_RADS
    k = dd["n2c_des_rpm"] / n2_100_rpm
    cvg_x = np.asarray(model.tables.cvg_x, float) * k
    cvg_y = np.asarray(model.tables.cvg_y, float)
    return {
        "n2c_pla_x": pla,
        "n2c_pla_y": dem,
        "ru_ref_x": n2c1,
        "ru_ref_y": ru,
        "ru_ff_x": n2c25,
        "ru_ff_y": ru,
        "cvg_x": cvg_x,
        "cvg_y": np.degrees(cvg_y),
    }


def write_tables(tables: dict[str, np.ndarray], out_dir: str | os.PathLike[str]) -> None:
    """Write the derived tables as the M08 parameter CSVs (n2c_pla, ru_ref, ru_ff, cvg_n2c)."""
    spec = {
        "n2c_pla.csv": (("pla_deg", "n2c_pla_x"), ("n2c25", "n2c_pla_y")),
        "ru_ref.csv": (("n2c", "ru_ref_x"), ("ru_pph_psi", "ru_ref_y")),
        "ru_ff.csv": (("n2c25", "ru_ff_x"), ("ru_pph_psi", "ru_ff_y")),
        "cvg_n2c.csv": (("n2c25", "cvg_x"), ("cvg_deg", "cvg_y")),
    }
    for fname, cols in spec.items():
        a = np.column_stack([tables[key] for _c, key in cols])
        lines = [",".join(c for c, _k in cols)] + [",".join(repr(float(v)) for v in row) for row in a]
        with open(os.path.join(out_dir, fname), "w") as fh:
            fh.write("\n".join(lines) + "\n")


__all__ = ["OperatingLine", "derive_tables", "measured_n2c_of_pla", "operating_line", "write_tables"]
