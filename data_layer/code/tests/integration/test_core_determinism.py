"""W0.2 A1 (I1): same (root, config) -> bitwise-identical outputs, in-process and in fresh subprocesses.

Sample: the full toy system (loop, sensor clock, monitor, events) for N = 2,400 steps. Two fresh
interpreters (``python -I``; each gets its own str-hash salt) must reproduce the in-process trace digest
and final snapshot id.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

from phalanx.core.snapshot import snapshot, snapshot_id
from phalanx.core.toy import build_toy_system

N = 2400
CFG = {"controlled": True, "monitored": True, "fused": True}

SCRIPT = textwrap.dedent(
    """
    import sys
    sys.path.insert(0, {src!r})
    from phalanx.core.snapshot import snapshot, snapshot_id
    from phalanx.core.toy import build_toy_system
    s = build_toy_system(controlled=True, monitored=True, fused=True)
    w, tr = s.run(s.start(), {n}, mode={mode!r}, record=s.output_ports())
    print(tr.digest(), snapshot_id(snapshot(s, w)), s.config_hash)
    """
)


def _in_process(mode="block"):
    s = build_toy_system(**CFG)
    w, tr = s.run(s.start(), N, mode=mode, record=s.output_ports())
    return tr.digest(), snapshot_id(snapshot(s, w)), s.config_hash


@pytest.mark.integration
@pytest.mark.determinism
def test_same_inputs_same_bits_in_process():
    a, b = _in_process(), _in_process()
    assert a == b
    other_root = build_toy_system(root=0xFEED, **CFG)
    _w, tr = other_root.run(other_root.start(), N, record=other_root.output_ports())
    assert tr.digest() != a[0]  # the digest is sensitive to the root (negative control)


@pytest.mark.integration
@pytest.mark.determinism
def test_same_bits_in_fresh_subprocesses(repo_root):
    ref = _in_process()
    src = str(repo_root / "src")
    outs = []
    for mode in ("block", "step"):
        r = subprocess.run(
            [sys.executable, "-I", "-c", SCRIPT.format(src=src, n=N, mode=mode)],
            capture_output=True,
            text=True,
            check=True,
        )
        outs.append(tuple(r.stdout.split()))
    assert outs[0] == outs[1] == ref
