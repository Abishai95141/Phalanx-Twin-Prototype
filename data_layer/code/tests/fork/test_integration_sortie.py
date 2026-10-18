"""A1 on the integrated telemetry System (invariants I1, I2, I8; AD-36): determinism, snapshot/restore, CRN.

Sample: the first gate sortie from post-start idle (n = 1 plan), short windows (stated per test):

- I1 in process: two independently built Systems give identical traces, CIR and states (12 s).
- I1 in a fresh process: a subprocess (``python -I``) reproduces the trace digest of the unfused System (2 s).
- Mid-sortie snapshot -> restore -> continue equals the uninterrupted run (composite sortie snapshot, recorder
  placement PD-W2.1a-2), bitwise: chunk traces, CIR, world states, recorder state, realised usage (snapshot at
  6 s, continue 6 s). Negative control: restoring the world alone with a fresh recorder state changes the CIR,
  so the recorder state is needed in a mid-sortie snapshot.
- I8 fork CRN: two branches from one snapshot, one with a scripted sensor fault injected; the exogenous M03
  outputs (process disturbances, turbulence, wind) stay bitwise identical while the faulted reading differs;
  another root changes them (negative control).
- I2/I3: validation mode (read-only state, purity check, unit/shape checks, no NaN or inf at any port
boundary,
  including the fused group's outputs) runs 1 s.
- No global RNG: the session fixture of ``tests/conftest.py`` fails any test that touches it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.state import trees_equal
from phalanx.integration.plans import gate_sorties
from phalanx.integration.sortie import SortieRunner, sortie_digest
from phalanx.integration.system import SortieSpec, build_sortie_system

pytestmark = pytest.mark.fork
ROOT = Path(__file__).resolve().parents[2]


def _spec(**kw):
    base = dict(plan=gate_sorties()[0], scenario="gate", root=0xA5, fused=True)
    base.update(kw)
    return SortieSpec(**base)


def _runner(**kw):
    return SortieRunner(build_sortie_system(_spec(**kw)), keep_cir=True)


@pytest.fixture(scope="module")
def reference():
    r = _runner()
    st = r.begin()
    st, a = r.run(st, 6 * 240)
    snap = r.snapshot(st)
    st, b = r.run(st, 6 * 240)
    return r, snap, st, a, b


def test_in_process_determinism(reference):
    _r0, _snap, st0, a0, b0 = reference
    r = _runner()
    st = r.begin()
    st, a = r.run(st, 12 * 240)
    assert sortie_digest(a) == sortie_digest(a0 + b0)
    assert all(trees_equal(st.world.states[m], st0.world.states[m]) for m in st0.world.states)
    assert trees_equal(st.rec, st0.rec) and trees_equal(st.usage, st0.usage)


def test_snapshot_mid_sortie_restore_continue_is_bitwise(reference):
    _r0, snap, st0, _a0, b0 = reference
    r = _runner()
    st = r.restore(snap)
    st, b = r.run(st, 6 * 240)
    assert sortie_digest(b) == sortie_digest(b0)
    assert all(trees_equal(st.world.states[m], st0.world.states[m]) for m in st0.world.states)
    assert trees_equal(st.rec, st0.rec) and trees_equal(st.usage, st0.usage)
    # negative control: the world alone with a fresh recorder state (M14 feed off: M14 itself rejects the
    # re-acquired past samples as out-of-order CIR) records different CIR -> the recorder state is needed
    r2 = SortieRunner(
        build_sortie_system(_spec()), keep_cir=True, feed_monitor=False, cir_channels=r.m14_channels
    )
    st2 = r2.restore(_with_feed_off(snap, r2))
    st2.rec = r2.recorder.init_state()
    st2, b2 = r2.run(st2, 6 * 240)
    assert _cir_digest(b2) != _cir_digest(b0)


def _cir_digest(chunks) -> str:
    from phalanx.core.canonical import PERSON_SNAPSHOT, digest

    parts = []
    for c in chunks:
        tab = c.cir.table
        for name in ("param_id", "lane", "sample_index", "t_sample", "value"):
            parts.append(repr(tab.column(name).to_pylist()).encode())
    return digest(b"".join(parts), PERSON_SNAPSHOT)


def _with_feed_off(snap: bytes, runner: SortieRunner) -> bytes:
    """The composite snapshot re-headed for a runner without the M14 feed (same world and usage parts)."""
    from phalanx.core.canonical import canonical_json, length_prefixed

    parts, pos = [], 8
    while pos < len(snap):
        m = int.from_bytes(snap[pos : pos + 8], "little")
        parts.append(snap[pos + 8 : pos + 8 + m])
        pos += 8 + m
    head = json.loads(parts[0].decode("ascii"))
    head["m14_feed"] = runner.feed_monitor
    head["cir_channels"] = list(runner.cir_channels)
    return snap[:8] + length_prefixed([canonical_json(head), *parts[1:]])


def test_fork_crn_exogenous_streams_identical_across_branches(reference):
    """I8: after the fork, every keyed stream both branches use gives identical draws at identical indices
    (``crn_audit`` on the draw ledgers), the purely exogenous process-disturbance outputs are bitwise equal,
    and the faulted reading differs. Turbulence and wind are not compared as outputs: their forming filters
    and shear depend on the (branch-dependent) airspeed and height; their draws are in the audit."""
    from phalanx.core.rng import crn_audit

    _r0, snap, _st0, _a0, _b0 = reference
    exo = ["env.w_engine", "env.w_bleed_pto", "env.w_hyd"]
    probe = ["sens.s_pa"]
    ra, rb = (
        SortieRunner(build_sortie_system(_spec(rng_ledger=True)), keep_cir=False, record=exo + probe)
        for _ in range(2)
    )
    sa, sb = ra.restore(snap), rb.restore(snap)
    t = sb.world.t_ns + 1_000_000_000
    # a static-pressure fault (M12 only): the PS3-vented fault used before the W2.1c merge makes M08 declare
    # ENG-015, which M14 now rejects (test_integration_validate::test_m08_fault_codes_are_m14_bit_codes)
    fault = Event(t, "faults.inject", "faults", {"mode": "FM.SNS.INLET_STATIC_TRAPPED", "severity": 1.0})
    sb.world = rb.ss.system.inject(sb.world, [fault])
    sa, oa = ra.run(sa, 4 * 240)
    sb, ob = rb.run(sb, 4 * 240)
    for port in exo:
        xa = np.concatenate([c.trace.ports[port] for c in oa])
        xb = np.concatenate([c.trace.ports[port] for c in ob])
        assert xa.tobytes() == xb.tobytes(), port
    pa = np.concatenate([c.trace.ports["sens.s_pa"] for c in oa])
    pb = np.concatenate([c.trace.ports["sens.s_pa"] for c in ob])
    assert not np.array_equal(pa, pb)  # the injected fault did change the branch
    rep = crn_audit(ra.ss.system.rng.ledger, rb.ss.system.rng.ledger)
    assert rep.identical, "no shared stream audited"
    assert not rep.values_differ, rep.values_differ
    assert not rep.consumption_differs, rep.consumption_differs
    assert not rep.only_in_a  # the fault branch only adds its own instance draws
    assert any("faults" in p for p in rep.only_in_b), rep.only_in_b
    other = SortieRunner(build_sortie_system(_spec(root=0xA6)), keep_cir=False, record=exo)
    so = other.begin()
    so, oo = other.run(so, 240)
    sa2 = SortieRunner(build_sortie_system(_spec()), keep_cir=False, record=exo)
    s2 = sa2.begin()
    s2, o2 = sa2.run(s2, 240)
    assert not np.array_equal(oo[0].trace.ports["env.w_engine"], o2[0].trace.ports["env.w_engine"])


def test_validation_mode_no_nan_and_purity():
    ss = build_sortie_system(_spec(validate=True, purity_check=True, block_len=64))
    w = ss.system.inject(ss.start(), ss.bootstrap_events())
    w, tr = ss.system.run(w, 240, record=ss.system.output_ports())
    for name, arr in tr.ports.items():
        if np.asarray(arr).dtype.kind == "f":
            assert np.all(np.isfinite(arr)), name


#: the child inherits the test session's NUMBA_CACHE_DIR (tests/conftest.py), so it loads the kernels the
#: parent compiled from the same sources instead of recompiling them
_CHILD = r"""
import sys
sys.path.insert(0, sys.argv[1])
from phalanx.integration.plans import gate_sorties
from phalanx.integration.system import SortieSpec, build_sortie_system
ss = build_sortie_system(SortieSpec(plan=gate_sorties()[0], scenario="gate", root=0xA5, fused=False))
w = ss.system.inject(ss.start(), ss.bootstrap_events())
w, tr = ss.system.run(w, int(sys.argv[2]), mode="step", record=ss.system.output_ports())
print("DIGEST", tr.digest(), ss.system.config_hash)
"""


def test_fresh_process_determinism():
    n = 480
    ss = build_sortie_system(_spec(fused=False))
    w = ss.system.inject(ss.start(), ss.bootstrap_events())
    w, tr = ss.system.run(w, n, mode="step", record=ss.system.output_ports())
    out = subprocess.run(
        [sys.executable, "-I", "-c", _CHILD, str(ROOT / "src"), str(n)],
        capture_output=True,
        text=True,
        check=True,
        timeout=1800,
    ).stdout
    line = next(x for x in out.splitlines() if x.startswith("DIGEST"))
    _, digest, cfg = line.split()
    assert cfg == ss.system.config_hash
    assert digest == tr.digest(), json.dumps({"child": digest, "parent": tr.digest()})
