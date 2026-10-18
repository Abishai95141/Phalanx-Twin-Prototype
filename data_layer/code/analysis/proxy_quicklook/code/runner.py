"""MF1 runs: one configuration x one CAL flight -> the MF1 statistics of the synthetic record at three levels
(truth, sensor = M12 output, recorded = M13 DASHlink words) and of the paired real record (targets).

A configuration is a JSON-able dict (points of the declared sweep ranges; nothing is fitted):

- ``fadec``: M08 parameter overrides (gov_kp, gov_ki, ps3_tau, at_kp, at_ki, at_rate, ...);
- ``engine``: ``H_LP`` / ``H_HP`` (rotor energy time constants, A-W2.4a-6: the kernel inertias scale with H),
  ``k_eta_fan_face`` (AD-46);
- ``mix``: disturbance-bank multipliers per engine channel (``fuel``, ``comb``, ``inlet``, ``shaft``, ``fan``)
  and per scope (``common``, ``unit``), applied to the loadings of `configs/proxy_dashlink/params/M03`
  (clipped to the declared loading ranges); ``tau``: multipliers of the factor correlation times by channel;
- ``word_delay_s``: PROTOTYPE recorder word-slot skew per family (``phalanx.proxy.run``; not adopted);
- ``engine.fan_face_flow_share``: PROTOTYPE AD-46 second LP path (efficiency-only fan_face; not adopted);
- ``sensor``: EGT/FF word time constants (``tau_egt``, ``tau_ff``) for the thermocouple-lag sensitivity;
- ``proto``: PROTOTYPE mechanisms behind flags (see ``prototypes.py``; not adopted).

The synthetic window is ``phalanx.proxy.inputs.running_window`` (whole flight with all engines running, from
levers and PH only), so the taxi composition of the battery's airborne rule is reproduced (MF1-D D2). The
real record is sliced to the same samples.
"""

from __future__ import annotations

import time
from dataclasses import replace

import numpy as np
from common import ROOT, guarded, identity
from mf1stats import record_stats

from phalanx.engine.separate import SF_PI
from phalanx.environment.disturbances import Factor
from phalanx.fadec.codes import L_GOV_N2
from phalanx.proxy.config import ProxyConfig, load_proxy_config
from phalanx.proxy.inputs import load_inputs, running_window
from phalanx.proxy.run import simulate_flight
from phalanx.validation.dashlink import load_record
from phalanx.validation.flightdata import FlightRecord

#: declared loading ranges (configs/proxy_dashlink/params/M03.yaml `sweep`), in loading order
LOAD_MAX = {"fuel": 0.02, "comb": 0.01, "inlet": 0.01, "shaft": 0.03, "fan": 0.02}
CHANNELS = ("fuel", "comb", "inlet", "shaft", "fan")
H_LP0, H_HP0 = 0.6, 0.3  # proxy M07 defaults (A-W2.4a-6)

_CFG: ProxyConfig | None = None


def base_config() -> ProxyConfig:
    global _CFG
    if _CFG is None:
        _CFG = load_proxy_config()
    return _CFG


def factors_with_mix(cfg: ProxyConfig, mix: dict | None, tau: dict | None) -> tuple[Factor, ...]:
    mix = mix or {}
    tau = tau or {}
    out = []
    for f in cfg.env.factors:
        if f.group != 0:
            out.append(f)
            continue
        scope_m = float(mix.get("common" if f.scope == 0 else "unit", 1.0))
        ld = list(f.loadings)
        for c, name in enumerate(CHANNELS):
            if c < len(ld):
                ld[c] = min(ld[c] * float(mix.get(name, 1.0)) * scope_m, LOAD_MAX[name])
        dom = max(range(len(CHANNELS)), key=lambda c: f.loadings[c] if c < len(f.loadings) else 0.0)
        ts = f.tau_s * float(tau.get(CHANNELS[dom], 1.0)) if f.tau_s > 0 else f.tau_s
        out.append(replace(f, loadings=tuple(ld), tau_s=min(max(ts, 0.05), 5.0) if f.tau_s > 0 else ts))
    return tuple(out)


def bank_factors(cfg: ProxyConfig, bank: dict) -> tuple[Factor, ...]:
    """The engine-group factors replaced by one aircraft-common and one per-unit OU factor per channel
    (AD-32 structure): loading SD x sqrt(common share) / SD x sqrt(1 - common share), correlation time tau;
    hydraulic factors kept. Factor ids 101-110 (their own RNG streams)."""
    out = [f for f in cfg.env.factors if f.group != 0]
    for j, c in enumerate(CHANNELS):
        b = bank.get(c)
        if not b:
            continue
        sd, rho, tau = float(b["sd"]), float(b["rho"]), float(b["tau"])
        for k, (scope, share) in enumerate(((0, rho), (1, 1.0 - rho))):
            ld = [0.0] * 6
            ld[j] = min(sd * float(np.sqrt(max(share, 0.0))), LOAD_MAX[c])
            out.append(
                Factor(101 + 2 * j + k, scope, 0, 1, tau_s=min(max(tau, 0.05), 5.0), loadings=tuple(ld))
            )
    return tuple(out)


def configure(spec: dict) -> tuple[ProxyConfig, object]:
    cfg = base_config()
    eng = dict(spec.get("engine", {}))
    p: dict[str, float] = {}
    if "H_LP" in eng:
        p["i_lp"] = float(cfg.engine.p[SF_PI["i_lp"]]) * float(eng["H_LP"]) / H_LP0
    if "H_HP" in eng:
        p["i_hp"] = float(cfg.engine.p[SF_PI["i_hp"]]) * float(eng["H_HP"]) / H_HP0
    if "k_eta_fan_face" in eng:
        p["k_eta_fan_face"] = float(eng["k_eta_fan_face"])
    if "fan_face_flow_share" in eng:  # PROTOTYPE flag (A-W2.4a-18)
        p["fan_face_flow_share"] = float(eng["fan_face_flow_share"])
    for k in ("gp_lag_tau", "gp_lag_kappa"):  # PROTOTYPE gas-path thermal lag (A-W2.4a-23, stage 3)
        if k in eng:
            p[k] = float(eng[k])
    if p:
        cfg = cfg.with_engine(**p)
    if spec.get("mix") or spec.get("tau"):
        cfg = cfg.with_factors(factors_with_mix(cfg, spec.get("mix"), spec.get("tau")))
    if spec.get("bank"):
        cfg = cfg.with_factors(bank_factors(cfg, spec["bank"]))
    fp = cfg.fadec_params.replace(**spec["fadec"]) if spec.get("fadec") else None
    if spec.get("sensor"):  # sensitivity of the word lags (tau_egt MEASURED 0.81 s, tau_ff 0.218 s)
        from phalanx.proxy.ident import configure as _sens

        cfg, fp2 = _sens(cfg, {k: float(v) for k, v in spec["sensor"].items()}, fp)
        fp = fp2 if spec.get("fadec") else None
    return cfg, fp


def real_window(mat_dir: str, fname: str, a: int, n: int) -> FlightRecord:
    rec = load_record(guarded(mat_dir, fname))
    sl = slice(a, a + n)
    return FlightRecord(
        flight_id=rec.flight_id,
        rate_hz=rec.rate_hz,
        outputs={f: np.asarray(v)[:, sl] for f, v in rec.outputs.items()},
        pla=np.asarray(rec.pla)[:, sl],
        theta=np.asarray(rec.theta)[sl],
        delta=np.asarray(rec.delta)[sl],
        phase=np.asarray(rec.phase)[sl],
        units=rec.units,
        meta={**rec.meta, "window": f"{a}:{a + n}"},
    )


def tracking(inp, a: int, n: int, rec: FlightRecord) -> dict[str, float]:
    """A/T tracking of the synthetic engines: median |N1 - N1C| (percent) on airborne A/T-engaged samples."""
    at = inp.at_engage[a : a + n] == 1
    ph = np.isin(inp.phase[a : a + n], (4, 5, 6))
    m = at & ph
    if m.sum() < 40:
        return {}
    err = np.abs(np.asarray(rec.outputs["N1"])[0, m] - inp.n1_cmd_pct[a : a + n][m])
    return {"at_n1_err_med": float(np.median(err)), "at_n1_err_p90": float(np.quantile(err, 0.9))}


def run_one(args: tuple[dict, str, int, str, bool]) -> dict:
    """(spec, flight file, order index, MAT dir, with_real) -> result row."""
    spec, fname, k, mat_dir, with_real = args
    t0 = time.time()
    cfg, fp = configure(spec)
    inp = load_inputs(guarded(mat_dir, fname))
    a, b = running_window(inp)
    sf = simulate_flight(
        cfg, inp, identity=identity(k), root=ROOT, window=(a, b), fadec_params=fp,
        word_delay_s=spec.get("word_delay_s"),
    )  # fmt: skip
    n = sf.record.n
    aten = inp.at_engage[a : a + n]
    gov = np.all(sf.regulator == L_GOV_N2, axis=0) if sf.regulator is not None else None
    row = {
        "config": spec.get("name", "?"),
        "spec": spec,
        "flight": fname,
        "k": k,
        "window": [a, a + n],
        "limiter_share": {str(i): round(float(v), 4) for i, v in enumerate(sf.limiter_share) if v > 0},
        "digest": sf.world_digest,
        "n_surge": None if sf.n_surge is None else [int(x) for x in sf.n_surge],
        "rec": record_stats(sf.record, aten, gov),
        "sen": record_stats(sf.sensor, aten, gov),
        "tru": record_stats(sf.truth, aten, gov),
        **tracking(inp, a, n, sf.record),
    }
    if with_real:
        row["real"] = record_stats(real_window(mat_dir, fname, a, n), aten, gov)
    row["seconds"] = round(time.time() - t0, 1)
    return row


__all__ = ["base_config", "configure", "real_window", "run_one"]
