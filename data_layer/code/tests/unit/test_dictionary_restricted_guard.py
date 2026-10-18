"""Guard: no restricted-source marker and no redacted value in any deliverable, and no redacted value in any
process document, analysis text or code, test or tool (report Appendix A1; E0 fix 1; E1 verifier §7; E1-HY
item 9).

Scanned, two tiers:

- **Deliverable roots** (markers and values): every file under ``configs/``, ``src/`` and ``docs/contract/``,
  plus a fresh build of the dictionary and all its generated artefacts (compiled JSON, TMATS text and Ch10
  setup record, ICD, tables, contract docs).
- **Process roots** (values only): every file under ``docs/`` (briefs, gate reports, the audit log, the
  assumption registry; ``docs/contract/`` is already a deliverable root), ``tests/`` and ``tools/``, and the
  text and code files of ``analysis/`` (binaries and data such as ``.csv``/``.json``/``.npz``/``.png`` are
  skipped). The marker words name the restricted sources; recording the policy in process documents, the
  audit trail and the redaction tests needs them, so only the values are banned there. A value is banned
  everywhere: E1 found restricted values quoted in a gate report, the audit log, a test docstring and
  analysis comments, which the deliverable-only guard could not see.

``research_notes/`` is internal evidence (sanity-check only) and is not scanned.

The restricted values are never written in this file. They are read at test time and turned into
in-context patterns, so the guard follows its sources without republishing them:

- the restricted-marked fragments of the raw inventory (a number with its unit, or a numeric band);
- the restricted column of the notes' two restricted-value replacement tables
  (``iaf_usage_and_validation_gap_closure.md`` table (c), rows whose old source is the NATOPS copy or the
  Hellenic manual; ``f404_in20_engine_model.md`` Q7 "Replacement status" table). Only **numeric bands** are
  taken from them, and two kinds are dropped by rule: a band whose two ends both appear in the row's
  officially released replacement (a released value that coincides, e.g. the T-50 idle band), and a band with
  a single-digit end (too generic to name a manual value). E1 showed why the inventory alone is not enough:
  every value quoted in the four files redacted on 2026-10-15 came from these tables, none from the
  inventory, so the extended roots alone would still have passed (E1-HY mutant run).

Files are decoded as UTF-8 (``errors="replace"``, so binary files are still scanned): the earlier Latin-1
decoding turned the en dash and the degree sign into two or three characters, so the guard's own ``[-–]``
and ``°C`` variants could never match a UTF-8 document written in the house style.

Sample: all files under the roots plus one build (the question is "is it anywhere", so nothing smaller
answers it). Negative controls plant a raw fragment, and the bare value, in a temporary tree for every root
kind (deliverable, docs, analysis code, tests, tools), and check the two documented exclusions (a marker in a
process root; a data file in ``analysis/``).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pytest

from phalanx.dictionary import build, compile_bundle, load_bundle
from phalanx.dictionary.generators import contract_v0_generator
from phalanx.dictionary.redact import GUARD_MARKER, RESTRICTED_MARKER, split_fragments
from phalanx.dictionary.seeder import read_inventory

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "configs" / "tejas" / "dictionary"
NOTES = REPO / "research_notes" / "Virtual fighter telemetry layer research"
INVENTORY = NOTES / "parameter_inventory.csv"
#: the notes' restricted-value replacement tables: (file, start of the line that opens the table, column of
#: the restricted value, column of the released replacement, (old-source column, accepted values) or None)
REPLACEMENT_TABLES = (
    ("iaf_usage_and_validation_gap_closure.md", "(Old source: N = F/A-18 NATOPS", 0, 2, (1, ("N", "H"))),
    ("f404_in20_engine_model.md", "**Replacement status for values that sibling notes took", 0, 1, None),
)
#: deliverable roots: neither a marker nor a value may appear
DELIVERABLE_ROOTS = (REPO / "configs", REPO / "src", REPO / "docs" / "contract", REPO / "solution_context")
#: process roots: no value may appear (markers allowed: they record the policy, see the module docstring)
PROCESS_ROOTS = (REPO / "docs", REPO / "analysis", REPO / "tests", REPO / "tools")
SCAN_ROOTS = DELIVERABLE_ROOTS + PROCESS_ROOTS
#: the one file allowed to name the markers (it defines them); values are still checked there
MARKER_EXEMPT = {REPO / "src" / "phalanx" / "dictionary" / "redact.py"}
#: ``analysis/`` is scanned for text and code only (E1-HY brief item 9: "skip binaries and data")
ANALYSIS_TEXT_SUFFIXES = frozenset(
    {".md", ".py", ".txt", ".sh", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".rst"}
)

_NUM = r"\d+(?:\.\d+)?"
_VALUE = re.compile(rf"(?<![\w.])({_NUM})(?:\s*[-–]\s*({_NUM}))?(?:\s*(degC|°C|psid|psi|kt|deg)\b)?")
_UNIT_VARIANTS = {"degC": r"\s*(?:degC|deg\s?C|°\s?C)", "°C": r"\s*(?:degC|deg\s?C|°\s?C)"}


def _restricted_fragments() -> list[tuple[str, str, str]]:
    """(param_id, field, fragment) for every restricted-marked fragment of the raw inventory."""
    out = []
    for row in read_inventory(INVENTORY):
        for field, text in row.items():
            out += [(row["param_id"], field, f) for f in split_fragments(text) if RESTRICTED_MARKER.search(f)]
    return out


def _value_patterns(fragment: str) -> list[tuple[re.Pattern[str], list[float]]]:
    """In-context patterns for the values of one fragment: numeric bands, and numbers followed by a unit.
    Bare numbers (for example an engine dash number) are not values and give no pattern."""
    out = []
    for m in _VALUE.finditer(fragment):
        a, b, unit = m.groups()
        if b is not None:
            pat = rf"(?<![\w.]){re.escape(a)}\s*[-–]\s*{re.escape(b)}(?![\d])"
            out.append((re.compile(pat), [float(a), float(b)]))
        elif unit is not None:
            unit_pat = _UNIT_VARIANTS.get(unit, rf"\s*{re.escape(unit)}")
            out.append((re.compile(rf"(?<![\w.]){re.escape(a)}{unit_pat}\b"), [float(a)]))
    return out


_TNUM = r"\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?"  # table numbers may carry thousands separators
_TBAND = re.compile(rf"(?<![\w.,])({_TNUM})\s*[-–]\s*({_TNUM})(?![\d,])")


def _table_rows() -> list[tuple[str, str, str]]:
    """(label, restricted cell, released-replacement cell) for every row of the replacement tables."""
    out = []
    for name, opener, col_v, col_r, src in REPLACEMENT_TABLES:
        lines = (NOTES / name).read_text(encoding="utf-8").splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith(opener))
        for line in lines[start + 1 :]:
            if line.startswith("#"):
                break
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) <= max(col_v, col_r) or set(cells[col_v]) <= set("-: "):
                continue
            if src is not None and cells[src[0]] not in src[1]:
                continue
            out.append((cells[col_v][:40], cells[col_v], cells[col_r]))
    return out


def _band_kind(a: str, b: str, released_nums: set[str]) -> str:
    """'released' (both ends in the released replacement), 'generic' (a single-digit end) or 'pattern'."""
    if a in released_nums and b in released_nums:
        return "released"
    if min(len(a.split(".")[0]), len(b.split(".")[0])) < 2:
        return "generic"
    return "pattern"


def _table_band_patterns() -> list[tuple[str, re.Pattern[str], tuple[float, float]]]:
    """(row label, in-context band pattern, band) from the restricted column of the replacement tables (rules
    in the module docstring)."""
    out = []
    for label, restricted, released in _table_rows():
        released_nums = {x.replace(",", "") for x in re.findall(_TNUM, released)}
        for m in _TBAND.finditer(restricted):
            a, b = (x.replace(",", "") for x in m.groups())
            if _band_kind(a, b, released_nums) != "pattern":
                continue
            ap, bp = (re.escape(x).replace(",", ",?") for x in m.groups())
            out.append((label, re.compile(rf"(?<![\w.,]){ap}\s*[-–]\s*{bp}(?![\d,])"), (float(a), float(b))))
    return out


@lru_cache(maxsize=1)
def _patterns() -> tuple[tuple[re.Pattern[str], tuple[float, ...]], ...]:
    pats = []
    for _, _, frag in _restricted_fragments():
        pats += [(p, tuple(v)) for p, v in _value_patterns(frag)]
    pats += [(p, v) for _, p, v in _table_band_patterns()]
    return tuple(pats)


def _files(roots, exclude=()) -> list[Path]:
    """Files under ``roots`` (sorted; no ``__pycache__``), minus anything under an ``exclude`` directory;
    under a root named ``analysis`` only text and code files (``ANALYSIS_TEXT_SUFFIXES``) are kept."""
    out = []
    ex = [Path(e) for e in exclude]
    for root in roots:
        for p in sorted(Path(root).rglob("*")):
            if not p.is_file() or "__pycache__" in p.parts or any(p.is_relative_to(e) for e in ex):
                continue
            if Path(root).name == "analysis" and p.suffix.lower() not in ANALYSIS_TEXT_SUFFIXES:
                continue
            out.append(p)
    return out


def scan(roots, exempt=frozenset(), *, markers=True, exclude=()) -> tuple[list[str], int]:
    """(findings, number of files scanned) for in-context restricted values and, if ``markers``, the guard
    markers."""
    findings = []
    files = _files(roots, exclude)
    for p in files:
        text = p.read_bytes().decode("utf-8", errors="replace")  # binary files are scanned too (ASCII kept)
        if markers and p not in exempt:
            findings += [f"{p}: marker {m.group(0)!r}" for m in GUARD_MARKER.finditer(text)]
        for pat, _ in _patterns():
            findings += [f"{p}: restricted value {m.group(0)!r}" for m in pat.finditer(text)]
    return findings, len(files)


def test_the_guard_knows_the_restricted_values():
    frags = _restricted_fragments()
    assert {(pid, f) for pid, f, _ in frags} == {
        ("ENG.T5", "notes_conflicts"),
        ("ENG.OIL_P", "notes_conflicts"),
        ("ENG.FUEL_INLET_T", "notes_conflicts"),
    }
    assert len(_patterns()) >= 4  # one band or value-with-unit per restricted figure
    # the notes' replacement tables are found and still carry their bands (a format change must fail here,
    # not silently weaken the guard): 30 band patterns from 21 of 49 rows on 2026-10-15
    tb = _table_band_patterns()
    assert len(tb) >= 25 and len({label for label, _, _ in tb}) >= 18
    assert len(_table_rows()) >= 40


def test_released_coincidences_and_generic_bands_are_not_patterns():
    """The table rule drops bands whose ends both appear in the row's released replacement (the T-50 idle
    band is released evidence) and bands with a single-digit end; every other band of the restricted column
    is a pattern."""
    kept = {v for _, _, v in _table_band_patterns()}
    kinds = []
    for _, restricted, released in _table_rows():
        released_nums = {x.replace(",", "") for x in re.findall(_TNUM, released)}
        for m in _TBAND.finditer(restricted):
            a, b = (x.replace(",", "") for x in m.groups())
            kinds.append(_band_kind(a, b, released_nums))
            if kinds[-1] == "pattern":
                assert (float(a), float(b)) in kept
    assert kinds.count("released") >= 1 and kinds.count("generic") >= 1 and kinds.count("pattern") >= 25


def test_no_restricted_marker_or_value_in_deliverables(tmp_path):
    build(CONFIG, tmp_path, extra_generators={"contract": contract_v0_generator})
    findings, n = scan([*DELIVERABLE_ROOTS, tmp_path], exempt=MARKER_EXEMPT)
    assert n > 100
    assert findings == [], findings[:10]


def test_no_restricted_value_in_docs_analysis_tests_or_tools():
    """E1-HY item 9: briefs, gate reports, the audit log, analysis text and code, tests and tools carry no
    restricted value (the deliverable roots are covered above; ``docs/contract`` is not scanned twice)."""
    findings, n = scan(PROCESS_ROOTS, markers=False, exclude=(REPO / "docs" / "contract",))
    assert n > 400  # 437 files on 2026-10-15; a collapse of the walk would show here
    roots_seen = {p.relative_to(REPO).parts[0] for p in _files(PROCESS_ROOTS, (REPO / "docs" / "contract",))}
    assert roots_seen == {"docs", "analysis", "tests", "tools"}
    assert findings == [], [f.split(": restricted value")[0] for f in findings[:10]]


def test_redacted_values_are_not_limits_or_ranges():
    """No number from a redacted fragment is a range bound or limit of that parameter's channels."""
    content = compile_bundle(load_bundle(CONFIG)).content
    for pid, _, frag in _restricted_fragments():
        values = {v for _, vs in _value_patterns(frag) for v in vs}
        assert values, frag
        for cid in content["parameters"][pid]["channel_ids"]:
            ch = content["channels"][cid]
            used = set()
            if ch["range"]:
                used |= {ch["range"]["min"], ch["range"]["max"]}
            for lim in ch["limits"]:
                used |= {v for k, v in lim.items() if isinstance(v, int | float) and not isinstance(v, bool)}
            assert not (used & values), (cid, sorted(used & values))


def test_guard_catches_a_planted_fragment(tmp_path):
    """Negative control: a raw restricted fragment planted in a config file is found (marker and value)."""
    _, _, frag = _restricted_fragments()[0]
    planted = tmp_path / "configs" / "tejas" / "dictionary" / "tables" / "planted.yaml"
    planted.parent.mkdir(parents=True)
    planted.write_text(f"note: '{frag}'\n", encoding="utf-8")
    findings, _ = scan([tmp_path])
    assert any("marker" in f for f in findings), findings
    assert any("restricted value" in f for f in findings), findings


def test_guard_catches_a_planted_value_without_its_marker(tmp_path):
    """Negative control: the value alone, with the marker words removed, is still found in context."""
    for _, _, frag in _restricted_fragments():
        bare = RESTRICTED_MARKER.sub("manual", frag)
        assert not GUARD_MARKER.search(bare)
        p = tmp_path / "docs" / "contract" / "planted.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"| planted | {bare} |\n", encoding="utf-8")
        findings, _ = scan([tmp_path])
        assert findings and all("restricted value" in f for f in findings), (frag, findings)


@pytest.mark.parametrize(
    "rel",
    [
        "docs/build_gates/planted_gate_report.md",
        "docs/build_audit_log.md",
        "docs/build_briefs/planted_brief.md",
        "analysis/some_experiment/code/planted.py",
        "analysis/some_experiment/REPORT.md",
        "tests/unit/test_planted.py",
        "tools/planted_tool.py",
    ],
)
def test_process_roots_catch_a_planted_bare_value(tmp_path, rel):
    """Negative control (E1-HY item 9): the bare value (marker words removed) planted in each process-root
    kind is found by the value scan used for the real process roots (``markers=False``)."""
    _, _, frag = _restricted_fragments()[0]
    bare = RESTRICTED_MARKER.sub("manual", frag)
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"note: {bare}\n", encoding="utf-8")
    findings, n = scan([tmp_path / rel.split("/")[0]], markers=False)
    assert n == 1
    assert findings and all("restricted value" in f for f in findings)


def test_process_roots_allow_marker_words_but_deliverables_do_not(tmp_path):
    """Documented design (module docstring): a marker word with no value is allowed in a process root and
    rejected in a deliverable root."""
    line = "The NATOPS-derived band is restricted-source and is not used.\n"
    for rel in ("docs/build_audit_log.md", "configs/tejas/note.yaml"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(line, encoding="utf-8")
    assert scan([tmp_path / "docs"], markers=False)[0] == []
    found, _ = scan([tmp_path / "configs"])
    assert len(found) == 2 and all("marker" in f for f in found)


def test_analysis_data_files_are_skipped_by_design(tmp_path):
    """Documented exclusion (brief item 9: analysis text and code only): a planted value in an analysis data
    file (.csv) is not scanned, while the same value in an analysis .txt log is found."""
    _, _, frag = _restricted_fragments()[0]
    bare = RESTRICTED_MARKER.sub("manual", frag)
    for name in ("results/table.csv", "results/log_run.txt"):
        p = tmp_path / "analysis" / "exp" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"{bare}\n", encoding="utf-8")
    findings, n = scan([tmp_path / "analysis"], markers=False)
    assert n == 1 and findings and all("log_run.txt" in f for f in findings)


def test_guard_catches_utf8_en_dash_and_degree_sign_variants(tmp_path):
    """Negative control for the decoding fix: the inventory values rewritten in the house style (en-dash
    bands, degree sign) in a UTF-8 file are found. Under the old Latin-1 decoding they were missed."""
    for k, (_, _, frag) in enumerate(_restricted_fragments()):
        bare = RESTRICTED_MARKER.sub("manual", frag)
        styled = re.sub(r"(\d)\s*-\s*(\d)", "\\1\u2013\\2", bare).replace("degC", "\u00b0C")
        assert styled != bare
        p = tmp_path / "docs" / f"styled_{k}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"| styled | {styled} |\n", encoding="utf-8")
        findings, _ = scan([p.parent], markers=False)
        assert any(f"styled_{k}.md" in f for f in findings), k


@pytest.mark.parametrize("dash", ["\u2013", "-"])
def test_guard_catches_a_planted_replacement_table_band(tmp_path, dash):
    """Negative control: every band of the notes' replacement tables (restricted column), planted in a gate
    report with an en dash or a hyphen, is found."""
    bands = _table_band_patterns()
    for k, (_, _, (a, b)) in enumerate(bands):
        text = f"{a:,.0f}{dash}{b:,.0f}" if max(a, b) >= 1000 else f"{a:g}{dash}{b:g}"
        p = tmp_path / "docs" / "build_gates" / f"planted_{k}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"The band was {text} in the manual.\n", encoding="utf-8")
    findings, n = scan([tmp_path / "docs"], markers=False)
    hit = {f.split(": restricted value")[0] for f in findings}
    assert n == len(bands) and len(hit) == n


def test_guard_ignores_unrelated_numbers(tmp_path):
    """Control: ordinary numbers and the redaction placeholder do not trigger the guard."""
    from phalanx.dictionary.redact import REDACTION_PLACEHOLDER

    p = tmp_path / "configs" / "ok.yaml"
    p.parent.mkdir(parents=True)
    p.write_text(
        f"range: [371, 871]\nlimit: 830\nnote: '{REDACTION_PLACEHOLDER}'\nrt: 45\n", encoding="utf-8"
    )
    findings, _ = scan([tmp_path])
    assert findings == []
