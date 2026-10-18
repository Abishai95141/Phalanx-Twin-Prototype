"""Static determinism audit for src/ (RULES.md rule 5; architecture invariants I1, I2).

Fails on constructs that break bitwise replay or forkability:
  R1  global / legacy NumPy RNG (np.random.seed, np.random.normal, ... at module level)
  R2  unseeded Generator construction (np.random.default_rng() with no argument)
  R3  stdlib `random` module
  R4  wall-clock reads (time.time, time.perf_counter, time.monotonic, datetime.now/utcnow/today, date.today)
  R5  builtin hash() (salted per process for str/bytes; never use for keys or record ids)
  R6  seed arithmetic (an expression like `seed + 1` / `seed * k`; spawn keys instead)
  R7  OS entropy / process identity (os.urandom, os.getrandom, os.getpid, uuid.uuid1/uuid4, the `secrets`
      module, builtin id())
  R8  integer-literal power (x ** 2) inside a Numba-jitted function: compiled code uses x*x, the pure-Python
      reference calls libm pow, which is not correctly rounded on darwin. Kernel != reference by 1 ULP. Write
      explicit products (x * x, (x * x) * x).

Calls are resolved through import aliases, so `from time import perf_counter; perf_counter()`,
`from numpy.random import default_rng; default_rng()` and `import numpy.random as npr; npr.PCG64()`
are caught.
R2 also covers bit generators and SeedSequence built with no seed (PCG64(), Philox(), SeedSequence(), ...).

Allow a specific line with a trailing comment:  `# audit: allow R4 <reason>`.
Also reports (does not fail on) STUB markers, which must be gone before Wave 2 exit.

Usage: python -I tools/audit_static.py src [more paths...]
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

LEGACY_NP_RANDOM = {
    "seed",
    "rand",
    "randn",
    "random",
    "random_sample",
    "ranf",
    "sample",
    "randint",
    "random_integers",
    "normal",
    "uniform",
    "standard_normal",
    "choice",
    "shuffle",
    "permutation",
    "binomial",
    "poisson",
    "exponential",
    "gamma",
    "beta",
    "lognormal",
    "multivariate_normal",
    "get_state",
    "set_state",
    "RandomState",
}
WALL_CLOCK = {
    ("time", "time"),
    ("time", "time_ns"),
    ("time", "perf_counter"),
    ("time", "perf_counter_ns"),
    ("time", "monotonic"),
    ("time", "monotonic_ns"),
    ("time", "process_time"),
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("datetime", "today"),
    ("date", "today"),
}
ALLOW_RE = re.compile(r"#\s*audit:\s*allow\s+(R\d)\b")
SEED_ARITH_RE = re.compile(r"\bseed\w*\s*[-+*^]\s*\w|\w\s*[-+*^]\s*\bseed\w*\b")


def _dotted(node: ast.AST) -> list[str]:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return parts[::-1]


UNSEEDED_CTORS = {"default_rng", "PCG64", "PCG64DXSM", "Philox", "SFC64", "MT19937", "SeedSequence"}
WALL_CLOCK_Q = {
    "time.time",
    "time.time_ns",
    "time.perf_counter",
    "time.perf_counter_ns",
    "time.monotonic",
    "time.monotonic_ns",
    "time.process_time",
    "time.process_time_ns",
    "time.thread_time",
    "datetime.datetime.now",
    "datetime.datetime.utcnow",
    "datetime.datetime.today",
    "datetime.date.today",
}
ENTROPY_Q = {"os.urandom", "os.getrandom", "os.getpid", "uuid.uuid1", "uuid.uuid4"}


def _unseeded(node: ast.Call) -> bool:
    """True when a generator/bit-generator/SeedSequence call has no seed (no args, or None/entropy=None)."""
    if not node.args and not node.keywords:
        return True
    first = node.args[0] if node.args else None
    if isinstance(first, ast.Constant) and first.value is None:
        return True
    for kw in node.keywords:
        if kw.arg in ("seed", "entropy") and isinstance(kw.value, ast.Constant) and kw.value.value is None:
            return True
    return False


def audit_file(path: Path) -> tuple[list[str], list[str]]:
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines()
    tree = ast.parse(src, filename=str(path))
    alias: dict[str, str] = {}  # local name -> fully qualified target
    findings: list[tuple[int, str, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                alias[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
                if a.name == "random":
                    findings.append((node.lineno, "R3", "stdlib random imported"))
                if a.name == "secrets":
                    findings.append((node.lineno, "R7", "secrets module imported (OS entropy)"))
        elif isinstance(node, ast.ImportFrom) and node.module:
            for a in node.names:
                alias[a.asname or a.name] = f"{node.module}.{a.name}"
            if node.module == "random":
                findings.append((node.lineno, "R3", "stdlib random imported"))
            if node.module == "secrets":
                findings.append((node.lineno, "R7", "secrets module imported (OS entropy)"))
            if node.module == "numpy.random":
                for a in node.names:
                    if a.name in LEGACY_NP_RANDOM:
                        findings.append((node.lineno, "R1", f"legacy numpy.random.{a.name} imported"))

    def qualify(d: list[str]) -> str:
        head = alias.get(d[0], d[0])
        return ".".join([head, *d[1:]])

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        d = _dotted(node.func)
        if not d:
            continue
        q = qualify(d)
        shown = ".".join(d)
        if q.startswith("numpy.random."):
            fn = q.rsplit(".", 1)[1]
            if fn in LEGACY_NP_RANDOM and q.count(".") == 2:
                findings.append((node.lineno, "R1", f"global/legacy RNG call {shown}()"))
            if fn in UNSEEDED_CTORS and _unseeded(node):
                findings.append((node.lineno, "R2", f"{shown}() without a seed/SeedSequence (OS entropy)"))
        if q in WALL_CLOCK_Q or (len(d) >= 2 and (d[-2], d[-1]) in WALL_CLOCK):
            findings.append((node.lineno, "R4", f"wall-clock read {shown}()"))
        if d == ["hash"] and "hash" not in alias:
            findings.append((node.lineno, "R5", "builtin hash() is process-salted"))
        if q in ENTROPY_Q or q.startswith("secrets."):
            findings.append((node.lineno, "R7", f"OS entropy / process identity {shown}()"))
        if d == ["id"] and "id" not in alias:
            findings.append((node.lineno, "R7", "builtin id() is a memory address (differs per process)"))

    def _is_jit(dec: ast.expr) -> bool:
        target = dec.func if isinstance(dec, ast.Call) else dec
        d = _dotted(target)
        return bool(d) and d[-1] in ("njit", "jit", "vectorize", "guvectorize")

    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef) and any(
            _is_jit(d) for d in fn.decorator_list
        ):
            for node in ast.walk(fn):
                if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
                    r = node.right
                    if isinstance(r, ast.UnaryOp) and isinstance(r.op, ast.USub):
                        r = r.operand
                    if (
                        isinstance(r, ast.Constant)
                        and isinstance(r.value, int | float)
                        and not isinstance(r.value, bool)
                    ):
                        if float(r.value).is_integer():
                            findings.append(
                                (
                                    node.lineno,
                                    "R8",
                                    f"integer-literal power ** {r.value} in jitted {fn.name}()",
                                )
                            )

    for i, line in enumerate(lines, 1):
        code = line.split("#", 1)[0]
        if SEED_ARITH_RE.search(code):
            findings.append((i, "R6", "seed arithmetic; derive streams by spawn key path instead"))

    errors, notes = [], []
    for lineno, rule, msg in sorted(set(findings)):
        line = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
        m = ALLOW_RE.search(line)
        if m and m.group(1) == rule:
            notes.append(f"{path}:{lineno}: {rule} allowed: {line.strip()}")
            continue
        errors.append(f"{path}:{lineno}: {rule} {msg}")
    for i, line in enumerate(lines, 1):
        if re.search(r"\bSTUB\b", line):
            notes.append(f"{path}:{i}: STUB marker (must be gone before Wave 2 exit)")
    return errors, notes


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in (argv or ["src"])]
    files = sorted(p for r in roots for p in ([r] if r.is_file() else r.rglob("*.py")))
    all_err: list[str] = []
    all_notes: list[str] = []
    for f in files:
        e, n = audit_file(f)
        all_err += e
        all_notes += n
    for n in all_notes:
        print("note:", n)
    for e in all_err:
        print("ERROR:", e)
    print(f"audit_static: {len(files)} files, {len(all_err)} errors, {len(all_notes)} notes")
    return 1 if all_err else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
