"""B7 progression laws in usage mode (PREREGISTRATION.md §3): the real M10 advanced by ``health.sortie`` events.

- B7-ENG-ERO-RATE: 100 engine serials, 5,000 flights at fighter severity S = 1 (the commercial reference the
  anchors are quoted for): HPC efficiency loss vs ProDiMES -5 % at 5,000 flights with Gamma/eta = 1.8; HPT
  efficiency loss at 3,000 cycles vs C-MAPSS -2.6 %.
- B7-ENG-FOUL-RATE: 100 serials, 500 EOT h at dust index 1: fouling vs Kurz & Brun ~1 %; a wash removes rho.
- B7-HYD-PUMP-TIME: 100 tails (200 pump serials), one sortie a day for 600 days: end of the flat period and
  time to the wear limit vs US 12,265,000 (flat ~5 months, limit ~11.5 months).
- B7-LG-BRAKE / B7-LG-TYRE (M10 surrogate): 20 tails, 2,000 one-landing sorties at the reference brake energy:
  life = 1 / mean wear per landing.

Sample sizes: 100 engine serials give the mean's relative SE below 2 % for the erosion gamma process (CV 0.3 at
1,000 flights) and 100 pumps the median's SE below 3 % for a CV 0.3 incubation; the brake/tyre surrogate means
are over 40,000 wheel-landings.

Usage: python -I progression.py OUT_DIR
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from phalanx.core.events import Event  # noqa: E402
from phalanx.core.rng import KeyPath, RngService, StreamRegistry  # noqa: E402
from phalanx.core.scheduler import System  # noqa: E402
from phalanx.dictionary import load_dictionary  # noqa: E402
from phalanx.health import (  # noqa: E402
    AIRFRAME_NAMES,
    HealthConfig,
    HealthModule,
    SortieUsage,
    load_health_params,
    sensor_bias_channels,
)
from phalanx.health.module import ENG_F  # noqa: E402

NS = 10**9
DAY = 86_400 * NS
D = load_dictionary()
P = load_health_params()
_AIR = {n: j for j, n in enumerate(AIRFRAME_NAMES)}


def _usage(sid: str, n: int, *, eot: float, landings: float = 1.0, dust: float = 1.0) -> SortieUsage:
    def one(v: float) -> tuple[float, ...]:
        return (v,) * n

    return SortieUsage(
        sortie_id=sid,
        flight_time_s=eot,
        eot_s=one(eot),
        tamp_s=one(0.0),
        type1=one(1.0),
        type3=one(3.0),
        type4=one(3.0),
        eftc=one(1.1),
        src_h=one(0.0),
        ps3_full=one(1.0),
        ps3_partial=one(3.0),
        ab_lights=one(0.0),
        starts=one(1.0),
        landings=landings,
        dust=dust,
    )


def _system(params, serials, tail: str, scenario: str):
    m = HealthModule("health", params, config=HealthConfig(tuple(serials), sensor_bias_channels(D), tail_no=tail))
    sysm = System([m], [], rng=RngService(0xB7, StreamRegistry()), identity=KeyPath.of(scenario=scenario, tail=tail))
    return m, sysm


def _fly(sysm, w, usages, dt_days: float = 1.0, record=None):
    """Fly the sortie usages one per ``dt_days``; ``record(k, state)`` after each sortie."""
    for k, u in enumerate(usages):
        t = w.t_ns + int(dt_days * DAY)
        w = sysm.inject(w, [Event(t, "health.sortie", "health", u.to_payload())])
        w, _ = sysm.run(w, (t * 240) // NS + 2 - w.k)
        if record is not None:
            record(k, w.states["health"])
    return w


def erosion_and_fouling(n: int = 100) -> dict:
    serials = [f"IN20-R{k:03d}" for k in range(n)]
    p1 = P.replace(severity_s=1.0)
    _, sysm = _system(p1, serials, "KH2011", "B7ERO")
    w = sysm.start()
    f0 = w.states["health"]["eng_f"].copy()
    snap = {}

    def rec(k, st):
        if k + 1 in (3000, 5000):
            snap[k + 1] = st["eng_f"].copy()

    _fly(sysm, w, (_usage(f"E{k}", n, eot=3600.0, dust=1.0) for k in range(5000)), dt_days=0.5, record=rec)
    out = {}
    for flights in (3000, 5000):
        f = snap[flights]
        hpc = f[:, ENG_F.index["ero_hpc"]] - f0[:, ENG_F.index["ero_hpc"]]
        hpt = f[:, ENG_F.index["ero_hpt"]] - f0[:, ENG_F.index["ero_hpt"]]
        out[f"{flights}_flights"] = {
            "hpc_eta_loss_mean": float(hpc.mean()),
            "hpc_eta_loss_sd": float(hpc.std(ddof=1)),
            "hpc_gamma_over_eta": float(P.value("erosion_flow_ratio_hpc")),
            "hpt_eta_loss_mean": float(hpt.mean()),
            "hpt_eta_loss_sd": float(hpt.std(ddof=1)),
        }
    # fouling over 500 EOT h at dust index 1: read off the 5,000-flight run's first 500 h is not separable
    # (washes are absent), so a separate short run
    _, sysm2 = _system(P, serials, "KH2012", "B7FOUL")
    w2 = sysm2.start()
    g0 = w2.states["health"]["eng_f"].copy()
    w2 = _fly(sysm2, w2, (_usage(f"F{k}", n, eot=3600.0, dust=1.0) for k in range(500)), dt_days=0.5)
    g = w2.states["health"]["eng_f"]
    foul = np.r_[g[:, ENG_F.index["foul_fan"]] - g0[:, ENG_F.index["foul_fan"]],
                 g[:, ENG_F.index["foul_hpc"]] - g0[:, ENG_F.index["foul_hpc"]]]
    out["fouling_500h"] = {"mean": float(foul.mean()), "sd": float(foul.std(ddof=1)), "n": int(foul.size)}
    return out


def pump_timing(n_tails: int = 100, days: int = 600) -> dict:
    flat_end, limit = [], []
    for k in range(n_tails):
        tail = f"P{k:03d}"
        _, sysm = _system(P, ("IN20-P",), tail, "B7PUMP")
        w = sysm.start()
        first = {0: None, 1: None}
        full = {0: None, 1: None}

        def rec(d, st, first=first, full=full):
            for h, name in ((0, "hyd1_pump_wear"), (1, "hyd2_pump_wear")):
                v = float(st["air"][_AIR[name]])
                if first[h] is None and v > 0.0:
                    first[h] = d
                if full[h] is None and v >= 1.0:
                    full[h] = d

        _fly(sysm, w, (_usage(f"{tail}-{d}", 1, eot=3600.0) for d in range(days)), dt_days=1.0, record=rec)
        for h in (0, 1):
            flat_end.append(first[h] if first[h] is not None else np.nan)
            limit.append(full[h] if full[h] is not None else np.nan)
    fe, li = np.array(flat_end, float), np.array(limit, float)
    return {
        "n_pumps": int(fe.size),
        "flat_end_median_days": float(np.nanmedian(fe)),
        "limit_median_days": float(np.nanmedian(li)),
        "limit_not_reached": int(np.isnan(li).sum()),
        "flat_end_q10_q90": [float(np.nanpercentile(fe, 10)), float(np.nanpercentile(fe, 90))],
        "limit_q10_q90": [float(np.nanpercentile(li, 10)), float(np.nanpercentile(li, 90))],
    }


def brake_tyre(n_tails: int = 20, landings: int = 2000) -> dict:
    wear = {"brake_wear_l": [], "brake_wear_r": [], "tyre_wear_l": [], "tyre_wear_r": []}
    for k in range(n_tails):
        tail = f"B{k:03d}"
        _, sysm = _system(P, ("IN20-B",), tail, "B7LG")
        w = sysm.start()
        a0 = w.states["health"]["air"].copy()
        w = _fly(sysm, w, (_usage(f"{tail}-{d}", 1, eot=1800.0) for d in range(landings)), dt_days=0.25)
        a = w.states["health"]["air"]
        for name in wear:
            wear[name].append(float(a[_AIR[name]] - a0[_AIR[name]]) / landings)
    br = np.r_[wear["brake_wear_l"], wear["brake_wear_r"]]
    ty = np.r_[wear["tyre_wear_l"], wear["tyre_wear_r"]]
    return {
        "brake_wear_per_landing": float(br.mean()),
        "brake_life_landings": float(1.0 / br.mean()),
        "tyre_wear_per_landing": float(ty.mean()),
        "tyre_life_landings": float(1.0 / ty.mean()),
        "n_wheels": int(br.size),
        "landings_per_wheel": landings,
    }


def spall(max_sorties: int = 80) -> dict:
    """B7-OIL-SPALL: an incipient spall (M10's initiation size, seeded through ``health.fault``) grown by the
    real M10 over 1-h sorties to the critical length. The growth law is deterministic (no draw), so one engine
    answers it (n = 1; the CRN identity is fixed). Per sortie: growth rate (mm/h) and debris per mm of growth."""
    _, sysm = _system(P, ("IN20-S",), "SP001", "B7SPALL")
    w = sysm.start()
    l0 = float(P.value("bearing_l0"))  # SI (m)
    seed = Event(DAY // 2, "health.fault", "health", {"state": "eng:spall_len", "delta": l0, "op": "set"})
    w = sysm.inject(w, [seed])
    w, _ = sysm.run(w, (DAY // 2 * 240) // NS + 2 - w.k)  # the seed lands before the first sortie
    crit = float(P.value("spall_critical"))
    rows = []
    h = 0.0
    for k in range(max_sorties):
        f0 = w.states["health"]["eng_f"][0].copy()
        w = _fly(sysm, w, [_usage(f"S{k}", 1, eot=3600.0)], dt_days=1.0)
        f1 = w.states["health"]["eng_f"][0]
        h += 1.0
        l_a, l_b = float(f0[ENG_F.index["spall_len"]]), float(f1[ENG_F.index["spall_len"]])
        dd = float(f1[ENG_F.index["debris"]] - f1[ENG_F.index["debris_wear"]]) - float(
            f0[ENG_F.index["debris"]] - f0[ENG_F.index["debris_wear"]]
        )
        rows.append({"eot_h": h, "len_before_mm": l_a * 1e3, "len_after_mm": l_b * 1e3, "spall_debris_mg": dd * 1e6})
        if l_b >= crit:
            break
    band = [r for r in rows if r["len_before_mm"] >= 0.8 and r["len_after_mm"] <= 3.4]
    rates = [r["len_after_mm"] - r["len_before_mm"] for r in band]  # mm per 1-h sortie
    per_mm = [r["spall_debris_mg"] / (r["len_after_mm"] - r["len_before_mm"]) for r in rows if r["len_after_mm"] > r["len_before_mm"]]
    reach = next((r["eot_h"] for r in rows if r["len_after_mm"] >= crit * 1e3), None)
    return {
        "n_engines": 1,
        "l0_mm": rows[0]["len_before_mm"] if rows else None,
        "critical_mm": crit * 1e3,
        "growth_mm_per_h_in_0.8_3.4mm": {"n_sorties": len(rates), "min": min(rates), "max": max(rates)},
        "growth_verdict": "PASS" if rates and all(0.08 <= x <= 0.34 for x in rates) else "FAIL",
        "debris_mg_per_mm": {"min": min(per_mm), "max": max(per_mm)},
        "debris_verdict": "PASS" if per_mm and all(2.0 <= x <= 50.0 for x in per_mm) else "FAIL",
        "eot_h_initiation_to_critical": reach,
        "rows": rows,
    }


def main(argv: list[str]) -> int:
    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)
    if argv[1:] == ["spall"]:  # B7-OIL-SPALL (pre-registered; run separately from the progression fleets)
        res = {"spall": spall()}
        (out / "b7_spall.json").write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8")
        print(json.dumps({k: v for k, v in res["spall"].items() if k != "rows"}, indent=1))
        return 0
    if argv[1:] == ["erosion"]:  # DEVIATIONS D2: the erosion check after the base-rate correction
        res = {"erosion_fouling": erosion_and_fouling()}
        (out / "b7_progression_d2.json").write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8")
        print(json.dumps(res, indent=1))
        return 0
    res = {"erosion_fouling": erosion_and_fouling(), "pump": pump_timing(), "brake_tyre": brake_tyre()}
    (out / "b7_progression.json").write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
