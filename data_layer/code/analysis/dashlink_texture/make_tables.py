"""Render the markdown tables used in the research notes from the results CSVs.

Usage: python -I make_tables.py <results_dir>
Writes tables_param_inventory.md, tables_texture.md, tables_engines.md
"""
import os
import sys
import csv
import collections

import numpy as np


def R(res, f):
    return list(csv.DictReader(open(os.path.join(res, f))))


def g(x, n=4):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return ""
    if not np.isfinite(v):
        return ""
    return f"{v:.{n}g}"


NOTES = {
    "WOW": "inverted: 1 = airborne (verified)", "LGDN": "inverted: 1 above FL150 (gear up), 0 on ground",
    "LGUP": "inverted: 0 above FL150, ~1 on ground", "NSQT": "1 = nose strut extended (airborne); leads WOW by ~6.5 s at lift-off",
    "MSQT_1": "1 only while airborne with gear extended (brief at lift-off, final approach)", "MSQT_2": "as MSQT_1",
    "PH": "codes 0-7 + rare 15 (invalid)", "GMT_SEC": "6-s granularity; constant in 57 records",
    "FRMC": "12-bit counter, +4 per frame, step 3 at wrap (period 4095)", "VAR_1107": "sync word = 0o1107+1; '1' in first frame of 7 short records",
    "VAR_2670": "sync word = 0o2670+1", "VAR_5107": "sync word = 0o5107+1", "VAR_6670": "sync word = 0o6670+1",
    "ESN_1": "262143 (all ones) in first frame of 7 records", "ACID": "755 glitch in first frame of 4 records",
    "DATE_YEAR": "2165 invalid word in 4312 frames (192 records)", "DATE_MONTH": "25 invalid", "DATE_DAY": "45 invalid; legit midnight roll-over",
    "VRTG": "-3.375 g sentinel, periodic bursts", "LATG": "-1.083 g sentinel, periodic bursts", "LONG": "-1.083 g sentinel, periodic bursts",
    "OIT_1": "-390 sentinel", "OIT_2": "-390 sentinel", "OIT_3": "-390 sentinel", "OIT_4": "-390 sentinel",
    "AOAC": "constant within every 120-s ground-idle window", "CAS": "validity-gated: reads 0 below 30 kt", "MACH": "reads 0 below ~0.10", "TAS": "validity-gated: reads 0 below 100 kt",
    "GS": "validity-gated: reads 0 below 50 kt",
    "FPAC": "held 0 on ground", "RALT": "clamped ~5500 ft above range", "FQTY_3": "always 0 (dead channel)",
    "CASM": "held (max airspeed schedule)", "VIB_1": "only 0-0.53 in/s; 98-99 % repeats", "N1C": "127.97 all-ones glitch (2)",
    "TH": "+-179.99 flags are heading-wrap dither, not dropouts", "MH": "wrap dither", "TRK": "wrap dither",
    "TRKM": "wrap dither", "WD": "wrap dither",
    "ELEV_2": "range 41.9-105.9 vs ELEV_1 -41.9-22: inconsistent conversion", "AIL_1": "41.9 floor sentinel",
}


NICE = [1, 10, 100, 1000, 10000, 45, 90, 180, 360, 3, 5, 15, 30, 60, 120, 1.5, 2.5, 25, 250, 2500]


def binary_scaled(lsb):
    """True if LSB = (nice full-scale number) / 2^k for some k (ARINC-429-BNR-like scaling)."""
    try:
        v = float(lsb)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(v) or v <= 0:
        return None
    for k in range(-4, 25):
        fs = v * 2 ** k
        for n in NICE:
            if abs(fs / n - 1) < 2e-4:
                return True
    return False


def main(res):
    P = R(res, "param_table.csv")
    S = R(res, "dropouts_sentinels.csv")
    iso = collections.defaultdict(list)
    for s in S:
        if float(s["isolated_per_record_hour"]) >= 0.05:
            iso[s["param"]].append(f"{float(s['isolated_per_record_hour']):.3g}/h @{float(s['value']):.5g}")
    stuck = collections.Counter(r["param"] for r in R(res, "dropouts_stuck.csv"))
    lines = ["| Param | Description | Units | Hz | Type | Typical range (p1 flight-min .. p99 flight-max) | LSB | Grid reg. | LSB x 4096 | Binary-scaled LSB | Repeats % | Isolated sentinel dropouts | Stuck runs (sibling rule) | Notes |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    xt = collections.Counter()
    for p in P:
        name = p["param"]
        typ = p["type"].replace("integer-continuous", "int-cont").replace("continuous", "cont")
        rng = f"{g(p['p01_flight_min'])} .. {g(p['p99_flight_max'])}"
        if p["type"] == "discrete":
            rng = "{" + p["values_union"].replace(";", ",")[:40] + "}"
        lines.append(f"| {name} | {p['description'][:34]} | {p['units'][:7]} | {g(p['rate_hz'])} | {typ} | {rng} | {g(p['lsb_mode'])} | "
                     f"{g(p['grid_frac_median'], 2)} | {g(p['lsb_x4096'])} | {'' if binary_scaled(p['lsb_mode']) is None or p['type'] == 'discrete' else ('yes' if binary_scaled(p['lsb_mode']) else 'no')} | {g(100 * float(p['frac_held_median']), 3)} | "
                     f"{'; '.join(iso.get(name, []))} | {stuck.get(name, '')} | {NOTES.get(name, '')} |")
        if p["type"] != "discrete" and binary_scaled(p["lsb_mode"]) is not None and float(p["rate_hz"]) >= 1:
            sys_drop = any(float(s["isolated_per_record_hour"]) >= 5 and float(s["frac_isolated_of_eq"]) > 0.5
                           for s in S if s["param"] == name)
            xt[(binary_scaled(p["lsb_mode"]), sys_drop)] += 1
    lines.append("")
    lines.append("Cross-tab (non-discrete parameters >= 1 Hz): (binary-scaled LSB?, systematic sentinel dropouts >= 5/h?) -> count: "
                 + "; ".join(f"{k}: {v}" for k, v in sorted(xt.items())))
    open(os.path.join(res, "tables_param_inventory.md"), "w").write("\n".join(lines) + "\n")
    print(sorted(xt.items()))
    # texture table
    T = R(res, "texture_summary.csv")
    tl = ["| Param | Regime | Windows (flights) | Hz | LSB | sigma/LSB med [IQR] | sigma (units) | resid within 1 LSB | raw within 1 LSB of median | repeats (dx=0) | dx=1 LSB | dx>=2 LSB | lag-1 ACF | tau_1/e resid (s) | tau_1/e linear-detrended (s) | excess kurtosis | frac >4 sd (Gauss 6e-5) | class |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for t in T:
        if t["param"][-2:] in ("_2", "_3", "_4") and t["param"][:2] in ("N1", "N2", "EG", "FF", "OI", "VI"):
            continue
        tl.append(f"| {t['param']} | {t['regime']} | {t['n_windows']} ({t['n_flights']}) | {g(t['rate'])} | {g(t['lsb'])} | "
                  f"{g(t['sigma_lsb_med'], 3)} [{g(t['sigma_lsb_p25'], 2)}-{g(t['sigma_lsb_p75'], 2)}] | {g(t['sigma_phys_med'], 3)} | "
                  f"{g(t['frac_resid_within_1lsb_med'], 2)} | {g(t['frac_raw_within_1lsb_of_median_med'], 2)} | {g(t['dx0_mean'], 2)} | "
                  f"{g(t['dx1_mean'], 2)} | {g(t['dx2plus_mean'], 2)} | {g(t['lag1_acf_med'], 2)} | {g(t['tau_e_resid_s_med'], 2)} | "
                  f"{g(t['tau_e_lin_s_med'], 3)} | {g(t['kurt_excess_med'], 2)} | {g(t['pooled_frac_beyond_4sd'], 2)} | {t['texture_class']} |")
    open(os.path.join(res, "tables_texture.md"), "w").write("\n".join(tl) + "\n")
    # engines table
    E = R(res, "engines_summary.csv")
    el = ["| Regime | Group | LSB | Windows (flights) | Level | Offset eng1..4 (units) | Offset (LSB) | Between-flight SD of offset eng1..4 | Within-flight SD | Independent sd eng1..4 (LSB) | Total resid sd (LSB) | Common-mode fraction | Mean inter-engine resid corr |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for e in E:
        o = ", ".join(g(e[f"offset_med_{i}"], 3) for i in range(1, 5))
        ol = ", ".join(g(e[f"offset_med_lsb_{i}"], 3) for i in range(1, 5))
        b = ", ".join(g(e[f"offset_between_flight_sd_{i}"], 2) for i in range(1, 5))
        w = ", ".join(g(e[f"offset_within_flight_sd_{i}"], 2) for i in range(1, 5))
        ind = ", ".join(g(e[f"indep_sd_lsb_med_{i}"], 2) for i in range(1, 5))
        el.append(f"| {e['regime']} | {e['group']} | {g(e['lsb'])} | {e['n_windows']} ({e['n_flights']}) | {g(e['mean_level'])} | {o} | {ol} | {b} | {w} | {ind} | "
                  f"{g(e['resid_sd_lsb_med'], 3)} | {g(e['common_mode_fraction_med'], 2)} | {g(e['mean_offdiag_corr_med'], 2)} |")
    open(os.path.join(res, "tables_engines.md"), "w").write("\n".join(el) + "\n")
    # misc: clean PLA steps per hour (engine-1 lever only, to avoid 4x counting)
    T = [r for r in R(res, "transients_steps.csv") if r["resp"] == "N1" and r["engine"] == "1"]
    FL = {r["file"]: r for r in R(res, "flight_level.csv")}
    elig = [r["file"] for r in R(res, "eligible_flights.csv")]
    air_h = sum(float(FL[f]["airborne_h"]) for f in elig)
    gnd_h = sum(float(FL[f]["record_h"]) - float(FL[f]["airborne_h"]) for f in elig)
    n_air = sum(1 for r in T if r["airborne"] == "1")
    n_gnd = sum(1 for r in T if r["airborne"] == "0")
    big_air = sum(1 for r in T if r["airborne"] == "1" and abs(float(r["dPLA"])) >= 20)
    misc = [f"clean PLA_1 steps (>=5 deg in 2 s, steady 10 s before / 27 s after), {len(elig)} eligible flights:",
            f"  airborne: {n_air} steps / {air_h:.1f} h = {n_air / air_h:.2f} per airborne hour; >=20 deg: {big_air / air_h:.2f}/h",
            f"  ground  : {n_gnd} steps / {gnd_h:.1f} h = {n_gnd / gnd_h:.2f} per ground hour",
            f"  per flight (median): {np.median([sum(1 for r in T if r['file'] == f) for f in elig]):.0f}"]
    open(os.path.join(res, "tables_misc.md"), "w").write("\n".join(misc) + "\n")
    print("\n".join(misc))
    print("tables written")


if __name__ == "__main__":
    main(sys.argv[1])
