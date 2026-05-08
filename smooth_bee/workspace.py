import json
import os
from pathlib import Path
from typing import Any

from smooth_bee import paths


def _root() -> Path:
    return paths.workspace_root()


def create(project_name: str) -> Path:
    project_dir = _root() / project_name
    for sub in ["phase5_sections", "phase6_results", "generated", "logs"]:
        (project_dir / sub).mkdir(parents=True, exist_ok=True)
    return project_dir


def get_path(project_name: str) -> Path:
    return _root() / project_name


def list_projects() -> list[dict]:
    root = _root()
    if not root.exists():
        return []
    results = []
    for d in sorted(root.iterdir()):
        if d.is_dir():
            state_file = d / "state.json"
            phase = "unknown"
            created_at = ""
            status = "unknown"
            if state_file.exists():
                try:
                    data = json.loads(state_file.read_text())
                    phase = data.get("current_phase", "unknown")
                    created_at = data.get("created_at", "")
                    if phase == "DONE":
                        status = "done"
                    elif phase == "FAILED":
                        status = "failed"
                    else:
                        status = "running"
                except Exception:
                    pass
            results.append({"name": d.name, "phase": phase, "path": str(d),
                             "created_at": created_at, "status": status})
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


def summarize_phase6(project_name: str) -> dict:
    """Parse phase6_results/ and return test + security counts."""
    phase6_dir = get_phase6_dir(project_name)
    total = passed = failed = repaired = 0

    if phase6_dir.exists():
        for f in phase6_dir.glob("*_codex.json"):
            try:
                data = json.loads(f.read_text())
                total += 1
                status = data.get("overall_status", "")
                if status in ("passed", "repaired"):
                    passed += 1
                elif status == "failed":
                    failed += 1
                repaired += data.get("failures_repaired", 0)
            except Exception:
                pass

    security_issues: list = []
    security_path = phase6_dir / "security_final.json" if phase6_dir.exists() else None
    if security_path and security_path.exists():
        try:
            security_issues = json.loads(security_path.read_text())
            if not isinstance(security_issues, list):
                security_issues = []
        except Exception:
            pass

    critical = sum(1 for i in security_issues if i.get("severity") == "critical")
    high = sum(1 for i in security_issues if i.get("severity") == "high")
    warnings = sum(1 for i in security_issues if i.get("severity") in ("medium", "low"))

    return {
        "sections_total": total,
        "sections_passed": passed,
        "sections_failed": failed,
        "sections_repaired": repaired,
        "security_total": len(security_issues),
        "security_critical": critical,
        "security_high": high,
        "security_warnings": warnings,
    }


def count_generated_files(project_name: str) -> tuple[int, int]:
    """Return (file_count, total_line_count) for the generated/ directory."""
    gen_dir = get_generated_dir(project_name)
    if not gen_dir.exists():
        return 0, 0
    file_count = 0
    line_count = 0
    for f in gen_dir.rglob("*"):
        if f.is_file():
            file_count += 1
            try:
                line_count += f.read_text(errors="replace").count("\n")
            except Exception:
                pass
    return file_count, line_count
