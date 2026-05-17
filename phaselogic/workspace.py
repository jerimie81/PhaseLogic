import json
import os
from pathlib import Path
from typing import Any

from phaselogic import paths


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
                    elif phase == "REPAIR":
                        status = "needs-repair"
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


def generate_build_report(project_name: str) -> Path:
    """Collate data from all phases into a polished Markdown report."""
    project_dir = get_path(project_name)
    report_path = project_dir / "BUILD_REPORT.md"
    
    # Gather data (with fallbacks if phases were skipped/incomplete)
    def _read_safe(fname):
        try:
            return read_artifact(project_name, fname)
        except Exception:
            return {}

    spec = _read_safe("phase1_spec.json")
    feasibility = _read_safe("phase2_feasibility.json")
    research = _read_safe("phase3_research.json")
    arch = _read_safe("phase4_architecture.json")
    summary = summarize_phase6(project_name)
    file_count, line_count = count_generated_files(project_name)
    
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# PhaseLogic Build Report: {project_name}",
        f"*Generated on {now}*",
        "",
        "## 1. Project Overview",
        f"**Description:** {spec.get('description', 'No description provided.')}",
        f"**Primary Language:** {spec.get('primary_language', 'N/A')}",
        f"**Frameworks:** {', '.join(spec.get('frameworks', [])) or 'N/A'}",
        "",
        "## 2. Feasibility & Research",
        f"**Feasibility Score:** {feasibility.get('feasibility_score', 'N/A')}/10",
        f"**Build Complexity:** {feasibility.get('complexity', 'N/A')}",
        "",
        "### Key Libraries & Toolchains",
    ]
    
    for tool in research.get("toolchains", []):
        lines.append(f"- **{tool.get('name')}**: {tool.get('version', 'latest')}")
        
    lines += [
        "",
        "## 3. Architecture & Coding",
        f"The project was divided into {len(arch.get('sections', []))} architectural sections.",
        "",
        "### Generated Artifacts",
        f"- **Total Files:** {file_count}",
        f"- **Lines of Code:** {line_count}",
        f"- **Workspace Path:** `{get_generated_dir(project_name)}`",
        "",
        "## 4. Quality Assurance & Security",
        "### Test Results",
        f"- **Sections Tested:** {summary['sections_total']}",
        f"- **Passed:** {summary['sections_passed']}",
        f"- **Failed:** {summary['sections_failed']}",
        f"- **Repaired:** {summary['sections_repaired']}",
        "",
        "### Security Audit",
        f"- **Critical Issues:** {summary['security_critical']}",
        f"- **High Severity:** {summary['security_high']}",
        f"- **Warnings:** {summary['security_warnings']}",
    ]
    
    if summary['security_total'] > 0:
        lines += [
            "",
            "#### Security Findings Summary",
            "| Severity | File | Issue |",
            "| :--- | :--- | :--- |",
        ]
        security_path = get_phase6_dir(project_name) / "security_final.json"
        if security_path.exists():
            issues = json.loads(security_path.read_text())
            for issue in issues[:20]: # Show top 20
                lines.append(f"| {issue.get('severity', 'N/A')} | {issue.get('file', 'N/A')} | {issue.get('description', 'N/A')} |")
            if len(issues) > 20:
                lines.append(f"| ... | ... | ... |")

    lines += [
        "",
        "---",
        "*Built with PhaseLogic: Professional AI Software Engineering Pipeline.*"
    ]
    
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
