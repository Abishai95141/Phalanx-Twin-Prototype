"""W2.4a-2 stage 4: closed-loop disturbance-to-word transfer of the identified proxy chain, per channel.

For the disturbance-bank identification (``st4_fit.py``) the bank's contribution to the fast-band spectra
of the recorded words is synthesised from per-channel transfer matrices: at three governed operating points
(climb, cruise, flight-idle descent: medians of the CAL A/T-engaged steady points, ``st_points``), the full
proxy chain (M08 with the A/T loop, M07, M12; bleed on) runs 1,500 s of synthetic constant-condition flight
with **one** per-unit OU factor (correlation time ``TAU_INJ``, loading ``SIG_INJ``) on one engine channel. The
sensor-level words (M12 output at the ACMS instants, no M13 texture) give, per sub-band of the MF1-D
spectral estimator (Welch 512/256 at 4 Hz, B1 fast-band power transfer), the cross-spectral matrix of the
four families normalised by the input's sub-band power: W_c[sub, i, j] = H_i H_j^* per unit input power,
averaged over the four engines (each driven by its own independent instance). A run with no factor gives
the numerical floor.

Linearity: loadings of 0.5 % (the bank's scale); the per-unit-power normalisation is exact for the injected
OU shape and approximate (aliasing above 2 Hz) for other correlation times, which ``st4_fit`` limits to
0.2-5 s; the fitted bank is verified with the full chain on CAL flights.

Usage::

    $PY -I analysis/proxy_quicklook/code/st4_tf.py <out.npz> [seconds] [kp:ki,kp:ki,...]
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script directory
import common  # noqa: F401  (src/ and the MF1-D estimators on the path)
from spectral import DF, FREQS, G_FAST, NBIN, NSUB, csd_matrix

from phalanx.core.rng import KeyPath
from phalanx.engine.steady import steady_state
from phalanx.environment.disturbances import Factor
from phalanx.proxy.config import load_proxy_config
from phalanx.proxy.inputs import ProxyFlightInputs
from phalanx.proxy.run import simulate_flight
from phalanx.proxy.system import effective_lever, trim_engine

FAMS = ("N1", "N2", "EGT", "FF")
CHANNELS = ("fuel", "comb", "inlet", "shaft", "fan")
#: governed operating points: medians of the A/T-engaged CAL steady points per phase (st_points, fit set)
OPS = {
    "climb": {"alt_ft": 19630.0, "mach": 0.60, "tat_c": 2.5, "n1": 93.4, "pla": 81.5, "ph": 4},
    "cruise": {"alt_ft": 27996.0, "mach": 0.70, "tat_c": -6.8, "n1": 92.2, "pla": 79.2, "ph": 5},
    "descent": {"alt_ft": 7392.0, "mach": 0.42, "tat_c": 15.5, "n1": 37.3, "pla": 25.6, "ph": 6},
}
TAU_INJ = 0.5
SIG_INJ = 0.005
#: autothrottle gains: the proxy M08 configuration's since stage 5 (identified on 687-CAL); stage-4 pass 1 ran
#: with the MF1 base 0.3 / 0.2 / 0.1 (A-W2.4a-17), selected by ``ST4_AT=mf1base`` for its reproduction.
#: A governor-strength grid: (Kp, Ki) scaled together from the
#: committed (2, 1 1/s) down (Kp window 0.5-8, Ki 0.1-5 1/s, A-W1.3b-3), where the RU x PS3 metering is no
#: longer overridden by the governor (AD-50). Kp alone at 0.5 with Ki 1 limit-cycles at flight idle (smoke run
#: tf_smoke_kp: the descent floor carries an EGT/FF oscillation), so the PI zero Ki/Kp is held
MF1_BASE_AT = {"at_kp": 0.3, "at_ki": 0.2, "at_rate": 0.1}
AT_GAINS = MF1_BASE_AT if os.environ.get("ST4_AT") == "mf1base" else {}
GOV_GRID = ((2.0, 1.0), (1.0, 0.5), (0.5, 0.25))
DISCARD_S = 120.0
ROOT = 20261015


def op_inputs(op: dict, seconds: float) -> ProxyFlightInputs:
    n = round(seconds * 4.0)
    full = np.full
    return ProxyFlightInputs(
        flight_id=f"st4-{op['ph']}",
        rate_hz=4.0,
        pla_deg=full((4, n), op["pla"]),
        alt_ft=full(n, op["alt_ft"]),
        mach=full(n, op["mach"]),
        tat_c=full(n, op["tat_c"]),
        phase=full(n, op["ph"], dtype=np.int64),
        wow=np.zeros(n, dtype=np.int64),
        at_engage=np.ones(n, dtype=np.int64),
        n1_cmd_pct=full(n, op["n1"]),
        blv=full(n, 15, dtype=np.int64),
        pack=full(n, 3, dtype=np.int64),
        eai=np.zeros(n, dtype=np.int64),
        wai=np.zeros(n, dtype=np.int64),
    )


def ou_subband_power(tau: float, sig: float) -> np.ndarray:
    """Sub-band power of a unit-variance OU (one-sided density 4 tau / (1 + (2 pi f tau)^2)) times sig^2,
    after the B1 fast-band power transfer, (NSUB,)."""
    dens = sig * sig * 4.0 * tau / (1.0 + (2.0 * np.pi * FREQS * tau) ** 2) * G_FAST
    return np.array([dens[NBIN * b + 1 : NBIN * b + NBIN + 1].sum() * DF for b in range(NSUB)])


def subband_matrix(X: np.ndarray) -> tuple[np.ndarray, int]:
    """Fast-band sub-band power matrix (NSUB, p, p) of raw signals X (p, n) over the whole record."""
    n = X.shape[1]
    starts = list(range(0, n - 512 + 1, 256))
    G, K = csd_matrix(X, starts)
    G = G * G_FAST[:, None, None]
    return np.stack([G[NBIN * b + 1 : NBIN * b + NBIN + 1].sum(0) * DF for b in range(NSUB)]), K


def gov_tag(kp: float, ki: float) -> str:
    return f"kp{kp:g}ki{ki:g}"


def op_airflow(cfg, op: dict) -> float:
    """Engine airflow W2 [kg/s] of the trim at the operating point (the thermocouple flux law's input)."""
    rec = op_inputs(op, 2.0).replay_inputs()
    bl = op_inputs(op, 2.0).bleed(cfg.bleed)
    tr = trim_engine(cfg, effective_lever(cfg, rec, at_floor=False), bleed_kgs=float(bl[0, 0]))
    st = steady_state(cfg.engine, tr.u, x0=tr.x)
    return float(st.aux_dict()["w2"])


def run(cfg, op: dict, factors, seconds: float, sortie: int, gains: tuple[float, float]) -> np.ndarray:
    inp = op_inputs(op, seconds)
    fp = cfg.fadec_params.replace(gov_kp=gains[0], gov_ki=gains[1], **AT_GAINS)
    sf = simulate_flight(cfg.with_factors(factors), inp, identity=KeyPath.of(scenario="st4-tf", tail="T0",
                         sortie=sortie), root=ROOT, fadec_params=fp)  # fmt: skip
    k0 = round(DISCARD_S * 4.0)
    X = np.vstack([np.asarray(sf.sensor.outputs[f])[e] for e in range(4) for f in FAMS])  # (16, n) e-major
    return X[:, k0:]


def main(out_npz: str, seconds: float = 1500.0, grid: tuple[tuple[float, float], ...] = GOV_GRID) -> None:
    cfg = load_proxy_config()
    res: dict[str, np.ndarray] = {}
    su = ou_subband_power(TAU_INJ, SIG_INJ)
    for oname, op in OPS.items():
        res[f"{oname}.w2"] = np.array(op_airflow(cfg, op))
    for gains in grid:
        for io, (oname, op) in enumerate(OPS.items()):
            t0 = time.time()
            tag = f"{gov_tag(*gains)}.{oname}"
            X0 = run(cfg, op, (), seconds, sortie=100 * io, gains=gains)
            P0, K = subband_matrix(X0)
            res[f"{tag}.floor"] = P0
            res[f"{tag}.level"] = X0.mean(axis=1)
            for jc, ch in enumerate(CHANNELS):
                ld = [0.0] * 6
                ld[jc] = SIG_INJ
                fac = (Factor(201 + jc, 1, 0, 1, tau_s=TAU_INJ, loadings=tuple(ld)),)
                X = run(cfg, op, fac, seconds, sortie=100 * io + jc + 1, gains=gains)
                P, K = subband_matrix(X)
                W = np.zeros((NSUB, 4, 4), complex)
                for e in range(4):
                    sl = slice(4 * e, 4 * e + 4)
                    W += P[:, sl, sl] / su[:, None, None]
                res[f"{tag}.{ch}"] = W / 4.0
                # cross-engine leakage of the per-unit runs (expected ~0: engines are independent)
                res[f"{tag}.{ch}.xleak"] = P[:, 0, 4] / su
            print(f"{tag}: {time.time() - t0:.0f} s, K = {K}", flush=True)
    res["su"] = su
    np.savez(out_npz, **res, meta=np.array([TAU_INJ, SIG_INJ, seconds, DISCARD_S]), gov_grid=np.array(grid))
    print("wrote", out_npz)


if __name__ == "__main__":
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 1500.0
    if len(sys.argv) > 3:
        grid = tuple(tuple(float(v) for v in g.split(":")) for g in sys.argv[3].split(","))
    else:
        grid = GOV_GRID
    main(sys.argv[1], secs, grid)
