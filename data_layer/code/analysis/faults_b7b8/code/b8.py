"""B8 event behaviour at fleet scale in usage mode (PREREGISTRATION.md §4).

8 one-tail operations worlds (TJ101-TJ108) x 180 days per BIT regime (immature, mature); real M02, M18, M21,
sink, M10, M11 (stochastic) and M14. Per world the run keeps M14's outbox (every BIT/caution record with its
time, code and sortie), M11's fault instances (mode, onset, clear, covered) and the maint.records rows.

Truth matching (pre-registered): a BIT record is a true detection iff an M11 instance active at its time lists
its code (the mode's detection codes, or a monitoring code of a graph node reachable from the mode's root);
otherwise it is a false alarm.

Usage: python -I b8.py run OUT_DIR [--workers 2] ; python -I b8.py analyse OUT_DIR
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import fleet as F  # noqa: E402

from phalanx.faults import load_catalogue, load_graph  # noqa: E402
from phalanx.monitoring import load_code_table, load_monitoring_params  # noqa: E402
from phalanx.monitoring.codes import MECHANISMS  # noqa: E402
from phalanx.monitoring.module import KIND_BIT  # noqa: E402

NS = 10**9
N_WORLDS, DAYS = 8, 180
ROOTS = {"immature": 0xB801, "mature": 0xB802}
BANDS = {
    "fa_rate_immature": (1.0, 10.0),
    "fa_rate_mature_max": 0.02,
    "fa_share_immature": (0.86, 0.999),
    "fa_share_mature": (0.22, 0.53),
    "persist_ge3": (0.10, 0.18),
    "persist_eq1": (0.67, 0.81),
    "nff_rtok": (0.25, 0.63),
    "cnd": (0.22, 0.54),
}


def instance_codes() -> dict[str, set[str]]:
    """Codes each mode can raise: its detection codes and the monitoring codes of graph nodes reachable from
    its root (cascade)."""
    cat, g = load_catalogue(), load_graph()
    out = {}
    for mid, m in cat.items():
        codes = set(m.codes) | {str(e.fields["code"]) for e in m.effects if e.target == "monitoring"}
        if m.graph_root:
            seen, todo = set(), [m.graph_root]
            while todo:
                n = todo.pop()
                if n in seen:
                    continue
                seen.add(n)
                codes |= {str(e["code"]) for e in g.nodes[n].effects if e.get("target") == "monitoring"}
                todo += [e.dst for e in g.out_edges(n)]
        out[mid] = {c for c in codes if not c.endswith("*")} | {
            c2 for c in codes if c.endswith("*") for c2 in m.codes if c2.startswith(c[:-1])
        }
    return out


def _sfx(um: bool) -> str:
    """Result-file suffix: "_um" for the DEVIATIONS D7 run (M14 in usage mode: every code a test)."""
    return "_um" if um else ""


def world_job(job: tuple[str, int, bool]) -> dict:
    regime, k, um = job
    s = F.run_world(k, DAYS, regime, ROOTS[regime], m14_usage_mode=um)
    st, f11 = s.world.states["m14"], s.world.states["m11"]
    codes = load_code_table(F.load_dictionary(), load_monitoring_params())
    mode_ids = list(load_catalogue())
    recs = s.records("maint.records")
    last: dict[str, dict] = {}
    for r in recs:
        key = f"{r['record_type']}|{r['record_key']}"
        if key not in last or int(r["record_version"]) >= int(last[key]["record_version"]):
            last[key] = r
    keep = ("record_type", "action_taken_code", "malfunction_code", "when_discovered", "shop_finding", "status",
            "t_open", "t_close", "flight_hours", "sortie_id", "system_code", "job_no", "type_maint_code",
            "inspection_type", "t_event")
    rows = [{k2: r.get(k2) for k2 in keep} for r in last.values()]
    sel = st["o_kind"] == KIND_BIT
    return {
        "regime": regime,
        "k": k,
        "tail": F.OneTailWorld(k, DAYS, regime).tail,
        "bit": {
            "code": [codes.codes[int(c)].code for c in st["o_code"][sel]],
            "t": [int(x) for x in st["o_t"][sel]],
            "sortie": [str(x) for x in st["o_sortie"][sel]],
            "mech": [MECHANISMS[int(x)] for x in st["o_mech"][sel]],
        },
        "faults": {
            "mode": [mode_ids[int(m)] for m in f11["inst_mode"]],
            "t0": [int(x) for x in f11["inst_t0"]],
            "t1": [int(x) for x in f11["inst_t1"]],
            "covered": [int(x) for x in f11["inst_covered"]],
        },
        "records": rows,
        "m14_power_cycles": int(st["clock"][0]),
    }


def run(out: Path, workers: int, um: bool = False) -> None:
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"b8_worlds{_sfx(um)}.jsonl"
    done = {(d["regime"], d["k"]) for d in map(json.loads, p.read_text().splitlines())} if p.exists() else set()
    todo = [(r, k, um) for r in ROOTS for k in range(N_WORLDS) if (r, k) not in done]
    with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as ex:
        for res in ex.map(world_job, todo):
            with open(p, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(res, sort_keys=True) + "\n")
            print(f"{res['regime']} {res['k']} done: {len(res['bit']['code'])} BIT", flush=True)


def _poisson_ci(k: int) -> tuple[float, float]:
    from scipy import stats

    lo = 0.0 if k == 0 else stats.chi2.ppf(0.025, 2 * k) / 2
    return float(lo), float(stats.chi2.ppf(0.975, 2 * k + 2) / 2)


def _wilson(k: int, n: int) -> tuple[float, float, float]:
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    from scipy import stats

    z = stats.norm.ppf(0.975)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, float(c - h), float(c + h)


def _overlap(ci: tuple[float, float, float], band: tuple[float, float]) -> str:
    _, lo, hi = ci
    if not np.isfinite(lo):
        return "FAIL (no data)"
    return "PASS" if (hi >= band[0] and lo <= band[1]) else "FAIL"


def analyse(out: Path, um: bool = False) -> dict:
    worlds = [json.loads(s) for s in (out / f"b8_worlds{_sfx(um)}.jsonl").read_text().splitlines()]
    icodes = instance_codes()
    res: dict = {"n_worlds": Counter(w["regime"] for w in worlds), "regimes": {}}
    for regime in ROOTS:
        ws = [w for w in worlds if w["regime"] == regime]
        fh = 0.0
        n_bit = n_false = 0
        episodes = []
        shop = Counter()
        jobs = Counter()
        admin_days = []
        admin_flights = Counter()  # B8-CHAIN2: monitored flights between opening and administrative close
        n_sorties = 0
        for w in ws:
            srt = sorted((r["t_open"], r["sortie_id"], r["flight_hours"]) for r in w["records"]
                         if r["record_type"] == "SORTIE" and r["flight_hours"] is not None)
            fh += sum(x[2] for x in srt)
            n_sorties += len(srt)
            order = {sid: i for i, (_, sid, _) in enumerate(srt)}
            f = w["faults"]
            false_flights = defaultdict(set)
            for code, t, sid in zip(w["bit"]["code"], w["bit"]["t"], w["bit"]["sortie"], strict=True):
                n_bit += 1
                true = any(
                    code in icodes[m] and t0 <= t and (t1 < 0 or t <= t1)
                    for m, t0, t1 in zip(f["mode"], f["t0"], f["t1"], strict=True)
                )
                if not true:
                    n_false += 1
                    if sid in order:
                        false_flights[code].add(order[sid])
            for flights in false_flights.values():
                fl = sorted(flights)
                run_len = 1
                for a, b in zip(fl, fl[1:], strict=False):
                    if b == a + 1:
                        run_len += 1
                    else:
                        episodes.append(run_len)
                        run_len = 1
                episodes.append(run_len)
            for r in w["records"]:
                if r["record_type"] == "SHOP_FINDING" and r["shop_finding"]:
                    shop[r["shop_finding"]] += 1
                if r["record_type"] == "DEFECT_WO" and r["when_discovered"] in ("WD-HMS", "WD-DBF", "WD-AIR"):
                    jobs[r["action_taken_code"]] += 1
                    if r["action_taken_code"] == "AT-ADM" and r["t_close"] and r["t_open"]:
                        admin_days.append((int(r["t_close"]) - int(r["t_open"])) / NS / 86400.0)
                        to, tc = int(r["t_open"]), int(r["t_close"])
                        admin_flights[sum(1 for x in srt if to < int(x[0]) <= tc)] += 1
        lo, hi = _poisson_ci(n_false)
        ep = np.array(episodes)
        troubleshot = sum(v for k2, v in jobs.items() if k2 not in ("AT-DEF", "AT-ADM", None))
        reg: dict = {
            "worlds": len(ws),
            "sorties": n_sorties,
            "flight_hours": fh,
            "bit_records": n_bit,
            "false_alarms": n_false,
            "fa_per_fh": n_false / fh if fh else float("nan"),
            "fa_per_fh_ci95": [lo / fh, hi / fh] if fh else None,
            "fa_share": _wilson(n_false, n_bit),
            "episodes": int(ep.size),
            "persist_ge3": _wilson(int((ep >= 3).sum()), int(ep.size)),
            "persist_eq1": _wilson(int((ep == 1).sum()), int(ep.size)),
            "shop_findings": dict(shop),
            "nff_rtok": _wilson(shop.get("RTOK", 0), sum(shop.values())),
            "bit_pilot_jobs_final_action": dict(jobs),
            "cnd": _wilson(jobs.get("AT-CND", 0), troubleshot),
            "admin_close_days_median": float(np.median(admin_days)) if admin_days else None,
            "admin_closes": len(admin_days),
            "admin_close_days_q10_q90": [float(np.percentile(admin_days, 10)), float(np.percentile(admin_days, 90))]
            if admin_days
            else None,
            "admin_close_flights": dict(admin_flights),
            "verdict_chain2": "PASS" if admin_flights and set(admin_flights) == {3} else "FAIL",
        }
        if regime == "immature":
            reg["verdict_fa_rate"] = "PASS" if (fh and BANDS["fa_rate_immature"][0] <= lo / fh
                                                and hi / fh <= BANDS["fa_rate_immature"][1]) else "FAIL"
            reg["verdict_fa_share"] = _overlap(reg["fa_share"], BANDS["fa_share_immature"])
            reg["verdict_persist_ge3"] = _overlap(reg["persist_ge3"], BANDS["persist_ge3"])
            reg["verdict_persist_eq1"] = _overlap(reg["persist_eq1"], BANDS["persist_eq1"])
        else:
            reg["verdict_fa_rate"] = "PASS" if (fh and hi / fh <= BANDS["fa_rate_mature_max"]) else "FAIL"
            reg["verdict_fa_share"] = _overlap(reg["fa_share"], BANDS["fa_share_mature"])
        reg["verdict_nff"] = _overlap(reg["nff_rtok"], BANDS["nff_rtok"])
        reg["verdict_cnd"] = _overlap(reg["cnd"], BANDS["cnd"])
        res["regimes"][regime] = reg
    res["m14_config"] = "usage mode, every code a test (DEVIATIONS D7)" if um else "pre-registered (telemetry)"
    res["fault_instances"] = {
        r: {
            "n": sum(len(w["faults"]["mode"]) for w in worlds if w["regime"] == r),
            "persistent": sum(1 for w in worlds if w["regime"] == r for t1 in w["faults"]["t1"] if t1 < 0),
            "modes": dict(Counter(m for w in worlds if w["regime"] == r for m in w["faults"]["mode"])),
        }
        for r in ROOTS
    }
    (out / f"b8{_sfx(um)}.json").write_text(json.dumps(res, indent=1, sort_keys=True, default=str), encoding="utf-8")
    return res


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("run", "analyse"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--usage-mode", action="store_true", help="DEVIATIONS D7: M14 with every code a test")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        run(a.out, a.workers, a.usage_mode)
    else:
        print(json.dumps(analyse(a.out, a.usage_mode), indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
