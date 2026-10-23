import time
from collections import deque


class ThermalFilter:
    def __init__(self, window_s: float, trim_ratio: float = 0.2, max_samples: int = 256):
        if window_s <= 0:
            raise ValueError("window_s must be positive")
        if not 0.0 <= trim_ratio < 0.5:
            raise ValueError("trim_ratio must be in [0, 0.5)")
        self._window_s = window_s
        self._trim_ratio = trim_ratio
        self._samples: deque[tuple[float, float]] = deque(maxlen=max_samples)

    def add(self, value: float, now: float | None = None) -> None:
        if value <= 0:
            return
        t = time.monotonic() if now is None else now
        self._samples.append((t, float(value)))
        self._prune(t)

    def value(self, now: float | None = None) -> float:
        self._prune(time.monotonic() if now is None else now)
        if not self._samples:
            return 0.0
        vals = sorted(v for _, v in self._samples)
        k = int(len(vals) * self._trim_ratio)
        core = vals[k:len(vals) - k] if k else vals
        return sum(core) / len(core)

    def clear(self) -> None:
        self._samples.clear()

    def __len__(self) -> int:
        return len(self._samples)

    def _prune(self, now: float) -> None:
        cutoff = now - self._window_s
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()
