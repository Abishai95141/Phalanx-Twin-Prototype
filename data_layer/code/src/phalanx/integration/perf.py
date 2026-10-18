"""A9 performance measurement of the telemetry truth loop (us per 240 Hz truth step, one tail).

Four measurements, each the **best of** ``repeats`` (the minimum is the least load-sensitive estimate on a
shared machine; the load average is recorded with the table):

1. ``per_step``: each continuous module's own ``step`` (``step_block`` with L = 1, Python wrapper included),
   on its inputs and state from a running System: the cost of the per-step segment path, module by module
   (what E1 measured as F2).
2. ``kernel``: each module's compiled kernel alone with L = 1, called from inside an ``@njit`` loop (no Python
   dispatch): the in-loop cost of the module in the fused group.
3. ``fused``: the fused group's compiled loop per executed step, and the whole fused ``step_block`` per step
   (with its per-block Python precomputation and output assembly), over a block of ``block`` steps.
4. ``system``: ``System.run`` per net step (block mode, events and cuts included) and the ``SortieRunner`` per
   step (adds the recorder, the M14 feed and the realised-usage accumulators); with ``unfused`` (the same
   sortie built with ``fused=False``), also ``System.run`` on the per-step segment path: the cost before
   fusing.

The floor (owner scope change, coordinator AD-55) is **>= 5x real time for the whole Tejas aircraft in
telemetry mode**: 1 / (240 x 5) s = 833 us per truth step for one tail, judged on the ``SortieRunner`` (the
whole aircraft: truth loop, recorder, M14 feed, usage). The system-level rows are timed both in wall-clock
and in process CPU time: on a CPU shared with other jobs the wall clock includes time spent waiting for a
core, the CPU time is the cost of the step itself (the runner is single-threaded). The real-time factor is
(1/240 s) / (time per step).
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

FLOOR_US = 1e6 / (240.0 * 5.0)  # >= 5x real time, whole aircraft, one tail (AD-55)
STEP_US = 1e6 / 240.0
RUNNER_KEY = "SortieRunner (whole aircraft, 10 s)"
UNFUSED_KEY = "System.run per-step path (unfused, 1 s)"
CYCLE = 12  # truth steps per common 60 Hz / 80 Hz frame period (240/60 = 4, 240/80 = 3)


@dataclass
class PerfTable:
    per_step: dict[str, float] = field(default_factory=dict)
    kernel: dict[str, float] = field(default_factory=dict)
    fused: dict[str, float] = field(default_factory=dict)
    system: dict[str, float] = field(default_factory=dict)
    system_cpu: dict[str, float] = field(default_factory=dict)
    load: tuple[float, float, float] = (0.0, 0.0, 0.0)
    context: dict[str, Any] = field(default_factory=dict)

    def render(self) -> str:
        la = " ".join(f"{x:.1f}" for x in self.load)
        lines = [f"load average {la}; floor {FLOOR_US:.1f} us/step (>= 5x real time, whole aircraft)"]
        lines.append(f"{'module':12s} {'per-step path':>14s} {'in-loop kernel':>15s}")
        for m in self.per_step:
            lines.append(f"{m:12s} {self.per_step[m]:14.1f} {self.kernel.get(m, float('nan')):15.2f}")
        lines.append(f"{'sum':12s} {sum(self.per_step.values()):14.1f} {sum(self.kernel.values()):15.2f}")
        for k, v in self.fused.items():
            lines.append(f"{k:42s} wall {v:9.1f} us/step")
        for k, v in self.system.items():
            cpu = self.system_cpu.get(k, float("nan"))
            lines.append(
                f"{k:42s} wall {v:9.1f} us/step ({STEP_US / v:5.1f}x real time); "
                f"CPU {cpu:9.1f} us/step ({STEP_US / cpu:5.1f}x)"
            )
        return "\n".join(lines)


def _best(fn: Callable[[], float], repeats: int) -> float:
    return min(fn() for _ in range(repeats))


def _best2(fn: Callable[[], None], steps: int, repeats: int) -> tuple[float, float]:
    """Best-of (wall, CPU) microseconds per step of ``fn`` (each minimum taken separately)."""
    walls, cpus = [], []
    for _ in range(repeats):
        w0 = time.perf_counter()  # audit: allow R4 benchmark timing
        c0 = time.process_time()  # audit: allow R4 benchmark timing
        fn()
        cpus.append((time.process_time() - c0) / steps * 1e6)  # audit: allow R4 benchmark timing
        walls.append((time.perf_counter() - w0) / steps * 1e6)  # audit: allow R4 benchmark timing
    return min(walls), min(cpus)


def _inputs_from_world(system, world, mid: str) -> dict[str, np.ndarray]:
    return {e.dst_port: np.asarray(world.held[e.src]) for e in system._in_edges[mid]}


def measure(
    ss, *, unfused=None, warm_s: float = 20.0, block: int = 240, repeats: int = 5, calls: int = 200
) -> PerfTable:
    """All four measurements on a built ``SortieSystem`` (``fused=True``) after ``warm_s`` of flight;
    ``unfused``: the same sortie built with ``fused=False`` (per-step path, 1 s after 1 s of warm-up)."""
    from numba import njit

    from phalanx.core.time import truth_step_time_ns

    from . import fused as FU
    from .sortie import SortieRunner
    from .system import CONTINUOUS_ORDER

    tab = PerfTable(load=os.getloadavg())  # audit: allow R4 load average (benchmark context only)
    sysm = ss.system
    w = sysm.inject(ss.start(), ss.bootstrap_events())
    w, _ = sysm.run(w, round(warm_s * 240))
    # ---- 1 and 2: per module. Kernel calls are counted over CYCLE consecutive steps (one 60 Hz and 80 Hz
    # frame period): an acquisition lane calls its kernel only in steps that open a frame.
    captured: dict[str, tuple] = {}
    calls_per_step: dict[str, float] = {}
    t_cycle = np.array([truth_step_time_ns(w.k + j) for j in range(CYCLE)], np.int64)
    for mid in CONTINUOUS_ORDER:
        mod = sysm.modules[mid]
        inp = {k: v[None, ...] for k, v in _inputs_from_world(sysm, w, mid).items()}
        real = mod._kernel
        count = [0]

        def cap(*args, _real=real, _mid=mid, _count=count, **kw):
            captured.setdefault(_mid, args)
            _count[0] += 1
            return _real(*args, **kw)

        # the state advances with the step (a module's clock and frame schedule live in its state)
        sts = [w.states[mid]]
        mod._kernel = cap
        try:
            for j in range(CYCLE):
                sts.append(mod.step_block(sts[j], inp, t_cycle[j : j + 1], 1.0 / 240.0)[0])
        finally:
            mod._kernel = real
        calls_per_step[mid] = count[0] / CYCLE

        def one(_mod=mod, _sts=sts, _inp=inp) -> float:
            t0 = time.perf_counter()  # audit: allow R4 benchmark timing
            for c in range(calls):
                j = c % CYCLE
                _mod.step_block(_sts[j], _inp, t_cycle[j : j + 1], 1.0 / 240.0)
            return (time.perf_counter() - t0) / calls * 1e6  # audit: allow R4 benchmark timing

        tab.per_step[mid] = _best(one, repeats)
    kernels = {
        "env": FU.env_kernel, "pilot": FU.pilot_kernel, "fadec": FU.fadec_block, "eng": FU.engine_kernel,
        "af": FU.airframe_kernel, "util": FU.utilities_kernel, "sens": FU.m12_kernel,
        "acq_fadec": FU.acq_kernel, "acq_dfcc": FU.acq_kernel, "fcs": FU.fcs_kernel,
    }  # fmt: skip
    for mid, args in captured.items():
        kern = kernels[mid]

        @njit(cache=False)
        def bench(r, a, _k=kern):
            out = _k(*a)
            for _ in range(r - 1):
                out = _k(*a)
            return out

        bench(2, tuple(args))

        def one_k(_b=bench, _a=tuple(args)) -> float:
            t0 = time.perf_counter()  # audit: allow R4 benchmark timing
            _b(calls * 10, _a)
            return (time.perf_counter() - t0) / (calls * 10) * 1e6  # audit: allow R4 benchmark timing

        tab.kernel[mid] = _best(one_k, repeats) * calls_per_step[mid]
    # ---- 3: the fused group over one block (no event inside: the timing of the loop itself)
    seg = next(g for g in sysm._segments if g.fused is not None)
    group = seg.fused
    orig = FU._truth_loop
    acc = {"loop": 0.0, "steps": 0}

    def timed(*a):
        t0 = time.perf_counter()  # audit: allow R4 benchmark timing
        r = orig(*a)
        acc["loop"] += time.perf_counter() - t0  # audit: allow R4 benchmark timing
        acc["steps"] += a[0]
        return r

    ks = np.arange(w.k, w.k + block, dtype=np.int64)
    members = group.members
    ext = {}
    for mid in members:
        for e in sysm._in_edges[mid]:
            if e.src_mod not in members:
                ext[e.dst] = np.broadcast_to(np.asarray(w.held[e.src]), (block, *np.shape(w.held[e.src])))
    h0 = {f"{m}.{p.name}": w.held[f"{m}.{p.name}"] for m in members for p in sysm.modules[m].ports_out}
    states = {m: w.states[m] for m in members}
    FU._truth_loop = timed
    try:

        def one_block() -> float:
            t0 = time.perf_counter()  # audit: allow R4 benchmark timing
            group.step_block(states, ext, h0, ks, 1.0 / 240.0)
            return (time.perf_counter() - t0) / block * 1e6  # audit: allow R4 benchmark timing

        tab.fused[f"fused step_block (block {block})"] = _best(one_block, repeats)
        acc["loop"], acc["steps"] = 0.0, 0
        best_loop = []
        for _ in range(repeats):
            acc["loop"], acc["steps"] = 0.0, 0
            group.step_block(states, ext, h0, ks, 1.0 / 240.0)
            best_loop.append(acc["loop"] / acc["steps"] * 1e6)
        tab.fused["fused compiled loop only"] = min(best_loop)
    finally:
        FU._truth_loop = orig

    # ---- 4: System.run and the runner (wall and CPU)
    rep = max(2, repeats // 2)
    key = "System.run (block mode, 10 s)"
    tab.system[key], tab.system_cpu[key] = _best2(lambda: sysm.run(w, 10 * 240), 2400, rep)
    r = SortieRunner(ss)
    st = r.begin()
    st, _ = r.run(st, round(warm_s * 240) // 240 * 240)
    key = RUNNER_KEY
    tab.system[key], tab.system_cpu[key] = _best2(lambda: r.run(st, 10 * 240), 2400, rep)
    if unfused is not None:
        su = unfused.system
        wu = su.inject(unfused.start(), unfused.bootstrap_events())
        wu, _ = su.run(wu, 240)
        key = UNFUSED_KEY
        tab.system[key], tab.system_cpu[key] = _best2(lambda: su.run(wu, 240), 240, 2)
    tab.context = {"warm_s": warm_s, "block": block, "repeats": repeats, "calls": calls,
                   "kernel_calls_per_step": calls_per_step}  # fmt: skip
    return tab


__all__ = ["FLOOR_US", "RUNNER_KEY", "STEP_US", "UNFUSED_KEY", "PerfTable", "measure"]
