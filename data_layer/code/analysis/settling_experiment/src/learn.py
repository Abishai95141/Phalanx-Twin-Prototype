"""Grouped cross-validation, flight-level AUC, bootstrap and permutation machinery (pre-registration section 4).

* Folds: GroupKFold-style, k = 5, repeated 3x; groups = flight id, so the real and synthetic versions of a
  flight are always in the same fold. Group-to-fold assignment is a seeded random permutation per repeat.
* Window scores are averaged to a flight score in each repeat; the flight score used for the AUC is the mean
  over the 3 repeats (each flight is out-of-fold exactly once per repeat).
* D2: L2-regularised logistic regression (median imputation, standardisation, C = 0.1, lbfgs) and
  histogram gradient boosting (200 iterations, learning rate 0.05, 15 leaves, min 20 samples per leaf,
  l2 = 1, 30 % features per split). Hyper-parameters are fixed a priori (no tuning on any comparison).
* D3: MiniRocket (aeon 1.6.0, 10,000 kernels) fitted once per comparison on all windows (unsupervised; labels
  unused) followed by ridge regression on +-1 labels with alpha chosen by exact leave-one-out over
  logspace(-3, 3, 10) inside each training fold, computed via one SVD per fold; this makes 1,000 label
  permutations cheap (batched).
"""
import numpy as np
from joblib import Parallel, delayed
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

K, REPEATS = 5, 3
ALPHAS = np.logspace(-3, 3, 10)


def folds(groups, seed):
    """List over repeats of list over folds of (train_mask, test_mask) at row level."""
    ug = np.unique(groups)
    out = []
    for r in range(REPEATS):
        rng = np.random.default_rng([seed, r])
        perm = rng.permutation(ug)
        fold_of = {g: i % K for i, g in enumerate(perm)}
        fr = np.array([fold_of[g] for g in groups])
        out.append([(fr != k, fr == k) for k in range(K)])
    return out


def make_model(kind, seed=0):
    if kind == "lr":
        return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler(),
                             LogisticRegression(C=0.1, max_iter=2000))
    if kind == "gb":
        return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=20,
                                              l2_regularization=1.0, max_features=0.3, early_stopping=False,
                                              random_state=seed)
    raise ValueError(kind)


def _fit_predict(kind, X, y, tr, te, seed):
    Xtr = X[tr]
    keep = np.nanstd(Xtr, 0) > 0
    keep &= np.isfinite(np.nanstd(Xtr, 0))
    m = make_model(kind, seed)
    m.fit(Xtr[:, keep], y[tr])
    return m.predict_proba(X[te][:, keep])[:, 1]


def flight_scores(win_scores, row_flight, n_flights):
    s = np.bincount(row_flight, win_scores, minlength=n_flights)
    c = np.bincount(row_flight, minlength=n_flights)
    out = np.full(n_flights, np.nan)
    out[c > 0] = s[c > 0] / c[c > 0]
    return out


def cv_scores(kind, X, y_row, row_flight, n_flights, groups, seed, n_jobs=8):
    """OOF flight scores (mean over repeats) for a D2 model. Rows = windows (or flights for SEG)."""
    F = folds(groups, seed)
    tasks = [(r, k, tr, te) for r, fl in enumerate(F) for k, (tr, te) in enumerate(fl)]
    preds = Parallel(n_jobs=n_jobs)(delayed(_fit_predict)(kind, X, y_row, tr, te, seed + 31 * r + k)
                                    for r, k, tr, te in tasks)
    reps = np.zeros((REPEATS, n_flights))
    win = np.zeros(X.shape[0])
    for (r, k, tr, te), p in zip(tasks, preds):
        ws = np.zeros(X.shape[0])
        ws[te] = p
        win[te] += p / REPEATS
        fs = flight_scores(ws[te], row_flight[te], n_flights)
        m = np.isfinite(fs)
        reps[r, m] = fs[m]
    return reps.mean(0), reps, win


# ---------------------------------------------------------------- ridge (D3) with batched permutations
def _ridge_fold(Z, Ytr_cols, tr, te):
    """Kernel-form ridge. Z: standardised features. Ytr_cols: (n_rows, B) labels (+-1).
    Alpha per label column by exact leave-one-out over ALPHAS. Returns test predictions (n_te, B)."""
    Xtr = Z[tr]
    mu = Xtr.mean(0)
    Xc = Xtr - mu
    Y = Ytr_cols[tr]
    ym = Y.mean(0)
    Yc = Y - ym
    Kt = Xc @ Xc.T
    w, U = np.linalg.eigh(Kt)
    keep = w > 1e-9 * w.max()
    w, U = w[keep], U[:, keep]
    UtY = U.T @ Yc
    U2 = U * U
    best_e = best_a = None
    for a in ALPHAS:
        d = w / (w + a)
        H = U2 @ d
        loo = ((Yc - U @ (d[:, None] * UtY)) / (1 - H)[:, None]) ** 2
        e = loo.mean(0)
        if best_e is None:
            best_e, best_a = e, np.full(e.shape, a)
        else:
            b = e < best_e
            best_e, best_a = np.where(b, e, best_e), np.where(b, a, best_a)
    KteU = ((Z[te] - mu) @ Xc.T) @ U
    out = np.empty((int(te.sum()), Y.shape[1]))
    for a in np.unique(best_a):
        cols = best_a == a
        out[:, cols] = KteU @ ((1.0 / (w + a))[:, None] * UtY[:, cols]) + ym[cols]
    return out


def ridge_cv_scores(Z, y_row, row_flight, n_flights, groups, seed, perm_labels=None):
    """OOF flight scores for ridge on features Z. perm_labels: optional (n_rows, B) matrix of permuted +-1
    labels; returns (scores (n_flights,), perm_scores (B, n_flights) or None)."""
    Y = (2 * y_row - 1.0)[:, None]
    if perm_labels is not None:
        Y = np.hstack([Y, perm_labels])
    F = folds(groups, seed)
    acc = np.zeros((Y.shape[1], n_flights))
    win = np.zeros(Z.shape[0])
    for fl in F:
        for tr, te in fl:
            P = _ridge_fold(Z, Y, tr, te)                  # (n_te, B+1)
            win[te] += P[:, 0] / REPEATS
            rf = row_flight[te]
            c = np.bincount(rf, minlength=n_flights)
            for b in range(P.shape[1]):
                s = np.bincount(rf, P[:, b], minlength=n_flights)
                m = c > 0
                acc[b, m] += s[m] / c[m]
    acc /= REPEATS
    return acc[0], (acc[1:] if perm_labels is not None else None), win


def standardise(Z):
    mu = Z.mean(0)
    sd = Z.std(0)
    sd[sd == 0] = 1
    return (Z - mu) / sd


# ---------------------------------------------------------------- AUC, bootstrap, permutation
def auc(y, s):
    m = np.isfinite(s)
    if len(np.unique(y[m])) < 2:
        return np.nan
    return float(roc_auc_score(y[m], s[m]))


def fast_auc(y, s):
    """AUC via ranks (vectorised over rows of s if 2-D)."""
    from scipy.stats import rankdata
    s = np.atleast_2d(s)
    r = rankdata(s, axis=1)
    n1 = y.sum()
    n0 = y.size - n1
    return (r[:, y == 1].sum(1) - n1 * (n1 + 1) / 2) / (n1 * n0)


def boot_indices(y, pair_id, B=2000, seed=0):
    """Flight-level bootstrap index sets. Paired designs resample pairs; unpaired resample within class."""
    rng = np.random.default_rng(seed)
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


def boot_auc(y, s, idx_sets):
    v = []
    for ix in idx_sets:
        yy, ss = y[ix], s[ix]
        m = np.isfinite(ss)
        if len(np.unique(yy[m])) < 2:
            continue
        v.append(fast_auc(yy[m], ss[m])[0])
    return np.array(v)


def perm_labels_flight(y_flight, pair_id, B, seed):
    """(B, n_flights) permuted flight labels: paired -> random swap within each pair; else shuffle."""
    rng = np.random.default_rng(seed)
    out = np.empty((B, y_flight.size), int)
    if pair_id is not None:
        up = np.unique(pair_id)
        for b in range(B):
            yb = y_flight.copy()
            flip = rng.random(up.size) < 0.5
            for p, f in zip(up, flip):
                if f:
                    ix = np.flatnonzero(pair_id == p)
                    yb[ix] = 1 - yb[ix]
            out[b] = yb
    else:
        for b in range(B):
            out[b] = rng.permutation(y_flight)
    return out


def boot_auc_windows(y_row, s_row, row_flight, idx_sets):
    """Window-level AUC with flight-cluster bootstrap: each resample takes all rows of the drawn flights."""
    rows_of = {}
    for i, f in enumerate(row_flight):
        rows_of.setdefault(int(f), []).append(i)
    rows_of = {k: np.array(v) for k, v in rows_of.items()}
    out = []
    for ix in idx_sets:
        r = [rows_of[f] for f in ix if f in rows_of]
        if not r:
            continue
        r = np.concatenate(r)
        yy, ss = y_row[r], s_row[r]
        if len(np.unique(yy)) < 2:
            continue
        out.append(fast_auc(yy, ss)[0])
    return np.array(out)
