import time
import threading


class RateLimiter:
    """Token-bucket rate limiter enforcing a minimum interval between calls."""

    def __init__(self, min_spacing_seconds: float):
        self._min_spacing = min_spacing_seconds
        self._last_call = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self._min_spacing:
                time.sleep(self._min_spacing - elapsed)
            self._last_call = time.monotonic()
