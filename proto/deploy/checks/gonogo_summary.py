"""Print the go/no-go report in a few lines."""
import json
import sys

r = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "proto/runs/gonogo/gonogo_report.json"))
print("VERDICT", r["verdict"], "| build", r["build_worlds_s"], "s | init", r["init"]["wall_s"], "s | one-day step", r["step"]["wall_s"], "s")
for k, c in r["checks"].items():
    if all(isinstance(v, dict) for v in c.values()):
        print(" ", k, {t: (v["ours"], v["preview"], v["identical_all_columns"]) for t, v in c.items()})
    else:
        print(" ", k, {a: b for a, b in c.items() if a != "late_counter_rows"})
