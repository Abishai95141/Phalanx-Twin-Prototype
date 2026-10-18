"""W2.4a-2 stage 5: staged indirect transient-weighted identification on 687-CAL (AD-34, AD-52 item 5).

Model: ``phalanx.proxy.ident`` - the deterministic closed loop (M08 governor and A/T loop <-> M07 -> M12)
from the recorded external commands (lever, A/T state and N1 command, flight condition, bleed), the indirect
method (consistent under process disturbances, which the residual absorbs; the direct method is biased,
W2.4a-1 A2). Windows: ``st5_segments.py`` (inputs only), each kept only if the empty-bank full chain is on the
N2 governor on >= ``GOV_MIN`` of its samples (per kind) (the difference Jacobians fail on limiter switches).

Stages (the W2.4a-1 A2 split: the joint fit on A/T data is ill-conditioned; per group it is recovered under
the right excitation). Stage 0 was added after the first run (the A/T windows are dominated by the
autothrottle outer loop, whose gains are placeholders, A-W2.4a-17: the plant fit compensated by driving the
inertias and word lags towards zero; ``results/stage5``):

0. **autothrottle loop on the A/T windows**, governor and plant held: ``at_kp``, ``at_ki``, ``at_rate``
   (M08 proxy A/T), fitted to the N1 and N2 words (the loop's controlled outputs);
1. **governor gains on the manual windows** (A/T off, approach lever moves), plant held: ``gov_kp``,
   ``gov_ki``, fitted to N1, N2 and FF;
2. **plant and word lags on the A/T windows**, with stages 0-1: rotor inertias ``i_lp``, ``i_hp`` (M07), the
   EGT indication lag ``tau_egt`` (M12 thermocouple flux law tau = tau_ref (W/W_ref)^-0.5: ``tau_egt`` is
   tau_ref) and the FF meter lag ``tau_ff`` (M12), all four words. The EGT lag carries the round-2 MEASURED
   prior (tau_TC,ref 0.81 s, CV range 0.55-1.18 s, read as a 95 % range of log tau: sigma_log =
   ln(1.18/0.55) / 3.92) as a Gaussian penalty scaled by the residual SD of the unpenalised fit (second
   pass); the unpenalised estimate is reported too (coordinator decision, audit #138).

Residuals: words minus model at the ACMS instants, N1/N2/EGT/FF scaled by 0.05 %, 0.05 %, 1 degC, 8 lb/h (the
word texture), times sqrt of the AD-34 transient weights of the driving command (A/T N1 command or lever).
A per-(window, engine, word) offset and gain of the model are removed (weighted LS; a first run with the
offset only let the steady-slope errors load the dynamic parameters): the steady levels and slopes are stage
1's (A-W2.4a-14), so the dynamic parameters fit the timing and shape of the responses. The gains are reported
(at the start and at the solution) as a check of the stage-1 slopes on transients.

Optimiser: Levenberg-Marquardt in log-parameters (as ``ident._lm``) with central-difference Jacobians; every
(parameter vector, segment) evaluation runs in a pool of worker processes that prepare every segment once.
The Jacobian step consistency (A-W2.4a-20) is checked at the solution with a 4x step. The prior pass starts
from the free solution (half the iterations). Stage 3 runs only if stage 2 moved a gain by more than 20 %.

Sample: the segments of ``st5_segments.py`` (n stated there). Data hygiene: 687-CAL only.

Usage::

    $PY -I analysis/proxy_quicklook/code/st5_ident.py <mat_dir> <segments.json> <out.json> [workers] [iters]
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script directory

import numpy as np
from common import ROOT, guarded, identity
from runner import base_config, real_window
from st4_tf import AT_GAINS

from phalanx.dictionary.params import load_param_set
from phalanx.engine.separate import SF_PI
from phalanx.fadec.codes import L_GOV_N2
from phalanx.proxy.config import PLATFORM
from phalanx.proxy.ident import (
    FD_STEP,
    configure,
    prepare,
    record_array,
    simulate,
    transient_weights_of,
)
from phalanx.proxy.inputs import load_inputs
from phalanx.proxy.run import simulate_flight

SCALES = np.array([0.05, 0.05, 1.0, 8.0])
#: governed share required per kind: A/T windows stay on the N2 governor; the manual approach windows cross
#: the accel / decel schedules during the lever moves (screened 2026-10-15: governed 0.94-0.97), which the
#: difference Jacobians see as switching times - their step consistency is checked at the solution
GOV_MIN = {"at": 0.98, "man": 0.94}
TAU_TC_PRIOR = 0.81
SIG_LOG_TC = float(np.log(1.18 / 0.55) / 3.92)
PLANT = ("i_lp", "i_hp", "tau_egt", "tau_ff")
GAINS = ("gov_kp", "gov_ki")
AT = ("at_kp", "at_ki", "at_rate")
FAMS = ("N1", "N2", "EGT", "FF")

_W: dict = {}


def _fadec(cfg, gains: dict[str, float] | None):
    """The configuration's M08 parameters (with ``st4_tf.AT_GAINS``: the MF1 base autothrottle gains of the
    first stage-5 run, ``ST4_AT=mf1base``) and the given overrides."""
    return cfg.fadec_params.replace(**{**AT_GAINS, **(gains or {})})


def _segment(cfg, fp, mat_dir: str, seg: dict) -> dict:
    inp = load_inputs(guarded(mat_dir, seg["flight"])).window(seg["a"], seg["b"])
    rec = inp.replay_inputs()
    prob = prepare(cfg, rec, fadec_params=fp, bleed_kgs=inp.bleed(cfg.bleed))
    y = record_array(real_window(mat_dir, seg["flight"], seg["a"], seg["b"] - seg["a"]))
    w = transient_weights_of(rec)
    n = min(prob.n_samples, y.shape[0], w.size)
    return {"prob": prob, "y": y[:n], "w": w[:n]}


def _init(mat_dir: str, segs: list[dict], held: dict[str, float], fams: list[int]):
    """Worker initializer: every segment prepared once with the held parameters (``ident.configure``: M07
    inertias, M12 word lags, M08 gains), and the word families the stage fits."""
    cfg = base_config().with_factors(())
    cfg, fp = configure(cfg, held, _fadec(cfg, None))
    _W["segs"] = [_segment(cfg, fp, mat_dir, s) for s in segs]
    _W["fams"] = list(fams)


def _shape(sim: np.ndarray, y: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-(engine, word) weighted offset and gain of the model on the window: sim' = mean(y) + b (sim -
    mean(sim)), b the weighted LS slope of y on sim. Returns (sim', b)."""
    ws = w / max(w.sum(), 1e-12)
    ms = np.einsum("t,tef->ef", ws, sim)
    my = np.einsum("t,tef->ef", ws, y)
    ds = sim - ms[None]
    vs = np.einsum("t,tef->ef", ws, ds * ds)
    b = np.einsum("t,tef->ef", ws, ds * (y - my[None])) / np.maximum(vs, 1e-300)
    return my[None] + b[None] * ds, b


def _resid_one(s: dict, names, theta) -> np.ndarray:
    """Transient-weighted, texture-scaled residual of the window's words; the per-(engine, word) offset and
    gain of the model are removed (``_shape``): the steady levels and slopes are stage 1's (A-W2.4a-14), so
    the dynamic parameters fit the timing and shape of the responses only."""
    sim = simulate(s["prob"], names, theta)
    n = min(sim.shape[0], s["y"].shape[0])
    w = s["w"][:n]
    sim_s, _b = _shape(sim[:n], s["y"][:n], w)
    r = (sim_s - s["y"][:n]) / SCALES[None, None, :] * np.sqrt(w)[:, None, None]
    return r[:, :, _W["fams"]].reshape(-1)


def _worker_gain(args):
    """(segment index, names, theta) -> the per-(engine, word) model gain b of ``_shape`` (diagnostic)."""
    k, names, theta = args
    s = _W["segs"][k]
    sim = simulate(s["prob"], names, np.asarray(theta))
    n = min(sim.shape[0], s["y"].shape[0])
    return _shape(sim[:n], s["y"][:n], s["w"][:n])[1]


def _worker_resid(args):
    """(segment index, names, theta) -> that segment's residual (every worker holds every segment)."""
    k, names, theta = args
    return _resid_one(_W["segs"][k], names, np.asarray(theta))


def _prior(names, theta, scale: float) -> np.ndarray:
    if "tau_egt" not in names or scale <= 0:
        return np.zeros(0)
    t = float(theta[list(names).index("tau_egt")])
    return np.array([(np.log(t) - np.log(TAU_TC_PRIOR)) / SIG_LOG_TC * scale])


def _resids(pool, n_seg, names, thetas, prior_scale) -> list[np.ndarray]:
    """Full residual vectors for several parameter vectors, every (theta, segment) evaluation in parallel."""
    tasks = [(k, names, th.tolist()) for th in thetas for k in range(n_seg)]
    parts = pool.map(_worker_resid, tasks, chunksize=1)
    out = []
    for i, th in enumerate(thetas):
        out.append(np.r_[np.concatenate(parts[i * n_seg : (i + 1) * n_seg]), _prior(names, th, prior_scale)])
    return out


def _jac(pool, n_seg, names, th, prior_scale, h):
    cand = []
    for j in range(th.size):
        for sgn in (1.0, -1.0):
            t = th.copy()
            t[j] = th[j] * np.exp(sgn * h)
            cand.append(t)
    rs = _resids(pool, n_seg, names, cand, prior_scale)
    return np.stack([(rs[2 * j] - rs[2 * j + 1]) / (2.0 * h) for j in range(th.size)], axis=1)


def lm(pool, n_seg, names, th0, *, prior_scale=0.0, max_iter=10, h=FD_STEP, tol=1e-4):
    """Levenberg-Marquardt in log-parameters (as ``ident._lm``); every residual and Jacobian evaluation runs
    its (parameter vector, segment) pieces in parallel."""
    names = tuple(names)
    th = np.asarray(th0, float)
    r = _resids(pool, n_seg, names, [th], prior_scale)[0]
    cost0 = cost = float(r @ r)
    lam, log = 1e-2, [(*th.tolist(), cost)]
    it = 0
    for it in range(1, max_iter + 1):
        J = _jac(pool, n_seg, names, th, prior_scale, h)
        g, H = J.T @ r, J.T @ J
        step = np.zeros_like(th)
        while True:
            step = np.linalg.solve(H + lam * np.diag(np.diag(H)), -g)
            cand = th * np.exp(np.clip(step, -0.7, 0.7))
            rc = _resids(pool, n_seg, names, [cand], prior_scale)[0]
            cc = float(rc @ rc)
            if cc < cost:
                lam = max(lam / 3.0, 1e-6)
                break
            lam *= 10.0
            if lam > 1e8:
                cand, rc, cc = th, r, cost
                break
        rel = (cost - cc) / max(cost, 1e-300)
        th, r, cost = cand, rc, cc
        log.append((*th.tolist(), cost))
        print(f"    it {it}: cost {cost:.1f} theta {np.round(th, 4)}", flush=True)
        if rel < tol and np.max(np.abs(step)) < 1e-3:
            break
    J = _jac(pool, n_seg, names, th, prior_scale, h)
    J2 = _jac(pool, n_seg, names, th, prior_scale, 4.0 * h)  # step-consistency check (A-W2.4a-20)
    dof = max(r.size - th.size, 1)
    s2 = cost / dof
    cov = np.linalg.pinv(J.T @ J) * s2
    se = th * np.sqrt(np.clip(np.diag(cov), 0, None))
    cons = [
        float(np.linalg.norm(J[:, j] - J2[:, j]) / max(np.linalg.norm(J[:, j]), 1e-300))
        for j in range(th.size)
    ]
    corr = cov / np.sqrt(np.outer(np.diag(cov), np.diag(cov)).clip(1e-300))
    return {
        "names": list(names),
        "theta": th.tolist(),
        "se": se.tolist(),
        "corr": corr.tolist(),
        "cost0": cost0,
        "cost": cost,
        "iterations": it,
        "resid_sd": float(np.sqrt(s2)),
        "cond": float(np.linalg.cond(J)),
        "jac_step_rel_diff": cons,
        "log": log,
    }


def governed(mat_dir: str, seg: dict, gains: dict[str, float] | None) -> float:
    """Share of the window's samples with every engine of the empty-bank full chain on the N2 governor."""
    cfg = base_config()
    cfg = cfg.with_factors(tuple(f for f in cfg.env.factors if f.group != 0))
    inp = load_inputs(guarded(mat_dir, seg["flight"]))
    sf = simulate_flight(
        cfg,
        inp,
        identity=identity(0),
        root=ROOT,
        window=(seg["a"], seg["b"]),
        fadec_params=_fadec(cfg, gains),
    )
    return float(np.mean(np.all(sf.regulator == L_GOV_N2, axis=0)))


def stage(mat_dir, segs, names, held, fams, workers, max_iter, label, prior=False):
    th0 = [held[k] for k in names]
    print(f"[{label}] {len(segs)} segments, {names} from {np.round(th0, 4)}; words {fams}", flush=True)
    ctx = mp.get_context("spawn")
    n = len(segs)
    rest = {k: v for k, v in held.items() if k not in names}
    with ctx.Pool(workers, initializer=_init, initargs=(mat_dir, segs, rest, fams)) as pool:
        t0 = time.time()
        res = {"free": lm(pool, n, names, th0, max_iter=max_iter), "words": [FAMS[f] for f in fams]}
        if prior:
            sc = res["free"]["resid_sd"]
            res["prior"] = lm(
                pool, n, names, res["free"]["theta"], prior_scale=sc, max_iter=max(max_iter // 2, 2)
            )
        # model gain per (window, engine, word) at the start and at the solution (1 = the steady slopes agree)
        for key, th in (("gain_start", th0), ("gain_free", res["free"]["theta"])):
            g = pool.map(_worker_gain, [(k, tuple(names), list(th)) for k in range(n)])
            res[key] = {FAMS[f]: [float(np.median(gk[:, f])) for gk in g] for f in range(len(FAMS))}
        res["seconds"] = round(time.time() - t0, 1)
    return res


def nominal_values(cfg) -> dict[str, float]:
    """The configuration's values of the identification parameters (ident.PARAMS)."""
    m12 = {f: load_param_set("M12", f"{f}_indication", platform=PLATFORM) for f in ("egt", "ff")}
    return {
        "i_lp": float(cfg.engine.p[SF_PI["i_lp"]]),
        "i_hp": float(cfg.engine.p[SF_PI["i_hp"]]),
        "tau_egt": float(m12["egt"].value("tau")),
        "tau_ff": float(m12["ff"].value("tau")),
        **{k: float(cfg.fadec_params.value(k)) for k in GAINS},
        **{k: float(cfg.fadec_params.value(k)) for k in AT},
    }


def main(mat_dir: str, seg_json: str, out: str, workers: int = 6, max_iter: int = 10) -> None:
    with open(seg_json) as fh:
        segs = json.load(fh)
    cfg = base_config()
    res: dict = {"segments": segs, "screen": {}}
    gains0 = {k: float(cfg.fadec_params.value(k)) for k in GAINS}  # the screen's governor
    kept = {}
    for kind in ("at", "man"):
        kept[kind] = []
        for s in segs[kind]:
            g = governed(mat_dir, s, gains0)
            res["screen"][f"{kind}:{s['flight']}:{s['a']}"] = g
            print(f"screen {kind} {s['flight']} {s['a']}-{s['b']}: governed {g:.3f}", flush=True)
            if g >= GOV_MIN[kind]:
                kept[kind].append(s)
    res["kept"] = kept
    nom = nominal_values(cfg)
    res["nominal"] = nom
    held = dict(nom)

    def save():
        with open(out, "w") as fh:  # partial result after each stage
            json.dump(res, fh, indent=1)

    s0 = stage(mat_dir, kept["at"], AT, held, [0, 1], workers, max_iter, "0 autothrottle")
    res["stage0"] = s0
    held.update(dict(zip(AT, s0["free"]["theta"], strict=True)))
    save()
    s1 = stage(mat_dir, kept["man"], GAINS, held, [0, 1, 3], workers, max_iter, "1 governor")
    res["stage1"] = s1
    held.update(dict(zip(GAINS, s1["free"]["theta"], strict=True)))
    save()
    s2 = stage(mat_dir, kept["at"], PLANT, held, [0, 1, 2, 3], workers, max_iter, "2 plant", prior=True)
    res["stage2"] = s2
    res["identified_free"] = {**held, **dict(zip(PLANT, s2["free"]["theta"], strict=True))}
    res["identified_prior"] = {**held, **dict(zip(PLANT, s2["prior"]["theta"], strict=True))}
    save()
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], *(int(x) for x in sys.argv[4:6]))
