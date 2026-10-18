"""Backtest and champion selection for the removal-risk model (``engines/hazard.py``), then the final fit.

Seeds: the training worlds' seeds in order; the last is the held-out test seed, the one before it the validation seed.

1. Challenger choice (test seed untouched): fit ``age`` and ``landmark`` on the seeds before the validation seed,
   compare their Brier score on the validation seed; the better one is the challenger.
2. Gate on the held-out seed: challenger and the class-exposure baseline (``class_exp``) are fitted on every seed but
   the test seed. The challenger becomes champion only if its Brier score on the test seed beats the baseline's;
   otherwise the baseline stays champion (as the false-alarm model keeps its Beta-Binomial champion).
3. The champion's kind is refitted on all seeds and saved to ``<train>/hazard_model.json`` (what the live twin reads).

Evaluation unit: landmark rows — every installation spell still fitted at age a ∈ {0, 10, 20, …} FH, predicting a
confirmed-fault removal within the next H = 15 FH (about 30 days of flying); rows censored inside the window are
dropped. Scores on the classes with ≥ 10 events: Brier, landmark AUC, Harrell's C-index (residual life vs predicted
risk over landmark rows), calibration in quintiles of predicted risk.

Writes proto/eval/hazard_backtest.json and .md. Usage: <ground python> proto/eval/hazard_backtest.py [train_dir]
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "ground"), str(HERE.parent / "ground" / "engines")]

import hazard as hz  # noqa: E402
from interfaces import SOURCE_LABEL, Source  # noqa: E402
from store import Root, Store  # noqa: E402

warnings.filterwarnings("ignore")
H_FH = 15.0
BIG = 2**62
COVS = ["age_fh", "alarms_last10", "alarm_rate", "prior_rtok", "inferred_install"]


def eval_rows(sp: pd.DataFrame) -> pd.DataFrame:
    lm = hz.landmark_rows(sp)
    if not len(lm):
        return lm
    lm["y"] = ((lm.event == 1) & (lm.resid_fh <= H_FH)).astype(int)
    return lm[(lm.y == 1) | (lm.resid_fh >= H_FH)].reset_index(drop=True)


def predict(m: hz.HazardModel, lm: pd.DataFrame) -> np.ndarray:
    return np.array([m.risk(r.klass, r.age_fh, H_FH, {c: getattr(r, c) for c in COVS}) for r in lm.itertuples()])


def scores(p: np.ndarray, lm: pd.DataFrame) -> dict:
    from lifelines.utils import concordance_index
    from sklearn.metrics import roc_auc_score

    y = lm.y.to_numpy()
    two = len(np.unique(y)) > 1
    return {
        "landmarks": int(len(y)),
        "events_in_window": int(y.sum()),
        "brier": round(float(np.mean((p - y) ** 2)), 6),
        "auc": round(float(roc_auc_score(y, p)), 4) if two else None,
        "c_index": round(float(concordance_index(lm.resid_fh, -p, lm.event)), 4) if two else None,
    }


def calibration(p: np.ndarray, lm: pd.DataFrame) -> list[dict]:
    out = []
    q = pd.qcut(pd.Series(p).rank(method="first"), 5, labels=False).to_numpy()
    for b in range(5):
        sel = q == b
        out.append({"bin": b + 1, "n": int(sel.sum()), "mean_predicted": round(float(p[sel].mean()), 5),
                    "observed": round(float(lm.y.to_numpy()[sel].mean()), 5)})
    return out


def main(train: Path) -> int:
    man = json.loads((train / "train_manifest.json").read_text())
    seeds = sorted({d["world_seed"] for d in man["worlds"]})
    spells = {}
    for k in seeds:
        st = Store([Root(train / f"seed={k}" / "fleet", Source.TRAIN, world_seed=k)])
        spells[k] = hz.build_spells(st, BIG, world_seed=k)
    cat = lambda ks: pd.concat([spells[k] for k in ks], ignore_index=True)  # noqa: E731
    tr_seeds, te_seeds = seeds[:-1], seeds[-1:]
    fit_s, val_s = tr_seeds[:-1], tr_seeds[-1:]

    # 1. challenger choice on the validation seed
    selection = {}
    fs, v_all = cat(fit_s), eval_rows(cat(val_s))
    for kind in ("age", "landmark"):
        mv = hz.HazardModel.fit(fs, kind=kind)
        v = v_all[v_all.klass.isin([k for k in mv.classes if mv.sufficient(k)])]
        selection[kind] = {"fit_seeds": fit_s, "validation_seeds": val_s, **scores(predict(mv, v), v)}
    challenger = min(selection, key=lambda k: selection[k]["brier"])

    # 2. gate on the held-out seed
    tr = cat(tr_seeds)
    models = {kind: hz.HazardModel.fit(tr, kind=kind, train_seeds=tr_seeds) for kind in ("class_exp", "age", "landmark")}
    fit_classes = [k for k in models["class_exp"].classes if models["class_exp"].sufficient(k)]
    te = eval_rows(cat(te_seeds))
    te_fit = te[te.klass.isin(fit_classes)].reset_index(drop=True)
    preds = {kind: predict(m, te_fit) for kind, m in models.items()}
    test = {kind: scores(p, te_fit) for kind, p in preds.items()}
    promoted = test[challenger]["brier"] < test["class_exp"]["brier"]
    champion = challenger if promoted else "class_exp"
    lm_model = models["landmark"]
    effects = {c: round(lm_model.params.get(f"lambda_:{c}", float("nan")), 4) for c in lm_model.covariates}

    # 3. final fit of the champion's kind on all seeds
    final = hz.HazardModel.fit(cat(seeds), kind=champion, train_seeds=seeds)
    final.champion_note = (f"held-out seed {te_seeds[0]}: Brier {test[champion]['brier']} vs class-exposure baseline "
                           f"{test['class_exp']['brier']}" if promoted else
                           f"challenger {challenger} did not beat it on held-out seed {te_seeds[0]}")
    final.to_json(train / "hazard_model.json")

    doc = {
        "source_label": SOURCE_LABEL[Source.TRAIN],
        "model_id": hz.MODEL_ID,
        "model_version": hz.MODEL_VERSION,
        "note": "Backtest on simulated (synthetic, unvalidated) training worlds: shows the pipeline works, not that "
                "it predicts real failures.",
        "seeds": {"fit_for_selection": fit_s, "validation": val_s, "train": tr_seeds, "test": te_seeds},
        "horizon_fh": H_FH,
        "landmark_step_fh": hz.LANDMARK_STEP,
        "penalizer": hz.PENALIZER,
        "min_events": hz.MIN_EVENTS,
        "train_events_by_class": models["class_exp"].events,
        "fit_classes": fit_classes,
        "insufficient_evidence_classes": [k for k in models["class_exp"].classes if k not in fit_classes],
        "kinds": hz.KINDS,
        "challenger_selection_on_validation": selection,
        "challenger": challenger,
        "test_scores_fit_classes": test,
        "champion": {
            "kind": champion,
            "label": hz.KINDS[champion],
            "why": (f"chosen over the other challenger on validation seed {val_s[0]}; beats the class-exposure baseline "
                    f"on held-out seed {te_seeds[0]} (Brier {test[champion]['brier']} vs {test['class_exp']['brier']})"
                    if promoted else f"the {challenger} challenger did not beat the class-exposure baseline on held-out "
                    f"seed {te_seeds[0]}; the baseline stays champion"),
            "held_out": test[champion],
        },
        "candidates": [
            {"name": kind, "label": hz.KINDS[kind], "brier": s["brier"], "auc": s["auc"], "c_index": s["c_index"],
             "promoted": kind == champion,
             "role": "baseline" if kind == "class_exp" else ("challenger" if kind == challenger else "not selected")}
            for kind, s in test.items()
        ],
        "promoted": promoted,
        "calibration_champion_quintiles": calibration(preds[champion], te_fit),
        "landmark_covariate_effects_log_scale": effects,
        "landmark_covariate_note": "AFT coefficients on log residual-life scale: negative = shorter residual life = "
                                   "higher risk",
        "c_index_note": "Harrell's C over landmark rows (residual life vs predicted risk); rows of one spell are "
                        "correlated. The class-exposure baseline gives one value per class, so its C-index within "
                        "a class is 0.5.",
        "final_model": {"path": str(train / "hazard_model.json"), "kind": champion, "seeds": seeds,
                        "events_by_class": final.events, "fit_classes": [k for k in final.classes if final.sufficient(k)],
                        "champion_note": final.champion_note},
    }
    (HERE / "hazard_backtest.json").write_text(json.dumps(doc, indent=1) + "\n")
    lines = [
        "# Removal-risk model: backtest and champion",
        "",
        f"Source: **{doc['source_label']}** (synthetic training worlds; not validated). Model `{hz.MODEL_ID}` "
        f"{hz.MODEL_VERSION}. Landmarks every {hz.LANDMARK_STEP:.0f} FH, horizon {H_FH:.0f} FH; ridge {hz.PENALIZER} "
        f"partial pooling across classes.",
        f"Fitted classes (≥ {hz.MIN_EVENTS} events): {', '.join(fit_classes)}. INSUFFICIENT_EVIDENCE: "
        f"{', '.join(doc['insufficient_evidence_classes'])}.",
        "",
        f"Challenger chosen on validation seed {val_s} (fit on {fit_s}): "
        + ", ".join(f"{k} Brier {v['brier']}" for k, v in selection.items()) + f" → **{challenger}**.",
        "",
        f"Held-out test seed {te_seeds} (fit on {tr_seeds}), fitted classes:",
        "",
        "| Model | Landmarks | Events in window | Brier | AUC | C-index |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for kind, s in test.items():
        tag = " (champion)" if kind == champion else (" (challenger)" if kind == challenger else "")
        lines.append(f"| {hz.KINDS[kind]}{tag} | {s['landmarks']} | {s['events_in_window']} | {s['brier']} | "
                     f"{s['auc']} | {s['c_index']} |")
    lines += ["", f"**Champion: {hz.KINDS[champion]}** — "
              + (f"the {challenger} challenger beats the class-exposure baseline on the held-out seed."
                 if promoted else f"the {challenger} challenger did not beat the class-exposure baseline; the "
                 "baseline stays champion."),
              "", f"Landmark-model covariate effects (log residual-life scale; negative = higher risk): {effects}.",
              "", "Calibration of the champion (quintiles of predicted risk):", "",
              "| Bin | n | Mean predicted | Observed |", "|---:|---:|---:|---:|"]
    lines += [f"| {c['bin']} | {c['n']} | {c['mean_predicted']} | {c['observed']} |"
              for c in doc["calibration_champion_quintiles"]]
    lines += ["", doc["c_index_note"], "", f"Final model ({champion}) on all seeds {seeds}: `{train / 'hazard_model.json'}`."]
    (HERE / "hazard_backtest.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "runs" / "train"))
