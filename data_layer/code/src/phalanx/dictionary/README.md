# M01: Parameter dictionary and provenance registry

**Architecture:** §6 M01, §8 (rate groups), §12 (contract), §15 (provenance), AD-14, AD-19, AD-24, AD-25, AD-35.
**Work package:** W0.3 (`docs/build_briefs/W0.3_dictionary.md`).

The dictionary is the single source of truth for every channel, scaling, rate, bus address, limit, code table and
evidence tag. TMATS, the **SYNTHETIC Phalanx ICD** and (through the W0.4 generator hook) the contract schemas are
generated from it. The bus map is synthetic everywhere: it is never the real Tejas ICD (RULES.md rule 6).

## Pipeline

```text
research_notes/.../parameter_inventory.csv   (189 rows x 33 fields, read-only evidence)
configs/tejas/dictionary/seed/overlay.yaml   (structured reading of each row; values verbatim or rule-cited)
configs/tejas/dictionary/tables/*.yaml       (LRUs, synthetic bus topology, rate groups, sinks, code tables, rules,
                                              constants)
        |  seeder.py  (redaction, lane/unit/component expansion, provenance, synthetic ICD allocation)
        v
configs/tejas/dictionary/sources/*.yaml      (one file per subsystem; generated_by: seeder)
        |  compiler.py + validate.py  (JSON-Schema + semantic validation; canonical JSON; blake2b-256)
        v
dictionary.<ver>.json                        (content + dict_hash; written by `build`, not committed)
        |  generators.py  (tmats, icd, param_table, assumptions, + hook)
        v
tmats.txt, tmats_setup_record.c10, icd.csv, icd.md, parameters.md, assumptions_w0.3.md
```

## Public API

```python
from phalanx.dictionary import load_dictionary

d = load_dictionary()  # compile the current tejas sources
d = load_dictionary("0.1.3")  # same, but require this version and the hash recorded in releases.yaml
d = load_dictionary(Path(".../dictionary.0.1.3.json"))  # read a compiled file (hash verified)
d = load_dictionary(Path("configs/proxy_dashlink/dictionary"))  # any platform dictionary directory

d.dict_version, d.dict_hash, d.platform, d.synthetic_label
d.param("ENG.N1")  # logical parameter: evidence {tag, source, classes, primary}, inventory row
d.channel("ENG.N1.V")  # physical channel (all fields below)
d.channels_for_param("ENG.N1")  # ENG.N1.A, ENG.N1.B (FADEC lanes), ENG.N1.V (validated output)
d.channels_for_measurand("ENG.N1")  # same set, keyed by measurand (the contract's param_id)
d.by_lru("FADEC")  # produced, digitised or transmitted by the LRU
d.by_rate_group("AV25", stage="bus")  # stage in {acquisition, producer, bus, record}
d.by_bus_address("AV-MUX-2", rt=5, sa=1)  # a 1553 message; word= narrows to one item
d.by_bus_address("RADALT-OAC", label=0o100)  # ARINC-429
d.by_bus_address("FTI-PCM", word=3)  # FTI PCM
d.acquisition_rate_hz("ENG.N1.A"), d.rate_hz("AV25")
d.units_map()  # {measurand_id: units} for the W0.4 fast path
d.param_set("channel_reference")  # core ParamSet (coherent SI, EvidenceTag, proxy) from the constants table
d.constants("channel_reference")  # the same set as written (value, units, evidence)
d.field_evidence("ENG.N1.V", "recorder_lsb")  # {ref, tag (EvidenceTag-parsable), source, proxy}
d.contract_location("ENG.N1.V")  # contract param_id/source_lru/lane/bus/rt_sa_word/label_sdi/units
d.code_table("ssm_bnr"), d.rule("R-LSB-BNR"), d.proxy_items()
d.eu_to_si("ENG.N1.V", pct)  # EU -> coherent SI on scalars/arrays (%N1 -> rad/s via channel_reference)
d.si_to_eu("AD.HP", metres)  # SI -> EU (m -> ft); exact inverse of eu_to_si up to float rounding
d.eu_conversion("AD.SAT")  # EUConversion(si_units='K', scale=1.0, offset=273.15, reference=None)
d.bit_codes(), d.bit_code("ENG-501")  # unified BIT/fault codes in index order; one row (+ group)
d.translate_bit_code("ENG-501", "M08")  # -> "ENG-502" (M08's earlier list, documented map)
d.code_word_eu("ENG.FAULT_CODES", "ECM-702")  # 1702 = k*1000 + NNN; d.code_word_code(cid, 1702)
d.code_word_bits(1702), d.code_word_value(0x06BE)  # EU <-> 16-bit word (k << 10 | NNN)
d.recorder_setup(), d.recording_events()  # R-1 events and time index (TMATS R-1\EV / R-1\IDX)
```

**EU <-> SI (for M13).** Each numeric channel converts with `si = eu * scale + offset`; the SI unit follows the
channel's quantity (`eu.SI_UNITS`: ft -> m, knot -> m/s, psi/bar/mbar -> Pa, degC/degF -> K, lb/hr -> kg/s,
deg -> rad, % -> fraction, ...). % of rated speed (ENG.N1, ENG.N2) converts through the `channel_reference`
constant that lists the parameter in `eu_reference_for` (13,270 / 16,810 rpm = 100 %). Discrete, enum and code
values are unchanged. Text and media channels raise `EUConversionError`. SPS.JFS.SPEED converts through
`channel_reference.jfs_rated_speed` (60,000 rpm, ASSUMPTION, equal to M09's `jfs.jfs_rated_speed`, tested).

**Codes (0.1.2).** `code_tables.bit_codes` is the one synthetic BIT/fault/exceedance table (AD-48 item 5): M14's
102 codes in M14's order (`index` = position) plus ENG-509/ENG-510, with groups, severity, PFL/MFL, mechanism,
source LRU, lane, CWS legend and voice channel, and monitor channel/limit id/sense/gate (`module_limits` names the
limit ids that are module parameters). `legacy.M08` maps M08's earlier list one-to-one. The code-word layout is
`bit_code_format.word_layout` (R-CODE-WORD). `fcs_law` 3 = GROUND; `flight_phase` 8-15 are synthetic fighter
phases (`synthetic_codes`); `mil1553_validity_bit` 1 = BUS_INVALID (AD-45).

**TMATS recorder setup (0.1.2).** `generate_tmats(content, recording=True, extra_events=())` emits `R-1\EV`
(the `buses.recorder` events, then any extra events) and `R-1\IDX` (time index) from the dictionary
(R-REC-SETUP); the published `tmats.txt` uses it. The default (`recording=False`, `E:F`) stays until M16
stops overlaying these lines (W2.1).

**Contract mapping (W0.4 `param.samples`).** `param_id` = `measurand_id`; `source_lru` = `acq_lru` (the LRU that
acquired or computed the value); `lane` = lane, or null for `""`; `bus` = 1553 bus / ARINC-429 link / FTI stream;
`rt_sa_word` = `RTnn/SAnn/Wnn` with a **0-based** data-word index (the dictionary and TMATS count data words from 1);
RT status words are `SA00/W00`, the mode-code-19 BIT word `SA31/W00`; `label_sdi` = `Looo/SDIn`. The fast path's
`FastPathConfig(dict_version, dict_hash, units)` takes `d.dict_version`, `d.dict_hash` and `d.units_map()`.

All returned objects are deeply read-only (`MappingProxyType`, tuples).

**Identity.** `param_id` = inventory row. `measurand_id` = `param_id[.unit][.component]` (one engineering unit per
measurand; this is what the contract record calls `param_id`). `lane` = `A`..`D` (DFCC/ADC lanes), `A`/`B` (FADEC
lanes, sensor cores), `V` (voted/validated output) or empty. `channel_id` = `measurand_id[.lane]`.

**Channel fields:** `quantity`, `units` (pint), `pressure_ref`, `signal`, `sensor_type`, `source_lru` (producer),
`acq_lru` (digitising LRU = clock domain), `range`, `native_step`, `converter_step` (FADEC lanes only),
`recorder_lsb`, `adc_bits`, `encoding`,
`transport` (1553 bus/RT/T-R/SA/word/words, ARINC-429 link/label/SDI, FTI stream/word, RS-422, internal, download,
maintenance record), `validity` (1553 validity-word bit, ARINC-429 SSM table, RT status), `rates` (acquisition, bus,
producer), `sinks` (sink, basis evidenced/assumed/derived, record group, consumer), `calibration` (counts->EU
polynomial and date), `limits`, `inputs` (lanes of a voted output), `proxy`, `prov` (provenance ref per field),
`inv_tokens`, `notes`.

## Provenance (100 %)

Every parameter carries the inventory's evidence tag (parsed into classes DIRECT / DIRECT-part / DIRECT-unnamed /
TRANSFER / MEASURED / ASSUMPTION), its source, and a `core_tag` that parses with the core kernel's `EvidenceTag`
(`phalanx.core.module`): the weakest class the inventory tag mentions, with the donor for TRANSFER. Rule, LRU, sink
and constant tags parse with `EvidenceTag` too; PROXY is a flag (`proxy: true` on P- rules), as in core `Param`. Every valued channel field, sink, record group and limit carries a
provenance ref:

- `inv`: the value is written in the inventory row. The compiler **verifies** numbers, units, sensor types, rate
  groups and sink flags against the embedded row text (`textcheck.py`); a value that is not there fails compilation.
- `R-...` / `P-...`: a rule in `tables/rules.yaml` with tag, source, sweep range, affected modules and an exposing
  test. Every ASSUMPTION/PROXY rule has an `assumption_id` and a row in `docs/assumptions.md` (W0.3 section), generated
  by `cli.py assumptions` and checked by the tests.

`stats.provenance_coverage_pct` in the compiled dictionary must be 100. Rule families justify only their own
fields (a `R-RANGE-*` rule cannot justify an LSB or a unit; `R-LSB-BNR` as a recorder LSB needs a BNR word).

**Constants** (`tables/constants.yaml`) need a tag that parses with `EvidenceTag` and a source; an ASSUMPTION or
proxy constant also needs a `sweep` [lo, hi] that brackets its value and a `prov` rule with an `assumption_id`
(its docs/assumptions.md row lists the constant). The compiler rejects anything less.

## Restricted-manual values (report Appendix A1)

A few inventory rows note a value whose only source is a restricted or limited-distribution manual. The seeder
redacts these **before** reading any value (`redact.py`, step 0): a `;`-separated fragment that carries a
restricted-manual marker is replaced whole by `[redacted: restricted-manual value omitted; see report Appendix
A1]`, and `inventory.redacted` lists the affected fields. Nothing in a source file, the compiled dictionary or a
generated artefact carries the value, and no field can cite it (the provenance checks see the redacted text).
In 0.1.1 three notes fields are redacted (ENG.T5, ENG.OIL_P, ENG.FUEL_INLET_T).
`tests/unit/test_dictionary_restricted_guard.py` scans `configs/`, `src/`, `docs/contract/` and a fresh build for
the markers and for the redacted values in context (read from the inventory at test time, never written in the
test), with negative controls.

## Determinism and versioning

- Strict YAML (duplicate keys are errors; non-string keys are errors).
- Canonical JSON = the core kernel's `canonical_json` (sorted keys, compact, ASCII, finite floats) after a JSON
  data-model check that maps -0.0 to 0.0; hash = core `digest` (blake2b-256, person `phx.dict.v1`) of the canonical
  content bytes. No wall clock, environment, file path or builtin `hash()` enters the output.
- `dict_version` (semver) lives in `dictionary.yaml`; `releases.yaml` records version -> hash. Any content change
  without a version bump fails the test suite (`python -I src/phalanx/dictionary/cli.py release --config ... --write`
  records a new release).

## Commands (run from the checkout; paths are arguments)

```bash
PY=/Users/abishaikc/Phalanx/.venv-build/bin/python
$PY -I src/phalanx/dictionary/cli.py seed --inventory "research_notes/Virtual fighter telemetry layer research/parameter_inventory.csv" --config configs/tejas/dictionary [--check]
$PY -I src/phalanx/dictionary/cli.py compile --config configs/tejas/dictionary
$PY -I src/phalanx/dictionary/cli.py build --config configs/tejas/dictionary --out <dir>
$PY -I src/phalanx/dictionary/cli.py assumptions --config configs/tejas/dictionary
$PY -I src/phalanx/dictionary/cli.py release --config configs/tejas/dictionary --write
```

## Generator hook (for the W0.4 contract generator)

A generator is `fn(dictionary: Dictionary, out_dir: Path) -> list[Path]`. Add it either to the manifest list
(`generators: [..., "phalanx.dictionary.contract.<module>:<function>"]`, resolved with importlib, `phalanx.*` only),
or call `register_generator(name, fn)` / `build(config, out, extra_generators={...})`. Generators never change the
dictionary or its hash. A ready adapter, `phalanx.dictionary.generators:contract_v0_generator`, writes the W0.4
contract v0 artefacts plus `dictionary_binding.json` (dict_version, dict_hash, units map); it is not enabled in the
Tejas manifest until the coordinator wires it (W0.X).

## Migration notes for dictionary 0.1.3 (W2.2 phase B)

- **FADEC lanes:** the 12 FADEC lane channels' `native_step` is now the FADEC converter step (span / 2^14,
  rule R-FADEC-ADC); the separate `converter_step` field is gone from the Tejas dictionary (it stays in the
  schema for other platforms, e.g. the DASHlink proxy). M13 already quantised the lanes there with its lane noise
  in EU (W2.2), so no quantiser, noise or ceiling moves (tested against a 0.1.2 view).
- **NAV.RADALT:** `signal` is `computed` (rule R-AD51-COMPUTED, A-W0.3-46): the radar altimeter's height word is
  the LRU tracker output supplied by the M12 avionics extension as a RECORDED value (AD-51); `adc_bits` is null.
  Range, LSB, ARINC-429 label and sinks are unchanged, so the bus map and the setup record do not change (only the
  release line of the setup record).
- **ENG.T1:** the span stays -54..149 degC, the F404 T1 RTD range (-65..300 degF, FOCSI), and a note documents
  the saturation: a colder compressor-inlet total temperature (the ISA stratosphere's -56.5 degC static only below
  about M0.24, or a cold-soaked ground) reads at the span floor; the FADEC holds T1 there or substitutes air-data
  T1 (W2.1b entry gate 3).
- **AD.DPA / AD.DPB:** range evidence checked, no change: 35-1,500 mbar is the Kala (2015) range of the ADC's
  flow-angle port transducers (DIRECT); a range starting at 35 mbar is absolute, so the channels stay absolute
  port pressures (R-AD-PORT-PRESSURE, 0.1.2).
- **ENG.AB_LIT:** the discrete UV flame detector gets its 0/1 range as the inventory row writes it (prov `inv`;
  the seeder now accepts a range on a bitfield discrete, inside what its fields can carry). It stays a word (no
  native step): M13 acquires it through the W2.2 word path, held and unquantised, and the M12 detector class
  produces it (PROXY A-W2.2-15). The setup record gains its C-group range lines (MOT1 1.0, MOT2 0.0).
- **Code table `ins_mode`:** code 0 is the string `OFF`; until 0.1.3 the unquoted YAML `OFF` was read as the
  boolean false (YAML 1.1). No wire value changes.

## Migration notes for dictionary 0.1.2 (W2.1)

- **M14:** read `d.bit_codes()` / `d.bit_code(c)` instead of the identity fields of `params/M14/codes.yaml`
  (index, desc, sev, list, mech, lru, lane, src, legend, voice, monitor channel/limit/sense/gate, groups); keep
  only behaviour fields there (tech, suspects, regime, sympathetic, displayed, persist_s, clear_s, cnd_by_tech).
  Replace `fadec_codes` with `d.translate_bit_code(code, "M08")` (differences: M08 ENG-506/507 now map to the
  new ENG-509/510, CAUTION/PFL/CWS-L06 like ENG-503; M08's ENG-701..703 map to ENG-701..703, which M14 may
  still choose not to re-record). Add behaviour rows for ENG-509/510.
- **M08:** emit the unified codes (`translate_bit_code`, or adopt the map in `codes.py`); the code-word value
  convention (k*1000 + NNN, prefixes ENG/ECM) is unchanged, now defined by `bit_code_format.word_layout`.
- **M16:** call `generate_tmats(content, recording=True, extra_events=...)` and drop `compose_setup_record`'s
  EV/IDX substitution, the `RECORDER_EVENTS` constants (use `d.recording_events()`) and the `index_interval`
  parameter (use `d.recorder_setup()["index"]["interval_s"]`; A-W1.7-12 becomes A-W0.3-44). Output is
  byte-identical (tested). Then the generator default flips to `recording=True`.
- **M15/M17:** read the code-word layout from `bit_code_format.word_layout` (A-W1.7-6 becomes A-W0.3-43); the
  decoder already maps the 1553 validity bit through `mil1553_validity_bit` (now BUS_INVALID).
- **M02/M13/M03:** flight_phase 8-15 are now released, so M02's name map emits MISSION/DESCENT/PATTERN/
  TOUCH_AND_GO/... instead of CRUISE/APPROACH fallbacks; M13's `AIRBORNE_PHASES` (3-6) and M03's Category C set
  (TAKEOFF/APPROACH/ROLLOUT) should be reviewed for the new codes.
- **M13 (FADEC lanes):** the 12 FADEC lane channels carry `converter_step` (span / 2^14, R-FADEC-ADC), finer than
  the word step. To use it, quantise FADEC lanes at `converter_step` and express their noise in EU (today
  sigma = sigma_steps x native_step, measured on the DASHlink 1/32 % lattice); then the dictionary moves the
  converter step into `native_step` (0.1.3). Also: SPS.JFS.SPEED now has an SI conversion, so it becomes an M13
  stream (249 -> 250).

## Generated artefacts

`src/phalanx/dictionary/generated/` holds the regenerated TMATS stub, SYNTHETIC ICD (CSV, Markdown), parameter table
and assumption rows, committed for review (a test checks they equal a fresh build). The compiled JSON and the Ch10
setup-record file are build outputs here. The published set, including `dictionary.<ver>.json` and the contract
docs, is `docs/contract/` (`make contract-docs`, W0.X; a test checks it matches a fresh build).

## Assumptions (tagged; full list in `docs/assumptions.md`, W0.3 section)

- The bus map, RT addresses, subaddresses, word layout, ARINC-429 labels and FTI PCM frame are a **synthetic ICD**
  [ASSUMPTION; R-ICD-*], following public conventions (MIL-STD-1553B, SAE AS15532 style, ARINC 429, IRIG 106).
- Recorder LSBs are DASHlink lattices, -400 MSDC resolutions or the inventory's recommendations [ASSUMPTION;
  R-LSB-*]; native steps equal the recorder LSB unless the inventory states a resolution [ASSUMPTION; R-NATIVE-EQ-LSB].
  DASHlink native steps (proxy-mode values) are **not** used in the Tejas dictionary.
- Rates inside evidenced bands are nominal choices (FADEC 60 Hz, INS 100 Hz, HUMS 1 Hz, FTI 64 Hz, CDR 16/8/4/1 Hz)
  [ASSUMPTION; R-RATE-*].
- Full-scale ranges where the inventory gives only an operating band or nothing [ASSUMPTION; R-RANGE-*].
- FTI.ALL and DVR.VIDEO are placeholder channels [PROXY; P-FTI-ALL, P-DVR].

## Validation criteria (tests `tests/*/test_dictionary_*.py`)

A1 provenance 100 % (negative: a missing tag/source/prov fails); A2 hash stable in-process and in a fresh process,
any edit changes it; A3 no orphans, no bus-address collisions (negatives); A4 units parse and match the quantity,
ranges fit ADC bits and words (negatives); A5 TMATS parses with pyChapter10 and round-trips the channel list and
locations; A6 all 189 rows seeded, channel count tested; A7 every ASSUMPTION/PROXY rule is in `docs/assumptions.md`
with the PROXY flag consistent; A8 `make check`. E0 (0.1.1): restricted-value guard and redaction carry test;
constants provenance; rule-family field checks; EU <-> SI on every unit class.

## Known limitations

- TMATS: attribute names and codes follow RCC 106-07 Ch9; conformance against an independent Ch10 parser and the
  public sample files is M16's acceptance (W1.7). Status-word measurands use the transmit-status-word mode code
  (MC 2) with word number 0.
- Model parameters (engine maps, gains) live in the W1.0 registry (`configs/<platform>/params/`, `params.py`);
  the `constants` table holds only the channel reference values.
- SPS.JFS.SPEED (% of rated speed) has no SI conversion until a JFS rated speed is set (see EU <-> SI).
- Only the Tejas platform is seeded; proxy-mode (DASHlink) dictionaries are W2.4 and reuse the same schema.
- Re-seeding re-allocates bus addresses deterministically; any ICD change needs a version bump.
