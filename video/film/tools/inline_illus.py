"""Inline the illustration plates a composition needs into assets/illus_inline.js (window.PHX_ILL[key] = svg text).
HyperFrames renders from file://, where fetch() of a sibling SVG is blocked, so plates travel as JS strings."""
import json
from pathlib import Path
F = Path(__file__).resolve().parents[1]
PLATES = {"hyd": "hydraulic-system.svg", "srv": "station-server.svg"}
out = ["window.PHX_ILL = window.PHX_ILL || {};"]
for k, name in PLATES.items():
    svg = (F / "assets/illustrations" / name).read_text()
    svg = svg[svg.index("<svg"):]                      # drop any XML prolog
    out.append(f"window.PHX_ILL[{json.dumps(k)}] = {json.dumps(svg)};")
(F / "assets/illus_inline.js").write_text("\n".join(out) + "\n")
print("wrote", F / "assets/illus_inline.js", sum(len(x) for x in out), "chars")
