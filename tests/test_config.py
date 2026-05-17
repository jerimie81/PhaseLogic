from pathlib import Path

from phaselogic import config


def test_config_loads_kimi_from_file(monkeypatch, tmp_path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(
        """
[kimi]
api_key = "kimi-file-key"
model = "kimi-model"
base_url = "https://kimi.example/v1"

[phases]
coding = "kimi"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("PHASELOGIC_CONFIG", str(cfg_path))
    monkeypatch.delenv("KIMI_API_KEY", raising=False)

    cfg = config.load()

    assert cfg.kimi_api_key == "kimi-file-key"
    assert cfg.kimi_model == "kimi-model"
    assert cfg.kimi_base_url == "https://kimi.example/v1"
    assert cfg.coding_agent == "kimi"


def test_config_loads_kimi_from_environment(monkeypatch, tmp_path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text("[kimi]\napi_key = \"\"\n", encoding="utf-8")
    monkeypatch.setenv("PHASELOGIC_CONFIG", str(cfg_path))
    monkeypatch.setenv("KIMI_API_KEY", "kimi-env-key")

    cfg = config.load()

    assert cfg.kimi_api_key == "kimi-env-key"


def test_config_loads_sandbox_settings(monkeypatch, tmp_path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(
        """
[sandbox]
enabled = true
required = false
image = "node:22"
allow_network = true
memory = "1g"
cpus = "1"
timeout_seconds = 120
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("PHASELOGIC_CONFIG", str(cfg_path))

    cfg = config.load()

    assert cfg.sandbox_enabled is True
    assert cfg.sandbox_required is False
    assert cfg.sandbox_image == "node:22"
    assert cfg.sandbox_allow_network is True
    assert cfg.sandbox_memory == "1g"
    assert cfg.sandbox_cpus == "1"
    assert cfg.sandbox_timeout_seconds == 120


def test_validate_requires_kimi_when_phase_uses_kimi(monkeypatch):
    cfg = config.Config(
        spec_agent="kimi",
        feasibility_agent="kimi",
        research_agent="kimi",
        architecture_agent="kimi",
        coding_agent="kimi",
        testing_agent="kimi",
        kimi_api_key="",
    )

    checks = config.validate(cfg)

    assert ("Kimi API key", False, "set KIMI_API_KEY or [kimi] api_key in config.toml") in checks
