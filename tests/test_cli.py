import subprocess
import sys
import json


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


def test_new_dry_run_can_use_seeded_intake_file(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("", encoding="utf-8")
    intake_path = tmp_path / "phase0_intake.json"
    intake_path.write_text(
        json.dumps(
            {
                "raw_description": "a FastAPI fitness tracker",
                "app_category": "service",
                "target_platforms": ["server"],
                "language": "python",
                "required_toolchains": ["docker", "python3"],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "phaselogic.cli",
            "new",
            "--name",
            "seeded-demo",
            "--dry-run",
            "--intake-file",
            str(intake_path),
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
    assert "Description: a FastAPI fitness tracker" in result.stdout
    assert "Required toolchains: docker, python3" in result.stdout
