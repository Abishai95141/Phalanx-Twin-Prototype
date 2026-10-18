"""B8-CHAIN1 (PREREGISTRATION.md §4): engine lube anomaly -> BIT -> work order -> repair, reported as measured
with its known limitation (M18 has no oil-pressure-transmitter position; anchor about 3 h, same day, with
parts).

No lube-anomaly instance occurred in the 16 B8 worlds (rare modes over 180 days each), so the chain is driven
in a one-tail operations world (``fleet.OneTailWorld``, mature regime, the same world as B8-CHAIN3): at a
ground instant on day 2 M11 receives ``faults.inject`` FM.SNS.OIL_P_TRANSMITTER (false-low oil-pressure
reading, covered, severity 1). From there everything is the real M11 (usage-mode detection edge ECM-702),
M14 (the code's test at the next sortie, download), M18 (work order, troubleshooting, repair) and M02. A
reference world with the same root and no injection gives the baseline.

Reported: the BIT records of the code, the work order(s) M18 opens for them (system, action taken, open and
close times), the tail's availability while they are open, and the sorties lost against the reference world.
n = 1 world and 1 injection per M14 configuration: the route is deterministic given the root; the duration is a
single measured value, not a statistic. Two configurations (DEVIATIONS D7): the operations-world M14 as
pre-registered (telemetry configuration: only internal codes are tests, so the usage-mode detection stand-in
on ECM-702, a CIR code, is never evaluated) and M14 in usage mode (every code a test, A-W1.5-26).

Usage: python -I chain1.py OUT_DIR
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import chain3 as C3  # noqa: E402
import fleet as F  # noqa: E402

from phalanx.core.events import Event  # noqa: E402
from phalanx.fork.session import OpsSession  # noqa: E402
from phalanx.monitoring.module import KIND_BIT, KIND_EXCEED  # noqa: E402

NS = 10**9
DAY = 86_400 * NS
MODE = "FM.SNS.OIL_P_TRANSMITTER"
CODES = ("ECM-702", "ENG-012")


def _latest(s: OpsSession) -> list[dict]:
    last: dict[str, dict] = {}
    for r in s.records("maint.records"):
        k = f"{r['record_type']}|{r['record_key']}"
        if k not in last or int(r["record_version"]) >= int(last[k]["record_version"]):
            last[k] = r
    return list(last.values())


def run_one(um: bool) -> dict:
    world = F.OneTailWorld(C3.WORLD_K, C3.DAYS, C3.REGIME, m14_usage_mode=um)
    epoch = world.epoch_utc_ns
    ref = OpsSession(world, C3.ROOT)
    ref.run_until(C3.DAYS * DAY)
    ref_sorties = C3._sorties(ref, epoch)
    t_inj = C3._ground_time(ref_sorties, 2 * DAY, 3600 * NS)

    s = OpsSession(F.OneTailWorld(C3.WORLD_K, C3.DAYS, C3.REGIME, m14_usage_mode=um), C3.ROOT)
    s.run_until(t_inj)
    pay = {"mode": MODE, "severity": 1.0, "covered": True}
    s.world = s.system.inject(s.world, [Event(t_inj, "faults.inject", "m11", pay, source="chain1")])
    s.run_until(C3.DAYS * DAY)
    sorties = C3._sorties(s, epoch)

    m14 = s.system.modules["m14"]
    st = s.world.states["m14"]
    codes = m14.config.codes.codes
    bits = [
        {"code": codes[int(c)].code, "t_h_after_injection": (int(t) - t_inj) / NS / 3600.0}
        for c, k, t in zip(st["o_code"], st["o_kind"], st["o_t"], strict=True)
        if int(k) in (KIND_BIT, KIND_EXCEED) and int(t) >= t_inj and codes[int(c)].code in CODES
    ]
    av = C3._availability(s, epoch)
    ref_jobs = {r["record_key"] for r in _latest(ref) if r["record_type"] == "DEFECT_WO"}
    jobs = []
    for r in _latest(s):
        if r["record_type"] != "DEFECT_WO" or r["record_key"] in ref_jobs or r.get("t_open") is None:
            continue
        t_open = C3._kernel(r["t_open"], epoch)
        if t_open < t_inj:
            continue
        t_close = C3._kernel(r["t_close"], epoch) if r.get("t_close") is not None else None
        jobs.append(
            {
                "system_code": r.get("system_code"),
                "when_discovered": r.get("when_discovered"),
                "malfunction_code": r.get("malfunction_code"),
                "action_taken_code": r.get("action_taken_code"),
                "status": r.get("status"),
                "t_open_h_after_injection": (t_open - t_inj) / NS / 3600.0,
                "duration_h": None if t_close is None else (t_close - t_open) / NS / 3600.0,
                "availability_at_open_plus_1h": av(t_open + 3600 * NS),
            }
        )
    f11 = s.world.states["m11"]
    res = {
        "n_worlds": 1,
        "world": {"tail": world.tail, "regime": C3.REGIME, "days": C3.DAYS, "root": C3.ROOT},
        "injection_day": t_inj / DAY,
        "mode": MODE,
        "m11_instances_open_at_end": int(sum(1 for t1 in f11["inst_t1"] if int(t1) < 0)),
        "bit_records": bits,
        "new_work_orders": sorted(jobs, key=lambda j: j["t_open_h_after_injection"]),
        "sorties_reference": len(ref_sorties),
        "sorties_with_fault": len(sorties),
        "limitation": "M18 has no oil-pressure-transmitter position (request to W2.6): the transmitter cannot be "
        "replaced at its own position, so troubleshooting ends on another engine position or as could-not-duplicate",
        "anchor": "about 3 h, same day, with parts (PREREGISTRATION §4)",
        "m14_config": "usage mode (D7)" if um else "pre-registered (telemetry)",
    }
    return res


def run(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    res = {"pre_registered_config": run_one(False), "usage_mode_d7": run_one(True)}
    (out / "b8_chain1.json").write_text(json.dumps(res, indent=1, sort_keys=True, default=str), encoding="utf-8")
    return res


if __name__ == "__main__":
    print(json.dumps(run(Path(sys.argv[1])), indent=1, default=str))
