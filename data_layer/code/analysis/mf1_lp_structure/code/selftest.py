"""MF1-D estimator self-tests on synthetic signals (no flight data); each check prints PASS/FAIL.

Every check is a negative-capable test: it compares an estimator with a value known by construction, with a
tolerance stated beside it. Run before any flight data is read and again before scaling.

Usage: python -I selftest.py <out_txt>
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script dir

import numpy as np
from common import DataGuardError, guard_path, selftest_generator
from scipy.signal import csd, lfilter
from spectral import (
    FS,
    NSUB,
    csd_matrix,
    multiple_coherence,
    pair_decomposition,
    partial_coherence,
    path_decomposition,
    residual_cross,
    segment_starts,
    subband,
    texture_first_decomposition,
    white_subband_power,
)

from phalanx.validation.battery.filters import lowpass

N = 24000  # 100 min at 4 Hz
LINES: list[str] = []


def check(name: str, ok: bool, detail: str) -> bool:
    line = f"{'PASS' if ok else 'FAIL'}  {name}: {detail}"
    LINES.append(line)
    print(line)
    return ok


def red(gen, n, a=0.9):
    """AR(1) process (red spectrum) with unit innovation variance."""
    return lfilter([1.0], [1.0, -a], gen.standard_normal(n))


def fast(x):
    return x - lowpass(x, FS, 0.2)


def run() -> bool:
    ok = True
    gen = selftest_generator(0)
    mask = np.ones(N, bool)
    starts = segment_starts(mask)

    # 1. Welch identity with scipy.csd on one contiguous run
    x = fast(red(gen, N))
    y = fast(red(gen, N) + 0.5 * x)
    G, K = csd_matrix(np.vstack([x, y]), starts)
    _f, ref = csd(x, y, fs=FS, window="hann", nperseg=512, noverlap=256, detrend="linear")
    err = float(np.max(np.abs(G[:, 0, 1] - ref)) / np.max(np.abs(ref)))
    ok &= check("welch_equals_scipy_csd", err < 1e-10, f"max rel err {err:.2e} (tol 1e-10), K={K}")

    # 2. sign and size of the equivalent delay: y lags x by 2 samples (0.5 s)
    s = red(gen, N + 10, 0.8)
    x = fast(s[10:])
    y = fast(s[8:-2])  # y[t] = s[t + 8] -> relative to x[t] = s[t + 10], y lags by 2 samples
    P = subband(csd_matrix(np.vstack([x, y]), starts)[0])
    T = np.zeros((NSUB, 2))
    pr = pair_decomposition(P, T, 0, 1, K)
    ok &= check("delay_sign_and_size", abs(pr.tau_eq - 0.5) < 0.02, f"tau_eq {pr.tau_eq:.4f} s (true +0.5)")
    ok &= check(
        "pure_delay_has_no_coherence_loss",
        abs(pr.L_coh_A) < 0.02 and pr.shares_A["dyn"] > 0.95,
        f"r {pr.r_spec:.3f} r_lag {pr.r_lag:.3f} L_coh {pr.L_coh_A:.4f} share_dyn {pr.shares_A['dyn']:.3f}",
    )
    r_td = float(np.corrcoef(x, y)[0, 1])
    ok &= check(
        "parseval_r_spec_vs_time_domain", abs(pr.r_spec - r_td) < 0.02, f"{pr.r_spec:.4f} vs {r_td:.4f}"
    )

    # 3. zero phase, independent noise: coherence loss only; texture ceiling recovers truth when T is known
    s = red(gen, N, 0.95)
    vn = 0.3 * np.var(fast(s))
    n1 = gen.standard_normal(N) * np.sqrt(vn)
    n2 = gen.standard_normal(N) * np.sqrt(vn)
    x, y = fast(s + n1), fast(s + n2)
    P = subband(csd_matrix(np.vstack([x, y]), starts)[0])
    T = np.column_stack([white_subband_power(vn), white_subband_power(vn)])
    pr = pair_decomposition(P, T, 0, 1, K)
    ok &= check(
        "zero_phase_noise_is_coherence_loss",
        abs(pr.L_phase_A) < 0.02 and pr.shares_A["coh"] > 0.9,
        f"L_phase {pr.L_phase_A:.4f} L_shape {pr.L_shape:.4f} share_coh {pr.shares_A['coh']:.3f}",
    )
    ok &= check(
        "texture_known_explains_loss",
        abs(pr.shares_A["beyond"]) < 0.1 and abs(pr.r_truth - 1) < 0.05,
        f"share_tex {pr.shares_A['tex']:.3f} share_beyond {pr.shares_A['beyond']:.3f} "
        f"r_truth {pr.r_truth:.3f}",
    )
    # negative control: same signals, texture assumed zero -> all of it is "beyond"
    pr0 = pair_decomposition(P, np.zeros((NSUB, 2)), 0, 1, K)
    ok &= check(
        "texture_zero_moves_loss_beyond",
        pr0.shares_A["beyond"] > 0.9,
        f"share_beyond {pr0.shares_A['beyond']:.3f} with T=0",
    )
    # D3 texture-first decomposition: same signals -> texture explains the loss, nothing beyond
    tf = texture_first_decomposition(P, T, 0, 1)
    ok &= check(
        "texture_first_known_texture",
        tf["s_tex"] > 0.9 and abs(tf["s_beyond"]) < 0.1,
        f"tf s_tex {tf['s_tex']:.3f} s_dyn {tf['s_dyn']:.3f} s_beyond {tf['s_beyond']:.3f}",
    )
    # delayed truth (coherence 1) + white texture: nothing beyond texture in either ordering
    s = red(gen, N + 10, 0.8)
    xd = fast(s[10:] + n1)
    yd = fast(s[8:-2] + n2)
    Pd = subband(csd_matrix(np.vstack([xd, yd]), starts)[0])
    prd = pair_decomposition(Pd, T, 0, 1, K)
    tfd = texture_first_decomposition(Pd, T, 0, 1)
    ok &= check(
        "delay_plus_texture_has_no_beyond",
        abs(prd.shares_A["beyond"]) < 0.05 and abs(tfd["s_beyond"]) < 0.05,
        f"A beyond {prd.shares_A['beyond']:.3f}, TF beyond {tfd['s_beyond']:.3f}, TF tex {tfd['s_tex']:.3f}",
    )

    # 4. white-noise texture power: Δ²/12 white noise through the fast operator
    q = (gen.random(N) - 0.5) * 0.04  # uniform ±Δ/2, var Δ²/12
    Pq = subband(csd_matrix(fast(q)[None, :], starts)[0])
    pred = white_subband_power(0.04**2 / 12)
    rel = float(np.real(Pq[:, 0, 0]).sum() / pred.sum())
    ok &= check("white_texture_power", abs(rel - 1) < 0.05, f"measured/predicted fast-band power {rel:.4f}")

    # 5. partial and multiple coherence: x1 = z + a, x2 = z + b
    z = red(gen, N, 0.9)
    a = red(gen, N, 0.9) * 0.6
    b = red(gen, N, 0.9) * 0.6
    X = np.vstack([fast(z + a), fast(z + b), fast(z)])
    P = subband(csd_matrix(X, starts)[0])
    pc = partial_coherence(P, 0, 1, 2)
    ok &= check("partial_coherence_given_common_is_zero", max(pc) < 0.03, f"PCF {pc[0]:.4f}, {pc[1]:.4f}")
    mc = multiple_coherence(P, np.zeros((NSUB, 3)), 0, [1, 2])
    expect = 1 / (1 + 0.36)
    ok &= check(
        "multiple_coherence_fraction", abs(mc.MCF - expect) < 0.03, f"MCF {mc.MCF:.4f} expect {expect:.4f}"
    )
    rv, rp = path_decomposition(P, 0, 1, 2)
    r01 = float(np.real(P[:, 0, 1]).sum() / np.sqrt(np.real(P[:, 0, 0]).sum() * np.real(P[:, 1, 1]).sum()))
    ok &= check(
        "path_decomposition_adds_up_and_routes_via_common",
        abs(rv + rp - r01) < 1e-10 and abs(rp) < 0.03,
        f"r {r01:.4f} = via {rv:.4f} + partial {rp:.4f}",
    )

    # 6. multiple-coherence texture ceiling: N1 = h(N2, FF) exactly + white texture on all three
    core = red(gen, N, 0.9)
    ffs = red(gen, N, 0.9)
    n1t = lfilter([0.3], [1, -0.7], core) + 0.2 * ffs
    tv = np.array([0.05, 0.05, 0.05]) * np.var(fast(n1t))
    noise = [gen.standard_normal(N) * np.sqrt(v) for v in tv]
    X = np.vstack([fast(n1t + noise[0]), fast(core + noise[1]), fast(ffs + noise[2])])
    P = subband(csd_matrix(X, starts)[0])
    T = np.column_stack([white_subband_power(v) for v in tv])
    mc = multiple_coherence(P, T, 0, [1, 2])
    ok &= check(
        "no_independent_N1_input_gives_zero_beyond",
        abs(mc.U_beyond) < 0.03 and mc.U_obs > 0.03,
        f"U_obs {mc.U_obs:.4f} U_tex {mc.U_tex:.4f} U_beyond {mc.U_beyond:.4f} ceiling {mc.MC_ceiling:.4f}",
    )
    lp = red(gen, N, 0.9) * 0.15  # independent LP input
    X2 = X.copy()
    X2[0] = fast(n1t + lp + noise[0])
    P2 = subband(csd_matrix(X2, starts)[0])
    mc2 = multiple_coherence(P2, T, 0, [1, 2])
    expect_lp = float(np.var(fast(lp)) / np.var(X2[0]))
    ok &= check(
        "independent_N1_input_is_detected_beyond_texture",
        abs(mc2.U_beyond - expect_lp) < 0.02,
        f"U_beyond {mc2.U_beyond:.4f} vs injected LP share {expect_lp:.4f} (tol 0.02)",
    )

    # 7. residual cross-engine coherence: common LP disturbance d shared by both engines
    d = red(gen, N, 0.9) * 0.3
    chans = []
    for _ in range(2):
        c2 = red(gen, N, 0.9)
        ff = red(gen, N, 0.9)
        e = red(gen, N, 0.9) * 0.3
        chans += [fast(lfilter([0.3], [1, -0.7], c2) + 0.2 * ff + d + e), fast(c2), fast(ff)]
    P = subband(csd_matrix(np.vstack(chans), starts)[0])
    rc = residual_cross(P, np.zeros((NSUB, 6)), 0, [1, 2], 3, [4, 5])
    ok &= check(
        "residual_cross_common_share_half",
        abs(rc["res_common_share"] - 0.5) < 0.07 and abs(rc["res_coh"] - 0.25) < 0.07,
        f"common share |gamma| {rc['res_common_share']:.3f} (expect 0.5), "
        f"MSC {rc['res_coh']:.3f} (expect 0.25)",
    )

    # 8. guard
    mat = "/tmp/x/raw/mat"
    refused = 0
    for p in (
        "/tmp/x/raw2/mat/687200104111158.mat",
        "/tmp/x/raw/mat/sub/687200104111158.mat",
        "/tmp/x/raw/mat/687200104111441.mat",
    ):
        try:
            guard_path(p, mat, {"687200104111158.mat"})
        except DataGuardError:
            refused += 1
    try:
        guard_path("/tmp/x/raw/mat/687200104111158.mat", "/tmp/x/raw2/mat", {"687200104111158.mat"})
    except DataGuardError:
        refused += 1
    accepted = guard_path("/tmp/x/raw/mat/687200104111158.mat", mat, {"687200104111158.mat"})
    ok &= check(
        "guard_refuses_raw2_outside_and_noncal",
        refused == 4 and accepted.name == "687200104111158.mat",
        f"{refused}/4",
    )

    # 9. double-quantiser error variance vs the round-2 rule LSB_nat^2/12 + LSB_rec^2/12
    for fam, Lr, r, phi0 in (("N1", 0.03125, 1.28, 1.04), ("EGT", 0.5, 1.6, 0.04875)):
        xs = np.linspace(10.0, 10.0 + 400 * Lr * r, 2_000_001)
        xn = Lr * (r * np.rint((xs / Lr - phi0) / r) + phi0)
        yq = Lr * np.rint(xn / Lr)
        v = float(np.var(yq - xs))
        rule = (Lr * r) ** 2 / 12 + Lr**2 / 12
        ok &= check(
            f"double_quantiser_variance_{fam}",
            abs(v / rule - 1) < 0.15,
            f"simulated {v:.6g} vs rule {rule:.6g} (ratio {v / rule:.3f})",
        )
    return ok


if __name__ == "__main__":
    good = run()
    with open(sys.argv[1], "w") as fh:
        fh.write("MF1-D estimator self-test (synthetic signals only; no flight data)\n")
        fh.write("\n".join(LINES) + "\n")
        fh.write(f"OVERALL: {'PASS' if good else 'FAIL'}\n")
    print("OVERALL", "PASS" if good else "FAIL")
