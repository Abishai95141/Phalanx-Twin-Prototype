"""Sortie runner: one telemetry-mode sortie through the W2.1 truth loop, with the M13 recorder and the M14
feed.

``SortieRunner(ss)`` drives a :class:`~.system.SortieSystem` from post-start idle (AD-46) to engine cut-off in
**chunks** of ``chunk_steps`` truth steps (default 240 = 1 s). After each chunk it

1. feeds the chunk's M12 frames, flight phases and the owning modules' LRU-computed values (``RECORDED``,
   AD-42) to the M13 recorder (``AcquisitionRecorder``: the same core and keyed streams as the in-loop lanes,
   so a lane value equals the recorded value at the same sample, A7);
2. hands the M14 channels of the chunk's CIR to M14 as one ``monitor.observe`` event at the chunk end (the
   recorder -> ECMS frame; ``source="recorder"``);
3. advances the realised-usage accumulators (M10's chunk-invariant LUI and Nz kernels on truth, with M14's
   gates) and checks the physical invariants (:class:`SortieAborted` on a violation).

**Recorder placement (AD-42, provisional -> proposed decision PD-W2.1a-2).** The recorder stays outside the
scheduler, run chunk-wise on the M12 trace (vectorised: it never enters the 240 Hz hot loop). Its state
cannot be derived from the World: the per-channel AR(1), freeze, deadband and interval-counting states of the
non-lane channels depend on the signal history. So a mid-sortie snapshot is a :meth:`SortieRunner.snapshot`:
the core world snapshot + the recorder state + the realised-usage state + the chunk cursor, taken at a chunk
boundary. Restore -> continue equals the uninterrupted run bitwise (CIR, ports, events;
``test_integration_sortie.py``). The M14 observe event of the last chunk is pending in the world's event
queue, so it is in the world snapshot.

**Sortie lifecycle (AD-48.2, W2.1c).** At t = 0 the runner injects M02's bootstrap and
``monitor.sortie_start`` (M14's power-up hook: PBIT at the window start, the post-start idle, rather than at
take-off). M02 then schedules ``ops.takeoff`` at the plan's take-off (M10 holds the sortie open, M11 places
its onsets over the planned airborne window with the plan's drivers, M14 keeps its power-up) and
``ops.sortie_done`` at engine cut-off (M11 ends the sortie; M14 writes its final LUIs and the OAC counters it
has a source for, then powers down). The injected events go through ``System.inject`` (the run's bootstrap
and order log).
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from phalanx.core.canonical import PERSON_SNAPSHOT, canonical_json, digest, length_prefixed
from phalanx.core.events import Event
from phalanx.core.scheduler import World
from phalanx.core.snapshot import restore as core_restore
from phalanx.core.snapshot import snapshot as core_snapshot
from phalanx.core.state import decode_tree, encode_tree
from phalanx.core.time import truth_step_time_ns

from .system import M_ID, SortieSystem

SORTIE_MAGIC = b"PHXSORT1"
#: dictionary flight_phase names during which the aircraft must be airborne (invariant check)
#: a take-off or landing roll held this far past the plan fails the sortie (A-W2.1-9)
MAX_HOLD_S = 300.0
AIRBORNE_PHASE_NAMES = ("CLIMB", "CRUISE", "MISSION", "DESCENT", "PATTERN")


class SortieAborted(RuntimeError):
    """A physical invariant failed during the sortie (ground impact in flight, loss of control, non-finite
    truth, fuel or mass inconsistency). ``kind`` names the invariant; ``phase`` is the dictionary
    flight_phase name at step ``k``; the message carries the evidence."""

    def __init__(self, kind: str, message: str, k: int, phase: str | None = None) -> None:
        where = "" if phase is None else f", {phase}"
        super().__init__(f"[{kind}] at step {k} (t = {k / 240.0:.2f} s{where}): {message}")
        self.kind = kind
        self.k = k
        self.phase = phase


@dataclass
class SortieState:
    """Everything a telemetry sortie needs to continue bit-for-bit (snapshot contents)."""

    world: World
    rec: dict[str, np.ndarray] | None
    usage: dict[str, np.ndarray]
    started: bool = False
    ended: bool = False


@dataclass
class ChunkOutput:
    """What one chunk produced (returned to the caller; not part of the state)."""

    k0: int
    trace: Any
    cir: Any | None
    records: Mapping[str, Any] | None


@dataclass
class SortieResult:
    """Outputs of a whole run (``run_to_end``)."""

    state: SortieState
    chunks: list[ChunkOutput] = field(default_factory=list)
    #: the sortie's validated ``sortie.manifest`` record (one row; ``phalanx.integration.manifest``)
    manifest: Any = None


def _recorded_sources(ss: SortieSystem) -> dict[str, str]:
    """Dictionary channel -> ``module.port`` of every LRU-computed channel a module of the System supplies."""
    import importlib

    from phalanx.sensors.avionics.channels import ADC_CHANNELS

    out: dict[str, str] = {}
    pkgs = (("fcs", "fcs"), ("fadec", "fadec"), ("util", "utilities"), ("monitor", "monitoring"))
    for mid, pkg in (*pkgs, ("avio", "sensors.avionics")):
        if mid not in ss.modules:
            continue
        rec = importlib.import_module(f"phalanx.{pkg}.ports").RECORDED
        ports = {p.name for p in ss.modules[mid].ports_out}
        for port, cid in rec.items():
            # M12 avionics (AD-51): M13 records only the ADC computed channels today; the INS/GPS, AHRS and
            # radar-altimeter channels have no M13 clock set and the status words no discrete path (W2.2 U6)
            if mid == "avio" and cid not in ADC_CHANNELS:
                continue
            if port in ports:
                out[cid] = f"{mid}.{port}"
    return out


class SortieRunner:
    """Chunked driver of one telemetry sortie (module docstring)."""

    def __init__(
        self,
        ss: SortieSystem,
        *,
        chunk_steps: int = 240,
        cir_channels: Sequence[str] | None = None,
        feed_monitor: bool = True,
        record: Sequence[str] = (),
        validate_events: bool = False,
        check_invariants: bool = True,
        keep_cir: bool = False,
        git_commit: str | None = None,
    ) -> None:
        from phalanx.acquisition.config import build_acquisition_config
        from phalanx.acquisition.record import AcquisitionRecorder
        from phalanx.dictionary.contract import load_contract

        if chunk_steps < 1:
            raise ValueError("chunk_steps must be >= 1")
        self.ss = ss
        self.chunk = int(chunk_steps)
        self.check_invariants = check_invariants
        self.keep_cir = keep_cir
        #: code commit for the run manifest (None: ``git rev-parse`` on the repository at manifest time)
        self.git_commit = git_commit
        self.validate_events = validate_events
        self.validator = None
        if validate_events:
            from .validate import EventValidator

            m_of = dict(M_ID)
            for mid in ss.system.order:
                m_of.setdefault(mid, "INTEGRATION")
            self.validator = EventValidator(m_of)
        mon = ss.modules["monitor"]
        self.recorded_src = _recorded_sources(ss)
        sens = ss.sensor_config
        recordable = set(sens.channels) | set(self.recorded_src)
        m14 = [c for c in mon.config.channels if c in recordable] if feed_monitor else []
        self.m14_missing = tuple(c for c in mon.config.channels if c not in recordable)
        chans = list(dict.fromkeys([*(cir_channels or ()), *m14]))
        bad = [c for c in chans if c not in recordable]
        if bad:
            raise ValueError(f"no producer for recorded channels {bad}")
        self.feed_monitor = bool(feed_monitor and m14)
        self.m14_channels = tuple(m14)
        self.cir_channels = tuple(chans)
        self.recorder = None
        if chans:
            acq = build_acquisition_config(ss.dictionary, chans, sensor_channels=sens.channels)
            self.recorder = AcquisitionRecorder(acq, ss.system.rng.scope(ss.system.identity))
            self.contract = load_contract("v0")
        # ports recorded per chunk
        need = {
            "scenario.phase",
            "af.wow",
            "af.hag",
            "af.alt",
            "af.alpha",
            "af.nz",
            "af.tas",
            "af.quat",
            "eng.n2",
            "eng.ps3",
            "eng.t5",
            "pilot.pla",
            "eng.ab_state",
            "eng.wf",
            "eng.wf_ab",
            "util.fuel_mass",
            "util.mass",
            "af.brake_energy_rate",
            "pilot.gear_cmd",
            "eng.flame_state",
        }
        if self.recorder is not None:
            need |= {f"sens.{p.name}" for p in ss.modules["sens"].ports_out}
            need |= {self.recorded_src[c] for c in chans if c in self.recorded_src}
        self.ports = tuple(sorted(need | set(record)))
        self.user_record = tuple(record)
        # realised-usage gates in truth units converted to M14's EU (same thresholds as the observed counters)
        self._gates = mon._gates
        self._nz_levels = mon._nz_levels
        self._nz_rearm = float(mon.params.value("nz_rearm_g"))
        self._n2_100 = float(ss.dictionary.param_set("channel_reference").value("n2_100pct"))
        from phalanx.scenario import phases as P

        dmap = P.dictionary_map()
        names = {
            int(code): str(name) for code, name in ss.dictionary.code_table("flight_phase")["codes"].items()
        }
        self._phase_names = names
        self._airborne_codes = np.array(
            sorted({code for code, name in names.items() if str(name) in AIRBORNE_PHASE_NAMES}),
            dtype=np.int64,
        )
        self._dmap = dmap
        self.k_end = int(ss.window.t_end_off_ns * 240 // 1_000_000_000)  # planned engine cut-off

    # ------------------------------------------------------------------------------------------ lifecycle
    def begin(self) -> SortieState:
        """The initial state at t = 0 with the bootstrap and lifecycle events injected."""
        from phalanx.health.usage import lui_init

        ss = self.ss
        w = ss.start()
        plan = ss.window
        # M02's power-up at the window start (ops.power_up, W2.5) powers M14 up (PBIT); no runner hook
        w = ss.system.inject(w, ss.bootstrap_events())
        if self.validator is not None:
            from .validate import validating

            w = validating(w, self.validator)
        ne = len(plan.engine_serials)
        f, i, s = lui_init()
        usage = {
            "lui_f": np.stack([f] * ne),
            "lui_i": np.stack([i] * ne),
            "lui_stack": np.stack([s] * ne),
            "nz_counts": np.zeros(self._nz_levels.size),
            "nz_armed": np.ones(self._nz_levels.size, dtype=np.int64),
            "flight_s": np.zeros(1),
            "landings": np.zeros(1, dtype=np.int64),
            "takeoffs": np.zeros(1, dtype=np.int64),
            # truth step of the first lift-off and of the last touchdown (-1: none yet; sortie.manifest)
            "k_takeoff": np.full(1, -1, dtype=np.int64),
            "k_landing": np.full(1, -1, dtype=np.int64),
            "ab_lights": np.zeros(ne, dtype=np.int64),
            "brake_j": np.zeros(2),
            "fuel_burn_kg": np.zeros(1),
            "max_nz": np.ones(1),
            "ab_s": np.zeros(1),
            "last": np.zeros(4 + ne),  # wow_main, gear, ab_state per engine..., (spare)
            "fuel0": np.zeros(1),
            "mass0": np.zeros(1),
        }
        st = SortieState(w, self.recorder.init_state() if self.recorder else None, usage)
        st.usage["fuel0"][0] = float(np.sum(w.held["util.fuel_mass"]))
        st.usage["mass0"][0] = float(w.held["util.mass"])
        st.usage["last"][0] = float(np.all(w.held["af.wow"][1:] == 1))
        st.usage["last"][1] = float(w.held["pilot.gear_cmd"])
        st.usage["last"][4 : 4 + ne] = np.asarray(w.held["eng.ab_state"], dtype=np.float64)
        st.started = True
        return st

    def run(
        self, st: SortieState, n_steps: int, *, mode: str = "block"
    ) -> tuple[SortieState, list[ChunkOutput]]:
        """Advance ``n_steps`` (a multiple of the chunk length, or up to the window end)."""
        outs: list[ChunkOutput] = []
        target = st.world.k + int(n_steps)
        while st.world.k < target:
            if st.world.k % self.chunk:
                raise ValueError("runs advance in whole chunks from a chunk boundary")
            n = min(self.chunk, target - st.world.k)
            st, out = self._chunk(st, n, mode)
            outs.append(out)
        return st, outs

    def run_to_end(
        self, st: SortieState, *, keep_chunks: bool = False, manifest: bool = True
    ) -> SortieResult:
        """Run to the window end (engine cut-off), close the sortie (lifecycle events, final usage) and emit
        its ``sortie.manifest`` record (``manifest=False``: skip it)."""
        res = SortieResult(st)
        while st.world.k < self.end_step(st):
            n = min(self.chunk, self.end_step(st) - st.world.k)
            st, out = self._chunk(st, n, "block")
            if keep_chunks:
                res.chunks.append(out)
        res.state = self.close(st)
        if manifest:
            res.manifest = self.manifest(res.state)
        return res

    def shift_ns(self, st: SortieState) -> int:
        """How far the flown sortie runs behind (+) or ahead of (-) the plan: the pilot's plan-clock shift
        from the physically gated take-off and landing rolls (A-W2.1-9)."""
        from phalanx.pilot import kernel as PK

        return int(np.asarray(st.world.states["pilot"]["i"])[PK.I_SHIFT])

    def end_step(self, st: SortieState) -> int:
        """Truth step of the flown engine cut-off (the planned one moved by :meth:`shift_ns`)."""
        t_end = int(self.ss.window.t_end_off_ns) + self.shift_ns(st)
        return int(t_end * 240 // 1_000_000_000)

    def manifest(self, st: SortieState, **kw: Any):
        """The sortie's validated ``sortie.manifest`` table at ``st`` (one row; see
        :func:`phalanx.integration.manifest.sortie_manifest` for the keyword arguments)."""
        from .manifest import sortie_manifest

        return sortie_manifest(self, st, **kw)

    def close(self, st: SortieState) -> SortieState:
        """End the telemetry window. At the window end it advances until the events due at engine cut-off
        have dispatched (M02's ``ops.sortie_done``: M11 ends the sortie, M14 writes its final LUIs and OAC
        counters and powers down, AD-48.2); before it (a short or aborted run) it advances one step, and M02's
        lifecycle events stay in the future."""
        if st.ended:
            return st
        t_end = int(self.ss.window.t_end_off_ns) + self.shift_ns(st)
        k_ev = -(-t_end * 240 // 1_000_000_000)  # first truth step at or after engine cut-off
        n = k_ev - st.world.k + 1 if st.world.k >= self.end_step(st) else 1
        w, _ = self.ss.system.run(st.world, max(1, n))
        return SortieState(w, st.rec, st.usage, st.started, True)

    # ------------------------------------------------------------------------------------------ one chunk
    def _chunk(self, st: SortieState, n: int, mode: str) -> tuple[SortieState, ChunkOutput]:
        from phalanx.acquisition.record import frames_from_trace

        ss = self.ss
        k0 = st.world.k
        w, tr = ss.system.run(st.world, n, mode=mode, record=self.ports)
        usage = {k: v.copy() for k, v in st.usage.items()}
        self._usage(usage, tr, k0)
        scen = ss.modules["scenario"]
        if scen.aborted(w.states["scenario"]):  # a start failure ground-aborted it (M02, AD-49)
            from phalanx.scenario.module import read_doc

            doc = read_doc(w.states["scenario"])["aborted"]
            raise SortieAborted(
                "ground_abort",
                f"M02 ground-aborted the sortie at {doc['t'] / 1e9:.2f} s: start failure {doc['mode']} "
                "(ops.start_failure from M11 at the power-up; ops.sortie_done (aborted) closed M11 and M14)",
                w.k,
            )
        if self.check_invariants:
            self._invariants(tr, k0, usage)
            hold = self.shift_ns(SortieState(w, st.rec, usage, st.started, st.ended)) / 1e9
            if hold > MAX_HOLD_S:  # the pilot holds the take-off (or landing) roll: no lift-off (touchdown)
                from phalanx.pilot import kernel as PK

                seg = int(np.asarray(w.states["pilot"]["i"])[PK.I_SEG])
                fine = int(ss.window.seg_i[seg, 0])
                raise SortieAborted(
                    "phase_hold",
                    f"the flown plan is {hold:.0f} s behind it in segment {seg} (fine phase {fine}): "
                    "no lift-off or touchdown",
                    w.k,
                )
        rec_state = st.rec
        cir = None
        records = None
        if self.recorder is not None:
            S, X = frames_from_trace(ss.sensor_config, tr.ports, "sens")
            external = {}
            for cid in self.recorder.external:
                v = np.asarray(tr.ports[self.recorded_src[cid]], dtype=np.float64).reshape(n, -1)[:, 0]
                external[cid] = (v, v)
            rec_state, records = self.recorder.process(
                rec_state, k0, S, X, np.asarray(tr.ports["scenario.phase"]), external
            )

            def to_cir(channels):
                return self.recorder.to_cir(
                    self.contract,
                    ss.window.tail,
                    ss.window.sortie_id,
                    records,
                    epoch_ns=ss.epoch_utc_ns,
                    channels=channels,
                )

            feed = to_cir(self.m14_channels) if self.feed_monitor else None
            if self.keep_cir:  # every recorded channel; M14 is still fed only its own channels
                cir = to_cir(None)
            elif feed is not None:
                cir = feed
            if self.feed_monitor:
                from phalanx.monitoring.io import cir_chunk_payload

                mon = ss.modules["monitor"]
                tab = feed.table if hasattr(feed, "table") else feed
                pay = cir_chunk_payload(mon.config, tab, epoch_utc_ns=ss.epoch_utc_ns)
                if pay["t"].size:
                    w.queue.push(
                        Event(truth_step_time_ns(w.k), "monitor.observe", "monitor", pay, source="recorder")
                    )
        return SortieState(w, rec_state, usage, st.started, st.ended), ChunkOutput(k0, tr, cir, records)

    # ------------------------------------------------------------------------------------------ usage, checks
    def _usage(self, u: dict[str, np.ndarray], tr, k0: int) -> None:
        """Realised usage from truth (chunk invariant): M10's LUI kernel on N2 %, PS3 psi, T5 degC, PLA deg
        with M14's gates; Nz level crossings on af.nz; flight time (main-gear WoW off); landings; AB
        light-ups; brake energy; fuel burned (integral of eng.wf + eng.wf_ab)."""
        from phalanx.health.usage import lui_kernel, nz_counter_kernel

        P = tr.ports
        n = P["af.nz"].shape[0]
        t = (np.arange(k0, k0 + n, dtype=np.int64) * 1_000_000_000) // 240
        n2 = np.asarray(P["eng.n2"]) / self._n2_100 * 100.0
        ps3 = np.asarray(P["eng.ps3"]) / 6894.757293168361
        t5 = np.asarray(P["eng.t5"]) - 273.15
        pla = np.degrees(np.asarray(P["pilot.pla"]))
        ok = np.ones(n, np.bool_)
        for e in range(n2.shape[1]):
            f, i, s = lui_kernel(
                u["lui_f"][e],
                u["lui_i"][e],
                u["lui_stack"][e],
                self._gates,
                t,
                n2[:, e],
                ps3[:, e],
                t5[:, e],
                pla[:, e],
                ok,
            )
            u["lui_f"][e], u["lui_i"][e], u["lui_stack"][e] = f, i, s
        c, a = nz_counter_kernel(u["nz_counts"], u["nz_armed"], self._nz_levels, self._nz_rearm, P["af.nz"])
        u["nz_counts"], u["nz_armed"] = c, a
        u["max_nz"][0] = max(float(u["max_nz"][0]), float(np.max(P["af.nz"])))
        wow = np.all(np.asarray(P["af.wow"])[:, 1:] == 1, axis=1).astype(np.float64)
        u["flight_s"][0] += float(np.sum(wow < 0.5)) / 240.0
        prev = np.concatenate([[u["last"][0]], wow[:-1]])
        down = np.flatnonzero((prev < 0.5) & (wow >= 0.5))
        up = np.flatnonzero((prev >= 0.5) & (wow < 0.5))
        u["landings"][0] += int(down.size)
        u["takeoffs"][0] += int(up.size)
        if up.size and u["k_takeoff"][0] < 0:
            u["k_takeoff"][0] = k0 + int(up[0])
        if down.size:
            u["k_landing"][0] = k0 + int(down[-1])
        u["last"][0] = wow[-1]
        ab = np.asarray(P["eng.ab_state"])
        ne = ab.shape[1]
        for e in range(ne):
            pv = np.concatenate([[u["last"][4 + e]], ab[:-1, e]])
            u["ab_lights"][e] += int(np.sum((pv < 2) & (ab[:, e] == 2)))
            u["last"][4 + e] = ab[-1, e]
        u["ab_s"][0] += float(np.sum(np.any(ab == 2, axis=1))) / 240.0
        u["brake_j"] += np.sum(np.asarray(P["af.brake_energy_rate"]), axis=0) / 240.0
        u["fuel_burn_kg"][0] += float(np.sum(np.asarray(P["eng.wf"]) + np.asarray(P["eng.wf_ab"]))) / 240.0

    def _invariants(self, tr, k0: int, u: Mapping[str, np.ndarray]) -> None:
        P = tr.ports
        ph = np.asarray(P["scenario.phase"])

        def abort(kind: str, message: str, j: int) -> SortieAborted:
            return SortieAborted(kind, message, k0 + j, self._phase_names.get(int(ph[j]), str(int(ph[j]))))

        for name in ("af.alt", "af.tas", "af.nz", "eng.n2", "eng.t5", "util.mass"):
            a = np.asarray(P[name])
            if not np.all(np.isfinite(a)):
                raise abort("non_finite", f"{name} is not finite", 0)
        q = np.asarray(P["af.quat"])
        nq = np.abs(np.sum(q * q, axis=1) - 1.0)
        if float(nq.max()) > 1e-6:
            raise abort("quaternion", f"|q|^2 - 1 = {float(nq.max()):.2e}", int(nq.argmax()))
        airborne = np.isin(ph, self._airborne_codes)
        hag = np.asarray(P["af.hag"])
        hit = np.flatnonzero(airborne & (hag < 1.0))
        if hit.size:
            j = int(hit[0])
            raise abort("ground_impact", f"airborne phase with height above ground {hag[j]:.2f} m", j)
        alpha = np.degrees(np.asarray(P["af.alpha"]))
        bad = np.flatnonzero(airborne & (np.abs(alpha) > 60.0))
        if bad.size:
            j = int(bad[0])
            raise abort("loss_of_control", f"|alpha| = {abs(alpha[j]):.1f} deg in flight", j)
        fuel = np.sum(np.asarray(P["util.fuel_mass"]), axis=1)
        if float(fuel.min()) < -1e-6:
            raise abort("fuel", f"negative fuel {float(fuel.min()):.3f} kg", int(fuel.argmin()))

    # ------------------------------------------------------------------------------------------ snapshots
    def snapshot(self, st: SortieState) -> bytes:
        """Composite snapshot at a chunk boundary: world + recorder state + realised usage + flags."""
        if st.world.k % self.chunk:
            raise ValueError("sortie snapshots are taken at chunk boundaries")
        world = core_snapshot(self.ss.system, st.world)
        rec = encode_tree(st.rec or {}, kind="recorder_state", name="m13.recorder", version=1)
        usage = encode_tree(st.usage, kind="sortie_usage", name="integration.usage", version=1)
        header = {
            "format": 1,
            "k": st.world.k,
            "chunk": self.chunk,
            "cir_channels": list(self.cir_channels),
            "m14_feed": self.feed_monitor,
            "started": st.started,
            "ended": st.ended,
            "config_hash": self.ss.system.config_hash,
        }
        return SORTIE_MAGIC + length_prefixed([canonical_json(header), world, rec, usage])

    def restore(self, data: bytes, *, strict: bool = True) -> SortieState:
        if data[: len(SORTIE_MAGIC)] != SORTIE_MAGIC:
            raise ValueError("not a sortie snapshot")
        parts, pos = [], len(SORTIE_MAGIC)
        while pos < len(data):
            m = int.from_bytes(data[pos : pos + 8], "little")
            parts.append(data[pos + 8 : pos + 8 + m])
            pos += 8 + m
        header = json.loads(parts[0].decode("ascii"))
        if header["chunk"] != self.chunk or tuple(header["cir_channels"]) != self.cir_channels:
            raise ValueError("snapshot taken with a different recorder configuration")
        if header["m14_feed"] != self.feed_monitor:
            raise ValueError("snapshot taken with a different M14 feed setting")
        w = core_restore(self.ss.system, parts[1], strict=strict)
        if self.validator is not None:
            from .validate import validating

            w = validating(w, self.validator)
        rec = decode_tree(parts[2], kind="recorder_state").tree if self.recorder is not None else None
        usage = decode_tree(parts[3], kind="sortie_usage").tree
        return SortieState(
            w, dict(rec) if rec is not None else None, dict(usage), header["started"], header["ended"]
        )

    @staticmethod
    def snapshot_id(data: bytes) -> str:
        return digest(data, PERSON_SNAPSHOT)

    # ------------------------------------------------------------------------------------------ results
    def realised_usage(self, st: SortieState):
        """The sortie's realised :class:`phalanx.health.usage.SortieUsage` from truth (finalised LUIs)."""
        from phalanx.health.usage import SortieUsage, lui_finalize, lui_readout

        u = st.usage
        ne = u["lui_f"].shape[0]
        per: dict[str, list[float]] = {
            k: []
            for k in (
                "eot_s",
                "tamp_s",
                "type1",
                "type3",
                "type4",
                "eftc",
                "src_h",
                "ps3_full",
                "ps3_partial",
            )
        }
        for e in range(ne):
            f, _i, _s = lui_finalize(u["lui_f"][e], u["lui_i"][e], u["lui_stack"][e], self._gates)
            r = lui_readout(f)
            for k in per:
                per[k].append(r[k])
        return SortieUsage(
            sortie_id=self.ss.window.sortie_id,
            flight_time_s=float(u["flight_s"][0]),
            ab_lights=tuple(float(x) for x in u["ab_lights"]),
            starts=(1.0,) * ne,
            landings=float(u["landings"][0]),
            gear_cycles=float(u["landings"][0]),
            brake_energy_j=(float(u["brake_j"][0]), float(u["brake_j"][1])),
            nz_counts=tuple(float(c) for c in u["nz_counts"]),
            **{k: tuple(v) for k, v in per.items()},
        )

    def observed_counters(self, st: SortieState) -> dict[str, float]:
        """M14's ``usage.counters`` rows of this sortie (param_id[engine] -> value), from its outbox."""
        from phalanx.monitoring.module import COUNTERS

        mon = self.ss.modules["monitor"]
        ms = st.world.states["monitor"]
        out: dict[str, float] = {}
        _ = (mon, COUNTERS)
        cum = np.asarray(ms["cum"], dtype=np.float64)
        cum0 = np.asarray(ms["cum0"], dtype=np.float64)
        for (pid, e), slot in mon._slots.items():
            out[pid if e < 0 else f"{pid}[{e}]"] = float(cum[slot] - cum0[slot])
        return out


def sortie_digest(results: Sequence[ChunkOutput]) -> str:
    """One digest over the traces and CIR of a run's chunks (determinism tests)."""
    parts = []
    for c in results:
        parts.append(c.trace.digest().encode())
        if c.cir is not None:
            tab = c.cir.table if hasattr(c.cir, "table") else c.cir
            parts.append(canonical_json({"n": tab.num_rows}))
            for name in tab.column_names:
                col = tab.column(name).to_pylist()
                parts.append(json.dumps(col, sort_keys=True, default=str).encode())
    return digest(length_prefixed(parts), PERSON_SNAPSHOT)


__all__ = [
    "AIRBORNE_PHASE_NAMES",
    "ChunkOutput",
    "SortieAborted",
    "SortieResult",
    "SortieRunner",
    "SortieState",
    "sortie_digest",
]

_ = math
