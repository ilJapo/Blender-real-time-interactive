"""CHOP data: an ordered set of named channels sharing one sample count."""
import fnmatch

import numpy as np


class Channels:
    """`data` is a float32 array shaped (channels, samples).

    A control signal is one sample per channel; audio, spectra and trails
    carry many samples. `rate` is the sample rate of the sample axis.
    """

    __slots__ = ("names", "data", "rate")

    def __init__(self, names=(), data=None, rate=60.0):
        self.names = list(names)
        if data is None:
            data = np.zeros((len(self.names), 1), dtype=np.float32)
        data = np.asarray(data, dtype=np.float32)
        if data.ndim == 1:
            data = data.reshape(len(self.names), -1) if self.names else data.reshape(0, 1)
        self.data = data
        self.rate = float(rate)

    # -- construction -----------------------------------------------------
    @classmethod
    def empty(cls):
        return cls((), np.zeros((0, 1), dtype=np.float32))

    @classmethod
    def from_dict(cls, values, rate=60.0):
        names = [str(k) for k in values]
        rows = [np.atleast_1d(np.asarray(v, dtype=np.float32)).ravel() for v in values.values()]
        n = max((len(r) for r in rows), default=1) or 1
        data = np.zeros((len(rows), n), dtype=np.float32)
        for i, r in enumerate(rows):
            if len(r) == n:
                data[i] = r
            elif len(r) == 1:
                data[i] = r[0]
            elif len(r):
                data[i] = np.interp(np.linspace(0, len(r) - 1, n), np.arange(len(r)), r)
        return cls(names, data, rate)

    # -- queries ----------------------------------------------------------
    @property
    def num_channels(self):
        return self.data.shape[0]

    @property
    def num_samples(self):
        return self.data.shape[1]

    def __len__(self):
        return self.data.shape[0]

    def __bool__(self):
        return self.data.shape[0] > 0

    def index(self, name):
        try:
            return self.names.index(name)
        except ValueError:
            return -1

    def chan(self, name):
        i = self.index(name)
        return self.data[i] if i >= 0 else None

    def get(self, name, default=0.0):
        i = self.index(name)
        return float(self.data[i, 0]) if i >= 0 else default

    def first(self, default=0.0):
        return float(self.data[0, 0]) if self.data.size else default

    def pick(self, name="", default=0.0):
        """Value of `name`, or of the first channel when `name` is empty."""
        return self.get(name, default) if name else self.first(default)

    def to_dict(self):
        return {n: float(d[0]) for n, d in zip(self.names, self.data)}

    def match(self, pattern):
        """Indices of channels matching a space separated list of glob patterns."""
        pats = pattern.split()
        if not pats:
            return list(range(len(self.names)))
        return [i for i, n in enumerate(self.names) if any(fnmatch.fnmatchcase(n, p) for p in pats)]

    # -- derivation -------------------------------------------------------
    def replace(self, data, names=None, rate=None):
        return Channels(self.names if names is None else names, data, self.rate if rate is None else rate)

    def select(self, indices):
        return Channels([self.names[i] for i in indices], self.data[indices], self.rate)

    def __repr__(self):
        return f"<Channels {self.num_channels}x{self.num_samples} {self.names[:6]}>"


def resample(data, n):
    """Linear resample of the sample axis to `n` samples."""
    if data.shape[1] == n:
        return data
    if data.shape[1] == 1:
        return np.repeat(data, n, axis=1)
    x = np.linspace(0, data.shape[1] - 1, n)
    xp = np.arange(data.shape[1])
    return np.stack([np.interp(x, xp, row) for row in data]).astype(np.float32) if len(data) else np.zeros((0, n), np.float32)


def align(inputs):
    """Bring several Channels to a common (channels, samples) shape.

    Fewer channels are cycled, a single sample is broadcast, other sample
    counts are resampled. Returns (names, [arrays], rate).
    """
    inputs = [c for c in inputs if c is not None and c.num_channels]
    if not inputs:
        return [], [], 60.0
    lead = max(inputs, key=lambda c: c.num_channels)
    nch = lead.num_channels
    ns = max(c.num_samples for c in inputs)
    out = []
    for c in inputs:
        d = resample(c.data, ns)
        if d.shape[0] != nch:
            d = d[np.arange(nch) % d.shape[0]]
        out.append(d)
    rate = max(inputs, key=lambda c: c.num_samples).rate
    return lead.names, out, rate


def unique_names(names):
    seen = {}
    out = []
    for n in names:
        if n in seen:
            seen[n] += 1
            n = f"{n}{seen[n]}"
        seen.setdefault(n, 0)
        out.append(n)
    return out
