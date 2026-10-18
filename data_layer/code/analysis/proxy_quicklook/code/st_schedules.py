"""W2.4a-2 stage 1: regenerate the plant-derived proxy settings after the steady identification.

1. The M08 proxy tables (``phalanx.proxy.schedules.derive_tables``: ratio-unit lines from the identified M07
   SLS operating line, the PLA demand at the ground reference condition) are written to
   ``configs/proxy_dashlink/params/M08``.
2. The thermocouple reference airflow of the proxy M12 (``tc_t5.w_ref``, ``egt_indication.w_ref``: the M07
   airflow at N1c 90 % SLS, the round-2 reference condition of the MEASURED law) is recomputed and printed for
   the M12 parameter file.

Usage::

    $PY -I analysis/proxy_quicklook/code/st_schedules.py <frozen ma_readable.json>
    <configs/proxy_dashlink/params/M08>
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script directory
import common  # noqa: F401  (src/ on the path)

from phalanx.engine.layout import X_N1
from phalanx.engine.steady import design_inputs, steady_state
from phalanx.proxy.config import load_proxy_config
from phalanx.proxy.schedules import derive_tables, operating_line, write_tables


def airflow_at_n1c(model, n1c_frac: float) -> float:
    """M07 inlet airflow [kg/s] at SLS ISA where N1 = ``n1c_frac`` of 100 % N1 (by N1 continuation)."""
    n1_100 = float(model.params.value("n1_100pct"))
    u = design_inputs(model)
    s = steady_state(model, u)
    f = s.x[X_N1] / n1_100
    while f > n1c_frac + 1e-9:
        f = max(n1c_frac, f - 0.01)
        s = steady_state(model, u, x0=s.x, target=("n1", f * n1_100))
        if not s.converged:
            raise RuntimeError(f"no steady state at N1 {f}")
    return float(s.aux_dict()["w2"])


def main(frozen: str, m08_dir: str) -> None:
    cfg = load_proxy_config()
    tabs = derive_tables(cfg.engine, frozen)
    write_tables(tabs, m08_dir)
    ol = operating_line(cfg.engine)
    print("operating line N2c1 range", float(ol.n2c1.min()), float(ol.n2c1.max()))
    print("demand n2c25 at PLA knots", np.round(tabs["n2c_pla_y"], 4).tolist())
    print("ru_ff monotone:", bool(np.all(np.diff(tabs["ru_ff_y"][np.argsort(tabs["ru_ff_x"])]) > 0)))
    print("thermocouple w_ref (airflow at N1c 90 % SLS) [kg/s]:", round(airflow_at_n1c(cfg.engine, 0.90), 2))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
