"""Print compact summaries of results/*.json (used while writing RESULTS.md).

Usage: python -I code/summarize.py m5 [30|240] | m1 | m2 | m3 | m4 | m8 | a1
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import RESULTS


def _load(name):
    with open(RESULTS / name) as fh:
        return json.load(fh)


def _t(s):
    return f"{s['median']:.4g} [{s['min']:.4g}-{s['max']:.4g}] sd {s['sd']:.2g} (n={s['n']})"


def m5(n="30"):
    d = _load(f"m5_gradients_n{n}.json")
    print("cs_ref", d["cs_ref"])
    nb = d["numba"]
    print(
        "numba r0 vs ref", nb["r0_vs_ref_maxabs"], "| fwd", _t(nb["forward_sim"]), "| rss", nb["peak_rss_mb"]
    )
    for k in ("fd_fwd_w1", "fd_fwd_w4", "fd_central_w1", "fd_central_w4", "cs_w1", "cs_w4"):
        v = nb[k]
        print(f"  {k:14s} t={_t(v['time'])} colerr med {v['col_rel_err_median']:.2e} p95 {v['col_rel_err_p95']:.2e}"
              f" max {v['col_rel_err_max']:.2e} frac<=1e-6 {v['frac_cols_le_1e-6']:.2f} grad_err {v['grad_rel_err']:.2e}"
              f" flips {v['sel_flips_vs_base']} worst {v['worst_cols']}")  # fmt: skip
    for k in ("forward_sim", "jacfwd", "grad"):
        j = d.get("jax_" + k) or d.get("jax", {})
        if k not in j:
            continue
        v = j[k]
        print("jax", k, "rss", j["peak_rss_mb"], "unroll", j.get("unroll"))
        extra = {kk: vv for kk, vv in v.items() if kk not in ("time", "cpu", "t_first_call_compile")}
        print(f"  {k:12s} compile {v['t_first_call_compile']:.2f}s t={_t(v['time'])} {extra}")


def generic(name):
    print(json.dumps(_load(name), indent=1)[:6000])


if __name__ == "__main__":
    what = sys.argv[1]
    if what == "m5":
        m5(sys.argv[2] if len(sys.argv) > 2 else "30")
    else:
        generic(what)
