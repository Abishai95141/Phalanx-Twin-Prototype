"""A7: the closed-loop coupling API of M08 (how the real M07, M12/M13 and M04/M03 plug in; W2.1 wiring).

M08 talks to the rest of the truth loop **only through its catalogue ports** (`ports.py`), so replacing the W1
test-fixture plant by the real M07 needs no change in M08. The loop is:

```text
 step k (Gauss-Seidel order):  ... -> FADEC (M08) -> engine (M07) -> ... -> sensors/lanes (M12/M13 in-loop)
                                       ^                                              |
                                       +---- lane buffers, delayed edge (back-edge) --+
```

**Contract for the in-loop lane source (M12/M13 `LaneAcquisition`, W1.6; AD-42):**
1. At truth step k it produces, for every FADEC lane channel (`ports.LANE_PORTS`, bound `lane.<channel_id>`),
   the readings at the FADEC frame instants in [t_k, t_{k+1}): truth interpolated between x_k (engine output
   at the start of step k, i.e. a delayed edge from M07) and x_{k+1} (engine output of step k), through the
   measurement chain, quantised in EU and converted to SI (`Dictionary.eu_to_si`).
2. It writes them to sample buffers in frame order (M13 port `lane_<id>` =
   `acquisition.module.lane_port(cid)`,
   shape `(capacity,)` for one engine; `(capacity, n_engines)` for a multi-engine proxy), slots >= n
   meaningless, using the **same clock** as M08: `ports.DEFAULT_CLOCK` is M13's
   `acquisition_clock("FADEC", 60)`. `lane_frames(clock, n_next, k)` returns those frames and interpolation
   weights; M08 recomputes the same frames for [t_{k-1}, t_k) at step k+1 (`Fadec.frame_schedule`). M08 reads
   only the value port; the companion `_t`, `_n`, `_first`, `_q` ports are not needed (same clock).
3. M08 reads the buffers through a delayed (back-)edge, so step k+1 processes the frames of [t_k, t_{k+1}) and
   its commands apply from t_{k+1}: the first truth frame after each compute instant (architecture §8).

**Contract for the engine (M07, W1.3a):** consume the catalogue commands `fadec.wf_cmd`, `fadec.wf_ab_cmd`,
`fadec.a8_cmd`, `fadec.vg_cmd`, `fadec.ignition` (bit 0 main igniters, bit 1 AB igniter) and `fadec.ab_enable`
on a forward (non-delayed) edge in the same step; declare them in its `bindings`. Process disturbances
(`env.w_engine`) enter M07's dynamics, never M08 (AD-32).

**Fused groups (W2.1):** the pure kernel `kernel.fadec_block(f, i, p, tables, cfg, dt, pla, p0, at_engage,
at_n1_cmd, lanes, n_frames)` and `Fadec.config` (p, tables, cfg, dt) are the compiled entry point; a fused
step_block calls it with L = 1 per truth step inside the loop (see `tests/fadec_fixture.py::_closed_loop`,
which
the A7 test proves bitwise equal to the System wiring).
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from phalanx.core.sampling import StepSamples, samples_for_steps
from phalanx.core.scheduler import Connection
from phalanx.core.time import ClockDomain, truth_interp_weights, truth_step_times_ns

from .ports import LANE_PORTS, PREFIX

LANE_EDGE_NOTE = (
    "FADEC lane back-edge (M08 W1.3b coupling contract): frames in [t_k, t_k+1) sampled at the end of step k "
    "are processed by M08 at step k+1; commands apply from t_k+1 (architecture §8, A-W1.3b-1)"
)


def lane_port_name(channel_id: str) -> str:
    """M13's lane value-port name of a dictionary channel (``ENG.N2.A`` -> ``lane_eng_n2_a``)."""
    from phalanx.acquisition.module import lane_port

    return lane_port(channel_id)


def lane_frames(clock: ClockDomain, n_next: int, k: int) -> tuple[StepSamples, np.ndarray]:
    """FADEC frames in [t_k, t_{k+1}) and their truth-interpolation weights toward x_{k+1} (A-W0.2-2).

    `n_next` is the lane source's next frame index (state; start at `clock.first_index_at_or_after(0)`); store
    `samples.next_index` back.
    """
    t0, t1 = truth_step_times_ns(np.array([k, k + 1], dtype=np.int64))
    ss = samples_for_steps(clock, int(n_next), np.array([t0]), np.array([t1]))
    if ss.times.size:
        _, w = truth_interp_weights(ss.times)
    else:
        w = np.empty(0, dtype=np.float64)
    return ss, w


def fadec_input_connections(
    fadec_id: str,
    bindings: Mapping[str, str],
    producers: Mapping[str, str],
    lane_source_id: str,
    lane_ports: Mapping[str, str] | None = None,
) -> list[Connection]:
    """Connections into M08 from its `bindings` (as returned by `ports.ports`).

    producers: catalogue prefix -> module id, e.g. {"pilot": "m04", "env": "m03"}.
    lane_ports: dictionary channel id -> lane-source output port (default: M13's naming,
        `acquisition.module.lane_port(cid)`, e.g. `ENG.N2.A` -> `lane_eng_n2_a`).
    Lane edges are delayed back-edges carrying `LANE_EDGE_NOTE`.
    """
    lane_ports = (
        {cid: lane_port_name(cid) for _n, cid, _u in LANE_PORTS} if lane_ports is None else dict(lane_ports)
    )
    out: list[Connection] = []
    for port, signal in bindings.items():
        if signal.startswith("lane."):
            cid = signal.split(".", 1)[1]
            out.append(
                Connection(f"{lane_source_id}.{lane_ports[cid]}", f"{fadec_id}.{port}", True, LANE_EDGE_NOTE)
            )
        else:
            prefix, name = signal.split(".", 1)
            if prefix not in producers:
                raise KeyError(f"no producer module given for catalogue prefix {prefix!r} ({signal})")
            out.append(Connection(f"{producers[prefix]}.{name}", f"{fadec_id}.{port}"))
    return out


def command_connections(
    fadec_id: str, consumer_id: str, consumer_bindings: Mapping[str, str]
) -> list[Connection]:
    """Forward edges from M08 to a consumer (M07, M14, ...) for each input bound to `fadec.<port>`."""
    out = []
    for port, signal in consumer_bindings.items():
        prefix, name = signal.split(".", 1)
        if prefix == PREFIX:
            out.append(Connection(f"{fadec_id}.{name}", f"{consumer_id}.{port}"))
    return out


__all__ = [
    "LANE_EDGE_NOTE",
    "command_connections",
    "fadec_input_connections",
    "lane_frames",
    "lane_port_name",
]
