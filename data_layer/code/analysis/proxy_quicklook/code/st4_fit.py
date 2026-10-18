"""W2.4a-2 stage 4: identification of the engine disturbance bank on 687-CAL by linear spectral synthesis.

Structure (AD-32, AD-46 amended, AD-52 item 4): per engine channel c (fuel metering, combustor efficiency,
inlet recovery, HP shaft load, fan_face = LP shaft torque), one aircraft-common and one per-unit OU factor
with a shared correlation time: total SD sigma_c, common variance share rho_c, tau_c
(``runner.bank_factors``, the form the bank is written in). A common spool-side factor (shaft load, LP
torque) moves every engine's spools; the fuel then follows the spools through the RU x PS3 metering (AD-50)
as far as the governor lets it.

Synthesis (expectation; the bank is independent of the inputs and of the texture): for flight f,

    P_f = P0_f + sum_c kron(Wbar_cf(sub) S_c(sub), sigma_c^2 [(1 - rho_c) I_4 + rho_c J_4])
    C_f = C0_f + sum_c kron(sum_sub Re Wbar_cf(sub) S_c(sub), ...)

with P0_f / C0_f the empty-bank chain on the flight (``st4_base``: input-driven content and texture, same
segments and mask as the real record), Wbar_cf the per-point closed-loop transfer matrices of ``st4_tf``
weighted by the flight's climb / cruise / descent shares, and S_c the OU sub-band power after the B1
fast-band transfer. The engines are exchangeable (the cross-engine transfer of a common factor is the
within-engine one).

Nuisance (pass 1; ``ST4_STC=fixed`` holds it at the configured value, pass 2): the EGT indication lag (M12
thermocouple flux law, tau = tau_ref (W/W_ref)^-0.5) scales by s_tc, applied to the bank's EGT transfer as
(1 + i w tau0) / (1 + i w s_tc tau0) per point; its prior is the round-2 MEASURED range (tau_TC,ref 0.81 s,
CV 0.55-1.18 s), and stage 5 identifies it (coordinator decision, audit #138).

Targets (pooled over the flights' governed in-flight segments, class GOVFLT; the real record with the same
estimators): within-engine fast-band r of the six pairs and cross-engine r of the four families (engine
means) and the fast-band SDs, from the time-domain covariance (as ``mf1stats.class_stats``); per spectral
pair (N2>N1, FF>N1, N2>FF, N1>EGT, N2>EGT, FF>EGT) phase and coherence in the 0.19-0.5 and 0.5-1 Hz bands,
equivalent delay and band-0 H1 gain (MF1-D ``pair_decomposition``). Distance units as the MF1 report: 0.1
for correlations, coherences and delays [s]; 20 deg for phases; log 1.35 for amplitudes.

Fit: bounded least squares (scipy TRF) in (log sigma, rho, log tau) per channel + log s_tc, multi-start from
a keyed Latin hypercube, per governor setting of the transfer grid. Loadings are clipped to the declared
ranges (``runner.LOAD_MAX``), tau to [0.05, 5] s.

Usage::

    $PY -I analysis/proxy_quicklook/code/st4_fit.py <base.npz> <out.json> <tf.npz> [<tf.npz> ...]
"""

from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script directory

import numpy as np
from common import ROOT
from mf1stats import SPEC_PAIRS, TQ16, WITHIN
from runner import CHANNELS, LOAD_MAX
from scipy.optimize import least_squares
from spectral import (
    DF,
    FREQS,
    G_FAST,
    NBIN,
    NSUB,
    REPORT_BANDS,
    SUB_FC,
    pair_decomposition,
    white_subband_power,
)
from st4_tf import OPS, gov_tag

from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.dictionary.params import load_param_set
from phalanx.validation.samples import SAMPLE_STREAM

FAMS = ("N1", "N2", "EGT", "FF")
NE = 4
OPN = tuple(OPS)
E_EGT = FAMS.index("EGT")
#: distance units (as the MF1 report objective)
U_R, U_PH, U_AMP = 0.1, 20.0, float(np.log(1.35))
TAU_LO, TAU_HI = 0.05, 5.0
#: prior range of the EGT-lag scale: round-2 tau_TC,ref CV 0.55-1.18 s around 0.81 s
STC_LO, STC_HI = 0.55 / 0.81, 1.18 / 0.81
#: aggregation over flights: ``pooled`` (pass 1 and the first pass-2 fit) or ``median`` (``ST4_AGG=median``:
#: per-flight statistics and their median, as the MF1 tables; the pooled powers are dominated by the flight
#: with the largest transients, which sized the pass-2 bank about 1.5 x too strong in the verification)
AGG = os.environ.get("ST4_AGG", "pooled")
if os.environ.get("ST4_STC") == "fixed":  # pass 2: the EGT lag is stage 5's (M12 config), not a nuisance
    STC_LO, STC_HI = 1.0 - 1e-9, 1.0 + 1e-9
N_START = 12


def ou_power(tau: float) -> np.ndarray:
    """Sub-band power of a unit-variance OU after the B1 fast-band transfer, (NSUB,)."""
    dens = 4.0 * tau / (1.0 + (2.0 * np.pi * FREQS * tau) ** 2) * G_FAST
    return np.array([dens[NBIN * b + 1 : NBIN * b + NBIN + 1].sum() * DF for b in range(NSUB)])


def ch(f: str, k: int) -> int:
    return FAMS.index(f) * NE + (k - 1)


class Data:
    """Per-flight empty-bank and real spectra for one governor setting, and the per-point transfers."""

    def __init__(self, base: str, tf: str, gains: tuple[float, float]):
        b = np.load(base)
        t = np.load(tf)
        g = gov_tag(*gains)
        self.flights = [str(x) for x in b["flights"]]
        nf = len(self.flights)
        self.P0 = [b[f"{g}.f{k}.sim.P"] for k in range(nf)]
        self.C0 = [b[f"{g}.f{k}.sim.C"] for k in range(nf)]
        self.K = np.array([int(b[f"{g}.f{k}.sim.K"]) for k in range(nf)])
        self.n = np.array([int(b[f"{g}.f{k}.sim.n"]) for k in range(nf)])
        sh = [b[f"{g}.f{k}.sim.ops"] for k in range(nf)]
        self.share_p = [s / s.sum() for s in sh]
        sh = [b[f"{g}.f{k}.sim.ops_td"] for k in range(nf)]
        self.share_c = [s / s.sum() for s in sh]
        self.Pr = [b[f"{g}.f{k}.real.P"] for k in range(nf)]
        self.Cr = [b[f"{g}.f{k}.real.C"] for k in range(nf)]
        self.Kr = np.array([int(b[f"{g}.f{k}.real.K"]) for k in range(nf)])
        self.nr = np.array([int(b[f"{g}.f{k}.real.n"]) for k in range(nf)])
        # W[op][c]: (NSUB, 4, 4) per unit input power (st4_tf normalisation)
        self.W = {o: {c: t[f"{g}.{o}.{c}"] for c in CHANNELS} for o in OPN}
        m12 = load_param_set("M12", "egt_indication", platform="proxy_dashlink")
        tau_ref, w_ref, n_exp = (float(m12.value(k)) for k in ("tau", "w_ref", "n_exp"))
        self.tau_ref = tau_ref
        self.tau0 = {o: tau_ref * (float(t[f"{o}.w2"]) / w_ref) ** (-n_exp) for o in OPN}
        self.T = white_subband_power(TQ16)

    def bank_blocks(self, theta: np.ndarray, k: int, which: str) -> tuple[np.ndarray, np.ndarray]:
        """(NSUB, 4, 4) unit-loading fam blocks summed over channels with their OU power, separately for the
        per-unit and the common parts: returns (Bu, Bc) such that the 16x16 bank cross-spectrum is
        kron(Bu, I) + kron(Bc, J)."""
        share = self.share_p[k] if which == "p" else self.share_c[k]
        stc = float(np.exp(theta[-1]))
        Bu = np.zeros((NSUB, 4, 4), complex)
        Bc = np.zeros((NSUB, 4, 4), complex)
        for j, c in enumerate(CHANNELS):
            sd, rho, tau = unpack(theta, j)
            S = ou_power(tau)
            Wc = np.zeros((NSUB, 4, 4), complex)
            for o, s in zip(OPN, share, strict=True):
                if s <= 0:
                    continue
                W = self.W[o][c].copy()
                om = 2.0 * np.pi * SUB_FC
                L = (1.0 + 1j * om * self.tau0[o]) / (1.0 + 1j * om * stc * self.tau0[o])
                # P_ij = conj(H_i) H_j S: the EGT response scales by L
                W[:, E_EGT, :] *= np.conj(L)[:, None]
                W[:, :, E_EGT] *= L[:, None]
                Wc += s * W
            Wc *= S[:, None, None]
            lu, lc = loads(sd, rho, c)
            Bu += lu * lu * Wc
            Bc += lc * lc * Wc
        return Bu, Bc

    def synth_flights(self, theta: np.ndarray) -> list[tuple[np.ndarray, np.ndarray, int]]:
        """Per-flight synthetic (P, C, K)."""
        eye, one = np.eye(NE), np.ones((NE, NE))
        out = []
        for k in range(len(self.flights)):
            Bu, Bc = self.bank_blocks(theta, k, "p")
            Pk = self.P0[k] + np.einsum("bij,kl->bikjl", Bu, eye).reshape(NSUB, 16, 16)
            Pk = Pk + np.einsum("bij,kl->bikjl", Bc, one).reshape(NSUB, 16, 16)
            Bu, Bc = self.bank_blocks(theta, k, "c")
            Cb = np.real(np.kron(Bu.sum(0), eye) + np.kron(Bc.sum(0), one))
            out.append((Pk, self.C0[k] + Cb, int(self.K[k])))
        return out

    def synth(self, theta: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
        """Pooled synthetic (P, C, K) over the flights."""
        eye, one = np.eye(NE), np.ones((NE, NE))
        Ps, Cs = np.zeros_like(self.P0[0]), np.zeros_like(self.C0[0])
        for k in range(len(self.flights)):
            Bu, Bc = self.bank_blocks(theta, k, "p")
            Pk = self.P0[k] + np.einsum("bij,kl->bikjl", Bu, eye).reshape(NSUB, 16, 16)
            Pk = Pk + np.einsum("bij,kl->bikjl", Bc, one).reshape(NSUB, 16, 16)
            Ps += self.K[k] * Pk
            Bu, Bc = self.bank_blocks(theta, k, "c")
            Cb = np.real(np.kron(Bu.sum(0), eye) + np.kron(Bc.sum(0), one))
            Cs += self.n[k] * (self.C0[k] + Cb)
        return Ps / self.K.sum(), Cs / self.n.sum(), int(self.K.sum())

    def empty(self) -> tuple[np.ndarray, np.ndarray, int]:
        P = sum(K * P for K, P in zip(self.K, self.P0, strict=True)) / self.K.sum()
        C = sum(n * C for n, C in zip(self.n, self.C0, strict=True)) / self.n.sum()
        return P, C, int(self.K.sum())

    def real(self) -> tuple[np.ndarray, np.ndarray, int]:
        P = sum(K * P for K, P in zip(self.Kr, self.Pr, strict=True)) / self.Kr.sum()
        C = sum(n * C for n, C in zip(self.nr, self.Cr, strict=True)) / self.nr.sum()
        return P, C, int(self.Kr.sum())


def unpack(theta: np.ndarray, j: int) -> tuple[float, float, float]:
    return float(np.exp(theta[3 * j])), float(theta[3 * j + 1]), float(np.exp(theta[3 * j + 2]))


def loads(sd: float, rho: float, c: str) -> tuple[float, float]:
    """(per-unit, common) loadings, each clipped to the channel's declared range (as runner.bank_factors)."""
    rho = min(max(rho, 0.0), 1.0)
    return min(sd * np.sqrt(1.0 - rho), LOAD_MAX[c]), min(sd * np.sqrt(rho), LOAD_MAX[c])


def stats(P: np.ndarray, C: np.ndarray, K: int, T: np.ndarray) -> dict[str, float]:
    """The fit statistics (engine means) from pooled sub-band powers and the time-domain covariance."""
    out: dict[str, float] = {}
    sd = np.sqrt(np.clip(np.diag(C), 1e-300, None))
    R = C / np.outer(sd, sd)
    for a, b in WITHIN:
        out[f"r.{a}-{b}"] = float(np.mean([R[ch(a, k), ch(b, k)] for k in range(1, NE + 1)]))
    for f in FAMS:
        out[f"x.{f}"] = float(
            np.mean([R[ch(f, i), ch(f, j)] for i in range(1, NE + 1) for j in range(i + 1, NE + 1)])
        )
        out[f"sd.{f}"] = float(np.mean([sd[ch(f, k)] for k in range(1, NE + 1)]))
    for a, b in SPEC_PAIRS:
        ph = np.zeros(2, complex)
        coh = np.zeros(2)
        tau = gain = 0.0
        for k in range(1, NE + 1):
            i, j = ch(a, k), ch(b, k)
            pr = pair_decomposition(P, T, i, j, K)
            ph += np.exp(1j * np.radians(pr.phase_bands_deg[:2]))
            coh += np.array(pr.coh_bands[:2])
            tau += pr.tau_eq
            m = (SUB_FC >= REPORT_BANDS[0][0]) & (SUB_FC < REPORT_BANDS[0][1])
            gain += float(np.abs(P[m, i, j].sum()) / np.real(P[m, i, i]).sum())
        key = f"{a}>{b}"
        for q in range(2):
            out[f"{key}.ph{q}"] = float(np.degrees(np.angle(ph[q])))
            out[f"{key}.coh{q}"] = float(coh[q] / NE)
        out[f"{key}.tau"] = tau / NE
        out[f"{key}.gain0"] = gain / NE
    return out


def distance(s: dict[str, float], r: dict[str, float]) -> dict[str, float]:
    d: dict[str, float] = {}
    for k, v in r.items():
        x = s[k]
        if k.startswith("sd.") or k.endswith(".gain0"):
            d[k] = float(np.log(max(x, 1e-12) / max(v, 1e-12)) / U_AMP)
        elif ".ph" in k:
            d[k] = float(((x - v + 180.0) % 360.0 - 180.0) / U_PH)
        else:
            d[k] = (x - v) / U_R
    return d


def bounds() -> tuple[np.ndarray, np.ndarray]:
    lo, hi = [], []
    for c in CHANNELS:
        lo += [np.log(LOAD_MAX[c] / 1000.0), 0.0, np.log(TAU_LO)]
        hi += [np.log(LOAD_MAX[c] * np.sqrt(2.0)), 1.0, np.log(TAU_HI)]
    lo.append(np.log(STC_LO))
    hi.append(np.log(STC_HI))
    return np.array(lo), np.array(hi)


def starts(n: int, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    svc = RngService(ROOT, StreamRegistry([SAMPLE_STREAM]))
    path = KeyPath.of(
        scenario="w24a2-st4-fit", subsystem=SAMPLE_STREAM.subsystem, component=SAMPLE_STREAM.component
    )
    gen = svc.generator(path, 0)
    u = np.empty((n, lo.size))
    for j in range(lo.size):
        u[:, j] = (gen.permutation(n) + gen.random(n)) / n
    z = lo + u * (hi - lo)
    z[0] = np.r_[np.tile([np.log(0.003), 0.5, np.log(0.5)], len(CHANNELS)), 0.0]  # a neutral start
    return z


def median_stats(per_flight: list[tuple[np.ndarray, np.ndarray, int]], T: np.ndarray) -> dict[str, float]:
    """Statistics per flight, then the median over flights (circular mean for phases): the aggregation of the
    MF1 tables (``aggregate.py``), which the full-chain verification reports."""
    ss = [stats(P, C, K, T) for P, C, K in per_flight]
    out = {}
    for k in ss[0]:
        v = np.array([s[k] for s in ss])
        if ".ph" in k:
            out[k] = float(np.degrees(np.angle(np.mean(np.exp(1j * np.radians(v))))))
        else:
            out[k] = float(np.median(v))
    return out


def fit_one(data: Data, n_start: int = N_START) -> dict:
    if AGG == "median":
        real_pf = [(P, C, K) for P, C, K in zip(data.Pr, data.Cr, data.Kr, strict=True)]
        r = median_stats(real_pf, data.T)
    else:
        r = stats(*data.real(), data.T)
    keys = sorted(r)
    lo, hi = bounds()

    def synth_stats(theta):
        if AGG == "median":
            return median_stats(data.synth_flights(theta), data.T)
        return stats(*data.synth(theta), data.T)

    def resid(theta):
        d = distance(synth_stats(theta), r)
        return np.array([d[k] for k in keys])

    best = None
    runs = []
    for z0 in starts(n_start, lo, hi):
        sol = least_squares(resid, np.clip(z0, lo, hi), bounds=(lo, hi), x_scale="jac", max_nfev=400)
        runs.append(float(2.0 * sol.cost))
        if best is None or sol.cost < best.cost:
            best = sol
    s_best = synth_stats(best.x)
    if AGG == "median":
        s_empty = median_stats(
            [(P, C, int(K)) for P, C, K in zip(data.P0, data.C0, data.K, strict=True)], data.T
        )
    else:
        s_empty = stats(*data.empty(), data.T)
    bank = {}
    for j, c in enumerate(CHANNELS):
        sd, rho, tau = unpack(best.x, j)
        lu, lc = loads(sd, rho, c)
        bank[c] = {"sd": sd, "rho": rho, "tau": tau, "load_unit": lu, "load_common": lc}
    return {
        "cost": float(2.0 * best.cost),
        "costs_by_start": runs,
        "rms": float(np.sqrt(2.0 * best.cost / len(keys))),
        "theta": best.x.tolist(),
        "bank": bank,
        "s_tc": float(np.exp(best.x[-1])),
        "tau_tc_ref": data.tau_ref * float(np.exp(best.x[-1])),
        "real": r,
        "synth": s_best,
        "empty": s_empty,
        "dist": distance(s_best, r),
        "dist_empty": distance(s_empty, r),
    }


def main(base: str, out: str, *tfs: str) -> None:
    res: dict = {"n_flights": None, "settings": {}}
    for tf in tfs:
        grid = [tuple(float(v) for v in g) for g in np.load(tf)["gov_grid"]]
        for gains in grid:
            t0 = time.time()
            data = Data(base, tf, gains)
            res["n_flights"] = len(data.flights)
            r = fit_one(data)
            r["seconds"] = round(time.time() - t0, 1)
            r["gains"] = list(gains)
            r["aggregation"] = AGG
            res["settings"][gov_tag(*gains)] = r
            de = float(np.sqrt(np.mean(np.square(list(r["dist_empty"].values())))))
            print(
                f"{gov_tag(*gains)}: rms {r['rms']:.3f} (empty bank {de:.3f}), s_tc {r['s_tc']:.2f},",
                f"{r['seconds']} s",
                flush=True,
            )
    with open(out, "w") as fh:
        json.dump(res, fh, indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main(*sys.argv[1:])
