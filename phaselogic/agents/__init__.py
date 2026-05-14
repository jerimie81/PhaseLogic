from phaselogic.agents.base import AgentAdapter, AgentError
from phaselogic.agents.claude_agent import ClaudeAgent
from phaselogic.agents.codex_agent import CodexAgent
from phaselogic.agents.gemini_agent import GeminiAgent
from phaselogic.agents.kimi_agent import KimiAgent
from phaselogic.agents.ollama_agent import OllamaAgent
from phaselogic.config import Config

def get_agent(name: str, cfg: Config) -> AgentAdapter:
    name = name.lower().strip()
    if name == "claude":
        return ClaudeAgent(cfg)
    elif name == "codex":
        return CodexAgent(cfg)
    elif name == "gemini":
        return GeminiAgent(cfg)
    elif name == "kimi":
        return KimiAgent(cfg)
    elif name == "ollama":
        return OllamaAgent(cfg)
    else:
        raise ValueError(f"Unknown agent type: {name}")
