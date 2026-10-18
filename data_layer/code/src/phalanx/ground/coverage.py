"""U6 channel-coverage plan: which route delivers each dictionary channel to the contract, or why it is
absent.

Data: ``configs/<platform>/coverage/channel_coverage.yaml`` (format ``phalanx.coverage/1``; schema in its
header). Each channel has exactly one owner class (``CLASSES``): an M12 sensor, a ``RECORDED`` LRU-computed
producer, another contract topic, or explicitly not simulated (contract state ``absent``, A-W2.2-11). Gaps
(``G-*``) and scope decisions (``S-*``) carry an owner, a work package and a plan. This module loads and
validates the file's internal consistency; ``tests/integration/test_w22_channel_coverage.py`` checks it
against the code (channel map, RECORDED ports, topics, M13 acquisition, monitor inputs, the
not_measured_states.csv cross-references).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from phalanx.core.module import ContractError
from phalanx.dictionary.params import params_dir
from phalanx.dictionary.yamlio import load_yaml

FORMAT = "phalanx.coverage/1"
CLASSES = ("m12_sensor", "recorded", "topic", "not_simulated")
GAP_KINDS = ("acquisition", "contract", "simulation", "scope")
TARGETS = (*CLASSES[:3], "none")
#: consumer route of a produced channel (AD-54): param_samples (a recorded-bus transport, both paths), fti
#: (the FTI PCM stream: only when the FTI system is fitted), internal (no full-path transport: stays in the
#: CIR)
ROUTES = ("param_samples", "fti", "internal")
_FIELDS = {
    "m12_sensor": ({"class"}, {"acq_gap", "route"}),
    "recorded": ({"class", "producer", "port"}, {"acq_gap", "route"}),
    "topic": ({"class", "topic", "producer"}, {"field", "gap"}),
    "not_simulated": ({"class", "gap", "target"}, {"nm"}),
}


@dataclass(frozen=True)
class Gap:
    """A named coverage gap (``G-*``) or scope decision (``S-*``)."""

    id: str
    kind: str
    title: str
    owner: tuple[str, ...]
    wp: str
    plan: str
    truth: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    consumers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChannelCoverage:
    """The route of one dictionary channel."""

    channel_id: str
    cls: str
    producer: str | None = None
    port: str | None = None
    topic: str | None = None
    field: str | None = None
    gap: str | None = None
    acq_gap: str | None = None
    target: str | None = None
    nm: tuple[str, ...] = ()
    route: str = "param_samples"

    @property
    def produced(self) -> bool:
        """Produced today (by the simulation, on some route): not ``not_simulated`` and no producer gap."""
        return self.cls != "not_simulated" and self.gap is None

    @property
    def in_param_samples(self) -> bool:
        """Reaches ``param.samples`` today in the service configuration (FTI not fitted): an M12 sensor or
        RECORDED channel with a recorded-bus route (AD-54) that the recording path can acquire."""
        return (
            self.cls in ("m12_sensor", "recorded") and self.acq_gap is None and self.route == "param_samples"
        )


@dataclass(frozen=True)
class CoveragePlan:
    platform: str
    channels: Mapping[str, ChannelCoverage]
    gaps: Mapping[str, Gap]
    truth_signals: Mapping[str, Mapping[str, str]]

    def counts(self) -> dict[str, int]:
        return dict(Counter(c.cls for c in self.channels.values()))

    def members(self, gap_id: str) -> tuple[str, ...]:
        """Channels that cite ``gap_id`` (as ``gap`` or ``acq_gap``)."""
        return tuple(c for c, e in self.channels.items() if gap_id in (e.gap, e.acq_gap))


def coverage_path(platform: str = "tejas", config_root: Path | None = None) -> Path:
    return params_dir(platform, config_root).parent / "coverage" / "channel_coverage.yaml"


def _tuple(v) -> tuple[str, ...]:
    if v is None:
        return ()
    if isinstance(v, str):
        return (v,)
    return tuple(str(x) for x in v)


def load_coverage(platform: str = "tejas", config_root: Path | None = None) -> CoveragePlan:
    """Load and validate the coverage plan (schema and internal references; not the code cross-checks)."""
    doc = load_yaml(coverage_path(platform, config_root))
    if doc.get("format") != FORMAT:
        raise ContractError(f"coverage plan format must be {FORMAT}")
    if tuple(doc.get("classes", ())) != CLASSES:
        raise ContractError(f"coverage classes must be {CLASSES}")
    gaps: dict[str, Gap] = {}
    for gid, g in (doc.get("gaps") or {}).items():
        if not str(gid).startswith(("G-", "S-")):
            raise ContractError(f"gap id {gid!r} must start with G- (gap) or S- (scope decision)")
        if g.get("kind") not in GAP_KINDS or (g["kind"] == "scope") != str(gid).startswith("S-"):
            raise ContractError(f"{gid}: kind must be one of {GAP_KINDS} (scope exactly for S- ids)")
        owner = _tuple(g.get("owner"))
        for key in ("title", "wp", "plan"):
            if not str(g.get(key, "")).strip():
                raise ContractError(f"{gid}: {key} is required")
        if not owner:
            raise ContractError(f"{gid}: an owner is required")
        gaps[str(gid)] = Gap(
            str(gid),
            str(g["kind"]),
            str(g["title"]),
            owner,
            str(g["wp"]),
            str(g["plan"]),
            _tuple(g.get("truth")),
            _tuple(g.get("sources")),
            _tuple(g.get("consumers")),
        )
    channels: dict[str, ChannelCoverage] = {}
    for cid, e in (doc.get("channels") or {}).items():
        cls = e.get("class")
        if cls not in CLASSES:
            raise ContractError(f"{cid}: class {cls!r} not in {CLASSES}")
        need, opt = _FIELDS[cls]
        keys = set(e)
        if not need <= keys or not keys <= need | opt:
            raise ContractError(
                f"{cid}: {cls} needs {sorted(need)} (optional {sorted(opt)}), got {sorted(keys)}"
            )
        for ref in (e.get("gap"), e.get("acq_gap")):
            if ref is not None and ref not in gaps:
                raise ContractError(f"{cid}: unknown gap {ref!r}")
        if e.get("acq_gap") is not None and gaps[e["acq_gap"]].kind != "acquisition":
            raise ContractError(f"{cid}: acq_gap {e['acq_gap']} is not an acquisition gap")
        if e.get("route", "param_samples") not in ROUTES:
            raise ContractError(f"{cid}: route {e['route']!r} not in {ROUTES}")
        if cls == "not_simulated" and e["target"] not in TARGETS:
            raise ContractError(f"{cid}: target {e['target']!r} not in {TARGETS}")
        channels[str(cid)] = ChannelCoverage(
            str(cid),
            cls,
            producer=e.get("producer"),
            port=e.get("port"),
            topic=e.get("topic"),
            field=e.get("field"),
            gap=e.get("gap"),
            acq_gap=e.get("acq_gap"),
            target=e.get("target"),
            nm=_tuple(e.get("nm")),
            route=str(e.get("route", "param_samples")),
        )
    unused = sorted(set(gaps) - {g for e in channels.values() for g in (e.gap, e.acq_gap) if g})
    if unused:
        raise ContractError(f"gaps cited by no channel: {unused}")
    truth = {str(k): dict(v) for k, v in (doc.get("truth_signals") or {}).items()}
    for sig, t in truth.items():
        # a signal read and recorded end to end (status bound) needs no gap; partial / unbound name theirs
        if t.get("gap") is None and t.get("status") == "bound":
            continue
        if t.get("gap") not in gaps:
            raise ContractError(f"truth signal {sig}: unknown gap {t.get('gap')!r}")
    return CoveragePlan(str(doc.get("platform", platform)), channels, gaps, truth)
