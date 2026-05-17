from phaselogic import publish


def test_secret_scan_finds_generic_secret(tmp_path):
    (tmp_path / "settings.py").write_text('API_KEY = "abcdefghijklmnopqrstuvwxyz"\n')

    findings = publish.scan_secrets(tmp_path)

    assert len(findings) == 1
    assert findings[0].path == "settings.py"
    assert findings[0].kind == "generic_secret_assignment"


def test_build_preflight_writes_report(monkeypatch, tmp_path):
    workspace_root = tmp_path / "workspace"
    generated = workspace_root / "demo" / "generated"
    generated.mkdir(parents=True)
    (generated / "app.py").write_text("print('hello')\n")
    monkeypatch.setenv("PHASELOGIC_WORKSPACE", str(workspace_root))

    preflight = publish.build_preflight(
        "demo",
        repo="owner/repo",
        branch="phaselogic/demo",
        base="main",
    )

    assert preflight.file_count == 1
    assert preflight.secret_findings == []
    assert "not a Git repository" in preflight.diff_preview
    assert (workspace_root / "demo" / "publish_preflight.json").exists()
