# Tejas model-parameter registry

There is one file per module: `M02.yaml` … `M22.yaml`. A module's numeric tables go in `<MODULE>/*.csv`.
The format and rules are defined in `src/phalanx/dictionary/params.py` (format `phalanx.params/1`). They are enforced
by `tests/unit/test_dictionary_params.py::test_repo_param_files_all_valid`:

- Every value has units, a description and evidence (`tag` + `source`).
- An `ASSUMPTION` needs a `sweep` range and an `assumption_id` registered in `docs/assumptions.md`.
- A `PROXY` needs an `assumption_id`.
- Values are converted to SI when loaded.

Channel semantics (ranges, LSBs, rates, bus map) stay in `configs/tejas/dictionary/` (M01). Model parameters (gains,
maps, time constants, rates of processes) live here. `registry_hash()` goes into every run manifest.
