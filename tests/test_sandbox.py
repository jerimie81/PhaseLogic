from pathlib import Path
import logging

from phaselogic.config import Config
from phaselogic.phases import phase6_testing
from phaselogic.sandbox import DockerSandbox, SandboxPolicy


def test_docker_sandbox_command_defaults_to_no_network(tmp_path):
    sandbox = DockerSandbox(image="example:latest")

    command = sandbox.command(tmp_path, ["pytest"])

    assert command[:2] == ["docker", "run"]
    assert "--network" in command
    assert command[command.index("--network") + 1] == "none"
    assert "example:latest" in command
    assert command[-1] == "pytest"


def test_docker_sandbox_can_allow_network(tmp_path):
    sandbox = DockerSandbox(policy=SandboxPolicy(allow_network=True))

    command = sandbox.command(Path(tmp_path), ["npm", "test"])

    assert command[command.index("--network") + 1] == "bridge"


def test_docker_sandbox_writes_runner_script(tmp_path):
    sandbox = DockerSandbox(image="example:latest")

    runner = sandbox.write_runner(tmp_path)

    text = runner.read_text()
    assert runner.name == "run_in_sandbox.sh"
    assert "--network none" in text
    assert "example:latest" in text
    assert runner.stat().st_mode & 0o111


def test_phase6_prepare_sandbox_writes_runner(monkeypatch, tmp_path):
    monkeypatch.setattr(phase6_testing.DockerSandbox, "available", lambda self: True)
    cfg = Config(sandbox_image="example:latest", sandbox_required=True)

    context = phase6_testing._prepare_sandbox(tmp_path, cfg, logging.getLogger("test"))

    assert context["enabled"] is True
    assert context["runner"] == "./.phaselogic/run_in_sandbox.sh"
    assert (tmp_path / ".phaselogic" / "run_in_sandbox.sh").exists()
