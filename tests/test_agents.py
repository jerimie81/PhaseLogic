from pathlib import Path

from phaselogic.agents import get_agent
from phaselogic.config import Config


def test_agent_factory_builds_configured_adapters():
    cfg = Config(
        gemini_api_key="gemini-key",
        kimi_api_key="kimi-key",
        openai_api_key="openai-key",
    )

    assert get_agent("gemini", cfg).name == "gemini"
    assert get_agent("kimi", cfg).name == "kimi"
    assert get_agent("codex", cfg).name == "codex"
    assert get_agent("ollama", cfg).name == "ollama"
    assert get_agent("claude", cfg).name == "claude"


def test_base_agent_call_for_report_writes_returned_json(tmp_path):
    from phaselogic.agents.base import AgentAdapter

    class JsonAgent(AgentAdapter):
        name = "json-agent"

        def call(self, prompt, system_prompt=None):
            return '{"status": "ok"}'

    report_path = tmp_path / "report.json"
    report = JsonAgent().call_for_report("write report", report_path)

    assert report == {"status": "ok"}
    assert report_path.exists()
