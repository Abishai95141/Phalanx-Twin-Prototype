"""Named MF1 sweeps: lists of configuration dicts (points of declared ranges; see runner.py for the keys).

Declared ranges (configs/proxy_dashlink/params/*.yaml `sweep`, docs/assumptions.md):
- M08 (A-W1.3b-3/-10, A-W1.3b-2): gov_kp [0, 8] with the Kp window ~1-4 (Kp 1 limit-cycles the W1 plant at
  ground idle, Kp >= 3-5 destroys the small-signal signs, AD-50); gov_ki [0.1, 5] 1/s; ps3_tau [0, 0.2] s;
  at_kp [0, 0.5]; at_ki [0, 0.3] 1/s; at_rate [0.01, 0.5] 1/s;
- M07 (A-W2.4a-6, A-W2.4a-10): H_LP [0.2, 2.0] s, H_HP [0.1, 1.0] s; k_eta_fan_face [0, 0.6];
- M03 (A-W1.1-1): loadings fuel <= 0.02, comb <= 0.01, inlet <= 0.01, shaft <= 0.03, fan <= 0.02; factor
  correlation times [0.05, 5] s.

``BASE`` is the committed proxy configuration with the autothrottle gains at a point that tracks the recorded
N1 command (the W1 fixture values 0.05/0.02/0.05 left a ~40 s take-off lag; A-W2.4a-17).
"""

from __future__ import annotations

import itertools

import numpy as np

BASE_FADEC = {"at_kp": 0.3, "at_ki": 0.2, "at_rate": 0.1}


def _spec(name: str, **kw) -> dict:
    s = {"name": name, "fadec": dict(BASE_FADEC)}
    for k, v in kw.items():
        if k == "fadec":
            s["fadec"].update(v)
        else:
            s[k] = v
    return s


def base() -> list[dict]:
    return [_spec("base")]


def oat() -> list[dict]:
    """One-at-a-time around BASE over each declared range (mechanism attribution)."""
    out = [_spec("base")]
    for v in (1.0, 1.5, 3.0, 4.0):
        out.append(_spec(f"gov_kp={v}", fadec={"gov_kp": v}))
    for v in (0.3, 3.0):
        out.append(_spec(f"gov_ki={v}", fadec={"gov_ki": v}))
    for v in (0.0, 0.2):
        out.append(_spec(f"ps3_tau={v}", fadec={"ps3_tau": v}))
    for kp, ki, rt in ((0.1, 0.05, 0.05), (0.5, 0.3, 0.2)):
        out.append(_spec(f"at={kp}/{ki}/{rt}", fadec={"at_kp": kp, "at_ki": ki, "at_rate": rt}))
    for v in (0.2, 1.2, 2.0):
        out.append(_spec(f"H_LP={v}", engine={"H_LP": v}))
    for v in (0.15, 0.6):
        out.append(_spec(f"H_HP={v}", engine={"H_HP": v}))
    for v in (0.0, 0.3, 0.45, 0.6):
        out.append(_spec(f"keta={v}", engine={"k_eta_fan_face": v}))
    for ch in ("fuel", "comb", "inlet", "shaft", "fan"):
        for m in (0.0, 3.0):
            out.append(_spec(f"mix.{ch}x{m}", mix={ch: m}))
    for m in (0.0, 3.0):
        out.append(_spec(f"mix.commonx{m}", mix={"common": m}))
        out.append(_spec(f"mix.unitx{m}", mix={"unit": m}))
    for d in (0.1, 0.2):
        out.append(_spec(f"skew.N1+{d}", word_delay_s={"N1": d}))
    return out


def lp() -> list[dict]:
    """LP-spool dynamics x LP-specific input (coordinator framing: primary and secondary candidates)."""
    out = []
    for h, k, fan in itertools.product((0.6, 1.2, 2.0), (0.0, 0.2, 0.45), (1.0, 3.0)):
        out.append(
            _spec(f"H_LP={h},keta={k},fan x{fan}", engine={"H_LP": h, "k_eta_fan_face": k}, mix={"fan": fan})
        )
    return out


#: joint space-filling design over the declared ranges (multipliers apply to the committed bank's loadings and
#: are clipped at the declared loading maxima by the runner)
LHS_RANGES = {
    "mix.fuel": (0.0, 2.0),
    "mix.comb": (0.0, 2.0),
    "mix.inlet": (0.0, 3.3),
    "mix.shaft": (0.0, 3.75),
    "mix.fan": (0.0, 5.0),
    "mix.common": (0.5, 3.0),
    "mix.unit": (0.3, 1.5),
    "engine.k_eta_fan_face": (0.0, 0.6),
    "engine.H_LP": (0.3, 1.2),
    "engine.H_HP": (0.15, 0.6),
    "fadec.gov_kp": (1.0, 4.0),
    "fadec.gov_ki": (0.3, 3.0),
    "fadec.ps3_tau": (0.0, 0.2),
    "fadec.at_kp": (0.1, 0.5),
    "fadec.at_ki": (0.05, 0.3),
    "fadec.at_rate": (0.05, 0.3),
    "skew.N1": (0.0, 0.2),
}
N_LHS = 48


def lhs() -> list[dict]:
    """Latin-hypercube design (N_LHS points) over LHS_RANGES; keyed stream (scenario mf1-reach-design), so the
    design is reproducible and independent of every simulation stream."""
    from common import ROOT

    from phalanx.core.rng import KeyPath, RngService, StreamRegistry
    from phalanx.validation.samples import SAMPLE_STREAM

    svc = RngService(ROOT, StreamRegistry([SAMPLE_STREAM]))
    path = KeyPath.of(
        scenario="mf1-reach-design", subsystem=SAMPLE_STREAM.subsystem, component=SAMPLE_STREAM.component
    )
    gen = svc.generator(path, 0)
    keys = list(LHS_RANGES)
    u = np.empty((N_LHS, len(keys)))
    for j in range(len(keys)):
        u[:, j] = (gen.permutation(N_LHS) + gen.random(N_LHS)) / N_LHS
    out = []
    for i in range(N_LHS):
        spec = _spec(f"lhs{i:02d}")
        for j, k in enumerate(keys):
            lo, hi = LHS_RANGES[k]
            v = round(float(lo + u[i, j] * (hi - lo)), 4)
            grp, name = k.split(".", 1)
            if grp == "skew":
                spec.setdefault("word_delay_s", {})[name] = v
            else:
                spec.setdefault(grp, {})[name] = v
        out.append(spec)
    return out


#: per-channel bank design (AD-32 structure: one aircraft-common and one per-unit OU factor per engine
#: channel): total SD (log-uniform from 1/200 of the declared maximum loading to the maximum), common share of
#: the variance, correlation time (log-uniform over [0.1, 3] s inside the declared [0.05, 5] s)
BANK_CH = ("fuel", "comb", "inlet", "shaft", "fan")
BANK_MAX = {"fuel": 0.02, "comb": 0.01, "inlet": 0.01, "shaft": 0.03, "fan": 0.02}
BANK_OTHER = {
    "engine.H_LP": (0.3, 1.2),
    "engine.k_eta_fan_face": (0.0, 0.6),
    "fadec.gov_kp": (1.0, 4.0),
    "fadec.at_kp": (0.1, 0.5),
    "fadec.at_ki": (0.05, 0.3),
    "skew.N1": (0.0, 0.2),
}
N_BANK = 32


def bank() -> list[dict]:
    """Joint Latin-hypercube design over the disturbance bank (per channel: SD, common share, tau) and the
    LP-dynamics / controller / skew parameters; keyed stream (scenario mf1-reach-bank)."""
    from common import ROOT

    from phalanx.core.rng import KeyPath, RngService, StreamRegistry
    from phalanx.validation.samples import SAMPLE_STREAM

    svc = RngService(ROOT, StreamRegistry([SAMPLE_STREAM]))
    path = KeyPath.of(
        scenario="mf1-reach-bank", subsystem=SAMPLE_STREAM.subsystem, component=SAMPLE_STREAM.component
    )
    gen = svc.generator(path, 0)
    dims = [f"bank.{c}.{q}" for c in BANK_CH for q in ("sd", "rho", "tau")] + list(BANK_OTHER)
    u = np.empty((N_BANK, len(dims)))
    for j in range(len(dims)):
        u[:, j] = (gen.permutation(N_BANK) + gen.random(N_BANK)) / N_BANK
    out = []
    for i in range(N_BANK):
        spec = _spec(f"bank{i:02d}")
        bank_spec: dict = {c: {} for c in BANK_CH}
        for j, d in enumerate(dims):
            x = float(u[i, j])
            if d.startswith("bank."):
                _b, c, q = d.split(".")
                if q == "sd":
                    hi = BANK_MAX[c]
                    v = hi / 200.0 * (200.0**x)
                elif q == "rho":
                    v = x
                else:
                    v = 0.1 * (30.0**x)
                bank_spec[c][q] = round(v, 6)
            else:
                lo, hi = BANK_OTHER[d]
                grp, name = d.split(".", 1)
                v = round(lo + x * (hi - lo), 4)
                if grp == "skew":
                    spec.setdefault("word_delay_s", {})[name] = v
                else:
                    spec.setdefault(grp, {})[name] = v
        spec["bank"] = bank_spec
        out.append(spec)
    return out


def verify() -> list[dict]:
    """Frontier configurations re-checked on more flights: the specs listed (by name) in
    ``results/verify_configs.json`` (written after the joint sweep, from its Pareto front)."""
    import json

    from common import RESULTS

    names = json.loads((RESULTS / "verify_configs.json").read_text())["configs"]
    pool = {s["name"]: s for s in [*bank(), *oat(), *lhs()]}
    return [pool[n] for n in names if n != "base"]  # base at n = 20 is the targets run


def proto() -> list[dict]:
    """PROTOTYPE and sensitivity variants around the joint design's best point (named in
    ``results/proto_base.json``; chosen by the governed joint distance before these runs): the thermocouple
    lag of the EGT word (MEASURED 0.81 s; 1.2 and 1.75 s as sensitivity, the latter the Tejas assumption),
    AD-46's second LP path (fan_face efficiency-only, flow share 0) at a high LP-specific loading, and the
    word-slot skew prototype."""
    import copy
    import json

    from common import RESULTS

    name = json.loads((RESULTS / "proto_base.json").read_text())["base"]
    b = next(s for s in bank() if s["name"] == name)
    out = [copy.deepcopy(b)]
    for tau in (1.2, 1.75):
        s = copy.deepcopy(b)
        s["name"] = f"{name}+tc{tau}"
        s["sensor"] = {"tau_egt": tau}
        out.append(s)
    for share, fan_sd in ((1.0, 0.01), (0.0, 0.01)):
        s = copy.deepcopy(b)
        s["name"] = f"{name}+fan{fan_sd}+share{share}"
        s["bank"]["fan"] = {"sd": fan_sd, "rho": 0.5, "tau": 1.0}
        s["engine"]["fan_face_flow_share"] = share
        s["engine"]["k_eta_fan_face"] = 0.2
        out.append(s)
    for skew in (0.0, 0.15):
        s = copy.deepcopy(b)
        s["name"] = f"{name}+skew{skew}"
        s["word_delay_s"] = {"N1": skew}
        out.append(s)
    # the efficiency-only path at a meaningful size: k_eta and the fan SD at their declared maxima (an LP
    # shaft-torque disturbance of about 1.2 % SD), added after the first proto run showed share 0 at k_eta 0.2
    # is too small to move anything
    s = copy.deepcopy(b)
    s["name"] = f"{name}+lptorque"
    s["bank"]["fan"] = {"sd": 0.02, "rho": 0.5, "tau": 1.0}
    s["engine"]["fan_face_flow_share"] = 0.0
    s["engine"]["k_eta_fan_face"] = 0.6
    out.append(s)
    s = copy.deepcopy(b)  # weakest governing inside the Kp window (AD-50: weak small-signal governing)
    s["name"] = f"{name}+kp1"
    s["fadec"]["gov_kp"] = 1.0
    out.append(s)
    return out


def st2() -> list[dict]:
    """W2.4a-2 stage 2: the W2.4a-1 reference points on the identified plant (stage 1): base, the joint
    design's best point ``bank19`` and its LP shaft-torque variant (the AD-46-amended LP path)."""
    pool = {s["name"]: s for s in [*base(), *bank(), *proto()]}
    return [pool[n] for n in ("base", "bank19", "bank19+lptorque")]


def st2x() -> list[dict]:
    """W2.4a-2 stage 2 small re-sweep on the identified plant: one disturbance channel at a time (the others
    off; the committed loading, x3 for the small ones so the channel dominates the fast band), to read which
    driver puts T5 ahead of or behind the spools, plus the 1.75 s thermocouple sensitivity on base."""
    out = []
    for ch, m in (("fuel", 1.0), ("comb", 3.0), ("inlet", 3.0), ("shaft", 1.0), ("fan", 3.0)):
        mix = {c: 0.0 for c in ("fuel", "comb", "inlet", "shaft", "fan")}
        mix[ch] = m
        out.append(_spec(f"only.{ch}x{m:g}", mix=mix))
    out.append(_spec("base+tc1.75", sensor={"tau_egt": 1.75}))
    return out


def st3() -> list[dict]:
    """W2.4a-2 stage 3: the gas-path thermal-lag PROTOTYPE (A-W2.4a-23; not adopted) on the identified plant
    with the demand pre-map: bank19 (fuel-dominated, the W2.4a-1 joint-design best point) and base without
    the lag (references) and with tau 1 / 2 / 3 s (kappa 1, a first-order lag) and tau 2 s, kappa 0.6 (a
    lag-lead); base with tau 2 and 4 s."""
    import copy

    pool = {s["name"]: s for s in [*base(), *bank()]}
    out = [copy.deepcopy(pool["base"]), copy.deepcopy(pool["bank19"])]
    for ref, taus in (
        ("bank19", ((1.0, 1.0), (2.0, 1.0), (3.0, 1.0), (2.0, 0.6))),
        ("base", ((2.0, 1.0), (4.0, 1.0))),
    ):
        for tau, kap in taus:
            s = copy.deepcopy(pool[ref])
            s["name"] = f"{ref}+gp{tau:g}k{kap:g}"
            s.setdefault("engine", {}).update({"gp_lag_tau": tau, "gp_lag_kappa": kap})
            out.append(s)
    return out


def st3v() -> list[dict]:
    """W2.4a-2 stage 3 check at n = 4: the two best st3 points (by the governed EGT phase and amplitude) and the
    bank19 reference."""
    pool = {s["name"]: s for s in st3()}
    return [pool[n] for n in ("bank19", "bank19+gp2k1", "bank19+gp3k1")]


def st4v() -> list[dict]:
    """W2.4a-2 stage 4 verification with the full chain: the bank identified by linear spectral synthesis
    (``results/stage4/st4_fit_{pooled,median}.json``) at each governor setting fitted, and the empty bank (the synthesis' P0
    reference). The autothrottle gains are the configuration's (stage 5), not ``BASE_FADEC``."""
    import json

    from common import RESULTS

    out = [{"name": "st4.empty", "bank": {"fuel": {"sd": 0.0, "rho": 0.0, "tau": 1.0}}}]
    settings = []
    for fname in ("st4_fit_pooled.json", "st4_fit_median.json"):  # pass 2 (the pooled bank is adopted)
        with open(RESULTS / "stage4" / fname) as fh:
            settings += list(json.load(fh)["settings"].items())
    for tag, r in settings:
        kp, ki = r["gains"]
        bank = {c: {k: b[k] for k in ("sd", "rho", "tau")} for c, b in r["bank"].items()}
        name = f"st4.{tag}" + ("" if r.get("aggregation", "pooled") == "pooled" else "." + r["aggregation"])
        spec = {"name": name, "fadec": {"gov_kp": kp, "gov_ki": ki}, "bank": bank}
        if abs(r["s_tc"] - 1.0) > 1e-6:
            spec["sensor"] = {"tau_egt": r["tau_tc_ref"]}
        out.append(spec)
    return out


SWEEPS = {
    "base": base, "oat": oat, "lp": lp, "lhs": lhs, "bank": bank, "verify": verify, "proto": proto,
    "st2": st2, "st2x": st2x, "st3": st3, "st3v": st3v, "st4v": st4v,
}  # fmt: skip
