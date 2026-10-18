"""MF1 report tables from aggregated sweeps (``aggregate.py`` output): targets, achievable region, Pareto
fronts, attribution (one-at-a-time and regression) and texture shifts. Writes Markdown and a JSON summary.

Usage: python -I report.py <out_dir> <agg_targets_json> <agg_sweep_json> [<agg_sweep_json> ...]

- **Targets**: real medians with flight-bootstrap CIs on the target flights (n stated), next to the 652 values
  of docs/behavioural_targets.md; base at truth / sensor / recorded level (texture shifts).
- **Two objective sets** (AD-52 item 2, joint target), each against the real medians *of the same flights and
  the same masks* (the GOV masks are paired per configuration):
  - ``battery``: B1 on the battery's airborne rule and spectra on the airborne samples (as MF1-D);
  - ``governed``: the same statistics on the samples where every synthetic engine's fuel is governed (no
    clamp: excludes the descents in which the un-identified plant sits on its minimum fuel, A-W2.4a-19).
  Groups: within-engine B1, cross-engine B1, phase structure, fast-band amplitude.
- **Achievable region**: per statistic the min-max over configurations (recorded level) and whether the real
  median lies inside. **Pareto front**: non-dominated on the four group distances.
- **Attribution**: change from ``base`` per configuration (OAT) and standardised regression coefficients over
  a joint design.
"""

from __future__ import annotations

import json
import math
import os
import sys

FAMS = ("N1", "N2", "EGT", "FF")


def objective_set(cls: str, spec: str) -> dict[str, tuple[str, ...]]:
    """Groups of objective keys for a correlation class prefix (``B1``/``GOV``) and spectral class (``SALL``/
    ``SGOV``)."""
    return {
        "within": (f"{cls}.N1-N2", f"{cls}.N1-FF", f"{cls}.N2-FF", f"{cls}.N1-EGT"),
        "cross": (f"{cls}.N1x_mean", f"{cls}.N2x_mean", f"{cls}.EGTx_mean"),
        "phase": (
            f"{spec}.N2>N1.phase_bands_deg[0]",
            f"{spec}.N2>N1.phase_bands_deg[1]",
            f"{spec}.N2>N1.coh_bands[0]",
            f"{spec}.N1>EGT.phase_bands_deg[0]",
            f"{spec}.N2>FF.tau_eq",
        ),
        "amplitude": tuple(f"FSDGOVFLT.{f}_mean" for f in FAMS),
    }


SETS = {"battery": objective_set("B1", "SALL"), "governed": objective_set("GOV", "SGOV")}
STATS = (
    "B1.N1-N2", "B1.N1-FF", "B1.N2-FF", "B1.N1-EGT", "B1.N2-EGT", "B1.N1x_mean", "B1.N2x_mean",
    "B1.EGTx_mean",
    "GOV.N1-N2", "GOV.N1-FF", "GOV.N2-FF", "GOV.N1-EGT", "GOV.N2-EGT", "GOV.N1x_mean", "GOV.N2x_mean",
    "GOV.EGTx_mean", "FLT.N1-N2", "FLT.N1-FF", "FLT.N2-FF", "FLT.N1-EGT", "CLB.N1-N2", "CRZ.N1-N2",
    "DES.N1-N2", "TAXI.N1-N2", "B2.FF>N2", "B2.FF>N1", "B2.N2>N1", "B2.FF>EGT",
    "SALL.N2>N1.phase_bands_deg[0]", "SALL.N2>N1.phase_bands_deg[1]", "SALL.N2>N1.gain_bands[0]",
    "SALL.N2>N1.gain_bands[1]", "SALL.N2>N1.coh_bands[0]", "SALL.N2>N1.coh_bands[1]", "SALL.N2>N1.tau_eq",
    "SALL.N2>N1.CF_effect", "SALL.N1>EGT.phase_bands_deg[0]", "SALL.N1>EGT.tau_eq", "SALL.N2>FF.tau_eq",
    "SALL.FF>N1.tau_eq", "SALL.FF>EGT.tau_eq",
    "SGOV.N2>N1.phase_bands_deg[0]", "SGOV.N2>N1.phase_bands_deg[1]", "SGOV.N2>N1.gain_bands[0]",
    "SGOV.N2>N1.coh_bands[0]", "SGOV.N2>N1.coh_bands[1]", "SGOV.N1>EGT.phase_bands_deg[0]",
    "SGOV.N2>FF.tau_eq",
    "SGOV.FF>N1.tau_eq", "SGOV.FF>EGT.tau_eq",
    "FSDGOVFLT.N1_mean", "FSDGOVFLT.N2_mean", "FSDGOVFLT.EGT_mean", "FSDGOVFLT.FF_mean",
    "taxi_share_of_air", "gov_share_of_air", "level.N2", "level.EGT", "level.FF",
)  # fmt: skip
#: docs/behavioural_targets.md (Tail 652 holdout, flight medians; engine 1)
T652 = {"B1.N1-N2": 0.47, "B1.N1-EGT": 0.56, "B1.N1-FF": 0.65, "B1.N2-FF": 0.67, "B1.N1x_mean": 0.81,
        "B1.N2x_mean": 0.75, "B1.EGTx_mean": 0.59, "B2.FF>N2": -0.50, "B2.FF>N1": 0.00, "B2.N2>N1": 0.50,
        "B2.FF>EGT": 0.75}  # fmt: skip


def dist(k: str, v: float, rv: float) -> float:
    """|synthetic - real| in scale units: 0.1 for correlations, coherence and lags [s]; 20 deg for phases; a
    log-ratio of 0.3 (x1.35) for the fast-band amplitudes."""
    if v is None or rv is None or math.isnan(v) or math.isnan(rv):
        return float("nan")
    if k.startswith("FSD"):
        return abs(math.log(max(v, 1e-12) / max(rv, 1e-12))) / 0.3
    return abs(v - rv) / (20.0 if "phase" in k else 0.1)


def _f(v, w=7, p=2):
    return " " * (w - 3) + "nan" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:{w}.{p}f}"


def pareto(points: dict[str, list[float]]) -> list[str]:
    front = []
    for a, pa in points.items():
        dominated = any(
            all(x <= y for x, y in zip(pb, pa, strict=True))
            and any(x < y for x, y in zip(pb, pa, strict=True))
            for b, pb in points.items()
            if b != a
        )
        if not dominated:
            front.append(a)
    return front


def _features(spec: dict) -> dict[str, float]:
    out = {}
    for grp in ("fadec", "engine", "mix"):
        for k, v in (spec.get(grp) or {}).items():
            out[f"{grp}.{k}"] = float(v)
    for k, v in (spec.get("word_delay_s") or {}).items():
        out[f"skew.{k}"] = float(v)
    for c, b in (spec.get("bank") or {}).items():
        for q, v in b.items():
            out[f"bank.{c}.{q}"] = math.log10(float(v)) if q in ("sd", "tau") and v > 0 else float(v)
    return out


def regression(cf: dict, keys_out: tuple[str, ...]) -> dict:
    """Standardised OLS coefficients of each statistic on the varied configuration parameters (sweeps with at
    least 12 configurations); log10 for bank SDs and taus."""
    import numpy as np

    names = list(cf)
    if len(names) < 12:
        return {}
    F = [_features(cf[c]["spec"]) for c in names]
    keys = sorted({k for f in F for k in f})
    X = np.array([[f.get(k, np.nan) for k in keys] for f in F])
    var = [j for j in range(len(keys)) if np.all(np.isfinite(X[:, j])) and X[:, j].std() > 0]
    if len(var) < 2:
        return {}
    keys = [keys[j] for j in var]
    X = X[:, var]
    Z = (X - X.mean(0)) / X.std(0)
    A = np.column_stack([np.ones(len(names)), Z])
    out = {}
    for k in keys_out:
        y = np.array([cf[c]["rec"].get(k, np.nan) for c in names])
        m = np.isfinite(y)
        if m.sum() < len(keys) + 3:
            continue
        beta, *_ = np.linalg.lstsq(A[m], y[m], rcond=None)
        pred = A[m] @ beta
        ss = float(np.sum((y[m] - y[m].mean()) ** 2))
        r2 = 1.0 - float(np.sum((y[m] - pred) ** 2)) / ss if ss > 0 else float("nan")
        out[k] = {"coef": {kk: float(b) for kk, b in zip(keys, beta[1:], strict=True)}, "r2": r2}
    return out


def main(out_dir: str, targets_json: str, *sweeps: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    tg = json.load(open(targets_json))
    real = tg["real"]
    base = tg["configs"].get("base")
    lines = [
        "# MF1 tables (generated by code/report.py)\n",
        f"Targets: real 687-CAL, n = {real['n']} flights.\n",
    ]
    lines.append("## Targets, base and texture shifts\n")
    lines.append(
        "Real: medians over flights [flight-bootstrap 95 % CI]. GOV statistics use the base run's governed "
        "mask. Base at truth (M07 at the sample instants), sensor (M12) and recorded (M13 words) level.\n"
    )
    lines.append("| statistic | real | 95 % CI | 652 | base tru | base sen | base rec |")
    lines.append("|---|---|---|---|---|---|---|")
    for k in STATS:
        lo, hi = real["ci"].get(k, (float("nan"), float("nan")))
        row = [k, _f(real["median"].get(k, float("nan"))), f"[{_f(lo, 5)}, {_f(hi, 5)}]",
               _f(T652.get(k, float("nan")))]  # fmt: skip
        row += [_f(base[lv].get(k)) if base else "" for lv in ("tru", "sen", "rec")]
        lines.append("| " + " | ".join(row) + " |")
    summary: dict = {"targets": {k: real["median"].get(k) for k in STATS}, "sweeps": {}}
    for sp in sweeps:
        ag = json.load(open(sp))
        name = os.path.basename(sp).replace(".json", "")
        cf = ag["configs"]
        n_fl = next(iter(cf.values()))["n"]
        lines.append(f"\n## Sweep `{name}` ({len(cf)} configurations, n = {n_fl} flights each)\n")
        real_of = {c: (e.get("real_same_flights") or ag["real"]["median"]) for c, e in cf.items()}
        lines.append("Achievable region (recorded level; real = median of the same flights and masks):\n")
        lines.append("| statistic | real | min | max | real inside |")
        lines.append("|---|---|---|---|---|")
        reg = {}
        for k in STATS:
            vals = [(c, e["rec"].get(k)) for c, e in cf.items()]
            vals = [(c, v) for c, v in vals if v is not None and not math.isnan(v)]
            if not vals:
                continue
            rvs = [real_of[c].get(k, float("nan")) for c, _v in vals]
            rvs = [r for r in rvs if not math.isnan(r)]
            rv = sorted(rvs)[len(rvs) // 2] if rvs else float("nan")
            lo, hi = min(v for _c, v in vals), max(v for _c, v in vals)
            inside = (lo <= rv <= hi) if not math.isnan(rv) else None
            reg[k] = (lo, hi, rv, inside)
            lines.append(f"| {k} | {_f(rv)} | {_f(lo)} | {_f(hi)} | {'yes' if inside else 'no'} |")
        res_sets = {}
        for sname, groups in SETS.items():
            grp, joint = {}, {}
            for c, e in cf.items():
                gd = []
                allk = []
                for ks in groups.values():
                    d = [dist(k, e["rec"].get(k, float("nan")), real_of[c].get(k, float("nan"))) for k in ks]
                    d = [x for x in d if not math.isnan(x)]
                    allk += d
                    gd.append(math.sqrt(sum(x * x for x in d) / len(d)) if d else float("nan"))
                grp[c] = gd
                joint[c] = math.sqrt(sum(x * x for x in allk) / len(allk)) if allk else float("nan")
            avail = [j for j in range(len(groups)) if all(not math.isnan(g[j]) for g in grp.values())]
            front = pareto({c: [g[j] for j in avail] for c, g in grp.items()}) if avail else []
            res_sets[sname] = {"groups": grp, "joint": joint, "pareto": front}
            lines.append(
                f"\nObjective set `{sname}`: RMS distance to the real medians per group (scale units: 0.1 "
                "for correlations, coherence and lags [s], 20 deg for phases, x1.35 for amplitudes; nan = "
                "statistic not computed in this sweep); Pareto = non-dominated on the available groups "
                "(best 15 "
                "by joint distance shown, all Pareto points):\n"
            )
            lines.append("| configuration | joint | " + " | ".join(groups) + " | Pareto |")
            lines.append("|---|---|" + "---|" * len(groups) + "---|")
            order = sorted(joint, key=joint.get)
            shown = [c for i, c in enumerate(order) if i < 15 or c in front or c == "base"]
            for c in shown:
                g = " | ".join(f"{x:.2f}" for x in grp[c])
                lines.append(f"| {c} | {joint[c]:.2f} | {g} | {'*' if c in front else ''} |")
        shortest = min(cf, key=len)
        ref = "base" if "base" in cf else (shortest if all(c.startswith(shortest) for c in cf) else None)
        if ref is not None:
            b = cf[ref]["rec"]
            keys = [k for k in STATS if k in b]
            lines.append(f"\nOne-at-a-time attribution: change from `{ref}` (recorded level)\n")
            lines.append("| configuration | " + " | ".join(keys) + " |")
            lines.append("|---|" + "---|" * len(keys))
            for c in sorted(cf):
                if c != ref:
                    e = cf[c]["rec"]
                    lines.append(
                        f"| {c} | " + " | ".join(_f(e.get(k, float("nan")) - b[k], 5) for k in keys) + " |"
                    )
        objs = tuple(dict.fromkeys(k for g in SETS.values() for ks in g.values() for k in ks))
        coef = regression(cf, objs)
        if coef:
            feats = sorted({f for v in coef.values() for f in v["coef"]})
            lines.append(
                "\nRegression attribution over the joint design (OLS on the standardised parameters; log10 "
                "for bank SDs and taus; coefficient = change per 1 SD of the parameter; R^2 last):\n"
            )
            lines.append("| statistic | " + " | ".join(feats) + " | R^2 |")
            lines.append("|---|" + "---|" * (len(feats) + 1))
            for k, v in coef.items():
                cells = " | ".join(_f(v["coef"].get(f, float("nan")), 5) for f in feats)
                lines.append(f"| {k} | {cells} | {v['r2']:.2f} |")
        summary["sweeps"][name] = {"region": reg, "sets": res_sets, "regression": coef}
    with open(os.path.join(out_dir, "mf1_tables.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    with open(os.path.join(out_dir, "mf1_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
    print("wrote", out_dir)


if __name__ == "__main__":
    main(*sys.argv[1:])
