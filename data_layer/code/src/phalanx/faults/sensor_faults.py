"""M11 -> M12 sensor-fault events (AD-42; architecture §7: sensor faults act at ``s_inst`` in M12).

M11 only schedules sensor faults. M12 (``phalanx.sensors.module.apply_sensor_fault``) owns their physics and
state, so a faulty reading takes the same generation path as a healthy one (I6). The event is kind
``sensor_fault`` addressed to the M12 module, with exactly the payload of :func:`sensor_fault_payload`:

| key | meaning |
|---|---|
| ``channel`` | dictionary channel id (an entry of M12's ``SensorConfig.bias_index()``) |
| ``mode`` | ``bias, drift, stuck, open, short, intermittent, spikes, slow, probe_open, probe_short, clear`` |
| ``value`` | SI: bias step; drift rate per second; short reading; spike amplitude; probe short |
| | reading; for ``slow`` the time-constant multiplier (>= 1) |
| ``rate`` | 1/s: spike rate, or mean intermittent state changes per second |
| ``duty`` | intermittent long-run open fraction, in (0, 1) |
| ``probe`` | harness probe index (probe modes), -1 otherwise |

M12 semantics: ``open`` reads the bottom of the channel's range, ``intermittent`` drops out to that reading
for a two-state Markov fraction ``duty`` of the time, and ``drift`` is unbounded; M11 bounds a drift by
switching it to a ``bias`` of the bound when the drift reaches it (``faults.sensor_hold``).
"""

from __future__ import annotations

import math

__all__ = [
    "PROBE_MODES",
    "SENSOR_FAULT_EVENT",
    "SENSOR_FAULT_KEYS",
    "SENSOR_FAULT_MODES",
    "intermittent_rate_duty",
    "sensor_fault_payload",
]

#: event kind M12 handles (``phalanx.sensors.module.SENSOR_FAULT_EVENT``; equality is tested)
SENSOR_FAULT_EVENT = "sensor_fault"
#: the payload keys, exactly (AD-42)
SENSOR_FAULT_KEYS = ("channel", "mode", "value", "rate", "duty", "probe")
SENSOR_FAULT_MODES = (
    "bias",
    "drift",
    "stuck",
    "open",
    "short",
    "intermittent",
    "spikes",
    "slow",
    "probe_open",
    "probe_short",
    "clear",
)
PROBE_MODES = ("probe_open", "probe_short")


def sensor_fault_payload(
    channel: str,
    mode: str,
    *,
    value: float = 0.0,
    rate: float = 0.0,
    duty: float = 0.5,
    probe: int = -1,
) -> dict[str, object]:
    """The AD-42 ``sensor_fault`` payload, checked against M12's acceptance rules before it is sent."""
    if mode not in SENSOR_FAULT_MODES:
        raise ValueError(f"unknown sensor-fault mode {mode!r}")
    value, rate, duty = float(value), float(rate), float(duty)
    if not (math.isfinite(value) and math.isfinite(rate) and math.isfinite(duty)):
        raise ValueError("sensor-fault value, rate and duty must be finite")
    if mode in ("spikes", "intermittent") and not rate > 0.0:
        raise ValueError(f"{mode} needs rate > 0 (1/s)")
    if mode == "intermittent" and not 0.0 < duty < 1.0:
        raise ValueError("intermittent duty must be in (0, 1)")
    if mode == "slow" and value < 1.0:
        raise ValueError("slow-response multiplier must be >= 1")
    if (mode in PROBE_MODES) != (probe >= 0):
        raise ValueError(f"{mode}: probe index {probe} (needed for probe modes only)")
    return {
        "channel": str(channel),
        "mode": mode,
        "value": value,
        "rate": rate,
        "duty": duty,
        "probe": int(probe),
    }


def intermittent_rate_duty(on_rate: float, off_rate: float) -> tuple[float, float]:
    """(rate, duty) of M12's intermittent mode from the two transition rates of a two-state Markov chain.

    ``on_rate`` is normal -> open per second, ``off_rate`` open -> normal. M12's dwell means are
    ``2 (1 - duty) / rate`` (normal) and ``2 duty / rate`` (open), so ``duty = on / (on + off)`` and
    ``rate = 2 on off / (on + off)``.
    """
    if not (on_rate > 0.0 and off_rate > 0.0):
        raise ValueError("transition rates must be > 0")
    s = on_rate + off_rate
    return 2.0 * on_rate * off_rate / s, on_rate / s
