"""A3 guard (W2.4a): Tail 687 archive 2 is reserved for the AD-33 gate (W2.4b) and is never read here.

Every proxy-mode file access goes through :func:`check_path` before anything is opened, and the proxy package
never names the reserved directory anywhere else (a static test greps the package and the W2.4a analysis
code). Only the pre-registered gate run (W2.4b) may pass ``allow_reserved=True``, after its pre-registration
is committed; no W2.4a code does.
"""

from __future__ import annotations

import os
from pathlib import Path

#: path component of the reserved archive (DASHlink Tail 687 archive 2)
RESERVED_COMPONENT = "raw2"


class ReservedDataError(PermissionError):
    """Raised before any read of the reserved archive."""


def is_reserved(path: str | os.PathLike[str]) -> bool:
    """True when ``path`` lies in (or is) the reserved archive directory (any path component named raw2)."""
    return RESERVED_COMPONENT in Path(path).parts


def check_path(path: str | os.PathLike[str], *, allow_reserved: bool = False) -> Path:
    """Return ``path`` as a Path, or raise :class:`ReservedDataError` if it points into the reserved
    archive."""
    p = Path(path)
    if is_reserved(p) and not allow_reserved:
        raise ReservedDataError(
            f"{p}: Tail 687 archive 2 is reserved for the AD-33 gate (W2.4b) and must not be read, listed or "
            "loaded in W2.4a"
        )
    return p


__all__ = ["RESERVED_COMPONENT", "ReservedDataError", "check_path", "is_reserved"]
