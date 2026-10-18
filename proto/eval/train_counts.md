# Training-world event counts (before fitting)

Source: **Simulated fleet history** — 32 tail-worlds (4 seeds × 8 tails) × 730 days = 63.96 tail-years, built with the live fleet's builder (`TailRunner`, new session roots). Synthetic and not validated.

Totals: 1427 shop findings; **123 CONFIRMED** (62 linked and not hard-time, 15 not linkable), 27 BCM, 1277 RTOK, 102 not linkable to a tail. Linked fault-confirmed findings: 89. Fault-confirmed removals (CONFIRMED or BCM, not hard-time) used as hazard events: **80** (1.392 per tail-year; CONFIRMED alone 1.923 per tail-year). Preview v0.9 for comparison: 0 CONFIRMED in about 3.7 tail-years.

| Class | Spells | Hazard events | Exposure FH | CONFIRMED | of which hard-time | BCM | RTOK | Unlinked | Hazard |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| ADC | 133 | 0 | 7820.8 | 0 | 0 | 0 | 118 | 8 | INSUFFICIENT_EVIDENCE |
| AMAGB | 37 | 0 | 8618.2 | 4 | 4 | 0 | 0 | 0 | INSUFFICIENT_EVIDENCE |
| BCU | 269 | 0 | 8512.1 | 0 | 0 | 0 | 273 | 21 | INSUFFICIENT_EVIDENCE |
| BRAKE | 108 | 0 | 19627.0 | 39 | 31 | 0 | 0 | 8 | INSUFFICIENT_EVIDENCE |
| CHUTE | 278 | 0 | 11176.3 | 0 | 0 | 0 | 0 | 0 | INSUFFICIENT_EVIDENCE |
| DFCC | 94 | 0 | 8307.6 | 0 | 0 | 0 | 81 | 2 | INSUFFICIENT_EVIDENCE |
| ENG | 51 | 1 | 8520.2 | 14 | 11 | 1 | 6 | 4 | INSUFFICIENT_EVIDENCE |
| FADEC | 185 | 0 | 7289.7 | 0 | 0 | 0 | 178 | 15 | INSUFFICIENT_EVIDENCE |
| FQGS | 157 | 0 | 8797.1 | 0 | 0 | 0 | 134 | 11 | INSUFFICIENT_EVIDENCE |
| GEN | 33 | 1 | 8618.2 | 0 | 0 | 1 | 0 | 0 | INSUFFICIENT_EVIDENCE |
| HYDP | 306 | 77 | 14985.4 | 66 | 0 | 24 | 190 | 16 | FIT |
| INGPS | 32 | 0 | 8618.2 | 0 | 0 | 0 | 0 | 0 | INSUFFICIENT_EVIDENCE |
| JFS | 296 | 0 | 8815.0 | 0 | 0 | 0 | 283 | 15 | INSUFFICIENT_EVIDENCE |
| OBOGS | 46 | 0 | 8857.8 | 0 | 0 | 0 | 14 | 2 | INSUFFICIENT_EVIDENCE |
| RADAR | 31 | 1 | 7555.7 | 0 | 0 | 1 | 0 | 0 | INSUFFICIENT_EVIDENCE |
| TYRE | 3942 | 0 | 48669.6 | 0 | 0 | 0 | 0 | 0 | INSUFFICIENT_EVIDENCE |

Classes with fewer than 10 hazard events return INSUFFICIENT_EVIDENCE.
Per tail-world rates and the event keys are in `train_counts.json`.
