"""W2.4a-2 stage 4: synthesis inputs on 687-CAL - the empty-bank chain and the real record as sub-band
cross-spectral matrices on the governed in-flight segments.

For each CAL flight of the fit sample (MF1-D order prefix, the stage-2/3 identities) and each governor setting
of the transfer grid (``st4_tf.GOV_GRID``), the full proxy chain runs **without** the engine disturbance bank
(hydraulic factors kept); its recorded words carry the input-driven content and the DASHlink texture. The MF1
estimators then give, on the class GOVFLT (airborne, PH 4-6, every synthetic engine on the N2 governor -
the paired mask of A-W2.4a-19), for the synthetic record and for the real record of the same window:

- ``P`` (NSUB, 16, 16): sub-band powers of the 16 B1 fast-band channels (MF1-D ``csd_matrix`` / ``subband``),
  with the segment count ``K`` (the spectral statistics: phases, delays, coherences);
- ``C`` (16, 16): the time-domain fast-band covariance on the whole mask (the class correlations and fast-band
  SDs, as ``mf1stats.class_stats``; Welch segments drop mask runs shorter than 128 s, the class statistics
  do not), with the sample count ``n``;
- the operating-point share of the segments (PH 4 climb, 5 cruise, 6 descent at the segment centre), which
  weights the per-point transfer matrices of ``st4_tf`` in the synthesis;
- the full MF1 ``record_stats`` of both records (the canonical statistics, to check that the statistics
  computed from P reproduce them).

Linear superposition: the bank is independent of the inputs and of the texture, so in expectation the bank
adds its own cross-spectrum to these P (``st4_fit``); the fitted bank is verified with the full chain.

Sample: n = 4 flights (MF1-D order[:4], the stage-2/3 attribution set: the smallest set whose medians
separate mechanism effects; the fit pools their segments). Data hygiene: 687-CAL only (``common.guarded``).

Usage::

    $PY -I analysis/proxy_quicklook/code/st4_base.py <mat_dir> <out.npz> [n_flights] [workers] [kp:ki,...]
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script directory

import numpy as np
from common import ROOT, flight_order, guarded, identity
from mf1stats import class_masks, fast_band, record_stats
from runner import base_config, real_window
from spectral import NPERSEG, csd_matrix, segment_starts, subband
from st4_tf import AT_GAINS, GOV_GRID, gov_tag

from phalanx.fadec.codes import L_GOV_N2
from phalanx.proxy.inputs import load_inputs, running_window
from phalanx.proxy.run import simulate_flight

CLASS = "GOVFLT"
OP_OF_PHASE = {4: 0, 5: 1, 6: 2}  # climb, cruise, descent (st4_tf.OPS order)


def empty_bank(cfg):
    """The configuration without the engine disturbance factors (hydraulic factors kept)."""
    return cfg.with_factors(tuple(f for f in cfg.env.factors if f.group != 0))


def spectra(X: np.ndarray, mask: np.ndarray, phase: np.ndarray) -> dict:
    """Sub-band powers on the mask's Welch segments (with their operating-point counts) and the time-domain
    fast-band covariance on the whole mask (the class statistics' estimator: ``mf1stats._corr``, ddof 0),
    with the operating-point sample shares."""
    starts = segment_starts(mask)
    G, K = csd_matrix(X, starts)
    ops = np.zeros(3)
    for s in starts:
        o = OP_OF_PHASE.get(int(phase[s + NPERSEG // 2]))
        if o is not None:
            ops[o] += 1
    Xm = X[:, mask]
    Xm = Xm - Xm.mean(axis=1, keepdims=True)
    C = Xm @ Xm.T / max(Xm.shape[1], 1)
    ops_td = np.array([np.sum(mask & (phase == p)) for p in OP_OF_PHASE], float)
    return {"P": subband(G), "K": K, "ops": ops, "C": C, "n": int(mask.sum()), "ops_td": ops_td}


def run_one(args: tuple[str, int, str, tuple[float, float]]) -> dict:
    fname, k, mat_dir, gains = args
    t0 = time.time()
    cfg = empty_bank(base_config())
    fp = cfg.fadec_params.replace(gov_kp=gains[0], gov_ki=gains[1], **AT_GAINS)
    inp = load_inputs(guarded(mat_dir, fname))
    a, b = running_window(inp)
    sf = simulate_flight(cfg, inp, identity=identity(k), root=ROOT, window=(a, b), fadec_params=fp)
    n = sf.record.n
    aten = inp.at_engage[a : a + n]
    gov = np.all(sf.regulator == L_GOV_N2, axis=0)
    real = real_window(mat_dir, fname, a, n)
    out: dict = {"flight": fname, "k": k, "gains": gains, "window": (a, a + n)}
    for lvl, rec in (("sim", sf.record), ("real", real)):
        m = class_masks(rec, aten, gov)[CLASS]
        out[lvl] = {
            **spectra(fast_band(rec), m, np.asarray(rec.phase)),
            "stats": record_stats(rec, aten, gov),
        }
    out["seconds"] = round(time.time() - t0, 1)
    return out


def main(mat_dir: str, out_npz: str, n_flights: int = 4, workers: int = 3, grid=GOV_GRID) -> None:
    flights = flight_order()[:n_flights]
    jobs = [(f, k, mat_dir, g) for g in grid for k, f in enumerate(flights)]
    res: dict[str, np.ndarray] = {}
    stats: dict = {}
    t0 = time.time()
    with mp.get_context("spawn").Pool(workers, maxtasksperchild=4) as pool:
        for i, r in enumerate(pool.imap_unordered(run_one, jobs), 1):
            tag = f"{gov_tag(*r['gains'])}.f{r['k']}"
            for lvl in ("sim", "real"):
                for q in ("P", "K", "ops", "C", "n", "ops_td"):
                    res[f"{tag}.{lvl}.{q}"] = np.asarray(r[lvl][q])
                stats[f"{tag}.{lvl}"] = r[lvl]["stats"]
            ks = f"K sim {r['sim']['K']} real {r['real']['K']} ops {r['sim']['ops']}"
            print(
                f"[{i}/{len(jobs)}] {tag} {r['flight']} {ks} {r['seconds']} s ({time.time() - t0:.0f} s)",
                flush=True,
            )

    np.savez(out_npz, **res, flights=np.array(flights), gov_grid=np.array(grid))
    with open(out_npz.replace(".npz", "_stats.json"), "w") as fh:
        json.dump(stats, fh, default=float)
    print("wrote", out_npz)


if __name__ == "__main__":
    g = (
        tuple(tuple(float(v) for v in x.split(":")) for x in sys.argv[5].split(","))
        if len(sys.argv) > 5
        else GOV_GRID
    )
    main(sys.argv[1], sys.argv[2], *(int(x) for x in sys.argv[3:5]), grid=g)
