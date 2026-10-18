"""M08 published ports (W1 interface catalogue `configs/interfaces/w1_ports.yaml`, module M08).

`ports(n_engines)` returns `(inputs, outputs, bindings)`. Catalogue output names are the catalogue keys
without the `fadec.` prefix. `bindings` maps every input port to the signal it reads:

- truth/world signals by catalogue key (`pilot.pla`, `env.p_s`, and in proxy mode `pilot.at_engage`,
  `pilot.at_n1_cmd`);
- digitised FADEC lanes from the in-loop observation path (`W1_interfaces.md` §3) as `lane.<channel_id>` with
  the dictionary channel id. Lane ports carry the **SI value of the digitised reading** (core ports are SI;
  M13 quantises in engineering units and converts with `Dictionary.eu_to_si`).

**Lane buffer convention (the coupling contract, see `coupling.py`).** The FADEC is a clock domain (60 Hz
nominal, AD-39) and shares its oscillator with the M13 lane source and M15 (AD-42): `DEFAULT_CLOCK =
acquisition_clock("FADEC", 60)`. Every lane port is a sample buffer of
`capacity = max_samples_per_step(clock)` slots (1 at 60 Hz): shape `(capacity,)` for one engine - exactly
M13's `lane_<id>` value port - and `(capacity, n_engines)` for the multi-engine proxy configuration. At truth
step `k` the buffer holds, in slots `[0, n)`, the lane readings at the FADEC frame instants that fall in
`[t_{k-1}, t_k)`; `n` and the instants follow from the shared clock (`samples_for_steps`). Slots `>= n` carry
no meaning. M08 computes each frame and its commands apply from `t_k` (the first truth frame after the compute
instant).

**Recorded computed channels (AD-42).** `RECORDED = {output port: dictionary channel id}` lists the
FADEC-computed channels M08 supplies to the recorder (M13 `external=`): the validated N1/N2/T1/PS3 selections
(`.V`), the T5 harness average `ENG.T5`, and the ignition, flameout, exceedance, status and fault-code words
(dimensionless; layouts in `codes.recorded_words`). Values are held between FADEC frames. `ENG.PLA.V` and
`ENG.A8.V` are not produced yet (M08 does not read the PLA resolver or nozzle LVDT lanes; see the README).
"""

from __future__ import annotations

from functools import cache

from phalanx.core.module import Port
from phalanx.core.sampling import max_samples_per_step
from phalanx.core.time import ClockDomain

from .codes import NS, SENSORS

PREFIX = "fadec"

#: nominal FADEC frame rate (AD-39; A-W0.3-25)
FADEC_RATE_HZ = 60.0


@cache
def fadec_clock(rate_hz: float = FADEC_RATE_HZ, platform: str = "tejas") -> ClockDomain:
    """The FADEC oscillator: M13's acquisition clock domain of the FADEC (AD-42, A-W1.6-21), so that M08, its
    in-loop lanes and the bus encoder (M15) share one oscillator."""
    from phalanx.acquisition.config import acquisition_clock

    return acquisition_clock("FADEC", float(rate_hz), platform=platform)


#: default FADEC oscillator (60 Hz nominal, offset and phase from M13's `clock_fadec`)
DEFAULT_CLOCK = fadec_clock()

#: lane input port -> (dictionary channel id, SI unit). Slot order = kernel lane-vector order.
LANE_PORTS: tuple[tuple[str, str, str], ...] = (
    ("n1_a", "ENG.N1.A", "rad/s"),
    ("n1_b", "ENG.N1.B", "rad/s"),
    ("n2_a", "ENG.N2.A", "rad/s"),
    ("n2_b", "ENG.N2.B", "rad/s"),
    ("t1_a", "ENG.T1.A", "K"),
    ("t1_b", "ENG.T1.B", "K"),
    ("t25", "ENG.T25", "K"),
    ("ps3_a", "ENG.PS3.A", "Pa"),
    ("ps3_b", "ENG.PS3.B", "Pa"),
    ("t5_a", "ENG.T5.HARNESS_A", "K"),
    ("t5_b", "ENG.T5.HARNESS_B", "K"),
    ("ab_lit", "ENG.AB_LIT", "1"),
)
#: kernel lane-vector slot of each lane port: sensor s lanes A/B at slots 2s, 2s+1; AB flame detector at 12
LANE_SLOT: dict[str, int] = {
    "n1_a": 0,
    "n1_b": 1,
    "n2_a": 2,
    "n2_b": 3,
    "t1_a": 4,
    "t1_b": 5,
    "t25": 6,
    "ps3_a": 8,
    "ps3_b": 9,
    "t5_a": 10,
    "t5_b": 11,
    "ab_lit": 12,
}
N_LANE_SLOTS = 13
AB_LIT_SLOT = 12
#: number of lanes per validated sensor (N1, N2, T1, T25, PS3, T5); T5 lanes are the two 4-probe harnesses
LANES_PER_SENSOR: tuple[int, ...] = (2, 2, 2, 1, 2, 2)
assert len(LANES_PER_SENSOR) == NS == len(SENSORS)

#: catalogue output names (W1_interfaces.md M08), in publication order
OUTPUT_NAMES: tuple[str, ...] = (
    "wf_cmd",
    "wf_ab_cmd",
    "a8_cmd",
    "vg_cmd",
    "ignition",
    "ab_enable",
    "active_limiter",
    "validation_state",
)

#: recorded FADEC-computed channels (AD-42): output port -> dictionary channel id
RECORDED: dict[str, str] = {
    "n1_v": "ENG.N1.V",
    "n2_v": "ENG.N2.V",
    "t1_v": "ENG.T1.V",
    "ps3_v": "ENG.PS3.V",
    "t5_avg": "ENG.T5",
    "ign_word": "ENG.IGN",
    "flameout_word": "ENG.FLAMEOUT",
    "limit_flags": "ENG.LIMIT_FLAGS",
    "status_word": "ENG.FADEC_STATUS",
    "fault_code": "ENG.FAULT_CODES",
}
#: validated-sensor index of each recorded value port (`codes.SENSORS` order); the rest are discrete words
RECORDED_SENSOR: dict[str, int] = {"n1_v": 0, "n2_v": 1, "t1_v": 2, "ps3_v": 4, "t5_avg": 5}
_RECORDED_UNIT = {"n1_v": "rad/s", "n2_v": "rad/s", "t1_v": "K", "ps3_v": "Pa", "t5_avg": "K"}
#: dictionary channels M08 is expected to supply but cannot produce yet (reported; see the README)
RECORDED_MISSING: dict[str, str] = {
    "ENG.PLA.V": "M08 governs on pilot.pla; the PLA resolver lanes (lane.ENG.PLA.A/B) are not validated yet",
    "ENG.A8.V": "M08 commands A8 open loop; the nozzle LVDT lanes (lane.ENG.A8.A/B) are not read yet",
}

#: cross-module events (AD-44 declaration convention), catalogued in configs/interfaces/w1_events.yaml:
#: M08 -> M14 (BIT/monitoring) fault and caution transitions `fadec.fault` / `fadec.caution`
#: (`Fadec(event_target=...)`), and M11 -> M08 physical fault injection `fadec.fault_inject` (AD-48.4).
MODULE_IDS = ("M08",)
_FAULT_EVENT_PAYLOAD = ("engine", "code", "set", "sensor", "lane", "description", "t_frame_ns", "frame")
EVENTS_OUT: dict[str, tuple[str, ...]] = {
    "fadec.fault": _FAULT_EVENT_PAYLOAD,
    "fadec.caution": _FAULT_EVENT_PAYLOAD,
}
EVENTS_IN: dict[str, tuple[str, ...]] = {
    "fadec.fault_inject": ("tail", "mode", "param", "instance", "engine", "clear"),
}


#: P0 (ambient static pressure) sources (W2.2). The Tejas FADEC reads the aircraft air data: the F404 ECU's P0
#: input is an altitude signal (NASA CR-179568 Fig. 3) [TRANSFER: F404-400], so P0 is the standard-atmosphere
#: pressure at the avionics ADC's pressure altitude AD.HP (= its position-error-corrected static pressure;
#: A-W1.3b-11 PROXY retired for Tejas). The DASHlink proxy chain has no aircraft air-data system: its P0 stays
#: the replayed static pressure of the recorded flight condition (env.p_s), as do TEST FIXTURE loops without
#: avionics.
P0_AIR_DATA = "avio.p0_from_hp"
P0_ENV = "env.p_s"


def capacity(clock: ClockDomain = DEFAULT_CLOCK) -> int:
    """Lane-buffer capacity: most FADEC frames that can fall in one 240 Hz truth step."""
    return max_samples_per_step(clock, 1)


def lane_shape(n_engines: int, clock: ClockDomain = DEFAULT_CLOCK) -> tuple[int, ...]:
    """Shape of one lane port: `(capacity,)` for one engine (M13's buffer), else `(capacity, n_engines)`."""
    cap = capacity(clock)
    return (cap,) if int(n_engines) == 1 else (cap, int(n_engines))


def ports(
    n_engines: int = 1,
    *,
    autothrottle: bool = False,
    clock: ClockDomain = DEFAULT_CLOCK,
    p0_source: str | None = None,
) -> tuple[tuple[Port, ...], tuple[Port, ...], dict[str, str]]:
    """(inputs, outputs, bindings) of one M08 instance (vectorised over `n_engines`).

    `autothrottle=True` adds the proxy-mode autothrottle inputs (architecture §14.3); the Tejas configuration
    has no autothrottle. Outputs are the catalogue ports followed by the `RECORDED` ports. `p0_source`: the
    signal bound to P0; default the air data (`P0_AIR_DATA`) on Tejas, the replayed `env.p_s` in proxy mode.
    """
    e = int(n_engines)
    if e < 1:
        raise ValueError("n_engines must be >= 1")
    ins: list[Port] = [
        Port("pla", "rad", "<f8", (e,)),
        Port("p0", "Pa", "<f8", ()),
    ]
    p0 = p0_source if p0_source is not None else (P0_ENV if autothrottle else P0_AIR_DATA)
    if p0 not in (P0_AIR_DATA, P0_ENV):
        raise ValueError(f"p0_source must be {P0_AIR_DATA!r} or {P0_ENV!r}, got {p0!r}")
    bindings = {"pla": "pilot.pla", "p0": p0}
    if autothrottle:
        ins += [Port("at_engage", "1", "<i8", ()), Port("at_n1_cmd", "1", "<f8", (e,))]
        bindings.update({"at_engage": "pilot.at_engage", "at_n1_cmd": "pilot.at_n1_cmd"})
    shp = lane_shape(e, clock)
    for name, cid, unit in LANE_PORTS:
        ins.append(Port(name, unit, "<f8", shp, clock))
        bindings[name] = f"lane.{cid}"
    outs = (
        Port("wf_cmd", "kg/s", "<f8", (e,), clock),
        Port("wf_ab_cmd", "kg/s", "<f8", (e,), clock),
        Port("a8_cmd", "m**2", "<f8", (e,), clock),
        Port("vg_cmd", "rad", "<f8", (e, 2), clock),
        Port("ignition", "1", "<i8", (e,), clock),
        Port("ab_enable", "1", "<i8", (e,), clock),
        Port("active_limiter", "1", "<i8", (e,), clock),
        Port("validation_state", "1", "<i8", (e, NS), clock),
    )
    assert tuple(p.name for p in outs) == OUTPUT_NAMES
    rec = tuple(
        Port(name, _RECORDED_UNIT[name], "<f8", (e,), clock)
        if name in RECORDED_SENSOR
        else Port(name, "1", "<i8", (e,), clock)
        for name in RECORDED
    )
    return tuple(ins), outs + rec, bindings


__all__ = [
    "AB_LIT_SLOT",
    "DEFAULT_CLOCK",
    "EVENTS_IN",
    "EVENTS_OUT",
    "FADEC_RATE_HZ",
    "LANES_PER_SENSOR",
    "LANE_PORTS",
    "LANE_SLOT",
    "MODULE_IDS",
    "N_LANE_SLOTS",
    "OUTPUT_NAMES",
    "P0_AIR_DATA",
    "P0_ENV",
    "PREFIX",
    "RECORDED",
    "RECORDED_MISSING",
    "RECORDED_SENSOR",
    "capacity",
    "fadec_clock",
    "lane_shape",
    "ports",
]
