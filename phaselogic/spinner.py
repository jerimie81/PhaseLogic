import os
import sys
import threading
import time
from typing import Optional

_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_ENABLED = sys.stderr.isatty() and os.environ.get("NO_COLOR", "") == ""


class Spinner:
    """Animated spinner on stderr during a blocking operation."""

    def __init__(self, label: str, enabled: bool = True,
                 avg_seconds: Optional[float] = None):
        self._label = label
        self._active = enabled and _ENABLED
        self._avg = avg_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_time: float = 0.0

    def start(self) -> "Spinner":
        if not self._active:
            return self
        self._start_time = time.monotonic()
        self._stop.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if not self._active or self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=1.0)
        clear_width = len(self._label) + 36
        sys.stderr.write("\r" + " " * clear_width + "\r")
        sys.stderr.flush()

    def _spin(self) -> None:
        i = 0
        while not self._stop.is_set():
            elapsed = time.monotonic() - self._start_time
            frame = _FRAMES[i % len(_FRAMES)]
            avg_hint = f" / ~{self._avg:.0f}s avg" if self._avg else ""
            sys.stderr.write(f"\r{frame} {self._label}... {elapsed:.1f}s{avg_hint}")
            sys.stderr.flush()
            i += 1
            self._stop.wait(0.1)

    def __enter__(self) -> "Spinner":
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
        return False
