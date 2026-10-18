"""M07 F404-IN20 engine truth model: CLM, dynamic shell, surrogate hooks (architecture §6 M07, AD-09).

Public API (see README.md):

- ``ports.PREFIX`` / ``ports.ports(n_engines)``: published ports and catalogue bindings;
- ``module.EngineModule``: the core module (240 Hz, ``step`` / ``step_block``);
- ``design.build_engine_model`` / ``load_engine_params``: parameters -> design point -> kernel vector;
- ``steady.steady_state`` / ``operating_line`` / ``linearize``: equilibria, sweeps, small-signal models;
- ``sim.simulate`` / ``state_from_x`` / ``input_block``: transient-window simulation for identification;
- ``ident.residuals`` / ``ident.jacobian_cs`` / ``ident.transient_weights``: AD-34 transient-weighted fits;
- ``corrected.corrected``: theta/delta corrected-parameter conventions.
"""
