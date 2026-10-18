"""Label-leak audit and G0 on every catalogue mode (W2.5; PREREGISTRATION.md §5).

For each mode and k in {0, 1}: a healthy and a faulty ground-run bench run of one identity (CRN), recorded by
M13; per pair: the paired pipeline invariance (deterministic), the texture-only and metadata-only features
(``leak_features``) and the G0 pipeline-only metadata (``metadata_features``) of both runs, and the three
negative-control variants of the faulty run. The audits pool the pairs.

Usage: python -I leak_campaign.py run OUT_DIR [--workers 3] [--modes M1,M2]  (resumable: done pairs skipped)
       python -I leak_campaign.py audit OUT_DIR
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
from phalanx.faults import load_catalogue  # noqa: E402
from phalanx.faults.leak import texture_visible  # noqa: E402
from phalanx.validation.guards import (  # noqa: E402
    RecordedRun,
    g0_audit,
    label_leak_audit,
    leak_features,
    metadata_features,
    paired_invariance,
)

NS = 10**9
SEED = 25
GROUND_RUN = B.GroundRun(duration_s=20.0, pla=((0.0, 18.0), (5.0, 60.0)))
T_INJECT = 5 * NS
#: M10-process modes: the M10 states their degraded condition sets at t = 0 (an aircraft degraded before the
#: run); magnitudes at the B7 values or at about half of the state's limit
M10_STATES: dict[str, tuple[tuple[str, float], ...]] = {
    "FM.ENG.FOULING": (("eng:foul_fan", 0.02), ("eng:foul_hpc", 0.02)),
    "FM.ENG.EROSION": (("eng:ero_hpc", 0.05), ("eng:ero_hpt", 0.026), ("eng:ero_lpt", 0.008)),
    "FM.ENG.RUB_IN": (("eng:rubin", 0.015),),
    "FM.ENG.HPT_DETERIORATION": (("eng:abn_hpt", 0.03),),
    "FM.ENG.LIFE_USAGE": (),  # life counters only: no physical state reaches a port
    "FM.ENG.BEARING_SPALL": (("eng:spall_len", 0.004), ("eng:debris", 4.0e-5)),
    "FM.ENG.OIL_CONDITION": (("eng:oil_fe", 1.5e-5),),
    "FM.ENG.SEAL_WEAR": (("eng:aux_seal_wear", 0.5),),
    "FM.ENG.NOZZLE_FLAP_CRACK": (("eng:aux_nozzle_hw", 0.5),),
    "FM.AD.VANE_FRICTION": (("util:ad_vane_friction_aoa_l", 0.5),),
    "FM.ELEC.GEN_REGULATION": (("util:gen_health", 0.5),),
    "FM.ELEC.BATTERY_FADE": (("util:batt_fade", 0.25),),
    "FM.HYD.PUMP_WEAR": (("util:hyd1_pump_wear", 1.0),),
    "FM.HYD.CONTAMINATION_TREND": (("util:hyd1_contamination", 0.5),),
    "FM.LG.LOCK_SPRING": (("util:lock_spring_l", 0.5),),
    "FM.FCS.ACTUATOR_WEAR": (("act:elevon_lo", 0.5),),
    "FM.UTIL.GENERIC_WEAR": (("util:fuel_pump_wear", 0.5),),
    "FM.ECS.HX_FOULING": (("util:ecs_hx_fouling", 0.5),),
    "FM.LG.BRAKE_WEAR": (("util:brake_wear_l", 0.5),),
    "FM.LG.TYRE_WEAR": (("util:tyre_wear_l", 0.5),),
    "FM.LG.STRUT_LOSS": (("util:strut_service_l", 0.5),),
    "FM.STR.FATIGUE": (("util:str_fatigue", 0.5),),
}
#: FM.SNS.GENERIC: a level-type drift on a FADEC lane (PREREGISTRATION §5)
GENERIC = {"sensor_mode": "drift", "key": "ENG.PS3.A", "magnitude": 0.02, "rate_per_s": 0.002}
NC_CHANNEL_T5 = "ENG.T5"
NC_CHANNEL_DROP = "ENG.N2.A"


def injection(mode_id: str) -> list[Event]:
    """The events that make a run faulty for ``mode_id`` (empty = not injectable)."""
    cat = load_catalogue()
    m = cat[mode_id]
    if m.process == "physics":
        return []
    if m.process == "m10":
        if mode_id not in M10_STATES:
            raise KeyError(f"no M10 state map for {mode_id}")
        return [
            Event(0, "health.fault", "health", {"state": s, "delta": float(v), "op": "set"}, source="bench")
            for s, v in M10_STATES[mode_id]
        ]
    pay: dict[str, object] = {"mode": mode_id, "covered": True}
    if mode_id == "FM.SNS.GENERIC":
        pay |= GENERIC
    return [Event(T_INJECT, "faults.inject", "faults", pay, source="bench")]


def _recorded(r: B.BenchRun, run_id: str) -> RecordedRun:
    return RecordedRun(
        run_id=run_id,
        value=r.value,
        rate_hz=r.rate_hz,
        n_frames=r.n_steps,
        validity=r.validity,
        flags=r.flags,
        t_sample=r.t_sample,
        input_digest=r.input_digest,
    )


def _g0_row(run: RecordedRun) -> tuple[list[float], list[str]]:
    acq = B._static()[7]
    lsb = {c: float(acq.P[i, AK.AP_SF]) for i, c in enumerate(acq.channels)}
    chans = {c: (np.asarray(run.value[c]), float(run.rate_hz[c])) for c in run.channels}
    x, names = metadata_features(chans, run.n_frames, run.n_frames // 240, lsb=lsb)
    return x.tolist(), names


def _nc_variants(f: RecordedRun, affected: set[str]) -> dict[str, RecordedRun]:
    """NC1 texture lattice leak, NC2 pipeline drop of the last second, NC3 a changed noise path on one
    unaffected channel (one sample moved by one recorded LSB)."""
    out = {}
    v = dict(f.value)
    v[NC_CHANNEL_T5] = np.round(np.asarray(v[NC_CHANNEL_T5]) / 1.0) * 1.0
    out["nc1"] = RecordedRun(**{**f.__dict__, "value": v})
    n_drop = int(round(f.rate_hz[NC_CHANNEL_DROP]))
    cut = {}
    for name in ("value", "validity", "flags", "t_sample"):
        d = dict(getattr(f, name))
        d[NC_CHANNEL_DROP] = np.asarray(d[NC_CHANNEL_DROP])[:-n_drop]
        cut[name] = d
    out["nc2"] = RecordedRun(**{**f.__dict__, **cut})
    acq = B._static()[7]
    lsb = {c: float(acq.P[i, AK.AP_SF]) for i, c in enumerate(acq.channels)}
    target = next(c for c in f.channels if c not in affected and np.asarray(f.value[c]).size > 2)
    v3 = dict(f.value)
    a = np.array(v3[target], copy=True)
    a[a.size // 2] += lsb[target]
    v3[target] = a
    out["nc3"] = RecordedRun(**{**f.__dict__, "value": v3})
    out["nc3_channel"] = target  # type: ignore[assignment]
    return out


def pair_job(mode_id: str, k: int) -> dict:
    cat = load_catalogue()
    idx = list(cat).index(mode_id)
    ident = B.bench_identity("LEAK", f"L{idx:02d}{k}", f"{mode_id.replace('.', '-')}-{k}")
    evs = injection(mode_id)
    hb = B.run_bench(GROUND_RUN, ident)
    fb = B.run_bench(GROUND_RUN, ident, evs)
    h, f = _recorded(hb, f"{mode_id}#{k}/H"), _recorded(fb, f"{mode_id}#{k}/F")
    affected = {c for c in h.channels if h.input_digest.get(c) != f.input_digest.get(c)}
    nc = _nc_variants(f, affected)
    tex, tex_names = leak_features([h, f, nc["nc1"]], "texture_only")
    meta, meta_names = leak_features([h, f, nc["nc2"]], "metadata_only")
    g0 = [_g0_row(r) for r in (h, f, nc["nc2"])]
    return {
        "mode": mode_id,
        "k": k,
        "injectable": bool(evs),
        "texture_visible": texture_visible(cat[mode_id], GENERIC if mode_id == "FM.SNS.GENERIC" else None),
        "affected": sorted(affected),
        "invariance": paired_invariance(h, f),
        "invariance_nc2": paired_invariance(h, nc["nc2"]),
        "invariance_nc3": paired_invariance(h, nc["nc3"]),
        "nc3_channel": nc["nc3_channel"],
        "texture": tex.tolist(),
        "texture_names": tex_names,
        "metadata": meta.tolist(),
        "metadata_names": meta_names,
        "g0": [r[0] for r in g0],
        "g0_names": g0[0][1],
        "m14_records": [int(hb.m14["o_kind"].size), int(fb.m14["o_kind"].size)],
        "m11_instances": int(fb.faults["inst_mode"].size),
    }


def _done(out: Path) -> set[tuple[str, int]]:
    p = out / "leak_pairs.jsonl"
    if not p.exists():
        return set()
    return {(d["mode"], d["k"]) for d in map(json.loads, p.read_text().splitlines())}


def run(out: Path, workers: int, modes: list[str] | None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    cat = load_catalogue()
    todo = [(m, k) for m in (modes or list(cat)) for k in (0, 1) if (m, k) not in _done(out)]
    print(f"{len(todo)} pairs to run", flush=True)
    with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as ex:
        futs = {ex.submit(pair_job, m, k): (m, k) for m, k in todo}
        for fut in futs:
            res = fut.result()
            with open(out / "leak_pairs.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps(res, sort_keys=True) + "\n")
            print(f"done {res['mode']}#{res['k']} affected={len(res['affected'])} inv={len(res['invariance'])}",
                  flush=True)


def _audit_rows(pairs: list[dict], key: str, variant_col: int | None):
    """(X, y, groups, names): healthy row 0 and faulty row 1 (or the negative-control row) of every pair."""
    X, y, grp = [], [], []
    for p, d in enumerate(pairs):
        rows = d[key]
        X += [rows[0], rows[variant_col if variant_col is not None else 1]]
        y += [0, 1]
        grp += [p, p]
    return np.array(X, float), np.array(y), np.array(grp), pairs[0][f"{key}_names"]


def _res(r) -> dict:
    return {
        "passed": bool(r.passed),
        "classifiers": {k: {kk: (vv if not isinstance(vv, np.floating) else float(vv)) for kk, vv in v.items()}
                        for k, v in r.classifiers.items()},
        "n_rows": dict(r.n_rows),
        "top_univariate": [list(t) for t in r.top_univariate[:8]],
    }


def audit(out: Path) -> dict:
    pairs = [json.loads(s) for s in (out / "leak_pairs.jsonl").read_text().splitlines()]
    pairs.sort(key=lambda d: (d["mode"], d["k"]))
    tex_pairs = [d for d in pairs if not d["texture_visible"]]
    res: dict = {"n_pairs": len(pairs), "n_modes": len({d["mode"] for d in pairs})}
    res["invariance_failures"] = {f"{d['mode']}#{d['k']}": d["invariance"] for d in pairs if d["invariance"]}
    res["nc2_invariance_caught"] = sum(bool(d["invariance_nc2"]) for d in pairs)
    res["nc3_invariance_caught"] = sum(bool(d["invariance_nc3"]) for d in pairs)
    for name, sel, key, col, fs in (
        ("texture_only", tex_pairs, "texture", None, "texture_only"),
        ("metadata_only", pairs, "metadata", None, "metadata_only"),
        ("nc1_texture", tex_pairs, "texture", 2, "texture_only"),
        ("nc2_metadata", pairs, "metadata", 2, "metadata_only"),
    ):
        X, y, g, names = _audit_rows(sel, key, col)
        r = label_leak_audit(X, y, g, names, feature_set=fs, seed=SEED)
        res[name] = _res(r)
    for name, col in (("g0", 1), ("nc2_g0", 2)):
        XA = np.array([d["g0"][0] for d in pairs], float)
        XB = np.array([d["g0"][col] for d in pairs], float)
        r = g0_audit(XA, XB, pairs[0]["g0_names"], paired=True, seed=SEED)
        res[name] = _res(r)
    res["texture_excluded_modes"] = sorted({d["mode"] for d in pairs if d["texture_visible"]})
    res["not_injectable"] = sorted({d["mode"] for d in pairs if not d["injectable"]})
    res["affected_channels"] = {f"{d['mode']}#{d['k']}": len(d["affected"]) for d in pairs}
    (out / "leak_audit.json").write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8")
    return res


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("run", "audit"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--modes", default="")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        run(a.out, a.workers, [m for m in a.modes.split(",") if m] or None)
    else:
        r = audit(a.out)
        print(json.dumps({k: r[k] for k in r if k not in ("affected_channels",)}, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
