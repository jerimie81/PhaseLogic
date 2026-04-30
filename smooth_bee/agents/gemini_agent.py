import requests
from typing import Optional

from smooth_bee.agents.base import AgentAdapter, AgentError
from smooth_bee.config import Config


class GeminiAgent(AgentAdapter):
    name = "gemini"

    def __init__(self, cfg: Config):
        self.cfg = cfg
        if not cfg.gemini_api_key:
            raise AgentError("GEMINI_API_KEY is not configured")
        self._base = (
            "https://generativelanguage.googleapis.com/v1beta/models"
            f"/{cfg.gemini_model}:generateContent"
        )

    def call(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        body: dict = {
            "contents": [{"parts": [{"text": prompt}]}],
        }
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        try:
            resp = requests.post(
                self._base,
                params={"key": self.cfg.gemini_api_key},
                json=body,
                timeout=self.cfg.timeout_seconds,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise AgentError(f"Gemini request failed: {e}")

        data = resp.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise AgentError(f"Unexpected Gemini response shape: {e}", str(data))
