"""Fault-mode catalogue as data (``configs/tejas/faults/catalogue.yaml``; architecture §6 M11, §9.2–§9.3,
AD-18).

Each mode says *what physical state changes* (effects), *how it starts* (onset process), *where its cascade
starts* (graph root) and *which BIT codes can see it* (detection with a coverage probability). It never says
what an observation looks like: observations come from the physics and monitoring (invariant I6).

**Validation status (AD-55, W2.5; format ``phalanx.fault_catalogue/2``):** every mode carries
``validation: {status, ...}``. The priority set (about ten maintenance-relevant faults, AD-55 item 3) is
``validated``: its B7 signature and progression checks were run in depth (``checks``: the B7 ids of
``analysis/faults_b7b8/``, with the literature anchor in ``evidence``); a validated mode's checks are
reported with their verdicts, PASS or FAIL. Every other mode is ``unvalidated`` with a ``reason`` that starts
with ``unvalidated (AD-55)``. The label-leak audit and G0 cover every mode whatever its status.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from phalanx.core.module import EvidenceTag
from phalanx.dictionary.yamlio import load_yaml

__all__ = [
    "CATALOGUE_FORMAT",
    "CLASSES",
    "EFFECT_TARGETS",
    "ONSET_PROCESSES",
    "SENSOR_MODES",
    "UNVALIDATED_PREFIX",
    "VALIDATION_STATUSES",
    "Effect",
    "FaultMode",
    "load_catalogue",
    "priority_set",
]

CATALOGUE_FORMAT = "phalanx.fault_catalogue/2"
#: AD-55 validation status of a mode (W2.5)
VALIDATION_STATUSES = ("validated", "unvalidated")
#: every unvalidated mode's reason starts with this (catalogue hygiene, W2.5 deliverable 7)
UNVALIDATED_PREFIX = "unvalidated (AD-55)"

CLASSES = ("degradation", "shock", "transient", "sensor", "discrete", "intermittent", "latent", "physics")
ONSET_PROCESSES = ("m10", "physics", "poisson", "per_event", "markov", "latent", "triggered", "scripted")
EFFECT_TARGETS = ("health", "sensors", "monitoring", "engine", "fadec", "utilities", "fcs", "airframe")
#: sensor-fault modes M12 applies at s_inst (architecture §7; AD-42 payload; "*" = given by the order)
SENSOR_MODES = (
    "bias",
    "drift",
    "stuck",
    "intermittent",
    "spikes",
    "open",
    "short",
    "slow",
    "probe_open",
    "probe_short",
    "*",
)
#: fields of a sensors effect (see ``FaultInjector._sensor_events`` for units)
SENSOR_FIELDS = ("channel", "mode", "magnitude", "rate_per_s", "rate", "duty", "probe", "factor", "level")
#: modes of the catalogued ``util.fault`` event (M11 -> M09, AD-44) a fault can start
UTIL_FAULT_MODES = ("gen_fail", "bk_fail", "fire_onset", "fire_loop_open", "fire_loop_short")
#: AD-47 events a fault can send to M05
FCS_EVENTS = ("channel_fault", "actuator_fault", "wow_fault")
PER_EVENT_DRIVERS = ("ab_lights", "starts", "cold_jfs_starts", "landings")
_REPO = Path(__file__).resolve().parents[3]
CATALOGUE_PATH = _REPO / "configs" / "tejas" / "faults" / "catalogue.yaml"


class CatalogueError(ValueError):
    pass


def _check_fcs(mid: str, e: Mapping[str, object]) -> None:
    """An fcs effect names an AD-47 event with fields M05 accepts (subsystem names from M05's layout)."""
    from phalanx.fcs.layout import SUBSYSTEMS

    ev = e.get("event")
    if ev not in FCS_EVENTS:
        raise CatalogueError(f"{mid}: fcs event {ev!r} not in {FCS_EVENTS} (AD-47)")
    if ev == "channel_fault" and e.get("subsystem") not in SUBSYSTEMS:
        raise CatalogueError(f"{mid}: unknown DFCC subsystem {e.get('subsystem')!r}")
    if ev == "actuator_fault" and e.get("mode") not in ("jam", "servo"):
        raise CatalogueError(f"{mid}: actuator fault mode must be jam or servo")
    if ev == "wow_fault" and (not e.get("legs") or e.get("value") not in (0, 1)):
        raise CatalogueError(f"{mid}: wow fault needs legs and a value of 0 or 1")


def airframe_effect_errors(e: Mapping[str, object]) -> list[str]:
    """An airframe effect (``af.fault_inject``, AD-48.4) names an M06 fault mode and a valid gear-leg spec."""
    from phalanx.airframe.kernel import AF_FAULT_MODES

    errs = []
    if e.get("mode") not in AF_FAULT_MODES:
        errs.append(f"airframe mode {e.get('mode')!r} not in M06's {AF_FAULT_MODES}")
    legs = e.get("legs")
    if legs is not None and (
        not isinstance(legs, list) or not legs or any(x not in (0, 1, 2) for x in legs) or "leg" in e
    ):
        errs.append(f"airframe legs {legs!r} must be a non-empty list of 0/1/2 (and no 'leg')")
    leg = e.get("leg", -1)
    if leg not in (-1, 0, 1, 2, "*", "key"):
        errs.append(f"airframe leg {leg!r} must be -1, 0, 1, 2, '*' or 'key'")
    return errs


@dataclass(frozen=True)
class Effect:
    target: str
    fields: Mapping[str, object]


@dataclass(frozen=True)
class FaultMode:
    id: str
    name: str
    subsystem: str
    cls: str
    nm_ref: str | None
    onset: Mapping[str, object]
    severity: Mapping[str, object]
    duration_s: float
    graph_root: str | None
    effects: tuple[Effect, ...]
    codes: tuple[str, ...]
    coverage: float
    refs: tuple[str, ...]
    signature: str
    evidence: Mapping[str, str]
    validation: Mapping[str, object]

    @property
    def validated(self) -> bool:
        """In the AD-55 priority set: B7/B8 run in depth (``validation.checks``)."""
        return self.validation.get("status") == "validated"

    @property
    def process(self) -> str:
        return str(self.onset["process"])

    def effects_fields(self) -> tuple[tuple[str, Mapping[str, object]], ...]:
        return tuple((e.target, e.fields) for e in self.effects)

    @property
    def injectable(self) -> bool:
        return self.process not in ("m10", "physics")


def _mode(mid: str, d: Mapping) -> FaultMode:
    def need(k: str):
        if k not in d:
            raise CatalogueError(f"{mid}: missing {k!r}")
        return d[k]

    allowed = {
        "name",
        "subsystem",
        "class",
        "nm_ref",
        "onset",
        "severity",
        "duration_s",
        "graph_root",
        "effects",
        "detection",
        "refs",
        "signature",
        "evidence",
        "validation",
    }
    extra = set(d) - allowed
    if extra:
        raise CatalogueError(f"{mid}: unknown keys {sorted(extra)}")
    cls = need("class")
    if cls not in CLASSES:
        raise CatalogueError(f"{mid}: class {cls!r} not in {CLASSES}")
    onset = dict(need("onset"))
    if onset.get("process") not in ONSET_PROCESSES:
        raise CatalogueError(f"{mid}: onset process {onset.get('process')!r} not in {ONSET_PROCESSES}")
    if onset["process"] == "per_event" and onset.get("driver") not in PER_EVENT_DRIVERS:
        raise CatalogueError(f"{mid}: per_event driver must be one of {PER_EVENT_DRIVERS}")
    effects = []
    for e in d.get("effects", []):
        t = e.get("target")
        if t not in EFFECT_TARGETS:
            raise CatalogueError(f"{mid}: effect target {t!r} not in {EFFECT_TARGETS}")
        if t == "sensors" and e.get("mode") not in SENSOR_MODES:
            raise CatalogueError(f"{mid}: sensor mode {e.get('mode')!r} not in {SENSOR_MODES}")
        if t == "sensors" and set(e) - {"target", *SENSOR_FIELDS}:
            raise CatalogueError(
                f"{mid}: unknown sensor-effect fields {sorted(set(e) - {'target', *SENSOR_FIELDS})}"
            )
        if t == "health" and not isinstance(e.get("state"), str):
            raise CatalogueError(f"{mid}: health effect needs a state")
        if t == "fcs":
            _check_fcs(mid, e)
        if t == "utilities" and e.get("mode") not in UTIL_FAULT_MODES:
            raise CatalogueError(
                f"{mid}: util.fault mode {e.get('mode')!r} not in {UTIL_FAULT_MODES} (AD-44)"
            )
        if t == "monitoring" and not isinstance(e.get("code"), str):
            raise CatalogueError(f"{mid}: monitoring effect needs a code")
        if t == "airframe" and (errs := airframe_effect_errors(e)):
            raise CatalogueError(f"{mid}: {'; '.join(errs)}")
        effects.append(Effect(t, {k: v for k, v in e.items() if k != "target"}))
    det = d.get("detection", {"codes": [], "coverage": 0.0})
    cov = float(det.get("coverage", 0.0))
    if not 0.0 <= cov <= 1.0:
        raise CatalogueError(f"{mid}: coverage must be in [0, 1]")
    ev = need("evidence")
    try:
        EvidenceTag.parse(str(ev["tag"]))
    except Exception as x:
        raise CatalogueError(f"{mid}: evidence tag: {x}") from x
    if not str(ev.get("source", "")).strip():
        raise CatalogueError(f"{mid}: evidence source is required")
    if cls != "degradation" and cls != "physics" and onset["process"] in ("m10", "physics"):
        raise CatalogueError(f"{mid}: only degradation/physics modes may use onset {onset['process']!r}")
    validation = _validation(mid, need("validation"))
    return FaultMode(
        mid,
        need("name"),
        need("subsystem"),
        cls,
        d.get("nm_ref"),
        onset,
        dict(d.get("severity", {"dist": "fixed", "value": 1.0})),
        float(d.get("duration_s", 0.0)),
        d.get("graph_root"),
        tuple(effects),
        tuple(det.get("codes", ())),
        cov,
        tuple(d.get("refs", ())),
        str(d.get("signature", "")),
        dict(ev),
        validation,
    )


def _validation(mid: str, v: object) -> Mapping[str, object]:
    """AD-55 status: ``validated`` with B7 ``checks`` (ids ``B7-...``) and the literature ``evidence``, or
    ``unvalidated`` with a ``reason`` starting with :data:`UNVALIDATED_PREFIX`."""
    if not isinstance(v, Mapping):
        raise CatalogueError(f"{mid}: validation must be a mapping")
    status = v.get("status")
    if status not in VALIDATION_STATUSES:
        raise CatalogueError(f"{mid}: validation status {status!r} not in {VALIDATION_STATUSES}")
    if status == "validated":
        if set(v) != {"status", "checks", "evidence"}:
            raise CatalogueError(f"{mid}: a validated mode has exactly status, checks and evidence")
        checks = v["checks"]
        if not isinstance(checks, list) or not checks or not all(str(c).startswith("B7-") for c in checks):
            raise CatalogueError(f"{mid}: validated checks must be a non-empty list of B7 ids")
        if not str(v["evidence"]).strip():
            raise CatalogueError(f"{mid}: a validated mode needs its literature evidence")
        return {"status": status, "checks": tuple(str(c) for c in checks), "evidence": str(v["evidence"])}
    if set(v) != {"status", "reason"} or not str(v["reason"]).startswith(UNVALIDATED_PREFIX):
        raise CatalogueError(
            f"{mid}: an unvalidated mode has status and a reason '{UNVALIDATED_PREFIX}: ...'"
        )
    return {"status": status, "reason": str(v["reason"])}


@lru_cache(maxsize=4)
def load_catalogue(path: str | None = None) -> Mapping[str, FaultMode]:
    """Fault modes by id, in file order (validated)."""
    doc = load_yaml(Path(path) if path else CATALOGUE_PATH)
    return parse_catalogue(doc)


def parse_catalogue(doc: Mapping) -> Mapping[str, FaultMode]:
    if doc.get("format") != CATALOGUE_FORMAT:
        raise CatalogueError(f"catalogue.yaml: format must be {CATALOGUE_FORMAT}")
    return {mid: _mode(mid, d) for mid, d in doc["modes"].items()}


def priority_set(catalogue: Mapping[str, FaultMode]) -> tuple[str, ...]:
    """The AD-55 priority set: the validated modes, in catalogue order."""
    return tuple(mid for mid, m in catalogue.items() if m.validated)
