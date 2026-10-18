"""U6 channel coverage (W2.2 item 2; A-W2.2-11): every dictionary channel has exactly one owner class, and the
plan in configs/tejas/coverage/channel_coverage.yaml agrees with the code, so no channel is silently absent.

Cross-checks (each a function returning problems, so the negative controls can plant defects):

- classification: the plan's channels are exactly the 464 dictionary channels, one class each;
- m12_sensor == the M12 channel map; recorded == the union of every ports.RECORDED (15 gated packages + the
  M12 avionics extension), with the producing module and port;
- acquisition: M13 builds an acquisition configuration for a produced channel iff it has no ``acq_gap``, and a
  refusal is the gap's reason (a missing LRU clock set); since W2.2 phase B every produced channel builds
  (numeric channels on their LRU clock sets, words through the word path);
- topics: usage.counters == the M14 counters; the other topic routes exist in the contract spec;
- not_simulated: absent from every producer, and ``nm`` equals the not_measured_states.csv rows citing it;
- named gaps (ECS, BRK.PRESS, HYD level, ENG.FUEL_INLET_T, SPS/JFS, the AD-42 truth signals) have owners and
  plans; gap truth signals are catalogued; truth-signal binding states match the code;
- M14 monitors whose input channel does not reach param.samples are named as consumers of that gap.

n = all 464 channels (exhaustive; the checks are deterministic).
"""

from __future__ import annotations

import csv
import dataclasses
import fnmatch
import importlib
import re
from collections.abc import Mapping
from functools import cache
from pathlib import Path

import pytest

from phalanx.acquisition.config import build_acquisition_config
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.contract import load_contract
from phalanx.dictionary.yamlio import load_yaml
from phalanx.ground.coverage import CLASSES, CoveragePlan, load_coverage
from phalanx.ground.fast_path import FTI_TRANSPORT, RECORDED_TRANSPORTS, FastPathConfig
from phalanx.monitoring.module import COUNTERS
from phalanx.sensors.config import build_sensor_config

ROOT = Path(__file__).resolve().parents[2]
D = load_dictionary()
PLAN = load_coverage()
CONTRACT = load_contract("v0")
PKGS = {
    "M02": "scenario",
    "M03": "environment",
    "M04": "pilot",
    "M05": "fcs",
    "M06": "airframe",
    "M07": "engine",
    "M08": "fadec",
    "M09": "utilities",
    "M10": "health",
    "M11": "faults",
    "M12": "sensors",
    "M13": "acquisition",
    "M14": "monitoring",
    "M18": "maintenance",
    "M21": "orders",
}
NM_CSV = ROOT / "research_notes" / "Virtual fighter telemetry layer research" / "not_measured_states.csv"
CATALOGUE = load_yaml(ROOT / "configs" / "interfaces" / "w1_ports.yaml")
#: code identity (lru, mech, monitor, ...) lives in the dictionary since W2.1c (AD-48.5); M14 codes.yaml keeps
#: behaviour rows only
CODES = {c: dict(D.bit_code(c)) for c in D.bit_codes()}
#: AD-42 truth signals the M12 channel map does not read (W2.2 phase B bound util.brake_p, util.hyd_res_level,
#: util.fuel_inlet_t and util.probe_heat; af.hag is read by the avionics radar altimeter)
AD42_UNBOUND = ("af.hag",)
#: named-gap channels W2.2 phase B item 2 produced: M12 sensors on M09 truth
ITEM2_PRODUCED = (
    "BRK.PRESS.L",
    "BRK.PRESS.R",
    "HYD.SYS1.LEVEL.LEVEL",
    "HYD.SYS2.LEVEL.LEVEL",
    "ENG.FUEL_INLET_T",
    "ECS.BLEED_T.PHX_IN",
    "ECS.BLEED_T.PHX_OUT",
    "ECS.COCKPIT_T.ACM_OUT",
    "ECS.COCKPIT_T.COCKPIT",
    "ECS.AVIONICS_T.TEMP",
    "ECS.BLEED_P",
    "ECS.CABIN_P.PRESS",
)


@cache
def m12_channels() -> tuple[str, ...]:
    return tuple(build_sensor_config(D).channels)


@cache
def recorded() -> dict[str, tuple[str, str]]:
    """channel -> (module, port) over every RECORDED map; a channel in two maps is a defect (raises)."""
    out: dict[str, tuple[str, str]] = {}
    maps = [(mod, importlib.import_module(f"phalanx.{pkg}.ports")) for mod, pkg in PKGS.items()]
    maps.append(("M12", importlib.import_module("phalanx.sensors.avionics.ports")))
    for mod, m in maps:
        for port, cid in getattr(m, "RECORDED", {}).items():
            if cid in out:
                raise AssertionError(f"{cid} is RECORDED by {out[cid]} and {(mod, port)}")
            out[cid] = (mod, port)
    return out


@cache
def acquisition_refusal(cid: str) -> str | None:
    """None if M13 builds an acquisition configuration for the channel, else the gap id its refusal
    implies."""
    try:
        build_acquisition_config(D, [cid], sensor_channels=m12_channels())
        return None
    except Exception as x:  # the message is classified below; anything else is a problem
        msg = str(x)
        m = re.search(r"no clock set for its acquisition domain LRU '([A-Z0-9_]+)'", msg)
        return f"G-ACQ-CLOCK-{m.group(1)}" if m else f"unclassified refusal: {msg}"


@cache
def nm_rows() -> tuple[dict[str, str], ...]:
    with NM_CSV.open(newline="", encoding="utf-8") as fh:
        return tuple(csv.DictReader(fh))


def nm_refs(cid: str) -> tuple[str, ...]:
    """not_measured_states.csv rows whose partial-information signals cite ``cid`` (rule in the plan
    header)."""
    out = []
    for r in nm_rows():
        for tok in r["partial_information_signals"].split(";"):
            t = re.sub(r"\s*\(.*\)\s*$", "", tok.strip())
            if not t or t == "none":
                continue
            if fnmatch.fnmatchcase(cid, t) if "*" in t else (cid == t or cid.startswith(t + ".")):
                out.append(r["state_id"])
                break
    return tuple(out)


def spec_fields(topic: str) -> set[str]:
    return set(CONTRACT.topics[topic].field_names)


def catalogue_signals() -> set[str]:
    return {name for m in CATALOGUE["modules"].values() for name in m["out"]}


# ---------------------------------------------------------------------------------------------- the checks
def classification_problems(plan: CoveragePlan) -> list[str]:
    ids = {c["channel_id"] for c in D.channels()}
    p = [f"{c}: not classified" for c in sorted(ids - set(plan.channels))]
    p += [f"{c}: not a dictionary channel" for c in sorted(set(plan.channels) - ids)]
    p += [f"{c}: class {e.cls}" for c, e in plan.channels.items() if e.cls not in CLASSES]
    return p


def producer_problems(plan: CoveragePlan) -> list[str]:
    p = []
    m12 = set(m12_channels())
    rec = recorded()
    counters = {pid for pid, _, _ in COUNTERS}
    for cid, e in plan.channels.items():
        if (e.cls == "m12_sensor") != (cid in m12):
            p.append(f"{cid}: class {e.cls} but M12 channel map membership is {cid in m12}")
        if (e.cls == "recorded") != (cid in rec):
            p.append(f"{cid}: class {e.cls} but RECORDED membership is {cid in rec}")
        elif e.cls == "recorded" and (e.producer, e.port) != rec[cid]:
            p.append(f"{cid}: producer {(e.producer, e.port)} != RECORDED {rec[cid]}")
        if (e.cls == "topic" and e.topic == "usage.counters") != (cid in counters):
            p.append(f"{cid}: usage.counters route != M14 COUNTERS membership ({cid in counters})")
        if e.cls == "not_simulated" and (cid in m12 or cid in rec or cid in counters):
            p.append(f"{cid}: not_simulated but produced")
    return p


def acquisition_problems(plan: CoveragePlan) -> list[str]:
    p = []
    for cid, e in plan.channels.items():
        if e.cls not in ("m12_sensor", "recorded"):
            continue
        got = acquisition_refusal(cid)
        if got != e.acq_gap:
            p.append(f"{cid}: M13 acquisition -> {got or 'builds'}, plan says {e.acq_gap or 'builds'}")
    return p


def route_problems(plan: CoveragePlan) -> list[str]:
    """AD-54: a produced channel's route follows its dictionary transport, and agrees with the fast path's
    visible set (service configuration: FTI not fitted; fitted: FTI channels join it)."""
    p = []
    vis = FastPathConfig.from_dictionary(D).visible
    vis_fti = FastPathConfig.from_dictionary(D, fti_fitted=True).visible
    for cid, e in plan.channels.items():
        if e.cls not in ("m12_sensor", "recorded"):
            continue
        t = D.channel(cid)["transport"]["type"]
        want = "param_samples" if t in RECORDED_TRANSPORTS else ("fti" if t == FTI_TRANSPORT else "internal")
        if e.route != want:
            p.append(f"{cid}: route {e.route}, transport {t} implies {want}")
        loc = D.contract_location(cid)
        key = (loc["param_id"], loc["source_lru"], loc["lane"])
        if (key in vis) != (e.route == "param_samples") or (key in vis_fti) != (e.route != "internal"):
            p.append(f"{cid}: route {e.route} disagrees with the fast path's visible channel set")
    return p


def topic_problems(plan: CoveragePlan) -> list[str]:
    p = []
    topics = set(CONTRACT.topics)
    dfcc_bit = [c for c, s in CODES.items() if s.get("lru") == "DFCC" and s.get("mech") == "CBIT"]
    for cid, e in plan.channels.items():
        if e.cls != "topic":
            continue
        if e.topic not in topics:
            p.append(f"{cid}: topic {e.topic} not in the contract")
            continue
        if e.field is not None and e.field not in spec_fields(e.topic):
            p.append(f"{cid}: field {e.field} not in {e.topic}")
        if e.producer == "none" and e.gap is None:
            p.append(f"{cid}: topic without a producer must name its gap")
        if e.topic == "events.bit_faults" and not dfcc_bit:
            p.append(f"{cid}: no DFCC CBIT codes feed events.bit_faults")
    return p


def not_simulated_problems(plan: CoveragePlan) -> list[str]:
    p = []
    for cid, e in plan.channels.items():
        want = nm_refs(cid) if e.cls == "not_simulated" else ()
        if e.cls == "not_simulated" and tuple(e.nm) != want:
            p.append(f"{cid}: nm {list(e.nm)} != not_measured_states.csv {list(want)}")
        if e.cls != "not_simulated" and e.nm:
            p.append(f"{cid}: nm cross-references are for absent channels only")
    return p


def gap_problems(plan: CoveragePlan) -> list[str]:
    p = []
    cat = catalogue_signals()
    for gid, g in plan.gaps.items():
        if not g.owner or not g.plan.strip() or not g.wp.strip():
            p.append(f"{gid}: owner, wp and plan are required")
        p += [f"{gid}: truth signal {s} not catalogued" for s in g.truth if s not in cat]
    absent = [c for c, e in plan.channels.items() if e.cls == "not_simulated"]  # produced ones are covered
    named = {
        "ECS": ("G-ECS", [c for c in absent if c.startswith(("ECS.", "LSS."))]),
        "brakes": ("G-BRAKES", [c for c in absent if c.startswith("BRK.")]),
        "HYD level": ("G-HYD-LEVEL", [c for c in absent if re.match(r"HYD\.SYS\d\.LEVEL\.", c)]),
        "SPS/JFS": ("G-SPS-JFS", [c for c in absent if c.startswith("SPS.")]),
    }
    # BRK.PRESS, the HYD level transmitters, the ECS points and ENG.FUEL_INLET_T are M12 sensors since W2.2
    p += [
        f"named gap channel {c}: class {plan.channels[c].cls}, not m12_sensor"
        for c in ITEM2_PRODUCED
        if plan.channels[c].cls != "m12_sensor"
    ]
    for name, (gid, chans) in named.items():
        if gid not in plan.gaps or not chans:
            p.append(f"named gap {name}: {gid} missing")
            continue
        p += [f"named gap {name}: {c} not on {gid}" for c in chans if plan.channels[c].gap != gid]
    return p


def truth_signal_problems(plan: CoveragePlan) -> list[str]:
    """AD-42 signals the M12 channel map does not read: still none of them is read by the channel map; status
    'bound' / 'partial' = read by the M12 avionics extension, 'unbound' = read by no part of M12."""
    p = []
    if set(plan.truth_signals) != set(AD42_UNBOUND):
        p.append(f"truth_signals {sorted(plan.truth_signals)} != {sorted(AD42_UNBOUND)}")
    m12_in = {s.signal for s in build_sensor_config(D).inputs}
    _, _, avio = importlib.import_module("phalanx.sensors.avionics.ports").ports(n_engines=1)
    bound = set(avio.values())
    for sig, t in plan.truth_signals.items():
        if sig in m12_in:
            p.append(f"{sig}: now bound by the M12 channel map (close its gap)")
        if (t["status"] in ("bound", "partial")) != (sig in bound):
            p.append(f"{sig}: status {t['status']} but read by the M12 avionics extension = {sig in bound}")
    return p


def consumer_problems(plan: CoveragePlan) -> list[str]:
    """Every M14 monitor whose input does not reach param.samples is a listed consumer of that channel's gap,
    and every listed consumer is such a monitor."""
    p = []
    expected: dict[str, set[str]] = {}
    for code, spec in CODES.items():
        mon = spec.get("monitor") if isinstance(spec, Mapping) else None
        if not mon:
            continue
        e = plan.channels.get(mon["channel"])
        if e is None:
            p.append(f"M14:{code}: monitor channel {mon['channel']} is not a dictionary channel")
            continue
        if not e.in_param_samples:
            expected.setdefault(e.gap or e.acq_gap, set()).add(f"M14:{code}")
    for gid, g in plan.gaps.items():
        got = {c for c in g.consumers if c.startswith("M14:")}
        if got != expected.get(gid, set()):
            p.append(
                f"{gid}: consumers {sorted(got)} != monitors without input {sorted(expected.get(gid, set()))}"
            )
    return p


CHECKS = (
    classification_problems,
    producer_problems,
    acquisition_problems,
    route_problems,
    topic_problems,
    not_simulated_problems,
    gap_problems,
    truth_signal_problems,
    consumer_problems,
)


# ---------------------------------------------------------------------------------------------- the tests
@pytest.mark.integration
@pytest.mark.parametrize("check", CHECKS, ids=[c.__name__ for c in CHECKS])
def test_coverage_plan_agrees_with_the_code(check):
    problems = check(PLAN)
    assert not problems, "\n".join(problems)


@pytest.mark.integration
def test_every_channel_has_exactly_one_owner_class():
    counts = PLAN.counts()
    assert sum(counts.values()) == len(PLAN.channels) == 464
    assert set(counts) == set(CLASSES)
    absent = [c for c, e in PLAN.channels.items() if not e.produced]
    assert all(PLAN.channels[c].gap for c in absent)  # every absence is named
    reach = [c for c, e in PLAN.channels.items() if e.in_param_samples]
    # 37 bus-recorded M12 sensors (incl. the UV flame detector ENG.AB_LIT and the 12 item-2 sensors on M09
    # truth, W2.2) + 125 RECORDED channels: the 50 numeric ones of phase A, the 53 words of the W2.2 word path
    # and the 22 INS/GPS, AHRS and radar-altimeter outputs on their clock sets (AD-54: the 103 internal lanes
    # and the 5 FTI channels are not consumer-visible in the service configuration)
    assert len(reach) == 162


def _planted(**changes: ChannelEdit) -> CoveragePlan:
    ch = dict(PLAN.channels)
    for cid, edit in changes.items():
        if edit is None:
            del ch[cid]
        else:
            ch[cid] = dataclasses.replace(ch[cid], **edit)
    return dataclasses.replace(PLAN, channels=ch)


ChannelEdit = dict | None


@pytest.mark.integration
def test_negative_controls_planted_defects_are_caught():
    assert classification_problems(_planted(**{"ENG.N1.A": None}))
    assert producer_problems(
        _planted(**{"ENG.N1.A": {"cls": "not_simulated", "gap": "G-ECS", "target": "none"}})
    )
    assert producer_problems(_planted(**{"ECS.TCV": {"cls": "m12_sensor", "gap": None, "target": None}}))
    assert producer_problems(_planted(**{"AD.HP": {"port": "rec_wrong"}}))
    assert acquisition_problems(_planted(**{"NAV.INS.LAT": {"acq_gap": "G-ACQ-CLOCK-INGPS"}}))  # it builds
    assert acquisition_problems(_planted(**{"CWS.MASTER": {"acq_gap": "G-ACQ-WORDS"}}))  # a word builds too
    refused = {"cls": "recorded", "producer": "M14", "port": "rec_mx_borescope", "gap": None, "target": None}
    assert acquisition_problems(_planted(**{"MX.BORESCOPE": refused}))  # M13 refuses (no LRU clock domain)
    assert route_problems(_planted(**{"ENG.N1.A": {"route": "param_samples"}}))
    assert route_problems(_planted(**{"AD.BOOM.PS": {"route": "internal"}}))
    assert not_simulated_problems(_planted(**{"MX.SOAP.FE": {"nm": ()}}))
    assert topic_problems(_planted(**{"SYS.IDS.TAIL_NO": {"field": "no_such_field"}}))
    assert consumer_problems(_planted(**{"ENG.CHIP": {"gap": "G-FIRE"}}))
    assert gap_problems(_planted(**{"ECS.TCV": {"gap": "G-ELEC"}}))
    assert gap_problems(
        _planted(**{"BRK.PRESS.L": {"cls": "not_simulated", "gap": "G-BRAKES", "target": "m12_sensor"}})
    )
