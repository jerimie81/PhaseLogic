import os
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

from phaselogic import paths

CODEX_KEY_PATH = Path.home() / ".codex" / "API-key"


@dataclass
class Config:
    claude_model: str = "claude-sonnet-4-6"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    kimi_api_key: str = ""
    kimi_model: str = "moonshot-v1-32k"
    kimi_base_url: str = "https://api.moonshot.ai/v1"
    openai_api_key: str = ""
    codex_model: str = "gpt-4o"
    ollama_model: str = "llama3"
    ollama_base_url: str = "http://localhost:11434"
    spec_agent: str = "claude"
    feasibility_agent: str = "gemini"
    research_agent: str = "gemini"
    architecture_agent: str = "claude"
    coding_agent: str = "gemini"
    testing_agent: str = "codex"
    timeout_seconds: int = 120
    max_retries: int = 3
    retry_backoff_base: float = 2.0
    intake_aggressiveness: int = 3
    sandbox_enabled: bool = True
    sandbox_required: bool = True
    sandbox_image: str = "python:3.11-slim"
    sandbox_allow_network: bool = False
    sandbox_memory: str = "2g"
    sandbox_cpus: str = "2"
    sandbox_timeout_seconds: int = 300


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
    phases = raw.get("phases", {})
    sandbox = raw.get("sandbox", {})

    return Config(
        claude_model=_get("claude", "model", default="claude-sonnet-4-6"),
        gemini_api_key=_get("gemini", "api_key", "GEMINI_API_KEY"),
        gemini_model=_get("gemini", "model", default="gemini-2.0-flash"),
        kimi_api_key=_get("kimi", "api_key", "KIMI_API_KEY"),
        kimi_model=_get("kimi", "model", default="moonshot-v1-32k"),
        kimi_base_url=_get("kimi", "base_url", default="https://api.moonshot.ai/v1"),
        openai_api_key=openai_key,
        codex_model=_get("codex", "model", default="gpt-4o"),
        ollama_model=_get("ollama", "model", default="llama3"),
        ollama_base_url=_get("ollama", "base_url", default="http://localhost:11434"),
        spec_agent=phases.get("spec", "claude"),
        feasibility_agent=phases.get("feasibility", "gemini"),
        research_agent=phases.get("research", "gemini"),
        architecture_agent=phases.get("architecture", "claude"),
        coding_agent=phases.get("coding", "gemini"),
        testing_agent=phases.get("testing", "codex"),
        timeout_seconds=int(orch.get("timeout_seconds", 120)),
        max_retries=int(orch.get("max_retries", 3)),
        retry_backoff_base=float(orch.get("retry_backoff_base", 2.0)),
        intake_aggressiveness=int(raw.get("intake", {}).get("aggressiveness", 3)),
        sandbox_enabled=_as_bool(sandbox.get("enabled", True)),
        sandbox_required=_as_bool(sandbox.get("required", True)),
        sandbox_image=str(sandbox.get("image", "python:3.11-slim")),
        sandbox_allow_network=_as_bool(sandbox.get("allow_network", False)),
        sandbox_memory=str(sandbox.get("memory", "2g")),
        sandbox_cpus=str(sandbox.get("cpus", "2")),
        sandbox_timeout_seconds=int(sandbox.get("timeout_seconds", 300)),
    )


def validate(cfg: Config) -> list[tuple[str, bool, str]]:
    """Check that all required integrations are configured. Returns (label, ok, hint) triples."""
    checks: list[tuple[str, bool, str]] = []

    used_agents = {
        cfg.spec_agent, cfg.feasibility_agent, cfg.research_agent,
        cfg.architecture_agent, cfg.coding_agent, cfg.testing_agent
    }

    if "claude" in used_agents:
        try:
            r = subprocess.run(["claude", "--version"], capture_output=True, timeout=5)
            ok = r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            ok = False
        checks.append(("Claude CLI", ok, "" if ok else "claude not found in PATH"))

    if "gemini" in used_agents:
        ok = bool(cfg.gemini_api_key)
        checks.append(("Gemini API key", ok, "" if ok else "set GEMINI_API_KEY or [gemini] api_key in config.toml"))

    if "kimi" in used_agents:
        ok = bool(cfg.kimi_api_key)
        checks.append(("Kimi API key", ok, "" if ok else "set KIMI_API_KEY or [kimi] api_key in config.toml"))

    if "codex" in used_agents:
        ok = bool(cfg.openai_api_key)
        checks.append(("Codex/OpenAI key", ok, "" if ok else "set OPENAI_API_KEY, [codex] api_key, or ~/.codex/API-key"))

    if "ollama" in used_agents:
        import urllib.request
        import urllib.error
        try:
            url = f"{cfg.ollama_base_url.rstrip('/')}/api/tags"
            urllib.request.urlopen(url, timeout=2)
            ok = True
        except Exception:
            ok = False
        checks.append(("Ollama Service", ok, "" if ok else f"could not reach {cfg.ollama_base_url}"))

    if cfg.sandbox_enabled and cfg.sandbox_required:
        from phaselogic.sandbox import DockerSandbox, SandboxPolicy
        sandbox = DockerSandbox(
            image=cfg.sandbox_image,
            policy=SandboxPolicy(
                allow_network=cfg.sandbox_allow_network,
                memory=cfg.sandbox_memory,
                cpus=cfg.sandbox_cpus,
                timeout_seconds=cfg.sandbox_timeout_seconds,
            ),
        )
        ok = sandbox.available()
        checks.append(("Docker sandbox", ok, "" if ok else "docker not found or not available"))

    return checks


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)
