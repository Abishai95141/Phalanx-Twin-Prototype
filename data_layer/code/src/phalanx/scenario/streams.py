"""M02 stream declarations (AD-37); see :mod:`.generator` for their use."""

from __future__ import annotations

from phalanx.core.rng import StreamDecl, Variate

SUBSYSTEM = "scenario"
STREAMS: tuple[StreamDecl, ...] = (
    StreamDecl(
        SUBSYSTEM, "weather", ("scenario", "base", "date"), Variate.GENERATOR, 1, "M02", "IMD day draws"
    ),
    StreamDecl(
        SUBSYSTEM,
        "day",
        ("scenario", "base", "date"),
        Variate.GENERATOR,
        1,
        "M02",
        "waves, cancels, rotation",
    ),
    StreamDecl(
        SUBSYSTEM, "slot", ("scenario", "sortie"), Variate.GENERATOR, 1, "M02", "per-slot sortie draws"
    ),
    StreamDecl(SUBSYSTEM, "pilot", ("scenario", "serial"), Variate.GENERATOR, 1, "M02", "pilot traits"),
    StreamDecl(SUBSYSTEM, "tail", ("scenario", "tail"), Variate.GENERATOR, 1, "M02", "tail affinity"),
    StreamDecl(
        SUBSYSTEM, "ground_run", ("scenario", "tail", "date"), Variate.GENERATOR, 1, "M02", "ground runs"
    ),
    StreamDecl(
        SUBSYSTEM, "usage", ("scenario", "sortie"), Variate.GENERATOR, 1, "M02", "usage drivers (chute)"
    ),
)

__all__ = ["STREAMS", "SUBSYSTEM"]
