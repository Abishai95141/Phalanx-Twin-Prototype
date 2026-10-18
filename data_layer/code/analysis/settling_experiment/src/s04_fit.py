"""Step 4 -- fit the texture model levels L0..L6, L6' and the T2 fleet prior on 687-CAL ONLY.

Parameters are estimated in the measured-residual domain (residual = cleaned real - low-pass) and the
noise scales / AR coefficients / common-mode scales / tail mixtures are calibrated by simulation on a fixed
subset of 50 CAL flights (method of simulated moments: generate with the current parameters, re-measure
with the identical pipeline, update multiplicatively), so that each level reproduces the CAL moments it is
meant to reproduce. Targets:
  pooled residual SD per (channel, regime)            -> sigma            (L0..L4)
  mean off-diagonal 4-engine residual covariance      -> common-mode scale (L2..L4)
  median W64 lag-1 ACF per channel / of family mean   -> phi_ind / phi_cm   (L2..L4)
  median W64 excess kurtosis and 4-sigma exceedance   -> tail (p, k) grid   (L4)
Empirical (not calibrated): power-bin multipliers, segment log-SD spread (L3); gating thresholds,
glitch rates, freeze rates/durations (L5); slip parameters from the mechanism check on CAL (L6);
old Gilbert-Elliott parameters by the dropout_bursts.py method on CAL (L6'); T2 fleet prior.

Usage: python -I s04_fit.py <mat687_dir> <texture_results_dir> <results_dir> [n_workers]
Writes results/model_params_<fc>.json, results/fit_report_<fc>.json
"""
import csv
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
from dlio import load_flight, parse_fname, robust_sigma  # noqa: E402
from common import regime_windows, engine_ok, read_csv  # noqa: E402
from pipeline import Pipe, regimes  # noqa: E402
from texture_model import Generator, N1_EDGES, CAS_EDGES  # noqa: E402
import fitstats as FS  # noqa: E402

TAILS_P = [0.005, 0.02, 0.06]
TAILS_K = [1.5, 2.0, 3.0, 4.5, 7.0]
G = None  # worker globals


def winit(tex_res, lattice):
    global G
    G = {"pipe": Pipe(tex_res, lattice), "tex": tex_res}


# ---------------------------------------------------------------- pass A (real CAL)
def pass_a(path):
    pipe = G["pipe"]
    F = load_flight(path)
    fid = C.flight_id(path)
    lab, tat, cas = regimes(F)
    out = {"fid": fid, "stats": {}}
    for fk in C.FC:
        ctx = FS.build_ctx(F, pipe, fk, lab, cas)
        res = {ch: ctx[ch]["xc"] - ctx[ch]["truth"] for ch in C.GROUP}
        out["stats"][fk] = FS.flight_stats(res, ctx, pipe, fid, with_segments=True)
    # ----- fixed-parameter data
    fx = {}
    fx["vrtg_unique"] = np.unique(F["VRTG"].x)
    fx["record_h"] = F["PH"].x.size / 3600.0
    air = F["WOW"].x == 1
    fx["air_h"] = air.sum() / 3600.0
    fx["minnz"] = {ch: float(F[ch].x[F[ch].x > 0].min()) if (F[ch].x > 0).any() else np.nan for ch in C.ENG}
    # freezes: sibling rule (engines), single-channel rule (VRTG), airborne only
    fz = {}
    for f in C.FAMILIES:
        X = [F[f"{f}_{k}"].x for k in range(1, 5)]
        L = pipe.lsb[f"{f}_1"]
        n = X[0].size
        airs = np.repeat(air, 4)[:n] if air.size * 4 >= n else np.r_[np.repeat(air, 4), np.zeros(n - air.size * 4, bool)]
        for k in range(4):
            x = X[k]
            same = np.r_[False, x[1:] == x[:-1]]
            d = np.diff(np.r_[0, (same & airs).astype(int), 0])
            st, en = np.flatnonzero(d == 1) - 1, np.flatnonzero(d == -1)
            dur = []
            for a, b in zip(st, en):
                if (b - a) / 4 < 30:
                    continue
                if all(np.ptp(X[j][a:b]) >= 5 * L for j in range(4) if j != k):
                    dur.append((b - a) / 4)
            fz[f"{f}_{k + 1}"] = dur
    v = F["VRTG"].x
    airv = np.repeat(air, 8)[:v.size]
    same = np.r_[False, v[1:] == v[:-1]] & airv
    d = np.diff(np.r_[0, same.astype(int), 0])
    fz["VRTG"] = [(b - a + 1) / 8 for a, b in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)) if (b - a + 1) / 8 >= 10]
    fx["freeze"] = fz
    # glitch words: isolated samples equal to the parameter's archive-wide maximum
    gl = {}
    for ch in C.GROUP:
        x = F[ch].x
        gmax = G["gmax"][ch]
        m = x == gmax
        if m.any():
            J = max(10 * pipe.lsb[ch], 5 * np.nan_to_num(robust_sigma(np.diff(x))))
            prev, nxt = np.r_[np.nan, x[:-1]], np.r_[x[1:], np.nan]
            gl[ch] = int(np.sum(m & (np.abs(x - prev) > J) & (np.abs(x - nxt) > J)))
        else:
            gl[ch] = 0
    fx["glitch"] = gl
    # T2 fleet prior: per steady window, per family, engine offsets vs 4-engine mean
    meta = parse_fname(path)
    day = (np.datetime64(f"{meta['year']:04d}-{meta['month']:02d}-{meta['day']:02d}") - np.datetime64("2001-01-01")).astype(int)
    rows = []
    for reg, wl in regime_windows(F).items():
        for (t0, t1) in wl:
            if reg == "ground_idle" and not all(engine_ok(F, e, t0, t1, reg) for e in range(1, 5)):
                continue
            for f in C.FAMILIES:
                m = [float(np.mean(F[f"{f}_{k}"].x[int(t0 * 4):int(t1 * 4)])) for k in range(1, 5)]
                rows.append((f, reg, fid, day, float(np.mean(m))) + tuple(mi - np.mean(m) for mi in m))
    fx["t2rows"] = rows
    # old Gilbert-Elliott (dropout_bursts.py method) for VRTG
    sv = -3.375
    m = np.abs(v - sv) <= 1e-6 * 3.375
    J = max(10 * pipe.lsb["VRTG"], 5 * np.nan_to_num(robust_sigma(np.diff(v))))
    prev, nxt = np.r_[np.nan, v[:-1]], np.r_[v[1:], np.nan]
    iso = np.flatnonzero(m & (np.abs(v - prev) > J) & (np.abs(v - nxt) > J))
    nsec = v.size // 8
    ev = np.bincount(iso[iso < nsec * 8] // 8, minlength=nsec)
    idx = np.flatnonzero(ev > 0)
    bd, starts, ein = [], [], 0
    if idx.size:
        for b in np.split(idx, np.flatnonzero(np.diff(idx) > 10) + 1):
            if b.size >= 2:
                bd.append(int(b[-1] - b[0] + 1))
                starts.append(int(b[0]))
                ein += int(ev[b[0]:b[-1] + 1].sum())
    fx["ge"] = {"dur": bd, "start_int": np.diff(starts).tolist(), "ev_in": ein, "ev_tot": int(ev.sum()),
                "sec_in": int(sum(bd)), "sec_tot": int(nsec)}
    out["fixed"] = fx
    return out


# ---------------------------------------------------------------- calibration worker
def sim_stats(args):
    path, fk, level, params = args
    pipe = G["pipe"]
    F = load_flight(path)
    fid = C.flight_id(path)
    ctx = FS.build_ctx(F, pipe, fk)
    gen = Generator(pipe, params)
    arrays = gen.generate(ctx, level, fid, arm="T1")
    res = FS.residuals(arrays, ctx, pipe, fk)
    return FS.flight_stats(res, ctx, pipe, fid)


def run_sim(pool, paths, fk, level, params):
    st = pool.map(sim_stats, [(p, fk, level, params) for p in paths], chunksize=1)
    return FS.summary(FS.merge(st))


def ratio(t, s, lo=1 / 3, hi=3.0):
    if not (np.isfinite(t) and np.isfinite(s)) or s <= 0 or t <= 0:
        return 1.0
    return float(np.clip(t / s, lo, hi))


def calibrate(pool, paths, paths_small, fk, T, emp, fixed, log):
    """Calibrate L0..L4 for one cut-off key. Returns {level: params}."""
    levels = {}
    sig = {ch: {r: (T["sd"][ch][r] if np.isfinite(T["sd"][ch][r]) else np.nanmedian(list(T["sd"][ch].values())))
                for r in map(str, range(7))} for ch in C.GROUP}
    nb = {ch: (len(CAS_EDGES) + 1 if ch == C.VRTG else len(N1_EDGES) + 1) for ch in C.GROUP}
    ones = {ch: np.ones((7, nb[ch])).tolist() for ch in C.GROUP}
    base = {"sigma": sig, "phi_ind": {ch: 0.0 for ch in C.GROUP}, "phi_cm": {f: 0.0 for f in C.FAMILIES},
            "cm_scale": {f: {str(r): 0.0 for r in range(7)} for f in C.FAMILIES},
            "pow_mult": ones, "pow_mult_cm": {f: np.ones((7, len(N1_EDGES) + 1)).tolist() for f in C.FAMILIES},
            "seg_sd": {k: {str(r): 0.0 for r in range(7)} for k in C.FAMILIES + [C.VRTG]},
            "tail": {ch: [0.0, 1.0] for ch in C.GROUP}, "tail_cm": {f: [0.0, 1.0] for f in C.FAMILIES}}

    def params_for(lv, lp):
        return {"levels": {lv: lp}, "fixed": fixed, "fc": C.FC[fk]}

    def update(lp, S, ar=False):
        for ch in C.GROUP:
            for r in map(str, range(7)):
                lp["sigma"][ch][r] *= ratio(T["sd"][ch][r], S["sd"][ch][r])
            if ar:
                if np.isfinite(T["acf1"][ch]) and np.isfinite(S["acf1"][ch]):
                    lp["phi_ind"][ch] = float(np.clip(lp["phi_ind"][ch] + 0.8 * (T["acf1"][ch] - S["acf1"][ch]), 0.0, 0.98))
        if ar:
            for f in C.FAMILIES:
                for r in map(str, range(7)):
                    t, s = T["cov"][f][r], S["cov"][f][r]
                    if not np.isfinite(t) or t <= 0:
                        lp["cm_scale"][f][r] = 0.0
                    elif np.isfinite(s) and s > 0:
                        lp["cm_scale"][f][r] *= float(np.clip(np.sqrt(t / s), 1 / 3, 3.0))
                    else:
                        lp["cm_scale"][f][r] = max(lp["cm_scale"][f][r], np.sqrt(t))
                if np.isfinite(T["acf1_mean"][f]) and np.isfinite(S["acf1_mean"][f]):
                    lp["phi_cm"][f] = float(np.clip(lp["phi_cm"][f] + 0.8 * (T["acf1_mean"][f] - S["acf1_mean"][f]), 0.0, 0.98))

    def err(S):
        e = []
        for ch in C.GROUP:
            for r in map(str, range(7)):
                if np.isfinite(T["sd"][ch][r]) and np.isfinite(S["sd"][ch][r]) and T["sd"][ch][r] > 0:
                    e.append(abs(np.log(max(S["sd"][ch][r], 1e-12) / T["sd"][ch][r])))
        return float(np.median(e)), float(np.percentile(e, 90))

    import copy
    # ---------------- L0 / L1
    for lv, iters in (("L0", 3), ("L1", 5)):
        lp = copy.deepcopy(base) if lv == "L0" else copy.deepcopy(levels["L0"])
        for it in range(iters):
            S = run_sim(pool, paths, fk, lv, params_for(lv, lp))
            log.append({"fc": fk, "level": lv, "iter": it, "sd_logerr_med_p90": err(S)})
            update(lp, S)
        S = run_sim(pool, paths, fk, lv, params_for(lv, lp))
        log.append({"fc": fk, "level": lv, "iter": "final", "sd_logerr_med_p90": err(S)})
        levels[lv] = lp
    # ---------------- L2
    lp = copy.deepcopy(levels["L1"])
    for ch in C.GROUP:
        lp["phi_ind"][ch] = float(np.clip(T["acf1"][ch], 0, 0.99)) if np.isfinite(T["acf1"][ch]) else 0.0
    for f in C.FAMILIES:
        lp["phi_cm"][f] = float(np.clip(T["acf1_mean"][f], 0, 0.99)) if np.isfinite(T["acf1_mean"][f]) else 0.0
        for r in map(str, range(7)):
            t = T["cov"][f][r]
            lp["cm_scale"][f][r] = float(np.sqrt(t)) if np.isfinite(t) and t > 0 else 0.0
            for k in range(1, 5):
                ch = f"{f}_{k}"
                s = lp["sigma"][ch][r]
                lp["sigma"][ch][r] = float(np.sqrt(max(s * s - lp["cm_scale"][f][r] ** 2, (0.3 * s) ** 2)))
    for lv, iters in (("L2", 8), ("L3", 6)):
        if lv == "L3":
            lp = copy.deepcopy(levels["L2"])
            lp["pow_mult"] = emp["pow_mult"]
            lp["pow_mult_cm"] = emp["pow_mult_cm"]
            lp["seg_sd"] = emp["seg_sd"]
        for it in range(iters):
            S = run_sim(pool, paths, fk, lv, params_for(lv, lp))
            log.append({"fc": fk, "level": lv, "iter": it, "sd_logerr_med_p90": err(S),
                        "acf1_abs_err_med": float(np.nanmedian([abs(S["acf1"][c] - T["acf1"][c]) for c in C.GROUP]))})
            update(lp, S, ar=True)
        levels[lv] = lp
    # ---------------- L4: tail grid, then recalibrate
    lp = copy.deepcopy(levels["L3"])
    grid = {}
    for p in TAILS_P:
        for k in TAILS_K:
            q = copy.deepcopy(lp)
            q["tail"] = {ch: [p, k] for ch in C.GROUP}
            q["tail_cm"] = {f: [p, k] for f in C.FAMILIES}
            grid[(p, k)] = run_sim(pool, paths_small, fk, "L4", params_for("L4", q))

    def loss(S, ch):
        a = (np.log(S["kurt"][ch] + 3) - np.log(T["kurt"][ch] + 3)) ** 2 if np.isfinite(S["kurt"][ch]) else 9
        b = (np.log(S["exc4"][ch] + 1e-4) - np.log(T["exc4"][ch] + 1e-4)) ** 2 if np.isfinite(S["exc4"][ch]) else 9
        return a + b
    S3 = run_sim(pool, paths_small, fk, "L3", params_for("L3", lp))
    for ch in C.GROUP:
        cands = [((0.0, 1.0), loss(S3, ch))] + [(pk, loss(S, ch)) for pk, S in grid.items()]
        lp["tail"][ch] = list(min(cands, key=lambda c: c[1])[0])
    for f in C.FAMILIES:
        cands = [((0.0, 1.0), sum(loss(S3, f"{f}_{k}") for k in range(1, 5)))] + \
                [(pk, sum(loss(S, f"{f}_{k}") for k in range(1, 5))) for pk, S in grid.items()]
        lp["tail_cm"][f] = list(min(cands, key=lambda c: c[1])[0])
    for it in range(4):
        S = run_sim(pool, paths, fk, "L4", params_for("L4", lp))
        log.append({"fc": fk, "level": "L4", "iter": it, "sd_logerr_med_p90": err(S)})
        update(lp, S, ar=True)
    levels["L4"] = lp
    final = {lv: run_sim(pool, paths, fk, lv, params_for(lv, levels[lv])) for lv in ("L0", "L1", "L2", "L3", "L4")}
    return levels, final


def empirical(M, fixed):
    """Power-bin multipliers and segment log-SD spread from the merged real CAL statistics."""
    pm, pmc, seg = {}, {}, {}
    for ch in C.GROUP:
        nb = FS.NB_V if ch == C.VRTG else FS.NB_ENG
        ss = M["ss"][ch].reshape(7, nb)
        nn = M["nn"][ch].reshape(7, nb)
        sd_r = np.sqrt(ss.sum(1) / np.maximum(nn.sum(1), 1))
        m = np.ones((7, nb))
        for r in range(7):
            for b in range(nb):
                if nn[r, b] >= 400 and sd_r[r] > 0:
                    m[r, b] = np.sqrt(ss[r, b] / nn[r, b]) / sd_r[r]
        pm[ch] = m.tolist()
    for f in C.FAMILIES:
        c = M["cov"][f].reshape(7, FS.NB_ENG)
        n = M["cvn"][f].reshape(7, FS.NB_ENG)
        cr = c.sum(1) / np.maximum(n.sum(1), 1)
        m = np.ones((7, FS.NB_ENG))
        for r in range(7):
            for b in range(FS.NB_ENG):
                if n[r, b] >= 400 and cr[r] > 0:
                    m[r, b] = np.sqrt(max(c[r, b] / n[r, b], 0) / cr[r])
        pmc[f] = m.tolist()
    # segment multipliers: covariance of half-segment log-SD deviations (unbiased for the true spread)
    for key in C.FAMILIES + [C.VRTG]:
        chans = [f"{key}_{k}" for k in range(1, 5)] if key != C.VRTG else [C.VRTG]
        seg[key] = {}
        for r in range(7):
            rows = [s for s in M["seg"] if s["regime"] == r]
            d1, d2 = [], []
            for s in rows:
                v = [s[ch] for ch in chans if s[ch][2]]
                if len(v) == len(chans):
                    d1.append(np.mean([x[0] for x in v]))
                    d2.append(np.mean([x[1] for x in v]))
            if len(d1) >= 10:
                d1, d2 = np.array(d1), np.array(d2)
                cv = np.cov(d1 - np.median(d1), d2 - np.median(d2))[0, 1]
                seg[key][str(r)] = float(np.sqrt(max(cv, 0.0)))
            else:
                seg[key][str(r)] = 0.0
    return {"pow_mult": pm, "pow_mult_cm": pmc, "seg_sd": seg}


def fixed_params(A, res, tex_res):
    fx = {}
    # VRTG lattice
    u = np.unique(np.concatenate([a["fixed"]["vrtg_unique"] for a in A]))
    b = -3.375
    c0 = np.rint((u - b) / 0.002288818359375)
    a_ls = np.linalg.lstsq(np.vstack([c0[1:], np.ones(c0.size - 1)]).T, u[1:], rcond=None)[0][0]
    a32 = float(np.float32(a_ls))
    code = np.rint((u - b) / a32)
    rec = (code.astype(np.float32) * np.float32(a32) + np.float32(b)).astype(np.float64)
    fx["lattice"] = {"VRTG": {"a": a32, "b": b, "n_unique_cal": int(u.size), "exact_fraction": float(np.mean(rec == u))}}
    # gating: lowest valid non-zero reading (5th percentile over flights of the per-flight minimum)
    # (EGT is not gated: its engine-off reading is ambient temperature, not zero)
    fx["gate"] = {ch: float(np.nanpercentile([a["fixed"]["minnz"][ch] for a in A], 5)) for ch in C.ENG
                  if not ch.startswith("EGT")}
    rec_h = sum(a["fixed"]["record_h"] for a in A)
    air_h = sum(a["fixed"]["air_h"] for a in A)
    fx["freeze"] = {}
    for ch in C.GROUP:
        d = [x for a in A for x in a["fixed"]["freeze"][ch]]
        fx["freeze"][ch] = {"rate_per_air_h": len(d) / air_h, "durations_s": d, "n_events": len(d)}
    gmax = {r["param"]: float(r["global_max"]) for r in read_csv(os.path.join(tex_res, "param_table.csv"))}
    fx["glitch"] = {ch: {"rate_per_h": sum(a["fixed"]["glitch"][ch] for a in A) / rec_h, "value": gmax[ch],
                         "n_events": sum(a["fixed"]["glitch"][ch] for a in A)} for ch in C.GROUP}
    fx["cal_record_h"], fx["cal_air_h"] = rec_h, air_h
    # L6 (clock-domain slip) from the mechanism check on CAL
    mech = list(csv.DictReader(open(os.path.join(res, "mechanism_flights.csv"))))
    dl = [float(r["delta_ppm_8Hz"]) for r in mech if r["set"] == "687-CAL" and r["delta_ppm_8Hz"] not in ("", "nan")]
    ms = json.load(open(os.path.join(res, "mechanism_summary.json")))["687-CAL"]["P5"]["channels"]["VRTG"]
    fx["slip"] = {"VRTG": {"delta_ppm": dl, "width_phase": ms["width_phase"], "p_in": ms["p_in"],
                           "w_s": ms["w_s"], "D_s": ms["D_s"], "sentinel": -3.375,
                           "note": "boxcar fit, background p_out not part of the pre-registered L6 (set to 0)"}}
    # L6' (old periodic Gilbert-Elliott) by the dropout_bursts.py method on CAL
    ge = [a["fixed"]["ge"] for a in A]
    dur = [d for g in ge for d in g["dur"]]
    si = [s for g in ge for s in g["start_int"]]
    ev_in, ev_tot = sum(g["ev_in"] for g in ge), sum(g["ev_tot"] for g in ge)
    s_in, s_tot = sum(g["sec_in"] for g in ge), sum(g["sec_tot"] for g in ge)
    fx["ge"] = {"VRTG": {"Np": int(round(np.median(si) * 8)), "dur_s": dur, "p_bad": ev_in / (s_in * 8),
                         "p_good": (ev_tot - ev_in) / ((s_tot - s_in) * 8), "sentinel": -3.375,
                         "burst_start_interval_s_median": float(np.median(si))}}
    # T2 fleet prior
    rows = [r for a in A for r in a["fixed"]["t2rows"]]
    t2 = {}
    for f in C.FAMILIES:
        R = [r for r in rows if r[0] == f]
        L = np.array([r[4] for r in R])
        O = np.array([r[5:9] for r in R])
        fids = np.array([r[2] for r in R])
        days = np.array([r[3] for r in R], float)
        Lref = float(np.median([r[4] for r in R if r[1] == "cruise"]))
        X = np.vstack([np.ones(L.size), L - Lref]).T
        coef = np.linalg.lstsq(X, O, rcond=None)[0]          # (2, 4): intercepts, slopes per engine
        resid = O - X @ coef
        uf = sorted(set(fids), key=lambda s: s)
        per = np.array([resid[fids == u].mean(0) for u in uf])    # per-flight mean residual offsets (date order)
        dd = np.array([days[fids == u][0] for u in uf])
        sj = float(np.sqrt(np.mean(per.var(0, ddof=1))))
        rho = float(np.mean([np.corrcoef(per[:-1, k], per[1:, k])[0, 1] for k in range(4)]))
        slopes = [np.polyfit(dd, per[:, k], 1)[0] * 30 for k in range(4)]
        t2[f] = {"L_ref": Lref, "s_a": float(np.std(coef[0], ddof=1)), "s_s": float(np.std(coef[1], ddof=1)),
                 "s_j": sj, "rho_j": max(rho, 0.0), "s_d_30d": float(np.sqrt(np.mean(np.square(slopes)))),
                 "cal_intercepts_687": coef[0].tolist(), "cal_slopes_687": coef[1].tolist(), "n_windows": int(L.size)}
    fx["t2"] = t2
    return fx


def main(mat687, tex_res, res, nw=8):
    t0 = time.time()
    rows = list(csv.DictReader(open(os.path.join(res, "splits.csv"))))
    cal = [os.path.join(mat687, r["file"]) for r in rows if r["set"] == "687-CAL"]
    gmax = {r["param"]: float(r["global_max"]) for r in read_csv(os.path.join(tex_res, "param_table.csv"))}

    with Pool(nw, initializer=_init_a, initargs=(tex_res, gmax)) as pool:
        A = pool.map(pass_a, cal, chunksize=2)
    print(f"pass A done ({len(A)} CAL flights) {time.time() - t0:.0f}s", flush=True)
    fixed = fixed_params(A, res, tex_res)
    lattice = fixed["lattice"]
    print("VRTG lattice", lattice, flush=True)
    rng = np.random.default_rng(C.ROOT_SEED)
    sub = sorted(rng.choice(len(cal), 50, replace=False))
    paths = [cal[i] for i in sub]
    paths_small = paths[:20]
    log = []
    with Pool(nw, initializer=winit, initargs=(tex_res, lattice)) as pool:
        for fk in C.FC:
            M = FS.merge([a["stats"][fk] for a in A])
            T = FS.summary(M)
            emp = empirical(M, fixed)
            levels, final = calibrate(pool, paths, paths_small, fk, T, emp, fixed, log)
            params = {"fc_key": fk, "fc": C.FC[fk], "levels": levels, "fixed": fixed,
                      "calibration_subset": [C.flight_id(p) for p in paths], "fitted_on": "687-CAL only"}
            with open(os.path.join(res, f"model_params_{fk}.json"), "w") as fh:
                json.dump(params, fh, default=float)
            with open(os.path.join(res, f"fit_report_{fk}.json"), "w") as fh:
                json.dump({"targets": T, "achieved": final, "log": [l for l in log if l["fc"] == fk]}, fh, indent=1, default=float)
            print(f"fc={fk} done {time.time() - t0:.0f}s", flush=True)


def _init_a(tex_res, gmax):
    winit(tex_res, None)
    G["gmax"] = gmax


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 8)
