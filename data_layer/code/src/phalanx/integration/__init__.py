"""W2.1a integration core: the truth loop of one aircraft built from the published port bindings.

- :mod:`.wiring` derives every ``Connection`` from the modules' ``ports.py`` bindings (never hand-wired) and
  documents each one-frame delay (architecture §8);
- :mod:`.system` builds the per-sortie telemetry-mode ``System`` (M02-M14) for one tail;
- :mod:`.fused` is the compiled truth-loop ``FusedGroup`` (AD-22, AD-36), bitwise equal to the per-step path;
- :mod:`.validate` checks every dispatched cross-module event against ``configs/interfaces/w1_events.yaml``;
- :mod:`.sortie` runs a sortie with the M13 recorder and the M14 feed, and snapshots/forks it;
- :mod:`.realised_usage` flies an M02 fleet plan in telemetry mode and returns the realised usage statistics.

See ``README.md`` in this package.
"""
