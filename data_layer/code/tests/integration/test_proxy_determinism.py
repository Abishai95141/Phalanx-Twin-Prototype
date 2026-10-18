"""A6 (W2.4a): determinism of the whole proxy pipeline (fresh-process digest).

The proxy flight runner (replay drivers, M03 disturbances, M08 <-> M07 separate_fixed -> M12 -> M13 lanes in
the fused loop, M13 DASHlink recording) is a pure function of (root seed, configuration, identity, inputs):
a fresh interpreter (``python -I``) and the test process produce the same world digest and the same
recorded/sensor/truth arrays, bit for bit; a different identity gives a different realisation (negative
control: the digest is sensitive to the keyed randomness).

Sample: 12 s of synthetic recorded inputs (2,880 truth steps, 48 ACMS samples; two N1-command steps) in a
fresh process and the test process: the smallest run that exercises every module, the disturbance draws
and the texture noise.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.determinism]
SRC = Path(__file__).resolve().parents[2] / "src"

SCRIPT = r"""
import hashlib, json, sys
sys.path.insert(0, sys.argv[1])
import numpy as np
from phalanx.core.rng import KeyPath
from phalanx.proxy.config import load_proxy_config
from phalanx.proxy.inputs import synthetic_inputs
from phalanx.proxy.run import simulate_flight
sortie = int(sys.argv[2])
cfg = load_proxy_config()
fp = cfg.fadec_params.replace(at_kp=0.3, at_ki=0.2, at_rate=0.1)
inp = synthetic_inputs(12.0, steps=((3.0, 2.0), (8.0, -2.0)))
ident = KeyPath.of(scenario="a6", tail="T687", sortie=sortie)
sf = simulate_flight(cfg, inp, identity=ident, root=4242, fadec_params=fp)
h = hashlib.sha256()
for lvl in (sf.record, sf.sensor, sf.truth):
    for f in ("N1", "N2", "EGT", "FF"):
        h.update(np.ascontiguousarray(lvl.outputs[f], dtype=np.float64).tobytes())
print(json.dumps({"world": sf.world_digest, "arrays": h.hexdigest()}))
"""


def _fresh(sortie: int) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    out = subprocess.run(
        [sys.executable, "-I", "-c", SCRIPT, str(SRC), str(sortie)],
        capture_output=True, text=True, check=True, env=env, timeout=900,
    )  # fmt: skip
    return json.loads(out.stdout.strip().splitlines()[-1])


def _in_process(sortie: int) -> dict:
    from phalanx.core.rng import KeyPath
    from phalanx.proxy.config import load_proxy_config
    from phalanx.proxy.inputs import synthetic_inputs
    from phalanx.proxy.run import simulate_flight

    cfg = load_proxy_config()
    fp = cfg.fadec_params.replace(at_kp=0.3, at_ki=0.2, at_rate=0.1)
    sf = simulate_flight(
        cfg,
        synthetic_inputs(12.0, steps=((3.0, 2.0), (8.0, -2.0))),
        identity=KeyPath.of(scenario="a6", tail="T687", sortie=sortie),
        root=4242,
        fadec_params=fp,
    )
    h = hashlib.sha256()
    for lvl in (sf.record, sf.sensor, sf.truth):
        for f in ("N1", "N2", "EGT", "FF"):
            h.update(np.ascontiguousarray(lvl.outputs[f], dtype=np.float64).tobytes())
    return {"world": sf.world_digest, "arrays": h.hexdigest()}


def test_fresh_process_digests_are_identical():
    a = _fresh(1)
    c = _in_process(1)
    assert a == c
    assert _in_process(2) != c  # another identity, another keyed realisation
