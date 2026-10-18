# Engine-health model: planted-fault detection

Source: **Generated engine trend (overlay v0.1)** — generated data, not validated physics or real engine data. Model `engine_health` 0.1.0 (Kalman level + trend, CUSUM, washes as known change points); tuning: nothing: settings fixed by hand before evaluation (engine_health.py).

Planted faults: 8; detected 8; detected before the true margin reached 0 °C: 8. Lead time (days from the alert becoming visible to the true limit crossing) min / median / max: [77.1, 156.9, 301.8]. Median delay after onset: 6.95 d. False alarms: 3 episodes in 9025 healthy flights = **0.033 per 100 flights**.

| Run | Fault | Mode | Onset | Detected (kind) | Delay d / EFH | True margin at alert °C | True limit | Lead d / EFH |
|---|---|---|---|---|---|---:|---|---|
| seed=1 | OVL-F1-TJ102 (IN20-TJ102) | gradual | 2026-04-20 15:00 | 2026-05-05 15:00 (step (CUSUM)) | 15.0 / 7.3 | 45.3 | 2026-07-31 20:00 | 87.1 / 47.1 |
| seed=1 | OVL-F2-TJ104 (IN20-TJ104) | step | 2026-05-12 08:30 | 2026-05-12 12:00 (step (CUSUM)) | 0.1 / 0.9 | 32.1 | 2027-03-10 08:30 | 301.8 / 78.7 |
| seed=2 | OVL-F1-TJ107 (IN20-TJ107) | gradual | 2026-04-06 08:30 | 2026-04-17 08:30 (step (CUSUM)) | 11.0 / 4.8 | 49.3 | not reached (18.0 °C left at 2026-08-10 08:30) | None / None |
| seed=2 | OVL-F2-TJ101 (IN20-TJ101) | step | 2026-05-11 15:00 | 2026-05-12 08:30 (step (CUSUM)) | 0.7 / 0.5 | 30.8 | not reached (3.6 °C left at 2028-01-04 20:00) | None / None |
| seed=3 | OVL-F1-TJ103 (IN20-TJ103) | gradual | 2026-04-06 15:00 | 2026-04-13 12:00 (step (CUSUM)) | 6.9 / 3.8 | 39.8 | 2026-06-29 15:00 | 77.1 / 42.1 |
| seed=3 | OVL-F2-TJ108 (IN20-000001) | step | 2026-05-11 08:30 | 2026-05-18 08:30 (step (CUSUM)) | 7.0 / 3.2 | 37.3 | 2026-12-23 20:00 | 219.4 / 80.3 |
| seed=4 | OVL-F1-TJ107 (IN20-000001) | gradual | 2026-04-06 08:30 | 2026-04-23 15:00 (step (CUSUM)) | 17.3 / 8.3 | 39.4 | 2026-08-21 08:30 | 119.7 / 41.3 |
| seed=4 | OVL-F2-TJ108 (IN20-TJ108) | step | 2026-05-12 12:00 | 2026-05-13 15:00 (step (CUSUM)) | 1.1 / 0.6 | 35.2 | 2026-11-23 20:00 | 194.1 / 88.1 |

| Run | Engines | Flights | Healthy flights | False-alarm episodes | per 100 flights | Tracking RMSE °C |
|---|---:|---:|---:|---:|---:|---:|
| seed=1 | 12 | 2744 | 2377 | 1 | 0.042 | 0.83 |
| seed=2 | 14 | 2457 | 2308 | 1 | 0.043 | 0.9 |
| seed=3 | 13 | 2950 | 2575 | 1 | 0.039 | 0.84 |
| seed=4 | 12 | 2145 | 1765 | 0 | 0.0 | 0.77 |
