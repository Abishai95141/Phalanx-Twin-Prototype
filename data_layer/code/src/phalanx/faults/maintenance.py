"""M11 -> M18 hidden-truth events (AD-44): ``truth.fault``, ``truth.fault_clear``, ``truth.incident``.

M18 uses them only to decide outcomes (what troubleshooting finds, whether a ground check reproduces); its
decisions use tech-log knowledge. Payloads use plain top-level keys (AD-48.1) at whole-second times
(:mod:`phalanx.health.protocol`).

Mapping rules [ASSUMPTION A-W1.5-27; SYNTHETIC positions of the W1.8 catalogue]:

- **position**: by mode (:data:`MODE_POSITION`), else by subsystem (:data:`SUBSYSTEM_POSITION`); a triggered
  hydraulic mode takes the system of its trigger (``hyd2`` -> ``HYDP2``). A mode with no maintainable position
  sends no ``truth.fault`` (M18 has nothing to act on; it still sees the BIT records).
- **serial**: the serial M18 installed at that position (``faults.install`` from M10), else the engine serial
  for ``ENG``.
- **symptom**: ``preflight`` for faults found at engine start; ``latent`` when the instance is not covered by
  any detection (missed detection) or has no code and no in-flight consequence; ``both`` for a covered fault
  with an in-flight consequence (shock, transient, discrete); ``bit`` for other covered faults; ``pilot`` for
  an in-flight event with no BIT code.
- **grounding**: true except for intermittent modes.
- **incidents** (:data:`INCIDENTS`): a JFS cold-start failure is a ``start_failure``; the brake-software
  defect and a bird strike are incidents on their positions.
"""

from __future__ import annotations

from collections.abc import Mapping

from phalanx.health.protocol import POSITION_STATES

from .catalogue import FaultMode

__all__ = [
    "INCIDENTS",
    "MODE_POSITION",
    "POSITIONS",
    "START_FAILURES",
    "SUBSYSTEM_POSITION",
    "position_of",
    "symptom_of",
]

POSITIONS: tuple[str, ...] = tuple(POSITION_STATES)

SUBSYSTEM_POSITION: Mapping[str, str] = {
    "engine": "ENG",
    "air_data": "ADC",
    "avionics": "RADAR",
    "electrical": "GEN",
    "hydraulics": "HYDP1",
    "flight_control": "DFCC",
    "fuel": "FQGS",
    "secondary_power": "JFS",
}

#: per-mode positions ("" = no maintainable position)
MODE_POSITION: Mapping[str, str] = {
    "FM.ENG.OIL_STARVATION": "AMAGB",
    "FM.SPS.AMAGB_GEAR_CRACK": "AMAGB",
    "FM.LG.BRAKE_SW_CONFIG": "BCU",
    "FM.LG.DOWNLOCK_FORCE": "",
    "FM.FCS.POOR_LUBE": "",
    "FM.HYD.ISA_CHECK_VALVE": "",
    "FM.HYD.WATER_CONTAMINATION": "",
    "FM.ELEC.PARTIAL_POWER_LOSS": "",
    "FM.SNS.GENERIC": "",
    "FM.FCS.ACTUATOR_JAM": "",
    "FM.FCS.SERVO_COIL": "",
}

#: mode -> (incident kind, positions)
INCIDENTS: Mapping[str, tuple[str, tuple[str, ...]]] = {
    "FM.SPS.JFS_COLD_START_FAIL": ("start_failure", ("JFS",)),
    "FM.LG.BRAKE_SW_CONFIG": ("excursion", ("TYR_L", "TYR_R", "BRK_L", "BRK_R")),
    "FM.ENG.FOD_BIRD": ("bird_strike", ("ENG",)),
}

_PREFLIGHT = frozenset({"FM.SPS.JFS_COLD_START_FAIL", "FM.ENG.HUNG_START", "FM.ENG.HOT_START"})
#: AD-49: modes that fail the engine start (found at engine start, before take-off): M11 reports them to M02
#: (``ops.start_failure``), which ground-aborts the sortie if it has not taken off
START_FAILURES = _PREFLIGHT
_IN_FLIGHT = frozenset({"shock", "transient", "discrete"})


def position_of(mode: FaultMode, key: str = "") -> str:
    """The M18 position of an instance of ``mode`` ("" if none)."""
    pos = MODE_POSITION.get(mode.id, SUBSYSTEM_POSITION.get(mode.subsystem, ""))
    if pos == "HYDP1" and "hyd2" in key:
        pos = "HYDP2"
    return pos


def symptom_of(mode: FaultMode, covered: bool) -> str:
    """How the fault shows itself to the maintenance organisation (M18 vocabulary)."""
    if mode.id in _PREFLIGHT:
        return "preflight"
    if mode.codes:
        if not covered:
            return "latent"
        return "both" if mode.cls in _IN_FLIGHT else "bit"
    return "pilot" if mode.cls in _IN_FLIGHT else "latent"
