"""Original, licence-free music bed for the film (numpy synthesis, deterministic).
94 BPM; D major / B minor palette; follows the act structure in edit/timing.json.
Writes edit/music/bed.wav (48 kHz stereo, 24-bit)."""
import json, sys
from pathlib import Path
import numpy as np
import soundfile as sf

R = Path(__file__).resolve().parent
# usage: make_music.py [timing.json] [music/bed.wav]   (v2: timing_v2.json music/bed_v2.wav — plan follows its "sections")
TIMING = sys.argv[1] if len(sys.argv) > 1 else "timing.json"
OUTF = sys.argv[2] if len(sys.argv) > 2 else "music/bed.wav"
T = json.loads((R / TIMING).read_text())
SR, BPM = 48000, 94.0
BEAT = 60 / BPM
DUR = T["total"] + 2.0
N = int(DUR * SR)
t = np.arange(N) / SR
rng = np.random.default_rng(26249)
S = {k: v["start"] for k, v in T["shots"].items()}

def hz(m): return 440.0 * 2 ** ((m - 69) / 12)
def env_ar(n, a, r):
    e = np.ones(n); A = int(a * SR); Rr = int(r * SR)
    if A: e[:A] = np.linspace(0, 1, A)
    if Rr: e[-Rr:] *= np.linspace(1, 0, Rr)
    return e
def lp(x, fc):
    a = np.exp(-2 * np.pi * fc / SR); y = np.empty_like(x); z = 0.0
    for i in range(len(x)): z = (1 - a) * x[i] + a * z; y[i] = z
    return y
def lp_fast(x, fc, k=2):
    # cascade of one-pole filters using cumulative trick on chunks (vectorised approx via FFT)
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    H = 1 / (1 + (f / fc) ** (2 * k)) ** .5
    return np.fft.irfft(X * H, len(x))

L = np.zeros(N); Rch = np.zeros(N)
def add(sig, start, pan=0.0, gain=1.0):
    i0 = int(start * SR); i1 = min(N, i0 + len(sig)); s = sig[: i1 - i0] * gain
    L[i0:i1] += s * np.sqrt(0.5 * (1 - pan)); Rch[i0:i1] += s * np.sqrt(0.5 * (1 + pan))

# chord progression (MIDI), 2 bars each: D(add9) – Bm7 – G(maj7) – A(sus)
CHORDS = [[50, 57, 62, 64, 66], [47, 54, 59, 62, 66], [43, 50, 59, 62, 66], [45, 52, 57, 62, 64]]
CHORDS_TENSE = [[47, 54, 59, 62], [43, 50, 55, 62], [45, 52, 57, 60], [42, 49, 54, 61]]
BAR = 4 * BEAT

def pad_note(m, dur, bright=900):
    n = int(dur * SR); tt = np.arange(n) / SR
    f = hz(m); sig = np.zeros(n)
    for k, (det, amp) in enumerate([(0, 1), (0.13, .7), (-0.11, .7), (12, .18), (7, .12)]):
        ff = f * 2 ** (det / 12) * (1 + 0.0015 * np.sin(2 * np.pi * (0.21 + 0.07 * k) * tt))
        ph = 2 * np.pi * np.cumsum(ff) / SR
        sig += amp * (np.sin(ph) + 0.22 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph))
    sig = lp_fast(sig, bright)
    return sig * env_ar(n, min(1.6, dur / 3), min(2.2, dur / 2.5)) / 6

def section(t0, t1, chords, bright, gain):
    tt = t0; i = 0
    while tt < t1 - 0.5:
        d = min(2 * BAR, t1 - tt) + 1.6
        for j, m in enumerate(chords[i % len(chords)]):
            add(pad_note(m, d, bright), tt, pan=(j - 2) * 0.22, gain=gain)
        tt += 2 * BAR; i += 1

def kick(gain=1.0):
    n = int(0.42 * SR); tt = np.arange(n) / SR
    f = 46 + 70 * np.exp(-tt * 28); ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-tt * 9) * gain
def pulse(t0, t1, gain, every=1):
    b = t0
    while b < t1: add(kick(), b, 0, gain); b += BEAT * every
def tick(gain):
    n = int(0.05 * SR); x = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 120)
    return lp_fast(x, 9000) - lp_fast(x, 4000) if n > 8 else x
def hats(t0, t1, gain):
    b = t0 + BEAT / 2
    while b < t1: add(tick(1), b, 0.3, gain); b += BEAT
def pluck(m, gain):
    n = int(0.9 * SR); tt = np.arange(n) / SR; f = hz(m)
    x = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt * 6.5)
    return x * gain * env_ar(n, 0.004, 0.05)
def arp(t0, t1, gain, chords):
    b = t0; i = 0
    pattern = [0, 2, 3, 4, 3, 2, 1, 2]
    while b < t1:
        c = chords[int((b - t0) // (2 * BAR)) % len(chords)]
        m = c[pattern[i % 8] % len(c)] + 12
        add(pluck(m, 1), b, 0.35 if i % 2 else -0.35, gain); b += BEAT / 2; i += 1

END = T["total"]
if "sections" in T:                                    # v2 cut: S13–S16, S25, S29, S32, S33A–D out; LinuxONE section in
    X = T["sections"]
    section(0, X["pain"], CHORDS, 1200, 0.9)                                   # promise
    section(X["pain"], X["solution"], CHORDS_TENSE, 700, 0.95)                 # pain
    pulse(S["S07"], X["solution"] - 0.5, 0.35, every=2)
    section(X["solution"], X["demo"], CHORDS, 1500, 0.85)                      # solution: groove builds from triage
    pulse(S["S17"], X["demo"], 0.42); hats(S["S18"], X["demo"], 0.05); arp(S["S18"], X["demo"], 0.10, CHORDS)
    section(X["demo"], X["proof"], CHORDS, 1300, 0.75)                         # demonstration
    pulse(X["demo"], X["proof"], 0.38); hats(X["demo"], X["proof"], 0.045); arp(X["demo"], X["proof"], 0.085, CHORDS)
    section(X["proof"], X["platform"], CHORDS, 1700, 0.82)                     # proof + audit
    pulse(X["proof"], X["platform"], 0.42); hats(X["proof"], X["platform"], 0.055); arp(X["proof"], X["platform"], 0.10, CHORDS)
    LX = X["platform"]                                                          # LinuxONE + result: riser, full groove
    section(LX, X["close"], CHORDS, 2100, 0.85)
    pulse(LX, X["close"], 0.48); hats(LX, X["close"], 0.07); arp(LX, X["close"], 0.13, CHORDS)
    rise_n = int(2.2 * SR); tt = np.arange(rise_n) / SR
    riser = rng.standard_normal(rise_n) * (tt / 2.2) ** 2.2
    riser = lp_fast(riser, 6000) - lp_fast(riser, 900)
    add(riser * 0.22, LX - 2.2, 0, 1.0)
    add(kick(1.3), LX, 0, 0.7)
    for j, m in enumerate([38, 50, 57, 62, 66, 69]):
        add(pad_note(m, END - X["close"] + 2.0, 2200), X["close"], pan=(j - 2.5) * 0.2, gain=1.0)
    add(kick(1.2), X["close"], 0, 0.6)
    PLAN_DONE = True
else:
    PLAN_DONE = False
if not PLAN_DONE:                                      # v1 plan (acts in timing.json)
    A1, A2, A3, A4, A5 = [a["start"] for a in T["acts"]]
    # Act 0: promise — airy D major pad
    section(0, S["S05"], CHORDS, 1200, 0.9)
    # Act 1: pain — tense minor colour, darker filter, sparse pulse from S07
    section(S["S05"], A2, CHORDS_TENSE, 700, 0.95)
    pulse(S["S07"], A2 - 0.5, 0.35, every=2)
    # Act 2: solution — brighter, building pulse + hats from S13, arp from S16
    section(A2, A3, CHORDS, 1500, 0.85)
    pulse(S["S13"], A3, 0.42); hats(S["S16"], A3, 0.05); arp(S["S16"], A3, 0.10, CHORDS)
    # Act 3a: demonstration — steady groove, gentle arp
    section(A3, A4, CHORDS, 1300, 0.75)
    pulse(A3, A4, 0.38); hats(A3, A4, 0.045); arp(A3, A4, 0.085, CHORDS)
    # Act 3b: proof + audit — lift at S28
    section(A4, A5, CHORDS, 1700, 0.82)
    pulse(A4, A5, 0.42); hats(S["S28"], A5, 0.055); arp(A4, A5, 0.10, CHORDS)
    # Act 4: the assistant — sparse on the pain beat, riser into "you just ask", full groove under the answer
    section(A5, S["S35"], CHORDS, 2100, 0.85)
    pulse(S["S33B"], S["S35"], 0.48); hats(S["S33B"], S["S35"], 0.07); arp(S["S33B"], S["S35"], 0.13, CHORDS)
    rise_n = int(2.2 * SR); tt = np.arange(rise_n) / SR
    riser = rng.standard_normal(rise_n) * (tt / 2.2) ** 2.2
    riser = lp_fast(riser, 6000) - lp_fast(riser, 900)
    add(riser * 0.22, S["S33B"] - 2.2, 0, 1.0)
    add(kick(1.3), S["S33B"], 0, 0.7)
    for j, m in enumerate([38, 50, 57, 62, 66, 69]):
        add(pad_note(m, END - S["S35"] + 2.0, 2200), S["S35"], pan=(j - 2.5) * 0.2, gain=1.0)
    add(kick(1.2), S["S35"], 0, 0.6)

# stereo room: short cross-delay
d = int(0.017 * SR); L[d:] += 0.18 * Rch[:-d]; Rch[d:] += 0.18 * L[:-d]
mix = np.stack([L, Rch], 1)
mix *= env_ar(N, 1.5, 2.5)[:, None]
mix /= np.max(np.abs(mix)) * 1.12
out = R / OUTF; out.parent.mkdir(exist_ok=True)
sf.write(out, mix, SR, subtype="PCM_24")
print(out, round(DUR, 2))
