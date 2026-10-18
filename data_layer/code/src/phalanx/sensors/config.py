"""M12 configuration: channel map + parameter sets + dictionary -> flat kernel tables (AD-22).

``build_sensor_config`` reads ``configs/<platform>/params/M12/channel_map.yaml`` (structure: which dictionary
channel is measured by which sensor class, from which truth signal) and ``M12.yaml`` (every number, with
provenance), checks both against the dictionary (channel exists, SI unit of the reading equals the dictionary
channel's ``eu_conversion(...).si_units``) and the W1 port catalogue (truth signal exists, unit matches), and
lays everything out as the flat arrays the kernel takes.

Nothing here invents a number: a class parameter is either read from ``M12.yaml`` or is a structural identity
(gain 1, offset 0, axis vector from the installation orientation in the map).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from phalanx.core.module import ContractError, ParamSet
from phalanx.core.units import ureg
from phalanx.dictionary.params import load_params, params_dir
from phalanx.dictionary.yamlio import load_yaml

from . import kernel as K

MAP_FORMAT = "phalanx.sensors.channel_map/1"
_REPO = Path(__file__).resolve().parents[3]
CATALOGUE_PATH = _REPO / "configs" / "interfaces" / "w1_ports.yaml"

#: global truth columns the physics needs (kernel ``cols`` order) and the catalogue signals feeding them
GLOBAL_SIGNALS: tuple[tuple[int, str, int], ...] = (
    (K.COL_MACH, "af.mach", 0),
    (K.COL_TS, "env.t_s", 0),
    (K.COL_PS, "env.p_s", 0),
    (K.COL_RHO, "env.rho", 0),
    (K.COL_TAS, "af.tas", 0),
    (K.COL_NZ, "af.nz", 0),
    (K.COL_FX, "af.f_spec_body", 0),
    (K.COL_FY, "af.f_spec_body", 1),
    (K.COL_FZ, "af.f_spec_body", 2),
)
_SRC = {n: i for i, n in enumerate(K.SRC_NAMES)}
_DYN = {n: i for i, n in enumerate(K.DYN_NAMES)}
_PE = {
    "gain": K.PE_GAIN,
    "offset": K.PE_OFFSET,
    "pattern": K.PE_PATTERN,
    "tau": K.PE_TAU,
    "wref": K.PE_WREF,
    "nexp": K.PE_NEXP,
    "wminf": K.PE_WMINF,
    "kf": K.PE_KF,
    "zeta": K.PE_ZETA,
    "wn": K.PE_WN,
    "ku": K.PE_KU,
    "kbend": K.PE_KBEND,
    "heater": K.PE_HEATER,
    "att": K.PE_ATT,
    "unwet": K.PE_UNWET,
    "dead": K.PE_DEAD,
    "easmin": K.PE_EASMIN,
    "level": K.PE_LEVEL,
}


def unit_group(si_units: str) -> str:
    """Port-name suffix of an SI unit group: ``rad/s`` -> ``rad_per_s``, ``m/s**2`` -> ``m_per_s2``."""
    u = si_units.strip()
    if u in ("1", ""):
        return "1"
    return u.replace("**", "").replace("/", "_per_").replace("*", "_").lower()


#: separator of an engine-instance channel id (U3, W2.4a): ``ENG.N1.A:E2`` = channel ENG.N1.A on engine 2
ENGINE_SEP = ":E"


def instance_id(channel_id: str, engine: int) -> str:
    """Id of the sensor instance of ``channel_id`` on engine ``engine`` (0-based): ``ENG.N1.A:E1`` for 0."""
    return f"{channel_id}{ENGINE_SEP}{int(engine) + 1}"


def dictionary_id(channel_id: str) -> str:
    """The dictionary channel id of an M12 channel or engine instance (``ENG.N1.A:E2`` -> ``ENG.N1.A``)."""
    return channel_id.split(ENGINE_SEP, 1)[0]


def engine_of(channel_id: str) -> int:
    """0-based engine of an engine-instance id, -1 for a plain channel id."""
    if ENGINE_SEP not in channel_id:
        return -1
    return int(channel_id.split(ENGINE_SEP, 1)[1]) - 1


def load_catalogue(path: Path = CATALOGUE_PATH) -> dict[str, dict[str, Any]]:
    cat = load_yaml(path)
    return {name: dict(spec) for m in cat["modules"].values() for name, spec in m["out"].items()}


def _equiv(u1: str, u2: str) -> bool:
    reg = ureg()
    a = reg.Quantity(1.0, "dimensionless" if u1 in ("1", "") else u1).to_base_units()
    b = reg.Quantity(1.0, "dimensionless" if u2 in ("1", "") else u2).to_base_units()
    return a.dimensionality == b.dimensionality and bool(np.isclose(a.magnitude, b.magnitude))


@dataclass(frozen=True)
class InputSpec:
    """One truth input port of M12: port name, catalogue signal, unit, shape and first kernel column."""

    port: str
    signal: str
    unit: str
    shape: tuple[int, ...]
    col0: int
    dtype: str = "<f8"  # the catalogue dtype of the signal (an integer state code is read as int64)

    @property
    def size(self) -> int:
        return int(np.prod(self.shape)) if self.shape else 1


@dataclass(frozen=True)
class SensorConfig:
    """Everything the M12 kernel and module need, as immutable arrays (see ``kernel.py`` for the columns)."""

    platform: str
    channels: tuple[str, ...]
    si_units: tuple[str, ...]
    classes: tuple[str, ...]
    elements: tuple[str, ...]
    inputs: tuple[InputSpec, ...]
    n_u: int
    cols: np.ndarray
    k: np.ndarray
    el_i: np.ndarray
    el_p: np.ndarray
    ch_i: np.ndarray
    ch_p: np.ndarray
    tx: np.ndarray
    ty: np.ndarray
    toff: np.ndarray
    n_sub: int
    groups: Mapping[str, tuple[int, ...]]
    group_units: Mapping[str, str]
    n_engines: int = 1

    @property
    def dict_ids(self) -> tuple[str, ...]:
        """Dictionary channel id of every channel (an engine instance ``X:Ek`` maps to ``X``)."""
        return tuple(dictionary_id(c) for c in self.channels)

    @property
    def engines(self) -> tuple[int, ...]:
        """0-based engine of every channel; -1 for channels that are not per-engine instances."""
        return tuple(engine_of(c) for c in self.channels)

    @property
    def n_ch(self) -> int:
        return len(self.channels)

    @property
    def n_el(self) -> int:
        return len(self.elements)

    def channel_index(self, channel_id: str) -> int:
        try:
            return self.channels.index(channel_id)
        except ValueError:
            raise KeyError(f"channel {channel_id!r} is not measured by this M12 configuration") from None

    def elements_of(self, channel_id: str) -> range:
        c = self.channel_index(channel_id)
        e0, ne = int(self.ch_i[c, K.IC_EL0]), int(self.ch_i[c, K.IC_NEL])
        return range(e0, e0 + ne)

    def bias_index(self) -> tuple[str, ...]:
        """Index map of ``health.sensor_bias`` as consumed here: one SI bias per M12 channel, this order."""
        return self.channels


def producer_dims() -> dict[str, int]:
    """Sizes of the catalogue symbols of the M09 signals M12 reads, from the index maps M09 publishes (single
    source of truth; E1-MF U1/U5): ``k`` = ``utilities.layout.TANKS``, ``buses`` = ``utilities.layout.BUSES``
    (DC main, DC essential, DC emergency, AC main: ``util.bus_v`` is (4,); M12's ELEC.DCBUS.V.{MAIN,
    ESSENTIAL, EMERGENCY} read indices 0-2), ``h`` = M09's hydraulic systems, ``points`` =
    ``utilities.layout.ECS_POINTS`` (``util.ecs_t`` / ``util.ecs_p``, W2.2). A local constant here once said
    ``buses = 3`` while M09 published 4 (E1 U1), which a System build would have rejected. A symbol not listed
    here (``g``, ...) has no M12 consumer; adding one means importing its producer's map, not a constant."""
    from phalanx.utilities.layout import BUSES, ECS_POINTS, N_HYD, TANKS

    return {"k": len(TANKS), "buses": len(BUSES), "h": int(N_HYD), "points": len(ECS_POINTS)}


def _pval(ps: ParamSet, name: str, where: str) -> Any:
    if name not in ps:
        raise ContractError(f"{where}: parameter {name!r} missing from set {ps.name}")
    return ps.value(name)


def build_sensor_config(
    dictionary: Any,
    *,
    platform: str = "tejas",
    params: Mapping[str, ParamSet] | None = None,
    channel_map: Mapping[str, Any] | None = None,
    n_engines: int = 1,
    dims: Mapping[str, int] | None = None,
    channels: tuple[str, ...] | None = None,
    config_root: Path | None = None,
) -> SensorConfig:
    """Build the M12 configuration.

    Args:
        dictionary: compiled M01 dictionary (``phalanx.dictionary.load_dictionary()``).
        params: M12 parameter sets (default: ``load_params("M12", platform=...)``).
        channel_map: parsed channel map (default: ``params/M12/channel_map.yaml`` of the platform).
        n_engines: engine count (catalogue symbol ``e``).
        dims: sizes of other catalogue symbols (``k`` fuel tanks, ``buses``, ``h``); the defaults are the
            producers' published index maps (``producer_dims``), never local constants.
        channels: optional subset of map channels (kept in map order).
    """
    params = (
        dict(params) if params is not None else load_params("M12", platform=platform, config_root=config_root)
    )
    if channel_map is None:
        channel_map = load_yaml(params_dir(platform, config_root) / "M12" / "channel_map.yaml")
    if channel_map.get("format") != MAP_FORMAT:
        raise ContractError(f"channel map format must be {MAP_FORMAT}")
    classes = channel_map["classes"]
    cmap = dict(channel_map["channels"])
    if channels is not None:
        missing = [c for c in channels if c not in cmap]
        if missing:
            raise ContractError(f"channels not in the M12 map: {missing}")
        cmap = {c: cmap[c] for c in cmap if c in set(channels)}
    if not cmap:
        raise ContractError("M12 configuration needs at least one channel")
    cat = load_catalogue()
    dims = {"e": n_engines, **producer_dims(), **(dims or {})}
    if n_engines > 1:
        cmap = _engine_instances(cmap, cat, n_engines)
    const = params["constants"]

    # ---- input layout --------------------------------------------------------------------------------------
    needed: list[str] = []

    def need(sig: str) -> None:
        if sig not in cat:
            raise ContractError(f"truth signal {sig!r} is not in the W1 port catalogue")
        if sig not in needed:
            needed.append(sig)

    need_global = set()
    for cid, spec in cmap.items():
        if spec.get("class") not in classes:
            raise ContractError(f"M12 {cid}: unknown class {spec.get('class')!r}")
        cls = classes[spec["class"]]
        need(spec["input"])
        if "flow" in cls:
            need(cls["flow"])
        if "heater_input" in cls:  # TAT de-icing heater state (W2.2: util.probe_heat)
            need(cls["heater_input"])
        src, dyn = cls["source"], cls["dynamics"]
        if src in ("tat", "pstatic", "ptotal", "vane"):
            need_global.add("af.mach")
        if src in ("pstatic", "ptotal") or dyn == "lag1_pneu":
            need_global.add("env.p_s")
        if src == "tat" or dyn == "lag1_pneu":
            need_global.add("env.t_s")
        if src == "tat" or dyn == "lag2_eas" or cls.get("flux") == "rho_tas":
            need_global |= {"env.rho", "af.tas"}
        if src == "vane" and not cls.get("no_bending"):
            need_global.add("af.nz")
        if src == "fuel_gauge":
            need_global.add("af.f_spec_body")
    for _, sig, _ in GLOBAL_SIGNALS:
        if sig in need_global:
            need(sig)
    inputs: list[InputSpec] = []
    col = 0
    for sig in needed:
        spec = cat[sig]
        shape = tuple(int(d) if isinstance(d, int) else int(dims[d]) for d in spec["shape"])
        port = sig.replace(".", "_")
        dtype = np.dtype(spec.get("dtype", "float64")).str
        inputs.append(InputSpec(port, sig, spec["unit"], shape, col, dtype))
        col += int(np.prod(shape)) if shape else 1
    col_of = {s.signal: s for s in inputs}
    cols = np.full(K.N_COLS, -1, dtype=np.int64)
    for ci, sig, idx in GLOBAL_SIGNALS:
        if sig in col_of:
            cols[ci] = col_of[sig].col0 + idx

    # ---- tables --------------------------------------------------------------------------------------------
    tab_ids: dict[tuple[str, str, str], int] = {}
    tx_list: list[np.ndarray] = []
    ty_list: list[np.ndarray] = []

    def table(pset: ParamSet, xname: str, yname: str, where: str) -> int:
        key = (pset.name, xname, yname)
        if key not in tab_ids:
            x = np.asarray(_pval(pset, xname, where), dtype=np.float64)
            y = np.asarray(_pval(pset, yname, where), dtype=np.float64)
            if x.ndim != 1 or x.shape != y.shape or x.size < 2 or np.any(np.diff(x) <= 0):
                raise ContractError(f"{where}: table {xname}/{yname} must be 1-D, equal length, increasing x")
            tab_ids[key] = len(tx_list)
            tx_list.append(x)
            ty_list.append(y)
        return tab_ids[key]

    # ---- elements and channels -----------------------------------------------------------------------------
    el_names: list[str] = []
    el_rows_i: list[np.ndarray] = []
    el_rows_p: list[np.ndarray] = []
    shared: dict[str, int] = {}
    ch_rows_i: list[np.ndarray] = []
    ch_rows_p: list[np.ndarray] = []
    si_units: list[str] = []
    cls_names: list[str] = []

    def element_row(
        cid: str, spec: Mapping[str, Any], cls: Mapping[str, Any]
    ) -> tuple[np.ndarray, np.ndarray]:
        where = f"M12 {cid} ({spec['class']})"
        ip = np.zeros(K.N_IE, dtype=np.int64)
        pe = np.zeros(K.N_PE, dtype=np.float64)
        ip[K.IE_SRC] = _SRC[cls["source"]]
        ip[K.IE_DYN] = _DYN[cls["dynamics"]]
        inp = col_of[spec["input"]]
        idx = int(spec.get("index", 0))
        if not 0 <= idx < inp.size:
            raise ContractError(f"{where}: index {idx} outside {spec['input']} of size {inp.size}")
        ip[K.IE_C0] = inp.col0 + idx
        ip[K.IE_CW] = -1
        ip[K.IE_TAB0] = -1
        ip[K.IE_TAB1] = -1
        ip[K.IE_HEAT] = col_of[cls["heater_input"]].col0 if "heater_input" in cls else -1
        pe[K.PE_GAIN] = 1.0
        pe[K.PE_WMINF] = 1.0
        pe[K.PE_WREF] = 1.0
        if "flow" in cls:
            ip[K.IE_CW] = col_of[cls["flow"]].col0 + idx
            ip[K.IE_WKIND] = K.WK_COLUMN
        if cls.get("flux") == "rho_tas":
            ip[K.IE_WKIND] = K.WK_RHO_TAS
        ps = params.get(cls["params"]) if "params" in cls else None
        if "params" in cls and ps is None:
            raise ContractError(f"{where}: parameter set {cls['params']!r} missing from M12.yaml")
        for kname, pname in (cls.get("map") or {}).items():
            pe[_PE[kname]] = float(_pval(ps, pname, where))
        for tname, (xn, yn) in (cls.get("tables") or {}).items():
            ip[K.IE_TAB0 if tname == "tab0" else K.IE_TAB1] = table(ps, xn, yn, where)
        tr = cls.get("transform")
        if tr == "a8_fraction":
            amin, amax = float(_pval(ps, "area_min", where)), float(_pval(ps, "area_max", where))
            pe[K.PE_GAIN] = 1.0 / (amax - amin)
            pe[K.PE_OFFSET] = -amin / (amax - amin)
        elif tr == "arm":
            pe[K.PE_GAIN] = float(_pval(ps, "arm", where))
        elif tr is not None:
            raise ContractError(f"{where}: unknown transform {tr!r}")
        if cls["source"] == "axis3":
            ax = spec.get("axis")
            if ax is None or len(ax) != 3:
                raise ContractError(f"{where}: axis3 source needs an installed 3-vector 'axis'")
            if idx != 0 or inp.size != 3:
                raise ContractError(f"{where}: axis3 reads a (3,) body vector from element 0")
            pe[K.PE_AX], pe[K.PE_AY], pe[K.PE_AZ] = (float(a) for a in ax)
        if cls["source"] == "fuel_gauge":
            sname, pname = str(spec["capacity"]).split(".")
            pe[K.PE_CAP] = float(_pval(params[sname], pname, where))
        if cls["dynamics"] in ("lag1", "lag1_flux", "lag1_pneu") and not pe[K.PE_TAU] > 0:
            raise ContractError(f"{where}: first-order element needs tau > 0")
        if cls["dynamics"] in ("lag2", "lag2_eas") and not pe[K.PE_ZETA] > 0:
            raise ContractError(f"{where}: second-order element needs zeta > 0")
        return ip, pe

    for cid, spec in cmap.items():
        cls_name = spec["class"]
        if cls_name not in classes:
            raise ContractError(f"M12 {cid}: unknown class {cls_name!r}")
        cls = classes[cls_name]
        ch = dictionary.channel(dictionary_id(cid))  # KeyError for an unknown channel
        conv = dictionary.eu_conversion(dictionary_id(cid))
        si = conv.si_units
        # unit of the reading produced by the source
        in_unit = col_of[spec["input"]].unit
        out_unit = {
            "pstatic": "Pa",
            "ptotal": "Pa",
            "tat": "K",
            "vane": "rad",
            "fuel_gauge": "kg",
            "discrete": "1",
        }.get(cls["source"], in_unit)
        if cls.get("transform") == "a8_fraction":
            out_unit = "1"
        elif cls.get("transform") == "arm":
            out_unit = "m"
        if not _equiv(out_unit, si):
            raise ContractError(
                f"M12 {cid}: sensor class {cls_name} reads {out_unit!r} but the dictionary channel's SI unit "
                f"is {si!r} ({ch['units']})"
            )
        n_probe = int(spec.get("probes", 1))
        ename = spec.get("element")
        if ename is not None and ename in shared:
            e0 = shared[ename]
        else:
            e0 = len(el_names)
            for p in range(n_probe):
                ip, pe = element_row(cid, spec, cls)
                el_rows_i.append(ip)
                el_rows_p.append(pe)
                el_names.append(ename or (cid if n_probe == 1 else f"{cid}#p{p}"))
            if ename is not None:
                shared[ename] = e0
        ic = np.zeros(K.N_IC, dtype=np.int64)
        ic[K.IC_EL0] = e0
        ic[K.IC_NEL] = n_probe
        if "hold" in cls:
            hold_s = float(_pval(params[cls["params"]], cls["hold"], f"M12 {cid}"))
            ic[K.IC_HOLD_NS] = round(hold_s * 1e9)
        pc = np.zeros(K.N_PC, dtype=np.float64)
        pc[K.PC_GAIN] = 1.0
        if "trip" in cls:  # a discrete channel: the LRU's input comparator on the detector signal
            if cls["source"] != "discrete":
                raise ContractError(f"M12 {cid}: a trip level needs the discrete source")
            ic[K.IC_DISC] = 1
            pc[K.PC_TRIP] = float(_pval(params[cls["params"]], cls["trip"], f"M12 {cid}"))
        rng = ch.get("range") or {}
        lo = rng.get("min")
        pc[K.PC_OPEN] = float(conv.to_si(lo)) if lo is not None else 0.0  # open circuit reads bottom of scale
        ch_rows_i.append(ic)
        ch_rows_p.append(pc)
        si_units.append(si)
        cls_names.append(cls_name)

    toff = np.zeros(len(tx_list) + 1, dtype=np.int64)
    for i, x in enumerate(tx_list):
        toff[i + 1] = toff[i] + x.size
    tx = np.concatenate(tx_list) if tx_list else np.zeros(1)
    ty = np.concatenate(ty_list) if ty_list else np.zeros(1)
    kvec = np.zeros(K.N_K, dtype=np.float64)
    kvec[K.K_P_SL] = float(const.value("p_sl"))
    kvec[K.K_T_SL] = float(const.value("t_sl"))
    kvec[K.K_RHO_SL] = float(const.value("rho_sl"))
    kvec[K.K_GAMMA] = float(const.value("gamma"))
    kvec[K.K_SUTH] = float(const.value("sutherland_s"))
    kvec[K.K_G0] = float(const.value("g0"))
    n_sub = int(const.value("n_sub"))
    if n_sub < 1:
        raise ContractError("n_sub must be >= 1")
    groups: dict[str, list[int]] = {}
    gunits: dict[str, str] = {}
    for i, u in enumerate(si_units):
        g = unit_group(u)
        groups.setdefault(g, []).append(i)
        gunits[g] = u
    chans = tuple(cmap)
    arrs = [np.array(a) for a in (el_rows_i, el_rows_p, ch_rows_i, ch_rows_p)]
    for a in (*arrs, cols, kvec, tx, ty, toff):
        a.flags.writeable = False
    return SensorConfig(
        platform=platform,
        channels=chans,
        si_units=tuple(si_units),
        classes=tuple(cls_names),
        elements=tuple(el_names),
        inputs=tuple(inputs),
        n_u=col,
        cols=cols,
        k=kvec,
        el_i=arrs[0],
        el_p=arrs[1],
        ch_i=arrs[2],
        ch_p=arrs[3],
        tx=tx,
        ty=ty,
        toff=toff,
        n_sub=n_sub,
        groups={g: tuple(v) for g, v in sorted(groups.items())},
        group_units=dict(sorted(gunits.items())),
        n_engines=int(n_engines),
    )


def _engine_instances(
    cmap: Mapping[str, Any], cat: Mapping[str, Mapping[str, Any]], n_engines: int
) -> dict[str, Any]:
    """U3 (W2.4a): with n_engines > 1 every channel whose truth input carries the engine axis (catalogue shape
    ``[e, ...]``) is measured by one sensor instance per engine: ``ENG.N1.A`` becomes ``ENG.N1.A:E1`` ...
    ``:E<n>``, instance k reading element k of its input (and of its flow signal). Aircraft-level channels are
    unchanged. A channel mapped to a non-zero engine index has no per-engine meaning and is refused. With one
    engine nothing is expanded (the Tejas configuration is unchanged)."""
    out: dict[str, Any] = {}
    for cid, spec in cmap.items():
        sig = cat.get(spec["input"], {})
        shape = list(sig.get("shape") or [])
        if not shape or shape[0] != "e":
            out[cid] = spec
            continue
        if int(spec.get("index", 0)) != 0:
            raise ContractError(f"M12 {cid}: engine-axis channel mapped to engine index {spec['index']}")
        for k in range(n_engines):
            inst = dict(spec)
            inst["index"] = k
            if "element" in spec:
                inst["element"] = f"{spec['element']}{ENGINE_SEP}{k + 1}"
            out[instance_id(cid, k)] = inst
    return out
