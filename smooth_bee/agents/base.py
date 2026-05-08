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
        from smooth_bee.spinner import Spinner
        label = f"Calling {self.name}"
        if self.phase_label:
            label += f" ({self.phase_label})"
        last_err = None
        for attempt in range(retries):
            with Spinner(label, enabled=self.spinner_enabled):
                try:
                    return self.call(prompt, system_prompt)
                except AgentError as e:
                    last_err = e
            if attempt < retries - 1:
                time.sleep(backoff_base ** attempt)
        raise last_err
