import json
import os
from pathlib import Path
from typing import Any

from smooth_bee.config import SMOOTH_BEE_ROOT

WORKSPACE_ROOT = SMOOTH_BEE_ROOT / "workspace"


def create(project_name: str) -> Path:
    project_dir = WORKSPACE_ROOT / project_name
    for sub in ["phase5_sections", "phase6_results", "generated", "logs"]:
        (project_dir / sub).mkdir(parents=True, exist_ok=True)
    return project_dir


def get_path(project_name: str) -> Path:
    return WORKSPACE_ROOT / project_name


def list_projects() -> list[dict]:
    if not WORKSPACE_ROOT.exists():
        return []
    results = []
    for d in sorted(WORKSPACE_ROOT.iterdir()):
        if d.is_dir():
            state_file = d / "state.json"
            phase = "unknown"
            if state_file.exists():
                try:
                    data = json.loads(state_file.read_text())
                    phase = data.get("current_phase", "unknown")
                except Exception:
                    pass
            results.append({"name": d.name, "phase": phase, "path": str(d)})
    return results


def read_artifact(project_name: str, filename: str) -> Any:
    path = get_path(project_name) / filename
    return json.loads(path.read_text())


def write_artifact(project_name: str, filename: str, data: Any) -> Path:
    path = get_path(project_name) / filename
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, path)
    return path


def write_generated_file(project_name: str, rel_path: str, content: str) -> Path:
    target = get_path(project_name) / "generated" / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def get_generated_dir(project_name: str) -> Path:
    return get_path(project_name) / "generated"


def get_phase5_dir(project_name: str) -> Path:
    return get_path(project_name) / "phase5_sections"


def get_phase6_dir(project_name: str) -> Path:
    return get_path(project_name) / "phase6_results"
