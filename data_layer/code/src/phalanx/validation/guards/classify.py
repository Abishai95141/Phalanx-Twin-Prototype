"""Grouped cross-validated classifiers, flight-level AUC and bootstrap (port of round-1 `learn.py`, the parts
used by the G0 trivial-cue audit and the label-leak audit).

- Folds: GroupKFold-style, k = 5, repeated 3x; groups = flight id, so the real and synthetic versions of a
  flight always share a fold. Group-to-fold assignment is a seeded permutation per repeat
  (`SeedSequence([seed, repeat])`, identical to round 1's `default_rng([seed, r])`).
- Flight score = mean of the out-of-fold window scores; the AUC uses the mean over the 3 repeats.
- Models (hyper-parameters fixed a priori): L2 logistic regression (median imputation, standardisation,
  C = 0.1, lbfgs) and histogram gradient boosting (200 iterations, learning rate 0.05, 15 leaves, 20 samples
  per leaf, l2 = 1, 30 % features per split).
- **Deviation from round-1 code (RULES.md rule 5):** round 1 gave each boosting fit an integer random state
  computed by adding multiples of the repeat and fold indices to the base seed (seed arithmetic). The port
  derives that integer from `SeedSequence(seed, spawn_key=(repeat, fold))` (`model_seed`). Folds, bootstrap
  and the logistic model are unchanged, so results agree with round 1 whenever the outcome does not depend on
  the boosting feature-subsampling draw (identical or perfectly separable features); otherwise they differ at
  the level of that draw.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy.stats import rankdata
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from phalanx.validation.battery.config import N_BOOT

__all__ = [
    "REPEATS",
    "K",
    "auc",
    "boot_auc",
    "boot_indices",
    "cv_scores",
    "fast_auc",
    "folds",
    "make_model",
    "model_seed",
]

K, REPEATS = 5, 3


def _gen(entropy: int | Sequence[int], spawn_key: tuple[int, ...] = ()) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(entropy, spawn_key=spawn_key)))


def folds(groups: np.ndarray, seed: int) -> list[list[tuple[np.ndarray, np.ndarray]]]:
    """List over repeats of list over folds of (train_mask, test_mask) at row level."""
    ug = np.unique(groups)
    out = []
    for r in range(REPEATS):
        perm = _gen([seed, r]).permutation(ug)
        fold_of = {g: i % K for i, g in enumerate(perm)}
        fr = np.array([fold_of[g] for g in groups])
        out.append([(fr != k, fr == k) for k in range(K)])
    return out


def model_seed(seed: int, repeat: int, fold: int) -> int:
    """Integer random_state for one boosting fit, from an identity-keyed SeedSequence (no seed arithmetic)."""
    return int(np.random.SeedSequence(seed, spawn_key=(repeat, fold)).generate_state(1, np.uint32)[0])


def make_model(kind: str, seed: int = 0):
    if kind == "lr":
        return make_pipeline(
            SimpleImputer(strategy="median", keep_empty_features=True),
            StandardScaler(),
            LogisticRegression(C=0.1, max_iter=2000),
        )
    if kind == "gb":
        return HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.05,
            max_leaf_nodes=15,
            min_samples_leaf=20,
            l2_regularization=1.0,
            max_features=0.3,
            early_stopping=False,
            random_state=seed,
        )
    raise ValueError(kind)


def _fit_predict(
    kind: str, X: np.ndarray, y: np.ndarray, tr: np.ndarray, te: np.ndarray, seed: int
) -> np.ndarray:
    Xtr = X[tr]
    keep = np.nanstd(Xtr, 0) > 0
    keep &= np.isfinite(np.nanstd(Xtr, 0))
    m = make_model(kind, seed)
    m.fit(Xtr[:, keep], y[tr])
    return m.predict_proba(X[te][:, keep])[:, 1]


def _flight_scores(win_scores: np.ndarray, row_flight: np.ndarray, n_flights: int) -> np.ndarray:
    s = np.bincount(row_flight, win_scores, minlength=n_flights)
    c = np.bincount(row_flight, minlength=n_flights)
    out = np.full(n_flights, np.nan)
    out[c > 0] = s[c > 0] / c[c > 0]
    return out


def cv_scores(
    kind: str,
    X: np.ndarray,
    y_row: np.ndarray,
    row_flight: np.ndarray,
    n_flights: int,
    groups: np.ndarray,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Out-of-fold flight scores (mean over repeats), per-repeat scores and window scores (run
    sequentially)."""
    F = folds(groups, seed)
    reps = np.zeros((REPEATS, n_flights))
    win = np.zeros(X.shape[0])
    for r, fl in enumerate(F):
        for k, (tr, te) in enumerate(fl):
            p = _fit_predict(kind, X, y_row, tr, te, model_seed(seed, r, k))
            ws = np.zeros(X.shape[0])
            ws[te] = p
            win[te] += p / REPEATS
            fs = _flight_scores(ws[te], row_flight[te], n_flights)
            m = np.isfinite(fs)
            reps[r, m] = fs[m]
    return reps.mean(0), reps, win


def auc(y: np.ndarray, s: np.ndarray) -> float:
    m = np.isfinite(s)
    if len(np.unique(y[m])) < 2:
        return np.nan
    return float(roc_auc_score(y[m], s[m]))


def fast_auc(y: np.ndarray, s: np.ndarray) -> np.ndarray:
    """AUC via ranks (vectorised over rows of s if 2-D)."""
    s = np.atleast_2d(s)
    r = rankdata(s, axis=1)
    n1 = y.sum()
    n0 = y.size - n1
    return (r[:, y == 1].sum(1) - n1 * (n1 + 1) / 2) / (n1 * n0)


def boot_indices(
    y: np.ndarray, pair_id: np.ndarray | None, B: int = N_BOOT, seed: int = 0
) -> list[np.ndarray]:
    """Flight-level bootstrap index sets. Paired designs resample pairs; unpaired designs resample within
    each class."""
    rng = _gen(seed)
    out = []
    if pair_id is not None:
        up = np.unique(pair_id)
        members = {p: np.flatnonzero(pair_id == p) for p in up}
        for _ in range(B):
            pick = rng.choice(up, up.size, replace=True)
            out.append(np.concatenate([members[p] for p in pick]))
    else:
        i1, i0 = np.flatnonzero(y == 1), np.flatnonzero(y == 0)
        for _ in range(B):
            out.append(np.r_[rng.choice(i1, i1.size), rng.choice(i0, i0.size)])
    return out


def boot_auc(y: np.ndarray, s: np.ndarray, idx_sets: Sequence[np.ndarray]) -> np.ndarray:
    v = []
    for ix in idx_sets:
        yy, ss = y[ix], s[ix]
        m = np.isfinite(ss)
        if len(np.unique(yy[m])) < 2:
            continue
        v.append(fast_auc(yy[m], ss[m])[0])
    return np.array(v)
