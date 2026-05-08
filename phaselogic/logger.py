import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from phaselogic import workspace
from phaselogic import color

_run_start: float | None = None
_TOTAL_PHASES = 6


def start_run() -> None:
    global _run_start
    _run_start = time.monotonic()


def elapsed_seconds() -> int:
    if _run_start is None:
        return 0
    return int(time.monotonic() - _run_start)


def get_logger(project_name: str) -> logging.Logger:
    log_dir = workspace.get_path(project_name) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    log_file = log_dir / f"session_{ts}.log"

    logger = logging.getLogger(f"phaselogic.{project_name}")
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        return logger

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)

    # Print log path so users know where to look
    print(color.yellow(f"Logging to: {log_file}"))

    return logger


def phase_banner(logger: logging.Logger, phase_num: int, phase_name: str) -> None:
    filled = phase_num - 1
    bar = "█" * filled + "░" * (_TOTAL_PHASES - filled)
    elapsed_str = ""
    if _run_start is not None:
        secs = int(time.monotonic() - _run_start)
        elapsed_str = f"  ~{secs}s elapsed"
    sep = "=" * 50
    progress = f"  [{bar}] Phase {phase_num}/{_TOTAL_PHASES}{elapsed_str}"
    logger.info(
        f"\n{color.cyan_bold(sep)}\n"
        f"  {color.cyan_bold(f'PHASE {phase_num}: {phase_name}')}\n"
        f"{progress}\n"
        f"{color.cyan_bold(sep)}"
    )
