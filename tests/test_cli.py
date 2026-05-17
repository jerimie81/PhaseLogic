import subprocess
import sys


def test_new_dry_run_does_not_require_api_keys(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "phaselogic.cli",
            "new",
            "a tiny command line timer",
            "--dry-run",
            "--aggressiveness",
            "1",
        ],
        capture_output=True,
        text=True,
        env={
            "PHASELOGIC_CONFIG": str(config_path),
            "PHASELOGIC_WORKSPACE": str(tmp_path / "workspace"),
        },
        timeout=20,
    )

    assert result.returncode == 0
    assert "[DRY RUN] Would execute pipeline phases" in result.stdout
