"""M08 code tables: limiter codes, validation states, AB/start states, ignition bits, synthetic fault codes.

Everything here is a **SYNTHETIC Phalanx construct** (AD-19; RULES.md rule 6). The codes are never claimed to
be the real IN20 FADEC codes.

**Fault codes are the dictionary's unified BIT/fault code table** (dictionary 0.1.2 ``code_tables.bit_codes``,
AD-48 item 5; ``Dictionary.bit_codes()``), re-keyed from M08's W1.3b list through the dictionary's legacy map
(``Dictionary.translate_bit_code(code, "M08")``): every ``FaultCode`` keeps its W1.3b code as ``legacy``, and
``tests/unit/test_fadec_codes.py`` ties the table to the dictionary (every code exists, every legacy code
translates to it, lanes and sensors agree). The W1.3b list reused numbers with other meanings than M14's (e.g.
legacy ENG-501 was the flameout, unified ENG-501 is the compressor stall); events and the ENG.FAULT_CODES word
now carry unified codes only.

The remaining tables (limiter codes, validation states, AB/start states, ignition bits) are proposed for the
dictionary as `fadec_active_limiter`, `fadec_validation_state`, `fadec_ab_state` and `fadec_ignition_bits`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# ------------------------------------------------------------------ validated engine sensors (order of `ns`)
#: sensor order of `fadec.validation_state` [e, ns] and of every per-sensor array in M08
SENSORS: tuple[str, ...] = ("N1", "N2", "T1", "T25", "PS3", "T5")
S_N1, S_N2, S_T1, S_T25, S_PS3, S_T5 = range(6)
NS = len(SENSORS)

# ------------------------------------------------------------------ validation state (per sensor, per frame)
V_OK = 0  # lanes valid and agreeing (dual: averaged)
V_SUSPECT = 1  # soft-fail: cross-channel disagreement (safer lane used) or one lane lost (other lane used)
V_FAILED = 2  # no valid lane and no substitution (holding the last good value)
V_SUBSTITUTED = (
    3  # on-board model value in use (analytical-check failure, or lanes lost and substitution allowed)
)
VALIDATION_STATE = {V_OK: "OK", V_SUSPECT: "SUSPECT", V_FAILED: "FAILED", V_SUBSTITUTED: "SUBSTITUTED"}

# ------------------------------------------------------------------ fuel-path regulator selected by MIN/MAX
L_FUEL_OFF = 0  # fuel shut off (PLA below cutoff, or N2 below the ignition permissive while starting)
L_GOV_N2 = 1  # N2 governor (below IRP: N2c scheduled on PLA/T25; or the proxy autothrottle demand)
L_N1 = 2  # N1 isochronous governor / limiter vs T1 with the 104.4 % corrected cap (at and above IRP)
L_N2MAX = 3  # N2 overspeed limiter
L_T5 = 4  # T5 fuel limiter (backup to the A8 T5 loop)
L_PS3MAX = 5  # PS3 maximum limiter
L_ACCEL = 6  # acceleration Wf/PS3 schedule
L_DECEL = 7  # deceleration Wf/PS3 schedule
L_PS3MIN = 8  # PS3 minimum (optional; governor branch below IRP, under the MIN protection limiters)
L_WFMIN = 9  # absolute minimum fuel flow clamp
L_WFMAX = 10  # absolute maximum fuel flow clamp
L_START_NDOT = 11  # sub-idle start/relight N2-rate governor (DEEC-style airstart logic)
FUEL_LIMITER = {
    L_FUEL_OFF: "FUEL_OFF",
    L_GOV_N2: "GOV_N2",
    L_N1: "N1_ISOCHRONOUS",
    L_N2MAX: "N2_MAX",
    L_T5: "T5_FUEL",
    L_PS3MAX: "PS3_MAX",
    L_ACCEL: "ACCEL_WF_PS3",
    L_DECEL: "DECEL_WF_PS3",
    L_PS3MIN: "PS3_MIN",
    L_WFMIN: "WF_MIN",
    L_WFMAX: "WF_MAX",
    L_START_NDOT: "START_N2DOT",
}
#: `fadec.active_limiter` = fuel code (bits 0-3) + NOZZLE_T5_BIT if the A8 T5 loop holds the nozzle
#: above its floor
NOZZLE_T5_BIT = 16


def decode_active_limiter(code: int) -> tuple[str, bool]:
    """(fuel regulator name, nozzle T5 loop active) of an `active_limiter` value."""
    return FUEL_LIMITER[int(code) & 15], bool(int(code) & NOZZLE_T5_BIT)


# ------------------------------------------------------------------ afterburner sequence
AB_OFF, AB_PREOPEN, AB_LIGHTING, AB_LIT, AB_RETRY_WAIT, AB_LOCKOUT = range(6)
AB_STATE = {
    AB_OFF: "OFF",
    AB_PREOPEN: "PREOPEN",
    AB_LIGHTING: "LIGHTING",
    AB_LIT: "LIT",
    AB_RETRY_WAIT: "RETRY_WAIT",
    AB_LOCKOUT: "LOCKOUT",
}

# ------------------------------------------------------------------ start / run state
ST_SHUTDOWN, ST_STARTING, ST_RUNNING = range(3)
START_STATE = {ST_SHUTDOWN: "SHUTDOWN", ST_STARTING: "STARTING", ST_RUNNING: "RUNNING"}

# ------------------------------------------------------------------ `fadec.ignition` bits
IGN_MAIN = 1  # main igniters (start window or flameout auto-relight)
IGN_AB = 2  # afterburner igniter (light-off sequence)

# ------------------------------------------------------------------ accommodation flags (int state, bitmask)
ACC_AB_INHIBIT = 1
ACC_N2_REDUCED = 2  # N2 limit reduced by ~1,000 rpm
ACC_ACT_SAFE = 4  # nozzle forced to its safe (floor + open bias) position; T5 loop off
ACC_REVERSION = 8  # second like failure: part-power reversion


# ------------------------------------------------------------------ fault bits -> unified codes
#: W1.3b (legacy) M08 code -> unified dictionary code: dictionary 0.1.2 ``bit_codes.legacy.M08`` (tie-tested)
LEGACY_TO_UNIFIED: dict[str, str] = {
    "ENG-011": "ENG-001", "ENG-012": "ENG-003", "ENG-013": "ENG-009", "ENG-014": "ENG-014",
    "ENG-015": "ENG-007", "ENG-016": "ENG-005", "ENG-021": "ENG-002", "ENG-022": "ENG-004",
    "ENG-023": "ENG-010", "ENG-024": "ENG-024", "ENG-025": "ENG-008", "ENG-026": "ENG-006",
    "ENG-031": "ENG-031", "ENG-032": "ENG-032", "ENG-033": "ENG-033", "ENG-034": "ENG-034",
    "ENG-035": "ENG-035", "ENG-036": "ENG-036", "ENG-041": "ENG-041", "ENG-042": "ENG-042",
    "ENG-043": "ENG-043", "ENG-044": "ENG-044", "ENG-045": "ENG-045", "ENG-046": "ENG-046",
    "ENG-051": "ENG-051", "ENG-052": "ENG-052", "ENG-053": "ENG-053", "ENG-054": "ENG-054",
    "ENG-055": "ENG-055", "ENG-056": "ENG-056", "ENG-501": "ENG-502", "ENG-502": "ENG-504",
    "ENG-503": "ENG-501", "ENG-504": "ENG-506", "ENG-505": "ENG-503", "ENG-506": "ENG-509",
    "ENG-507": "ENG-510", "ENG-508": "ENG-508", "ENG-701": "ENG-701", "ENG-702": "ENG-702",
    "ENG-703": "ENG-703",
}  # fmt: skip


@dataclass(frozen=True)
class FaultCode:
    bit: int
    code: str  # unified dictionary code (bit_codes, SSS-NNN; AD-19 synthetic)
    kind: str  # event kind: "fadec.fault" (BIT/function code) or "fadec.caution" (caution discrete)
    sensor: str  # sensor name or "" for function monitors
    lane: str  # "A", "B" or ""
    description: str
    legacy: str  # the W1.3b M08 code (traceability; never emitted)


def _fc(bit: int, legacy: str, kind: str, sensor: str, lane: str, description: str) -> FaultCode:
    return FaultCode(bit, LEGACY_TO_UNIFIED[legacy], kind, sensor, lane, description, legacy)


def _sensor_codes() -> list[FaultCode]:
    out = []
    for s, name in enumerate(SENSORS):
        out.append(_fc(s, f"ENG-{11 + s:03d}", "fadec.fault", name, "A", f"{name} lane A failed"))
        out.append(_fc(6 + s, f"ENG-{21 + s:03d}", "fadec.fault", name, "B", f"{name} lane B failed"))
        out.append(
            _fc(12 + s, f"ENG-{31 + s:03d}", "fadec.fault", name, "", f"{name} cross-channel soft-fail")
        )
        out.append(
            _fc(
                18 + s,
                f"ENG-{41 + s:03d}",
                "fadec.fault",
                name,
                "",
                f"{name} analytical fail, model substituted",
            )
        )
        out.append(_fc(24 + s, f"ENG-{51 + s:03d}", "fadec.fault", name, "", f"{name} signal fail (no lane)"))
    return out


B_FLAMEOUT = 30
B_HUNG_START = 31
B_STALL = 32
B_SUBIDLE = 33
B_AB_NOLIGHT = 34
B_AB_LOCKOUT = 35
B_AB_BLOWOUT = 36
B_REVERSION = 37
B_OVERTEMP = 38
B_N1_OVERSPEED = 39
B_N2_OVERSPEED = 40

FAULT_CODES: tuple[FaultCode, ...] = (
    *_sensor_codes(),
    _fc(B_FLAMEOUT, "ENG-501", "fadec.caution", "", "", "Flameout detected, auto-relight active"),
    _fc(B_HUNG_START, "ENG-502", "fadec.caution", "", "", "Hung start / hung relight"),
    _fc(B_STALL, "ENG-503", "fadec.caution", "", "", "Compressor stall detected"),
    _fc(B_SUBIDLE, "ENG-504", "fadec.caution", "", "", "Sub-idle (N2 below run threshold, fuel on)"),
    _fc(B_AB_NOLIGHT, "ENG-505", "fadec.fault", "", "", "Afterburner no-light"),
    _fc(B_AB_LOCKOUT, "ENG-506", "fadec.caution", "", "", "Afterburner failed: retries exhausted"),
    _fc(B_AB_BLOWOUT, "ENG-507", "fadec.fault", "", "", "Afterburner blowout"),
    _fc(B_REVERSION, "ENG-508", "fadec.caution", "", "", "Control reversion (second like failure)"),
    _fc(B_OVERTEMP, "ENG-701", "fadec.caution", "", "", "T5 over-temperature"),
    _fc(B_N1_OVERSPEED, "ENG-702", "fadec.caution", "", "", "N1 overspeed"),
    _fc(B_N2_OVERSPEED, "ENG-703", "fadec.caution", "", "", "N2 overspeed"),
)
FAULT_BY_BIT = {f.bit: f for f in FAULT_CODES}
N_FAULT_BITS = max(FAULT_BY_BIT) + 1
assert N_FAULT_BITS <= 63 and len(FAULT_BY_BIT) == len(FAULT_CODES)
assert len({f.code for f in FAULT_CODES}) == len(FAULT_CODES)
assert len(LEGACY_TO_UNIFIED) == len(FAULT_CODES) == len({f.legacy for f in FAULT_CODES})


def bit_sensor_lane_fail(s: int, lane: int) -> int:
    return s + 6 * lane


def bit_xc(s: int) -> int:
    return 12 + s


def bit_analytic(s: int) -> int:
    return 18 + s


def bit_signal_fail(s: int) -> int:
    return 24 + s


def active_codes(mask: int) -> list[str]:
    """Synthetic codes of the bits set in a fault bitmask (ascending bit order)."""
    return [FAULT_BY_BIT[b].code for b in sorted(FAULT_BY_BIT) if (int(mask) >> b) & 1]


# ------------------------------------------------------------------ recorded discrete words (AD-42 RECORDED)
# Bit layouts are the dictionary encodings (configs/tejas/dictionary/sources/engine.yaml, synthetic ICD):
#   ENG.IGN          bit 0 IGNITION_ON (main igniters)
#   ENG.FLAMEOUT     bit 0 FLAMEOUT_DETECTED, bit 1 AUTO_RELIGHT_ACTIVE
#   ENG.LIMIT_FLAGS  bit 0 N1_OVERSPEED, bit 1 N2_OVERSPEED, bit 2 T5_OVERTEMP; bits 3 OIL_PRESSURE_LOW and
#                    4 VIBRATION_HIGH are not M08 monitors (left 0; merged downstream, see README)
#   ENG.FADEC_STATUS bit 0 CH_A_IN_CONTROL, bit 1 CH_B_IN_CONTROL, bit 2 CH_A_FAIL, bit 3 CH_B_FAIL,
#                    bit 4 SENSOR_SUBSTITUTION_ACTIVE (one control channel modelled: A always in control)
#   ENG.FAULT_CODES  16-bit code word (format SSS-NNN, prefixes ENG/ECM): 1000 * prefix index + NNN of the
#                    highest-priority active unified code (exceedance 7xx > function 5xx > sensor 0xx, then
#                    the lowest number); 0 = no active code. EU value convention of A-W1.7-6 (k << 10 | NNN;
#                    Dictionary.code_word_eu); the priority rule is M08's proposal.
CODE_PREFIXES = ("ENG", "ECM")


def _code_value(code: str) -> int:
    pre, num = code.split("-")
    return 1000 * CODE_PREFIXES.index(pre) + int(num)


def _block_rank(code: str) -> int:
    n = int(code.split("-")[1])
    return 0 if n >= 700 else (1 if n >= 500 else 2)


#: fault bits in fault-code-word priority order
CODE_WORD_ORDER: tuple[int, ...] = tuple(
    f.bit for f in sorted(FAULT_CODES, key=lambda f: (_block_rank(f.code), int(f.code.split("-")[1])))
)


def code_word(mask) -> np.ndarray:
    """ENG.FAULT_CODES word(s) of fault bitmask(s) (any shape; int64)."""
    m = np.asarray(mask, dtype=np.int64)
    out = np.zeros(m.shape, dtype=np.int64)
    done = np.zeros(m.shape, dtype=bool)
    for b in CODE_WORD_ORDER:
        on = ((m >> b) & 1).astype(bool) & ~done
        out[on] = _code_value(FAULT_BY_BIT[b].code)
        done |= on
    return out


def recorded_words(ignition, faults, vstate) -> dict[str, np.ndarray]:
    """The FADEC discrete words of the recorded channels from the kernel outputs.

    ignition, faults: int arrays [...]; vstate: int array [..., NS]. Returns int64 arrays [...] keyed by
    dictionary channel id.
    """
    ign = np.asarray(ignition, dtype=np.int64)
    f = np.asarray(faults, dtype=np.int64)
    vs = np.asarray(vstate, dtype=np.int64)
    main = (ign & IGN_MAIN) != 0
    fo = ((f >> B_FLAMEOUT) & 1) != 0

    def bit(b):
        return (f >> b) & 1

    return {
        "ENG.IGN": main.astype(np.int64),
        "ENG.FLAMEOUT": fo.astype(np.int64) | ((fo & main).astype(np.int64) << 1),
        "ENG.LIMIT_FLAGS": bit(B_N1_OVERSPEED) | (bit(B_N2_OVERSPEED) << 1) | (bit(B_OVERTEMP) << 2),
        "ENG.FADEC_STATUS": np.ones(f.shape, dtype=np.int64)
        | ((vs == V_SUBSTITUTED).any(axis=-1).astype(np.int64) << 4),
        "ENG.FAULT_CODES": code_word(f),
    }


__all__ = [
    "AB_STATE",
    "ACC_AB_INHIBIT",
    "ACC_ACT_SAFE",
    "ACC_N2_REDUCED",
    "ACC_REVERSION",
    "CODE_PREFIXES",
    "CODE_WORD_ORDER",
    "FAULT_BY_BIT",
    "FAULT_CODES",
    "FUEL_LIMITER",
    "IGN_AB",
    "IGN_MAIN",
    "LEGACY_TO_UNIFIED",
    "NOZZLE_T5_BIT",
    "NS",
    "SENSORS",
    "START_STATE",
    "VALIDATION_STATE",
    "FaultCode",
    "active_codes",
    "code_word",
    "decode_active_limiter",
    "recorded_words",
]
