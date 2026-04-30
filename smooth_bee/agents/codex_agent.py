import json
import os
import subprocess
from pathlib import Path
from typing import Optional

from smooth_bee.agents.base import AgentAdapter, AgentError
from smooth_bee.config import Config


class CodexAgent(AgentAdapter):
    name = "codex"

    def __init__(self, cfg: Config, working_dir: Optional[Path] = None):
        self.cfg = cfg
        self.working_dir = working_dir

    def call(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        env = {**os.environ}
        if self.cfg.openai_api_key:
            env["OPENAI_API_KEY"] = self.cfg.openai_api_key

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        cmd = ["codex", "exec", full_prompt]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                cwd=self.working_dir,
                timeout=self.cfg.timeout_seconds,
            )
        except FileNotFoundError:
            raise AgentError("codex CLI not found — ensure it is installed and on PATH")
        except subprocess.TimeoutExpired:
            raise AgentError(f"codex exec timed out after {self.cfg.timeout_seconds}s")

        if result.returncode != 0:
            raise AgentError(
                f"codex exited {result.returncode}: {result.stderr[:500]}",
                result.stdout,
            )

        return result.stdout.strip()

    def call_for_report(
        self,
        prompt: str,
        report_path: Path,
        system_prompt: Optional[str] = None,
    ) -> dict:
        """Run codex and read back a JSON report it writes to report_path."""
        self.call(prompt, system_prompt)
        if not report_path.exists():
            raise AgentError(
                f"Codex did not produce expected report at {report_path}"
            )
        return json.loads(report_path.read_text())
