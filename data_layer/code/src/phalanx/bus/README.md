# M15 Bus encoder and clock domains (W1.7)

**Purpose.** Put CIR samples on the recorded avionics buses of the **SYNTHETIC Phalanx ICD** the way an
asynchronous, multi-clock aircraft would: MIL-STD-1553B transactions under a bus-controller schedule,
ARINC-429 labels with SSM, and the FTI PCM minor frame. Architecture §6 M15, §8; AD-06, AD-11, AD-39.

## Interfaces

```python
from phalanx.bus.icd import BusIcd  # bus model of the dictionary (messages, labels, PCM frame)
from phalanx.bus.clocks import STREAMS, SortieIdentity, LruOscillator, lru_oscillator, acquisition_oscillators
from phalanx.bus.encoder import BusConfig, encode_bus, BusTraffic, check_cir_on_oscillator
from phalanx.bus.schedule import build_schedule, BcSchedule
from phalanx.bus.words import encode_item_words, arinc429_words

icd = BusIcd.from_dictionary(load_dictionary())
oscs = acquisition_oscillators(dictionary, epoch_ns)  # M13 clock domains (A-W1.6-21) as bus crystals
traffic = encode_bus(
    cir_batch, icd, BusConfig.from_params(), ident, rng, t0=..., t1=..., fti_fitted=False, oscillators=oscs
)
```

- **Batch interface** (W1_interfaces.md §4): M15 consumes a whole CIR batch of one sortie; it has no truth-loop
  ports, so there is no `ModuleBase`/`ports.py` (the port catalogue covers M02–M10 only).
- `BusTraffic.buses[i]` (`BusTransactions`): per transaction the poll instant, words on the wire (command,
  status, data), response time, timeout; **truth** (restricted): the buffer update read, the CIR row behind every
  item, the duplicate-poll flag.
- `STREAMS` (AD-37): `bus.osc_offset` (scenario, serial), `bus.osc_phase` (scenario, tail, sortie, sensor=LRU),
  `bus.rt_response` (scenario, serial). The caller registers them in the run's `StreamRegistry`.

## Mechanism

1. **One crystal per LRU unit** (`clocks.py`): frame ticks `floor(phi + n·1e9/(f(1+Δ)))`. Sub-rates (DFCC
   FCS40 inside its 80 Hz frame) are every k-th tick of the same crystal, never an independent clock. For the
   LRUs M13 acquires on, the crystal is M13's acquisition clock (`acquisition_oscillators`, A-W1.6-21), passed
   as `oscillators=` to `encode_bus` / `run_full_path`; other LRUs use keyed draws (Δ per unit serial, φ per
   sortie). W2.2 check: `check_cir_on_oscillator(t, osc, rate_hz=...)` per CIR stream
   (`tests/integration/test_bus_m13_clocks.py` runs real M13 output through the full path).
2. **Transmit buffers**: an RT LRU writes a message buffer at its update ticks `u`, with the latest samples
   acquired at or before `u` (`u − L_relay` for relayed items), `L_proc` later.
3. **BC schedule** (`schedule.py`): minor frame = one OAC tick (50 Hz); group g every `50/f_g` frames; sub-rates
   on the least-loaded phase; messages back to back with the recorded inter-message gap.
4. **Polls** read the latest completed write: duplicates and skips come only from this schedule mismatch (AD-06);
   no slip sentinels on digital words (§7).
5. **Words** (`words.py`): AS15532-style BNR/UBNR from the dictionary calibration, 32-bit MSW first, bitfields,
   enums, synthetic code words; validity words first; RT status word = ICD RT address + the CIR status flags.

## Assumptions (tagged; rows in `docs/assumptions.md`, W1.7)

A-W1.7-1 (crystal offsets/phases), -2 (processing latency 8 ms), -3 (relay latency 1 ms), -4 (BC schedule),
-5 (sub-rate slot 0), -7 (validity encoding, absent RT = timeout); the code-word layout is the dictionary's
`bit_code_format.word_layout` (`icd.CodeWordLayout`; A-W0.3-43, replacing A-W1.7-6 in the W2.2 migration). TRANSFER values from the
public KC-135 Ch10 sample: RT response 5.7–6.3 µs, inter-message gap 28 µs. Parameters: `configs/tejas/params/M15.yaml`.

## Validation criteria

| Criterion | Tests |
|---|---|
| A1 encode/decode within quantisation for every bus channel (296) | `tests/unit/test_bus_words.py` |
| A2 bus loading ≤ 50 %; every message at its rate | `tests/unit/test_bus_schedule.py` |
| A2 dup/skip fractions, skew, slip-window period 1/(f·ΔΔ) | `tests/statistical/test_bus_clock_stats.py` |
| Latency/age, relay, timeout, validity bit, busy RT, CRN timing | `tests/integration/test_bus_encoder.py` |
| Oscillators keyed, phase-locked sub-rates | `tests/unit/test_bus_clocks.py` |
| M13 instants on the M15 crystal; M13 output round trip | `tests/integration/test_bus_m13_clocks.py` |

## Known limitations

- No bus errors (message error, parity, word count) are generated yet; the decoder handles them if present.
- Only bus A is used (no A/B redundancy switching); WPN-MUX has no RTs in the dictionary, so no traffic.
- An LRU that has no CIR stream at all is modelled as not answering (timeout), which also covers "not simulated".
- Response time is constant per RT unit (no per-message jitter).
