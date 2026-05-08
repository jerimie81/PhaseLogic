import time
from abc import ABC, abstractmethod
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
