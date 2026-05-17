import subprocess

from phaselogic.connectors import get_connector, list_connectors
from phaselogic.permissions import Permission


def test_connector_registry_exposes_local_git():
    names = [connector.name for connector in list_connectors()]

    assert "git" in names
    assert "github" in names


def test_local_git_health_check(monkeypatch):
    class Result:
        returncode = 0
        stdout = "git version test\n"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: Result())

    status = get_connector("git").health_check()

    assert status.connected is True
    assert status.detail == "git version test"
    assert any(Permission.GIT in capability.permissions for capability in status.capabilities)


def test_github_health_check(monkeypatch):
    class Result:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["git", "--version"]:
            return Result(stdout="git version test\n")
        if cmd[:2] == ["gh", "--version"]:
            return Result(stdout="gh version test\n")
        if cmd[:3] == ["gh", "auth", "status"]:
            return Result(stdout="Logged in\n")
        return Result(returncode=1, stderr="unexpected")

    monkeypatch.setattr(subprocess, "run", fake_run)

    status = get_connector("github").health_check()

    assert status.connected is True
    assert "gh authenticated" in status.detail
