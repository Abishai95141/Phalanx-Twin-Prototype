"""I2/I3 end to end: the full toy system under validation mode (``validate=True, purity_check=True``) is
bit-identical to production mode, in step and block mode, and the guards were actually exercised.

Sample: N = 2,400 steps of every toy feature at once (fused loop or loop fallback, drifting-clock sensor
buffer, 10 Hz step_block sampler, event-emitting monitor, event-only counter), plus the usage-mode system
over 10 simulated minutes.
"""

from __future__ import annotations

import pytest

import phalanx.core.scheduler as sched
from phalanx.core.snapshot import snapshot
from phalanx.core.toy import build_toy_system, build_usage_system, start_usage

N = 2400
FULL = {
    "fused": {"controlled": True, "monitored": True, "sampled": True, "fused": True},
    "fallback": {"controlled": True, "monitored": True, "sampled": True},
}


def _run(cfg, mode, validate):
    s = build_toy_system(**cfg, validate=validate, purity_check=validate)
    w, tr = s.run(s.start(), N, mode=mode, record=s.output_ports())
    return s, w, tr


@pytest.mark.integration
@pytest.mark.determinism
@pytest.mark.parametrize("name", sorted(FULL))
def test_full_toy_validation_mode_is_bit_identical_to_production(name, monkeypatch):
    calls = {"units": 0, "finite": 0}
    real_strip, real_finite = sched.strip_quantity, sched._check_finite

    def strip_spy(*a):
        calls["units"] += 1
        return real_strip(*a)

    def finite_spy(*a):
        calls["finite"] += 1
        return real_finite(*a)

    monkeypatch.setattr(sched, "strip_quantity", strip_spy)
    monkeypatch.setattr(sched, "_check_finite", finite_spy)
    cfg = FULL[name]
    s_prod, w_prod, t_prod = _run(cfg, "step", validate=False)
    assert calls == {"units": 0, "finite": 0}  # production mode pays nothing
    ref_snap, ref_digest = snapshot(s_prod, w_prod), t_prod.digest()
    for mode in ("step", "block"):
        s_val, w_val, t_val = _run(cfg, mode, validate=True)
        ex = s_val.execution()
        assert ex["validate"] and ex["purity_check"]
        assert snapshot(s_val, w_val) == ref_snap
        assert t_val.digest() == ref_digest
    assert calls["units"] > 1000 and calls["finite"] > 1000  # the guards really ran
    _, _w_blk, t_blk = _run(cfg, "block", validate=False)
    assert t_blk.digest() == ref_digest


@pytest.mark.integration
def test_usage_system_validation_mode_is_bit_identical():
    def go(validate):
        s = build_usage_system(mean_interval_s=2.0, validate=validate, purity_check=validate)
        w, tr = s.run(start_usage(s), 240 * 600, record=["counter.count", "renewal.last_interval"])
        return snapshot(s, w), tr.digest()

    assert go(True) == go(False)
