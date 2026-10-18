"""Proxy flight runner (W2.4a): replay a DASHlink flight's recorded inputs through the proxy chain and record
the DASHlink engine words as the battery's ``FlightRecord`` (textured), together with the same instants at
truth level and at sensor level (for the MF1 texture attribution).

Chain: ``system.build_proxy_system(fused=True)`` (M03 replay + disturbances, M04 replay with the A/T state, U4
producers, M08 <-> M07 -> M12 -> M13 lanes) run block by block; every block's M12 frames feed M13's recording
entry point (``acquisition.record.AcquisitionRecorder``) with the System's identity, so the recorded words get
the keyed DASHlink texture (double quantiser on the native grid with its offset, recorder lattice,
idiosyncratic noise at the measured level, validity gate, episodic freezes) on the ACMS clock (the replay time
base, A-W2.4a-12).

The recorded input channels of the record (PLA, theta, delta, phase) are the replayed ones, so a synthetic
record is paired with the real flight sample for sample (``FlightRecord`` pairing rule of M20).

**PROTOTYPE flag (MF1 caveat a; not adopted):** ``word_delay_s`` delays the M12 frames of a recorded family
(e.g. ``{"N1": 0.15}``) by that time before recording, i.e. the word is sampled earlier in the frame than the
replay instant it is stamped with (recorder word-slot skew). M13's DASHlink texture samples every ACMS word at
the same instant; the real word-slot positions are not in the files (empirical_dashlink_texture.md Q8, "Gaps")
and fixed inter-channel skews of 0.04-0.23 s are measured between other channel pairs (same section). The
delay is an integer number of 240 Hz truth steps (4.2 ms resolution). Default: none.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from phalanx.acquisition.record import AcquisitionRecorder, frames_from_trace
from phalanx.core.module import ParamSet
from phalanx.core.rng import KeyPath
from phalanx.core.time import truth_step_times_ns
from phalanx.engine.layout import I_NAMES
from phalanx.validation.dashlink import corrections
from phalanx.validation.flightdata import DASHLINK_UNITS, FlightRecord

from .config import RECORDED, ProxyConfig
from .inputs import ProxyFlightInputs
from .system import ProxySystem, build_proxy_system

FAMILIES = ("N1", "N2", "EGT", "FF")


@dataclass(frozen=True)
class SimFlight:
    """One simulated proxy flight window: the textured record and the same instants before texture."""

    record: FlightRecord  # M13 DASHlink words (EU): what the battery compares with real data
    truth: FlightRecord  # true measurand at the same instants (EU; M07 truth, M12 harness/averaging only)
    sensor: FlightRecord  # M12 sensor output at the same instants (EU; sensor dynamics, no texture)
    limiter_share: np.ndarray  # (n_codes,) share of truth steps per M08 active-limiter code (engine 1)
    n_steps: int
    world_digest: str
    #: (E, n) M08 fuel regulator (``fadec.codes`` FUEL_LIMITER code, bits 0-3) of the truth step holding each
    #: recorded sample; None when the limiter was not recorded
    regulator: np.ndarray | None = None
    #: (E,) surge events per engine over the window (M07 state ``n_surge``; a diagnostic of the stall margins)
    n_surge: np.ndarray | None = None


def _family_rows(cfg: ProxyConfig) -> dict[str, list[int]]:
    """Recorded channel index (in ``cfg.recording.channels``) per family, ordered by engine position."""
    out: dict[str, list[int]] = {f: [] for f in FAMILIES}
    for fam in FAMILIES:
        did = next(k for k, v in RECORDED.items() if v == fam)
        for e in range(cfg.n_engines):
            out[fam].append(cfg.recording.channels.index(f"{did}:E{e + 1}"))
    return out


def simulate_flight(
    cfg: ProxyConfig,
    inp: ProxyFlightInputs,
    *,
    identity: KeyPath,
    root: int,
    window: tuple[int, int] | None = None,
    fadec_params: ParamSet | None = None,
    chunk_steps: int = 24000,
    record_limiter: bool = True,
    word_delay_s: dict[str, float] | None = None,
) -> SimFlight:
    """Simulate samples [a, b) of the flight's 4-Hz input grid (default: all) and record the words.

    ``word_delay_s``: PROTOTYPE recorder word-slot skew per family (module docstring); not adopted."""
    a, b = window if window is not None else (0, inp.n)
    w = inp.window(a, b)
    rec_in = w.replay_inputs()
    ps: ProxySystem = build_proxy_system(
        cfg,
        rec_in,
        identity=identity,
        root=root,
        fadec_params=fadec_params,
        fused=True,
        block_len=chunk_steps,
        bleed_kgs=w.bleed(cfg.bleed),
        pto_w=cfg.bleed.pto_w,
    )
    syst = ps.system
    recorder = AcquisitionRecorder(cfg.recording, syst.rng.scope(identity))
    rstate = recorder.init_state()
    records: dict = {}
    n_total = round((b - a) * 240 / w.rate_hz)
    sens_ports = [f"sens.{p.name}" for p in ps.modules["sens"].ports_out]
    want = [*sens_ports, "scenario.phase"] + (["fadec.active_limiter"] if record_limiter else [])
    world = syst.start()
    k0 = 0
    s_prev = None
    sens_samples: list[np.ndarray] = []
    lim_counts = np.zeros(32, dtype=np.int64)
    lim_steps: list[np.ndarray] = []
    sens_cfg = cfg.sensors
    rec_cols = np.asarray(cfg.recording.sensor_index, dtype=np.int64)
    delay = _delay_columns(cfg, word_delay_s)
    tail: dict[int, np.ndarray] = {}
    while k0 < n_total:
        n = min(chunk_steps, n_total - k0)
        world, trace = syst.run(world, n, mode="block", record=want)
        S, X = frames_from_trace(sens_cfg, trace.ports, "sens")
        if delay:
            S, X = _delayed(S, X, delay, tail)
        phase = np.asarray(trace.ports["scenario.phase"], dtype=np.int64)
        n_before = {
            c: sum(x.size for x in records[c].t_sample) if c in records else 0 for c in recorder.acq.channels
        }
        rstate, records = recorder.process(rstate, k0, S, X, phase, records=records)
        # M12-level values at the same acquisition instants (linear interpolation between frame ends,
        # M13's rule)
        c0 = recorder.acq.channels[0]
        new_t = np.concatenate(records[c0].t_sample)[n_before[c0] :]
        sens_samples.append(_interp_frames(S[:, rec_cols], s_prev, new_t, k0))
        s_prev = S[-1, rec_cols].copy()
        if record_limiter:
            lim_all = np.asarray(trace.ports["fadec.active_limiter"]).reshape(n, -1)
            lim = lim_all[:, 0]
            lim_counts += np.bincount(np.clip(lim, 0, 31), minlength=32)
            lim_steps.append((lim_all & 15).astype(np.int8))
        k0 += n
    rows = _family_rows(cfg)
    conv = [cfg.dictionary.eu_conversion(c.split(":", 1)[0]) for c in cfg.recording.channels]
    val = {c: np.concatenate(records[c].value) for c in cfg.recording.channels}
    tru = {c: np.concatenate(records[c].truth) for c in cfg.recording.channels}
    sen_si = np.concatenate(sens_samples, axis=0)
    nmin = min(v.size for v in val.values())
    nmin = min(nmin, w.n, sen_si.shape[0])

    def fam_arr(src: dict[str, np.ndarray] | None, fam: str) -> np.ndarray:
        out = np.empty((cfg.n_engines, nmin))
        for e, ci in enumerate(rows[fam]):
            cid = cfg.recording.channels[ci]
            if src is None:
                out[e] = conv[ci].to_eu(sen_si[:nmin, ci])
            else:
                out[e] = src[cid][:nmin]
        return out

    th, de = corrections(w.alt_ft[:nmin], w.mach[:nmin], w.tat_c[:nmin])
    base = dict(
        rate_hz=w.rate_hz,
        pla=w.pla_deg[:, :nmin],
        theta=th,
        delta=de,
        phase=w.phase[:nmin],
        units=DASHLINK_UNITS,
        t0_ns=0,
    )
    meta = {
        "source": "phalanx proxy (W2.4a-1)",
        "flight": inp.flight_id,
        "window": f"{a}:{b}",
        "identity": identity.canonical(),
    }
    record = FlightRecord(
        flight_id=inp.flight_id,
        outputs={f: fam_arr(val, f) for f in FAMILIES},
        meta={**meta, "level": "recorded"},
        **base,
    )
    truth = FlightRecord(
        flight_id=inp.flight_id,
        outputs={f: fam_arr(tru, f) for f in FAMILIES},
        meta={**meta, "level": "truth"},
        **base,
    )
    sensor = FlightRecord(
        flight_id=inp.flight_id,
        outputs={f: fam_arr(None, f) for f in FAMILIES},
        meta={**meta, "level": "sensor"},
        **base,
    )
    dig = world_digest(world)
    tot = max(int(lim_counts.sum()), 1)
    regulator = None
    if record_limiter:
        steps = np.concatenate(lim_steps, axis=0)  # (n_total, E)
        t_s = np.concatenate(records[cfg.recording.channels[0]].t_sample)[:nmin]
        edges = truth_step_times_ns(np.arange(n_total + 1, dtype=np.int64))
        k = np.clip(np.searchsorted(edges, t_s, side="right") - 1, 0, n_total - 1)
        regulator = np.ascontiguousarray(steps[k].T.astype(np.int64))
    n_surge = np.asarray(world.states["eng"]["i"])[:, I_NAMES.index("n_surge")].copy()
    return SimFlight(record, truth, sensor, lim_counts / tot, n_total, dig, regulator, n_surge)


def _delay_columns(cfg: ProxyConfig, word_delay_s: dict[str, float] | None) -> dict[int, int]:
    """M12 column -> delay in truth steps for the recorded channels of each delayed family."""
    if not word_delay_s:
        return {}
    out: dict[int, int] = {}
    rows = _family_rows(cfg)
    for fam, sec in word_delay_s.items():
        if fam not in FAMILIES or sec < 0:
            raise ValueError(f"word_delay_s: family {fam!r} must be one of {FAMILIES} with a delay >= 0")
        steps = round(float(sec) * 240.0)
        if steps:
            for ci in rows[fam]:
                out[int(cfg.recording.sensor_index[ci])] = steps
    return out


def _delayed(
    S: np.ndarray, X: np.ndarray, delay: dict[int, int], tail: dict[int, np.ndarray]
) -> tuple[np.ndarray, np.ndarray]:
    """Frames with the given columns delayed by their step counts, carrying the history across blocks in
    ``tail`` (the first frame is held before the start)."""
    S, X = S.copy(), X.copy()
    for col, d in delay.items():
        both = np.stack([S[:, col], X[:, col]])  # (2, L)
        prev = tail.get(col)
        if prev is None:
            prev = np.repeat(both[:, :1], d, axis=1)
        ext = np.concatenate([prev, both], axis=1)
        S[:, col], X[:, col] = ext[0, : S.shape[0]], ext[1, : S.shape[0]]
        tail[col] = ext[:, -d:]
    return S, X


def world_digest(world) -> str:
    """SHA-256 over every module's canonical state digest (module order sorted)."""
    import hashlib

    from phalanx.core.state import tree_digest

    h = hashlib.sha256()
    for mid in sorted(world.states):
        st = world.states[mid]
        if len(st):
            h.update(mid.encode())
            h.update(tree_digest(dict(st)).encode())
    return h.hexdigest()


def _interp_frames(S: np.ndarray, s_prev: np.ndarray | None, t_samples: np.ndarray, k0: int) -> np.ndarray:
    """Values at sample instants by linear interpolation between frame-end rows of S (row j = value at
    t_{k0+j+1}); the row before the chunk is ``s_prev`` (value at t_{k0}); the very first frame has no
    predecessor (its value is used, as M13 primes on the first stepped frame)."""
    ks = (
        np.searchsorted(
            truth_step_times_ns(np.arange(k0, k0 + S.shape[0] + 1, dtype=np.int64)), t_samples, side="right"
        )
        - 1
    )
    j = ks  # sample lies in [t_{k0+j}, t_{k0+j+1}) -> between row j-1 (at t_{k0+j}) and row j
    t_lo = truth_step_times_ns(k0 + j)
    t_hi = truth_step_times_ns(k0 + j + 1)
    wgt = ((t_samples - t_lo) / (t_hi - t_lo)).astype(np.float64)[:, None]
    hi = S[j]
    prev = np.vstack([S[:1] if s_prev is None else s_prev[None], S[:-1]])
    lo = prev[j]
    return lo + wgt * (hi - lo)


def simulate_many(
    cfg: ProxyConfig,
    flights: Sequence[tuple[ProxyFlightInputs, tuple[int, int]]],
    *,
    scenario: str,
    root: int,
    fadec_params: ParamSet | None = None,
) -> list[SimFlight]:
    """Several flights with identities (scenario, tail T687, sortie = flight index)."""
    out = []
    for j, (inp, win) in enumerate(flights):
        ident = KeyPath.of(scenario=scenario, tail="T687", sortie=j + 1)
        out.append(
            simulate_flight(cfg, inp, identity=ident, root=root, window=win, fadec_params=fadec_params)
        )
    return out


__all__ = ["FAMILIES", "SimFlight", "simulate_flight", "simulate_many", "world_digest"]
