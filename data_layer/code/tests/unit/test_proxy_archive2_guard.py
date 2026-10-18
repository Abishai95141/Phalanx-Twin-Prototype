"""A3 (W2.4a): Tail 687 archive 2 is reserved for the AD-33 gate (W2.4b); no W2.4a code may open it.

- the guard refuses a reserved path **before** any file system access (the refused path does not exist, so an
  attempted open would raise FileNotFoundError instead; an audit hook also sees no open);
- every proxy entry point that takes a path (``load_inputs``, ``mat_path``, the MF1 study's ``guarded``)
  goes through it;
- static grep: the reserved directory name appears in the proxy package only in ``proxy/guard.py``, and
  nowhere in the W2.4a analysis code (which imports the guard), so no other code can name it.

No data: synthetic paths only.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from phalanx.proxy.guard import RESERVED_COMPONENT, ReservedDataError, check_path, is_reserved
from phalanx.proxy.inputs import load_inputs, mat_path

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
RESERVED = Path("/nonexistent") / "dashlink_tail687" / RESERVED_COMPONENT / "mat" / "687200101010000.mat"


def test_guard_refuses_the_reserved_archive_and_passes_others():
    assert is_reserved(RESERVED) and is_reserved(RESERVED.parent.parent)
    assert not is_reserved("/data/dashlink_tail687/raw/mat/687200101010000.mat")
    assert not is_reserved("/data/raw20/x.mat")  # a component, not a substring
    with pytest.raises(ReservedDataError):
        check_path(RESERVED)
    assert check_path("/data/raw/x.mat") == Path("/data/raw/x.mat")


def test_entry_points_refuse_before_any_file_access():
    """load_inputs on a reserved path raises the guard error, not FileNotFoundError, and opens nothing."""
    opened: list[str] = []

    def hook(event, args):
        if event == "open" and args and RESERVED_COMPONENT in str(args[0]):
            opened.append(str(args[0]))

    sys.addaudithook(hook)  # audit hooks cannot be removed; this one only records
    with pytest.raises(ReservedDataError):
        load_inputs(RESERVED)
    with pytest.raises(ReservedDataError):
        mat_path(RESERVED.parent, RESERVED.name)
    assert opened == []


def test_mf1_study_guard_refuses_reserved_and_non_cal_files():
    path = ROOT / "analysis" / "proxy_quicklook" / "code" / "common.py"
    spec = importlib.util.spec_from_file_location("proxy_quicklook_common", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cal = sorted(mod.cal_flights())
    with pytest.raises(ReservedDataError):
        mod.guarded(RESERVED.parent, cal[0])
    with pytest.raises(mod.DataGuardError):
        mod.guarded("/data/raw/mat", "687200104111441.mat")  # a 687-TEST flight (splits.csv)
    with pytest.raises(mod.DataGuardError):
        mod.guarded("/data/dashlink_tail652/mat", cal[0])
    assert mod.guarded("/data/raw/mat", cal[0]) == Path("/data/raw/mat") / cal[0]


def test_static_grep_reserved_name_only_in_the_guard():
    hits = []
    for base in (ROOT / "src" / "phalanx" / "proxy", ROOT / "analysis" / "proxy_quicklook"):
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix in (".py", ".md", ".yaml", ".json", ".txt"):
                if RESERVED_COMPONENT in p.read_text(encoding="utf-8", errors="ignore"):
                    hits.append(p.relative_to(ROOT).as_posix())
    assert hits == ["src/phalanx/proxy/guard.py"], hits
