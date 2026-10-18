"""M7: code ergonomics evidence.

  E1 logical lines of code (no blanks, comments or docstrings) of each backend's kernel, and of the code needed
     for the M5 Jacobian per backend.
  E2 debuggability: does the compiled kernel run uncompiled (Numba: NUMBA_DISABLE_JIT=1; JAX: jax.disable_jit())
     and give the same digest as compiled? 1 unit, 240 steps (1 s; uncompiled JAX is slow).

Usage: python -I code/s10_m7_ergonomics.py
"""

from __future__ import annotations

import ast
import io
import json
import os
import subprocess
import sys
import tokenize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import HERE, PY, machine_info, save_json

STEPS = 240


def logical_lines(path, func_names=None) -> int:
    """Count source lines carrying code tokens, excluding comments and docstrings (optionally only in functions)."""
    src = open(path).read()
    tree = ast.parse(src)
    doc_lines = set()
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Module):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):  # fmt: skip
                doc_lines.update(range(body[0].lineno, body[0].end_lineno + 1))
        if func_names and isinstance(node, ast.FunctionDef) and node.name in func_names:
            spans.append((node.lineno, node.end_lineno))
    code_lines = set()
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
                        tokenize.ENCODING, tokenize.ENDMARKER):  # fmt: skip
            continue
        for ln in range(tok.start[0], tok.end[0] + 1):
            code_lines.add(ln)
    code_lines -= doc_lines
    if func_names:
        code_lines = {ln for ln in code_lines if any(a <= ln <= b for a, b in spans)}
    return len(code_lines)


def e2_sub(which: str) -> dict:
    import harness as Hn

    sc = Hn.Scenario([0], "combat", STEPS)
    if which == "numba":
        r = Hn.run(Hn.make_backend("numba", sc, "single"), sc, 0, STEPS, STEPS)
        import numba

        return {"digest": r["digests"][0], "jit_disabled": bool(numba.config.DISABLE_JIT)}
    import jax

    jax.config.update("jax_enable_x64", True)
    f = Hn.make_backend("jax", sc, "single", unroll=4)
    a = Hn.run(f, sc, 0, STEPS, STEPS)["digests"][0]
    with jax.disable_jit():
        b = Hn.run(f, sc, 0, STEPS, STEPS)["digests"][0]
    return {"digest_jit": a, "digest_disable_jit": b}


def main():
    if "--sub" in sys.argv:
        print(json.dumps(e2_sub(sys.argv[-1])))
        return
    files = {
        "numpy_reference": HERE / "ref_numpy.py",
        "numba": HERE / "be_numba.py",
        "jax": HERE / "be_jax.py",
    }
    res = {"machine": machine_info(), "E1_kernel_loc": {k: logical_lines(v) for k, v in files.items()}}
    m5 = HERE / "s06_m5_gradients.py"
    res["E1_jacobian_code_loc"] = {
        "numba_fd_and_complex_step (method_numba)": logical_lines(m5, {"method_numba"}),
        "jax_jacfwd_and_grad (method_jax)": logical_lines(m5, {"method_jax"}),
    }
    env = dict(os.environ, XLA_FLAGS="--xla_cpu_multi_thread_eigen=false", NUMBA_NUM_THREADS="1")

    def sub(which, extra=None):
        e = dict(env, **(extra or {}))
        r = subprocess.run([PY, "-I", __file__, "--sub", which], capture_output=True, text=True, env=e)
        if r.returncode != 0:
            return {"error": r.stderr.strip().splitlines()[-1][:300]}
        return json.loads(r.stdout.strip().splitlines()[-1])

    nb_c = sub("numba")
    nb_py = sub("numba", {"NUMBA_DISABLE_JIT": "1"})
    res["E2_numba"] = {"compiled": nb_c, "uncompiled_python": nb_py,
                       "same_digest": nb_c.get("digest") == nb_py.get("digest")}  # fmt: skip
    jx = sub("jax")
    res["E2_jax"] = {**jx, "same_digest": jx.get("digest_jit") == jx.get("digest_disable_jit")}
    print(json.dumps(res, indent=1), file=sys.stderr)
    save_json("m7_ergonomics.json", res)


if __name__ == "__main__":
    main()
