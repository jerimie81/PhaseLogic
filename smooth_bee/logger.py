import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from smooth_bee import workspace


def get_logger(project_name: str) -> logging.Logger:
    log_dir = workspace.get_path(project_name) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    log_file = log_dir / f"session_{ts}.log"

    logger = logging.getLogger(f"smooth-bee.{project_name}")
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        return logger

    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def phase_banner(logger: logging.Logger, phase_num: int, phase_name: str) -> None:
    bar = "=" * 50
    logger.info(f"\n{bar}\n  PHASE {phase_num}: {phase_name}\n{bar}")
