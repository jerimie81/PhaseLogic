import json
import urllib.request
import urllib.error
from typing import Optional

from phaselogic.agents.base import AgentAdapter, AgentError
from phaselogic.config import Config


class OllamaAgent(AgentAdapter):
    name = "ollama"

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def call(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        model = self.cfg.ollama_model
        url = f"{self.cfg.ollama_base_url.rstrip('/')}/api/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        
        if system_prompt:
            payload["system"] = system_prompt

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=self.cfg.timeout_seconds) as response:
                result = json.loads(response.read().decode("utf-8"))
                response_text = result.get("response", "")
                
                # Try to parse and return only the JSON content
                try:
                    data = json.loads(response_text)
                    return response_text
                except json.JSONDecodeError:
                    return response_text
        except urllib.error.URLError as e:
            raise AgentError(f"Ollama API request failed: {e}", "")
