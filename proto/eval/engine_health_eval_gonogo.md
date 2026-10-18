# Engine-health model: planted-fault detection

Source: **Generated engine trend (overlay v0.1)** — generated data, not validated physics or real engine data. Model `engine_health` 0.1.0 (Kalman level + trend, CUSUM, washes as known change points); tuning: nothing: settings fixed by hand before evaluation (engine_health.py).

Planted faults: 2; detected 2; detected before the true margin reached 0 °C: 2. Lead time (days from the alert becoming visible to the true limit crossing) min / median / max: None. Median delay after onset: 4.5 d. False alarms: 0 episodes in 531 healthy flights = **0.0 per 100 flights**.

| Run | Fault | Mode | Onset | Detected (kind) | Delay d / EFH | True margin at alert °C | True limit | Lead d / EFH |
|---|---|---|---|---|---|---:|---|---|
| gonogo | OVL-F1-TJ106 (IN20-TJ106) | gradual | 2026-04-06 12:00 | 2026-04-14 08:30 (step (CUSUM)) | 7.9 / 5.7 | 43.3 | not reached (16.0 °C left at 2026-06-22 15:00) | None / None |
| gonogo | OVL-F2-TJ102 (IN20-TJ102) | step | 2026-05-12 08:30 | 2026-05-13 12:00 (step (CUSUM)) | 1.1 / 0.5 | 31.1 | not reached (21.6 °C left at 2026-06-22 08:30) | None / None |

| Run | Engines | Flights | Healthy flights | False-alarm episodes | per 100 flights | Tracking RMSE °C |
|---|---:|---:|---:|---:|---:|---:|
| gonogo | 9 | 598 | 531 | 0 | 0.0 | 0.86 |
