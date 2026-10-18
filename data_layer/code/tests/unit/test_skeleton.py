"""W0.1: the package skeleton matches architecture §16 and the static audit catches what it must."""

from __future__ import annotations

import importlib
import subprocess
import sys
import textwrap

import pytest

import phalanx

SUBPACKAGES = [
    "core",
    "dictionary",
    "scenario",
    "environment",
    "pilot",
    "fcs",
    "airframe",
    "engine",
    "fadec",
    "utilities",
    "health",
    "faults",
    "sensors",
    "acquisition",
    "monitoring",
    "bus",
    "recorder",
    "ground",
    "maintenance",
    "streaming",
    "validation",
    "orders",
    "fork",
]


@pytest.mark.unit
def test_version():
    assert phalanx.__version__


@pytest.mark.unit
@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_imports(name):
    mod = importlib.import_module(f"phalanx.{name}")
    assert mod.__doc__, f"phalanx.{name} needs a docstring naming its module ID"


BAD = {
    "R1": "import numpy as np\nx = np.random.normal(0, 1)\n",
    "R2": "import numpy as np\ng = np.random.default_rng()\n",
    "R2-from": "from numpy.random import default_rng\ng = default_rng()\n",
    "R2-bitgen": "import numpy as np\ng = np.random.Generator(np.random.PCG64())\n",
    "R2-seedseq": "import numpy.random as npr\nss = npr.SeedSequence()\n",
    "R2-none": "import numpy as np\nss = np.random.SeedSequence(entropy=None)\n",
    "R3": "import random\n",
    "R4": "import time\nt = time.time()\n",
    "R4-from": "from time import perf_counter\nt = perf_counter()\n",
    "R4-datetime": "from datetime import datetime\nt = datetime.now()\n",
    "R5": "k = hash('abc')\n",
    "R6": "def f(seed):\n    return seed + 1\n",
    "R7-urandom": "import os\nb = os.urandom(8)\n",
    "R7-uuid": "from uuid import uuid4\nu = uuid4()\n",
    "R7-secrets": "import secrets\n",
    "R7-id": "x = object()\nk = id(x)\n",
    "R7-pid": "import os\np = os.getpid()\n",
    "R8": "from numba import njit\n\n@njit\ndef f(x):\n    return x ** 2\n",
}


@pytest.mark.unit
@pytest.mark.parametrize("rule", sorted(BAD))
def test_static_audit_catches(tmp_path, repo_root, rule):
    f = tmp_path / "bad.py"
    f.write_text(BAD[rule])
    r = subprocess.run(
        [sys.executable, "-I", str(repo_root / "tools/audit_static.py"), str(f)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1 and rule.split("-")[0] in r.stdout, r.stdout


@pytest.mark.unit
def test_static_audit_allows_annotated_and_clean(tmp_path, repo_root):
    f = tmp_path / "ok.py"
    f.write_text(
        textwrap.dedent("""\
        import numpy as np
        ss = np.random.SeedSequence(entropy=1, spawn_key=(3, 4))
        g = np.random.Generator(np.random.Philox(ss))
        g2 = np.random.default_rng(np.random.SeedSequence(7))
        def f(secrets):  # a local name 'secrets' is not the secrets module
            return list(secrets)
        def g(x):  # an integer power outside a jitted function is fine
            return x ** 2
        import time
        t = time.perf_counter()  # audit: allow R4 benchmark timing only
    """)
    )
    r = subprocess.run(
        [sys.executable, "-I", str(repo_root / "tools/audit_static.py"), str(f)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout
