"""M02 phase grammar codes and their mapping onto the dictionary ``flight_phase`` code table.

AD-28 layer 3 (report §4 "Phase grammar"): a fixed opening (power-up -> start -> idle -> taxi -> take-off ->
climb), mission blocks, and a fixed closing (RTB -> pattern, optional touch-and-go loops -> landing -> taxi ->
optional hot refuel -> shutdown).

``scenario.phase`` (W1_interfaces §2 M02) carries the **dictionary** code (`configs/tejas/dictionary/tables/
code_tables.yaml` ``flight_phase``). That table currently holds the DASHlink PH codes 0-7 ("fighter-specific
phases are added by W1.1 if needed"); the dictionary is coordinator-owned in W1, so the fighter phases are a
**dictionary change request** (W1.1 report). Each fine phase lists its preferred dictionary name first and
the existing fallback second; the mapping upgrades automatically when the proposed names are released.
"""

from __future__ import annotations

from functools import lru_cache

# fine phase codes (M02 internal; part of the sortie-plan payload)
PREFLIGHT, ENGINE_START, GROUND_IDLE, TAXI_OUT, RUNUP, TAKEOFF, CLIMB = 1, 2, 3, 4, 5, 6, 7
TRANSIT, MISSION, DESCENT, PATTERN, APPROACH, LANDING, TOUCH_AND_GO = 8, 9, 10, 11, 12, 13, 14
TAXI_IN, HOT_REFUEL, SHUTDOWN, POSTFLIGHT, GROUND_RUN = 15, 16, 17, 18, 19

FINE_NAMES: dict[int, str] = {
    PREFLIGHT: "PREFLIGHT",
    ENGINE_START: "ENGINE_START",
    GROUND_IDLE: "GROUND_IDLE",
    TAXI_OUT: "TAXI_OUT",
    RUNUP: "RUNUP",
    TAKEOFF: "TAKEOFF",
    CLIMB: "CLIMB",
    TRANSIT: "TRANSIT",
    MISSION: "MISSION",
    DESCENT: "DESCENT",
    PATTERN: "PATTERN",
    APPROACH: "APPROACH",
    LANDING: "LANDING",
    TOUCH_AND_GO: "TOUCH_AND_GO",
    TAXI_IN: "TAXI_IN",
    HOT_REFUEL: "HOT_REFUEL",
    SHUTDOWN: "SHUTDOWN",
    POSTFLIGHT: "POSTFLIGHT",
    GROUND_RUN: "GROUND_RUN",
}

#: preferred dictionary name(s) per fine phase, most specific first; the last is in dictionary 0.1.x
DICTIONARY_NAMES: dict[int, tuple[str, ...]] = {
    PREFLIGHT: ("PREFLIGHT",),
    ENGINE_START: ("ENGINE_START", "PREFLIGHT"),
    GROUND_IDLE: ("PREFLIGHT",),
    TAXI_OUT: ("TAXI",),
    RUNUP: ("TAXI",),
    TAKEOFF: ("TAKEOFF",),
    CLIMB: ("CLIMB",),
    TRANSIT: ("CRUISE",),
    MISSION: ("MISSION", "CRUISE"),
    DESCENT: ("DESCENT", "APPROACH"),
    PATTERN: ("PATTERN", "APPROACH"),
    APPROACH: ("APPROACH",),
    LANDING: ("ROLLOUT",),
    TOUCH_AND_GO: ("TOUCH_AND_GO", "APPROACH"),
    TAXI_IN: ("TAXI",),
    HOT_REFUEL: ("HOT_REFUEL", "TAXI"),
    SHUTDOWN: ("SHUTDOWN", "TAXI"),
    POSTFLIGHT: ("UNKNOWN",),
    GROUND_RUN: ("GROUND_RUN", "PREFLIGHT"),
}

#: airborne fine phases (engine flight time is counted take-off to landing)
AIRBORNE = frozenset({CLIMB, TRANSIT, MISSION, DESCENT, PATTERN, APPROACH})

#: dictionary change request (W1.1 report): fighter phases proposed for the flight_phase code table
PROPOSED_DICTIONARY_CODES: dict[int, str] = {
    8: "ENGINE_START",
    9: "MISSION",
    10: "DESCENT",
    11: "PATTERN",
    12: "TOUCH_AND_GO",
    13: "SHUTDOWN",
    14: "GROUND_RUN",
    15: "HOT_REFUEL",
}


@lru_cache(maxsize=4)
def _phase_table(platform: str = "tejas") -> dict[str, int]:
    from phalanx.dictionary import load_dictionary

    codes = load_dictionary(platform=platform).code_table("flight_phase")["codes"]
    return {str(name): int(code) for code, name in codes.items()}


def dictionary_phase_code(name: str, platform: str = "tejas") -> int:
    """Code of a ``flight_phase`` name in the current dictionary (KeyError if absent)."""
    return _phase_table(platform)[name]


def fine_to_dictionary(fine: int, platform: str = "tejas") -> int:
    """Dictionary ``flight_phase`` code for a fine phase (first preferred name present)."""
    table = _phase_table(platform)
    for name in DICTIONARY_NAMES[fine]:
        if name in table:
            return table[name]
    raise KeyError(f"no dictionary flight_phase code for fine phase {FINE_NAMES[fine]}")


def dictionary_map(platform: str = "tejas") -> dict[int, int]:
    """fine code -> dictionary code for every fine phase."""
    return {k: fine_to_dictionary(k, platform) for k in FINE_NAMES}
