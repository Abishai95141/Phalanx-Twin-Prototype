"""Step 3: merge reproduction and scenario outputs into ``video/data/forks/results.json``.

Usage: ./run.sh assemble.py
Inputs (all written by this folder's scripts): ``reproduction_<tail>.json``, ``scenario_S1.json``,
``scenario_S2.json``, ``scenario_S3.json`` and optional supplementary ``scenario_<S>_<tag>.json``.
"""

from __future__ import annotations

import datetime as dt
import glob
import json
import math
import platform
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "data" / "forks"
SCEN = ("S1", "S2", "S3")
TITLES = {
    "S1": "TJ107 recurring HYD-101: filter the code (HUMAN) + troubleshoot once (AGENT)",
    "S2": "TJ108 AOG since 2026-04-03: expedite the brake-chute AOG demand (AGENT)",
    "S3": "TJ105 tyres at 7 of 8 landings: requisition 2 tyres for the base (AGENT)",
}


def clean(x):
    if isinstance(x, float):
        return None if not math.isfinite(x) else x
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean(v) for v in x]
    return x


def mode_block(md: dict) -> dict:
    kp = {}
    for k, v in md["kpis"].items():
        d = v["paired_difference_treatment_minus_status_quo"]
        kp[k] = {
            "status_quo": {x: v["status_quo"][x] for x in ("mean", "ci_low", "ci_high", "sd")},
            "treatment": {x: v["treatment"][x] for x in ("mean", "ci_low", "ci_high", "sd")},
            "paired_difference": {x: d[x] for x in ("mean", "sd", "ci_low", "ci_high", "n")},
        }
    statuses: dict[str, dict[str, int]] = {}
    verdicts: dict[str, int] = {}
    for mem in md["members"]:
        for oid, rows in mem["order_status"].items():
            final = rows[-1]["status"] if rows else "NONE"
            statuses.setdefault(oid, {})
            statuses[oid][final] = statuses[oid].get(final, 0) + 1
        for g in mem["gateway_verdicts"]:
            verdicts[g["verdict"]] = verdicts.get(g["verdict"], 0) + 1
    extra = {}
    if "nmcs_exit" in md["members"][0]:
        extra["nmcs_exit_per_member"] = [m["nmcs_exit"] for m in md["members"]]
    if "tyre_jobs" in md["members"][0]:
        extra["tyre_jobs_per_member"] = [m["tyre_jobs"] for m in md["members"]]
    return {
        "mode": md["mode"],
        "mode_note": md["mode_note"],
        "n_pairs": md["n_pairs"],
        "headline_kpis": md["headline_kpis"],
        "kpis": kp,
        "derived": {
            k: {
                "definition": v["definition"],
                "status_quo": {x: v["status_quo"][x] for x in ("mean", "ci_low", "ci_high", "sd")},
                "treatment": {x: v["treatment"][x] for x in ("mean", "ci_low", "ci_high", "sd")},
                "paired_difference": {
                    x: v["paired_difference_treatment_minus_status_quo"][x] for x in ("mean", "sd", "ci_low", "ci_high", "n")
                },
            }
            for k, v in md.get("derived", {}).items()
        },
        "paired_difference_first_10_pairs": {
            k: {x: v[x] for x in ("mean", "sd", "ci_low", "ci_high", "n")}
            for k, v in md.get("paired_difference_first_10_pairs", {}).items()
        },
        "order_final_status_counts": statuses,
        "gateway_verdict_counts": verdicts,
        "wall_s": md["wall_s"],
        **extra,
    }


def belief_vs_ensemble(doc: dict) -> dict | None:
    if not {"belief", "ensemble"} <= set(doc["modes"]):
        return None
    b = {m["member"]: m for m in doc["modes"]["belief"]["members"]}
    e = {m["member"]: m for m in doc["modes"]["ensemble"]["members"]}
    common = sorted(set(b) & set(e))
    same = {
        arm: sum(b[m]["record_digest"][arm] == e[m]["record_digest"][arm] for m in common)
        for arm in ("status_quo", "treatment")
    }
    same_kpis = {
        arm: sum(b[m][arm] == e[m][arm] for m in common) for arm in ("status_quo", "treatment")
    }
    return {
        "members_compared": len(common),
        "identical_record_digests": same,
        "identical_kpis": same_kpis,
        "meaning": "belief member m vs ensemble member m share the exogenous future; identical digests mean "
        "the reference belief posterior's resampling did not change any emitted record in the window",
    }


def scenario_block(doc: dict) -> dict:
    return {
        "title": TITLES.get(doc["scenario"], doc["scenario"]),
        "tail": doc["tail"],
        "epoch": doc["epoch"],
        "horizon_days": doc["horizon_days"],
        "window": doc["window"],
        "snapshot_id": doc["snapshot_id"],
        "fleet_days_built": doc["fleet_days_built"],
        "status_quo": doc["status_quo"],
        "treatment": doc["treatment"],
        "orders": doc["orders"],
        "evidence_record_ids": sorted({h for o in doc["orders"] for h in o["evidence"]}),
        "decision_context": doc["decision_context"],
        "gateway_verdicts_at_epoch": doc["gateway_verdicts_at_epoch"],
        "oracle_continuation_check": doc.get("oracle_continuation_check"),
        "results": {m: mode_block(md) for m, md in doc["modes"].items()},
        "belief_vs_ensemble": belief_vs_ensemble(doc),
        "wall_s": doc["wall_s"],
        "per_member_file": f"scenario_{doc['scenario']}{doc.get('_tag', '')}.json",
    }


def main() -> None:
    repro = {}
    for f in sorted(glob.glob(str(OUT / "reproduction_*.json"))):
        d = json.loads(Path(f).read_text())
        repro[d["tail"]] = {
            "snapshot_id": d["snapshot_id"],
            "all_consumer_rows_before_epoch_identical": all(
                v["identical_all_columns"] for k, v in d["checks"].items() if k.endswith("_before_epoch")
            ),
            "checks": d["checks"],
            "wall_s_run_to_epoch": d["wall_s_run_to_epoch"],
        }
    world = json.loads((OUT / "reproduction_TJ107.json").read_text())["world"]
    scen = {}
    for s in SCEN:
        p = OUT / f"scenario_{s}.json"
        if p.exists():
            scen[s] = scenario_block(json.loads(p.read_text()))
    supp = {}
    for f in sorted(glob.glob(str(OUT / "scenario_S*_*.json"))):
        d = json.loads(Path(f).read_text())
        tag = Path(f).stem.split("_", 2)[2]
        d["_tag"] = "_" + tag
        supp[f"{d['scenario']}_{tag}"] = scenario_block(d)
    pk = {}
    for name in ("numpy", "scipy", "pyarrow", "numba", "jsonschema"):
        try:
            pk[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pk[name] = None
    doc = {
        "label": "PREVIEW v0.9 data-layer simulator. Synthetic fleet, synthetic codes and part numbers; "
        "behaviour NOT validated; cost is a relative proxy. Not real Tejas/IAF data.",
        "generated_utc": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "how": "see README.md in this folder",
        "provenance": {
            "data_layer_source": "/Users/abishaikc/Downloads/phalanx_data_layer_preview/code (read-only)",
            "world": world,
            "python": platform.python_version(),
            "packages": pk,
            "scripts": "video/tools/forks/{phx_forks,reproduce,run_forks,assemble}.py",
        },
        "conventions": {
            "difference": "treatment minus status quo, CRN-paired by ensemble member (ForkService.compare paired=True); "
            "Student t 95 % interval over pairs",
            "arm_interval": "Student t 95 % interval of the arm mean over members (not paired)",
            "fractions": "mc, fmc, nmcs, nmcm, nmcd are fractions of the window (0-1) for the one tail",
            "kpi_scope": "each scenario's world holds one tail (preview per-tail worlds), so KPIs are that tail's",
            "modes": {
                "belief": "IN-LOOP number (what the product can show): data layer's reference SurvivalPosterior (PROXY)",
                "ensemble": "OFFLINE evaluation only (true state, privileged)",
                "oracle": "not reported; used once per scenario only to validate bitwise continuation",
            },
        },
        "reproduction": repro,
        "belief_posterior_footprint": (
            json.loads((OUT / "belief_check.json").read_text()) if (OUT / "belief_check.json").exists() else None
        ),
        "scenarios": scen,
        "supplementary": supp,
    }
    (OUT / "results.json").write_text(json.dumps(clean(doc), indent=2, allow_nan=False) + "\n")
    for s, b in scen.items():
        print(s, b["tail"], b["snapshot_id"][:16])
        for m, r in b["results"].items():
            for k in r["headline_kpis"]:
                d = r["kpis"][k]["paired_difference"]
                print(f"  {m:8s} {k:20s} d={d['mean']:+.4f} [{d['ci_low']:+.4f}, {d['ci_high']:+.4f}] n={d['n']}")
    for s, b in supp.items():
        print("supp", s)
        for m, r in b["results"].items():
            for k in r["headline_kpis"]:
                d = r["kpis"][k]["paired_difference"]
                print(f"  {m:8s} {k:20s} d={d['mean']:+.4f} [{d['ci_low']:+.4f}, {d['ci_high']:+.4f}] n={d['n']}")


if __name__ == "__main__":
    main()
