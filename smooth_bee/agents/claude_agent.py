import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from smooth_bee.agents.base import AgentAdapter, AgentError
from smooth_bee.config import Config

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


class ClaudeAgent(AgentAdapter):
    name = "claude"

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def call(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        cmd = ["claude", "--print", "--output-format", "json"]
        if system_prompt:
            cmd += ["--system-prompt", system_prompt]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(prompt)
            prompt_file = f.name

        try:
            cmd.append(prompt)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.cfg.timeout_seconds,
            )
        finally:
            Path(prompt_file).unlink(missing_ok=True)

        if result.returncode != 0:
            raise AgentError(
                f"claude exited {result.returncode}: {result.stderr[:500]}",
                result.stdout,
            )

        raw = _ANSI.sub("", result.stdout).strip()
        try:
            data = json.loads(raw)
            # claude --output-format json wraps the text in {"result": "..."}
            return data.get("result") or data.get("text") or raw
        except json.JSONDecodeError:
            return raw
