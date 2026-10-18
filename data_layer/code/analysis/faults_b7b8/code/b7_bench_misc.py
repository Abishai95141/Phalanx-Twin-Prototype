"""B7 bench checks for the sensor-bias, hydraulic-pump and generator faults (PREREGISTRATION.md §3:
B7-SNS-BIAS, B7-HYD-PUMP-SIG, B7-ELEC-GEN). n = 5 pairs each; a pair is a healthy and a faulty run of one
identity (CRN).

Usage: python -I b7_bench_misc.py run OUT_DIR [--workers 2] [--kinds gen,bias,hyd] [--pairs 0,1] ;
       python -I b7_bench_misc.py analyse OUT_DIR

Kinds ``gen``, ``bias``, ``hyd`` are the pre-registered runs. Post-hoc runs (DEVIATIONS.md): ``bias_d3`` (each
run trimmed at its own initial engine inputs, D3: the 90-deg diagnostic was lost in two pairs whose healthy
engine rolled back below idle) and the diagnostic ``gen_d4`` (pair 0 only: the ground run closed by its shut-down
event, D4, to separate "M14 never evaluated after the onset" from "nothing declares ELE-401 in telemetry mode";
a deterministic wiring question, so one pair answers it).
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import bench as B  # noqa: E402

from phalanx.acquisition import kernel as AK  # noqa: E402
from phalanx.core.events import Event  # noqa: E402
from phalanx.monitoring.module import KIND_BIT, KIND_CAUTION  # noqa: E402

NS = 10**9
N_PAIRS = 5
BIAS_PROG = B.GroundRun(duration_s=82.0, pla=((0.0, 18.0), (12.0, 60.0), (52.0, 90.0)))
HYD_PROG = B.GroundRun(duration_s=180.0, pla=((0.0, 31.0),))
GEN_PROG = B.GroundRun(duration_s=20.0, pla=((0.0, 31.0),))
BIAS_SEVERITY = 0.5
N1_REF_RAD_S = 13270.0 * 2.0 * np.pi / 60.0  # 100 % N1 (M07 reference); a healthy run below half of it at
# PLA 90 rolled back below idle (diagnostic flag only)


def _bias_events() -> list[Event]:
    pay = {"mode": "FM.SNS.T5_HARNESS_BIAS", "severity": BIAS_SEVERITY, "covered": True}
    return [Event(0, "faults.inject", "faults", pay, source="b7")]


def _hyd_events() -> list[Event]:
    return [Event(0, "health.fault", "health", {"state": "util:hyd1_pump_wear", "delta": 1.0, "op": "set"})]


def _gen_onset(p: int) -> int:
    return 10 * NS + round(0.37 * p * NS)


def _gen_events(p: int) -> list[Event]:
    pay = {"mode": "FM.ELEC.GEN_DIODE", "severity": 1.0, "covered": True}
    return [Event(_gen_onset(p), "faults.inject", "faults", pay, source="b7")]


def _window(r: B.BenchRun, c: str, t0: float, t1: float) -> np.ndarray:
    t = r.t_sample[c] * 1e-9
    return r.value[c][(t >= t0) & (t < t1)]


def _port(r: B.BenchRun, name: str, col: int = 0) -> np.ndarray:
    return r.ports[name].reshape(r.n_steps, -1)[:, col]


def _bias_summary(r: B.BenchRun) -> dict:
    tk = np.arange(r.n_steps) / 240.0
    w60, w90 = (tk >= 32.0) & (tk < 52.0), (tk >= 72.0) & (tk < 82.0)
    out = {
        "harness_b_60": float(_window(r, "ENG.T5.HARNESS_B", 32.0, 52.0).mean()),
        "harness_a_60": float(_window(r, "ENG.T5.HARNESS_A", 32.0, 52.0).mean()),
        "t5_avg_60": float(_window(r, "ENG.T5", 32.0, 52.0).mean()),
        "truth_t5_60": float(_port(r, "eng.t5")[w60].mean()),
        "truth_n2_60": float(_port(r, "eng.n2")[w60].mean()),
        "truth_t5_90": float(_port(r, "eng.t5")[w90].mean()),
        "truth_n1_90": float(_port(r, "eng.n1")[w90].mean()),
        "truth_a8_90": float(_port(r, "eng.a8")[w90].mean()),
        "truth_thrust_90": float(_port(r, "eng.thrust")[w90].mean()),
        "limiter_90": sorted({int(x) for x in _port(r, "fadec.active_limiter")[w90]}),
    }
    codes = B._static()[5]
    st = r.m14
    out["m14_codes"] = sorted({codes.codes[int(c)].code for c in st["o_code"][st["o_kind"] == KIND_BIT]})
    return out


def _hyd_summary(r: B.BenchRun) -> dict:
    return {
        "sys1_t_last30": float(_window(r, "HYD.SYS1.T", 150.0, 180.0).mean()),
        "sys2_t_last30": float(_window(r, "HYD.SYS2.T", 150.0, 180.0).mean()),
        "sys1_p_last30": float(_window(r, "HYD.SYS1.P", 150.0, 180.0).mean()),
        "sys1_t_rate_k_per_min": float(
            (_window(r, "HYD.SYS1.T", 170.0, 180.0).mean() - _window(r, "HYD.SYS1.T", 60.0, 70.0).mean()) / (110 / 60)
        ),
        "truth_sys1_t_end": float(_port(r, "util.hyd_t", 0)[-1]),
    }


def _gen_summary(r: B.BenchRun, p: int, faulty: bool) -> dict:
    tk = np.arange(r.n_steps) * (NS / 240.0)
    t_on = _gen_onset(p)
    gen = _port(r, "util.gen_online")
    ess = _port(r, "util.bus_v", 1)  # DC essential (M09 bus order: main, essential, emergency, AC)
    out: dict = {"onset_s": t_on / NS}
    after = tk >= t_on
    off = np.flatnonzero(after & (gen < 0.5))
    out["gen_offline_delay_s"] = float((tk[off[0]] - t_on) / NS) if off.size else None
    bad = np.flatnonzero(after & ((ess < 22.0) | (ess > 29.0)))
    if bad.size:
        # the interruption: from the first out-of-band sample to the first in-band sample after it
        back = np.flatnonzero(after & (tk > tk[bad[0]]) & (ess >= 22.0) & (ess <= 29.0))
        out["ess_out_of_band_s"] = float((tk[back[0]] - tk[bad[0]]) / NS) if back.size else float("inf")
    else:
        out["ess_out_of_band_s"] = 0.0
    out["ess_min_v"] = float(ess[after].min())
    codes = B._static()[5]
    st = r.m14
    sel = (st["o_t"] >= t_on) & np.isin(st["o_kind"], (KIND_BIT, KIND_CAUTION))
    out["m14_codes_after_onset"] = sorted({codes.codes[int(c)].code for c in st["o_code"][sel]})
    return out


def pair_job(job: tuple[str, int]) -> dict:
    kind, p = job
    base = kind.split("_")[0]
    # the post-hoc kinds reuse the pre-registered identities (same exogenous draws, CRN)
    ident = B.bench_identity(f"B7{base.upper()}", f"{base[0].upper()}{p}", f"P{p}")
    if base == "bias":
        d3 = kind == "bias_d3"
        h = B.run_bench(BIAS_PROG, ident, trim_at_start=d3)
        f = B.run_bench(BIAS_PROG, ident, _bias_events(), trim_at_start=d3)
        acq = B._static()[7]
        lsb = float(acq.P[acq.channels.index("ENG.T5.HARNESS_B"), AK.AP_SF])
        from phalanx.health import sensor_bias_channels

        bc = {x.channel_id: x for x in sensor_bias_channels(B._static()[0])}["ENG.T5.HARNESS_B"]
        return {
            "kind": kind,
            "pair": p,
            "H": _bias_summary(h),
            "F": _bias_summary(f),
            "lsb": lsb,
            "injected_bias_k": 0.12 * BIAS_SEVERITY * float(bc.span_si),  # catalogue magnitude x severity x span
        }
    if kind == "hyd":
        h, f = B.run_bench(HYD_PROG, ident), B.run_bench(HYD_PROG, ident, _hyd_events())
        return {"kind": kind, "pair": p, "H": _hyd_summary(h), "F": _hyd_summary(f)}
    end = B.shutdown_event(ident, round((GEN_PROG.duration_s - 0.01) * NS)) if kind == "gen_d4" else []
    h, f = B.run_bench(GEN_PROG, ident, end), B.run_bench(GEN_PROG, ident, [*_gen_events(p), *end])
    return {"kind": kind, "pair": p, "H": _gen_summary(h, p, False), "F": _gen_summary(f, p, True)}


def _ci(v) -> dict:
    from scipy import stats

    v = np.asarray(v, np.float64)
    m, s = float(v.mean()), float(v.std(ddof=1))
    h = float(stats.t.ppf(0.975, v.size - 1)) * s / np.sqrt(v.size)
    return {"n": int(v.size), "mean": m, "ci95": [m - h, m + h], "values": v.tolist()}


def _d(pairs: list[dict], key: str) -> np.ndarray:
    return np.array([d["F"][key] - d["H"][key] for d in pairs])


def analyse_bias(pairs: list[dict]) -> dict:
    """B7-SNS-BIAS rules (i) and (ii) and the 90-deg diagnostic (PREREGISTRATION §3)."""
    bias = float(pairs[0]["injected_bias_k"])
    lsb = float(pairs[0]["lsb"])
    sb, sa = _ci(_d(pairs, "harness_b_60")), _ci(_d(pairs, "harness_a_60"))
    tol = max(lsb, 0.02 * bias)
    t5, n2 = _ci(_d(pairs, "truth_t5_60")), _ci(_d(pairs, "truth_n2_60"))
    n2_pct = abs(n2["mean"]) / float(np.mean([d["H"]["truth_n2_60"] for d in pairs])) * 100.0
    out = {
        "n_pairs": len(pairs),
        "injected_bias_k": bias,
        "lsb_k": lsb,
        "i_harness_b_shift_k": sb,
        "i_harness_a_shift_k": sa,
        "i_tolerance_k": tol,
        "i_verdict": "PASS" if abs(sb["mean"] - bias) <= tol and abs(sa["mean"]) <= lsb else "FAIL",
        "ii_truth_t5_shift_k": t5,
        "ii_truth_n2_shift_pct": n2_pct,
        "ii_verdict": "PASS" if abs(t5["mean"]) < 0.5 and n2_pct < 0.05 else "FAIL",
        "m14_codes_faulty_only": sorted(
            set().union(*(set(d["F"]["m14_codes"]) - set(d["H"]["m14_codes"]) for d in pairs))
        ),
    }
    diag = {}
    for key in ("truth_t5_90", "truth_n1_90", "truth_a8_90", "truth_thrust_90"):
        diag[key] = _ci([d["F"][key] / d["H"][key] - 1.0 for d in pairs])
    diag["healthy_limiter_90"] = sorted({c for d in pairs for c in d["H"]["limiter_90"]})
    diag["healthy_rolled_back_pairs"] = [d["pair"] for d in pairs if d["H"]["truth_n1_90"] < 0.5 * N1_REF_RAD_S]
    out["diagnostic_90deg"] = diag
    return out


def analyse_hyd(pairs: list[dict]) -> dict:
    """B7-HYD-PUMP-SIG: system-1 fluid temperature up with the CI excluding 0, system 2 unchanged."""
    s1, s2 = _ci(_d(pairs, "sys1_t_last30")), _ci(_d(pairs, "sys2_t_last30"))
    return {
        "n_pairs": len(pairs),
        "sys1_t_shift_k": s1,
        "sys2_t_shift_k": s2,
        "verdict": "PASS" if s1["ci95"][0] > 0.0 and abs(s2["mean"]) < 0.1 else "FAIL",
        "diagnostic_sys1_p_shift": _ci(_d(pairs, "sys1_p_last30")),
        "diagnostic_sys1_t_rate_shift_k_per_min": _ci(_d(pairs, "sys1_t_rate_k_per_min")),
    }


def analyse_gen(pairs: list[dict]) -> dict:
    """B7-ELEC-GEN: in every run, generator offline within one frame, essential DC back in band within 50 ms
    (MIL-STD-704F), ELE-401 recorded by M14 after the onset."""
    frame = 1.0 / 240.0
    rows = []
    for d in sorted(pairs, key=lambda x: x["pair"]):
        f = d["F"]
        rows.append(
            {
                "pair": d["pair"],
                "offline_delay_s": f["gen_offline_delay_s"],
                "ess_out_of_band_s": f["ess_out_of_band_s"],
                "ess_min_v": f["ess_min_v"],
                "m14_codes_after_onset": f["m14_codes_after_onset"],
                "healthy_m14_codes_after_onset": d["H"]["m14_codes_after_onset"],
                "offline_ok": f["gen_offline_delay_s"] is not None and f["gen_offline_delay_s"] <= frame + 1e-9,
                "transfer_ok": f["ess_out_of_band_s"] <= 0.050,
                "ele401_ok": "ELE-401" in f["m14_codes_after_onset"],
            }
        )
    crit = {k: all(r[k] for r in rows) for k in ("offline_ok", "transfer_ok", "ele401_ok")}
    return {"n_pairs": len(rows), "runs": rows, "criteria": crit, "verdict": "PASS" if all(crit.values()) else "FAIL"}


def analyse(out: Path) -> dict:
    allp = [json.loads(s) for s in (out / "b7_misc_pairs.jsonl").read_text().splitlines()]
    by: dict[str, list[dict]] = {}
    for d in allp:
        by.setdefault(d["kind"], []).append(d)
    fns = {"bias": analyse_bias, "hyd": analyse_hyd, "gen": analyse_gen}
    res: dict = {}
    for kind, pairs in sorted(by.items()):
        pairs.sort(key=lambda d: d["pair"])
        r = fns[kind.split("_")[0]](pairs)
        r["status"] = "pre-registered" if "_" not in kind else f"post hoc ({kind.split('_')[1].upper()}, DEVIATIONS.md)"
        res[kind] = r
    (out / "b7_misc.json").write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8")
    return res


def run(out: Path, workers: int, kinds: list[str], pairs: list[int] | None = None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    path = out / "b7_misc_pairs.jsonl"
    done = {(d["kind"], d["pair"]) for d in map(json.loads, path.read_text().splitlines())} if path.exists() else set()
    sel = range(N_PAIRS) if pairs is None else pairs
    todo = [(k, p) for k in kinds for p in sel if (k, p) not in done]
    with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as ex:
        for res in ex.map(pair_job, todo):
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(res, sort_keys=True) + "\n")
            print(f"{res['kind']} {res['pair']} done", flush=True)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("run", "analyse"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--kinds", default="gen,bias,hyd")
    ap.add_argument("--pairs", default=None, help="comma-separated pair indices (default all)")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        run(a.out, a.workers, a.kinds.split(","), None if a.pairs is None else [int(x) for x in a.pairs.split(",")])
        return 0
    for kind, r in analyse(a.out).items():
        print(kind, r["status"], {k: v for k, v in r.items() if "verdict" in k})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
