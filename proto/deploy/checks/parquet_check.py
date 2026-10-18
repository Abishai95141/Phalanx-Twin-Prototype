"""Server check: can this platform's pyarrow read the preview's Parquet and round-trip its own?"""
import glob
import sys

import pyarrow as pa
import pyarrow.parquet as pq

P = "/home/linux1/phalanx/phalanx_data_layer_preview/data/v0.9/fleet"
R = "/home/linux1/phalanx/Phalanx-Solution/proto/runs/gonogo/fleet"


def tryread(fs, label):
    ok = bad = 0
    err = None
    for f in fs:
        try:
            pq.read_table(f).to_pylist()
            ok += 1
        except Exception as e:  # noqa: BLE001
            bad += 1
            err = err or f"{f.split('/phalanx/')[-1]}: {e}"
    print(f"{label:28s} ok {ok:4d} bad {bad:4d} | {err or ''}")


print("pyarrow", pa.__version__, sys.byteorder)
for topic in ["maint.records", "events.bit_faults", "usage.counters", "orders.commands"]:
    tryread(sorted(glob.glob(f"{P}/{topic}/**/*.parquet", recursive=True))[:200], "preview " + topic)
    tryread(sorted(glob.glob(f"{R}/{topic}/**/*.parquet", recursive=True))[:200], "ours    " + topic)
t = pa.table({
    "a": pa.array([1, None, 3], pa.int64()),
    "s": ["x", None, "z"],
    "b": pa.array([b"\x01" * 16, None, b"\x02" * 16], pa.binary(16)),
    "l": pa.array([[b"\x01" * 16], None, []], pa.list_(pa.binary(16))),
})
pq.write_table(t, "/tmp/rt.parquet")
print("roundtrip equal:", pq.read_table("/tmp/rt.parquet").equals(t))
