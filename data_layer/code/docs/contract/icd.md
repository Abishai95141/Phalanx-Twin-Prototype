# SYNTHETIC Phalanx ICD (tejas, dictionary 0.1.3)

> **SYNTHETIC Phalanx ICD - bus map, RT/SA/word and label allocations are synthetic, NOT the real Tejas ICD.** Generated from the M01 dictionary; do not edit by hand.

## Topology

| Bus / link | Type | Controller / transmitter | Terminals / receivers | Monitors |
|---|---|---|---|---|
| AV-MUX-1 | MIL-STD-1553B | OAC | INGPS (RT 10), AHRS (RT 11), RADAR (RT 12), SMS (RT 13) | CDR, HUMS_DAU |
| AV-MUX-2 | MIL-STD-1553B | OAC | DFCC (RT 1), FADEC (RT 5), BHEEM_EU (RT 7), ECFM_C (RT 8) | CDR, HUMS_DAU |
| WPN-MUX | MIL-STD-1553B | SMS | - | - |
| CWS-OAC | ARINC-429 (low) | CWS | OAC | - |
| RADALT-OAC | ARINC-429 (high) | RADALT | OAC | - |
| ADC-DFCC | RS-422 (not recorded) | ADC | DFCC | - |
| FTP-DFCC | RS-422 (not recorded) | FTP | DFCC | - |
| FTI-PCM | PCM 12-bit @ 64 Hz | FTI_DAS | - | - |

## arinc429 CWS-OAC

| Channel | RT | T/R | SA | Word(s) | Label | Encoding | LSB | Units | Range | Validity | Group |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CWS.LEGEND.A |  |  |  |  | 100 | bitfield19 [CWS-L01@0+1;CWS-L02@1+1;CWS-L03@2+1;CWS-L04@3+1;CWS-L05@4+1;CWS-L06@5+1;CWS-L07@6+1;CWS-L08@7+1;CWS-L09@8+1;CWS-L10@9+1;CWS-L11@10+1;CWS-L12@11+1;CWS-L13@12+1;CWS-L14@13+1;CWS-L15@14+1] |  | dimensionless |  | ssm ssm_dis | AV12.5 |
| CWS.LEGEND.B |  |  |  |  | 101 | bitfield19 [CWS-L16@0+1;CWS-L17@1+1;CWS-L18@2+1;CWS-L19@3+1;CWS-L20@4+1;CWS-L21@5+1;CWS-L22@6+1;CWS-L23@7+1;CWS-L24@8+1;CWS-L25@9+1;CWS-L26@10+1;CWS-L27@11+1;CWS-L28@12+1;CWS-L29@13+1;CWS-L30@14+1] |  | dimensionless |  | ssm ssm_dis | AV12.5 |
| CWS.MASTER |  |  |  |  | 102 | bitfield19 [MASTER_WARNING@0+1;MASTER_CAUTION@1+1] |  | dimensionless |  | ssm ssm_dis | AV12.5 |
| CWS.VOICE.AOA |  |  |  |  | 103 | bitfield19 [VOICE_WARNING_ACTIVE@0+1] |  | dimensionless |  | ssm ssm_dis | AV12.5 |
| CWS.VOICE.CANOPY |  |  |  |  | 104 | bitfield19 [VOICE_WARNING_ACTIVE@0+1] |  | dimensionless |  | ssm ssm_dis | AV12.5 |
| CWS.VOICE.LOW_ALT |  |  |  |  | 105 | bitfield19 [VOICE_WARNING_ACTIVE@0+1] |  | dimensionless |  | ssm ssm_dis | AV12.5 |
| CWS.VOICE.UC |  |  |  |  | 106 | bitfield19 [VOICE_WARNING_ACTIVE@0+1] |  | dimensionless |  | ssm ssm_dis | AV12.5 |

## arinc429 RADALT-OAC

| Channel | RT | T/R | SA | Word(s) | Label | Encoding | LSB | Units | Range | Validity | Group |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NAV.RADALT |  |  |  |  | 100 | bnr19 | 1 | ft | 0..5000 | ssm ssm_bnr | AV25 |

## fti_pcm FTI-PCM

| Channel | RT | T/R | SA | Word(s) | Label | Encoding | LSB | Units | Range | Validity | Group |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AD.BOOM.ALPHA |  |  |  | 1 |  | bnr12 | 0.0625 | deg | -90..90 | frame_sync | FTI |
| AD.BOOM.BETA |  |  |  | 2 |  | bnr12 | 0.0625 | deg | -90..90 | frame_sync | FTI |
| AD.BOOM.PS |  |  |  | 3 |  | ubnr12 | 0.5 | mbar | 35..1300 | frame_sync | FTI |
| AD.BOOM.PT |  |  |  | 4 |  | ubnr12 | 1.0 | mbar | 35..2700 | frame_sync | FTI |
| ENG.WFAB |  |  |  | 5 |  | ubnr12 | 16 | lb/hr | 0..30000 | frame_sync | FTI |
| FCS.FTP.FLAGS |  |  |  | 6 |  | bitfield12 [EXCITATION_ACTIVE@0+1;AUTO_ABORT@1+1] |  | dimensionless |  | frame_sync | FTI |
| FCS.FTP.TEST_POINT |  |  |  | 7 |  | ubnr12 | 1 | count | 0..99 | frame_sync | FTI |
| STRUCT.STRAIN.MLG |  |  |  | 8 |  | bnr12 | 4.0 | microstrain | -5000..5000 | frame_sync | FTI |
| STRUCT.STRAIN.STORES |  |  |  | 9 |  | bnr12 | 4.0 | microstrain | -5000..5000 | frame_sync | FTI |
| STRUCT.STRAIN.WING |  |  |  | 10 |  | bnr12 | 4.0 | microstrain | -5000..5000 | frame_sync | FTI |

## mil1553 AV-MUX-1

| Channel | RT | T/R | SA | Word(s) | Label | Encoding | LSB | Units | Range | Validity | Group |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NAV.GPS.STATUS.FOM | 10 | T | 1 | 3 |  | enum16 |  | dimensionless |  | validity_word w1 b15 | AV50 |
| NAV.GPS.STATUS.GPS_FIX | 10 | T | 1 | 4 |  | enum16 |  | dimensionless |  | validity_word w1 b14 | AV50 |
| NAV.GPS.STATUS.INS_MODE | 10 | T | 1 | 5 |  | enum16 |  | dimensionless |  | validity_word w1 b13 | AV50 |
| NAV.INS.ACCEL.X | 10 | T | 1 | 6 |  | bnr16 | 0.001 | standard_gravity | -12..12 | validity_word w1 b12 | AV50 |
| NAV.INS.ACCEL.Y | 10 | T | 1 | 7 |  | bnr16 | 0.001 | standard_gravity | -12..12 | validity_word w1 b11 | AV50 |
| NAV.INS.ACCEL.Z | 10 | T | 1 | 8 |  | bnr16 | 0.001 | standard_gravity | -12..12 | validity_word w1 b10 | AV50 |
| NAV.INS.ALT | 10 | T | 1 | 9+1 |  | bnr32 | 3.0517578125e-05 | ft | -2000..60000 | validity_word w1 b9 | AV50 |
| NAV.INS.BODY_RATES.P_NB | 10 | T | 1 | 11+1 |  | bnr32 | 0.01 | deg/s | -400..400 | validity_word w1 b8 | AV50 |
| NAV.INS.BODY_RATES.P_WB | 10 | T | 1 | 13+1 |  | bnr32 | 0.01 | deg/s | -400..400 | validity_word w1 b7 | AV50 |
| NAV.INS.BODY_RATES.Q_NB | 10 | T | 1 | 15+1 |  | bnr32 | 0.01 | deg/s | -400..400 | validity_word w1 b6 | AV50 |
| NAV.INS.BODY_RATES.Q_WB | 10 | T | 1 | 17+1 |  | bnr32 | 0.01 | deg/s | -400..400 | validity_word w1 b5 | AV50 |
| NAV.INS.BODY_RATES.R_NB | 10 | T | 1 | 19+1 |  | bnr32 | 0.01 | deg/s | -400..400 | validity_word w1 b4 | AV50 |
| NAV.INS.BODY_RATES.R_WB | 10 | T | 1 | 21+1 |  | bnr32 | 0.01 | deg/s | -400..400 | validity_word w1 b3 | AV50 |
| NAV.INS.HDG_TRUE | 10 | T | 1 | 23 |  | ubnr16 | 0.0055 | deg | 0..360 | validity_word w1 b2 | AV50 |
| NAV.INS.LAT | 10 | T | 1 | 24+1 |  | bnr32 | 5.960464477539063e-08 | deg | -90..90 | validity_word w1 b1 | AV50 |
| NAV.INS.LON | 10 | T | 1 | 26+1 |  | bnr32 | 1.1920928955078125e-07 | deg | -180..180 | validity_word w1 b0 | AV50 |
| NAV.INS.PITCH | 10 | T | 1 | 28 |  | bnr16 | 0.011 | deg | -90..90 | validity_word w2 b15 | AV50 |
| NAV.INS.ROLL | 10 | T | 1 | 29 |  | bnr16 | 0.011 | deg | -180..180 | validity_word w2 b14 | AV50 |
| NAV.INS.VD | 10 | T | 1 | 30+1 |  | bnr32 | 0.01 | ft/s | -1000..1000 | validity_word w2 b13 | AV50 |
| NAV.INS.VE | 10 | T | 2 | 2+1 |  | bnr32 | 0.01 | ft/s | -3000..3000 | validity_word w1 b15 | AV50 |
| NAV.INS.VN | 10 | T | 2 | 4+1 |  | bnr32 | 0.01 | ft/s | -3000..3000 | validity_word w1 b14 | AV50 |
| AV.LRU.HEALTH.INGPS.LINK | 10 | T | 3 | 2 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b15 | AV12.5 |
| AV.LRU.HEALTH.INGPS.MEMORY | 10 | T | 3 | 3 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b14 | AV12.5 |
| AV.LRU.HEALTH.INGPS.PORT | 10 | T | 3 | 4 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b13 | AV12.5 |
| AV.LRU.HEALTH.INGPS.TEMP | 10 | T | 3 | 5 |  | bnr16 | 0.1 | degF | -67..257 | validity_word w1 b12 | AV12.5 |
| NAV.AHRS.HEADING | 11 | T | 1 | 2 |  | ubnr16 | 0.01 | deg | 0..360 | validity_word w1 b15 | AV25 |
| NAV.AHRS.PITCH | 11 | T | 1 | 3 |  | bnr16 | 0.01 | deg | -90..90 | validity_word w1 b14 | AV25 |
| NAV.AHRS.ROLL | 11 | T | 1 | 4 |  | bnr16 | 0.01 | deg | -180..180 | validity_word w1 b13 | AV25 |
| AV.LRU.HEALTH.AHRS.LINK | 11 | T | 2 | 2 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b15 | AV12.5 |
| AV.LRU.HEALTH.AHRS.MEMORY | 11 | T | 2 | 3 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b14 | AV12.5 |
| AV.LRU.HEALTH.AHRS.PORT | 11 | T | 2 | 4 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b13 | AV12.5 |
| AV.LRU.HEALTH.AHRS.TEMP | 11 | T | 2 | 5 |  | bnr16 | 0.1 | degF | -67..257 | validity_word w1 b12 | AV12.5 |
| AV.LRU.HEALTH.RADAR.LINK | 12 | T | 1 | 2 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b15 | AV12.5 |
| AV.LRU.HEALTH.RADAR.MEMORY | 12 | T | 1 | 3 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b14 | AV12.5 |
| AV.LRU.HEALTH.RADAR.PORT | 12 | T | 1 | 4 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b13 | AV12.5 |
| AV.LRU.HEALTH.RADAR.TEMP | 12 | T | 1 | 5 |  | bnr16 | 0.1 | degF | -67..257 | validity_word w1 b12 | AV12.5 |
| AV.LRU.HEALTH.SMS.LINK | 13 | T | 1 | 2 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b15 | AV12.5 |
| AV.LRU.HEALTH.SMS.MEMORY | 13 | T | 1 | 3 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b14 | AV12.5 |
| AV.LRU.HEALTH.SMS.PORT | 13 | T | 1 | 4 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b13 | AV12.5 |
| AV.LRU.HEALTH.SMS.TEMP | 13 | T | 1 | 5 |  | bnr16 | 0.1 | degF | -67..257 | validity_word w1 b12 | AV12.5 |
| STORES.CONFIG.RELEASE | 13 | T | 1 | 6 |  | bitfield16 [STATION_1_RELEASED@0+1;STATION_2_RELEASED@1+1;STATION_3_RELEASED@2+1;STATION_4_RELEASED@3+1;STATION_5_RELEASED@4+1;STATION_6_RELEASED@5+1;STATION_7_RELEASED@6+1;STATION_8_RELEASED@7+1;STATION_9_RELEASED@8+1] |  | dimensionless |  | validity_word w1 b11 | AV12.5 |
| STORES.CONFIG.STATION_1 | 13 | T | 1 | 7 |  | enum16 |  | dimensionless |  | validity_word w1 b10 | AV12.5 |
| STORES.CONFIG.STATION_2 | 13 | T | 1 | 8 |  | enum16 |  | dimensionless |  | validity_word w1 b9 | AV12.5 |
| STORES.CONFIG.STATION_3 | 13 | T | 1 | 9 |  | enum16 |  | dimensionless |  | validity_word w1 b8 | AV12.5 |
| STORES.CONFIG.STATION_4 | 13 | T | 1 | 10 |  | enum16 |  | dimensionless |  | validity_word w1 b7 | AV12.5 |
| STORES.CONFIG.STATION_5 | 13 | T | 1 | 11 |  | enum16 |  | dimensionless |  | validity_word w1 b6 | AV12.5 |
| STORES.CONFIG.STATION_6 | 13 | T | 1 | 12 |  | enum16 |  | dimensionless |  | validity_word w1 b5 | AV12.5 |
| STORES.CONFIG.STATION_7 | 13 | T | 1 | 13 |  | enum16 |  | dimensionless |  | validity_word w1 b4 | AV12.5 |
| STORES.CONFIG.STATION_8 | 13 | T | 1 | 14 |  | enum16 |  | dimensionless |  | validity_word w1 b3 | AV12.5 |
| STORES.CONFIG.STATION_9 | 13 | T | 1 | 15 |  | enum16 |  | dimensionless |  | validity_word w1 b2 | AV12.5 |

## mil1553 AV-MUX-2

| Channel | RT | T/R | SA | Word(s) | Label | Encoding | LSB | Units | Range | Validity | Group |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FCS.ACT.BIT.AIRBRAKE_L | 1 | T | 1 | 3 |  | bitfield16 [SERVO_FAIL_A@0+1;SERVO_FAIL_B@1+1;SERVO_FAIL_C@2+1;SERVO_FAIL_D@3+1;LVDT_SUM_FAIL_A@4+1;LVDT_SUM_FAIL_B@5+1;LVDT_SUM_FAIL_C@6+1;LVDT_SUM_FAIL_D@7+1;HYD_PRESS_FAIL_A@8+1;HYD_PRESS_FAIL_B@9+1;HYD_PRESS_FAIL_C@10+1;HYD_PRESS_FAIL_D@11+1] |  | dimensionless |  | validity_word w1 b15 | AV50 |
| FCS.ACT.BIT.AIRBRAKE_R | 1 | T | 1 | 4 |  | bitfield16 [SERVO_FAIL_A@0+1;SERVO_FAIL_B@1+1;SERVO_FAIL_C@2+1;SERVO_FAIL_D@3+1;LVDT_SUM_FAIL_A@4+1;LVDT_SUM_FAIL_B@5+1;LVDT_SUM_FAIL_C@6+1;LVDT_SUM_FAIL_D@7+1;HYD_PRESS_FAIL_A@8+1;HYD_PRESS_FAIL_B@9+1;HYD_PRESS_FAIL_C@10+1;HYD_PRESS_FAIL_D@11+1] |  | dimensionless |  | validity_word w1 b14 | AV50 |
| FCS.ACT.BIT.ELEVON_LIB | 1 | T | 1 | 5 |  | bitfield16 [SERVO_FAIL_A@0+1;SERVO_FAIL_B@1+1;SERVO_FAIL_C@2+1;SERVO_FAIL_D@3+1;LVDT_SUM_FAIL_A@4+1;LVDT_SUM_FAIL_B@5+1;LVDT_SUM_FAIL_C@6+1;LVDT_SUM_FAIL_D@7+1;HYD_PRESS_FAIL_A@8+1;HYD_PRESS_FAIL_B@9+1;HYD_PRESS_FAIL_C@10+1;HYD_PRESS_FAIL_D@11+1] |  | dimensionless |  | validity_word w1 b13 | AV50 |
| FCS.ACT.BIT.ELEVON_LOB | 1 | T | 1 | 6 |  | bitfield16 [SERVO_FAIL_A@0+1;SERVO_FAIL_B@1+1;SERVO_FAIL_C@2+1;SERVO_FAIL_D@3+1;LVDT_SUM_FAIL_A@4+1;LVDT_SUM_FAIL_B@5+1;LVDT_SUM_FAIL_C@6+1;LVDT_SUM_FAIL_D@7+1;HYD_PRESS_FAIL_A@8+1;HYD_PRESS_FAIL_B@9+1;HYD_PRESS_FAIL_C@10+1;HYD_PRESS_FAIL_D@11+1] |  | dimensionless |  | validity_word w1 b12 | AV50 |
| FCS.ACT.BIT.ELEVON_RIB | 1 | T | 1 | 7 |  | bitfield16 [SERVO_FAIL_A@0+1;SERVO_FAIL_B@1+1;SERVO_FAIL_C@2+1;SERVO_FAIL_D@3+1;LVDT_SUM_FAIL_A@4+1;LVDT_SUM_FAIL_B@5+1;LVDT_SUM_FAIL_C@6+1;LVDT_SUM_FAIL_D@7+1;HYD_PRESS_FAIL_A@8+1;HYD_PRESS_FAIL_B@9+1;HYD_PRESS_FAIL_C@10+1;HYD_PRESS_FAIL_D@11+1] |  | dimensionless |  | validity_word w1 b11 | AV50 |
| FCS.ACT.BIT.ELEVON_ROB | 1 | T | 1 | 8 |  | bitfield16 [SERVO_FAIL_A@0+1;SERVO_FAIL_B@1+1;SERVO_FAIL_C@2+1;SERVO_FAIL_D@3+1;LVDT_SUM_FAIL_A@4+1;LVDT_SUM_FAIL_B@5+1;LVDT_SUM_FAIL_C@6+1;LVDT_SUM_FAIL_D@7+1;HYD_PRESS_FAIL_A@8+1;HYD_PRESS_FAIL_B@9+1;HYD_PRESS_FAIL_C@10+1;HYD_PRESS_FAIL_D@11+1] |  | dimensionless |  | validity_word w1 b10 | AV50 |
| FCS.ACT.BIT.RUDDER | 1 | T | 1 | 9 |  | bitfield16 [SERVO_FAIL_A@0+1;SERVO_FAIL_B@1+1;SERVO_FAIL_C@2+1;SERVO_FAIL_D@3+1;LVDT_SUM_FAIL_A@4+1;LVDT_SUM_FAIL_B@5+1;LVDT_SUM_FAIL_C@6+1;LVDT_SUM_FAIL_D@7+1;HYD_PRESS_FAIL_A@8+1;HYD_PRESS_FAIL_B@9+1;HYD_PRESS_FAIL_C@10+1;HYD_PRESS_FAIL_D@11+1] |  | dimensionless |  | validity_word w1 b9 | AV50 |
| FCS.ACT.BIT.SLAT_IB_L | 1 | T | 1 | 10 |  | bitfield16 [SERVO_FAIL_A@0+1;SERVO_FAIL_B@1+1;SERVO_FAIL_C@2+1;SERVO_FAIL_D@3+1;LVDT_SUM_FAIL_A@4+1;LVDT_SUM_FAIL_B@5+1;LVDT_SUM_FAIL_C@6+1;LVDT_SUM_FAIL_D@7+1;HYD_PRESS_FAIL_A@8+1;HYD_PRESS_FAIL_B@9+1;HYD_PRESS_FAIL_C@10+1;HYD_PRESS_FAIL_D@11+1] |  | dimensionless |  | validity_word w1 b8 | AV50 |
| FCS.ACT.BIT.SLAT_IB_R | 1 | T | 1 | 11 |  | bitfield16 [SERVO_FAIL_A@0+1;SERVO_FAIL_B@1+1;SERVO_FAIL_C@2+1;SERVO_FAIL_D@3+1;LVDT_SUM_FAIL_A@4+1;LVDT_SUM_FAIL_B@5+1;LVDT_SUM_FAIL_C@6+1;LVDT_SUM_FAIL_D@7+1;HYD_PRESS_FAIL_A@8+1;HYD_PRESS_FAIL_B@9+1;HYD_PRESS_FAIL_C@10+1;HYD_PRESS_FAIL_D@11+1] |  | dimensionless |  | validity_word w1 b7 | AV50 |
| FCS.ACT.BIT.SLAT_MB_L | 1 | T | 1 | 12 |  | bitfield16 [SERVO_FAIL_A@0+1;SERVO_FAIL_B@1+1;SERVO_FAIL_C@2+1;SERVO_FAIL_D@3+1;LVDT_SUM_FAIL_A@4+1;LVDT_SUM_FAIL_B@5+1;LVDT_SUM_FAIL_C@6+1;LVDT_SUM_FAIL_D@7+1;HYD_PRESS_FAIL_A@8+1;HYD_PRESS_FAIL_B@9+1;HYD_PRESS_FAIL_C@10+1;HYD_PRESS_FAIL_D@11+1] |  | dimensionless |  | validity_word w1 b6 | AV50 |
| FCS.ACT.BIT.SLAT_MB_R | 1 | T | 1 | 13 |  | bitfield16 [SERVO_FAIL_A@0+1;SERVO_FAIL_B@1+1;SERVO_FAIL_C@2+1;SERVO_FAIL_D@3+1;LVDT_SUM_FAIL_A@4+1;LVDT_SUM_FAIL_B@5+1;LVDT_SUM_FAIL_C@6+1;LVDT_SUM_FAIL_D@7+1;HYD_PRESS_FAIL_A@8+1;HYD_PRESS_FAIL_B@9+1;HYD_PRESS_FAIL_C@10+1;HYD_PRESS_FAIL_D@11+1] |  | dimensionless |  | validity_word w1 b5 | AV50 |
| FCS.ACT.BIT.SLAT_OB_L | 1 | T | 1 | 14 |  | bitfield16 [SERVO_FAIL_A@0+1;SERVO_FAIL_B@1+1;SERVO_FAIL_C@2+1;SERVO_FAIL_D@3+1;LVDT_SUM_FAIL_A@4+1;LVDT_SUM_FAIL_B@5+1;LVDT_SUM_FAIL_C@6+1;LVDT_SUM_FAIL_D@7+1;HYD_PRESS_FAIL_A@8+1;HYD_PRESS_FAIL_B@9+1;HYD_PRESS_FAIL_C@10+1;HYD_PRESS_FAIL_D@11+1] |  | dimensionless |  | validity_word w1 b4 | AV50 |
| FCS.ACT.BIT.SLAT_OB_R | 1 | T | 1 | 15 |  | bitfield16 [SERVO_FAIL_A@0+1;SERVO_FAIL_B@1+1;SERVO_FAIL_C@2+1;SERVO_FAIL_D@3+1;LVDT_SUM_FAIL_A@4+1;LVDT_SUM_FAIL_B@5+1;LVDT_SUM_FAIL_C@6+1;LVDT_SUM_FAIL_D@7+1;HYD_PRESS_FAIL_A@8+1;HYD_PRESS_FAIL_B@9+1;HYD_PRESS_FAIL_C@10+1;HYD_PRESS_FAIL_D@11+1] |  | dimensionless |  | validity_word w1 b3 | AV50 |
| FCS.AIRBRAKE.POS.L.V | 1 | T | 1 | 16 |  | bnr16 | 1 | mm | 0..294 | validity_word w1 b2 | AV50 |
| FCS.AIRBRAKE.POS.R.V | 1 | T | 1 | 17 |  | bnr16 | 1 | mm | 0..294 | validity_word w1 b1 | AV50 |
| FCS.AIRDATA_MISTRACK | 1 | T | 1 | 18 |  | bitfield16 [ADC_A_EXCLUDED@0+1;ADC_B_EXCLUDED@1+1;ADC_C_EXCLUDED@2+1;ADC_D_EXCLUDED@3+1;PRESSURE_MISTRACK@4+1;AOA_VANE_MISTRACK@5+1;AOSS_VANE_MISTRACK@6+1] |  | dimensionless |  | validity_word w1 b0 | AV50 |
| FCS.ASA.NY.V | 1 | T | 1 | 19 |  | bnr16 | 0.001 | standard_gravity | -4.5..4.5 | validity_word w2 b15 | AV50 |
| FCS.CH.STATUS.A | 1 | T | 1 | 20 |  | bitfield16 [CHANNEL_FAILED@0+1;CHANNEL_RESET@1+1;CHANNEL_DROPOUT@2+1;CCDL_FAIL@3+1] |  | dimensionless |  | validity_word w2 b14 | AV50 |
| FCS.CH.STATUS.B | 1 | T | 1 | 21 |  | bitfield16 [CHANNEL_FAILED@0+1;CHANNEL_RESET@1+1;CHANNEL_DROPOUT@2+1;CCDL_FAIL@3+1] |  | dimensionless |  | validity_word w2 b13 | AV50 |
| FCS.CH.STATUS.C | 1 | T | 1 | 22 |  | bitfield16 [CHANNEL_FAILED@0+1;CHANNEL_RESET@1+1;CHANNEL_DROPOUT@2+1;CCDL_FAIL@3+1] |  | dimensionless |  | validity_word w2 b12 | AV50 |
| FCS.CH.STATUS.D | 1 | T | 1 | 23 |  | bitfield16 [CHANNEL_FAILED@0+1;CHANNEL_RESET@1+1;CHANNEL_DROPOUT@2+1;CCDL_FAIL@3+1] |  | dimensionless |  | validity_word w2 b11 | AV50 |
| FCS.ELEVON.LIB.CMD | 1 | T | 1 | 24 |  | bnr16 | 0.02 | deg | -25..25 | validity_word w2 b10 | AV50 |
| FCS.ELEVON.LIB.POS.V | 1 | T | 1 | 25 |  | bnr16 | 0.02 | deg | -25..25 | validity_word w2 b9 | AV50 |
| FCS.ELEVON.LOB.CMD | 1 | T | 1 | 26 |  | bnr16 | 0.02 | deg | -25..25 | validity_word w2 b8 | AV50 |
| FCS.ELEVON.LOB.POS.V | 1 | T | 1 | 27 |  | bnr16 | 0.02 | deg | -25..25 | validity_word w2 b7 | AV50 |
| FCS.ELEVON.RIB.CMD | 1 | T | 1 | 28 |  | bnr16 | 0.02 | deg | -25..25 | validity_word w2 b6 | AV50 |
| FCS.ELEVON.RIB.POS.V | 1 | T | 1 | 29 |  | bnr16 | 0.02 | deg | -25..25 | validity_word w2 b5 | AV50 |
| FCS.ELEVON.ROB.CMD | 1 | T | 1 | 30 |  | bnr16 | 0.02 | deg | -25..25 | validity_word w2 b4 | AV50 |
| FCS.ELEVON.ROB.POS.V | 1 | T | 1 | 31 |  | bnr16 | 0.02 | deg | -25..25 | validity_word w2 b3 | AV50 |
| FCS.HEATER_I.AOA_VANE_L | 1 | T | 1 | 32 |  | bnr16 | 0.05 | A | 0..10 | validity_word w2 b2 | AV50 |
| FCS.HEATER_I.AOA_VANE_R | 1 | T | 2 | 3 |  | bnr16 | 0.05 | A | 0..10 | validity_word w1 b15 | AV50 |
| FCS.HEATER_I.LADP | 1 | T | 2 | 4 |  | bnr16 | 0.05 | A | 0..10 | validity_word w1 b14 | AV50 |
| FCS.HEATER_I.NADP | 1 | T | 2 | 5 |  | bnr16 | 0.05 | A | 0..10 | validity_word w1 b13 | AV50 |
| FCS.HEATER_I.RADP | 1 | T | 2 | 6 |  | bnr16 | 0.05 | A | 0..10 | validity_word w1 b12 | AV50 |
| FCS.HEATER_I.TAT | 1 | T | 2 | 7 |  | bnr16 | 0.05 | A | 0..10 | validity_word w1 b11 | AV50 |
| FCS.KALMAN_ATT.PITCH | 1 | T | 2 | 8 |  | bnr16 | 0.01 | deg | -90..90 | validity_word w1 b10 | AV50 |
| FCS.KALMAN_ATT.ROLL | 1 | T | 2 | 9 |  | bnr16 | 0.01 | deg | -180..180 | validity_word w1 b9 | AV50 |
| FCS.MODE.FLAGS | 1 | T | 2 | 10 |  | bitfield16 [AUTOPILOT_ENGAGED@0+1;ALSR_ACTIVE@1+1;AOA_LIMITER_ACTIVE@2+1;G_LIMITER_ACTIVE@3+1;REVERSION_LATCHED@4+1] |  | dimensionless |  | validity_word w1 b8 | AV50 |
| FCS.MODE.LAW | 1 | T | 2 | 11 |  | enum16 |  | dimensionless |  | validity_word w1 b7 | AV50 |
| FCS.PEDAL.V | 1 | T | 2 | 12 |  | bnr16 | 0.1 | percent | -100..100 | validity_word w1 b6 | AV50 |
| FCS.RSA.P.V | 1 | T | 2 | 13+1 |  | bnr32 | 0.005 | deg/s | -300..300 | validity_word w1 b5 | AV50 |
| FCS.RSA.R.V | 1 | T | 2 | 15 |  | bnr16 | 0.005 | deg/s | -60..60 | validity_word w1 b4 | AV50 |
| FCS.RUDDER.CMD | 1 | T | 2 | 16 |  | bnr16 | 0.02 | deg | -30..30 | validity_word w1 b3 | AV50 |
| FCS.RUDDER.POS.V | 1 | T | 2 | 17 |  | bnr16 | 0.02 | deg | -30..30 | validity_word w1 b2 | AV50 |
| FCS.SLAT.POS.IB_L.V | 1 | T | 2 | 18 |  | bnr16 | 0.05 | deg | 0..30 | validity_word w1 b1 | AV50 |
| FCS.SLAT.POS.IB_R.V | 1 | T | 2 | 19 |  | bnr16 | 0.05 | deg | 0..30 | validity_word w1 b0 | AV50 |
| FCS.SLAT.POS.MB_L.V | 1 | T | 2 | 20 |  | bnr16 | 0.05 | deg | 0..30 | validity_word w2 b15 | AV50 |
| FCS.SLAT.POS.MB_R.V | 1 | T | 2 | 21 |  | bnr16 | 0.05 | deg | 0..30 | validity_word w2 b14 | AV50 |
| FCS.SLAT.POS.OB_L.V | 1 | T | 2 | 22 |  | bnr16 | 0.05 | deg | 0..30 | validity_word w2 b13 | AV50 |
| FCS.SLAT.POS.OB_R.V | 1 | T | 2 | 23 |  | bnr16 | 0.05 | deg | 0..30 | validity_word w2 b12 | AV50 |
| FCS.STICK.PITCH.V | 1 | T | 2 | 24 |  | bnr16 | 0.1 | percent | -100..100 | validity_word w2 b11 | AV50 |
| FCS.STICK.ROLL.V | 1 | T | 2 | 25 |  | bnr16 | 0.1 | percent | -100..100 | validity_word w2 b10 | AV50 |
| FCS.VOTED.DE | 1 | T | 2 | 26 |  | bnr16 | 0.02 | deg | -25..25 | validity_word w2 b9 | AV50 |
| FCS.VOTED.NZ | 1 | T | 2 | 27 |  | bnr16 | 0.001 | standard_gravity | -13..13 | validity_word w2 b8 | AV50 |
| FCS.VOTED.Q | 1 | T | 2 | 28 |  | bnr16 | 0.005 | deg/s | -60..60 | validity_word w2 b7 | AV50 |
| HYD.CH_STATUS | 1 | T | 2 | 29 |  | bitfield16 [CH_A_PRESSURE_OK@0+1;CH_B_PRESSURE_OK@1+1;CH_C_PRESSURE_OK@2+1;CH_D_PRESSURE_OK@3+1] |  | dimensionless |  | validity_word w2 b6 | AV50 |
| LG.WOW | 1 | T | 2 | 30 |  | bitfield16 [NOSE_WOW@0+1;LEFT_WOW@1+1;RIGHT_WOW@2+1] |  | dimensionless |  | validity_word w2 b5 | AV50 |
| AD.AOA | 1 | T | 3 | 3 |  | bnr16 | 0.044 | deg | -10..45 | validity_word w1 b15 | AV25 |
| AD.AOA_VANE_L.V | 1 | T | 3 | 4 |  | bnr16 | 0.044 | deg | -45..45 | validity_word w1 b14 | AV25 |
| AD.AOA_VANE_R.V | 1 | T | 3 | 5 |  | bnr16 | 0.044 | deg | -45..45 | validity_word w1 b13 | AV25 |
| AD.AOSS_VANE.V | 1 | T | 3 | 6 |  | bnr16 | 0.044 | deg | -45..45 | validity_word w1 b12 | AV25 |
| AD.BETA | 1 | T | 3 | 7 |  | bnr16 | 0.05 | deg | -30..30 | validity_word w1 b11 | AV25 |
| AD.CAS | 1 | T | 3 | 8 |  | bnr16 | 0.0625 | knot | 0..800 | validity_word w1 b10 | AV25 |
| AD.DPA.V | 1 | T | 3 | 9 |  | ubnr16 | 0.03125 | mbar | 35..1500 | validity_word w1 b9 | AV25 |
| AD.DPB.V | 1 | T | 3 | 10 |  | ubnr16 | 0.03125 | mbar | 35..1500 | validity_word w1 b8 | AV25 |
| AD.HBARO | 1 | T | 3 | 11+1 |  | bnr32 | 1 | ft | -2000..60000 | validity_word w1 b7 | AV25 |
| AD.HDOT | 1 | T | 3 | 13 |  | bnr16 | 10 | ft/min | -60000..60000 | validity_word w1 b6 | AV25 |
| AD.HP | 1 | T | 3 | 14+1 |  | bnr32 | 1 | ft | -2000..60000 | validity_word w1 b5 | AV25 |
| AD.MACH | 1 | T | 3 | 16 |  | bnr16 | 0.0001 | dimensionless | 0..2.0 | validity_word w1 b4 | AV25 |
| AD.PS.V | 1 | T | 3 | 17 |  | ubnr16 | 0.03125 | mbar | 35..1300 | validity_word w1 b3 | AV25 |
| AD.PT.V | 1 | T | 3 | 18+1 |  | bnr32 | 0.03125 | mbar | 35..2700 | validity_word w1 b2 | AV25 |
| AD.QBAR | 1 | T | 3 | 20 |  | bnr16 | 0.5 | pound_force/foot**2 | 0..2500 | validity_word w1 b1 | AV25 |
| AD.SAT | 1 | T | 3 | 21 |  | bnr16 | 0.25 | degC | -80..60 | validity_word w1 b0 | AV25 |
| AD.TAS | 1 | T | 3 | 22 |  | bnr16 | 0.125 | knot | 0..1100 | validity_word w2 b15 | AV25 |
| AD.TAT | 1 | T | 3 | 23 |  | bnr16 | 0.25 | degC | -60..150 | validity_word w2 b14 | AV25 |
| AD.VALID.A | 1 | T | 3 | 24 |  | bitfield16 [PS_VALID@0+1;PT_VALID@1+1;DPA_VALID@2+1;DPB_VALID@3+1;AOA_VANE_L_VALID@4+1;AOA_VANE_R_VALID@5+1;AOSS_VANE_VALID@6+1;TAT_VALID@7+1;HEATER_OK@8+1;BIT_PASS@9+1] |  | dimensionless |  | validity_word w2 b13 | AV25 |
| AD.VALID.B | 1 | T | 3 | 25 |  | bitfield16 [PS_VALID@0+1;PT_VALID@1+1;DPA_VALID@2+1;DPB_VALID@3+1;AOA_VANE_L_VALID@4+1;AOA_VANE_R_VALID@5+1;AOSS_VANE_VALID@6+1;TAT_VALID@7+1;HEATER_OK@8+1;BIT_PASS@9+1] |  | dimensionless |  | validity_word w2 b12 | AV25 |
| AD.VALID.C | 1 | T | 3 | 26 |  | bitfield16 [PS_VALID@0+1;PT_VALID@1+1;DPA_VALID@2+1;DPB_VALID@3+1;AOA_VANE_L_VALID@4+1;AOA_VANE_R_VALID@5+1;AOSS_VANE_VALID@6+1;TAT_VALID@7+1;HEATER_OK@8+1;BIT_PASS@9+1] |  | dimensionless |  | validity_word w2 b11 | AV25 |
| AD.VALID.D | 1 | T | 3 | 27 |  | bitfield16 [PS_VALID@0+1;PT_VALID@1+1;DPA_VALID@2+1;DPB_VALID@3+1;AOA_VANE_L_VALID@4+1;AOA_VANE_R_VALID@5+1;AOSS_VANE_VALID@6+1;TAT_VALID@7+1;HEATER_OK@8+1;BIT_PASS@9+1] |  | dimensionless |  | validity_word w2 b10 | AV25 |
| AV.LRU.HEALTH.DFCC.LINK | 1 | T | 4 | 2 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b15 | AV12.5 |
| AV.LRU.HEALTH.DFCC.MEMORY | 1 | T | 4 | 3 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b14 | AV12.5 |
| AV.LRU.HEALTH.DFCC.PORT | 1 | T | 4 | 4 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b13 | AV12.5 |
| AV.LRU.HEALTH.DFCC.TEMP | 1 | T | 4 | 5 |  | bnr16 | 0.1 | degF | -67..257 | validity_word w1 b12 | AV12.5 |
| FCS.BIT.LOG | 1 | T | 4 | 6 |  | code_word16 |  | dimensionless |  | validity_word w1 b11 | AV12.5 |
| ENG.A8.V | 5 | T | 1 | 2 |  | bnr16 | 0.1 | percent | 0..100 | validity_word w1 b15 | AV25 |
| ENG.AB_LIT | 5 | T | 1 | 3 |  | bitfield16 [AB_FLAME_DETECTED@0+1] |  | dimensionless | 0..1 | validity_word w1 b14 | AV25 |
| ENG.CVG | 5 | T | 1 | 4 |  | bnr16 | 0.1 | deg | -5..55 | validity_word w1 b13 | AV25 |
| ENG.FVG | 5 | T | 1 | 5 |  | bnr16 | 0.1 | deg | 0..55 | validity_word w1 b12 | AV25 |
| ENG.N1.V | 5 | T | 1 | 6 |  | bnr16 | 0.03125 | percent | 0..115 | validity_word w1 b11 | AV25 |
| ENG.N2.V | 5 | T | 1 | 7 |  | bnr16 | 0.03125 | percent | 0..110 | validity_word w1 b10 | AV25 |
| ENG.P5 | 5 | T | 1 | 8 |  | bnr16 | 0.06 | psi | 0..60 | validity_word w1 b9 | AV25 |
| ENG.PLA.V | 5 | T | 1 | 9 |  | bnr16 | 0.088 | deg | 0..130 | validity_word w1 b8 | AV25 |
| ENG.PS3.V | 5 | T | 1 | 10 |  | bnr16 | 0.5 | psi | 0..500 | validity_word w1 b7 | AV25 |
| ENG.T1.V | 5 | T | 1 | 11 |  | bnr16 | 1.0 | degC | -54..149 | validity_word w1 b6 | AV25 |
| ENG.T5 | 5 | T | 1 | 12 |  | bnr16 | 0.5 | degC | 371..871 | validity_word w1 b5 | AV25 |
| ENG.WFM | 5 | T | 1 | 13 |  | bnr16 | 8 | lb/hr | 0..12000 | validity_word w1 b4 | AV25 |
| AV.LRU.HEALTH.FADEC.LINK | 5 | T | 2 | 2 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b15 | AV12.5 |
| AV.LRU.HEALTH.FADEC.MEMORY | 5 | T | 2 | 3 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b14 | AV12.5 |
| AV.LRU.HEALTH.FADEC.PORT | 5 | T | 2 | 4 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b13 | AV12.5 |
| AV.LRU.HEALTH.FADEC.TEMP | 5 | T | 2 | 5 |  | bnr16 | 0.1 | degF | -67..257 | validity_word w1 b12 | AV12.5 |
| ENG.BLEED_STATE | 5 | T | 2 | 6 |  | bitfield16 [BLEED_OFF@0+1;BLEED_DOOR_OPEN@1+1;ANTI_ICE_VALVE_OPEN@2+1] |  | dimensionless |  | validity_word w1 b11 | AV12.5 |
| ENG.CHIP | 5 | T | 2 | 7 |  | bitfield16 [CHIP_DETECTED@0+1] |  | dimensionless |  | validity_word w1 b10 | AV12.5 |
| ENG.FADEC_STATUS | 5 | T | 2 | 8 |  | bitfield16 [CH_A_IN_CONTROL@0+1;CH_B_IN_CONTROL@1+1;CH_A_FAIL@2+1;CH_B_FAIL@3+1;SENSOR_SUBSTITUTION_ACTIVE@4+1] |  | dimensionless |  | validity_word w1 b9 | AV12.5 |
| ENG.FAULT_CODES | 5 | T | 2 | 9 |  | code_word16 |  | dimensionless |  | validity_word w1 b8 | AV12.5 |
| ENG.FLAMEOUT | 5 | T | 2 | 10 |  | bitfield16 [FLAMEOUT_DETECTED@0+1;AUTO_RELIGHT_ACTIVE@1+1] |  | dimensionless |  | validity_word w1 b7 | AV12.5 |
| ENG.IGN | 5 | T | 2 | 11 |  | bitfield16 [IGNITION_ON@0+1] |  | dimensionless |  | validity_word w1 b6 | AV12.5 |
| ENG.LIMIT_FLAGS | 5 | T | 2 | 12 |  | bitfield16 [N1_OVERSPEED@0+1;N2_OVERSPEED@1+1;T5_OVERTEMP@2+1;OIL_PRESSURE_LOW@3+1;VIBRATION_HIGH@4+1] |  | dimensionless |  | validity_word w1 b5 | AV12.5 |
| ENG.LUBE_DP | 5 | T | 2 | 13 |  | bitfield16 [LUBE_FILTER_DP_HIGH@0+1] |  | dimensionless |  | validity_word w1 b4 | AV12.5 |
| ENG.OIL_LEVEL | 5 | T | 2 | 14 |  | bitfield16 [OIL_LEVEL_LOW@0+1] |  | dimensionless |  | validity_word w1 b3 | AV12.5 |
| ENG.OIL_P | 5 | T | 2 | 15 |  | bnr16 | 2.442 | psi | 0..200 | validity_word w1 b2 | AV12.5 |
| ENG.FUEL_INLET_T | 5 | T | 3 | 2 |  | bnr16 | 0.5 | degC | -40..120 | validity_word w1 b15 | AV6.25 |
| ENG.OIL_T | 5 | T | 3 | 3 |  | bnr16 | 1.343 | degC | -54..180 | validity_word w1 b14 | AV6.25 |
| ENG.VIB.N1_1REV | 5 | T | 4 | 2 |  | bnr16 | 0.03125 | in/s | 0..5 | validity_word w1 b15 | SLOW1 |
| ENG.VIB.N2_1REV | 5 | T | 4 | 3 |  | bnr16 | 0.03125 | in/s | 0..5 | validity_word w1 b14 | SLOW1 |
| ENG.VIB.OVERALL | 5 | T | 4 | 4 |  | bnr16 | 0.03125 | in/s | 0..5 | validity_word w1 b13 | SLOW1 |
| BRK.PEDAL.L | 7 | T | 1 | 2 |  | ubnr16 | 0.001953125 | percent | 0..100 | validity_word w1 b15 | AV25 |
| BRK.PEDAL.R | 7 | T | 1 | 3 |  | ubnr16 | 0.001953125 | percent | 0..100 | validity_word w1 b14 | AV25 |
| BRK.PRESS.L | 7 | T | 1 | 4 |  | ubnr16 | 0.00390625 | bar | 0..200 | validity_word w1 b13 | AV25 |
| BRK.PRESS.R | 7 | T | 1 | 5 |  | ubnr16 | 0.00390625 | bar | 0..200 | validity_word w1 b12 | AV25 |
| BRK.WHEEL_SPEED.FLAGS | 7 | T | 1 | 6 |  | bitfield16 [SKID_VALVE_L@0+1;SKID_VALVE_R@1+1;ANTISKID_FAIL@2+1] |  | dimensionless |  | validity_word w1 b11 | AV25 |
| BRK.WHEEL_SPEED.SPEED_L | 7 | T | 1 | 7 |  | ubnr16 | 0.0625 | rpm | 0..3500 | validity_word w1 b10 | AV25 |
| BRK.WHEEL_SPEED.SPEED_R | 7 | T | 1 | 8 |  | ubnr16 | 0.0625 | rpm | 0..3500 | validity_word w1 b9 | AV25 |
| HYD.SYS1.P | 7 | T | 1 | 9 |  | bnr16 | 0.5 | bar | 0..350 | validity_word w1 b8 | AV25 |
| HYD.SYS2.P | 7 | T | 1 | 10 |  | bnr16 | 0.5 | bar | 0..350 | validity_word w1 b7 | AV25 |
| NWS.STATE.FEEDBACK_POT | 7 | T | 1 | 11 |  | bnr16 | 0.00390625 | deg | -75..75 | validity_word w1 b6 | AV25 |
| NWS.STATE.FLAGS | 7 | T | 1 | 12 |  | bitfield16 [FREE_CASTOR@0+1;NWS_FAIL@1+1] |  | dimensionless |  | validity_word w1 b5 | AV25 |
| NWS.STATE.INPUT_POT | 7 | T | 1 | 13 |  | bnr16 | 0.00390625 | deg | -75..75 | validity_word w1 b4 | AV25 |
| AV.LRU.HEALTH.BHEEM_EU.LINK | 7 | T | 2 | 2 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b15 | AV12.5 |
| AV.LRU.HEALTH.BHEEM_EU.MEMORY | 7 | T | 2 | 3 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b14 | AV12.5 |
| AV.LRU.HEALTH.BHEEM_EU.PORT | 7 | T | 2 | 4 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b13 | AV12.5 |
| AV.LRU.HEALTH.BHEEM_EU.TEMP | 7 | T | 2 | 5 |  | bnr16 | 0.1 | degF | -67..257 | validity_word w1 b12 | AV12.5 |
| CHUTE.STATE | 7 | T | 2 | 6 |  | bitfield16 [CHUTE_DEPLOYED@0+1;CHUTE_JETTISONED@1+1;CHUTE_UNSAFE@2+1] |  | dimensionless |  | validity_word w1 b11 | AV12.5 |
| ELEC.GEN.OUT | 7 | T | 2 | 7 |  | bitfield16 [GENERATOR_OFFLINE@0+1] |  | dimensionless |  | validity_word w1 b10 | AV12.5 |
| FIRE.WARN | 7 | T | 2 | 8 |  | bitfield16 [ENGINE_BAY_FIRE@0+1;ENGINE_BAY_OVERHEAT@1+1;EXTINGUISHER_FIRED@2+1;EXTINGUISHER_LOW@3+1] |  | dimensionless |  | validity_word w1 b9 | AV12.5 |
| HYD.FILTER_DP | 7 | T | 2 | 9 |  | bitfield16 [FILTER_1_CLOGGED@0+1;FILTER_2_CLOGGED@1+1;FILTER_3_CLOGGED@2+1;FILTER_4_CLOGGED@3+1;FILTER_5_CLOGGED@4+1;FILTER_6_CLOGGED@5+1;FILTER_7_CLOGGED@6+1;FILTER_8_CLOGGED@7+1;FILTER_9_CLOGGED@8+1] |  | dimensionless |  | validity_word w1 b8 | AV12.5 |
| HYD.SYS1.LP | 7 | T | 2 | 10 |  | bitfield16 [LOW_PRESSURE@0+1] |  | dimensionless |  | validity_word w1 b7 | AV12.5 |
| HYD.SYS2.LP | 7 | T | 2 | 11 |  | bitfield16 [LOW_PRESSURE@0+1] |  | dimensionless |  | validity_word w1 b6 | AV12.5 |
| LG.POSITION | 7 | T | 2 | 12 |  | bitfield16 [NOSE_UPLOCKED@0+1;NOSE_DOWNLOCKED@1+1;LEFT_UPLOCKED@2+1;LEFT_DOWNLOCKED@3+1;RIGHT_UPLOCKED@4+1;RIGHT_DOWNLOCKED@5+1;HANDLE_DOWN@6+1;DOORS_CLOSED@7+1] |  | dimensionless |  | validity_word w1 b5 | AV12.5 |
| SPS.AMAGB.OIL_LOW | 7 | T | 2 | 13 |  | bitfield16 [OIL_LEVEL_LOW@0+1;CHIP_DETECTED@1+1] |  | dimensionless |  | validity_word w1 b4 | AV12.5 |
| SPS.AMAGB.SPEED | 7 | T | 2 | 14 |  | bnr16 | 10 | rpm | 0..17500 | validity_word w1 b3 | AV12.5 |
| SPS.JFS.EGT | 7 | T | 2 | 15 |  | ubnr16 | 0.015625 | degC | 0..1000 | validity_word w1 b2 | AV12.5 |
| SPS.JFS.SPEED | 7 | T | 2 | 16 |  | ubnr16 | 0.001953125 | percent | 0..110 | validity_word w1 b1 | AV12.5 |
| ELEC.BACKUP.STATUS.BITE | 7 | T | 3 | 3 |  | bitfield16 [BITE_FAIL@0+1;GENERATOR_ONLINE@1+1] |  | dimensionless |  | validity_word w1 b15 | AV6.25 |
| ELEC.BACKUP.STATUS.CURR | 7 | T | 3 | 4 |  | ubnr16 | 0.00390625 | A | 0..180 | validity_word w1 b14 | AV6.25 |
| ELEC.BACKUP.STATUS.VOLT | 7 | T | 3 | 5 |  | ubnr16 | 0.0009765625 | V | 0..42 | validity_word w1 b13 | AV6.25 |
| ELEC.DCBUS.V.EMERGENCY | 7 | T | 3 | 6 |  | bnr16 | 0.05 | V | 0..43.5 | validity_word w1 b12 | AV6.25 |
| ELEC.DCBUS.V.ESSENTIAL | 7 | T | 3 | 7 |  | bnr16 | 0.05 | V | 0..43.5 | validity_word w1 b11 | AV6.25 |
| ELEC.DCBUS.V.MAIN | 7 | T | 3 | 8 |  | bnr16 | 0.05 | V | 0..43.5 | validity_word w1 b10 | AV6.25 |
| ELEC.GEN.F | 7 | T | 3 | 9 |  | bnr16 | 0.1 | Hz | 0..610.5 | validity_word w1 b9 | AV6.25 |
| ELEC.GEN.I | 7 | T | 3 | 10 |  | bnr16 | 0.5 | A | 0..200 | validity_word w1 b8 | AV6.25 |
| ELEC.GEN.V.PH_A | 7 | T | 3 | 11 |  | bnr16 | 0.1 | V | 0..177 | validity_word w1 b7 | AV6.25 |
| ELEC.GEN.V.PH_B | 7 | T | 3 | 12 |  | bnr16 | 0.1 | V | 0..177 | validity_word w1 b6 | AV6.25 |
| ELEC.GEN.V.PH_C | 7 | T | 3 | 13 |  | bnr16 | 0.1 | V | 0..177 | validity_word w1 b5 | AV6.25 |
| ELEC.TRU.VI.TRU1.CURR | 7 | T | 3 | 14 |  | bnr16 | 1 | A | 0..250 | validity_word w1 b4 | AV6.25 |
| ELEC.TRU.VI.TRU1.VOLT | 7 | T | 3 | 15 |  | bnr16 | 0.1 | V | 0..43.5 | validity_word w1 b3 | AV6.25 |
| ELEC.TRU.VI.TRU2.CURR | 7 | T | 3 | 16 |  | bnr16 | 1 | A | 0..250 | validity_word w1 b2 | AV6.25 |
| ELEC.TRU.VI.TRU2.VOLT | 7 | T | 3 | 17 |  | bnr16 | 0.1 | V | 0..43.5 | validity_word w1 b1 | AV6.25 |
| HYD.SYS1.LEVEL.LEVEL | 7 | T | 3 | 18 |  | bnr16 | 0.5 | percent | 0..100 | validity_word w1 b0 | AV6.25 |
| HYD.SYS1.LEVEL.LOW | 7 | T | 3 | 19 |  | bitfield16 [LEVEL_LOW@0+1] |  | dimensionless |  | validity_word w2 b15 | AV6.25 |
| HYD.SYS1.T | 7 | T | 3 | 20 |  | bnr16 | 0.5 | degC | -54..135 | validity_word w2 b14 | AV6.25 |
| HYD.SYS2.LEVEL.LEVEL | 7 | T | 3 | 21 |  | bnr16 | 0.5 | percent | 0..100 | validity_word w2 b13 | AV6.25 |
| HYD.SYS2.LEVEL.LOW | 7 | T | 3 | 22 |  | bitfield16 [LEVEL_LOW@0+1] |  | dimensionless |  | validity_word w2 b12 | AV6.25 |
| HYD.SYS2.T | 7 | T | 3 | 23 |  | bnr16 | 0.5 | degC | -54..135 | validity_word w2 b11 | AV6.25 |
| ELEC.BATT.AH | 7 | T | 4 | 2 |  | bnr16 | 0.1 | A*hour | 0..45 | validity_word w1 b15 | SLOW1 |
| ELEC.BATT.CURR | 7 | T | 4 | 3 |  | bnr16 | 0.015625 | A | -400..400 | validity_word w1 b14 | SLOW1 |
| ELEC.BATT.LOW | 7 | T | 4 | 4 |  | bitfield16 [BATT_LOW@0+1] |  | dimensionless |  | validity_word w1 b13 | SLOW1 |
| ELEC.BATT.VOLT | 7 | T | 4 | 5 |  | ubnr16 | 0.0009765625 | V | 0..43.5 | validity_word w1 b12 | SLOW1 |
| SPS.AMAGB.OIL_T.HIGH | 7 | T | 4 | 6 |  | bitfield16 [OIL_TEMP_HIGH@0+1] |  | dimensionless |  | validity_word w1 b11 | SLOW1 |
| SPS.AMAGB.OIL_T.TEMP | 7 | T | 4 | 7 |  | bnr16 | 1 | degC | -54..150 | validity_word w1 b10 | SLOW1 |
| AV.LRU.HEALTH.ECFM_C.LINK | 8 | T | 1 | 3 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b15 | AV12.5 |
| AV.LRU.HEALTH.ECFM_C.MEMORY | 8 | T | 1 | 4 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b14 | AV12.5 |
| AV.LRU.HEALTH.ECFM_C.PORT | 8 | T | 1 | 5 |  | bitfield16 [LOCAL_FAILURE_CODE@0+8;EXTERNAL_FAILURE_CODE@8+8] |  | dimensionless |  | validity_word w1 b13 | AV12.5 |
| AV.LRU.HEALTH.ECFM_C.TEMP | 8 | T | 1 | 6 |  | bnr16 | 0.1 | degF | -67..257 | validity_word w1 b12 | AV12.5 |
| ECS.SWITCHES | 8 | T | 1 | 7 |  | bitfield16 [ECS_PRESSURE_HIGH@0+1;ECS_PRESSURE_LOW@1+1;HOT_AIR_LEAK@2+1] |  | dimensionless |  | validity_word w1 b11 | AV12.5 |
| FUEL.BOOST_P | 8 | T | 1 | 8 |  | bitfield16 [F2_PUMP_PRESSURE_LOW@0+1;F2_PUMP_RUNNING@1+1] |  | dimensionless |  | validity_word w1 b10 | AV12.5 |
| FUEL.QTY.TANK.DT_CL | 8 | T | 1 | 9 |  | bnr16 | 1 | kg | 0..2458 | validity_word w1 b9 | AV12.5 |
| FUEL.QTY.TANK.DT_IB_L | 8 | T | 1 | 10 |  | bnr16 | 1 | kg | 0..2458 | validity_word w1 b8 | AV12.5 |
| FUEL.QTY.TANK.DT_IB_R | 8 | T | 1 | 11 |  | bnr16 | 1 | kg | 0..2458 | validity_word w1 b7 | AV12.5 |
| FUEL.QTY.TANK.F1 | 8 | T | 1 | 12 |  | bnr16 | 1 | kg | 0..2458 | validity_word w1 b6 | AV12.5 |
| FUEL.QTY.TANK.F1A | 8 | T | 1 | 13 |  | bnr16 | 1 | kg | 0..2458 | validity_word w1 b5 | AV12.5 |
| FUEL.QTY.TANK.F2 | 8 | T | 1 | 14 |  | bnr16 | 1 | kg | 0..2458 | validity_word w1 b4 | AV12.5 |
| FUEL.QTY.TANK.WING_L | 8 | T | 1 | 15 |  | bnr16 | 1 | kg | 0..2458 | validity_word w1 b3 | AV12.5 |
| FUEL.QTY.TANK.WING_R | 8 | T | 1 | 16 |  | bnr16 | 1 | kg | 0..2458 | validity_word w1 b2 | AV12.5 |
| FUEL.REFUEL_EVT | 8 | T | 1 | 17 |  | bitfield16 [GROUND_REFUEL@0+1;AAR@1+1;HOT_REFUEL@2+1;FUEL_DUMP@3+1] |  | dimensionless |  | validity_word w1 b1 | AV12.5 |
| FUEL.TANK_PRESS.FLAGS | 8 | T | 1 | 18 |  | bitfield16 [DROP_TANKS_PRESSURISED@0+1;OVERPRESSURE@1+1] |  | dimensionless |  | validity_word w1 b0 | AV12.5 |
| FUEL.TANK_PRESS.PRESS | 8 | T | 1 | 19 |  | ubnr16 | 1.52587890625e-05 | bar | 0..0.75 | validity_word w2 b15 | AV12.5 |
| FUEL.TOTAL.FLAGS | 8 | T | 1 | 20 |  | bitfield16 [LOW_FUEL@0+1;BINGO@1+1] |  | dimensionless |  | validity_word w2 b14 | AV12.5 |
| FUEL.TOTAL.TOTAL | 8 | T | 1 | 21 |  | bnr16 | 1 | kg | 0..6000 | validity_word w2 b13 | AV12.5 |
| ECS.AVIONICS_T.HOT | 8 | T | 2 | 2 |  | bitfield16 [AVIONICS_HOT@0+1] |  | dimensionless |  | validity_word w1 b15 | AV6.25 |
| ECS.AVIONICS_T.TEMP | 8 | T | 2 | 3 |  | bnr16 | 0.0078125 | degC | -54..150 | validity_word w1 b14 | AV6.25 |
| ECS.BLEED_P | 8 | T | 2 | 4 |  | ubnr16 | 0.000244140625 | bar | 0..9.6 | validity_word w1 b13 | AV6.25 |
| ECS.BLEED_T.ACM_TURBINE_IN | 8 | T | 2 | 5 |  | bnr16 | 0.015625 | degC | -54..282 | validity_word w1 b12 | AV6.25 |
| ECS.BLEED_T.PHX_IN | 8 | T | 2 | 6 |  | bnr16 | 0.03125 | degC | -54..894 | validity_word w1 b11 | AV6.25 |
| ECS.BLEED_T.PHX_OUT | 8 | T | 2 | 7 |  | bnr16 | 0.015625 | degC | -54..282 | validity_word w1 b10 | AV6.25 |
| ECS.CABIN_P.CABIN_ALT | 8 | T | 2 | 8 |  | bnr16 | 2.0 | ft | -2000..60000 | validity_word w1 b9 | AV6.25 |
| ECS.CABIN_P.PRESS | 8 | T | 2 | 9 |  | ubnr16 | 0.00048828125 | psi | 0..16 | validity_word w1 b8 | AV6.25 |
| ECS.COCKPIT_T.ACM_OUT | 8 | T | 2 | 10 |  | bnr16 | 0.00390625 | degC | -55..100 | validity_word w1 b7 | AV6.25 |
| ECS.COCKPIT_T.COCKPIT | 8 | T | 2 | 11 |  | bnr16 | 0.00390625 | degC | -55..100 | validity_word w1 b6 | AV6.25 |
| ECS.COCKPIT_T.SUPPLY | 8 | T | 2 | 12 |  | bnr16 | 0.00390625 | degC | -55..100 | validity_word w1 b5 | AV6.25 |
| ECS.TCV | 8 | T | 2 | 13 |  | ubnr16 | 0.001953125 | deg | 0..90 | validity_word w1 b4 | AV6.25 |
| FUEL.TEMP | 8 | T | 2 | 14 |  | bnr16 | 0.00390625 | degC | -40..120 | validity_word w1 b3 | AV6.25 |
| LSS.LOX_QTY | 8 | T | 3 | 2 |  | ubnr16 | 0.0001220703125 | L | 0..5 | validity_word w1 b15 | SLOW1 |
| LSS.OBOGS.FAIL | 8 | T | 3 | 3 |  | bitfield16 [OBOGS_FAIL@0+1] |  | dimensionless |  | validity_word w1 b14 | SLOW1 |
| LSS.OBOGS.O2 | 8 | T | 3 | 4 |  | ubnr16 | 0.001953125 | percent | 0..100 | validity_word w1 b13 | SLOW1 |
| LSS.OBOGS.PRESS | 8 | T | 3 | 5 |  | ubnr16 | 0.0078125 | kPa | 0..500 | validity_word w1 b12 | SLOW1 |
| AV.1553.BUS_STATUS.AV-MUX-1 | 31 | R | 1 | 2 |  | bitfield16 [BUS_A_FAIL@0+1;BUS_B_FAIL@1+1;BUS_A_ACTIVE@2+1;BUS_B_ACTIVE@3+1;MESSAGE_ERROR_SEEN@4+1] |  | dimensionless |  | validity_word w1 b15 | AV12.5 |
| AV.1553.BUS_STATUS.AV-MUX-2 | 31 | R | 1 | 3 |  | bitfield16 [BUS_A_FAIL@0+1;BUS_B_FAIL@1+1;BUS_A_ACTIVE@2+1;BUS_B_ACTIVE@3+1;MESSAGE_ERROR_SEEN@4+1] |  | dimensionless |  | validity_word w1 b14 | AV12.5 |
| AV.1553.BUS_STATUS.WPN-MUX | 31 | R | 1 | 4 |  | bitfield16 [BUS_A_FAIL@0+1;BUS_B_FAIL@1+1;BUS_A_ACTIVE@2+1;BUS_B_ACTIVE@3+1;MESSAGE_ERROR_SEEN@4+1] |  | dimensionless |  | validity_word w1 b13 | AV12.5 |
| SYS.EVENT_MARKER | 31 | R | 1 | 5 |  | bitfield16 [PILOT_EVENT_MARK@0+1] |  | dimensionless |  | validity_word w1 b12 | AV12.5 |
| SYS.TIME.UTC | 31 | R | 2 | 2+1 |  | bnr32 | 0.001 | s | 0..86400 | validity_word w1 b15 | SLOW1 |

## mil1553_modecode AV-MUX-1

| Channel | RT | T/R | SA | Word(s) | Label | Encoding | LSB | Units | Range | Validity | Group |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AV.LRU.BIT.INGPS | 10 |  |  | 19 |  | bitfield16 [BIT_FAIL@0+1;PBIT_FAIL@1+1;CBIT_FAIL@2+1;IBIT_IN_PROGRESS@3+1] |  | dimensionless |  | rt_status | AV12.5 |
| AV.LRU.BIT.AHRS | 11 |  |  | 19 |  | bitfield16 [BIT_FAIL@0+1;PBIT_FAIL@1+1;CBIT_FAIL@2+1;IBIT_IN_PROGRESS@3+1] |  | dimensionless |  | rt_status | AV12.5 |
| AV.LRU.BIT.RADAR | 12 |  |  | 19 |  | bitfield16 [BIT_FAIL@0+1;PBIT_FAIL@1+1;CBIT_FAIL@2+1;IBIT_IN_PROGRESS@3+1] |  | dimensionless |  | rt_status | AV12.5 |
| AV.LRU.BIT.SMS | 13 |  |  | 19 |  | bitfield16 [BIT_FAIL@0+1;PBIT_FAIL@1+1;CBIT_FAIL@2+1;IBIT_IN_PROGRESS@3+1] |  | dimensionless |  | rt_status | AV12.5 |

## mil1553_modecode AV-MUX-2

| Channel | RT | T/R | SA | Word(s) | Label | Encoding | LSB | Units | Range | Validity | Group |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AV.LRU.BIT.DFCC | 1 |  |  | 19 |  | bitfield16 [BIT_FAIL@0+1;PBIT_FAIL@1+1;CBIT_FAIL@2+1;IBIT_IN_PROGRESS@3+1] |  | dimensionless |  | rt_status | AV12.5 |
| AV.LRU.BIT.FADEC | 5 |  |  | 19 |  | bitfield16 [BIT_FAIL@0+1;PBIT_FAIL@1+1;CBIT_FAIL@2+1;IBIT_IN_PROGRESS@3+1] |  | dimensionless |  | rt_status | AV12.5 |
| AV.LRU.BIT.BHEEM_EU | 7 |  |  | 19 |  | bitfield16 [BIT_FAIL@0+1;PBIT_FAIL@1+1;CBIT_FAIL@2+1;IBIT_IN_PROGRESS@3+1] |  | dimensionless |  | rt_status | AV12.5 |
| AV.LRU.BIT.ECFM_C | 8 |  |  | 19 |  | bitfield16 [BIT_FAIL@0+1;PBIT_FAIL@1+1;CBIT_FAIL@2+1;IBIT_IN_PROGRESS@3+1] |  | dimensionless |  | rt_status | AV12.5 |

## mil1553_status AV-MUX-1

| Channel | RT | T/R | SA | Word(s) | Label | Encoding | LSB | Units | Range | Validity | Group |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AV.RT.STATUS.INGPS | 10 |  |  |  |  | bitfield16 [TERMINAL_FLAG@0+1;DYNAMIC_BUS_CONTROL_ACCEPTANCE@1+1;SUBSYSTEM_FLAG@2+1;BUSY@3+1;BROADCAST_COMMAND_RECEIVED@4+1;SERVICE_REQUEST@8+1;INSTRUMENTATION@9+1;MESSAGE_ERROR@10+1;RT_ADDRESS_0@11+1;RT_ADDRESS_1@12+1;RT_ADDRESS_2@13+1;RT_ADDRESS_3@14+1;RT_ADDRESS_4@15+1] |  | dimensionless |  | rt_status | AV50 |
| AV.RT.STATUS.AHRS | 11 |  |  |  |  | bitfield16 [TERMINAL_FLAG@0+1;DYNAMIC_BUS_CONTROL_ACCEPTANCE@1+1;SUBSYSTEM_FLAG@2+1;BUSY@3+1;BROADCAST_COMMAND_RECEIVED@4+1;SERVICE_REQUEST@8+1;INSTRUMENTATION@9+1;MESSAGE_ERROR@10+1;RT_ADDRESS_0@11+1;RT_ADDRESS_1@12+1;RT_ADDRESS_2@13+1;RT_ADDRESS_3@14+1;RT_ADDRESS_4@15+1] |  | dimensionless |  | rt_status | AV50 |
| AV.RT.STATUS.RADAR | 12 |  |  |  |  | bitfield16 [TERMINAL_FLAG@0+1;DYNAMIC_BUS_CONTROL_ACCEPTANCE@1+1;SUBSYSTEM_FLAG@2+1;BUSY@3+1;BROADCAST_COMMAND_RECEIVED@4+1;SERVICE_REQUEST@8+1;INSTRUMENTATION@9+1;MESSAGE_ERROR@10+1;RT_ADDRESS_0@11+1;RT_ADDRESS_1@12+1;RT_ADDRESS_2@13+1;RT_ADDRESS_3@14+1;RT_ADDRESS_4@15+1] |  | dimensionless |  | rt_status | AV50 |
| AV.RT.STATUS.SMS | 13 |  |  |  |  | bitfield16 [TERMINAL_FLAG@0+1;DYNAMIC_BUS_CONTROL_ACCEPTANCE@1+1;SUBSYSTEM_FLAG@2+1;BUSY@3+1;BROADCAST_COMMAND_RECEIVED@4+1;SERVICE_REQUEST@8+1;INSTRUMENTATION@9+1;MESSAGE_ERROR@10+1;RT_ADDRESS_0@11+1;RT_ADDRESS_1@12+1;RT_ADDRESS_2@13+1;RT_ADDRESS_3@14+1;RT_ADDRESS_4@15+1] |  | dimensionless |  | rt_status | AV50 |

## mil1553_status AV-MUX-2

| Channel | RT | T/R | SA | Word(s) | Label | Encoding | LSB | Units | Range | Validity | Group |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AV.RT.STATUS.DFCC | 1 |  |  |  |  | bitfield16 [TERMINAL_FLAG@0+1;DYNAMIC_BUS_CONTROL_ACCEPTANCE@1+1;SUBSYSTEM_FLAG@2+1;BUSY@3+1;BROADCAST_COMMAND_RECEIVED@4+1;SERVICE_REQUEST@8+1;INSTRUMENTATION@9+1;MESSAGE_ERROR@10+1;RT_ADDRESS_0@11+1;RT_ADDRESS_1@12+1;RT_ADDRESS_2@13+1;RT_ADDRESS_3@14+1;RT_ADDRESS_4@15+1] |  | dimensionless |  | rt_status | AV50 |
| AV.RT.STATUS.FADEC | 5 |  |  |  |  | bitfield16 [TERMINAL_FLAG@0+1;DYNAMIC_BUS_CONTROL_ACCEPTANCE@1+1;SUBSYSTEM_FLAG@2+1;BUSY@3+1;BROADCAST_COMMAND_RECEIVED@4+1;SERVICE_REQUEST@8+1;INSTRUMENTATION@9+1;MESSAGE_ERROR@10+1;RT_ADDRESS_0@11+1;RT_ADDRESS_1@12+1;RT_ADDRESS_2@13+1;RT_ADDRESS_3@14+1;RT_ADDRESS_4@15+1] |  | dimensionless |  | rt_status | AV50 |
| AV.RT.STATUS.BHEEM_EU | 7 |  |  |  |  | bitfield16 [TERMINAL_FLAG@0+1;DYNAMIC_BUS_CONTROL_ACCEPTANCE@1+1;SUBSYSTEM_FLAG@2+1;BUSY@3+1;BROADCAST_COMMAND_RECEIVED@4+1;SERVICE_REQUEST@8+1;INSTRUMENTATION@9+1;MESSAGE_ERROR@10+1;RT_ADDRESS_0@11+1;RT_ADDRESS_1@12+1;RT_ADDRESS_2@13+1;RT_ADDRESS_3@14+1;RT_ADDRESS_4@15+1] |  | dimensionless |  | rt_status | AV50 |
| AV.RT.STATUS.ECFM_C | 8 |  |  |  |  | bitfield16 [TERMINAL_FLAG@0+1;DYNAMIC_BUS_CONTROL_ACCEPTANCE@1+1;SUBSYSTEM_FLAG@2+1;BUSY@3+1;BROADCAST_COMMAND_RECEIVED@4+1;SERVICE_REQUEST@8+1;INSTRUMENTATION@9+1;MESSAGE_ERROR@10+1;RT_ADDRESS_0@11+1;RT_ADDRESS_1@12+1;RT_ADDRESS_2@13+1;RT_ADDRESS_3@14+1;RT_ADDRESS_4@15+1] |  | dimensionless |  | rt_status | AV50 |
