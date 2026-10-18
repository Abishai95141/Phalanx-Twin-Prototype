"""W2.4a-2 stage 1: write the identified steady plant parameters into the proxy configuration.

Reads an ``st_ident.py fit`` result and sets, in ``configs/proxy_dashlink/params/M07.yaml`` (set
``off_design``) and ``M09.yaml`` (set ``boundary``), the value and a [MEASURED] evidence line naming the
result file, the fit sample and the white-residual standard error. Parameters the fit held are left as they
are.

Usage::

    $PY -I analysis/proxy_quicklook/code/st_adopt.py <fit.json> <committed result path>
    <configs/proxy_dashlink/params>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

#: identification name -> (file, yaml name, scale to the yaml unit)
TARGETS = {
    "fan_wc_mod_a": ("M07.yaml", "fan_wc_mod_a", 1.0),
    "fan_wc_mod_k": ("M07.yaml", "fan_wc_mod_k", 1.0),
    "fan_eff_mod_a": ("M07.yaml", "fan_eff_mod_a", 1.0),
    "fan_eff_mod_k": ("M07.yaml", "fan_eff_mod_k", 1.0),
    "hpc_wc_mod_a": ("M07.yaml", "hpc_wc_mod_a", 1.0),
    "hpc_wc_mod_k": ("M07.yaml", "hpc_wc_mod_k", 1.0),
    "hpc_eff_mod_a": ("M07.yaml", "hpc_eff_mod_a", 1.0),
    "hpc_eff_mod_k": ("M07.yaml", "hpc_eff_mod_k", 1.0),
    "fan_nc_mod_a": ("M07.yaml", "fan_nc_mod_a", 1.0),
    "fan_nc_mod_k": ("M07.yaml", "fan_nc_mod_k", 1.0),
    "hpc_nc_mod_a": ("M07.yaml", "hpc_nc_mod_a", 1.0),
    "hpc_nc_mod_k": ("M07.yaml", "hpc_nc_mod_k", 1.0),
    "rni_exp": ("M07.yaml", "rni_exp", 1.0),
    "w_pack": ("M09.yaml", "w_pack", 1.0),
    "w_pack_gnd": ("M09.yaml", "w_pack_ground", 1.0),
    "w_eai": ("M09.yaml", "w_eai", 1.0),
    "w_wai": ("M09.yaml", "w_wai", 1.0),
    "pto_kw": ("M09.yaml", "pto_power", 1e3),
}


def set_param(text: str, name: str, value: float, evidence: str) -> str:
    """Replace the ``value:`` and ``evidence:`` lines of parameter ``name`` (4-space indented block)."""
    m = re.search(rf"^    {re.escape(name)}:\n((?:      .*\n)+)", text, flags=re.M)
    if m is None:
        raise KeyError(name)
    block = m.group(1)
    block = re.sub(r"^      value: .*$", f"      value: {value!r}", block, count=1, flags=re.M)
    block = re.sub(r"^      evidence: .*$", f"      evidence: {evidence}", block, count=1, flags=re.M)
    return text[: m.start(1)] + block + text[m.end(1) :]


def main(fit_json: str, result_path: str, params_dir: str) -> None:
    fit = json.load(open(fit_json))
    files: dict[str, str] = {}
    for name in fit["free"]:
        fname, yname, scale = TARGETS[name]
        p = Path(params_dir) / fname
        text = files.get(fname) or p.read_text()
        se = fit["se_white"].get(name)
        v = round(float(fit["theta"][name]) * scale, 6)
        ev = (
            '{tag: MEASURED, source: "W2.4a-2 stage-1 steady identification on 687-CAL '
            f"({fit['n_points']} quasi-steady points, {fit['n_bins']} bins, 12 flights; white-residual SE "
            f'{se * scale:.3g}); {result_path}"}}'
        )
        files[fname] = set_param(text, yname, v, ev)
    for fname, text in files.items():
        (Path(params_dir) / fname).write_text(text)
        print("updated", fname)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
