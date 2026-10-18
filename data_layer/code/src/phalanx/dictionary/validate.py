"""Semantic validation of dictionary sources at compile time (M01; brief W0.3 §3).

Every check returns a list of human-readable error strings that name the offending channel/table entry. The
compiler collects all of them and raises one :class:`~phalanx.dictionary.compiler.CompileError`. Checks:

- provenance: every parameter has an evidence tag and a source; every valued channel field, sink and limit has
  a provenance ref; ``inv`` refs are verified against the embedded inventory text; rule refs exist; every
  ASSUMPTION/PROXY rule has an ``assumption_id``; PROXY refs and the channel ``proxy`` flag agree (A1, A7);
- units parse in pint and match the declared quantity; pressure channels state their reference (A4);
- ranges, LSBs, native steps and ADC bits are mutually consistent and the range fits the encoded word (A4);
- rate groups exist and serve the stage they are used for (A4);
- producer LRUs, consumers and terminals exist; every channel has at least one sink (no orphans) (A3);
- bus addresses are unique: 1553 (bus, RT, T/R, SA, word) ranges do not overlap, ARINC-429 (link, label, SDI)
  and FTI (stream, word) are unique, message lengths agree (A3);
- synthetic labelling is present on the manifest, the bus table and every synthetic code table (RULES.md rule
  6).
"""

from __future__ import annotations

import itertools
import math
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from . import icd
from .codes import bit_code_errors
from .schema import (
    PROV_FIELDS,
    QUANTITIES,
    core_tag_error,
    parse_tag_classes,
    rule_is_proxy,
    rule_needs_register,
)
from .textcheck import (
    acq_group_for,
    bus_group_for,
    contains_number,
    marked_assumption,
    unit_justified,
)
from .units import check_unit

__all__ = ["affected_params", "channel_rule_refs", "validate_all"]

_RECORDED = ("mil1553", "arinc429", "fti_pcm")
_SINK_COLUMNS = {
    "COCKPIT": "sink_cockpit",
    "CDR": "sink_crash_recorder",
    "ECMS_HUMS": "sink_ecms_hums",
    "MPDRU": "sink_mpdru_maint_download",
    "FTI": "sink_fti_only",
}


def _prov_targets(ch: Mapping[str, Any]) -> list[str]:
    """Valued fields of a channel that need a provenance entry."""
    out = []
    for f in PROV_FIELDS:
        if "." in f:
            top, sub = f.split(".", 1)
            if ch[top].get(sub) is not None:
                out.append(f)
        elif ch.get(f) is not None:
            out.append(f)
    return out


def validate_tables(tables: Mapping[str, Any], manifest: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    rules = tables["rules"]["rules"]
    for rid, r in rules.items():
        bad = core_tag_error(r["tag"])
        if bad:
            errs.append(f"rule {rid}: {bad}")
        needs_row = rule_needs_register(r)
        if needs_row and "assumption_id" not in r:
            errs.append(
                f"rule {rid}: ASSUMPTION/PROXY rule without an assumption_id (docs/assumptions.md row)"
            )
        if needs_row and not r.get("exposing_test"):
            errs.append(f"rule {rid}: ASSUMPTION/PROXY rule without an exposing test")
        if not needs_row and "assumption_id" in r:
            errs.append(f"rule {rid}: assumption_id on a rule that is neither ASSUMPTION nor PROXY")
        if rid.startswith("P-") != rule_is_proxy(r):
            errs.append(f"rule {rid}: P- rules and only P- rules carry proxy: true")
    ids = [r["assumption_id"] for r in rules.values() if "assumption_id" in r]
    for a in sorted({i for i in ids if ids.count(i) > 1}):
        errs.append(f"assumption_id {a} used by more than one rule")

    def ref_ok(ref: str, where: str) -> None:
        if ref != "inv" and ref not in rules:
            errs.append(f"{where}: unknown provenance ref {ref}")

    for lid, lru in tables["lrus"]["lrus"].items():
        if "frame_hz" in lru:
            if "frame_prov" not in lru:
                errs.append(f"lru {lid}: frame_hz without frame_prov")
            else:
                ref_ok(lru["frame_prov"], f"lru {lid}")
        bad = core_tag_error(lru["evidence"]["tag"])
        if bad:
            errs.append(f"lru {lid}: {bad}")
    for gid, g in tables["rate_groups"]["groups"].items():
        ref_ok(g["prov"], f"rate group {gid}")
        if g["kind"] == "periodic" and "rate_hz" not in g:
            errs.append(f"rate group {gid}: periodic group without rate_hz")
        if "band_hz" in g and "rate_hz" in g and not (g["band_hz"][0] <= g["rate_hz"] <= g["band_hz"][1]):
            errs.append(f"rate group {gid}: nominal rate {g['rate_hz']} outside its band {g['band_hz']}")
    for name, t in tables["code_tables"]["tables"].items():
        ref_ok(t["prov"], f"code table {name}")
        for extra in t.get("extra_prov", []):
            ref_ok(extra, f"code table {name}")
        if "synthetic_codes" in t and not set(t["synthetic_codes"]) <= set(t.get("codes", {})):
            errs.append(f"code table {name}: synthetic_codes lists codes the table does not have")
        if "word_layout" in t:
            ref_ok(t["word_layout"]["prov"], f"code table {name} word_layout")
    rec = tables["buses"].get("recorder")
    if rec is not None:
        ref_ok(rec["prov"], "recorder setup")
        ids = [e["id"] for e in rec["events"]]
        if len(set(ids)) != len(ids):
            errs.append("recorder setup: duplicate event ids")
    lrus = tables["lrus"]["lrus"]
    buses = tables["buses"]
    seen_rt: dict[tuple[str, int], str] = {}
    for bus, b in buses["mil1553"].items():
        ref_ok(b["prov"], f"bus {bus}")
        for who in [b["bc"], *b["monitors"], *b["rts"]]:
            if who not in lrus:
                errs.append(f"bus {bus}: unknown LRU {who}")
        for lru, rt in b["rts"].items():
            ref_ok(rt["prov"], f"bus {bus} RT {lru}")
            for addr in [rt["address"], *rt.get("mirrors", [])]:
                key = (bus, addr)
                if key in seen_rt:
                    errs.append(f"bus {bus}: RT address {addr} used by {seen_rt[key]} and {lru}")
                seen_rt[key] = lru
    for kind in ("arinc429", "rs422", "fti_pcm"):
        for link, b in buses[kind].items():
            ref_ok(b.get("prov", ""), f"{kind} {link}")
            for who in [b.get("transmitter"), *b.get("receivers", [])]:
                if who is not None and who not in lrus:
                    errs.append(f"{kind} {link}: unknown LRU {who}")
    if not manifest["synthetic_icd"] or "SYNTHETIC" not in manifest["synthetic_label"]:
        errs.append("manifest: the bus map must be labelled SYNTHETIC (RULES.md rule 6)")
    for sid, s in tables["sinks"]["sinks"].items():
        bad = core_tag_error(s["evidence"]["tag"])
        if bad:
            errs.append(f"sink {sid}: {bad}")
        for key in ("default_group", "default_group_engine"):
            if key in s and s[key] not in tables["rate_groups"]["groups"]:
                errs.append(f"sink {sid}: unknown {key} {s[key]}")
    for set_name, entries in tables["constants"]["sets"].items():
        for cname, c in entries.items():
            errs += _constant_errors(f"constant {set_name}.{cname}", c, rules)
            try:
                from phalanx.core.units import parse_unit, ureg

                parse_unit(str(ureg().Quantity(c["value"], c["units"]).to_base_units().units))
            except Exception as exc:  # pint and core raise several error types
                errs.append(f"constant {set_name}.{cname}: units {c['units']!r} do not convert to SI ({exc})")
    return errs


def _constant_errors(where: str, c: Mapping[str, Any], rules: Mapping[str, Any]) -> list[str]:
    """Provenance of one ``constants`` entry (RULES.md rules 2-3, brief W0.3 A1/A7).

    Every constant needs a tag that parses with the core ``EvidenceTag``. An ASSUMPTION constant (or one
    flagged ``proxy``) also needs a ``sweep`` [lo, hi] that brackets its value, and a ``prov`` naming an
    ASSUMPTION/PROXY rule with an ``assumption_id``, so that it has a docs/assumptions.md row. A PROXY
    constant must cite a ``P-`` rule. A ``prov`` must always name a known rule.
    """
    errs: list[str] = []
    tag = c["evidence"]["tag"]
    bad = core_tag_error(tag)
    if bad:
        errs.append(f"{where}: {bad}")
    if not str(c["evidence"].get("source", "")).strip():
        errs.append(f"{where}: evidence without a source")
    prov = c.get("prov")
    if prov is not None and prov != "inv" and prov not in rules:
        errs.append(f"{where}: unknown provenance ref {prov}")
    is_assumption = "ASSUMPTION" in parse_tag_classes(tag) or tag.strip().upper().startswith("ASSUMPTION")
    is_proxy = bool(c.get("proxy", False))
    if not (is_assumption or is_proxy):
        return errs
    kind = "PROXY" if is_proxy else "ASSUMPTION"
    sweep = c.get("sweep")
    if sweep is None:
        errs.append(f"{where}: {kind} constant without a sweep range")
    elif not (sweep[0] <= c["value"] <= sweep[1]):
        errs.append(f"{where}: sweep {list(sweep)} does not bracket the value {c['value']}")
    if prov is None:
        errs.append(f"{where}: {kind} constant without a prov rule (it needs a docs/assumptions.md row)")
    elif prov == "inv" or (
        prov in rules and not (rule_needs_register(rules[prov]) and "assumption_id" in rules[prov])
    ):
        errs.append(f"{where}: prov {prov} is not an ASSUMPTION/PROXY rule with an assumption_id")
    elif prov in rules and is_proxy and not rule_is_proxy(rules[prov]):
        errs.append(f"{where}: PROXY constant must cite a P- rule, not {prov}")
    return errs


def _eu_reference_errors(params: Mapping[str, Mapping[str, Any]], tables: Mapping[str, Any]) -> list[str]:
    """``eu_reference_for`` on constants: % of rated speed channels and the speed they convert with."""
    from .units import registry

    errs: list[str] = []
    seen: dict[str, str] = {}
    for set_name, entries in tables["constants"]["sets"].items():
        for cname, c in entries.items():
            targets = c.get("eu_reference_for") or []
            if not targets:
                continue
            where = f"constant {set_name}.{cname}"
            try:
                registry().Quantity(c["value"], c["units"]).to("rad/s")
            except Exception:  # pint raises several error types
                errs.append(
                    f"{where}: eu_reference_for needs a rotational-speed value, got units {c['units']!r}"
                )
            for pid in targets:
                if pid not in params:
                    errs.append(f"{where}: eu_reference_for names unknown parameter {pid}")
                    continue
                for cid, ch in params[pid]["channels"].items():
                    if ch["quantity"] != "speed_percent":
                        errs.append(f"{where}: {cid} is {ch['quantity']}, not speed_percent")
                    if cid in seen:
                        errs.append(f"{cid}: two EU reference speeds ({seen[cid]}, {set_name}.{cname})")
                    seen[cid] = f"{set_name}.{cname}"
    return errs


def validate_channels(
    params: Mapping[str, Mapping[str, Any]],
    tables: Mapping[str, Any],
) -> list[str]:
    """All channel-level checks. ``params`` maps param_id -> parameter dict (with ``channels``)."""
    errs: list[str] = []
    rules = tables["rules"]["rules"]
    lrus = tables["lrus"]["lrus"]
    groups = tables["rate_groups"]["groups"]
    sinks_t = tables["sinks"]["sinks"]
    code_tables = tables["code_tables"]["tables"]
    buses = tables["buses"]
    all_channels = {cid for p in params.values() for cid in p["channels"]}

    for pid, p in params.items():
        ev = p["evidence"]
        if not ev.get("tag", "").strip() or not ev.get("source", "").strip():
            errs.append(f"{pid}: parameter without an evidence tag and a source")
        elif not parse_tag_classes(ev["tag"]):
            errs.append(f"{pid}: evidence tag {ev['tag']!r} names no evidence class")
        else:
            bad = core_tag_error(ev.get("core_tag", ev["tag"]))
            if bad:
                errs.append(f"{pid}: core_tag {ev.get('core_tag', ev['tag'])!r}: {bad}")
        inv = p.get("inventory", {}).get("fields")
        for cid, ch in p["channels"].items():
            errs += _check_channel(
                cid, ch, inv, rules, lrus, groups, sinks_t, code_tables, buses, all_channels
            )
    errs += _check_addresses(params)
    return errs


#: rule families and the only channel fields they can justify (a range rule cannot justify an LSB or a unit)
_RULE_FIELD_FAMILIES: tuple[tuple[str, frozenset[str]], ...] = (
    ("R-RANGE-", frozenset({"range"})),
    ("R-LSB-", frozenset({"recorder_lsb", "native_step"})),
    ("R-NATIVE-EQ-LSB", frozenset({"native_step"})),
    ("R-ADC-BITS", frozenset({"adc_bits"})),
    ("R-CAL-", frozenset({"calibration"})),
    ("R-UNIT-CHOICE", frozenset({"units", "range"})),
)


def _rule_fields(rule_id: str) -> frozenset[str] | None:
    for prefix, fields in _RULE_FIELD_FAMILIES:
        if rule_id.startswith(prefix):
            return fields
    return None


def _check_channel(cid, ch, inv, rules, lrus, groups, sinks_t, code_tables, buses, all_channels) -> list[str]:
    errs: list[str] = []
    prov = ch["prov"]
    is_proxy = False

    def ref(r: str, what: str) -> None:
        nonlocal is_proxy
        if r == "inv":
            if inv is None:
                errs.append(f"{cid}: {what} claims provenance 'inv' but the parameter has no inventory row")
        elif r not in rules:
            errs.append(f"{cid}: {what} cites unknown rule {r}")
        elif rule_is_proxy(rules[r]):
            is_proxy = True

    # --- provenance coverage --------------------------------------------------------------------------------
    for f in _prov_targets(ch):
        if f not in prov:
            errs.append(f"{cid}: field '{f}' has no provenance (evidence tag/source)")
        else:
            ref(prov[f], f)
    for k in prov:
        if k not in PROV_FIELDS:
            errs.append(f"{cid}: provenance for unknown field '{k}'")
        allowed = _rule_fields(prov[k])
        if allowed is not None and k not in allowed:
            errs.append(f"{cid}: rule {prov[k]} cannot justify field '{k}' (it justifies {sorted(allowed)})")
    if prov.get("recorder_lsb") == "R-LSB-BNR" and ch["encoding"].get("type") not in ("bnr", "ubnr"):
        errs.append(
            f"{cid}: recorder LSB cites R-LSB-BNR but the channel is not a BNR word ({ch['encoding']})"
        )
    for s in ch["sinks"]:
        ref(s["prov"], f"sink {s['sink']}")
        ref(s["group_prov"], f"sink {s['sink']} group")
    for lim in ch["limits"]:
        ref(lim["prov"], f"limit {lim['kind']}")
    if ch["proxy"] != is_proxy:
        errs.append(
            f"{cid}: proxy flag {ch['proxy']} disagrees with its provenance (PROXY rule cited: {is_proxy})"
        )

    # --- 'inv' claims verified against the inventory text ---------------------------------------------------
    if inv is not None:
        errs += _check_inv_claims(cid, ch, inv)

    # --- units ----------------------------------------------------------------------------------------------
    errs += [f"{cid}: {e}" for e in check_unit(ch["quantity"], ch["units"])]
    if (ch["quantity"] == "pressure") != ("pressure_ref" in ch):
        errs.append(f"{cid}: pressure_ref must be given exactly for pressure channels")

    # --- range, quantisation, word fit ----------------------------------------------------------------------
    rng = ch["range"]
    enc = ch["encoding"]
    ttype = ch["transport"]["type"]
    finite = rng is not None and rng["min"] is not None and rng["max"] is not None
    if rng is not None and finite and not rng["min"] < rng["max"]:
        errs.append(f"{cid}: range min {rng['min']} is not below max {rng['max']}")
    numeric = enc["type"] in ("bnr", "ubnr", "float64", "int64_ticks")
    if enc["type"] in ("bnr", "ubnr"):
        if not finite or ch["recorder_lsb"] is None:
            errs.append(f"{cid}: {enc['type']} word needs a finite range and a recorder LSB")
        elif not icd.fits_word(rng["min"], rng["max"], ch["recorder_lsb"], enc["type"], enc["word_bits"]):
            errs.append(
                f"{cid}: range [{rng['min']}, {rng['max']}] with LSB {ch['recorder_lsb']} does not fit a "
                f"{enc['word_bits']}-bit {enc['type']} word"
            )
        if ttype == "mil1553" and enc.get("words") != math.ceil(enc["word_bits"] / 16):
            errs.append(
                f"{cid}: {enc['word_bits']}-bit word needs {math.ceil(enc['word_bits'] / 16)} 1553 words"
            )
    if ttype in _RECORDED and numeric and enc["type"] not in ("bnr", "ubnr"):
        errs.append(f"{cid}: numeric value on a recorded transport must be BNR/UBNR word-encoded")
    if ch["adc_bits"] is not None:
        if not finite or ch["native_step"] is None:
            errs.append(f"{cid}: adc_bits needs a finite range and a native step")
        elif (rng["max"] - rng["min"]) / ch["native_step"] > 2 ** ch["adc_bits"] * (1 + 1e-9):
            errs.append(
                f"{cid}: span {rng['max'] - rng['min']} / native step {ch['native_step']} needs more than "
                f"{ch['adc_bits']} ADC bits"
            )
    conv = ch.get("converter_step")
    if conv is not None:
        if ch["role"] != "lane" or not finite or ch["native_step"] is None or conv > ch["native_step"]:
            errs.append(
                f"{cid}: converter_step needs a finite lane channel and must not exceed its native step"
            )
        elif ch["adc_bits"] is not None and (rng["max"] - rng["min"]) / conv > 2 ** ch["adc_bits"] * (
            1 + 1e-9
        ):
            errs.append(f"{cid}: converter step {conv} needs more than {ch['adc_bits']} ADC bits")
    if ch["calibration"] is not None:
        c = ch["calibration"]["coefficients"]
        if ch["recorder_lsb"] is None or not math.isclose(c[1], ch["recorder_lsb"], rel_tol=1e-12):
            errs.append(f"{cid}: calibration gain {c[1]} differs from the recorder LSB {ch['recorder_lsb']}")
    if enc["type"] == "bitfield":
        used: set[int] = set()
        names = [f["name"] for f in enc["fields"]]
        if len(names) != len(set(names)):
            errs.append(f"{cid}: duplicate bit names")
        for f in enc["fields"]:
            bits = set(range(f["lsb_bit"], f["lsb_bit"] + f["width"]))
            if bits & used:
                errs.append(f"{cid}: bit field {f['name']} overlaps another field")
            used |= bits
            if max(bits) >= enc["word_bits"]:
                errs.append(f"{cid}: bit field {f['name']} exceeds the {enc['word_bits']}-bit word")
    if enc["type"] == "enum" and enc.get("code_table") not in code_tables:
        errs.append(f"{cid}: unknown code table {enc.get('code_table')}")

    # --- rate groups ----------------------------------------------------------------------------------------
    for stage, key in (("acquisition", "acquisition"), ("bus", "bus"), ("producer", "producer")):
        g = ch["rates"][key]
        if g is None:
            continue
        if g not in groups:
            errs.append(f"{cid}: unknown {stage} rate group {g}")
        elif stage not in groups[g]["stages"]:
            errs.append(f"{cid}: rate group {g} does not serve the {stage} stage")
    acq = ch["rates"]["acquisition"]
    if acq in groups and groups[acq]["kind"] == "lru_frame" and "frame_hz" not in lrus.get(ch["acq_lru"], {}):
        errs.append(f"{cid}: acquisition group {acq} needs a frame rate for LRU {ch['acq_lru']}")
    if ttype in _RECORDED and ch["rates"]["bus"] is None:
        errs.append(f"{cid}: recorded transport without a bus rate group")

    # --- producers, consumers, sinks (no orphans) -----------------------------------------------------------
    for key in ("source_lru", "acq_lru"):
        if ch[key] not in lrus:
            errs.append(f"{cid}: unknown {key} {ch[key]}")
    if not ch["sinks"]:
        errs.append(f"{cid}: orphan channel (no sink)")
    for s in ch["sinks"]:
        if s["sink"] not in sinks_t:
            errs.append(f"{cid}: unknown sink {s['sink']}")
            continue
        if sinks_t[s["sink"]]["kind"] == "consumer":
            if s.get("consumer") not in lrus:
                errs.append(f"{cid}: INTERNAL sink without a known consumer LRU")
        elif s["group"] is None:
            errs.append(f"{cid}: sink {s['sink']} without a record group")
        if s["group"] is not None and (
            s["group"] not in groups or "record" not in groups[s["group"]]["stages"]
        ):
            errs.append(f"{cid}: sink {s['sink']} group {s['group']} is not a record rate group")
    for i in ch["inputs"]:
        if i not in all_channels:
            errs.append(f"{cid}: input {i} is not a channel")
    if ch["role"] == "voted" and not ch["inputs"]:
        errs.append(f"{cid}: voted output without inputs")

    # --- transport references -------------------------------------------------------------------------------
    t = ch["transport"]
    if t["type"] in ("mil1553", "mil1553_status", "mil1553_modecode"):
        b = buses["mil1553"].get(t.get("bus"))
        if b is None:
            errs.append(f"{cid}: unknown 1553 bus {t.get('bus')}")
        elif t.get("rt") == 31:
            if t.get("tr") != "R" or t.get("rt_lru") != b["bc"]:
                errs.append(
                    f"{cid}: broadcast (RT 31) messages must be BC-to-RT receive messages from the BC"
                )
        elif b["rts"].get(t.get("rt_lru"), {}).get("address") != t.get("rt"):
            errs.append(f"{cid}: RT {t.get('rt')} is not the address of {t.get('rt_lru')} on {t.get('bus')}")
        if t["type"] == "mil1553" and not all(k in t for k in ("sa", "word", "words", "message_words")):
            errs.append(f"{cid}: 1553 data item without SA/word allocation")
        if t["type"] == "mil1553" and ch["validity"]["method"] != "validity_word":
            errs.append(f"{cid}: 1553 data item without a validity-word mapping")
    if t["type"] == "arinc429":
        if t.get("link") not in buses["arinc429"]:
            errs.append(f"{cid}: unknown ARINC-429 link {t.get('link')}")
        if "label" not in t or "sdi" not in t:
            errs.append(f"{cid}: ARINC-429 item without label/SDI")
        if ch["validity"]["method"] != "ssm":
            errs.append(f"{cid}: ARINC-429 item without SSM validity")
    if t["type"] == "fti_pcm":
        stream = buses["fti_pcm"].get(t.get("stream"))
        if stream is None or "word" not in t:
            errs.append(f"{cid}: FTI item without a known stream and word")
        elif enc.get("word_bits") != stream["word_bits"]:
            errs.append(f"{cid}: {enc.get('word_bits')}-bit item in a {stream['word_bits']}-bit PCM stream")
    if t["type"] == "arinc429" and enc.get("word_bits") not in (None, icd.ARINC429_BNR_BITS):
        errs.append(
            f"{cid}: ARINC-429 data field is {icd.ARINC429_BNR_BITS} bits, not {enc.get('word_bits')}"
        )
    if t["type"] in ("arinc429", "fti_pcm") and enc.get("words", 1) != 1:
        errs.append(f"{cid}: an ARINC-429 label or FTI PCM word carries exactly one word")
    if t["type"] == "rs422" and t.get("link") not in buses["rs422"]:
        errs.append(f"{cid}: unknown RS-422 link {t.get('link')}")
    if t["type"] == "internal" and t.get("lru") not in lrus:
        errs.append(f"{cid}: internal transport in unknown LRU {t.get('lru')}")
    if ch["quantity"] not in QUANTITIES:
        errs.append(f"{cid}: unknown quantity {ch['quantity']}")
    return errs


def _check_inv_claims(cid: str, ch: Mapping[str, Any], inv: Mapping[str, str]) -> list[str]:
    """Verify that values whose provenance is 'inv' are written in the inventory row."""
    errs = []
    prov = ch["prov"]
    tok = ch.get("inv_tokens", {})
    for f, ref in prov.items():
        if ref == "inv" and marked_assumption(inv, f):
            errs.append(
                f"{cid}: '{f}' claims 'inv' but the inventory marks it [ASSUMPTION] "
                "(cite R-INV-FIELD-ASSUMPTION)"
            )
    for s in ch["sinks"]:
        if s["group_prov"] == "inv" and marked_assumption(inv, "sink_group"):
            errs.append(
                f"{cid}: sink {s['sink']} record group claims 'inv' but the inventory marks it [ASSUMPTION]"
            )
    if prov.get("units") == "inv" and not unit_justified(ch["units"], inv["units"], tok.get("units")):
        errs.append(f"{cid}: unit {ch['units']!r} claimed from the inventory but not in {inv['units']!r}")
    rng = ch["range"]
    if prov.get("range") == "inv" and rng is not None:
        for v in (rng["min"], rng["max"]):
            if v is None:
                if "cumulative" not in inv["range"]:
                    errs.append(
                        f"{cid}: open range claimed from the inventory but the row does not say 'cumulative'"
                    )
            elif v != 0 and not contains_number(inv["range"], v):
                errs.append(f"{cid}: range value {v} claimed from the inventory but not in {inv['range']!r}")
    for field, col in (
        ("native_step", ("native_resolution", "units")),
        ("recorder_lsb", ("recommended_quantization",)),
    ):
        if prov.get(field) == "inv" and ch[field] is not None:
            text = " | ".join(inv[c] for c in col)
            ok = tok[field] in text if field in tok else contains_number(text, ch[field])
            if not ok:
                errs.append(f"{cid}: {field} {ch[field]} claimed from the inventory but not in {text!r}")
    if prov.get("sensor_type") == "inv" and ch["sensor_type"] != inv["origin_sensor_type"].strip():
        errs.append(f"{cid}: sensor_type differs from the inventory origin_sensor_type")
    if (
        prov.get("rates.acquisition") == "inv"
        and acq_group_for(inv["rate_group_acquisition"]) != ch["rates"]["acquisition"]
    ):
        errs.append(f"{cid}: acquisition group {ch['rates']['acquisition']} is not the inventory's")
    if prov.get("rates.bus") == "inv":
        mapped = bus_group_for(inv["rate_group_bus"])
        if mapped is None or mapped[0] != ch["rates"]["bus"]:
            errs.append(
                f"{cid}: bus group {ch['rates']['bus']} is not the inventory's {inv['rate_group_bus']!r}"
            )
    for s in ch["sinks"]:
        col = _SINK_COLUMNS.get(s["sink"])
        if s["prov"] == "inv" and col is not None and not inv[col].strip().startswith("Y"):
            errs.append(
                f"{cid}: sink {s['sink']} claimed as evidenced but the inventory flag is {inv[col]!r}"
            )
        if s["prov"] == "R-SINK-ASSUMED" and col is not None and not inv[col].strip().startswith("A"):
            errs.append(f"{cid}: sink {s['sink']} cited as assumed but the inventory flag is {inv[col]!r}")
    fields = (
        "range",
        "notes_conflicts",
        "texture_mechanisms",
        "name",
        "physical_drivers",
        "validity_status_flags",
    )
    for lim in ch["limits"]:
        if lim["prov"] != "inv":
            continue
        for k in ("low", "high", "value"):
            if k in lim and not any(contains_number(inv[f], lim[k]) for f in fields):
                errs.append(
                    f"{cid}: limit {lim['kind']} {k}={lim[k]} claimed from the inventory "
                    "but not written there"
                )
    return errs


def _check_addresses(params: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """No two channels share a bus address (A3)."""
    errs: list[str] = []
    words: dict[tuple, list[tuple[int, int, str]]] = defaultdict(list)
    msg_len: dict[tuple, set[int]] = defaultdict(set)
    msg_group: dict[tuple, set[str]] = defaultdict(set)
    singles: dict[tuple, list[str]] = defaultdict(list)
    for p in params.values():
        for cid, ch in p["channels"].items():
            t = ch["transport"]
            if t["type"] == "mil1553" and all(k in t for k in ("sa", "word", "words", "message_words")):
                key = (t["bus"], t["rt"], t["tr"], t["sa"])
                words[key].append((t["word"], t["word"] + t["words"] - 1, cid))
                msg_len[key].add(t["message_words"])
                msg_group[key].add(ch["rates"]["bus"])
                if t["word"] + t["words"] - 1 > t["message_words"]:
                    errs.append(
                        f"{cid}: words {t['word']}..{t['word'] + t['words'] - 1} exceed the message length"
                    )
                v = ch["validity"]
                if v.get("method") == "validity_word":
                    singles[("valbit", *key, v["word"], v["bit"])].append(cid)
                    if v["word"] >= t["word"]:
                        errs.append(f"{cid}: validity word {v['word']} is not before the data words")
            elif t["type"] in ("mil1553_status", "mil1553_modecode"):
                singles[(t["type"], t["bus"], t["rt"])].append(cid)
            elif t["type"] == "arinc429" and "label" in t:
                singles[("429", t["link"], t["label"], t["sdi"])].append(cid)
            elif t["type"] == "fti_pcm" and "word" in t:
                singles[("fti", t["stream"], t["word"])].append(cid)
    for key, spans in words.items():
        spans.sort()
        for (a0, a1, ca), (b0, b1, cb) in itertools.pairwise(spans):
            if b0 <= a1:
                errs.append(
                    f"bus address collision on {key}: {ca} words {a0}..{a1} and {cb} words {b0}..{b1}"
                )
        if len(msg_len[key]) > 1:
            errs.append(f"message {key} has inconsistent lengths {sorted(msg_len[key])}")
        if len(msg_group[key]) > 1:
            errs.append(f"message {key} mixes rate groups {sorted(msg_group[key])}")
    for key, cids in singles.items():
        if len(cids) > 1:
            errs.append(f"address collision {key}: {sorted(cids)}")
    return errs


def validate_all(
    params: Mapping[str, Mapping[str, Any]], tables: Mapping[str, Any], manifest: Mapping[str, Any]
) -> list[str]:
    """Tables + channels; sorted, de-duplicated error list."""
    errs = validate_tables(tables, manifest) + validate_channels(params, tables)
    errs += _eu_reference_errors(params, tables)
    channels = {cid: ch for p in params.values() for cid, ch in p["channels"].items()}
    errs += bit_code_errors(tables["code_tables"]["tables"], channels)
    return sorted(set(errs))


def channel_rule_refs(ch: Mapping[str, Any], param: Mapping[str, Any], tables: Mapping[str, Any]) -> set[str]:
    """Every rule a channel depends on: cited directly, or implied by its rate groups, clock domain, code
    table,
    bus topology and the parameter's evidence tag."""
    groups = tables["rate_groups"]["groups"]
    lrus = tables["lrus"]["lrus"]
    refs: set[str] = {
        *ch["prov"].values(),
        *(s["prov"] for s in ch["sinks"]),
        *(s["group_prov"] for s in ch["sinks"]),
        *(lim["prov"] for lim in ch["limits"]),
    }
    used_groups = [g for g in ch["rates"].values() if g] + [s["group"] for s in ch["sinks"] if s["group"]]
    refs |= {groups[g]["prov"] for g in used_groups if g in groups}
    acq = ch["rates"]["acquisition"]
    if acq in groups and groups[acq]["kind"] == "lru_frame":
        refs.add(lrus.get(ch["acq_lru"], {}).get("frame_prov", "inv"))
    if ch["encoding"].get("code_table"):
        ct = tables["code_tables"]["tables"].get(ch["encoding"]["code_table"], {})
        refs.add(ct.get("prov", "inv"))
        refs |= set(ct.get("extra_prov", []))
    if ch["encoding"].get("type") == "code_word":
        layout = tables["code_tables"]["tables"].get("bit_code_format", {}).get("word_layout")
        if layout:
            refs.add(layout["prov"])
    ttype = ch["transport"]["type"]
    if ttype in ("mil1553", "mil1553_status", "mil1553_modecode", "arinc429"):
        refs.add("R-ICD-TOPOLOGY")
    if ttype in ("mil1553", "mil1553_status", "mil1553_modecode"):
        refs.add("R-ICD-RT-MAP")
    if "ASSUMPTION" in param["evidence"].get("classes", parse_tag_classes(param["evidence"]["tag"])):
        refs.add("R-INV-ROW-ASSUMPTION")
    refs.discard("inv")
    return refs


def affected_params(
    params: Mapping[str, Mapping[str, Any]], tables: Mapping[str, Any], rule_id: str
) -> list[str]:
    """Parameter ids with at least one channel that depends on ``rule_id`` (see :func:`channel_rule_refs`)."""
    return sorted(
        pid
        for pid, p in params.items()
        if any(rule_id in channel_rule_refs(ch, p, tables) for ch in p["channels"].values())
    )
