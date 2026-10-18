"""Gain-schedule design for the DFCC replica (Phalanx design; the real Tejas gain tables are not public).

The Tejas control laws are gain-scheduled on Mach and altitude "so that a uniform gain margin is obtained
throughout the flight envelope" (JOAST 58(4) [DIRECT]). The tables are not public, so this module **designs**
them on the M06 airframe model (A-W1.2-22, ASSUMPTION):

- **Pitch** (q / Nz blend, PI): at each (Mach, altitude) grid point the airframe is trimmed at the reference
  mass and linearised (``phalanx.airframe.analysis.short_period``); state feedback on (alpha, q, integral of
  the blended error) is placed by ``scipy.signal.place_poles`` at short-period ``(w_sp, zeta_sp)`` and an
  integrator pole ``p_i``, then converted to the implemented output feedback on measured ``nz`` (with its
  elevon-lift feedthrough) and ``q``. Candidate ``w_sp`` values are tried from fast to slow; the first that
  gives the target margins on the lifted sampled-data loop (``linear.py``: 80 Hz frame, 8 ms delay, 9 Hz
  servo) is kept.
- **Roll** (stability-axis roll-rate command, PI) by pole placement on the one-state roll mode.
- **Yaw** (beta and yaw-rate feedback) by pole placement on the two-state Dutch-roll approximation.

``build_schedule()`` produces the rows of ``configs/tejas/params/M05/gains.csv``; a test re-runs the design
at sample points and checks the committed table (no silent drift between M06 and the M05 gains).
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
from scipy.signal import place_poles

from phalanx.airframe.analysis import (
    Condition,
    lateral,
    reference_mass_properties,
    short_period,
    trim,
)
from phalanx.airframe.build import AirframeConfig

from .linear import Margins, PitchGains, lifted_pitch_loop, margins_discrete

GAIN_COLUMNS = ("g_n", "g_q", "g_i", "g_ff", "g_pr", "g_ir", "g_b", "g_r")


@dataclass(frozen=True)
class DesignSettings:
    """Design inputs. Every field is mirrored by an ``M05.yaml`` parameter (``settings_from_params``)."""

    n_ref: float = 1.0  # g per normalised unit (Nz channel)
    q_ref: float = 0.05  # rad/s per normalised unit (pitch-rate channel)
    blend_m0: float = 0.90
    blend_m1: float = 1.00
    zeta_sp: float = 0.75
    p_i_ratio: float = 0.4  # integrator pole as a fraction of w_sp
    w_sp_candidates: tuple[float, ...] = (3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0)
    zeta_candidates: tuple[float, ...] = (0.75, 0.9)
    p_i_candidates: tuple[float, ...] = (0.25, 0.4, 0.55)
    gm_ref_db: float = 10.0  # score normalisers: score = min(GM / gm_ref, PM / pm_ref)
    pm_ref_deg: float = 60.0
    servo_wn: float = 2.0 * math.pi * 9.0
    servo_zeta: float = 0.7
    frame: float = 1.0 / 80.0
    delay: float = 2.0 / 240.0
    w_roll: float = 4.0
    zeta_roll: float = 0.9
    w_dr_min: float = 2.5
    zeta_dr: float = 0.6
    x_asa: float = 2.0  # ASA station forward of the CG, m
    rsa_wn: float = 2.0 * math.pi * 50.0
    asa_wn: float = 2.0 * math.pi * 100.0
    sensor_zeta: float = 0.7
    g0: float = 9.80665


def blend(mach: float, s: DesignSettings) -> float:
    if mach <= s.blend_m0:
        return 0.0
    if mach >= s.blend_m1:
        return 1.0
    return (mach - s.blend_m0) / (s.blend_m1 - s.blend_m0)


def place_pitch(
    a_sp: np.ndarray,
    b_sp: np.ndarray,
    nz_alpha: float,
    nz_de: float,
    w: float,
    s: DesignSettings,
    w_sp: float,
) -> PitchGains:
    """Pole placement on (alpha, q, z) converted to output feedback on (nz at the ASA, q) and the integrator.

    The ASA reading is ``nz_a alpha + nz_q q + nz_d u`` with the lever-arm terms of ``x_asa`` folded in.
    """
    nz_a = nz_alpha + s.x_asa * a_sp[1, 0] / s.g0
    nz_q = s.x_asa * a_sp[1, 1] / s.g0
    nz_d = nz_de + s.x_asa * b_sp[1] / s.g0
    c_alpha = w * nz_a / s.n_ref
    c_q = w * nz_q / s.n_ref + (1.0 - w) / s.q_ref
    d_y = w * nz_d / s.n_ref
    a = np.zeros((3, 3))
    a[0:2, 0:2] = a_sp
    a[2, 0] = -c_alpha
    a[2, 1] = -c_q
    b = np.array([[b_sp[0]], [b_sp[1]], [-d_y]])
    z = s.zeta_sp
    if z < 0.999:
        wd = w_sp * math.sqrt(1.0 - z * z)
        sp_poles = [-z * w_sp + 1j * wd, -z * w_sp - 1j * wd]
    else:  # critically / over-damped: two distinct real poles
        r = math.sqrt(max(z * z - 1.0, 1e-4))
        sp_poles = [-w_sp * (z + r), -w_sp * (z - r)]
    poles = [*sp_poles, -s.p_i_ratio * w_sp]
    k = place_poles(a, b, poles).gain_matrix[0]  # u = -k x
    # implemented: u = g_n (nz_a alpha + nz_q q + nz_d u) + g_q q + g_i z
    g_n = -k[0] / (nz_a - k[0] * nz_d)
    dd = 1.0 - g_n * nz_d
    g_q = -k[1] * dd - g_n * nz_q
    g_i = -k[2] * dd
    g_ff = g_i / (s.p_i_ratio * w_sp)  # command zero on the integrator pole (step response set by the SP)
    return PitchGains(float(g_n), float(g_q), float(g_i), float(g_ff))


def pitch_margins(sp, gains: PitchGains, w: float, s: DesignSettings) -> Margins:
    ad, bd, cd, dd = lifted_pitch_loop(
        sp.a,
        sp.b,
        sp.nz_alpha,
        sp.nz_de,
        gains,
        w,
        s.n_ref,
        s.q_ref,
        wn=s.servo_wn,
        zeta=s.servo_zeta,
        frame=s.frame,
        delay=s.delay,
        x_asa=s.x_asa,
        g0=s.g0,
        rsa_wn=s.rsa_wn,
        rsa_zeta=s.sensor_zeta,
        asa_wn=s.asa_wn,
        asa_zeta=s.sensor_zeta,
    )
    return margins_discrete(ad, bd, cd, dd, s.frame)


def _score(m: Margins, s: DesignSettings) -> float:
    """min(GM / gm_ref, PM / pm_ref) capped at 1: margins beyond the target earn nothing (no sluggish
    designs)."""
    if not m.stable or not math.isfinite(m.pm_deg):
        return -1.0
    return min(m.gm_db / s.gm_ref_db, m.pm_deg / s.pm_ref_deg, 1.0)


def design_pitch(sp, mach: float, s: DesignSettings) -> tuple[PitchGains, Margins, float]:
    """Best pole set over the candidate grid: highest capped margin score, then the highest short-period
    frequency, then the fastest integrator (deterministic order)."""
    w = blend(mach, s)
    best = None
    for w_sp in s.w_sp_candidates:
        for z in s.zeta_candidates:
            for pir in s.p_i_candidates:
                ss = DesignSettings(**{**s.__dict__, "zeta_sp": z, "p_i_ratio": pir})
                g = place_pitch(sp.a, sp.b, sp.nz_alpha, sp.nz_de, w, ss, w_sp)
                m = pitch_margins(sp, g, w, ss)
                key = (round(_score(m, s), 6), w_sp, pir)
                if best is None or key > best[0]:
                    best = (key, g, m, w_sp)
    assert best is not None
    return best[1], best[2], best[3]


def design_lateral(lat, s: DesignSettings) -> tuple[float, float, float, float]:
    """(g_pr, g_ir, g_b, g_r) from the body-axis lateral derivatives (rows beta_dot, p_dot, r_dot)."""
    a, b = lat.a, lat.b
    l_p, l_da = a[1, 1], b[1, 0]
    g_pr = (2.0 * s.zeta_roll * s.w_roll + l_p) / l_da
    g_ir = s.w_roll**2 / l_da
    y_b, n_b, n_r, n_dr = a[0, 0], a[2, 0], a[2, 2], b[2, 1]
    w_open = math.sqrt(max(n_b + y_b * n_r, 0.0))
    w_dr = max(w_open, s.w_dr_min)
    g_r = (-2.0 * s.zeta_dr * w_dr - y_b - n_r) / n_dr
    g_b = (w_dr**2 - n_b - y_b * (n_r + n_dr * g_r)) / n_dr
    return float(g_pr), float(g_ir), float(g_b), float(g_r)


def design_point(
    cfg: AirframeConfig,
    ps,
    mach: float,
    alt: float,
    s: DesignSettings,
    *,
    alpha_feasible: float = math.radians(20.0),
    gear: float = 0.0,
    force_w: float | None = None,
) -> tuple[dict[str, float], Margins, float, bool]:
    """Gains at one (Mach, altitude) point at the reference mass. ``ok`` is False when the trim AoA exceeds
    ``alpha_feasible`` or the designed loop is not stable (the caller then falls back to a neighbour)."""
    mass, cg, inertia = reference_mass_properties(ps)
    cond = Condition(alt, mach, mass, cg, inertia, gear=gear)
    guess = (0.05 if mach > 0.5 else 0.2, 0.0, 30000.0)
    tr = trim(cfg, cond, guess=guess)
    sp = short_period(cfg, cond, tr)
    if force_w is None:
        g, m, w_sp = design_pitch(sp, mach, s)
    else:  # fixed-gain reversion: pitch-rate command (w = 0), no Mach information
        ss = DesignSettings(**{**s.__dict__, "blend_m0": 9.0, "blend_m1": 10.0})
        g, m, w_sp = design_pitch(sp, 0.0, ss)
    lat = lateral(cfg, cond, tr)
    g_pr, g_ir, g_b, g_r = design_lateral(lat, s)
    # usable only inside the AoA band and when the margin template (>= 6 dB / 35 deg, JOAST 58(4)) is met
    ok = abs(tr.alpha) < alpha_feasible and m.stable and m.gm_db >= 6.0 and m.pm_deg >= 35.0
    gains = {
        "g_n": g.g_n,
        "g_q": g.g_q,
        "g_i": g.g_i,
        "g_ff": g.g_ff,
        "g_pr": g_pr,
        "g_ir": g_ir,
        "g_b": g_b,
        "g_r": g_r,
    }
    return gains, m, w_sp, ok


def build_schedule(
    cfg: AirframeConfig,
    ps,
    machs: Iterable[float],
    alts: Iterable[float],
    s: DesignSettings | None = None,
    *,
    alpha_feasible: float = math.radians(20.0),
) -> list[dict[str, float]]:
    """Gain rows over the (Mach, altitude) grid; infeasible points copy the nearest lower-altitude row."""
    s = s or DesignSettings()
    rows = []
    for mach in machs:
        prev = None
        for alt in alts:
            try:
                gains, m, w_sp, ok = design_point(cfg, ps, mach, alt, s, alpha_feasible=alpha_feasible)
            except RuntimeError:
                gains, m, w_sp, ok = {}, None, math.nan, False
            if not ok and prev is not None:
                gains = dict(prev)
            elif not ok and not gains:
                raise RuntimeError(f"no feasible design at M{mach} {alt} m and no lower-altitude fallback")
            row = {"mach": mach, "alt": alt, **gains}
            row["w_sp"] = w_sp if ok else -1.0
            row["gm_db"] = m.gm_db if (m is not None and ok) else -1.0
            row["pm_deg"] = m.pm_deg if (m is not None and ok) else -1.0
            row["feasible"] = 1.0 if ok else 0.0
            rows.append(row)
            prev = {k: row[k] for k in GAIN_COLUMNS}
    return rows


def write_csv(path, rows: list[dict[str, float]], columns: tuple[str, ...]) -> None:
    lines = [",".join(columns)]
    for r in rows:
        lines.append(",".join(repr(float(r[c])) for c in columns))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> None:
    """Regenerate ``M05/gains.csv`` and ``M05/fixed_gains.csv`` (deterministic; ~3-5 min).

    Usage (from the checkout): ``python -I -c "import sys; sys.path.insert(0, 'src');
    from phalanx.fcs.design import main; main(['configs/tejas/params'])"``
    """
    import argparse
    from pathlib import Path

    from phalanx.airframe.build import airframe_param_set, build_config

    from .build import fcs_param_set, settings_from_params

    ap = argparse.ArgumentParser(description=main.__doc__)
    ap.add_argument("params_dir", type=Path)
    a = ap.parse_args(argv)
    root = a.params_dir.resolve().parent.parent  # configs/
    fps = fcs_param_set("tejas", root)
    s = settings_from_params(fps)
    aps = airframe_param_set("tejas", root)
    cfg = build_config(aps, 1)
    afeas = float(fps.value("alpha_feasible"))
    rows = build_schedule(
        cfg, aps, list(fps.value("grid_mach")), list(fps.value("grid_alt")), s, alpha_feasible=afeas
    )
    out = a.params_dir / "M05"
    write_csv(out / "gains.csv", rows, ("mach", "alt", *GAIN_COLUMNS, "w_sp", "gm_db", "pm_deg", "feasible"))
    fixed = []
    for name, gear in (("up", 0.0), ("down", 1.0)):
        gains, m, _w_sp, ok = design_point(
            cfg,
            aps,
            float(fps.value(f"fixed_{name}_mach")),
            float(fps.value(f"fixed_{name}_alt")),
            s,
            gear=gear,
            force_w=0.0,
        )
        if not ok:
            raise RuntimeError(f"fixed-gain design point ({name}) is not feasible")
        fixed.append({**gains, "gear": gear, "gm_db": m.gm_db, "pm_deg": m.pm_deg})
    write_csv(out / "fixed_gains.csv", fixed, ("gear", *GAIN_COLUMNS, "gm_db", "pm_deg"))
