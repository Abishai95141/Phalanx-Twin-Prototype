"""M08 FADEC, closed-loop governing and engine signal validation (architecture §6 M08, AD-31). See README.md.

Public API: `Fadec` (module), `load_fadec_params`, `FadecConfig`, the `ports` submodule (W1 catalogue:
`phalanx.fadec.ports.ports(n_engines)` and `PREFIX`, re-exported here), `fadec_block` (compiled kernel for
W2.1 fused groups), `kernel_reference` (NumPy reference), the coupling helpers in `coupling` and the code
tables in `codes`.

`phalanx.fadec.ports` is the submodule, as for every other package (W2.1 F6): the package does not re-export
the `ports()` function under the submodule's name, which used to shadow it (`phalanx.fadec.ports` was a
function after `import phalanx.fadec`).
"""

from . import ports
from .codes import FAULT_CODES, SENSORS, active_codes, decode_active_limiter
from .kernel import fadec_block
from .module import Fadec
from .params import FadecConfig, load_fadec_params
from .ports import DEFAULT_CLOCK, PREFIX
from .reference import kernel_reference

__all__ = [
    "DEFAULT_CLOCK",
    "FAULT_CODES",
    "PREFIX",
    "SENSORS",
    "Fadec",
    "FadecConfig",
    "active_codes",
    "decode_active_limiter",
    "fadec_block",
    "kernel_reference",
    "load_fadec_params",
    "ports",
]
