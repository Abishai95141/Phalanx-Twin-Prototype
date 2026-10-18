"""Diagnostics of the label-leak audit (no verdicts; DEVIATIONS.md): which modes and channels carry the
classifier separation, and are the separating features confined to channels whose acquisition input the
fault's physics changed?

For every pair, a feature of channel c can differ between the healthy and the faulty run only if c is in the
pair's ``affected`` set (the paired invariance found unaffected channels bitwise identical). This script counts,
for the top separating features, how many pairs show a difference and whether each of them is an affected
channel of that pair, and lists the modes with the largest standardised differences.

Usage: python -I leak_diagnose.py OUT_DIR [--feature texture|metadata|g0]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from phalanx.validation.guards.g0 import pipeline_only_columns  # noqa: E402
from phalanx.validation.guards.label_leak import TEXTURE_FEATURES  # noqa: E402

#: per-channel feature suffixes of each feature set (the channel id is the name without the suffix)
SUFFIXES = {
    "texture": tuple(f"_{k}" for k in TEXTURE_FEATURES),
    "metadata": ("_n_over_rate", "_f32repr", "_n"),
    "g0": ("_n_over_rate", "_dtype", "_hasnan", "_f32repr", "_n"),
}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--feature", default="texture")
    ap.add_argument("--top", type=int, default=6)
    a = ap.parse_args(argv)
    pairs = [json.loads(s) for s in (a.out / "leak_pairs.jsonl").read_text().splitlines()]
    key = a.feature
    if key == "texture":
        pairs = [d for d in pairs if not d["texture_visible"]]
    names = pairs[0][f"{key}_names"]
    H = np.array([d[key][0] for d in pairs], float)
    F = np.array([d[key][1] for d in pairs], float)
    if key == "g0":  # the binding pipeline-only subset only
        keep = pipeline_only_columns(names)
        names, H, F = [names[j] for j in keep], H[:, keep], F[:, keep]
    D = F - H
    sd = np.nanstd(np.r_[H, F], axis=0)
    sd[sd == 0] = np.inf
    # univariate paired effect: mean difference over the pooled SD
    eff = np.nanmean(D, axis=0) / sd
    order = np.argsort(-np.abs(eff))[: a.top]
    report = {"n_pairs": len(pairs), "features": []}
    def chan_of(n: str) -> str:
        for s in SUFFIXES[key]:
            if n.endswith(s):
                return n[: -len(s)]
        return ""  # a run-level feature
    for j in order:
        name = names[j]
        ch = chan_of(name)
        diff = np.abs(D[:, j]) > 0
        in_aff = [ch in set(d["affected"]) for d in pairs]
        per_mode = defaultdict(float)
        for d, dv in zip(pairs, D[:, j], strict=True):
            per_mode[d["mode"]] += abs(dv) / (sd[j] if np.isfinite(sd[j]) else 1.0)
        top_modes = sorted(per_mode.items(), key=lambda kv: -kv[1])[:6]
        report["features"].append(
            {
                "feature": name,
                "std_effect": float(eff[j]),
                "pairs_differing": int(diff.sum()),
                "differing_pairs_where_channel_affected": int(np.sum(diff & np.array(in_aff))),
                "top_modes": [(m, round(v, 2)) for m, v in top_modes],
            }
        )
    unaff_diff = 0
    for d, row in zip(pairs, D, strict=True):
        aff = set(d["affected"])
        for j, n in enumerate(names):
            if row[j] != 0 and chan_of(n) and chan_of(n) not in aff:
                unaff_diff += 1
    report["feature_differences_on_unaffected_channels"] = unaff_diff
    print(key, "feature differences on unaffected channels:", unaff_diff)
    for f in report["features"]:
        print(
            f"  {f['feature']} effect {f['std_effect']:+.3f} differing {f['pairs_differing']} "
            f"(affected {f['differing_pairs_where_channel_affected']}) modes {f['top_modes'][:3]}"
        )
    (a.out / f"leak_diagnose_{key}.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
