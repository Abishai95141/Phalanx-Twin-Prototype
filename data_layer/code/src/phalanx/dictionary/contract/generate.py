"""Generate the contract artefacts from the spec (deterministic).

Writes, for a spec line ``v<major>``::

    generated/v<major>/contract.md                        summary (owner review, downstream docs)
    generated/v<major>/arrow/<topic>.schema.b64           Arrow schema (full view): base64 of the IPC bytes
    generated/v<major>/arrow/<topic>.schema.txt           the same schema as text, metadata untruncated
    generated/v<major>/arrow/<topic>.consumer.schema.b64  consumer view (the consumer tree's file schema)
    generated/v<major>/arrow/<topic>.consumer.schema.txt  (consumer-visible topics only)
    generated/v<major>/avro/<topic>.avsc                  Avro schemas (v1.x Kafka adapter)
    generated/v<major>/jsonschema/<topic>.json            JSON-Schema, consumer view (manifests, orders)

Read an Arrow schema back with ``read_arrow_schema(text)`` (``pyarrow.ipc.read_schema`` on the decoded bytes).
All artefacts are text so the dictionary's generator hook can write them; the IPC bytes are base64-encoded.

Usage (from a checkout)::

    python -I src/phalanx/dictionary/contract/generate.py            # regenerate in place
    python -I src/phalanx/dictionary/contract/generate.py --check    # exit 1 if the checked-in files drifted

A test asserts the checked-in artefacts equal a fresh generation, so they can never silently drift from the
spec.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pyarrow as pa

if __package__ in (None, ""):  # run as a script: import phalanx from this checkout's src/
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from phalanx.dictionary.contract.loader import load_contract
from phalanx.dictionary.contract.markdown import render_markdown

GENERATED_ROOT = Path(__file__).resolve().parent / "generated"


def _json_text(obj: object) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def arrow_schema_text(schema: pa.Schema) -> str:
    """Base64 of the Arrow IPC serialisation of ``schema`` (deterministic for the pinned pyarrow)."""
    return base64.b64encode(schema.serialize().to_pybytes()).decode("ascii") + "\n"


def read_arrow_schema(text: str) -> pa.Schema:
    """Inverse of :func:`arrow_schema_text`."""
    return pa.ipc.read_schema(pa.py_buffer(base64.b64decode(text.strip())))


def arrow_schema_dump(schema: pa.Schema) -> str:
    """Readable dump with every field and schema metadata value in full."""
    return schema.to_string(truncate_metadata=False, element_size_limit=1 << 30) + "\n"


def artefacts(version: str = "v0") -> dict[str, str]:
    """Relative path -> file text for every generated artefact of ``version``."""
    c = load_contract(version)
    out = {"contract.md": render_markdown(c)}
    for t in c.topic_names:
        out[f"arrow/{t}.schema.b64"] = arrow_schema_text(c.schemas[t])
        out[f"arrow/{t}.schema.txt"] = arrow_schema_dump(c.schemas[t])
        if not c.topics[t].restricted:
            out[f"arrow/{t}.consumer.schema.b64"] = arrow_schema_text(c.consumer_schema(t))
            out[f"arrow/{t}.consumer.schema.txt"] = arrow_schema_dump(c.consumer_schema(t))
        out[f"avro/{t}.avsc"] = _json_text(c.avro_schema(t))
        if c.topics[t].json_schema and not c.topics[t].restricted:
            out[f"jsonschema/{t}.json"] = _json_text(c.json_schema(t, audience="consumer"))
    return out


def main(argv: list[str]) -> int:
    check = "--check" in argv
    version = next((a for a in argv if a.startswith("v")), "v0")
    root = GENERATED_ROOT / version
    files = artefacts(version)
    drift = []
    for rel, text in sorted(files.items()):
        path = root / rel
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                drift.append(rel)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    if check:
        extra = sorted(
            str(p.relative_to(root))
            for p in root.rglob("*")
            if p.is_file() and str(p.relative_to(root)) not in files
        )
        if drift or extra:
            print(f"generated artefacts drifted: changed={drift} unexpected={extra}")
            return 1
        print(f"generated artefacts up to date ({len(files)} files)")
        return 0
    print(f"wrote {len(files)} files under {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
