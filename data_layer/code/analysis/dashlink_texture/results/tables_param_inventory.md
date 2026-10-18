| Param | Description | Units | Hz | Type | Typical range (p1 flight-min .. p99 flight-max) | LSB | Grid reg. | LSB x 4096 | Binary-scaled LSB | Repeats % | Isolated sentinel dropouts | Stuck runs (sibling rule) | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BLAC | BODY LONGITUDINAL ACCELERATION | G | 16 | cont | -0.3781 .. 0.3463 | 0.000977 | 1 | 4.002 | no | 49.8 |  |  |  |
| CTAC | CROSS TRACK ACCELERATION | G | 16 | cont | -0.7327 .. 0.7157 | 0.000977 | 1 | 4.002 | no | 33.9 |  |  |  |
| FPAC | FLIGHT PATH ACCELERATION | G | 16 | cont | -0.3713 .. 0.3483 | 0.000977 | 1 | 4.002 | no | 60.1 |  |  | held 0 on ground |
| IVV | INERTIAL VERTICAL SPEED LSP | FT/MIN | 16 | int-cont | -4922 .. 5004 | 1 | 1 | 4096 | yes | 38.9 |  |  |  |
| PTCH | PITCH ANGLE LSP | DEG | 8 | cont | -11.57 .. 19.59 | 0.01099 | 1 | 45 | yes | 56.9 |  |  |  |
| RALT | RADIO ALTITUDE LSP | FEET | 8 | cont | -4.438 .. 5500 | 0.125 | 1 | 512 | yes | 81.3 |  |  | clamped ~5500 ft above range |
| ROLL | ROLL ANGLE LSP | DEG | 8 | cont | -36.66 .. 36.88 | 0.01099 | 1 | 45 | yes | 33.5 |  |  |  |
| VRTG | VERTICAL ACCELERATION | G | 8 | cont | -3.375 .. 1.677 | 0.002289 | 0.99 | 9.375 | no | 27.3 | 792/h @-3.375 |  | -3.375 g sentinel, periodic bursts |
| ALT | PRESSURE ALTITUDE LSP | FEET | 4 | int-cont | -289.5 .. 3.501e+04 | 1 | 1 | 4096 | yes | 27.5 |  |  |  |
| ALTR | ALTITUDE RATE | FT/MIN | 4 | int-cont | -5664 .. 5800 | 16 | 1 | 6.554e+04 | yes | 11.9 |  |  |  |
| AOA1 | ANGLE OF ATTACK 1 | DEG | 4 | cont | -16.48 .. 29.9 | 0.04394 | 1 | 180 | yes | 47.4 |  |  |  |
| AOA2 | ANGLE OF ATTACK 2 | DEG | 4 | cont | -15.42 .. 45 | 0.04394 | 1 | 180 | yes | 29.8 |  |  |  |
| AOAC | CORRECTED ANGLE OF ATTACK | DEG | 4 | cont | -15.49 .. 11.4 | 0.04394 | 1 | 180 | yes | 49.7 |  |  | constant within every 120-s ground-idle window |
| AOAI | INDICATED ANGLE OF ATTACK | DEG | 4 | cont | -15.64 .. 29.97 | 0.04394 | 1 | 180 | yes | 41.1 |  |  |  |
| BAL1 | BARO CORRECT ALTITUDE LSP | FEET | 4 | int-cont | -21 .. 3.502e+04 | 1 | 1 | 4096 | yes | 22.6 |  |  |  |
| BAL2 | BARO CORRECT ALTITUDE LSP | FEET | 4 | int-cont | -17 .. 3.502e+04 | 1 | 1 | 4096 | yes | 22.4 |  |  |  |
| CAS | COMPUTED AIRSPEED LSP | KNOTS | 4 | cont | 0 .. 303.1 | 0.0625 | 1 | 256 | yes | 43.7 | 1.44/h @0 |  | validity-gated: reads 0 below 30 kt |
| CASM | MAX ALLOWABLE AIRSPEED | KNOTS | 4 | cont | 0 .. 300 | 0.25 | 1 | 1024 | yes | 100 | 0.0709/h @0 |  | held (max airspeed schedule) |
| DA | DRIFT ANGLE | DEG | 4 | cont | -90 .. 89.96 | 0.04394 | 1 | 180 | yes | 63 | 0.51/h @-89.999 |  |  |
| EGT_1 | EXHAUST GAS TEMPERATURE 1 | DEG | 4 | cont | 0 .. 627 | 0.5 | 1 | 2048 | yes | 81.4 |  | 72 |  |
| EGT_2 | EXHAUST GAS TEMPERATURE 2 | DEG | 4 | cont | 0 .. 621.2 | 0.5 | 1 | 2048 | yes | 81.4 |  | 31 |  |
| EGT_3 | EXHAUST GAS TEMPERATURE 3 | DEG | 4 | cont | 0 .. 614.5 | 0.5 | 1 | 2048 | yes | 80.7 |  | 9 |  |
| EGT_4 | EXHAUST GAS TEMPERATURE 4 | DEG | 4 | cont | 0 .. 615.5 | 0.5 | 1 | 2048 | yes | 81.1 |  | 34 |  |
| FF_1 | FUEL FLOW 1 | LBS/HR | 4 | int-cont | 0 .. 3040 | 8 | 1 | 3.277e+04 | yes | 86.4 |  | 98 |  |
| FF_2 | FUEL FLOW 2 | LBS/HR | 4 | int-cont | 0 .. 2976 | 8 | 1 | 3.277e+04 | yes | 84.9 |  |  |  |
| FF_3 | FUEL FLOW 3 | LBS/HR | 4 | int-cont | 0 .. 2928 | 8 | 1 | 3.277e+04 | yes | 84.6 |  |  |  |
| FF_4 | FUEL FLOW 4 | LBS/HR | 4 | int-cont | 0 .. 3068 | 8 | 1 | 3.277e+04 | yes | 86.6 |  |  |  |
| GS | GROUND SPEED LSP | KNOTS | 4 | cont | 0 .. 512.5 | 0.125 | 1 | 512 | yes | 78.6 |  |  | validity-gated: reads 0 below 50 kt |
| LATG | LATERAL ACCELERATION | G | 4 | cont | -1.083 .. 0.224 | 0.0005079 | 1 | 2.081 | no | 10.5 | 152/h @-1.0833 |  | -1.083 g sentinel, periodic bursts |
| LONG | LONGITUDINAL ACCELERATION | G | 4 | cont | -1.083 .. 0.3317 | 0.0005079 | 1 | 2.081 | no | 19.5 | 160/h @-1.0833 |  | -1.083 g sentinel, periodic bursts |
| MACH | MACH LSP | MACH | 4 | cont | 0 .. 0.7441 | 6.3e-05 | 1 | 0.2581 | no | 35.1 | 0.286/h @0 |  | reads 0 below ~0.10 |
| MH | MAGNETIC HEADING LSP | DEG | 4 | cont | -180 .. 180 | 0.005493 | 1 | 22.5 | yes | 26.3 | 0.0721/h @-179.99; 0.0613/h @179.99 |  | wrap dither |
| N1C | N1 COMMAND LSP | %RPM | 4 | cont | 0 .. 97 | 0.01562 | 1 | 64 | yes | 64.7 |  |  | 127.97 all-ones glitch (2) |
| N1T | N1 TARGET LSP | %RPM | 4 | cont | 0 .. 97 | 0.01562 | 1 | 64 | yes | 56.9 |  |  |  |
| N1_1 | FAN SPEED 1 LSP | %RPM | 4 | cont | 0 .. 97.16 | 0.03125 | 1 | 128 | yes | 58.4 |  | 5 |  |
| N1_2 | FAN SPEED 2 LSP | %RPM | 4 | cont | 0 .. 101.2 | 0.03125 | 1 | 128 | yes | 57.3 |  |  |  |
| N1_3 | FAN SPEED 3 LSP | %RPM | 4 | cont | 0 .. 97.09 | 0.03125 | 1 | 128 | yes | 52.9 |  |  |  |
| N1_4 | FAN SPEED 4 LSP | %RPM | 4 | cont | 0 .. 97.23 | 0.03125 | 1 | 128 | yes | 57.2 |  |  |  |
| N2_1 | CORE SPEED 1 LSP | %RPM | 4 | cont | 0 .. 95.52 | 0.03125 | 1 | 128 | yes | 65 |  | 1 |  |
| N2_2 | CORE SPEED 2 LSP | %RPM | 4 | cont | 0 .. 95.92 | 0.03125 | 1 | 128 | yes | 63.5 |  |  |  |
| N2_3 | CORE SPEED 3 LSP | %RPM | 4 | cont | 0 .. 95.94 | 0.03125 | 1 | 128 | yes | 55.9 |  |  |  |
| N2_4 | CORE SPEED 4 LSP | %RPM | 4 | cont | 0 .. 96.02 | 0.03125 | 1 | 128 | yes | 65.6 |  |  |  |
| NSQT | SQUAT SWITCH NOSE MAIN GEAR |  | 4 | discrete | {0,1} |  | 1 |  |  | 98.5 |  |  | 1 = nose strut extended (airborne); leads WOW by ~6.5 s at lift-off |
| PLA_1 | POWER LEVER ANGLE 1 | DEG | 4 | cont | -1.055 .. 88.9 | 0.08789 | 1 | 360 | yes | 87.1 |  | 958 |  |
| PLA_2 | POWER LEVER ANGLE 2 | DEG | 4 | cont | -0.1758 .. 89.12 | 0.08789 | 1 | 360 | yes | 84.9 |  | 8 |  |
| PLA_3 | POWER LEVER ANGLE 3 | DEG | 4 | cont | 0 .. 89.12 | 0.08789 | 1 | 360 | yes | 84.2 |  | 8 |  |
| PLA_4 | POWER LEVER ANGLE 4 | DEG | 4 | cont | -1.934 .. 89.03 | 0.08789 | 1 | 360 | yes | 85.5 |  | 30 |  |
| TAS | TRUE AIRSPEED LSP | KNOTS | 4 | cont | 0 .. 446.6 | 0.0625 | 1 | 256 | yes | 40.9 | 0.28/h @0 |  | validity-gated: reads 0 below 100 kt |
| TH | TRUE HEADING LSP | DEG | 4 | cont | -180 .. 180 | 0.005493 | 1 | 22.5 | yes | 26.3 | 0.113/h @179.99; 0.107/h @-179.99 |  | +-179.99 flags are heading-wrap dither, not dropouts |
| TRK | TRACK ANGLE TRUE LSP | DEG | 4 | cont | -180 .. 180 | 0.005493 | 1 | 22.5 | yes | 28.7 | 0.131/h @179.99; 0.121/h @-179.99 |  | wrap dither |
| TRKM | TRACK ANGLE MAG LSP | DEG | 4 | cont | -180 .. 180 | 0.005493 | 1 | 22.5 | yes | 28.7 | 0.0613/h @-179.99; 0.0565/h @179.99 |  | wrap dither |
| VIB_1 | ENGINE VIBRATION 1 | IN/SEC | 4 | cont | 0 .. 0.3438 | 0.03125 | 1 | 128 | yes | 98.1 |  | 2 | only 0-0.53 in/s; 98-99 % repeats |
| VIB_2 | ENGINE VIBRATION 2 | IN/SEC | 4 | cont | 0 .. 0.3438 | 0.03125 | 1 | 128 | yes | 99 |  | 1 |  |
| VIB_3 | ENGINE VIBRATION 3 | IN/SEC | 4 | cont | 0 .. 0.4219 | 0.03125 | 1 | 128 | yes | 98.7 |  |  |  |
| VIB_4 | ENGINE VIBRATION 4 | IN/SEC | 4 | cont | 0 .. 0.2812 | 0.03125 | 1 | 128 | yes | 99.2 |  |  |  |
| WD | WIND DIRECTION TRUE | DEG | 4 | cont | -180 .. 179.3 | 0.7031 | 1 | 2880 | yes | 78.1 | 0.634/h @179.3; 0.63/h @-180 |  | wrap dither |
| WS | WIND SPEED | KNOTS | 4 | cont | 0 .. 143.4 | 0.9961 | 1 | 4080 | no | 91.2 |  |  |  |
| APUF | APU FIRE WARNING |  | 2 | discrete | {0} |  |  |  |  | 100 |  |  |  |
| CCPC | CONTROL COLUMN POSITION CAPT | COUNTS | 2 | int-cont | 0 .. 3322 | 1 | 1 | 4096 | yes | 45.8 | 39.6/h @0 |  |  |
| CCPF | CONTROL COLUMN POSITION F/O | COUNTS | 2 | int-cont | 0 .. 3069 | 1 | 1 | 4096 | yes | 51.2 | 32.5/h @0 |  |  |
| CWPC | CONTROL WHEEL POSITION CAPT | COUNTS | 2 | int-cont | 0 .. 3426 | 1 | 1 | 4096 | yes | 64.2 | 9.77/h @0 |  |  |
| CWPF | CONTROL WHEEL POSITION F/O | COUNTS | 2 | int-cont | 0 .. 3345 | 1 | 1 | 4096 | yes | 35.6 | 33.2/h @0 |  |  |
| GMT_HOUR | GREENWICH MEAN TIME (HOUR) | Hour | 2 | int-cont | 0 .. 45 | 1 | 1 | 4096 | yes | 100 |  |  |  |
| GMT_MINUTE | GREENWICH MEAN TIME (MINUTE) | Minute | 2 | int-cont | 0 .. 165 | 1 | 1 | 4096 | yes | 99.2 |  |  |  |
| GMT_SEC | GREENWICH MEAN TIME (SECOND) | Second | 2 | discrete | {0,6,12,18,24,30,36,42,48,54,90} | 6 | 1 | 2.458e+04 |  | 91.7 |  |  | 6-s granularity; constant in 57 records |
| MSQT_1 | SQUAT SWITCH LEFT MAIN GEAR |  | 2 | discrete | {0,1} |  | 1 |  |  | 100 |  |  | 1 only while airborne with gear extended (brief at lift-off, final approach) |
| MSQT_2 | SQUAT SWITCH RIGHT MAIN GEAR |  | 2 | discrete | {0,1} |  | 1 |  |  | 100 |  |  | as MSQT_1 |
| PI | IMPACT PRESSURE LSP | MB | 2 | cont | 0 .. 156.8 | 0.03125 | 1 | 128 | yes | 26.1 | 0.243/h @0 |  |  |
| PS | STATIC PRESSURE LSP | IN | 2 | cont | 3.515 .. 30.25 | 0.0009766 | 1 | 4 | yes | 31.4 |  |  |  |
| PSA | AVARAGE STATIC PRESSURE LSP | MB | 2 | cont | 119 .. 1024 | 0.03125 | 1 | 128 | yes | 30.1 |  |  |  |
| PT | TOTAL PRESSURE LSP | MB | 2 | cont | 150.5 .. 1059 | 0.03125 | 1 | 128 | yes | 13.2 |  |  |  |
| RUDD | RUDDER POSITION | DEG | 2 | cont | -41.9 .. 39.79 | 0.02046 | 0.99 | 83.8 | no | 29.3 | 33.9/h @-41.9 |  |  |
| RUDP | RUDDER PEDAL POSITION | COUNTS | 2 | int-cont | 0 .. 3026 | 1 | 1 | 4096 | yes | 59.5 | 36.2/h @0 |  |  |
| SHKR | STICK SHAKER |  | 2 | discrete | {0,1} |  | 1 |  |  | 0.66 |  |  |  |
| TOCW | TAKEOFF CONF WARNING |  | 2 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| ABRK | AIRBRAKE POSITION | DEG | 1 | cont | 60 .. 120 | 0.01465 | 0.98 | 60 | yes | 97.5 | 11.4/h @60; 3.31/h @119.98 |  |  |
| ACMT | ACMS TIMING USED T1HZ |  | 1 | int-cont | 0 .. 86 | 1 | 1 | 4096 | yes | 54.1 | 401/h @0 |  |  |
| AIL_1 | AILERON POSITION LH | DEG | 1 | cont | 41.9 .. 104.1 | 0.02045 | 0.99 | 83.78 | no | 20.7 | 8.74/h @41.9 |  | 41.9 floor sentinel |
| AIL_2 | AILERON POSITION RH | DEG | 1 | cont | 41.9 .. 105.7 | 0.02045 | 0.99 | 83.78 | no | 15.3 | 10.3/h @41.9 |  |  |
| ALTS | SELECTED ALTITUDE LSP | FEET | 1 | int-cont | 0 .. 3.5e+04 | 100 | 1 | 4.096e+05 | yes | 99.7 |  |  |  |
| APFD | AP FD STATUS |  | 1 | discrete | {0,1,2} | 1 | 1 | 4096 |  | 99.9 |  |  |  |
| ATEN | A/T ENGAGE STATUS |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| A_T | THRUST AUTOMATIC ON |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| BLV | BLEED AIR ALL VALVES |  | 1 | discrete | {0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15} | 1 | 1 | 4096 |  | 99.9 |  |  |  |
| BPGR_1 | BRAKE PRESSURE LH GREEN | PSI | 1 | cont | 0 .. 405.3 | 4.883 | 1 | 2e+04 | yes | 100 |  |  |  |
| BPGR_2 | BRAKE PRESSURE RH GREEN | PSI | 1 | cont | 0 .. 2988 | 4.883 | 1 | 2e+04 | yes | 79.7 | 0.85/h @0 |  |  |
| BPYR_1 | BRAKE PRESSURE LH YELLOW | PSI | 1 | cont | 0 .. 3186 | 4.883 | 1 | 2e+04 | yes | 70.3 | 9.03/h @0 |  |  |
| BPYR_2 | BRAKE PRESSURE RH YELLOW | PSI | 1 | cont | 0 .. 400.4 | 9.766 | 1 | 4e+04 | yes | 100 |  |  |  |
| CALT | CABIN HIGH ALTITUDE |  | 1 | discrete | {0} |  |  |  |  | 100 |  |  |  |
| CASS | SELECTED AIRSPEED | KNOTS | 1 | cont | 0 .. 300 | 0.25 | 1 | 1024 | yes | 98.8 |  |  |  |
| CRSS | SELECTED COURSE | DEG | 1 | cont | -180 .. 178.9 | 0.9668 | 0.2 | 3960 | no | 99.5 |  |  |  |
| DFGS | DFGS 1&2 MASTER |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| DWPT | DISTANCE TO WAYPOINT LSP |  | 1 | int-cont | 0 .. 7.137e+05 | 4 | 1 | 1.638e+04 | yes | 44.1 | 20.9/h @0 |  |  |
| EAI | ENGINE ANTICE ALL POSITIONS |  | 1 | discrete | {0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15} | 1 | 1 | 4096 |  | 99.8 |  |  |  |
| ELEV_1 | ELEVATOR POSITION LEFT | DEG | 1 | cont | -41.9 .. 21.79 | 0.02046 | 1 | 83.8 | no | 25 | 10.2/h @-41.9 |  |  |
| ELEV_2 | ELEVATOR POSITION RIGHT | DEG | 1 | cont | 41.9 .. 105.5 | 0.02046 | 1 | 83.8 | no | 25.3 | 10.5/h @41.9 |  | range 41.9-105.9 vs ELEV_1 -41.9-22: inconsistent conversion |
| EVNT | EVENT MARKER |  | 1 | discrete | {0,1} |  | 1 |  |  | 92 |  |  |  |
| FADF | FADEC FAIL ALL ENGINES |  | 1 | discrete | {0,1,13,14,15} |  | 1 |  |  | 100 |  |  |  |
| FADS | FADEC STATUS ALL ENGINES |  | 1 | discrete | {0,13,14,15} |  | 1 |  |  | 100 |  |  |  |
| FGC3 | DFGS STATUS 3 |  | 1 | int-cont | 0 .. 2042 | 1 | 1 | 4096 | yes | 97.5 |  |  |  |
| FIRE_1 | ENGINE FIRE #1 |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| FIRE_2 | ENGINE FIRE #2 |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| FIRE_3 | ENGINE FIRE #3 |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| FIRE_4 | ENGINE FIRE #4 |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| FLAP | T.E. FLAP POSITION | COUNTS | 1 | int-cont | 54 .. 3691 | 1 | 1 | 4096 | yes | 57.8 |  |  |  |
| FQTY_1 | FUEL QUANTITY TANK 1 LSB | LBS | 1 | int-cont | 0 .. 8312 | 8 | 1 | 3.277e+04 | yes | 72.3 |  |  |  |
| FQTY_2 | FUEL QUANTITY TANK 2 LSB | LSB | 1 | int-cont | 0 .. 4528 | 8 | 1 | 3.277e+04 | yes | 100 |  |  |  |
| FQTY_3 | FUEL QUANTITY TANK 3 LSB | LSB | 1 | discrete | {0} |  |  |  |  | 100 |  |  | always 0 (dead channel) |
| FQTY_4 | FUEL QUANTITY TANK 4 LSB | LSB | 1 | int-cont | 0 .. 8456 | 8 | 1 | 3.277e+04 | yes | 71.2 |  |  |  |
| GLS | GLIDESLOPE DEVIATION | DDM | 1 | cont | -0.7987 .. 0.7751 | 0.00039 | 1 | 1.597 | no | 39 | 0.142/h @-0.79872 |  |  |
| GPWS | GPWS 1-5 |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| HDGS | SELECTED HEADING | DEG | 1 | cont | -180 .. 178.9 | 0.9668 | 0.26 | 3960 | no | 99.3 |  |  |  |
| HF1 | HF KEYING #1 |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| HF2 | HF KEYING #2 |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| HYDG | LOW HYDRAULIC PRESSURE GREEN |  | 1 | discrete | {0,1} |  | 1 |  |  | 99.4 |  |  |  |
| HYDY | LOW HYDRAULIC PRESSURE YELLOW |  | 1 | discrete | {0,1} |  | 1 |  |  | 99.1 |  |  |  |
| ILSF | ILS FREQUENCY LSP |  | 1 | int-cont | 100 .. 2.303e+06 | 1.843e+04 | 1 | 7.55e+07 | no | 100 |  |  |  |
| LATP | LATITUDE POSITION LSP | DEG | 1 | cont | 0 .. 50.49 | 0.0001723 | 1 | 0.7059 | no | 25.7 |  |  |  |
| LGDN | GEARS L&R DOWN LOCKED |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  | inverted: 1 above FL150 (gear up), 0 on ground |
| LGUP | GEARS L&R UP LOCKED |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  | inverted: 0 above FL150, ~1 on ground |
| LMOD | LATERAL ENGAGE MODES |  | 1 | discrete | {0,1,2,3,4,5,6,7,8,9,10,12,13,14} | 1 | 1 | 4096 |  | 99.8 |  |  |  |
| LOC | LOCALIZER DEVIATION | DDM | 1 | cont | -0.4014 .. 0.4012 | 0.000196 | 1 | 0.8028 | no | 1.5 | 0.222/h @-0.40141; 0.159/h @0.40121 |  |  |
| LONP | LONGITUDE POSITION LSP | DEG | 1 | cont | -104.7 .. 0.3516 | 0.0001838 | 1 | 0.7529 | no | 27.7 |  |  |  |
| MNS | SELECTED MACH | MMACH | 1 | int-cont | 0 .. 729 | 1 | 1 | 4096 | yes | 91.4 |  |  |  |
| MRK | MARKERS- INNER, MIDDLE, OUTER |  | 1 | discrete | {0,3,4,5,6,7} | 2 | 1 | 8192 |  | 99.4 |  |  |  |
| MW | MASTER WARNING |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| N1CO | N1 COMPENSATION |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| OIPL | LOW OIL PRESSURE ALL ENGINES |  | 1 | discrete | {0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15} | 1 | 1 | 4096 |  | 99.8 |  |  |  |
| OIP_1 | OIL PRESSURE 1 | PSI | 1 | cont | 0 .. 95.24 | 2.442 | 1 | 1e+04 | no | 68.9 | 8.64/h @0 | 28 |  |
| OIP_2 | OIL PRESSURE 2 | PSI | 1 | cont | 0 .. 107.4 | 2.442 | 1 | 1e+04 | no | 71.3 | 9.15/h @0 |  |  |
| OIP_3 | OIL PRESSURE 3 | PSI | 1 | cont | 0 .. 100.1 | 2.442 | 1 | 1e+04 | no | 70.8 | 9.55/h @0 |  |  |
| OIP_4 | OIL PRESSURE 4 | PSI | 1 | cont | 0 .. 90.35 | 2.442 | 1 | 1e+04 | no | 70.7 | 9.77/h @0 | 1 |  |
| OIT_1 | OIL TEMPERATURE 1 | DEG | 1 | cont | -390 .. 125.1 | 1.343 | 0.98 | 5501 | no | 78.3 | 10.3/h @-390 |  | -390 sentinel |
| OIT_2 | OIL TEMPERATURE 2 | DEG | 1 | cont | -390 .. 125.8 | 1.343 | 0.98 | 5501 | no | 81.6 | 9.27/h @-390 | 9 | -390 sentinel |
| OIT_3 | OIL TEMPERATURE 3 | DEG | 1 | cont | -390 .. 124.4 | 1.343 | 0.98 | 5501 | no | 81.5 | 9.69/h @-390 | 1 | -390 sentinel |
| OIT_4 | OIL TEMPERATURE 4 | DEG | 1 | cont | -390 .. 125.8 | 1.343 | 0.98 | 5501 | no | 79.1 | 9.96/h @-390 |  | -390 sentinel |
| PACK | PACK AIR CONDITIONING ALL |  | 1 | discrete | {0,1,2,3} | 1 | 1 | 4096 |  | 99.9 |  |  |  |
| PH | FLIGHT PHASE FROM ACMS |  | 1 | discrete | {0,1,2,3,4,5,6,7,15} | 1 | 1 | 4096 |  | 99.8 |  |  | codes 0-7 + rare 15 (invalid) |
| POVT | PYLON OVERHEAT ALL ENGINES |  | 1 | discrete | {0} |  |  |  |  | 100 |  |  |  |
| PTRM | PITCH TRIM POSITION | DEG | 1 | cont | -36.86 .. 8.956 | 0.02046 | 1 | 83.8 | no | 52.2 | 9.21/h @-36.86 |  |  |
| PUSH | STICK PUSHER |  | 1 | discrete | {0,1} |  | 1 |  |  | 94.4 |  |  |  |
| SAT | STATIC AIR TEMPERATURE | DEG | 1 | cont | -53 .. 41.5 | 0.25 | 1 | 1024 | yes | 82.4 |  |  |  |
| SMKB | ANIMAL BAY SMOKE |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| SMOK | SMOKE WARNING |  | 1 | discrete | {0} |  |  |  |  | 100 |  |  |  |
| SNAP | MANUAL SNAPSHOT SWITCH |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| SPLG | SPOILER DEPLOY GREEN |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| SPLY | SPOILER DEPLOY YELLOW |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| SPL_1 | ROLL SPOILER LEFT | DEG | 1 | cont | 36.54 .. 73.12 | 0.009613 | 0.99 | 39.37 | no | 39 | 9.41/h @36.54 |  |  |
| SPL_2 | ROLL SPOILER RIGHT | DEG | 1 | cont | 36.54 .. 73.94 | 0.009613 | 0.99 | 39.37 | no | 48.3 | 11.3/h @36.54 |  |  |
| TAI | TAIL ANTICE ON |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| TAT | TOTAL AIR TEMPERATURE | DEG | 1 | cont | -33.75 .. 42.12 | 0.25 | 1 | 1024 | yes | 84.7 |  |  |  |
| TCAS | TCAS LSP |  | 1 | int-cont | 0 .. 2.944e+04 | 128 | 1 | 5.243e+05 | no | 100 |  |  |  |
| TMAG | TRUE/MAG HEADING SELECT |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| TMODE | THRUST MODE |  | 1 | discrete | {0,1,2,4,5,7,8,9,10,12} | 1 | 1 | 4096 |  | 99.8 |  |  |  |
| VHF1 | VHF KEYING #1 |  | 1 | discrete | {0,1} |  | 1 |  |  | 90.2 |  |  |  |
| VHF2 | VHF KEYING #2 |  | 1 | discrete | {0,1} |  | 1 |  |  | 91.9 |  |  |  |
| VHF3 | VHF KEYING #3 |  | 1 | discrete | {0,1} |  | 1 |  |  | 99.4 |  |  |  |
| VMODE | VERTICAL ENGAGE MODES |  | 1 | discrete | {0,1,2,3,4,5,6,7,8,11,13,15} | 1 | 1 | 4096 |  | 99.6 |  |  |  |
| VSPS | SELECTED VERTICAL SPEED | FT/MIN | 1 | int-cont | -4000 .. 2992 | 48 | 0.6 | 1.966e+05 | yes | 99.6 |  |  |  |
| WAI_1 | INNER WING DEICE |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| WAI_2 | OUTER WING ANTICE |  | 1 | discrete | {0} |  |  |  |  | 100 |  |  |  |
| WOW | WEIGHT ON WHEELS |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  | inverted: 1 = airborne (verified) |
| WSHR | WINDSHEAR WARNING |  | 1 | discrete | {0,1} |  | 1 |  |  | 100 |  |  |  |
| ACID | AIRCRAFT NUMBER |  | 0.25 | discrete | {687,755} |  | 1 |  |  | 100 |  |  | 755 glitch in first frame of 4 records |
| DATE_DAY | Date (Day) | Day | 0.25 | int-cont | 1 .. 45 | 1 | 1 | 4096 | yes | 100 |  |  | 45 invalid; legit midnight roll-over |
| DATE_MONTH | Date (Month) | Month | 0.25 | discrete | {4,5,7,8,9,25} |  | 1 |  |  | 100 |  |  | 25 invalid |
| DATE_YEAR | Date (Year) | Year | 0.25 | discrete | {2001,2165} |  | 1 |  |  | 100 |  |  | 2165 invalid word in 4312 frames (192 records) |
| DVER_1 | DATABASE ID VERSION CHAR 1 |  | 0.25 | discrete | {126} |  |  |  |  | 100 |  |  |  |
| DVER_2 | DATABASE ID VERSION CHAR 2 |  | 0.25 | discrete | {0,50} |  | 1 |  |  | 100 |  |  |  |
| ECYC_1 | ENGINE CYCLE 1 LSP | HOURS | 0.25 | int-cont | 6746 .. 7661 |  | 1 |  |  | 99.9 |  |  |  |
| ECYC_2 | ENGINE CYCLE 2 LSP | HOURS | 0.25 | int-cont | 6746 .. 7661 |  | 1 |  |  | 99.9 |  |  |  |
| ECYC_3 | ENGINE CYCLE 3 LSP | HOURS | 0.25 | int-cont | 3370 .. 7661 | 1 | 1 | 4096 | yes | 99.9 |  |  |  |
| ECYC_4 | ENGINE CYCLE 4 LSP | HOURS | 0.25 | int-cont | 4587 .. 9144 | 1 | 1 | 4096 | yes | 99.9 |  |  |  |
| EHRS_1 | ENGINE HOURS 1 LSP | HOURS | 0.25 | int-cont | 4891 .. 7454 | 1 | 1 | 4096 | yes | 99.9 |  |  |  |
| EHRS_2 | ENGINE HOURS 2 LSP | HOURS | 0.25 | int-cont | 3212 .. 7454 | 1 | 1 | 4096 | yes | 99.9 |  |  |  |
| EHRS_3 | ENGINE HOURS 3 LSP | HOURS | 0.25 | int-cont | 4891 .. 7454 | 1 | 1 | 4096 | yes | 99.9 |  |  |  |
| EHRS_4 | ENGINE HOURS 4 LSP | HOURS | 0.25 | int-cont | 3894 .. 8817 | 1 | 1 | 4096 | yes | 99.9 |  |  |  |
| ESN_1 | ENGINE SERIAL NUMBER 1 LSP | UNITS | 0.25 | discrete | {8007,262143} |  | 1 |  |  | 100 |  |  | 262143 (all ones) in first frame of 7 records |
| ESN_2 | ENGINE SERIAL NUMBER 2 LSP | UNITS | 0.25 | discrete | {7958,262143} |  | 1 |  |  | 100 |  |  |  |
| ESN_3 | ENGINE SERIAL NUMBER 3 LSP | UNITS | 0.25 | discrete | {4302,8104,262143} |  | 1 |  |  | 100 |  |  |  |
| ESN_4 | ENGINE SERIAL NUMBER 4 LSP | UNITS | 0.25 | discrete | {7748,262143} |  | 1 |  |  | 100 |  |  |  |
| FRMC | FRAME COUNTER |  | 0.25 | int-cont | 0 .. 4095 | 1 | 1 | 4096 | yes | 0 |  |  | 12-bit counter, +4 per frame, step 3 at wrap (period 4095) |
| VAR_1107 | SYNC WORD FOR SUBFRAME 1 | <units> | 0.25 | discrete | {1,584} |  | 1 |  |  | 100 |  |  | sync word = 0o1107+1; '1' in first frame of 7 short records |
| VAR_2670 | SYNC WORD FOR SUBFRAME 2 | <units> | 0.25 | discrete | {1465} |  |  |  |  | 100 |  |  | sync word = 0o2670+1 |
| VAR_5107 | SYNC WORD FOR SUBFRAME 3 | <units> | 0.25 | discrete | {2632} |  |  |  |  | 100 |  |  | sync word = 0o5107+1 |
| VAR_6670 | SYNC WORD FOR SUBFRAME 4 | <units> | 0.25 | discrete | {3513} |  |  |  |  | 100 |  |  | sync word = 0o6670+1 |

Cross-tab (non-discrete parameters >= 1 Hz): (binary-scaled LSB?, systematic sentinel dropouts >= 5/h?) -> count: (False, False): 17; (False, True): 15; (True, False): 71; (True, True): 6
