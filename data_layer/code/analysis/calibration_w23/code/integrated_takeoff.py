"""W2.3a item 1 in the integrated aircraft (coordinator, 2026-10-15): gate sortie 2 (TJ213) from post-start
idle through the ground segments and the take-off acceleration; idle extraction, idle governing, roll-back.

Records (1 s means of 240 Hz, and the 1 s minimum of N2): N2, N1, T5, Wf, PS3, PLA, M08 regulator (1 s mode),
M09 PTO and bleed, M07 stall margin, scenario phase, TAS. Reports
- ``idle_long``: the longest ground-idle segment (PLA < 25 deg) after its first quarter: mean N2, N2 peak to
  peak over its last 60 s (idle governing), PTO/bleed mean and maximum, mean Wf/PS3 (lb/h/psi), minimum
  stall margin, regulators;
- ``at_slam``: the idle 5 s before the throttle reaches IRP (PLA >= 86 deg): N2, PTO, bleed, Wf/PS3;
- ``after_irp``: the 20 s from the throttle reaching IRP: N2 minimum (of the 240 Hz samples), N2 and N1 at
  the end, the first second N1 reaches 100 %, regulators, T5 maximum.
Deterministic (gate scenario root 0xA5, the W2.1a take-off test's). Sample: n = 1 sortie window, the one the
coordinator's observation (ENG-506) came from.

Usage: python -I integrated_takeoff.py OUT.json [max_s] [SERIES.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

PORTS = ["eng.n2", "eng.n1", "eng.t5", "eng.wf", "eng.ps3", "pilot.pla", "fadec.active_limiter",
         "util.pto_power", "util.bleed_extract", "eng.stall_margin", "scenario.phase", "af.tas"]  # fmt: skip
N1R, N2R = 13270.0 * 2 * np.pi / 60, 16810.0 * 2 * np.pi / 60
RU = 3600 / 0.45359237 * 6894.757  # (kg/s)/Pa -> (lb/h)/psi


def run(max_s: int) -> dict[str, np.ndarray]:
    from phalanx.integration.plans import gate_sorties
    from phalanx.integration.sortie import SortieRunner
    from phalanx.integration.system import SortieSpec, build_sortie_system

    ss = build_sortie_system(SortieSpec(plan=gate_sorties()[1], scenario="gate", root=0xA5))
    r = SortieRunner(ss, validate_events=False, record=PORTS)
    st = r.begin()
    rows = {p: [] for p in PORTS}
    n2_min = []
    while st.world.k < max_s * 240:
        st, outs = r.run(st, 240)
        c = outs[0]
        for p in PORTS:
            a = np.asarray(c.trace.ports[p], float).reshape(240, -1)[:, 0]
            if p in ("fadec.active_limiter", "scenario.phase"):  # 1 s mode (regulator code: low 4 bits)
                mask = 15 if p == "fadec.active_limiter" else -1
                rows[p].append(np.bincount(a.astype(np.int64) & mask).argmax())
            else:
                rows[p].append(a.mean())
        n2_min.append(float(np.asarray(c.trace.ports["eng.n2"]).min()))
    d = {p: np.array(v, float) for p, v in rows.items()}
    d["n2_min"] = np.array(n2_min)
    return d


def summarise(d: dict[str, np.ndarray]) -> dict:
    pla = np.degrees(d["pilot.pla"])
    lim = d["fadec.active_limiter"].astype(np.int64)
    out: dict = {}
    idle = np.flatnonzero(pla < 25.0)
    if idle.size:
        segs = np.split(idle, np.flatnonzero(np.diff(idle) > 1) + 1)
        long = max(segs, key=len)
        w = long[len(long) // 4 :]  # the steady part of the longest idle segment (skip the start transient)
        n2 = d["eng.n2"][w] / N2R * 100
        out["idle_long"] = {
            "t0_s": int(long[0]),
            "t1_s": int(long[-1]),
            "n2_pct": round(float(n2.mean()), 3),
            "n2_p2p_last_60s_pct": round(float(np.ptp(n2[-60:])), 3),
            "pto_kw": round(float(d["util.pto_power"][w].mean() / 1e3), 2),
            "pto_kw_max": round(float(d["util.pto_power"][w].max() / 1e3), 2),
            "bleed_kgs": round(float(d["util.bleed_extract"][w].mean()), 4),
            "bleed_kgs_max": round(float(d["util.bleed_extract"][w].max()), 4),
            "wf_ps3_pph_psi": round(float((d["eng.wf"][w] / d["eng.ps3"][w]).mean() * RU), 3),
            "stall_margin_min": round(float(d["eng.stall_margin"][w].min()), 4),
            "regulators": sorted({int(x) for x in lim[w]}),
        }
    if np.any(pla >= 86.0):
        k = int(np.argmax(pla >= 86.0))
        pre = [j for j in range(max(0, k - 5), k) if pla[j] < 25.0]
        if pre:
            out["at_slam"] = {
                "t_s": k,
                "n2_pct": round(float(d["eng.n2"][pre].mean() / N2R * 100), 3),
                "pto_kw": round(float(d["util.pto_power"][pre].mean() / 1e3), 2),
                "bleed_kgs": round(float(d["util.bleed_extract"][pre].mean()), 4),
                "wf_ps3_pph_psi": round(float((d["eng.wf"][pre] / d["eng.ps3"][pre]).mean() * RU), 3),
            }
        w = slice(k, min(k + 20, len(pla)))
        n1 = d["eng.n1"][w] / N1R
        t100 = np.flatnonzero(n1 >= 1.0)
        out["after_irp"] = {
            "n2_min_pct": round(float(d["n2_min"][w].min() / N2R * 100), 3),
            "n2_end_pct": round(float(d["eng.n2"][w][-1] / N2R * 100), 3),
            "n1_end_pct": round(float(n1[-1] * 100), 3),
            "t_n1_100pct_s": int(t100[0]) if t100.size else None,
            "regulators": sorted({int(x) for x in lim[w]}),
            "t5_max_k": round(float(d["eng.t5"][w].max()), 1),
        }
    return out


def main(argv: list[str]) -> None:
    max_s = int(argv[1]) if len(argv) > 1 else 1100
    d = run(max_s)
    out = summarise(d)
    print(json.dumps(out, indent=1))
    Path(argv[0]).parent.mkdir(parents=True, exist_ok=True)
    Path(argv[0]).write_text(json.dumps(out, indent=1) + "\n")
    if len(argv) > 2:
        Path(argv[2]).write_text(json.dumps({p: np.round(v, 5).tolist() for p, v in d.items()}))


if __name__ == "__main__":
    main(sys.argv[1:])
