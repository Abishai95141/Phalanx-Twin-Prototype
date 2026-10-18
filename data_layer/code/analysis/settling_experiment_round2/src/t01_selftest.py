"""Self-tests (CAL data only): numba PCHIP == scipy PCHIP; fused M-A kernels == numpy reference implementations
for both variants, with CAL-fitted and overridden unit parameters; B1 == analysis/correlation_check/corr_check.

Usage: python -I t01_selftest.py <mat687_dir> <correlation_check_dir>
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2common as R  # noqa: E402
import ma_model as MAM  # noqa: E402
import battery as BT  # noqa: E402


def main(mat687, ccdir):
    rng = np.random.default_rng(0)
    worst = 0.0
    for _ in range(200):
        x = np.unique(np.sort(rng.uniform(0, 100, int(rng.integers(3, 9)))))
        if x.size < 3:
            continue
        p = np.r_[rng.normal(), np.abs(rng.normal(size=x.size - 1)) * rng.choice([0, 1, 5], x.size - 1)]
        m = MAM.MonoMap(x)
        z = rng.uniform(-20, 120, 3000)
        worst = max(worst, float(np.max(np.abs(m(p, z) - m.scipy_eval(p, z)))))
    print(f"PCHIP numba vs scipy max abs diff {worst:.2e}", "PASS" if worst < 1e-9 else "FAIL")
    cal = R.cal_files()
    ds = [R.load(os.path.join(mat687, f)) for f in cal[:3]]
    B = MAM.Batch(ds, [MAM.running_mask_cal(d) for d in ds])
    cm = B.corrected_measured()
    for variant in ("P", "S"):
        ma = MAM.MA(8, variant)
        sel = np.flatnonzero(B.w > 0)[::7]
        for nm, z, rule in (("f", B.PLA, "mix"), ("g", cm["Wc"], "log"), ("h", cm["N2c"], "mix"), ("kW", cm["Wc"], "log"),
                            ("kN", cm["N1c"], "mix")):
            ma.knots[nm] = MAM.knot_rule(z[sel], 8, rule)
        for st in ma.STAGES:
            lo, hi = ma.bounds(st)
            p = rng.normal(size=lo.size) * 0.3
            ma.p[st] = np.clip(p, np.where(np.isfinite(lo), lo + 0.01, -5), np.where(np.isfinite(hi), hi - 0.01, 5))
        # realistic map values
        q = ma.p["FFN2"]
        q[:8] = MAM.MonoMap.init_from(ma.knots["f"], B.PLA[sel], cm["Wc"][sel])
        q[17:25] = MAM.MonoMap.init_from(ma.knots["g"], cm["Wc"][sel], cm["N2c"][sel])
        ma.p["N1"][:8] = MAM.MonoMap.init_from(ma.knots["h"], cm["N2c"][sel], cm["N1c"][sel])
        ma.p["EGT"][:8] = MAM.MonoMap.init_from(ma.knots["kW"], cm["Wc"][sel], cm["Tc"][sel])
        ma.p["EGT"][8:15] = 0.5
        ma.p["EGT"][15] = 0.6
        if variant == "S":
            ma.p["FFN2"][9:12] = np.clip(ma.p["FFN2"][9:12], -0.05, 0.05)
        for ov in (None, ma.draw_offsets("selftest")):
            u_ref = ma.unit(B, ov) if ov is not None else None
            u_new = {k + "_4": np.asarray(v, float) for k, v in ov.items()} if ov is not None else None
            r1 = ma._ref_sim_ffn2(B, ma.p["FFN2"], u_ref)
            r2 = ma.sim_ffn2(B, ma.p["FFN2"], u_new)
            d1 = max(float(np.max(np.abs(a - b))) for a, b in zip(r1, r2))
            n1a = ma._ref_sim_n1(B, ma.p["N1"], r1[2], u_ref)
            n1b = ma.sim_n1(B, ma.p["N1"], r2[2], u_new)
            ea = ma._ref_sim_egt(B, ma.p["EGT"], r1[0], n1a, u_ref)
            eb = ma.sim_egt(B, ma.p["EGT"], r2[0], n1b, u_new)
            d2, d3 = float(np.max(np.abs(n1a - n1b))), float(np.max(np.abs(ea - eb)))
            ok = max(d1, d2, d3) < 1e-6
            print(f"variant {variant} override {'prior' if ov else 'cal'}: max diff FFN2 {d1:.2e} N1 {d2:.2e} EGT {d3:.2e}",
                  "PASS" if ok else "FAIL")
            keep = rng.random(B.n) < 0.15
            c = ma.sim_ffn2(B, ma.p["FFN2"], u_new, keep=keep)
            dc = max(float(np.max(np.abs(a[keep] - b))) for a, b in zip(r2, c))
            dn = float(np.max(np.abs(n1b[keep] - ma.sim_n1(B, ma.p["N1"], r2[2], u_new, keep=keep))))
            de = float(np.max(np.abs(eb[keep] - ma.sim_egt(B, ma.p["EGT"], r2[0], n1b, u_new, keep=keep))))
            print(f"   compact outputs == full[keep]: FFN2 {dc:.1e} N1 {dn:.1e} EGT {de:.1e}",
                  "PASS" if max(dc, dn, de) == 0 else "FAIL")
    sys.path.insert(0, ccdir)
    import corr_check as CC
    for f, d in zip(cal[:3], ds):
        a = CC.flight_stats(os.path.join(mat687, f))
        b = BT.b1_stats(d["Y"])
        print("B1 == corr_check", f, "PASS" if (np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])) else "FAIL")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
