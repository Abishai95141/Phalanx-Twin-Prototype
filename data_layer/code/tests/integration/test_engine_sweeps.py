"""M07 ASSUMPTION sweeps (RULES.md rule 3: "sweep it inside a plausible range"; brief: ASSUMPTION values need
sweeps).

For every scalar ASSUMPTION/PROXY parameter of ``configs/tejas/params/M07.yaml`` with a ``sweep: [lo, hi]``,
the model is rebuilt at each end (design closure included) and must: close the design point (84 kN max AB,
70 kg/s, OPR 28 are DIRECT and held by construction), reach an equilibrium at the design inputs, and run a
2 s fuel chop (to 60 % for 0.9 s at the design nozzle; fan surge pops on the recovery) without non-finite
outputs and without an N1 overspeed run-away (the numerical-instability signature). The end state is
recorded, not asserted: at fan_ncmap_design = 1.05 the engine settles at a second, stall-hang-like
equilibrium on the fan speed-line peak (N1 about 93 %, numerically converged; a finding). The sensitivity
of four observables (dry SLS thrust, SLS MIL T5, N1 dip and N1 at the end of the chop) is printed and
recorded per end so the report can say how much each assumption matters. Sample: 2 ends per parameter
(the sweep definition); one 2 s transient per end.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.dictionary.params import _to_si, params_dir
from phalanx.dictionary.yamlio import load_yaml
from phalanx.engine.design import build_engine_model, load_engine_params
from phalanx.engine.layout import U_WF, Y_NAMES, A
from phalanx.engine.sim import input_block, simulate, state_from_x
from phalanx.engine.steady import design_inputs, steady_state


def _sweeps() -> list[tuple[str, str, float, float, str]]:
    doc = load_yaml(params_dir("tejas") / "M07.yaml")
    out = []
    for _sname, entries in doc["sets"].items():
        for name, e in entries.items():
            tag = str(e["evidence"]["tag"])
            if "sweep" not in e or "value" not in e or not np.isscalar(e["value"]):
                continue
            if not (tag.startswith("ASSUMPTION") or e.get("proxy")):
                continue
            lo, hi = e["sweep"]
            out.append((name, e["units"], float(lo), float(hi), e.get("assumption_id", "")))
    return out


SWEEPS = _sweeps()


def _observables(m) -> dict[str, float]:
    st = m.design.stations
    ss = steady_state(m, design_inputs(m))
    assert ss.converged
    n = 480
    wf = np.full(n, ss.u[U_WF])
    wf[24:240] *= 0.6
    r = simulate(m, state_from_x(m, ss.x), *input_block(n, 1, ss.u, wf_cmd=wf))
    assert np.all(np.isfinite(r.y)), "non-finite outputs in the chop transient"
    n1 = r.y[:, 0, Y_NAMES.index("n1")]
    assert n1.max() / n1[0] < 1.03, "N1 overspeed run-away (numerical instability) in the chop transient"
    return {
        "fn_dry_kN": st["fn_dry"] / 1e3,
        "t5_mil_K": float(ss.aux[A["t5"]]),
        "n1_dip_pct": float((n1.min() / n1[0] - 1.0) * 100.0),
        "n1_end_pct": float((n1[-1] / n1[0] - 1.0) * 100.0),
    }


@pytest.fixture(scope="module")
def nominal():
    return _observables(build_engine_model())


@pytest.mark.unit
def test_every_assumption_parameter_has_a_sweep():
    """Registry rule (loader-enforced) restated for M07: the closure and dynamics assumptions are swept."""
    names = {s[0] for s in SWEEPS}
    for must in ("fpr_design", "bpr_design", "t4_design", "i_lp", "i_hp", "v3", "tau_comb", "p_acc_design"):
        assert must in names, must


@pytest.mark.integration
@pytest.mark.parametrize("name,units,lo,hi,aid", SWEEPS, ids=[s[0] for s in SWEEPS])
def test_sweep_ends_build_close_and_run(name, units, lo, hi, aid, nominal, record_property):
    ps = load_engine_params()
    for end, v in (("lo", lo), ("hi", hi)):
        si, _ = _to_si(v, units)
        m = build_engine_model(ps.replace(**{name: si}))
        assert abs(m.design.max_ab["fn"] - 84_000.0) < 1.0 and m.design.stations["w2"] == 70.0
        obs = _observables(m)
        for k, val in obs.items():
            record_property(f"{end}_{k}", round(val, 3))
            record_property(f"{end}_{k}_delta", round(val - nominal[k], 3))
        print(
            f"\nSWEEP {aid} {name} {end}={v} {units}: "
            + ", ".join(f"{k} {obs[k] - nominal[k]:+.3f}" for k in obs)
        )
