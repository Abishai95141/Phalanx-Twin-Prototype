"""Safely extract the .mat files of a DASHlink tail archive.

Only members whose basename matches <tail><YYYYMMDDhhmm>[_1].mat are written,
always flattened to the basename (no path traversal), never executed.
Usage: python -I extract.py <zip> <out_dir>
"""
import os
import sys
import zipfile
import hashlib
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dlio import FNAME_RE  # noqa: E402


def main(zpath, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    h = hashlib.sha256()
    with open(zpath, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    report = {"zip": os.path.basename(zpath), "zip_bytes": os.path.getsize(zpath),
              "zip_sha256": h.hexdigest(), "written": 0, "skipped": []}
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            base = os.path.basename(info.filename)
            if info.is_dir():
                continue
            if not FNAME_RE.match(base):
                report["skipped"].append(info.filename)
                continue
            dst = os.path.join(out_dir, base)
            with z.open(info) as src, open(dst, "wb") as out:
                while True:
                    b = src.read(1 << 20)
                    if not b:
                        break
                    out.write(b)
            report["written"] += 1
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
