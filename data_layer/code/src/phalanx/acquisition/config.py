"""M13 configuration: dictionary + ``M13.yaml`` + acquisition map -> per-channel kernel tables.

Everything that defines the recorded word comes from the dictionary (M01): native step, recorder LSB, range,
acquisition LRU and rate, signal type, EU <-> SI conversion and contract identity. ``M13.yaml`` adds only the
texture parameters (noise, gating, deadband, freeze, glitch, clocks, slip), each with provenance.

**Noise ceiling (W0.5 finding, A-W1.6-23).** For every channel the effective idiosyncratic sigma
``sigma * max(phase multiplier) * sqrt(1 + p_tail (k_tail^2 - 1))`` must not exceed the measured idiosyncratic
level of its class (``ceiling_*`` sets). ``build_acquisition_config`` refuses a configuration that breaks it.

**Converter step (dictionary 0.1.2 migration, W2.2; 0.1.3).** The 12 FADEC lanes are digitised by the FADEC's
own converter (span / 2^14, R-FADEC-ADC, A-W0.3-41), finer than their recorded word: since dictionary 0.1.3
that step is their ``native_step``, and their noise and ceilings are given in EU (``sigma_eu``). A dictionary
that still carries a separate ``converter_step`` (0.1.2, the DASHlink proxy) quantises at it, and its noise
and ceiling must then be in EU, never in ``sigma_steps``: a step-relative noise would change silently when the
step moves into ``native_step``. Noise in steps (all other channels) stays ``sigma_steps x native_step``.
"""

from __future__ import annotations

import fnmatch
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np

from phalanx.core.module import ContractError, ParamSet
from phalanx.core.time import ClockDomain
from phalanx.dictionary.params import load_params, params_dir
from phalanx.dictionary.yamlio import load_yaml
from phalanx.sensors.config import dictionary_id

from . import kernel as K

MAP_FORMAT = "phalanx.acquisition.map/1"
#: flight-phase codes in which episodic freezes may start (dictionary code table ``flight_phase``:
#: 3 TAKEOFF, 4 CLIMB, 5 CRUISE, 6 APPROACH, and the synthetic fighter phases added in dictionary 0.1.2:
#: 9 MISSION, 10 DESCENT, 11 PATTERN, 12 TOUCH_AND_GO; the proxy rates are per airborne hour)
AIRBORNE_PHASES = (3, 4, 5, 6, 9, 10, 11, 12)


@dataclass(frozen=True)
class SlipSpec:
    """Analog slip of one domain: converter clock, collision window [ns], in-window sentinel probability."""

    converter: ClockDomain
    window_ns: int
    p_in: float


@dataclass(frozen=True)
class DomainSpec:
    """One acquisition clock domain (an LRU's oscillator at one acquisition rate) and its channels."""

    name: str
    lru: str
    clock: ClockDomain
    channels: tuple[int, ...]
    slip: SlipSpec | None


@dataclass(frozen=True)
class AcqConfig:
    """Per-channel acquisition tables in kernel order (see ``kernel.py`` for the columns)."""

    channels: tuple[str, ...]
    sensor_index: tuple[int, ...]  # index into the M12 channel list; -1 for an externally computed channel
    domains: tuple[DomainSpec, ...]
    domain_of: np.ndarray
    P: np.ndarray
    Q: np.ndarray
    regime: np.ndarray
    airborne: np.ndarray
    slot_phase_ns: np.ndarray
    sigma_eff_eu: np.ndarray
    ceiling_eu: np.ndarray
    location: tuple[Mapping[str, Any], ...]
    signals: tuple[str, ...]

    @property
    def n(self) -> int:
        return len(self.channels)

    def index(self, channel_id: str) -> int:
        try:
            return self.channels.index(channel_id)
        except ValueError:
            raise KeyError(f"channel {channel_id!r} is not acquired by this configuration") from None

    def eu_scale(self) -> np.ndarray:
        return self.P[:, K.AP_SCALE]

    def eu_offset(self) -> np.ndarray:
        return self.P[:, K.AP_OFF]


def _rule(rules: Sequence[Mapping[str, str]] | None, cid: str) -> str | None:
    for r in rules or ():
        if fnmatch.fnmatchcase(cid, r["match"]):
            return r["set"]
    return None


def _code_bound(x: float, step: float, off: float, *, upper: bool) -> int:
    r = (x - off) / step
    n = round(r)
    if abs(r - n) <= 1e-9 * max(1.0, abs(r)):
        return int(n)
    return math.floor(r) if upper else math.ceil(r)


def _clock(lru: str, rate: float, ps: ParamSet) -> ClockDomain:
    return ClockDomain(
        f"{lru}@{rate:g}Hz", rate, float(ps.value("offset_ppm")), round(float(ps.value("phase")) * 1e9)
    )


def acquisition_clock(
    lru: str,
    rate_hz: float,
    *,
    platform: str = "tejas",
    params: Mapping[str, ParamSet] | None = None,
    acq_map: Mapping[str, Any] | None = None,
    config_root: Path | None = None,
) -> ClockDomain:
    """The acquisition ``ClockDomain`` of ``lru`` at ``rate_hz`` (A-W1.6-21).

    A controller that computes on in-loop lanes (M08 FADEC, M05 DFCC) and the bus encoder (M15) must use this
    domain, so that their compute/update instants are the acquisition instants M13 samples at.
    """
    params = (
        dict(params) if params is not None else load_params("M13", platform=platform, config_root=config_root)
    )
    if acq_map is None:
        acq_map = load_yaml(params_dir(platform, config_root) / "M13" / "acquisition_map.yaml")
    clk_set = (acq_map.get("clocks") or {}).get(lru)
    if clk_set is None:
        raise ContractError(f"no M13 clock set for LRU {lru!r}")
    return _clock(lru, float(rate_hz), params[clk_set])


def acquisition_domain_lru(dictionary: Any, channel_id: str) -> str:
    """The LRU whose crystal acquires ``channel_id``: the domain of its dictionary acquisition rate group when
    that names an LRU (FCS80 -> DFCC, FADEC-INT -> FADEC, FTI -> FTI_DAS, LRU-INT-INS -> INGPS,
    ECMS10 -> ECMS), else the channel's own ``acq_lru`` (``owning LRU`` groups: LRU-INT, LRU-INT-SLOW, ...).

    Example: ENG.WFAB has ``acq_lru`` FADEC but rate group FTI, so it is sampled on the FTI_DAS crystal, the
    PCM frame crystal it shares with the other FTI channels.
    """
    ch = dictionary.channel(dictionary_id(channel_id))  # engine instances (U3) use their channel's entry
    group = ch["rates"]["acquisition"]
    dom = dictionary.content["rate_groups"][group].get("domain")
    if dom in dictionary.content["lrus"]:
        return str(dom)
    if dom == "owning LRU":
        return str(ch["acq_lru"])
    raise ContractError(f"{channel_id}: acquisition rate group {group!r} has no LRU clock domain ({dom!r})")


#: dictionary encodings of status / discrete / code words, acquired by the word path (W2.2, A-W2.2-12)
WORD_ENCODINGS = frozenset({"bitfield", "enum", "code_word"})


def is_word_channel(dictionary: Any, channel_id: str) -> bool:
    """A status / discrete / code word: a word encoding and no native step (nothing to quantise)."""
    ch = dictionary.channel(dictionary_id(channel_id))
    return (ch.get("encoding") or {}).get("type") in WORD_ENCODINGS and ch.get("native_step") is None


def acquisition_rate(dictionary: Any, channel_id: str) -> float | None:
    """The channel's acquisition rate: the dictionary's, or for an event-driven word (no periodic acquisition
    rate) its bus refresh rate: the LRU puts its current word on the bus every bus frame (A-W2.2-12)."""
    did = dictionary_id(channel_id)
    rate = dictionary.acquisition_rate_hz(did)
    if rate is None and is_word_channel(dictionary, did):
        bus = dictionary.channel(did)["rates"].get("bus")
        if bus is not None:
            rate = dictionary.content["rate_groups"][bus].get("rate_hz")
    return rate


def _word_max(dictionary: Any, ch: Mapping[str, Any]) -> int:
    """Largest EU value of a word: all bits set, or for a code word the largest k * scale + NNN."""
    enc = ch["encoding"]
    if enc["type"] == "code_word":
        lay = dictionary.content["code_tables"]["bit_code_format"]["word_layout"]
        k_max = (1 << int(lay["prefix_index"]["width"])) - 1
        n_max = (1 << int(lay["number"]["width"])) - 1
        return int(k_max * int(lay["eu_prefix_scale"]) + n_max)
    return (1 << (int(enc["word_bits"]) * int(enc.get("words", 1)))) - 1


def clock_consistency_problems(
    dictionary: Any,
    acq: AcqConfig,
    *,
    params: Mapping[str, ParamSet] | None = None,
    acq_map: Mapping[str, Any] | None = None,
) -> list[str]:
    """Every acquisition stream must sit on the clock of its dictionary acquisition domain at its dictionary
    acquisition rate (``acquisition_domain_lru``, ``Dictionary.acquisition_rate_hz``, ``acquisition_clock``).
    Returns one message per violating channel (empty when consistent)."""
    problems = []
    for c, cid in enumerate(acq.channels):
        dom = acq.domains[int(acq.domain_of[c])]
        lru = acquisition_domain_lru(dictionary, cid)
        rate = acquisition_rate(dictionary, cid)
        expect = acquisition_clock(lru, float(rate), params=params, acq_map=acq_map)
        if dom.lru != lru or dom.clock != expect:
            problems.append(
                f"{cid}: sampled on {dom.clock.name} ({dom.lru}, {float(dom.clock.f_nom_hz):g} Hz, "
                f"{float(dom.clock.offset_ppm):g} ppm) but the dictionary acquisition domain is {lru} at "
                f"{float(rate):g} Hz ({expect.name}, {float(expect.offset_ppm):g} ppm)"
            )
    return problems


def effective_sigma(sigma: float, regime: np.ndarray, p_tail: float, k_tail: float) -> float:
    """Largest stationary standard deviation of the noise process over the phase multipliers."""
    return float(sigma * float(np.max(regime)) * math.sqrt(1.0 + p_tail * (k_tail * k_tail - 1.0)))


def build_acquisition_config(
    dictionary: Any,
    channels: Sequence[str],
    *,
    sensor_channels: Sequence[str] = (),
    platform: str = "tejas",
    params: Mapping[str, ParamSet] | None = None,
    acq_map: Mapping[str, Any] | None = None,
    config_root: Path | None = None,
) -> AcqConfig:
    """Acquisition tables for ``channels`` (dictionary channel ids).

    Args:
        sensor_channels: the M12 channel list; a channel found there reads M12's ``s_inst``; any other channel
            is an LRU-computed channel recorded from an externally supplied value (A-W1.6-32).
        params / acq_map: overrides of ``M13.yaml`` / ``M13/acquisition_map.yaml`` (tests, proxy mode).
    """
    params = (
        dict(params) if params is not None else load_params("M13", platform=platform, config_root=config_root)
    )
    if acq_map is None:
        acq_map = load_yaml(params_dir(platform, config_root) / "M13" / "acquisition_map.yaml")
    if acq_map.get("format") != MAP_FORMAT:
        raise ContractError(f"acquisition map format must be {MAP_FORMAT}")
    if len(set(channels)) != len(channels) or not channels:
        raise ContractError("acquisition channels must be a non-empty list without duplicates")
    sens = {c: i for i, c in enumerate(sensor_channels)}
    n = len(channels)
    P = np.zeros((n, K.N_AP), dtype=np.float64)
    Q = np.zeros((n, K.N_AQ), dtype=np.int64)
    regime = np.ones((n, K.N_PHASE), dtype=np.float64)
    sig_eff = np.zeros(n)
    ceil_eu = np.zeros(n)
    locs: list[Mapping[str, Any]] = []
    signals: list[str] = []
    dom_key: list[tuple[str, float]] = []
    clocks: dict[tuple[str, float], ClockDomain] = {}
    slips: dict[tuple[str, float], SlipSpec | None] = {}

    def pv(set_name: str, name: str) -> Any:
        if set_name not in params or name not in params[set_name]:
            raise ContractError(f"M13 parameter {set_name}.{name} missing")
        return params[set_name].value(name)

    for c, cid in enumerate(channels):
        did = dictionary_id(cid)  # an engine instance (U3, ``X:Ek``) is acquired as its dictionary channel
        ch = dictionary.channel(did)
        conv = dictionary.eu_conversion(did)
        # a status / discrete / code word (W2.2 word path, A-W2.2-12): the producer's integer word, held, read
        # at the LRU's rate without quantiser, noise or glitch; its full scale is the word's bit width
        word = is_word_channel(dictionary, did)
        qn = 1.0 if word else ch.get("native_step")
        if qn is None or not qn > 0:
            raise ContractError(f"M13 {cid}: no native step (not a numerically acquired channel)")
        lrec = None if word else ch.get("recorder_lsb")
        rng = ch.get("range") or {}
        if word and (rng.get("min") is None or rng.get("max") is None):  # no declared span: the word's bits
            rng = {"min": 0, "max": _word_max(dictionary, ch)}
        if rng.get("min") is None or rng.get("max") is None:
            raise ContractError(f"M13 {cid}: acquisition needs a full-scale range")
        rate = acquisition_rate(dictionary, did)
        if rate is None or not rate > 0:
            raise ContractError(f"M13 {cid}: no periodic acquisition rate")
        lru = acquisition_domain_lru(dictionary, cid)  # the crystal owner, not necessarily acq_lru
        # an LRU converter resolution carried apart from the native step (dictionary 0.1.2, the DASHlink
        # proxy): the native quantiser runs there; otherwise (0.1.3 FADEC lanes included) the native step
        qconv = ch.get("converter_step")
        if qconv is not None and not 0 < float(qconv) <= float(qn):
            raise ContractError(f"M13 {cid}: converter_step {qconv} must be in (0, native_step {qn}]")
        q_acq = float(qconv) if qconv is not None else float(qn)
        hasrec = lrec is not None
        sf = float(lrec) if hasrec else q_acq
        o_n = 0.0  # A-W1.6-30: Tejas native-grid offset
        oset = _rule(acq_map.get("native_offset"), did)
        if oset is not None:  # W2.4a hook: native-grid offset of a recorded word, in recorder LSB (DASHlink)
            if not hasrec:
                raise ContractError(f"M13 {cid}: a native-grid offset needs a recorder lattice")
            o_n = float(pv(oset, "offset_lsb")) * sf
        of = 0.0 if hasrec else o_n
        cmin = _code_bound(float(rng["min"]), sf, of, upper=False)
        cmax = _code_bound(float(rng["max"]), sf, of, upper=True)
        P[c, K.AP_SCALE] = conv.scale
        P[c, K.AP_OFF] = conv.offset
        P[c, K.AP_QN] = q_acq
        P[c, K.AP_ON] = o_n
        P[c, K.AP_SF] = sf
        P[c, K.AP_OF] = of
        Q[c, K.AQ_HASREC] = int(hasrec)
        Q[c, K.AQ_CMIN] = cmin
        Q[c, K.AQ_CMAX] = cmax
        Q[c, K.AQ_MODE] = (
            K.MODE_HOLD if word else (K.MODE_COUNT if ch.get("signal") == "frequency" else K.MODE_POINT)
        )
        signals.append(str(ch.get("signal")))
        # -- noise and its ceiling (a word has neither: its texture is its producer's, A-W2.2-12)
        if not word:
            nset = _rule(acq_map.get("noise"), did)
            if nset is None:
                raise ContractError(f"M13 {cid}: no noise rule matches")
            if nset in params and "sigma_eu" in params[nset]:
                sigma = float(pv(nset, "sigma_eu"))
            elif qconv is not None:
                raise ContractError(
                    f"M13 {cid}: a converter-step channel needs its noise in EU ({nset}.sigma_eu), "
                    "not in steps"
                )
            else:
                sigma = float(pv(nset, "sigma_steps")) * float(qn)
            tau_c = float(pv(nset, "tau_c"))
            phi = math.exp(-1.0 / (rate * tau_c)) if tau_c > 0 else 0.0
            P[c, K.AP_SIGMA] = sigma
            P[c, K.AP_PHI] = phi
            P[c, K.AP_SQ] = math.sqrt(1.0 - phi * phi)
            P[c, K.AP_TAILP] = float(pv(nset, "tail_p"))
            P[c, K.AP_TAILK] = float(pv(nset, "tail_k"))
            reg = np.asarray(pv(nset, "regime_mult"), dtype=np.float64)
            if reg.shape != (K.N_PHASE,) or np.any(reg < 0):
                raise ContractError(f"M13 {nset}.regime_mult must be {K.N_PHASE} non-negative values")
            regime[c] = reg
            sig_eff[c] = effective_sigma(sigma, reg, P[c, K.AP_TAILP], P[c, K.AP_TAILK])
            cset = _rule(acq_map.get("ceiling"), did)
            if cset is None:
                raise ContractError(f"M13 {cid}: no noise-ceiling rule matches")
            ps = params[cset]
            if qconv is not None and "sigma_eu" not in ps:
                raise ContractError(
                    f"M13 {cid}: a converter-step channel needs its noise ceiling in EU ({cset})"
                )
            ceil_eu[c] = (
                float(ps.value("sigma_eu"))
                if "sigma_eu" in ps
                else float(ps.value("sigma_steps")) * float(qn)
            )
            if sig_eff[c] > ceil_eu[c] * (1.0 + 1e-12) + 1e-300:
                raise ContractError(
                    f"M13 {cid}: effective noise sigma {sig_eff[c]:.6g} EU exceeds the measured "
                    f"idiosyncratic ceiling {ceil_eu[c]:.6g} EU ({cset}); W0.5 noise-ceiling rule (A-W1.6-23)"
                )
        # -- gating, deadband, freeze, glitch (none on a word: a glitch would fabricate status bits)
        art = {} if word else acq_map
        gset = _rule(art.get("gate"), did)
        if gset is not None:
            Q[c, K.AQ_GATE] = 1
            P[c, K.AP_GATE] = float(pv(gset, "threshold_eu"))
            Q[c, K.AQ_C0] = min(max(_code_bound(0.0, sf, of, upper=False), cmin), cmax)
        dset = _rule(art.get("deadband"), did)
        if dset is not None:
            P[c, K.AP_DB] = float(pv(dset, "width_eu"))
        fset = _rule(art.get("freeze"), did)
        if fset is not None:
            P[c, K.AP_FRZP] = float(pv(fset, "rate")) / rate
            P[c, K.AP_FRZMIN] = float(pv(fset, "dur_min")) * rate
            P[c, K.AP_FRZMEAN] = float(pv(fset, "dur_mean_excess")) * rate
        glset = _rule(art.get("glitch"), did)
        if glset is not None:
            P[c, K.AP_GLP] = float(pv(glset, "rate")) / rate
        # -- clock domain and slip
        clk_set = (acq_map.get("clocks") or {}).get(lru)
        if clk_set is None:
            raise ContractError(f"M13 {cid}: no clock set for its acquisition domain LRU {lru!r}")
        key = (lru, float(rate))
        if key not in clocks:
            clk = _clock(lru, rate, params[clk_set])
            clocks[key] = clk
            slip = None
            if float(pv(clk_set, "slip_enabled")) > 0.5:
                conv_clk = ClockDomain(
                    f"{lru}@{rate:g}Hz.converter",
                    rate,
                    clk.offset_ppm + Fraction(repr(float(pv(clk_set, "conv_offset_ppm")))),
                    clk.phase_ns,
                )
                slip = SlipSpec(
                    conv_clk, round(float(pv(clk_set, "window")) * 1e9), float(pv(clk_set, "p_in"))
                )
            slips[key] = slip
        if slips[key] is not None and ch.get("signal") == "analog":
            Q[c, K.AQ_SLIP] = 1
            P[c, K.AP_PIN] = slips[key].p_in
        dom_key.append(key)
        locs.append(dictionary.contract_location(did))
    # domains in first-appearance order; analog slip slots spread over one period by channel id
    order: list[tuple[str, float]] = []
    for k_ in dom_key:
        if k_ not in order:
            order.append(k_)
    dom_of = np.array([order.index(k_) for k_ in dom_key], dtype=np.int64)
    slot = np.zeros(n, dtype=np.int64)
    domains = []
    for di, k_ in enumerate(order):
        members = tuple(int(c) for c in np.flatnonzero(dom_of == di))
        slipping = sorted((c for c in members if Q[c, K.AQ_SLIP] == 1), key=lambda c: channels[c])
        per = clocks[k_].period_ns
        for s, c in enumerate(slipping):
            slot[c] = math.floor(per * s / len(slipping))
        domains.append(DomainSpec(clocks[k_].name, k_[0], clocks[k_], members, slips[k_]))
    air = np.zeros(K.N_PHASE, dtype=np.int64)
    air[list(AIRBORNE_PHASES)] = 1
    for a in (P, Q, regime, air, slot, sig_eff, ceil_eu, dom_of):
        a.flags.writeable = False
    cfg = AcqConfig(
        channels=tuple(channels),
        sensor_index=tuple(sens.get(c, -1) for c in channels),
        domains=tuple(domains),
        domain_of=dom_of,
        P=P,
        Q=Q,
        regime=regime,
        airborne=air,
        slot_phase_ns=slot,
        sigma_eff_eu=sig_eff,
        ceiling_eu=ceil_eu,
        location=tuple(locs),
        signals=tuple(signals),
    )
    problems = clock_consistency_problems(dictionary, cfg, params=params, acq_map=acq_map)
    if problems:  # build-time invariant (also tested with a negative control)
        raise ContractError("acquisition clock domains disagree with the dictionary:\n" + "\n".join(problems))
    return cfg
