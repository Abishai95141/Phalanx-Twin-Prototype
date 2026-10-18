"""Copy the preview's consumer fleet tree (Parquet) to Arrow IPC with the same relative paths and the same
schema metadata, for machines where Parquet is unreliable (IBM Z). Run where Parquet works (the Mac):

    proto/ground/.venv/bin/python proto/deploy/preview_to_ipc.py <preview fleet dir> <out dir>
"""
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

src, out = Path(sys.argv[1]), Path(sys.argv[2])
assert "_restricted" not in str(src)
n = 0
for f in sorted(src.rglob("part-*.parquet")):
    t = pq.ParquetFile(str(f)).read()  # keeps the file's schema metadata (contract hash, topic, audience)
    dst = out / f.relative_to(src).with_suffix(".arrow")
    dst.parent.mkdir(parents=True, exist_ok=True)
    with pa.OSFile(str(dst), "wb") as sink, pa.ipc.new_file(sink, t.schema, options=pa.ipc.IpcWriteOptions(compression="zstd")) as w:
        w.write_table(t)
    n += 1
print(f"wrote {n} IPC files to {out}")
