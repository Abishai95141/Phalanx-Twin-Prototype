"""Cross-module index-map ties (E1-MF, U5): a consumer reads each column of a multi-unit signal with the
meaning its producer published.

E1 found these maps defined twice with no test tying them (mutants m02 and m13 survived): `env.w_engine`
columns (M03 vs M07), `health.engine` (M10 vs M07), `util.bus_v` and the tanks (M09 vs M12), `fcs.surf_pos`
(M05 vs M12), plus `health.actuator` (M10 vs M05) and the M12 hydraulic and wheel channels found while
auditing. The `health.sensor_bias` (M10 vs M12) and `health.utility` (M10 vs M09) maps are already tied in
`tests/unit/test_health_catalogue.py`.

Each test reads the *effective* consumer index from the consumer's own build (M12: the kernel column of every
channel's element, `ch_i`/`el_i`, i.e. what the compiled kernel reads; M07: the kernel input layout) and
compares it with the producer's published names. Name correspondences that are not literal are written out
once here with their source. The M07 module adapter (`tests/integration/test_engine_module_adapter.py`) ties
the same two M07 maps behaviourally (distinct per-column inputs through `EngineModule` vs the kernel driven by
name).

Sample: structural (whole published maps; no simulation).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from phalanx.dictionary import load_dictionary
from phalanx.sensors import kernel as SK
from phalanx.sensors.config import build_sensor_config

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def m12():
    return build_sensor_config(load_dictionary())


def m12_reads(cfg) -> dict[str, tuple[str, int]]:
    """channel id -> (catalogue signal, index within it) that M12's kernel reads for the channel's (first)
    element: the column ``el_i[e0, IE_C0]`` located in the input layout ``cfg.inputs``."""
    out = {}
    for c, cid in enumerate(cfg.channels):
        e0 = int(cfg.ch_i[c, SK.IC_EL0])
        col = int(cfg.el_i[e0, SK.IE_C0])
        spec = next(s for s in cfg.inputs if s.col0 <= col < s.col0 + s.size)
        out[cid] = (spec.signal, col - spec.col0)
    return out


def _of(reads: dict, signal: str) -> dict[str, int]:
    return {cid: i for cid, (s, i) in reads.items() if s == signal}


# ---------------------------------------------------------------------------------------------- M09 -> M12
#: M09 bus name <- dictionary DC-bus measurand suffix (M09 utilities/layout.py: "DC order =
#: ELEC.DCBUS.V.{MAIN, ESSENTIAL, EMERGENCY}"; the master box's Main/Essential/Emergency buses,
#: tejas_utility_systems.md, DDP node 9647). M09's fourth bus (AC_MAIN) has no ELEC.DCBUS channel.
DC_BUS_OF = {"MAIN": "DC_MAIN", "ESSENTIAL": "DC_ESS", "EMERGENCY": "DC_EMERG"}


def test_bus_voltage_channels_read_m09_buses_by_name(m12):
    """U1/U5 (m13): every ELEC.DCBUS.V channel reads the M09 bus of the same name, and M12 sizes `util.bus_v`
    as M09 publishes it (4: DC main, DC essential, DC emergency, AC main)."""
    from phalanx.utilities.layout import BUSES
    from phalanx.utilities.ports import ports as m09_ports

    reads = _of(m12_reads(m12), "util.bus_v")
    assert set(reads) == {f"ELEC.DCBUS.V.{k}" for k in DC_BUS_OF}, reads
    for cid, i in reads.items():
        assert BUSES[i] == DC_BUS_OF[cid.rsplit(".", 1)[1]], (cid, i, BUSES)
    spec = next(s for s in m12.inputs if s.signal == "util.bus_v")
    published = {p.name: p.shape for p in m09_ports(1)[1]}["bus_v"]
    assert spec.shape == published == (len(BUSES),), (spec.shape, published)


def test_fuel_gauges_read_m09_tanks_by_name(m12):
    """Every FUEL.QTY.TANK.<name> gauge reads M09's tank <name> (M09 TANKS are the dictionary tank names), and
    every M09 tank has a gauge."""
    from phalanx.utilities.layout import TANKS

    reads = _of(m12_reads(m12), "util.fuel_mass")
    assert {cid.removeprefix("FUEL.QTY.TANK.") for cid in reads} == set(TANKS)
    for cid, i in reads.items():
        assert TANKS[i] == cid.removeprefix("FUEL.QTY.TANK."), (cid, i)
    assert next(s for s in m12.inputs if s.signal == "util.fuel_mass").shape == (len(TANKS),)


def test_hydraulic_channels_read_their_system(m12):
    """HYD.SYS<n>.P/T read hydraulic system n = index n-1 of M09's (h=2) vectors (M09 layout: 'pressures
    util.hyd_p are gauge (dictionary HYD.SYSn.P is gauge)'; system order 1, 2)."""
    from phalanx.utilities.layout import N_HYD

    reads = m12_reads(m12)
    for sig in ("util.hyd_p", "util.hyd_t"):
        r = _of(reads, sig)
        assert r and len(r) == N_HYD
        for cid, i in r.items():
            assert cid.startswith("HYD.SYS") and int(cid[len("HYD.SYS")]) - 1 == i, (cid, i)


def test_wheel_speed_channels_read_their_wheel(m12):
    """BRK.WHEEL_SPEED.SPEED_L/R read wheel 0/1 of af.wheel_speed (M06: left, right main; M09 the same)."""
    r = _of(m12_reads(m12), "af.wheel_speed")
    assert r == {"BRK.WHEEL_SPEED.SPEED_L": 0, "BRK.WHEEL_SPEED.SPEED_R": 1}, r


# ------------------------------------------------------------------------------------------ M05 -> M12, M10
def test_surface_position_channels_read_m05_surfaces(m12):
    """Every FCS surface-position transducer lane reads the fcs.surf_pos entry M05 publishes for that surface
    (M05 `SURFACE_CHANNELS`, the dictionary measurand of each index), and every surface has transducers."""
    from phalanx.fcs.ports import N_SURF, SURFACE_CHANNELS, _pos_measurand

    reads = _of(m12_reads(m12), "fcs.surf_pos")
    assert reads
    seen = set()
    for cid, i in reads.items():
        assert cid.rsplit(".", 1)[0] == _pos_measurand(i), (cid, i, SURFACE_CHANNELS[i])
        seen.add(i)
    assert seen == set(range(N_SURF))


#: M10 health.actuator name -> M05 surface (fcs.surf_pos order; W1_interfaces.md M05/M10: health.actuator is
#: (13,) in fcs.surf_pos order). Slats are numbered 1-6 in M10 and named spanwise in M05 (A-W1.6-16).
ACTUATOR_OF = {
    "elevon_lo": "ELEVON_LOB",
    "elevon_li": "ELEVON_LIB",
    "elevon_ri": "ELEVON_RIB",
    "elevon_ro": "ELEVON_ROB",
    "rudder": "RUDDER",
    **{
        f"slat_{k}": s
        for k, s in enumerate(
            ("SLAT_OB_L", "SLAT_MB_L", "SLAT_IB_L", "SLAT_IB_R", "SLAT_MB_R", "SLAT_OB_R"), 1
        )
    },
    "airbrake_l": "AIRBRAKE_L",
    "airbrake_r": "AIRBRAKE_R",
}


def test_actuator_health_follows_the_surface_order():
    """health.actuator (M10) is indexed in fcs.surf_pos order (M05): entry j is the actuator of surface j."""
    from phalanx.fcs.ports import ACT_BIT_UNITS
    from phalanx.health.layout import ACTUATORS

    assert len(ACTUATORS) == len(ACT_BIT_UNITS)
    assert [ACTUATOR_OF[a] for a in ACTUATORS] == list(ACT_BIT_UNITS)


# ------------------------------------------------------------------------------------------ M03, M10 -> M07
def test_w_engine_columns_are_m03_channels_in_m07_inputs():
    """env.w_engine columns (AD-32, AD-46): M03 writes its first five ENGINE_CHANNELS as the columns; M07
    names the same columns and feeds column j to its kernel input ``w_<name_j>``."""
    from phalanx.engine.layout import N_W_ENGINE, U_NAMES, U_WFM_D, W_ENGINE_NAMES
    from phalanx.environment.disturbances import ENGINE_CHANNELS
    from phalanx.environment.disturbances import N_W_ENGINE as M03_NW

    assert M03_NW == N_W_ENGINE == 5
    assert tuple(ENGINE_CHANNELS[:M03_NW]) == W_ENGINE_NAMES
    assert tuple(U_NAMES[U_WFM_D : U_WFM_D + N_W_ENGINE]) == tuple(f"w_{n}" for n in W_ENGINE_NAMES)
    from phalanx.dictionary.yamlio import load_yaml

    cat = load_yaml(Path(__file__).resolve().parents[2] / "configs" / "interfaces" / "w1_ports.yaml")
    note = cat["modules"]["M03"]["out"]["env.w_engine"]["note"]
    listed = note[note.index("[") + 1 : note.index("]")].split(", ")
    assert tuple(listed) == W_ENGINE_NAMES, note  # the catalogue states the same order


def test_health_engine_columns_are_m10_deltas_in_m07_inputs():
    """health.engine columns: M10's ENGINE_DELTAS are M07's HEALTH_NAMES, fed to kernel inputs
    ``h_<name>``."""
    from phalanx.engine.layout import HEALTH_NAMES, N_HEALTH, U_H0, U_NAMES
    from phalanx.health.layout import ENGINE_DELTAS

    assert ENGINE_DELTAS == HEALTH_NAMES and len(ENGINE_DELTAS) == N_HEALTH
    assert tuple(U_NAMES[U_H0 : U_H0 + N_HEALTH]) == tuple(f"h_{n}" for n in ENGINE_DELTAS)


# ---------------------------------------------------------------------------------------------- the extractor
def test_m12_reads_extractor_follows_a_planted_index():
    """Negative control for the extractor: a channel map whose ELEC.DCBUS.V.MAIN index is moved to 3 (the AC
    bus) changes what `m12_reads` reports, so the bus tie above fails (mutant m13 shape)."""
    from phalanx.dictionary.params import params_dir
    from phalanx.dictionary.yamlio import load_yaml

    cmap = load_yaml(params_dir("tejas") / "M12" / "channel_map.yaml")
    chans = dict(cmap["channels"])
    chans["ELEC.DCBUS.V.MAIN"] = {**chans["ELEC.DCBUS.V.MAIN"], "index": 3}
    cfg = build_sensor_config(load_dictionary(), channel_map={**cmap, "channels": chans})
    assert m12_reads(cfg)["ELEC.DCBUS.V.MAIN"] == ("util.bus_v", 3)
    with pytest.raises(AssertionError):
        test_bus_voltage_channels_read_m09_buses_by_name(cfg)
    assert np.all(cfg.el_i[:, SK.IE_C0] >= 0)
