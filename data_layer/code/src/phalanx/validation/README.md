# `phalanx.validation`: M20 validation and calibration harness (W0.5 skeleton)

The behavioural fidelity battery (B1–B6), the guards (G0 binding, G1 diagnostic, label-leak interface), a
deterministic sample selector and a NASA-STD-7009B credibility-card stub. The battery is the project's
primary realism gate (architecture §14.1, AD-21, AD-30): synthetic-vs-real distances against real-vs-real
bars, with a flight-bootstrap FAIL rule. Discriminators are not part of it (diagnostic only).

Binding sources: `docs/architecture.md` §1, §6 M20, §14, §15, AD-21, AD-30, AD-33; the round-2
pre-registration `analysis/settling_experiment_round2/PREREGISTRATION.md` §4–5 and `DEVIATIONS.md` D1–D8;
`analysis/correlation_check/` (B1).

## Files

| File | Contents |
|---|---|
| `flightdata.py` | `FlightRecord`: the battery's input structure (see below) |
| `battery/config.py` | `BatteryConfig` (DASHlink proxy defaults) and the pre-registered estimator constants |
| `battery/stats.py` | per-flight statistics B1–B6 (`flight_stats`, `flight_stats_many`), port of round-2 `battery.py` |
| `battery/evaluate.py` | distances, joint flight bootstrap, verdicts, decision rule; port of round-2 `battery_eval.py` |
| `battery/run.py` | `run_battery`: the round-2 protocol (bars, paired arms, comparison order) |
| `guards/g0.py` | G0 metadata vector (port of round-1 `features.gate0`) and audit (port of `s07_gate0.evaluate`) |
| `guards/g1.py` | G1 residue counts and total-variation distance |
| `guards/label_leak.py` | label-leak audit (W2.5): paired pipeline invariance, texture-only and metadata-only feature sets on `RecordedRun` or `FlightRecord`, classifier core (one-sided, AD-40) |
| `guards/classify.py` | grouped CV, flight-level AUC, bootstrap (port of round-1 `learn.py` parts) |
| `samples.py` | deterministic flight-sample selector (`phalanx.core.rng`), n and justification recorded |
| `credibility.py` | credibility card: factors, levels, domain of validation, Level-2 ceiling, Markdown |
| `dashlink.py` | DASHlink MAT → `FlightRecord` adapter (port of `dlio.load_flight` + `r2common.load`); refuses `raw2/` |
| `reference.py` | readers for stored round-2 per-flight statistics, flight lists and `battery.json` |
| `testing.py` | **control fixture, not a model**: toy control flights and negative-control operators |
| `boundary_fixtures.py` | **control fixture**: flights and PLA traces placed exactly on every battery threshold |
| `units.py` | pint unit equivalence for the unit check (`units_equivalent`) |
| `golden/` | data-free golden fixtures made by the original round-1/round-2 code (`round2_golden.*`, `round2_boundaries.*`) and their generator scripts |

## Input structure (for W2.4 proxy mode, W1.6/W1.7 producers, the contract reader)

```python
FlightRecord(
    flight_id: str,                  # file stem or sortie_id
    rate_hz: float,                  # analysis rate; 4.0 for DASHlink engine words
    outputs: {family: ndarray (n_units, n)},   # "N1", "N2", "EGT", "FF"; row k = engine position k+1
    pla: ndarray (n_units, n),       # power-lever angle [deg]: defines throttle steps (B3 ii) and B3 (i) input
    theta: ndarray (n,),             # inlet total-temperature ratio (TAT + 273.15) / 288.15
    delta: ndarray (n,),             # inlet total-pressure ratio
    phase: ndarray (n,) int,         # flight-phase code (DASHlink PH 1..7)
    units: {name: unit},             # pint-equivalent to BatteryConfig.units (any spelling), never converted
    t0_ns: int = 0,                  # AD-35 time of sample 0
    meta: {str: str},                # provenance
)
```

- Values are **decoded engineering values** (contract `value_eu`), on one uniform grid, finite (the contract
  uses sentinels and validity, never NaN). Arrays are copied and frozen on construction.
- Units in proxy mode: N1/N2 `percent`, EGT `degC` (or `K`), FF `lb/h`, PLA `deg` (A-W0.5-1). Any pint-equivalent
  spelling passes (the dictionary's `lb/hr`, `%`, `degree`); dimensionally compatible but different units fail
  (`kg/s`, `K` for a `degC` channel, `rad`, `dimensionless` for `percent`), because nothing is converted.
- Real and synthetic versions of a flight must share `pla`, `theta`, `delta` and `phase` (paired D_sim).

## Use

```python
from phalanx.core.rng import RngService, StreamRegistry
from phalanx.validation.battery import BOOTSTRAP_STREAM, Bootstrap, flight_stats_many, run_battery
from phalanx.validation.samples import SAMPLE_STREAM, select_flights, temporal_halves

rng = RngService(root, StreamRegistry([SAMPLE_STREAM, BOOTSTRAP_STREAM]))
sample = select_flights(eligible, 20, rng=rng, scenario="proxy_gate.s20", purpose="...", justification="...")
H = flight_stats_many(holdout_records)  # real holdout
P = flight_stats_many(partner_records)  # D_tail partner, equal count
S = {"arm": flight_stats_many(synthetic_records)}  # paired with H by flight
report = run_battery(H, P, early_idx, late_idx, S, Bootstrap.from_service(rng, "proxy_gate.s20"))
report.arms["arm"].verdicts["B1"].verdict  # PASS / FAIL / INCONCLUSIVE, with D_sim, D_tail, D_temp, CIs, n
```

`Bootstrap(np.random.SeedSequence(20261015))` and `select_flights(..., entropy=...)` are the round-2
compatibility mode (PCG64 over an explicit SeedSequence): use them only to reproduce round-2 numbers/lists.

## Reproduction of round 2 (W0.5 acceptance A1/A2)

| Check | n | Result | Tolerance |
|---|---|---|---|
| Evaluation layer on the stored round-2 per-flight stats, all 9 arms, `holdout_652_s20` | 20 per group | 3,486 values (D, CIs, bounds, group values) bit-identical; all verdicts equal | rtol 1e-12 |
| Per-flight stats from MAT files, 11 groups, round-2 environment | 20 | bit-identical | exact |
| Per-flight stats from MAT files, build environment | 20 | ≤ ~1e-11 relative; B3 (ii) τ ≤ 1.7e-4 relative | rtol 1e-9; τ rtol 1e-3 |
| End-to-end (MAT → port stats → port battery), 4 arms | 20 | verdicts equal; distances within tolerance | rtol 1e-9; B3 (ii) 1e-3 |
| G0 metadata vectors (342 features), G0 audit, G1 | 20 + 20 | exact | exact |
| Flight lists (`holdout_652`, `holdout_652_s20`, temporal halves) | 110 / 20 | identical | exact |
| Data-free golden (control flights, original round-2 code in `.venv-settling`) | 4 per group | evaluation layer exact; stats within tolerance | as above |
| Data-free boundary golden (inputs on every threshold, original round-1/round-2 code) | 1 constructed case per side of each threshold | identical side of every threshold; `find_steps`, evaluation, settings exact | as above |
| Scale step (one-off script, after the s20 checks passed): full `holdout_652`, all 9 arms | 110 per group | evaluation layer bit-identical; from MAT ≤ 6.1e-15 relative (B3 ii ≤ 4.0e-7); 0 verdict mismatches | as above |
| Same script on `holdout_652_s20`, all 9 arms from MAT | 20 | ≤ 4.8e-15 relative (B3 ii ≤ 1.4e-7); 0 verdict mismatches | as above |

Two port details matter for exactness: B5 group moments are summed left to right (Python ≥ 3.12's builtin
`sum` is compensated for floats and moves B5 (i) by ~1e-11), and the B3 (ii) time constants depend on
scipy's least-squares path (1e-7 to 1.7e-4 relative between scipy 1.17 and 1.18).

## Test layout and markers (all tiers)

| Directory | What goes there | Marker(s) | In `make check` |
|---|---|---|---|
| `tests/unit/` | one function or class, constructed inputs with known answers, guards and error paths | `unit` | yes |
| `tests/property/` | hypothesis invariants (D(A, A) = 0, symmetry, verdict rule, selector properties) | `property` | yes |
| `tests/golden/` | reproduction of a frozen reference (round-2 code outputs, MQTG replays, pinned mappings) | `golden` | yes |
| `tests/statistical/` | ensembles and negative/positive controls with a stated n (data-free) | `statistical` | yes |
| `tests/integration/` | several modules together; real-data reproduction (also `data`, `slow`) | `integration` | yes, unless `data`/`slow` |
| `tests/fork/` | snapshot, replay, fork and CRN tests | `fork` | yes |
| any | needs DASHlink or other external data (paths from env, skipped when absent) | `data` | **no** (`make test-all`) |
| any | long-running (minutes) | `slow` | **no** (`make test`) |
| any | bitwise determinism | `determinism` | yes |

File names are `test_<package>_*.py` (this package: `test_validation_*.py`). Every test that uses data states
its n and why in its docstring. Data paths: `PHALANX_DASHLINK_652`, `PHALANX_DASHLINK_687` (archive 1 only),
`PHALANX_ROUND2_SYNTHETIC`. Tail 687 archive 2 (`raw2/`) is reserved for the AD-33 gate; `dashlink.load_mat`
refuses it.

## Assumptions (tagged; registered in `docs/assumptions.md`, section W0.5)

| ID | Statement | Tag |
|---|---|---|
| A-W0.5-1 | Battery inputs are decoded engineering values in proxy units, checked not converted | [ASSUMPTION] |
| A-W0.5-2 | Battery constants are the DASHlink proxy configuration; no Tejas configuration yet | [ASSUMPTION] |
| A-W0.5-3 | Data-free tests use a toy control fixture (not a model) | [ASSUMPTION] (fixture) |
| A-W0.5-4 | G0 one-sided by default (decided, AD-40); two-sided only for round-2 reproduction | decision |
| A-W0.5-5 | G0 stand-in tables are fixture values | [ASSUMPTION] (fixture) |
| A-W0.5-6 | Credibility reported per factor and channel x regime, never one score | [ASSUMPTION] |

No `PROXY` items: the battery is a port of pre-registered estimators and models no physics.

## Validation criteria

- The port reproduces round 2 (table above) and the original code on control flights (`make check`).
- The battery can fail: fast-band decoupling FAILs B1/B4, a 2-s FF delay FAILs B2, a replicate of the same
  process PASSes all six (control flights); on DASHlink the same breaks FAIL and 20 other flights of the same
  tail draw no FAIL. G0 (one-sided) flags a dtype cue and a moderate record-length cue and does not flag null
  metadata; G1 separates single from double quantisation; the label-leak core flags a planted cue.
- Every battery threshold is pinned in `make check` by the boundary golden (inputs on each threshold, outputs
  of the original code): a one-sample or sub-LSB change of any threshold fails it.
- **Mutation sweep (W0.5 E0 follow-up):** 77 single-constant mutations of the battery, guards, classifier and
  DASHlink adapter (one sample, 0.01 deg, 0.05 LSB, +-0.001 in R^2, one recorder LSB in the airborne rule, or the
  next integer), each run against the data-free validation tests: 76 caught. The survivor is the B2
  z-score guard `1e-12` → `1e-11`, which cannot change any output (the lag is the argmax of a correlation
  that every positive rescaling leaves unchanged; a zero-variance series gives all-zero correlations for any
  guard value). Resolution limits: the 5-LSB step rule is pinned to 0.05 LSB (lattice data averaged over
  20 samples), the airborne rule to one recorder LSB (0.03125 %).
- No global RNG, no wall-clock reads, no seed arithmetic (`tools/audit_static.py`, `tests/conftest.py`).

## Known limitations

- **G0 sidedness (decided, AD-40):** G0 and the label-leak audit are **one-sided by default**: FAIL only if
  the CI lower bound of the AUC is above 0.5. The pre-registered two-sided rule falsely FAILed 6 of 20 null
  replicates (40 pairs), always with the CI below 0.5; one-sided, none of them FAILs, and a real cue
  (AUC ~0.8) still FAILs. `sided="two"` reproduces round 2 and is used only for that.
- **Fast-band sensitivity to LSB-level noise:** ±1 LSB of independent noise on real s20 flights FAILs B1,
  B3 (i) and B4. M13 noise above the measured idiosyncratic level will fail the battery (consistent with
  round-2 REPORT §3.5).
- Boosting draws in G0/label-leak are seeded by spawn key, not round-1 seed arithmetic: identical results
  whenever the outcome does not depend on that draw (all round-2 G0 results).
- B9 (downstream fitness), B7 and B8 are not ported (build items); B3 (ii) depends on scipy's optimiser.
- The credibility card is a stub (structure and renderer); its content is W3.3.
- Only the four-engine, 4-Hz DASHlink configuration is defined (A-W0.5-2).
