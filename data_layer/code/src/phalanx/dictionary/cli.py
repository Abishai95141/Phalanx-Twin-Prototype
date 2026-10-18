"""Command line for the M01 dictionary. Run from a checkout (paths are arguments; nothing is read implicitly).

Commands (``CFG=configs/tejas/dictionary``)::

    python -I src/phalanx/dictionary/cli.py seed --inventory <parameter_inventory.csv> --config $CFG
    python -I src/phalanx/dictionary/cli.py seed --inventory <...> --config $CFG --check   # 1 if stale
    python -I src/phalanx/dictionary/cli.py compile --config $CFG [--out <dir>]
    python -I src/phalanx/dictionary/cli.py build --config $CFG --out <dir>
    python -I src/phalanx/dictionary/cli.py release --config $CFG [--write]
    python -I src/phalanx/dictionary/cli.py assumptions --config $CFG
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path


def _api():
    """Import the package (inserting this checkout's src/ when run as a script under ``python -I``)."""
    if __package__ in (None, ""):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    return importlib.import_module("phalanx.dictionary")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="phalanx-dictionary", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seed", help="parameter_inventory.csv + overlay -> sources/*.yaml")
    s.add_argument("--inventory", required=True, type=Path)
    s.add_argument("--config", required=True, type=Path)
    s.add_argument("--check", action="store_true", help="compare with the committed sources; do not write")
    c = sub.add_parser("compile", help="compile and print version, hash and statistics")
    c.add_argument("--config", required=True, type=Path)
    c.add_argument("--out", type=Path)
    b = sub.add_parser("build", help="compile, write dictionary.<ver>.json and run the manifest generators")
    b.add_argument("--config", required=True, type=Path)
    b.add_argument("--out", required=True, type=Path)
    r = sub.add_parser("release", help="print (or write) the releases.yaml entry for the current sources")
    r.add_argument("--config", required=True, type=Path)
    r.add_argument("--write", action="store_true")
    a = sub.add_parser("assumptions", help="print the W0.3 rows for docs/assumptions.md")
    a.add_argument("--config", required=True, type=Path)
    args = ap.parse_args(argv)
    api = _api()

    if args.cmd == "seed":
        seeder = importlib.import_module("phalanx.dictionary.seeder")
        sources = seeder.seed_sources(args.inventory, args.config)
        if args.check:
            stale = []
            for name, text in seeder.render_sources(sources).items():
                p = args.config / "sources" / name
                if not p.is_file() or p.read_text(encoding="utf-8") != text:
                    stale.append(name)
            print("seeded sources up to date" if not stale else f"stale seeded sources: {stale}")
            return 1 if stale else 0
        for p in seeder.write_sources(sources, args.config / "sources"):
            print(p)
        return 0
    if args.cmd == "compile":
        compiled = api.compile_dictionary(args.config)
        print(
            json.dumps(
                {
                    "dict_version": compiled.dict_version,
                    "dict_hash": compiled.dict_hash,
                    "stats": compiled.content["stats"],
                },
                indent=1,
            )
        )
        if args.out:
            print(api.write_compiled(compiled, args.out))
        return 0
    if args.cmd == "build":
        _, written = api.build(args.config, args.out)
        for name, paths in written.items():
            for p in paths:
                print(f"{name}: {p}")
        return 0
    if args.cmd == "release":
        compiled = api.compile_dictionary(args.config)
        yamlio = importlib.import_module("phalanx.dictionary.yamlio")
        rel_path = args.config / "releases.yaml"
        doc = yamlio.load_yaml(rel_path)
        doc["releases"] = doc.get("releases") or {}
        entry = {"dict_hash": compiled.dict_hash, "release_date": compiled.content["release_date"]}
        print(f"{compiled.dict_version}: {entry}")
        if args.write:
            doc["releases"][compiled.dict_version] = entry
            header = "".join(
                line + "\n"
                for line in rel_path.read_text(encoding="utf-8").splitlines()
                if line.startswith("#")
            )
            rel_path.write_text(header + yamlio.dump_yaml(doc), encoding="utf-8")
        return 0
    if args.cmd == "assumptions":
        gens = importlib.import_module("phalanx.dictionary.generators")
        print(gens.assumptions_markdown(api.compile_dictionary(args.config).content), end="")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
