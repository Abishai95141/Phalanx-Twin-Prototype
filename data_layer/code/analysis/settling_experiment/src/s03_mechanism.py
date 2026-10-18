"""Step 3 -- mechanism check: dropout bursts as clock-domain slip (pre-registration section 5, P1-P5).

Model under test. The recorder reads a channel at rate f; the source updates at f(1+Delta). The read
instant therefore slips by Delta source periods per sample, and its beat phase is
    theta_k = frac(phi_c + k * Delta)      (k = sample index at the channel's own rate,
                                            phi_c = the channel's own phase, i.e. its word slot).
Reads that fall within a collision window of width w seconds around a source update
(|theta| <= w f / 2) return the zero-count sentinel with probability p. Consequences:
burst period 1/(f Delta) s, burst duration D = w / Delta s, i.e. w = D * Delta.

Per flight (all sets; decisions are taken from 687-CAL only):
  * isolated sentinel events per analog channel (rule of dashlink_texture/dropout_bursts.py);
    rate groups 8 Hz {VRTG}, 4 Hz {LATG, LONG}, 2 Hz {CCPC, CCPF, CWPF, RUDP, RUDD},
    1 Hz {OIT_1-4, AIL, ELEV, SPL, PTRM, BPYR_1}  (ACMT excluded: it is a timing word, not analog);
  * Delta_hat per rate group = argmax of the INCOHERENT sum over the group's channels of the Rayleigh
    power |sum_k exp(2 pi i k Delta)|^2 / n_c, Delta in [800, 1020] ppm (2-ppm grid, 0.02-ppm refinement).
    (v1 of this script summed coherently; channels of one group have distinct fixed slot phases, which
    made the pooled profiles multi-peaked -- see DEVIATIONS.md.)
  * phi_c per channel at the group's Delta_hat; split-half Delta_hat for VRTG;
  * folded loss profile per channel (200 phase bins, events / samples) pooled over flights -> boxcar ML
    fit with free centre (half-width h, p_in, p_out) -> w = 2h/f, D = 2h/(Delta f);
  * clock-word offset from GMT step edges (GMT_HOUR/MINUTE/SEC at 2 Hz): least squares of GMT value on
    edge time with 3-s outlier rejection; Delta_clock = slope - 1;
  * P3: per analog channel, offset of its burst train relative to the VRTG train in units of the 8-Hz period;
  * P4: digital channels N1, N2, EGT, FF (x4). Transient sample k: |local slope| >= 2 LSB/sample and
    |x[k+2]-x[k-2]| >= 8 LSB, slope = (x[k+2]+x[k+1]-x[k-1]-x[k-2])/6. Stale read: x[k] == x[k-1].
    Test (i), primary: per channel the centred phasor sum S_c = sum_stale e^{2 pi i theta} - p_c sum_trans e^{2 pi i theta}
    at the flight's analog Delta_hat (free phase); T = sum over flights and channels of |S_c|^2; null from
    200 control beat frequencies Delta_hat * r, r in [0.7,0.9] U [1.1,1.3].
    Test (ii), secondary: boxcar matched filter -- max over 50 phase offsets of the stale excess inside a
    window of the 4-Hz analog width, summed over channels and flights; same control-frequency null.
Decision rules ("verdict"; written before the first run, unchanged since):
  P1 CAL medians of the 4-, 2-, 1-Hz Delta_hat within 2 ppm of the 8-Hz median, with the 95 % CI of each
     paired median difference overlapping [-2, 2] ppm. Separately reported: Delta_burst vs Delta_clock.
  P2 Spearman(Delta_burst, Delta_clock) > 0 with one-sided p < 0.05 -> confirmed; if the split-half
     reliability of Delta_burst is < 0.3 (no detectable between-flight variation) -> untestable.
  P3 Rayleigh test of the offsets across flights p < 0.05 AND |circular mean| < 0.1 period (coincidence).
  P4 test (i) p < 0.05 -> confirmed (digital stale/duplicate reads are then added at L6).
  P5 w per rate group (median over the group's channels): max/min <= 1.5 -> confirmed, else refuted.
"verdict_text" (added after the first run, reported alongside and labelled post hoc in REPORT.md):
  the pre-registered sentence read literally, where it is weaker than the rule above --
  P2 without the reliability gate; P3 "phase-related" = Rayleigh p < 0.05 for every channel.

Usage: python -I s03_mechanism.py <mat687_dir> <mat652_dir> <texture_results_dir> <results_dir> [n_workers]
Writes results/mechanism_flights.csv, mechanism_profiles.npz, mechanism_summary.json, mechanism_decisions.json
"""
import csv
import json
import os
import sys
from multiprocessing import Pool

import numpy as np
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
from dlio import load_flight, robust_sigma  # noqa: E402
from common import read_csv, load_lsb  # noqa: E402

GROUPS = {8: ["VRTG"], 4: ["LATG", "LONG"], 2: ["CCPC", "CCPF", "CWPF", "RUDP", "RUDD"],
          1: ["OIT_1", "OIT_2", "OIT_3", "OIT_4", "AIL_1", "AIL_2", "ELEV_1", "ELEV_2", "SPL_1", "SPL_2",
              "PTRM", "BPYR_1"]}
RATE_OF = {c: f for f, cs in GROUPS.items() for c in cs}
ANALOG = [c for cs in GROUPS.values() for c in cs]
DIGITAL = C.ENG
NBIN = 200
DGRID = np.arange(800e-6, 1020e-6 + 1e-9, 2e-6)
CTRL_R = np.r_[np.linspace(0.7, 0.9, 100), np.linspace(1.1, 1.3, 100)]
NPH = 50
SENT = LSB = None


def init(tex_res):
    global SENT, LSB
    LSB = load_lsb(tex_res)
    SENT = {}
    for r in read_csv(os.path.join(tex_res, "dropouts_sentinels.csv")):
        if float(r["isolated_per_record_hour"]) >= 5 and float(r["frac_isolated_of_eq"]) > 0.5:
            SENT[r["param"]] = float(r["value"])


def iso_events(x, v, lsb):
    m = np.abs(x - v) <= 1e-6 * max(1.0, abs(v))
    sd = robust_sigma(np.diff(x))
    J = max(10 * lsb, 5 * (sd if np.isfinite(sd) else 0))
    prev = np.r_[np.nan, x[:-1]]
    nxt = np.r_[x[1:], np.nan]
    return np.flatnonzero(m & (np.abs(x - prev) > J) & (np.abs(x - nxt) > J))


def wrap(t):
    return (t + 0.5) % 1.0 - 0.5


def phasors(k, d):
    return np.exp(2j * np.pi * np.outer(np.atleast_1d(d), k)).sum(1)


def fit_delta(klist):
    """Incoherent Rayleigh power over channels. Returns (Delta_hat, Z) or (nan, nan)."""
    klist = [k.astype(float) for k in klist if k.size >= 4]
    if sum(k.size for k in klist) < 8:
        return np.nan, np.nan

    def power(ds):
        return sum(np.abs(phasors(k, ds)) ** 2 / k.size for k in klist)
    P = power(DGRID)
    d0 = DGRID[np.argmax(P)]
    fine = np.arange(d0 - 3e-6, d0 + 3e-6 + 1e-12, 0.02e-6)
    P2 = power(fine)
    j = int(np.argmax(P2))
    return float(fine[j]), float(P2[j])


def chan_phase(k, d):
    """Phase phi such that the channel's events centre on theta = 0."""
    s = phasors(k.astype(float), d)[0]
    return float((-np.angle(s) / (2 * np.pi)) % 1.0)


def gmt_slope(F):
    H, M, S = F["GMT_HOUR"].x, F["GMT_MINUTE"].x, F["GMT_SEC"].x
    ok = (H <= 23) & (M <= 59) & (S <= 59)
    g = H * 3600 + M * 60 + S
    if ok.sum() < 200:
        return np.nan, np.nan, 0
    gi = np.flatnonzero(ok)
    gv = np.unwrap(g[gi] * 2 * np.pi / 86400) * 86400 / (2 * np.pi)
    ch = np.flatnonzero(np.diff(gv) != 0) + 1
    ch = ch[(gi[ch] - gi[ch - 1]) == 1]
    if ch.size < 20:
        return np.nan, np.nan, int(ch.size)
    t = (gi[ch] - 0.5) / 2.0
    y = gv[ch]
    r0 = y - 1.0009 * t
    keep = np.abs(r0 - np.median(r0)) <= 4.0
    for _ in range(3):
        if keep.sum() < 20 or np.ptp(t[keep]) < 600:
            return np.nan, np.nan, int(keep.sum())
        b, a = np.polyfit(t[keep], y[keep], 1)
        keep = np.abs(y - (a + b * t)) <= 3.0
    if keep.sum() < 20 or np.ptp(t[keep]) < 600:
        return np.nan, np.nan, int(keep.sum())
    b, a = np.polyfit(t[keep], y[keep], 1)
    res = y[keep] - (a + b * t[keep])
    se = np.std(res) / (np.std(t[keep]) * np.sqrt(keep.sum()))
    return float(b - 1.0), float(se), int(keep.sum())


def digital_transients(x, lsb):
    n = x.size
    if n < 10:
        return np.array([], int), np.array([], bool)
    k = np.arange(2, n - 2)
    slope = (x[k + 2] + x[k + 1] - x[k - 1] - x[k - 2]) / 6.0 / lsb
    span = np.abs(x[k + 2] - x[k - 2]) / lsb
    tr = (np.abs(slope) >= 2) & (span >= 8)
    kk = k[tr]
    return kk, x[kk] == x[kk - 1]


def per_flight(args):
    path, fset, tex_res = args
    if SENT is None:
        init(tex_res)
    F = load_flight(path)
    rec = {"file": os.path.basename(path), "set": fset}
    prof = {}
    dhat = {}
    evk = {}
    for f, chans in GROUPS.items():
        ks = {c: iso_events(F[c].x, SENT[c], LSB.get(c, np.nan)) for c in chans if c in F and c in SENT}
        evk.update(ks)
        d, Z = fit_delta(list(ks.values()))
        dhat[f] = d
        rec[f"n_events_{f}Hz"] = int(sum(k.size for k in ks.values()))
        rec[f"delta_ppm_{f}Hz"] = d * 1e6 if np.isfinite(d) else np.nan
        rec[f"Z_{f}Hz"] = Z
        if not np.isfinite(d):
            continue
        for c, kc in ks.items():
            if kc.size < 4:
                continue
            ph = chan_phase(kc, d)
            rec[f"phi_{c}"] = ph
            n = F[c].x.size
            sc = np.histogram(wrap(ph + np.arange(n) * d), NBIN, (-0.5, 0.5))[0]
            ev = np.histogram(wrap(ph + kc * d), NBIN, (-0.5, 0.5))[0]
            prof[c] = (ev, sc)
        if f == 8 and "VRTG" in ks and ks["VRTG"].size >= 16:
            k8 = ks["VRTG"]
            half = F["VRTG"].x.size // 2
            rec["delta_ppm_8Hz_h1"] = fit_delta([k8[k8 < half]])[0] * 1e6
            rec["delta_ppm_8Hz_h2"] = fit_delta([k8[k8 >= half] - half])[0] * 1e6
    # ---- P3: per channel, offset of the burst train relative to the VRTG train (8-Hz period units)
    d8 = dhat.get(8, np.nan)
    if np.isfinite(d8) and "phi_VRTG" in rec:
        p8 = rec["phi_VRTG"]
        T8 = 1.0 / (8 * d8)
        tmid = F["VRTG"].x.size / 8 / 2
        for c in ANALOG:
            f = RATE_OF[c]
            if c == "VRTG" or f"phi_{c}" not in rec or not np.isfinite(dhat.get(f, np.nan)):
                continue
            df, pc = dhat[f], rec[f"phi_{c}"]
            m = np.round(tmid * f * df + pc)
            tf = (m - pc) / (df * f)
            m8 = np.round(tf * 8 * d8 + p8)
            t8 = (m8 - p8) / (d8 * 8)
            rec[f"p3_offset_{c}"] = float(wrap((tf - t8) / T8))
    # ---- clock word
    dc, se, ne = gmt_slope(F)
    rec["delta_clock_ppm"] = dc * 1e6 if np.isfinite(dc) else np.nan
    rec["delta_clock_se_ppm"] = se * 1e6 if np.isfinite(se) else np.nan
    rec["gmt_edges"] = ne
    # ---- P4: digital stale reads in transients
    dv = [dhat[f] for f in (8, 4, 2) if np.isfinite(dhat.get(f, np.nan))]
    dpool = float(np.median(dv)) if dv else np.nan
    rec["delta_ppm_pool"] = dpool * 1e6 if np.isfinite(dpool) else np.nan
    out_dig = None
    ntr = nst = 0
    if np.isfinite(dpool):
        ds = np.r_[dpool, dpool * CTRL_R]
        S2 = np.zeros(ds.size)
        box = np.zeros((ds.size, NPH))
        stale_by_phase = np.zeros(NBIN)
        all_by_phase = np.zeros(NBIN)
        for c in DIGITAL:
            kk, st = digital_transients(F[c].x, LSB[c])
            ntr += kk.size
            nst += int(st.sum())
            if kk.size < 20 or st.sum() == 0:
                continue
            p = st.mean()
            E = np.exp(2j * np.pi * np.outer(ds, kk.astype(float)))
            S = E[:, st].sum(1) - p * E.sum(1)
            S2 += np.abs(S) ** 2
            # boxcar matched filter (test ii): window half-width HW4 (phase units), NPH offsets
            th = (np.outer(ds, kk.astype(float))) % 1.0
            bins = np.minimum((th * NPH).astype(int), NPH - 1)
            for j in range(ds.size):
                a = np.bincount(bins[j], minlength=NPH).astype(float)
                s = np.bincount(bins[j][st], minlength=NPH).astype(float)
                box[j] += s - p * a
            th0 = wrap(kk * dpool)  # phase relative to sample 0 (free phase; for the figure only)
            all_by_phase += np.histogram(th0, NBIN, (-0.5, 0.5))[0]
            stale_by_phase += np.histogram(th0[st], NBIN, (-0.5, 0.5))[0]
        out_dig = {"S2": S2, "box": box, "stale_by_phase": stale_by_phase, "all_by_phase": all_by_phase}
    rec["dig_transient_samples"] = ntr
    rec["dig_stale"] = nst
    return rec, prof, out_dig


def boxcar_fit(ev, sc, f, dmed):
    """ML fit of a boxcar loss profile with free centre: (centre, half-width h, p_in, p_out)."""
    n = ev.size
    E2 = np.r_[ev, ev]
    S2 = np.r_[sc, sc]
    ce = np.r_[0, np.cumsum(E2)]
    cs = np.r_[0, np.cumsum(S2)]
    Et, St = ev.sum(), sc.sum()
    best = None
    for L in range(1, n // 2):              # window length in bins
        for s0 in range(n):
            ein = ce[s0 + L] - ce[s0]
            sin = cs[s0 + L] - cs[s0]
            eo, so = Et - ein, St - sin
            pin = np.clip(ein / max(sin, 1), 1e-9, 1 - 1e-9)
            pout = np.clip(eo / max(so, 1), 1e-12, 1 - 1e-9)
            ll = ein * np.log(pin) + (sin - ein) * np.log(1 - pin) + eo * np.log(pout) + (so - eo) * np.log(1 - pout)
            if best is None or ll > best[0]:
                best = (ll, L, s0, pin, pout)
    _, L, s0, pin, pout = best
    width = L / n
    centre = wrap((s0 + L / 2) / n - 0.5)
    pr = ev / np.maximum(sc, 1)
    return {"width_phase": width, "centre_phase": centre, "p_in": float(pin), "p_out": float(pout),
            "w_s": width / f, "D_s": width / (dmed * f), "peak_bin_p": float(pr.max()),
            "frac_events_in_window": float((ce[s0 + L] - ce[s0]) / max(Et, 1))}


def boot_ci(x, fn=np.median, B=2000, seed=0):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size < 3:
        return [np.nan, np.nan]
    r = np.random.default_rng(seed)
    bs = [fn(x[r.integers(0, x.size, x.size)]) for _ in range(B)]
    return [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


def rayleigh(v):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    n = v.size
    if n < 5:
        return {"n": int(n)}
    z = np.exp(2j * np.pi * v)
    R = np.abs(z.mean())
    Zr = n * R ** 2
    pr = float(np.exp(-Zr) * (1 + (2 * Zr - Zr ** 2) / (4 * n) - (24 * Zr - 132 * Zr ** 2 + 76 * Zr ** 3 - 9 * Zr ** 4) / (288 * n ** 2)))
    return {"n": int(n), "mean_resultant_length": float(R), "rayleigh_p": max(pr, 0.0),
            "circular_mean_period_units": float(np.angle(z.mean()) / (2 * np.pi)),
            "circular_sd_period_units": float(np.sqrt(-2 * np.log(max(R, 1e-12))) / (2 * np.pi))}


def summarise(recs, profs, digs, label):
    col = lambda k: np.array([float(r.get(k, np.nan)) if r.get(k, "") != "" else np.nan for r in recs])  # noqa: E731
    out = {"set": label, "n_flights": len(recs)}
    # ---------------- P1
    p1 = {}
    for f in (8, 4, 2, 1):
        v = col(f"delta_ppm_{f}Hz")
        p1[f"{f}Hz"] = {"n": int(np.isfinite(v).sum()), "median_ppm": float(np.nanmedian(v)), "ci95": boot_ci(v),
                         "iqr": [float(np.nanpercentile(v, 25)), float(np.nanpercentile(v, 75))],
                         "burst_period_s_at_median": float(1 / (f * np.nanmedian(v) * 1e-6)),
                         "burst_period_samples_at_median": float(1 / (np.nanmedian(v) * 1e-6))}
    strict_ok = True
    diffs = {}
    d8 = col("delta_ppm_8Hz")
    for f in (4, 2, 1):
        dd = col(f"delta_ppm_{f}Hz") - d8
        ci = boot_ci(dd)
        med = float(np.nanmedian(dd))
        diffs[f"{f}Hz_minus_8Hz"] = {"median_ppm": med, "ci95": ci, "n": int(np.isfinite(dd).sum())}
        strict_ok &= abs(med) <= 2 and ci[0] <= 2 and ci[1] >= -2
    dcl = d8 - col("delta_clock_ppm")
    wil = stats.wilcoxon(dcl[np.isfinite(dcl)])
    p1["paired_rate_differences"] = diffs
    dck = col("delta_clock_ppm")
    p1["clock"] = {"n": int(np.isfinite(dck).sum()), "median_ppm": float(np.nanmedian(dck)), "ci95": boot_ci(dck),
                   "iqr": [float(np.nanpercentile(dck, 25)), float(np.nanpercentile(dck, 75))],
                   "median_se_ppm": float(np.nanmedian(col("delta_clock_se_ppm")))}
    p1["burst8_minus_clock"] = {"median_ppm": float(np.nanmedian(dcl)), "ci95": boot_ci(dcl), "n": int(np.isfinite(dcl).sum()),
                                "wilcoxon_p": float(wil.pvalue)}
    p1["verdict"] = "confirmed" if strict_ok else "refuted"
    out["P1"] = p1
    # ---------------- P2
    h1, h2 = col("delta_ppm_8Hz_h1"), col("delta_ppm_8Hz_h2")
    m = np.isfinite(h1) & np.isfinite(h2)
    rel = stats.spearmanr(h1[m], h2[m])
    m2 = np.isfinite(d8) & np.isfinite(dck)
    sp = stats.spearmanr(d8[m2], dck[m2])
    sp_se = stats.spearmanr(d8[m2 & (col("delta_clock_se_ppm") < 3)], dck[m2 & (col("delta_clock_se_ppm") < 3)])
    p2 = {"n": int(m2.sum()), "spearman_rho": float(sp.statistic), "p_one_sided": float(sp.pvalue / 2 if sp.statistic > 0 else 1 - sp.pvalue / 2),
          "spearman_rho_clock_se_lt3ppm": float(sp_se.statistic), "p_one_sided_clock_se_lt3ppm": float(sp_se.pvalue / 2),
          "n_clock_se_lt3ppm": int((m2 & (col("delta_clock_se_ppm") < 3)).sum()),
          "split_half_reliability_rho": float(rel.statistic),
          "between_flight_sd_burst_ppm": float(np.nanstd(d8)),
          "within_flight_halfdiff_sd_ppm": float(np.nanstd(h1 - h2) / np.sqrt(2)),
          "between_flight_sd_clock_ppm": float(np.nanstd(dck))}
    p2["verdict_text"] = "confirmed" if (p2["spearman_rho"] > 0 and p2["p_one_sided"] < 0.05) else "refuted"
    p2["verdict"] = "untestable" if p2["split_half_reliability_rho"] < 0.3 else p2["verdict_text"]
    out["P2"] = p2
    # ---------------- P3 (per channel)
    p3 = {}
    ok_pre = ok_strict = True
    for c in ANALOG:
        if c == "VRTG":
            continue
        r = rayleigh(col(f"p3_offset_{c}"))
        r["rate_hz"] = RATE_OF[c]
        p3[c] = r
        if r.get("n", 0) < 5:
            continue
        ok_pre &= r["rayleigh_p"] < 0.05
        ok_strict &= r["rayleigh_p"] < 0.05 and abs(r["circular_mean_period_units"]) < 0.1
    p3["verdict_text"] = "confirmed" if ok_pre else "refuted"
    p3["verdict"] = "confirmed" if ok_strict else "refuted"
    out["P3"] = p3
    # ---------------- P5 (+ per-channel window fits)
    p5 = {"channels": {}}
    for c in ANALOG:
        if c not in profs:
            continue
        f = RATE_OF[c]
        p5["channels"][c] = dict(boxcar_fit(*profs[c], f, np.nanmedian(col(f"delta_ppm_{f}Hz")) * 1e-6), rate_hz=f)
    grp = {}
    for f in (8, 4, 2, 1):
        ws = [v["w_s"] for v in p5["channels"].values() if v["rate_hz"] == f]
        Ds = [v["D_s"] for v in p5["channels"].values() if v["rate_hz"] == f]
        ps = [v["p_in"] for v in p5["channels"].values() if v["rate_hz"] == f]
        if ws:
            grp[f"{f}Hz"] = {"w_s_median": float(np.median(ws)), "w_s_range": [float(min(ws)), float(max(ws))],
                             "D_s_median": float(np.median(Ds)), "p_in_median": float(np.median(ps))}
    p5["groups"] = grp
    wm = [g["w_s_median"] for g in grp.values()]
    p5["w_max_over_min"] = float(max(wm) / min(wm))
    p5["verdict"] = "confirmed" if p5["w_max_over_min"] <= 1.5 else "refuted"
    out["P5"] = p5
    # ---------------- P4
    p4 = {}
    dd = [d for d in digs if d is not None]
    if dd:
        T = np.sum([d["S2"] for d in dd], 0)
        p4["test_i_T_true"] = float(T[0])
        p4["test_i_T_ctrl_median"] = float(np.median(T[1:]))
        p4["test_i_ratio_true_over_ctrl_median"] = float(T[0] / np.median(T[1:]))
        p4["test_i_p"] = float((1 + np.sum(T[1:] >= T[0])) / (1 + T[1:].size))
        hw = int(round(grp["4Hz"]["w_s_median"] * 4 * NPH)) if "4Hz" in grp else 3
        hw = max(hw, 1)
        box = np.sum([d["box"] for d in dd], 0)              # (n_freq, NPH)
        boxw = np.zeros_like(box)
        for s in range(hw):
            boxw += np.roll(box, -s, axis=1)
        M = boxw.max(1)
        p4["test_ii_window_bins"] = hw
        p4["test_ii_max_excess_true"] = float(M[0])
        p4["test_ii_p"] = float((1 + np.sum(M[1:] >= M[0])) / (1 + M[1:].size))
        p4["n_flights"] = len(dd)
        p4["transient_samples"] = int(sum(float(r.get("dig_transient_samples", 0) or 0) for r in recs))
        p4["stale_samples"] = int(sum(float(r.get("dig_stale", 0) or 0) for r in recs))
        p4["stale_rate"] = p4["stale_samples"] / max(p4["transient_samples"], 1)
        p4["verdict"] = "confirmed" if p4["test_i_p"] < 0.05 else "refuted"
    else:
        p4["verdict"] = "untestable"
    out["P4"] = p4
    return out


def main(mat687, mat652, tex_res, res, nw=8):
    init(tex_res)
    rows = list(csv.DictReader(open(os.path.join(res, "splits.csv"))))
    jobs = [(os.path.join(mat687 if r["tail"] == "687" else mat652, r["file"]), r["set"], tex_res) for r in rows]
    with Pool(nw, initializer=init, initargs=(tex_res,)) as pool:
        outs = pool.map(per_flight, jobs, chunksize=2)
    recs = [o[0] for o in outs]
    keys = sorted(set().union(*[r.keys() for r in recs]), key=lambda k: (k not in ("file", "set"), k))
    with open(os.path.join(res, "mechanism_flights.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(recs)
    summary, npz = {}, {}
    for label in ("687-CAL", "687-TEST", "652"):
        idx = [i for i, r in enumerate(recs) if r["set"] == label]
        profs = {}
        for c in ANALOG:
            pr = [outs[i][1][c] for i in idx if c in outs[i][1]]
            if pr:
                profs[c] = (np.sum([p[0] for p in pr], 0), np.sum([p[1] for p in pr], 0))
                npz[f"{label}_{c}_events"], npz[f"{label}_{c}_samples"] = profs[c]
        digs = [outs[i][2] for i in idx]
        summary[label] = summarise([recs[i] for i in idx], profs, digs, label)
        dd = [d for d in digs if d is not None]
        npz[f"{label}_digital_stale_by_phase"] = np.sum([d["stale_by_phase"] for d in dd], 0)
        npz[f"{label}_digital_all_by_phase"] = np.sum([d["all_by_phase"] for d in dd], 0)
    np.savez(os.path.join(res, "mechanism_profiles.npz"), **npz)
    with open(os.path.join(res, "mechanism_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=1, default=float)
    cal = summary["687-CAL"]
    dec = {"source": "687-CAL only",
           "P4_digital_stale_reads_at_L6": cal["P4"]["verdict"] == "confirmed",
           "verdicts": {p: cal[p]["verdict"] for p in ("P1", "P2", "P3", "P4", "P5")},
           "verdicts_text_post_hoc": {p: cal[p].get("verdict_text", cal[p]["verdict"]) for p in ("P1", "P2", "P3", "P4", "P5")}}
    with open(os.path.join(res, "mechanism_decisions.json"), "w") as fh:
        json.dump(dec, fh, indent=1)
    for label in summary:
        s = summary[label]
        print(label, {p: (s[p]["verdict"], s[p].get("verdict_text", "")) for p in ("P1", "P2", "P3", "P4", "P5")})
    print(json.dumps(dec))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]) if len(sys.argv) > 5 else 8)
