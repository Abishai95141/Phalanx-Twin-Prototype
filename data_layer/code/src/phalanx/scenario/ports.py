"""M02 published ports (W1_interfaces.md §2 M02; configs/interfaces/w1_ports.yaml) and cross-module events
(AD-44; configs/interfaces/w1_events.yaml; checked by tests/integration/test_event_protocol.py)."""

from __future__ import annotations

from phalanx.core.module import Port

PREFIX = "scenario"
MODULE_IDS = ("M02",)
#: ``scenario.sortie_plan`` keys (``SortiePlan.to_payload``, phalanx.scenario.plan; ``summary`` is optional)
PLAN_KEYS = (
    "sortie_id",
    "rng_key",
    "tail",
    "squadron",
    "base",
    "field_elev_m",
    "mission_type",
    "pilot_id",
    "night",
    "t_start_utc_ns",
    "t_kernel0_ns",
    "engine_serials",
    "drop_tanks",
    "fuel_kg",
    "t_off_ns",
    "seg_f",
    "seg_i",
    "t_end_off_ns",
    "ambient",
    "pilot_traits",
    "duration_s",
    "chute",
)

#: produced cross-module events {kind: payload keys} (operations mode; module.py docstring)
EVENTS_OUT: dict[str, tuple[str, ...]] = {
    "ops.offer_request": ("day", "reply_to"),
    "ops.launch": ("sortie_id", "tail_no", "reply_to"),
    "ops.ground_abort": ("tail_no", "sortie_id"),
    "ops.power_up": ("tail_no", "sortie_id", "engine_starts", "cold_soak"),
    "ops.sortie_done": (
        "sortie_id",
        "tail_no",
        "t_takeoff",
        "t_landing",
        "flight_hours",
        "landings",
        "engine_cycles",
        "engine_starts",
        "chute_streamed",
        "mission_type",
        "crew_id",
        "aborted",
    ),
    "usage.sortie_summary": (
        "sortie_id",
        "tail_no",
        "flight_hours",
        "engine_cycles",
        "engine_starts",
        "landings",
        "time_at_temp_s",
        "max_nz",
        "ab_time_s",
        "dust_index",
        "salt_index",
        "engine_serials",
        "ground_run",
        "t_end",
        "eot_s",
        "ab_lights",
        "type1",
        "type3",
        "type4",
        "nz_exceed",
        "chute_streamed",
        "exposure_h",
    ),
    "m18.disruption": ("cls", "factor", "t0", "t1"),
    # AD-49: the sortie plan to M03 / M04 (SortiePlan.to_payload; + summary in usage mode) and the day's
    # flying task to the record sink
    "scenario.sortie_plan": PLAN_KEYS,
    "kpi.plan": ("t_utc", "date", "planned_sorties", "planned_fh"),
    # AD-48.2: at the actual take-off (operations mode: the committed sortie's; sortie mode: the plan's)
    "ops.takeoff": (
        "sortie_id",
        "tail_no",
        "t_takeoff",
        "t_landing",
        "ab_lights",
        "engine_starts",
        "landings",
        "dust_index",
    ),
    # M09 (AD-49 fill-to-target): planned fuel per M09 tank and the fuel temperature (scenario/refuel.py)
    "util.refuel": ("tail", "tank", "target_kg", "t_fuel"),
    # AD-47, flat payloads, at the sortie (or ground-run) start: field elevation to M06, power-up BIT to M05
    "af.ground_elevation": ("tail", "h"),
    "fcs.pbit_start": ("tail",),
}

#: consumed cross-module events {kind: payload keys the handler reads}
EVENTS_IN: dict[str, tuple[str, ...]] = {
    "ops.offer": ("day", "tails", "restrict"),
    "ops.launch_denied": ("sortie_id", "tail_no", "reason"),
    "ops.assign": ("tail_no", "order_id", "date", "sorties", "mission_type"),
    "ops.restrict": ("tail_no", "limit", "value", "until_days"),
    # AD-49: a start failure before take-off ground-aborts the sortie
    "ops.start_failure": ("tail_no", "sortie_id", "mode"),
    # W2.1a take-off fix (A-W2.1-9): the pilot's segment in force (sortie mode with a segment source)
    "pilot.segment": ("tail", "segment", "fine"),
}


def ports(n_engines: int = 1) -> tuple[tuple[Port, ...], tuple[Port, ...], dict[str, str]]:
    """(inputs, outputs, bindings). M02 is event-driven: no inputs; ``sortie_plan`` is an event."""
    if n_engines < 1:
        raise ValueError("n_engines >= 1")
    outputs = (
        Port("epoch_utc_ns", "ns", "<i8"),  # AD-38: contract time = epoch + kernel t
        Port("phase", "1", "<i8"),  # dictionary flight_phase code (held)
    )
    return (), outputs, {}


def replay_ports(n_engines: int = 1) -> tuple[tuple[Port, ...], tuple[Port, ...]]:
    """``scenario.replay.ScenarioReplay`` (proxy mode, W2.4a U4): the M02 outputs served from a record."""
    _, outs, _ = ports(n_engines)
    return (), outs
