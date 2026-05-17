from phaselogic import agent_profiles
from phaselogic.config import Config


def test_create_and_load_agent_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("PHASELOGIC_AGENT_PROFILES", str(tmp_path))

    path = agent_profiles.create_template("Builder")
    profiles = agent_profiles.load_profiles()

    assert path == tmp_path / "builder.toml"
    assert "Builder" in profiles
    assert profiles["Builder"].validation_errors() == []
    assert "generated_write" in profiles["Builder"].workspace_permissions


def test_agent_profile_validation_rejects_unknown_permission():
    profile = agent_profiles.AgentProfile(
        name="bad",
        provider="gemini",
        model="gemini-2.0-flash",
        workspace_permissions=["root"],
    )

    assert profile.validation_errors()


def test_agent_profile_test_uses_adapter_call(monkeypatch):
    from phaselogic import agents, config

    calls = {}

    class ReadyAgent:
        def call(self, prompt, system_prompt=None):
            calls["prompt"] = prompt
            calls["system_prompt"] = system_prompt
            return "READY"

    def fake_get_agent(name, cfg):
        calls["name"] = name
        calls["model"] = cfg.gemini_model
        return ReadyAgent()

    monkeypatch.setattr(config, "load", lambda: Config(gemini_api_key="key"))
    monkeypatch.setattr(agents, "get_agent", fake_get_agent)

    profile = agent_profiles.AgentProfile(
        name="builder",
        provider="gemini",
        model="gemini-test-model",
    )

    ok, message = profile.test()

    assert ok is True
    assert message == "Connection successful."
    assert calls["name"] == "gemini"
    assert calls["model"] == "gemini-test-model"
