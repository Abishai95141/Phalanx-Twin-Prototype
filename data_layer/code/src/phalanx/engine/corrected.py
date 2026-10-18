"""Corrected-parameter conventions for the M07 outputs (architecture §6 M07 "outputs in corrected
parameters").

theta = T2 / 288.15 K and delta = P2 / 101325 Pa at the engine face (TM-100159 convention, [TRANSFER:
F404-400]). A port's corrected value is ``value * theta**a * delta**b`` with the textbook exponents below.
The model itself is formulated on corrected map coordinates, so these relations hold by construction up to
the effects the physics adds (absolute accessory loads, heat soak, real-gas properties, humidity); test A2
(``tests/integration/test_engine_corrected.py``) checks the invariance under ISA offsets. Real recorder data
collapse imperfectly (report §3: fuel scatter 22 % -> 2 %; EGT exponent 0.5-0.73, behavioural target B5
0.73), so the EGT exponent is a configurable argument, not a constant of nature.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

T_REF = 288.15
P_REF = 101325.0
# port -> (theta exponent, delta exponent)
CORRECTIONS: dict[str, tuple[float, float]] = {
    "n1": (-0.5, 0.0),
    "n2": (-0.5, 0.0),
    "t2": (-1.0, 0.0),
    "t25": (-1.0, 0.0),
    "t3": (-1.0, 0.0),
    "t5": (-1.0, 0.0),
    "bleed_t3": (-1.0, 0.0),
    "p2": (0.0, -1.0),
    "ps3": (0.0, -1.0),
    "p5": (0.0, -1.0),
    "bleed_p3": (0.0, -1.0),
    "wf": (-0.5, -1.0),
    "wf_ab": (-0.5, -1.0),
    "w2": (0.5, -1.0),
    "thrust": (0.0, -1.0),
    "a8": (0.0, 0.0),
    "vg_igv": (0.0, 0.0),
    "vg_vsv": (0.0, 0.0),
}


def corrected(
    outputs: Mapping[str, np.ndarray], t2: np.ndarray, p2: np.ndarray, *, egt_theta_exponent: float = 1.0
) -> dict[str, np.ndarray]:
    """Corrected values of every port in ``CORRECTIONS`` present in ``outputs`` (same shapes)."""
    th = np.asarray(t2, float) / T_REF
    de = np.asarray(p2, float) / P_REF
    out = {}
    for k, (a, b) in CORRECTIONS.items():
        if k not in outputs:
            continue
        if k == "t5":
            a = -egt_theta_exponent
        out[k] = np.asarray(outputs[k], float) * th**a * de**b
    return out
