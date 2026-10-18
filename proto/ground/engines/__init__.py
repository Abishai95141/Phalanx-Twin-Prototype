"""Diagnostic and predictive engines of the ground side (DEVELOPMENT.md §2.5).

Each engine module exposes ``run(store, twin, t) -> list[interfaces.Finding]``; every Finding and Belief carries
the model id, version and source label from ``engines.common.MODELS``. Engines read only through the as-of store
(``t_ingest ≤ t``) and share one per-epoch context (``engines.common.context``) so the frames are read once.

S2 owns every module here except ``hazard.py`` and ``engine_health.py`` (S3).
"""
