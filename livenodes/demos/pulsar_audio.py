"""A seamless 8-bar loop at 124 BPM, synthesised with numpy (no samples, no filters
that need per-sample Python loops). Am - F - C - G, two bars each."""
import numpy as np

RATE = 44100
BPM = 124.0
BARS = 8
BEAT = 60.0 / BPM
LENGTH = BARS * 4 * BEAT

# chord roots and voicings (MIDI notes), two bars per chord
PROGRESSION = [
    (45, (57, 60, 64, 69)),   # A minor
    (41, (57, 60, 65, 69)),   # F major
    (48, (55, 60, 64, 67)),   # C major
    (43, (55, 59, 62, 67)),   # G major
]


def hz(note):
    return 440.0 * 2.0 ** ((note - 69) / 12.0)


def _place(out, sig, start):
    """Mix `sig` into `out` at sample `start`, wrapping the tail to the loop start."""
    n = len(out)
    start %= n
    end = start + len(sig)
    if end <= n:
        out[start:end] += sig
    else:
        cut = n - start
        out[start:] += sig[:cut]
        out[:len(sig) - cut] += sig[cut:]


def _kick(rng):
    t = np.arange(int(0.45 * RATE)) / RATE
    freq = 46.0 + 110.0 * np.exp(-t * 32.0)
    phase = 2 * np.pi * np.cumsum(freq) / RATE
    body = np.sin(phase) * np.exp(-t * 6.5)
    click = rng.standard_normal(len(t)) * np.exp(-t * 400.0) * 0.25
    return np.tanh((body + click) * 1.6)


def _noise_burst(rng, dur, decay, colour):
    """Shaped noise: colour > 0 brighter (differentiated), < 0 darker (integrated)."""
    n = int(dur * RATE)
    x = rng.standard_normal(n + abs(colour) + 1)
    for _ in range(abs(colour)):
        x = np.diff(x) if colour > 0 else np.cumsum(x) * 0.05
    x = x[:n]
    x /= np.abs(x).max() + 1e-9
    t = np.arange(n) / RATE
    return x * np.exp(-t * decay)


def _clap(rng):
    a = _noise_burst(rng, 0.25, 22.0, 1)
    out = np.zeros(len(a) + int(0.02 * RATE))
    for k, g in ((0, 0.6), (int(0.008 * RATE), 0.5), (int(0.017 * RATE), 1.0)):  # flam
        out[k:k + len(a)] += a * g
    return out * 0.5


def _saw(freq, t, harmonics, bright):
    """Band-limited saw by additive synthesis; `bright` (array or float) shapes the rolloff."""
    s = np.zeros_like(t)
    for k in range(1, harmonics + 1):
        if freq * k > RATE * 0.45:
            break
        s += np.sin(2 * np.pi * freq * k * t) / k * np.exp(-(k - 1) / np.maximum(bright, 1e-3))
    return s


def render(seed=7):
    rng = np.random.default_rng(seed)
    n = int(round(LENGTH * RATE))
    kick, clap, hats, bass, pad, arp = (np.zeros(n) for _ in range(6))
    beats = BARS * 4
    kick_snd, clap_snd = _kick(rng), _clap(rng)
    t_all = np.arange(n) / RATE
    since_beat = (t_all % BEAT)
    duck = 1.0 - 0.75 * np.exp(-since_beat * 9.0)  # sidechain pump

    for b in range(beats):
        s = int(b * BEAT * RATE)
        _place(kick, kick_snd, s)
        if b % 4 in (1, 3):
            _place(clap, clap_snd, s)
        _place(hats, _noise_burst(rng, 0.12, 28.0, 3) * 0.55, s + int(BEAT * 0.5 * RATE))   # offbeat open hat
        if b >= 16:  # second half: 16th closed hats
            for q in (0.25, 0.75):
                _place(hats, _noise_burst(rng, 0.04, 90.0, 3) * 0.25, s + int(BEAT * q * RATE))

    for bar in range(BARS):
        root, chord = PROGRESSION[bar // 2]
        bar_start = bar * 4 * BEAT
        # bass on the offbeat eighths, with a closing filter per note
        for e in range(8):
            if e % 2 == 0:
                continue
            start = bar_start + e * BEAT * 0.5
            dur = BEAT * 0.45
            t = np.arange(int(dur * RATE)) / RATE
            env = np.minimum(t / 0.004, 1.0) * np.exp(-t * 5.0)
            note = root + (12 if e == 7 and bar % 2 else 0)
            sig = _saw(hz(note), t, 24, 2.0 + 10.0 * np.exp(-t * 18.0)) * env
            _place(bass, sig * 0.55, int(start * RATE))
        # pad: the whole bar, detuned voices
        if bar % 2 == 0:
            dur = 8 * BEAT
            t = np.arange(int(dur * RATE)) / RATE
            env = np.minimum(t / 0.6, 1.0) * np.minimum((dur - t) / 0.8, 1.0)
            sig = np.zeros_like(t)
            for note in chord:
                for det in (-0.09, 0.0, 0.11):
                    sig += _saw(hz(note + det), t + rng.uniform(0, 0.01), 10, 2.5)
            _place(pad, sig * env * 0.06, int(bar_start * RATE))
        # arpeggio in the second half: 16ths through the chord, an octave up
        if bar >= 4:
            pattern = [0, 1, 2, 3, 2, 1, 3, 2]
            for k in range(16):
                note = chord[pattern[k % 8]] + 12
                start = bar_start + k * BEAT * 0.25
                t = np.arange(int(0.22 * RATE)) / RATE
                env = np.minimum(t / 0.002, 1.0) * np.exp(-t * 16.0)
                tone = np.sin(2 * np.pi * hz(note) * t) + 0.35 * np.sin(4 * np.pi * hz(note) * t)
                gain = 0.10 * (0.6 + 0.4 * (k % 4 == 0))
                _place(arp, tone * env * gain, int(start * RATE))
                _place(arp, tone * env * gain * 0.35, int((start + BEAT * 0.75) * RATE))  # dotted echo

    mix = kick * 0.9 + clap * 0.35 + hats * 0.22 + (bass * 0.8 + pad + arp * 0.8) * duck
    mix = np.tanh(mix * 1.1)
    mix *= 0.89 / (np.abs(mix).max() + 1e-9)  # about -1 dBFS
    return mix.astype(np.float32)


def write(path, seed=7):
    import aud
    data = render(seed).reshape(-1, 1)
    aud.Sound.buffer(data, float(RATE)).write(path, rate=RATE, channels=1)
    return path
