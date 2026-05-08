import requests
from typing import Optional

from phaselogic.agents.base import AgentAdapter, AgentError
from phaselogic.config import Config


class KimiAgent(AgentAdapter):
    name = "kimi"

    def __init__(self, cfg: Config):
        self.cfg = cfg
        if not cfg.kimi_api_key:
            raise AgentError("KIMI_API_KEY is not configured")
        self._url = f"{cfg.kimi_base_url.rstrip('/')}/chat/completions"

    def call(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": self.cfg.kimi_model,
            "messages": messages,
        }

        try:
            resp = requests.post(
                self._url,
                headers={"Authorization": f"Bearer {self.cfg.kimi_api_key}"},
                json=body,
                timeout=self.cfg.timeout_seconds,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise AgentError(f"Kimi request failed: {e}")

        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise AgentError(f"Unexpected Kimi response shape: {e}", str(data))
