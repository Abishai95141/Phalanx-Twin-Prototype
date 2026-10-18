"""Generators run on a compiled dictionary, and the hook for extra generators (brief W0.3 §4).

A generator is ``fn(dictionary: Dictionary, out_dir: Path) -> list[Path]``: it reads only the compiled
dictionary and writes deterministic files into ``out_dir``. Built-ins: ``tmats``, ``icd``, ``param_table``,
``assumptions``.

**Hook for the coordinator (W0.X):** the W0.4 contract generator plugs in without editing this module, either

1. by listing it in the platform manifest ``configs/<platform>/dictionary/dictionary.yaml``::

       generators: [tmats, icd, param_table, assumptions,
                    "phalanx.dictionary.generators:contract_v0_generator"]

   (``module:function`` import strings are resolved with importlib; the module must be inside ``phalanx``;
   :func:`contract_v0_generator` adapts W0.4's ``phalanx.dictionary.contract.generate.artefacts``), or
2. programmatically: ``register_generator("contract", fn)`` before calling :func:`build`, or ``build(...,
   extra_generators={"contract": fn})``.

The dictionary hash never depends on generators; generators consume the dictionary.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from . import icd, tmats
from .compiler import write_compiled
from .model import Dictionary
from .schema import rule_is_proxy, rule_needs_register

__all__ = [
    "BUILTIN_GENERATORS",
    "Generator",
    "assumptions_markdown",
    "build",
    "contract_v0_generator",
    "param_table_markdown",
    "register_generator",
    "resolve_generator",
    "run_generators",
]

Generator = Callable[[Dictionary, Path], list[Path]]


def _gen_tmats(d: Dictionary, out: Path) -> list[Path]:
    text = tmats.generate_tmats(_plain(d), recording=True)  # with the recorder setup (R-1\EV, R-1\IDX)
    p_txt = out / "tmats.txt"
    p_txt.write_text(text, encoding="ascii")
    p_c10 = out / "tmats_setup_record.c10"
    p_c10.write_bytes(tmats.tmats_packet_bytes(text))
    return [p_txt, p_c10]


def _gen_icd(d: Dictionary, out: Path) -> list[Path]:
    content = _plain(d)
    p_csv = out / "icd.csv"
    p_csv.write_text(icd.icd_csv(content), encoding="utf-8")
    p_md = out / "icd.md"
    p_md.write_text(icd.icd_markdown(content), encoding="utf-8")
    return [p_csv, p_md]


def _gen_param_table(d: Dictionary, out: Path) -> list[Path]:
    p = out / "parameters.md"
    p.write_text(param_table_markdown(_plain(d)), encoding="utf-8")
    return [p]


def _gen_assumptions(d: Dictionary, out: Path) -> list[Path]:
    p = out / "assumptions_w0.3.md"
    p.write_text(assumptions_markdown(_plain(d)), encoding="utf-8")
    return [p]


def contract_v0_generator(d: Dictionary, out: Path) -> list[Path]:
    """Adapter for the W0.4 contract generator (not enabled by default; the coordinator wires it in W0.X).

    Writes the W0.4 contract v0 artefacts (``phalanx.dictionary.contract.generate.artefacts``) under
    ``out/contract/v0/`` plus ``dictionary_binding.json`` (dict_version, dict_hash and the measurand -> units
    map that the fast path's ``FastPathConfig`` takes). Enable it by adding
    ``"phalanx.dictionary.generators:contract_v0_generator"`` to the manifest's ``generators`` list.
    """
    import json

    from phalanx.dictionary.contract.generate import artefacts

    root = out / "contract" / "v0"
    written = []
    for rel, text in sorted(artefacts("v0").items()):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        written.append(p)
    binding = {"dict_version": d.dict_version, "dict_hash": d.dict_hash, "units": d.units_map()}
    p = root / "dictionary_binding.json"
    p.write_text(json.dumps(binding, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    # the contract's migration notes (every version step of the line), published beside the version folders
    note = Path(__file__).resolve().parent / "contract" / "MIGRATION.md"
    m = out / "contract" / "MIGRATION.md"
    m.write_text(note.read_text(encoding="utf-8"), encoding="utf-8")
    return [*written, p, m]


BUILTIN_GENERATORS: dict[str, Generator] = {
    "tmats": _gen_tmats,
    "icd": _gen_icd,
    "param_table": _gen_param_table,
    "assumptions": _gen_assumptions,
}
_REGISTERED: dict[str, Generator] = {}


def register_generator(name: str, fn: Generator) -> None:
    """Register an extra generator under ``name`` (process-local; generators never change the dictionary)."""
    if name in BUILTIN_GENERATORS:
        raise ValueError(f"{name!r} is a built-in generator")
    _REGISTERED[name] = fn


def resolve_generator(spec: str) -> Generator:
    """A generator from a built-in/registered name or a ``phalanx.<module>:<function>`` import string."""
    if spec in BUILTIN_GENERATORS:
        return BUILTIN_GENERATORS[spec]
    if spec in _REGISTERED:
        return _REGISTERED[spec]
    if ":" in spec:
        module, func = spec.split(":", 1)
        if not module.startswith("phalanx."):
            raise ValueError(f"generator {spec!r}: only modules inside the phalanx package may be imported")
        return getattr(importlib.import_module(module), func)
    raise KeyError(f"unknown generator {spec!r}")


def run_generators(
    d: Dictionary, out_dir: str | Path, names: list[str], extra: Mapping[str, Generator] | None = None
) -> dict[str, list[Path]]:
    """Run ``names`` (manifest order) then ``extra`` (sorted by name); returns {name: written paths}."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: dict[str, list[Path]] = {}
    for name in names:
        written[name] = list(resolve_generator(name)(d, out))
    for name in sorted(extra or {}):
        written[name] = list(extra[name](d, out))
    return written


def build(
    config_dir: str | Path, out_dir: str | Path, *, extra_generators: Mapping[str, Generator] | None = None
) -> tuple[Dictionary, dict[str, list[Path]]]:
    """Compile ``config_dir``, write ``dictionary.<ver>.json`` and run the manifest's generators into
    ``out_dir``."""
    from .model import load_dictionary

    d = load_dictionary(Path(config_dir))
    out = Path(out_dir)
    path = write_compiled(d.compiled, out)
    written = run_generators(d, out, list(d.content["generators"]), extra_generators)
    return d, {"dictionary": [path], **written}


def _plain(d: Dictionary) -> dict[str, Any]:
    """The compiled content as plain dicts/lists (generators were written against the JSON data model)."""
    return d.compiled.content


# ------------------------------------------------------------------------------------------------------------
# Markdown generators
# ------------------------------------------------------------------------------------------------------------
def _fmt_num(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def param_table_markdown(c: Mapping[str, Any]) -> str:
    """One row per channel: identity, units, range, quantisation, rate groups, sinks, evidence, assumption
    rules."""
    rules = c["rules"]
    lines = [
        f"# Phalanx parameter dictionary: {c['platform']} {c['dict_version']}",
        "",
        f"> Generated from the M01 dictionary; do not edit. {c['synthetic_label']}.",
        "",
        f"{c['stats']['parameters']} parameters (inventory rows), {c['stats']['channels']} channels "
        f"({', '.join(f'{k} {v}' for k, v in c['stats']['channels_by_role'].items())}). "
        f"Provenance coverage {c['stats']['provenance_coverage_pct']} % of valued fields.",
        "",
        "| Channel | Name | Units | Range | LSB / native | Acq → bus → record | Sinks | Evidence (core tag) "
        "| Assumption/PROXY rules |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for cid, ch in c["channels"].items():
        p = c["parameters"][ch["param_id"]]
        rng = ch["range"]
        rng_s = f"{_fmt_num(rng['min'])}..{_fmt_num(rng['max'])}" if rng else ""
        q = f"{_fmt_num(ch['recorder_lsb'])} / {_fmt_num(ch['native_step'])}" if ch["native_step"] else ""
        rec = ",".join(sorted({s["group"] for s in ch["sinks"] if s["group"]}))
        rates = f"{ch['rates']['acquisition']} → {ch['rates']['bus'] or '-'} → {rec or '-'}"
        sinks = ",".join(s["sink"] + ("?" if s["basis"] == "assumed" else "") for s in ch["sinks"])
        refs = sorted(
            {
                r
                for r in [*ch["prov"].values(), *(s["prov"] for s in ch["sinks"])]
                if r in rules and rule_needs_register(rules[r])
            }
        )
        lines.append(
            f"| `{cid}` | {ch['name'].replace('|', '/')} | {ch['units']} | {rng_s} | {q} | {rates} "
            f"| {sinks} | "
            f"{p['evidence'].get('core_tag', p['evidence']['primary'])} | {' '.join(refs)} |"
        )
    return "\n".join(lines) + "\n"


def _compact(pids: list[str]) -> str:
    """'ENG: PLA, N1; FCS: RSA.P' style list of parameter ids grouped by prefix."""
    groups: dict[str, list[str]] = {}
    for pid in pids:
        head, _, tail = pid.partition(".")
        groups.setdefault(head, []).append(tail or head)
    return "; ".join(f"{h}: {', '.join(v)}" for h, v in groups.items())


def assumptions_markdown(c: Mapping[str, Any]) -> str:
    """The W0.3 rows of docs/assumptions.md (one row per ASSUMPTION/PROXY rule, listing the affected
    parameters)."""
    lines = [
        "| ID | Statement | Tag | Source / evidence | Sweep range | Affects | Exposing test "
        "| Replacement route | Status |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for a in c["assumption_register"]:
        r = c["rules"][a["rule"]]
        statement = " ".join(f"**{a['rule']}** {r['title']}. {r['statement']}".split())
        affects = (
            f"{', '.join(r['affects'])}; {len(a['affects_params'])} params: {_compact(a['affects_params'])}"
        )
        if a.get("affects_constants"):
            affects += f"; constants: {', '.join(a['affects_constants'])}"
        tag = "PROXY" if rule_is_proxy(r) else "[ASSUMPTION]"
        source = r["source"] + (f" (basis: {r['basis']})" if r.get("basis") else "")
        cells = [
            a["assumption_id"],
            statement,
            tag,
            source,
            r["sweep"],
            affects,
            r.get("exposing_test", ""),
            r.get("replacement", ""),
            "open",
        ]
        lines.append("| " + " | ".join(str(x).replace("|", "/") for x in cells) + " |")
    return "\n".join(lines) + "\n"
