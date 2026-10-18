"""Redaction of restricted-manual values from inventory text (report Appendix A1; RULES.md rule 3).

Some inventory rows record, as a sanity-check note, a value whose only source is a restricted or
limited-distribution manual. Report Appendix A1 says such values "must not appear in deliverables". The
seeder therefore redacts every inventory field **before** it reads any value from it:

- A field is split into fragments at ``;`` outside parentheses (the inventory's fragment separator).
- A fragment that carries a restricted-source marker (:data:`RESTRICTED_MARKER`) is replaced, as a whole, by
  :data:`REDACTION_PLACEHOLDER`. Numbers in it are never carried, and nothing derived from it is either: the
  provenance checks (``textcheck``) see only the redacted text, so no field can claim a redacted value.
- All other fragments, and the separators and whitespace between them, are kept byte for byte.

This module is the only place in ``src/`` and ``configs/`` that names the markers.
``tests/unit/test_dictionary_restricted_guard.py`` scans the deliverables for the markers and for the
redacted values in context.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

__all__ = [
    "GUARD_MARKER",
    "REDACTION_PLACEHOLDER",
    "RESTRICTED_MARKER",
    "redact_row",
    "redact_text",
    "split_fragments",
]

#: a fragment carrying any of these is restricted-source (report Appendix A1: the restricted F/A-18 manual
#: copy and the Hellenic AF F-16 manual; "restricted-source" is the inventory's own label)
RESTRICTED_MARKER = re.compile(
    r"restricted|NATOPS|Hellenic|limited[- ]distribution|do not cite", re.IGNORECASE
)

#: markers that must never appear in a deliverable (the guard test); narrower than RESTRICTED_MARKER, because
#: "restricted" alone is ordinary vocabulary elsewhere (for example the W0.4 restricted truth tree)
GUARD_MARKER = re.compile(r"NATOPS|Hellenic|restricted[- ]source", re.IGNORECASE)

#: replaces a restricted-source fragment; it names no value and carries no guard marker
REDACTION_PLACEHOLDER = "[redacted: restricted-manual value omitted; see report Appendix A1]"


def split_fragments(text: str) -> list[str]:
    """Split ``text`` at ``;`` outside parentheses/brackets. ``";".join(result) == text``."""
    out: list[str] = []
    depth = 0
    start = 0
    for i, ch in enumerate(text):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        elif ch == ";" and depth == 0:
            out.append(text[start:i])
            start = i + 1
    out.append(text[start:])
    return out


def redact_text(text: str) -> tuple[str, int]:
    """(``text`` with every restricted-source fragment replaced by the placeholder, number of fragments
    replaced)."""
    frags = split_fragments(text)
    n = 0
    for i, frag in enumerate(frags):
        if RESTRICTED_MARKER.search(frag) and frag.strip() != REDACTION_PLACEHOLDER:
            lead = frag[: len(frag) - len(frag.lstrip())]
            trail = frag[len(frag.rstrip()) :]
            frags[i] = f"{lead}{REDACTION_PLACEHOLDER}{trail}"
            n += 1
    return ";".join(frags), n


def redact_row(row: Mapping[str, str]) -> tuple[dict[str, str], list[str]]:
    """(a redacted copy of an inventory row, the names of the fields that were changed, in row order)."""
    out: dict[str, str] = {}
    changed: list[str] = []
    for key, value in row.items():
        new, n = redact_text(value)
        out[key] = new
        if n:
            changed.append(key)
    return out, changed
