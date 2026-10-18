# `phalanx.proxy`: DASHlink proxy mode (W2.4a)

The build's engine-side chain in the DASHlink Tail 687 configuration (architecture §14.3, AD-31…AD-34,
AD-43, AD-46, AD-50, AD-52), driven by recorded **inputs** only. Configuration: `configs/proxy_dashlink/`
(dictionary, M03, M07, M08, M12, M13). Engine: M07 `separate_fixed` (`phalanx.engine.separate`,
`separate_design`; topology hook `engine.topology`).

| File | Content |
|---|---|
| `inputs.py` | DASHlink MAT -> recorded inputs (PLA x4, pressure altitude, Mach, TAT, PH, WOW, ATEN, N1C), A3-guarded; `running_window` (whole flight with every engine running, from levers and PH); `synthetic_inputs` (tests, A2, A6) |
| `guard.py` | A3: refuses any path into the reserved archive before it is opened |
| `replay.py` | U4 replay producers: `AirframeReplay` (af.mach/tas/alt; ports = `airframe.ports.replay_ports`), `ProxyBoundary` (util.*, health.*), `NoAfterburnerLane` |
| `system.py` | the proxy `System`, wired only from published bindings; `wiring_problems` (its own conformance check); engine trim at the first sample |
| `loop.py` | `ProxyLoopGroup`: compiled fused block over M08/M07/M12/M13-lanes (bitwise equal to the modules) |
| `run.py` | `simulate_flight` -> textured `FlightRecord` + truth and sensor levels at the same instants + per-sample M08 regulator; PROTOTYPE `word_delay_s` |
| `schedules.py`, `config.py` | M08 tables derived from the proxy M07 (regenerated in tests); `load_proxy_config` |
| `ident.py` | identification machinery (AD-34): deterministic closed-loop model, transient-weighted OE / PEM with an AR innovations model, direct method, residual spectra |

## U3 (multi-engine lanes) and U4 (replay producers)

- **U3.** M12 builds one sensor instance per engine for every channel whose truth input carries the engine
  axis (`ENG.N1.A:E1` … `:En`, reading element k); M13's `LaneAcquisition` groups the instances of one
  dictionary lane into a (capacity, n_engines) port bound as `lane.<channel_id>`; M10's `health.sensor_bias`
  index map follows M12's instances. For one engine nothing changes (plain channel ids; golden digest test).
- **U4.** The recorded flight condition is produced inside the chain: `scenario.phase` by
  `scenario.replay.ScenarioReplay` (`scenario.ports.replay_ports`), `af.mach/tas/alt` by
  `AirframeReplay` (`airframe.ports.replay_ports`, a partial publication of M06). The hardened conformance gate
  includes them (PROXY configuration) and its U3/U4 exceptions are removed.

## Assumptions and validation

Assumptions: `docs/assumptions.md` W2.4a rows A-W2.4a-1…20 (cycle, anchors, maps, inertias, proxy lanes, ACMS
clock, M08 regimes and derived schedules, U4 constants, whole-flight window, A/T representation, PROTOTYPE
flags, the off-design plant limitation, the identification model). Known limitation (A-W2.4a-19): the
un-identified plant's part-power fuel/EGT levels and its ram-driven LP spool at flight idle; W2.4a-2 steady
identification replaces them.

Validation: `tests/integration/test_proxy_engine.py` (A1 structure, operating line, limitations),
`test_proxy_multi_engine_lanes.py` (U3), `test_proxy_chain.py` (U4 wiring, fused == modules, snapshot,
governed replay, prototype flag), `test_proxy_determinism.py` (A6), `test_proxy_ident.py` (A2),
`tests/unit/test_proxy_config.py`, `test_proxy_archive2_guard.py` (A3), and the conformance gate.
The MF1 study and the A2 self-test: `analysis/proxy_quicklook/`.
