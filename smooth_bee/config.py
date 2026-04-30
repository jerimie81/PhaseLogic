import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from smooth_bee import paths

CODEX_KEY_PATH = Path.home() / ".codex" / "API-key"


@dataclass
class Config:
    claude_model: str = "claude-sonnet-4-6"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    kimi_api_key: str = ""
    kimi_model: str = "moonshot-v1-32k"
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    openai_api_key: str = ""
    codex_model: str = "gpt-4o"
    timeout_seconds: int = 120
    max_retries: int = 3
    retry_backoff_base: float = 2.0


def load() -> Config:
    cfg_path = paths.config_path()
    raw = {}
    if cfg_path.exists():
        with open(cfg_path, "rb") as f:
            raw = tomllib.load(f)

    def _get(section, key, env_var=None, default=""):
        val = raw.get(section, {}).get(key, default)
        if not val and env_var:
            val = os.environ.get(env_var, default)
        return val

    openai_key = _get("codex", "api_key", "OPENAI_API_KEY")
    if not openai_key and CODEX_KEY_PATH.exists():
        openai_key = CODEX_KEY_PATH.read_text().strip()

    orch = raw.get("orchestration", {})

    return Config(
        claude_model=_get("claude", "model", default="claude-sonnet-4-6"),
        gemini_api_key=_get("gemini", "api_key", "GEMINI_API_KEY"),
        gemini_model=_get("gemini", "model", default="gemini-2.0-flash"),
        kimi_api_key=_get("kimi", "api_key", "KIMI_API_KEY"),
        kimi_model=_get("kimi", "model", default="moonshot-v1-32k"),
        kimi_base_url=_get("kimi", "base_url", default="https://api.moonshot.cn/v1"),
        openai_api_key=openai_key,
        codex_model=_get("codex", "model", default="gpt-4o"),
        timeout_seconds=int(orch.get("timeout_seconds", 120)),
        max_retries=int(orch.get("max_retries", 3)),
        retry_backoff_base=float(orch.get("retry_backoff_base", 2.0)),
    )
