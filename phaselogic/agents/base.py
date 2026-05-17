import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class AgentError(Exception):
    def __init__(self, message: str, raw: str = ""):
        super().__init__(message)
        self.raw = raw


class AgentAdapter(ABC):
    name: str = "base"
    phase_label: str = ""
    spinner_enabled: bool = True

    @abstractmethod
    def call(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Send prompt to the AI and return the text response."""

    def call_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        retries: int = 3,
        backoff_base: float = 2.0,
    ) -> str:
        from phaselogic.spinner import Spinner
        from phaselogic import memory

        label = f"Calling {self.name}"
        if self.phase_label:
            label += f" ({self.phase_label})"

        avg = memory.agent_avg_seconds(self.name)

        last_err = None
        for attempt in range(retries):
            t_start = time.monotonic()
            succeeded = False
            with Spinner(label, enabled=self.spinner_enabled, avg_seconds=avg):
                try:
                    result = self.call(prompt, system_prompt)
                    succeeded = True
                    return result
                except AgentError as e:
                    last_err = e
                finally:
                    duration = time.monotonic() - t_start
                    memory.log_agent_call(self.name, duration, succeeded)

            if attempt < retries - 1:
                time.sleep(backoff_base ** attempt)

        raise last_err

    def call_for_report(
        self,
        prompt: str,
        report_path: Path,
        system_prompt: Optional[str] = None,
    ) -> dict:
        """
        Request a structured report from an agent.

        CLI agents such as Codex can override this to write files directly.
        API agents usually return the report text, so the base implementation
        parses the response as JSON and writes it to report_path.
        """
        raw = self.call(prompt, system_prompt)
        if report_path.exists():
            return json.loads(report_path.read_text())
        try:
            report = json.loads(_strip_json_fence(raw))
        except json.JSONDecodeError as e:
            raise AgentError(f"{self.name} did not return valid JSON report: {e}", raw)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report


def _strip_json_fence(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()
