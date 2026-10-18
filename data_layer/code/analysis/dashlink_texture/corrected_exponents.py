"""Scan the theta exponent of the EGT and fuel-flow corrections (engines_corrected_blocks.csv).

EGTc(a) = (EGT+273.15)/theta^a ;  FFc(b) = FF/(delta*theta^b) ; x = N1/theta^0.5
For each exponent: quadratic fit vs x, residual SD and correlation of residual with altitude.
Usage: python -I corrected_exponents.py <results_dir>
"""
import os
import sys
import csv

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import read_csv  # noqa: E402


def main(res):
    B = read_csv(os.path.join(res, "engines_corrected_blocks.csv"))
    alt = np.array([float(b["ALT"]) for b in B])
    th = (np.array([float(b["TAT"]) for b in B]) + 273.15) / 288.15
    de = np.array([float(b["PT"]) for b in B]) / 1013.25
    rows = []
    for e in range(1, 5):
        n1 = np.array([float(b[f"N1_{e}"]) for b in B])
        ff = np.array([float(b[f"FF_{e}"]) for b in B])
        egt = np.array([float(b[f"EGT_{e}"]) for b in B]) + 273.15
        ok = (n1 > 20) & (ff > 0)
        x = (n1 / np.sqrt(th))[ok]
        for kind, base, scan in (("EGT", egt, np.arange(0, 1.21, 0.05)), ("FF", ff / de, np.arange(0, 1.51, 0.05))):
            for a in scan:
                y = (base / th ** a)[ok]
                r = y - np.polyval(np.polyfit(x, y, 2), x)
                rows.append({"engine": e, "param": kind, "theta_exponent": round(float(a), 3),
                             "resid_sd_pct_of_mean": float(100 * r.std() / y.mean()),
                             "resid_corr_alt": float(np.corrcoef(alt[ok], r)[0, 1])})
    with open(os.path.join(res, "corrected_exponent_scan.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    for kind in ("EGT", "FF"):
        for e in range(1, 5):
            rr = [r for r in rows if r["param"] == kind and r["engine"] == e]
            best_sd = min(rr, key=lambda r: r["resid_sd_pct_of_mean"])
            best_c = min(rr, key=lambda r: abs(r["resid_corr_alt"]))
            print(kind, e, "min-SD exponent", best_sd["theta_exponent"], round(best_sd["resid_sd_pct_of_mean"], 3),
                  "| zero-alt-corr exponent", best_c["theta_exponent"], round(best_c["resid_corr_alt"], 3))


if __name__ == "__main__":
    main(sys.argv[1])
