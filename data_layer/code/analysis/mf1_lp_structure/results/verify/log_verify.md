# MF1-D verification on 5 CAL flights (order[:5])

n = 5: verification stage of PREREGISTRATION.md section 7 (formats, segments, B1 sanity, spectra).

## V1 formats

| Flight | samples | rates OK | finite | airborne frac | ATEN values |
|---|---|---|---|---|---|
| 687200107202208.mat | 20688 | True | True | 0.918 | [0, 1] |
| 687200105031623.mat | 21856 | True | True | 0.942 | [0, 1] |
| 687200108150546.mat | 19056 | True | True | 0.811 | [0, 1] |
| 687200107181544.mat | 16960 | True | True | 0.938 | [0, 1] |
| 687200107210730.mat | 21088 | True | True | 0.931 | [0, 1] |

**V1: PASS**

## V2 segments (samples / K / included)

| Flight | ALL | AT | MAN | CLB | CRZ | DES | FLT | TAXI | AT_FLT | MAN_FLT |
|---|---|---|---|---|---|---|---|---|---|---|
| 687200107202208.mat | 18994/70/y | 17000/65/y | 1994/4/n | 6116/22/y | 6152/21/y | 5212/18/y | 17480/67/y | 1290/1/n | 16704/64/y | 776/2/n |
| 687200105031623.mat | 20588/75/y | 16916/65/y | 3672/7/y | 5960/22/y | 6352/21/y | 4996/15/y | 17308/66/y | 3068/5/n | 16656/64/y | 652/1/n |
| 687200108150546.mat | 15458/53/y | 13171/50/y | 2287/1/n | 3376/10/y | 4484/13/y | 5248/17/y | 13108/50/y | 2206/1/n | 12884/49/y | 224/0/n |
| 687200107181544.mat | 15902/60/y | 11428/43/y | 4474/13/y | 4772/17/y | 3032/8/y | 4660/15/y | 12464/47/y | 3190/9/y | 11148/42/y | 1316/4/n |
| 687200107210730.mat | 19641/70/y | 14842/56/y | 4799/12/y | 5120/19/y | 5908/17/y | 4276/10/y | 15304/58/y | 4137/9/y | 14524/55/y | 780/2/n |

PH composition of the ALL (airborne-rule) and MAN classes (PH 2 taxi, 3 take-off, 4 climb, 5 cruise, 6 approach, 7 rollout):

- 687200107202208.mat: ALL {'2': 1290, '3': 132, '4': 6116, '5': 6152, '6': 5212, '7': 92}; MAN {'2': 1126, '6': 776, '7': 92}; airborne samples outside Welch segments 818 ({'2': 818})
- 687200105031623.mat: ALL {'2': 3068, '3': 144, '4': 5960, '5': 6352, '6': 4996, '7': 68}; MAN {'2': 2952, '6': 652, '7': 68}; airborne samples outside Welch segments 876 ({'2': 876})
- 687200108150546.mat: ALL {'2': 2206, '3': 112, '4': 3376, '5': 4484, '6': 5248, '7': 32}; MAN {'2': 2031, '6': 224, '7': 32}; airborne samples outside Welch segments 1378 ({'2': 1378})
- 687200107181544.mat: ALL {'2': 3190, '3': 124, '4': 4772, '5': 3032, '6': 4660, '7': 124}; MAN {'2': 3034, '6': 1316, '7': 124}; airborne samples outside Welch segments 30 ({'2': 30})
- 687200107210730.mat: ALL {'2': 4137, '3': 116, '4': 5120, '5': 5908, '6': 4276, '7': 84}; MAN {'2': 3935, '6': 780, '7': 84}; airborne samples outside Welch segments 1209 ({'2': 1209})

## V3 B1 sanity (5-flight medians vs published 51-flight CAL fold-0 medians; tolerance 0.10)

| Engine | Pair | median r_B1 (n=5) | fold-0 | diff | within 0.10 |
|---|---|---|---|---|---|
| 1 | N1-N2 | 0.462 | 0.438 | +0.024 | True |
| 1 | N1-FF | 0.662 | 0.628 | +0.034 | True |
| 1 | N2-FF | 0.620 | 0.577 | +0.043 | True |
| 1 | N1-EGT | 0.572 | 0.571 | +0.001 | True |
| 1 | N2-EGT | 0.101 | 0.077 | +0.024 | True |
| 1 | FF-EGT | 0.319 | 0.319 | -0.000 | True |
| 2 | N1-N2 | 0.441 | 0.439 | +0.002 | True |
| 2 | N1-FF | 0.659 | 0.642 | +0.017 | True |
| 2 | N2-FF | 0.741 | 0.695 | +0.046 | True |
| 2 | N1-EGT | 0.569 | 0.565 | +0.004 | True |
| 2 | N2-EGT | 0.107 | 0.043 | +0.064 | True |
| 2 | FF-EGT | 0.287 | 0.263 | +0.024 | True |

r_B1 (battery `b1_stats`) equals this pipeline's time-domain fast-band r on the same samples to < 1e-12 for every flight and pair: **True**.

**V3: PASS**

## V4 spectral reconstruction (median over flights of |r_spec - r_B1|; tolerance 0.03)

| Engine | Pair | median abs(r_spec - r_B1) | median abs(r_spec - r_seg) | max abs(r_spec - r_B1) |
|---|---|---|---|---|
| 1 | N1-N2 | 0.007 | 0.015 | 0.032 |
| 1 | N1-FF | 0.010 | 0.012 | 0.025 |
| 1 | N2-FF | 0.019 | 0.013 | 0.130 |
| 1 | N1-EGT | 0.019 | 0.019 | 0.086 |
| 1 | N2-EGT | 0.055 | 0.017 | 0.082 |
| 1 | FF-EGT | 0.022 | 0.017 | 0.111 |
| 2 | N1-N2 | 0.035 | 0.010 | 0.105 |
| 2 | N1-FF | 0.007 | 0.004 | 0.017 |
| 2 | N2-FF | 0.017 | 0.021 | 0.093 |
| 2 | N1-EGT | 0.018 | 0.018 | 0.075 |
| 2 | N2-EGT | 0.027 | 0.021 | 0.134 |
| 2 | FF-EGT | 0.013 | 0.010 | 0.110 |

r_seg = time-domain r on exactly the samples covered by the Welch segments. Differences between r_B1 and r_seg come only from airborne-rule samples outside the segments (all PH 2 taxi at the 25 % N1 threshold, see V2).

**V4: FAIL (see text)**

## V5 spectra

- `spectra_687200107202208.svg`
- `spectra_687200105031623.svg`
- `spectra_687200108150546.svg`
- `spectra_687200107181544.svg`
- `spectra_687200107210730.svg`

## V6 self-test: PASS (`results/log_selftest.txt`)

## Primary cell on the 5 flights (engine 1, ALL, N1-N2; development look, no verdict)

- CF_N1: [0.697, 0.704, 0.724, 0.725, 0.652] (SD 0.030)
- CF_N2: [0.696, 0.713, 0.731, 0.73, 0.667] (SD 0.027)
- s_dyn: [0.921, 0.925, 0.876, 0.886, 0.843] (SD 0.034)

n rule start: sigma_max = 0.0339, n_pred = 2.8 -> n1 = 20.

