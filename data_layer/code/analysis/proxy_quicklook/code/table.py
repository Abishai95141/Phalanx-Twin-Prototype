"""Print aggregated MF1 statistics: real (paired, same flights) vs configurations, at the recorded level and,
for one configuration, truth/sensor/recorded (texture attribution). Development viewer.

Usage: python -I table.py <agg_json> [config ...] [--levels]
"""

from __future__ import annotations

import json
import sys

STATS = (
    ("B1.N1-N2", "B1 N1-N2"),
    ("B1.N1-FF", "B1 N1-FF"),
    ("B1.N2-FF", "B1 N2-FF"),
    ("B1.N1-EGT", "B1 N1-EGT"),
    ("B1.N2-EGT", "B1 N2-EGT"),
    ("B1.N1x_mean", "B1 N1 cross-eng"),
    ("B1.N2x_mean", "B1 N2 cross-eng"),
    ("B1.EGTx_mean", "B1 EGT cross-eng"),
    ("FLT.N1-N2", "FLT N1-N2"),
    ("FLT.N1-FF", "FLT N1-FF"),
    ("FLT.N2-FF", "FLT N2-FF"),
    ("FLT.N1-EGT", "FLT N1-EGT"),
    ("CLB.N1-N2", "CLB N1-N2"),
    ("CRZ.N1-N2", "CRZ N1-N2"),
    ("DES.N1-N2", "DES N1-N2"),
    ("DES.N1-FF", "DES N1-FF"),
    ("TAXI.N1-N2", "TAXI N1-N2"),
    ("B2.FF>N2", "B2 FF>N2 s"),
    ("B2.FF>N1", "B2 FF>N1 s"),
    ("B2.N2>N1", "B2 N2>N1 s"),
    ("B2.FF>EGT", "B2 FF>EGT s"),
    ("SALL.N2>N1.phase_bands_deg[0]", "N2>N1 phase .19-.5"),
    ("SALL.N2>N1.phase_bands_deg[1]", "N2>N1 phase .5-1"),
    ("SALL.N2>N1.gain_bands[0]", "N2>N1 gain .19-.5"),
    ("SALL.N2>N1.gain_bands[1]", "N2>N1 gain .5-1"),
    ("SALL.N2>N1.coh_bands[0]", "N2>N1 coh .19-.5"),
    ("SALL.N2>N1.coh_bands[1]", "N2>N1 coh .5-1"),
    ("SALL.N2>N1.tau_eq", "N2>N1 tau_eq s"),
    ("SALL.N2>N1.r_lag", "N2>N1 r_lag"),
    ("SALL.N1>EGT.phase_bands_deg[0]", "N1>EGT phase .19-.5"),
    ("SALL.N1>EGT.tau_eq", "N1>EGT tau_eq s"),
    ("SALL.N2>EGT.tau_eq", "N2>EGT tau_eq s"),
    ("SALL.N2>FF.tau_eq", "N2>FF tau_eq s"),
    ("SALL.FF>N1.tau_eq", "FF>N1 tau_eq s"),
    ("SALL.FF>EGT.tau_eq", "FF>EGT tau_eq s"),
    ("SALL.N2>N1.CF_effect", "CF N1 (vs N2)"),
    ("taxi_share_of_air", "taxi share of air"),
    ("level.N2", "median N2 %"),
    ("level.EGT", "median EGT C"),
    ("level.FF", "median FF lb/h"),
)


def f(v):
    return "   nan" if v is None or v != v else f"{v:7.2f}"


def main(path: str, *args: str) -> None:
    levels = "--levels" in args
    configs = [a for a in args if a != "--levels"]
    agg = json.load(open(path))
    cf = agg["configs"]
    configs = configs or sorted(cf)
    real = agg["real"]
    print(f"real n = {real['n']}")
    if levels:
        c = configs[0]
        print(
            f"{'statistic':22s} {'real':>7s} {'CI':>15s} {'rec':>7s} {'sen':>7s} {'tru':>7s}"
            f"   ({c}, n={cf[c]['n']})"
        )
        for k, lab in STATS:
            lo, hi = real["ci"].get(k, (None, None))
            ci = f"[{lo:5.2f},{hi:5.2f}]" if lo is not None and lo == lo else ""
            print(
                f"{lab:22s} {f(real['median'].get(k))} {ci:>15s} "
                + " ".join(f(cf[c][lv].get(k)) for lv in ("rec", "sen", "tru"))
            )
        return
    head = f"{'statistic':22s} {'real':>7s}" + "".join(f" {c[:12]:>12s}" for c in configs)
    print(head)
    for k, lab in STATS:
        print(
            f"{lab:22s} {f(real['median'].get(k))}"
            + "".join(f" {f(cf[c]['rec'].get(k)):>12s}" for c in configs)
        )


if __name__ == "__main__":
    main(*sys.argv[1:])
