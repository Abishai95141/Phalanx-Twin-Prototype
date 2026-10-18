# `phalanx.environment`: M03 environment and process disturbances (W1.1)

All exogenous stochastic inputs of the truth loop (architecture §6 M03, AD-32, §8): the atmosphere at the
aircraft, mean wind and shear, continuous turbulence and discrete gusts, and the **per-unit process
disturbances** that make engines and spools correlated without moving in lockstep
(`docs/behavioural_targets.md`; round-2 REPORT §3.1, §8 H-a).

## Files

| File | Contents |
|---|---|
| `atmosphere.py` | USSA-1976 profile, anchored ISA-offset profile, design-day (MIL-HDBK-310 style) profile, moist-air state (`@njit`) |
| `climatology.py` | IMD 1991-2020 station climatology (5 Tejas-relevant bases), day-weather draws, ambient sampler, `Ambient` payload |
| `turbulence.py` | MIL-F-8785C scales, von Kármán / Dryden forming filters (time-varying Tustin, DF2T), 1-cosine gust, log shear, analytic spectra |
| `disturbances.py` | AD-32 latent-factor bank: OU / OU2 / resonant shaping filters, exact (Van Loan) discretisation, analytic PSD / cross-PSD / coherence |
| `era5.py` | ERA5 replay interface (`Era5Column`), adapter to a profile, METAR surface override |
| `kernel.py` | the `@njit` environment kernel (one pass per block of 240 Hz ticks) |
| `module.py` | `EnvironmentModule` (truth loop), `EnvironmentReplay` (proxy mode), `Gust`, `standard_ambient` |
| `config.py` | `load_env_config()` -> `EnvConfig` from `configs/tejas/params/M03.yaml` |
| `ports.py` | `PREFIX = "env"`, `ports(n_engines=1, n_hyd=2)` |

## Interfaces

**Ports** (W1_interfaces §2 M03; `configs/interfaces/w1_ports.yaml`):

| In | Bound to | Note |
|---|---|---|
| `alt` (m) | `af.alt` | read as **geometric altitude above MSL** (one-frame delayed back-edge) |
| `hag` (m) | `af.hag` | height above the local ground: shear and low-altitude turbulence (terrain is M06's) |
| `tas` (m/s) | `af.tas` | forming-filter airspeed (floored at `v_min`) |
| `phase` (int) | `scenario.phase` | Category C phases (dictionary TAKEOFF, APPROACH, ROLLOUT) select z0 = 0.15 ft |

Outputs: `t_s` K, `p_s` Pa, `rho` kg/m^3, `a_sound` m/s, `q_spec` kg/kg, `wind_ned` (3,) m/s,
`turb_vel_body` (3,) m/s, `turb_rate_body` (3,) rad/s, `w_engine` (e, 5) =
`[fuel_metering, combustor_eff, inlet_recovery, shaft_load, fan_face]` fractional (AD-46: `fan_face` is the
fan-face distortion on fan flow capacity and efficiency, the LP-spool-specific path), `w_bleed_pto` (e,) fractional,
`w_hyd` (h,) m^3/s.

**Events:** `scenario.sortie_plan` (payload `ambient`: `Ambient.vector()`; optional `duration_s` for
stochastic gusts) re-anchors the atmosphere and sets the turbulence class; tick count, filter states and
disturbance states continue (the exogenous future is not perturbed).

**Streams** (AD-37): `env_turb.gust` (scenario, tail, sortie; 4 normals per tick); `env_turb.gust_events`
(GENERATOR); `env_dist.f<id>` per factor: aircraft scope (scenario, tail, sortie), unit scope
(scenario, tail, serial, sortie) with the engine or hydraulic serial. Draw index = absolute tick in state.

**Python API:**
```python
load_env_config(platform="tejas") -> EnvConfig            # .with_turbulence(...), .with_factors(...)
EnvironmentModule(id, cfg, *, n_engines=1, engine_serials=None, hyd_units=("HYD1","HYD2"),
                  ambient: Ambient | None = None, profile=None, profile_wind=False, gusts=(),
                  cat_c_codes=None, compiled=True, identity=None)
EnvironmentReplay(id, cfg, *, pressure_alt_m, mach, tat_k, rate_hz, t0_ns=0, n_engines=1, ...)
Climatology / StationClimatology / SamplerParams; draw_day(station, month, gen, sp) -> DayWeather;
ambient_at(station, day, hour_utc, t_utc_s, sp, *, field_elev_m, magnus) -> Ambient
DisturbanceBank(factors, n_engines, n_hyd, dt): .cross_psd(j, k, f), .coherence(j, k, f), .out_index(...)
era5.profile_at(col, t_utc_s, consts, magnus, *, metar=None) -> (profile, n)
```

## Method and evidence (tags in `configs/tejas/params/M03.yaml`)

- **Atmosphere** [TRANSFER: USSA-76, a standard; E1-HY]: piecewise-linear T over geopotential altitude,
  hydrostatic pressure, dry USSA exactly when no vapour; moist density and speed of sound through the virtual temperature
  [ASSUMPTION A-W1.1-4]. Climatology atmospheres anchor at the IMD station pressure with an ISA temperature
  offset [A-W1.1-3]; design days read the table altitude as pressure altitude (JSSG-2007A Fig. 5 note 4).
- **Climatology** [DIRECT: IMD 1991-2020]: monthly 0300/1200 UTC pressure, dry bulb, vapour pressure, wind
  direction, mean wind, daily max/min and monthly extremes, phenomenon days for Coimbatore (Sulur), Naliya,
  Bikaner (Nal), Jaisalmer, Jodhpur. Day-level variability and the diurnal shape are [ASSUMPTION
  A-W1.1-5..8].
- **Turbulence** [TRANSFER: MIL-F-8785C/MIL-HDBK-1797 via MathWorks]: von Kármán (production) or Dryden
  (tests); intensities by class [A-W1.1-10]; body axes [A-W1.1-13]; 1-cosine gusts [A-W1.1-12].
- **AD-32 disturbances**: latent-factor bank (aircraft-common, unit-level, unit-and-channel factors) with
  configurable PSD forms and loadings, hence configurable cross-unit and within-unit cross-channel coherence.
  Values are placeholders [A-W1.1-1], identified in W2.4.

## Validation criteria (W1.1 acceptance → tests)

| ID | Test |
|---|---|
| A1 | `tests/unit/test_environment_atmosphere.py` (USSA P_b to 1e-6, sea level and layer temperatures at print precision, anchor/hydrostatics, design-day convention); `tests/golden/test_environment_mil310.py` (**xfail strict: MIL-HDBK-310 tables not in the evidence base**) |
| A2 | `tests/statistical/test_environment_turbulence_psd.py` (n = 2^20 ticks per model; band PSD vs filter, variance vs sigma^2, negative control); `tests/unit/test_environment_turbulence.py` (rational vK within 5 % of analytic for L w / V in [0.01, 10]) |
| A3 | `tests/statistical/test_environment_disturbances_psd.py` (common-only, unit-only, mixed, within-engine cross-channel, fan_face common + engine-specific (AD-46),
n_engines 1, 2 and 4 (AD-43 proxy), hydraulics, shipped placeholders; negative control); `tests/unit/test_environment_era5_replay.py` (4-engine proxy replay smoke) |
| A4 | `tests/fork/test_environment_crn.py` (identity reproducibility, re-fitted engine stream isolation, CRN audit with a divergent plan order, negative control) |
| A7 | `tests/integration/test_environment_module.py` (compiled == reference bitwise; whole tree under `NUMBA_DISABLE_JIT=1` in a subprocess; step == block for 1/7/1024; snapshot mid-run; validation mode) |

## Known limitations

- MIL-HDBK-310 tables absent (data request); only the mechanism is tested.
- Full USSA-1976 Table I is not in the evidence base; the golden check uses the 7-figure layer table.
- The rational von Kármán forms roll off as w^-2 instead of w^-5/3 above L w / V ~ 10.
- Turbulence intensity tables, Indian turbulence climatology and gust statistics are assumptions.
- `af.alt` is catalogued as a "pressure-altitude reference"; M03 needs the geometric altitude (a pressure
  altitude would make the atmosphere a function of itself). Reported as an interface clarification.
- Conditions are frozen per sortie (no diurnal drift during a sortie).
