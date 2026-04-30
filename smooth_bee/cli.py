import argparse
import re
import subprocess
import sys
from pathlib import Path

from smooth_bee import config, state as st, workspace as ws, memory


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text)
    return text[:40].strip("-")


def cmd_new(args) -> None:
    cfg = config.load()
    description = args.description
    name = args.name if args.name else _slugify(description)

    project_dir = ws.get_path(name)
    if project_dir.exists():
        print(f"Project '{name}' already exists. Use: smooth-bee resume {name}")
        sys.exit(1)

    print(f"Starting project: {name}")
    print(f"Description: {description}")

    if args.dry_run:
        print("\n[DRY RUN] Would execute pipeline phases:")
        for i, phase in enumerate(["SPEC (Claude)", "FEASIBILITY (Kimi)", "RESEARCH (Gemini)",
                                    "ARCHITECTURE (Claude)", "CODING (Gemini+Kimi)", "TESTING (Codex)"], 1):
            print(f"  Phase {i}: {phase}")
        print(f"\nWorkspace would be: {project_dir}")
        return

    ws.create(name)
    state = st.create(name, description, project_dir)
    memory.register_project(name, str(project_dir))

    from smooth_bee.orchestrator import Orchestrator
    Orchestrator(name, cfg).run()


def cmd_resume(args) -> None:
    cfg = config.load()
    name = args.project_name
    project_dir = ws.get_path(name)

    if not project_dir.exists():
        print(f"Project '{name}' not found. Use: smooth-bee new \"<description>\"")
        sys.exit(1)

    if args.phase:
        target = getattr(st.Phase, args.phase.upper(), None)
        if target is None:
            print(f"Unknown phase: {args.phase}")
            sys.exit(1)
        state = st.load(project_dir)
        # rewind to just before the target phase
        phase_order = list(st._TRANSITIONS.keys())
        idx = phase_order.index(target) if target in phase_order else -1
        if idx >= 0:
            state.current_phase = phase_order[idx - 1] if idx > 0 else st.Phase.INIT
            state.completed_phases = [p.value for p in phase_order[:max(0, idx - 1)]]
            st.save(state, project_dir)
            print(f"Rewound to phase: {state.current_phase.value}")

    from smooth_bee.orchestrator import Orchestrator
    Orchestrator(name, cfg).run()


def cmd_list(args) -> None:
    projects = ws.list_projects()
    if not projects:
        print("No projects found.")
        return
    print(f"{'PROJECT':<30} {'PHASE':<15}")
    print("-" * 45)
    for p in projects:
        print(f"{p['name']:<30} {p['phase']:<15}")


def cmd_status(args) -> None:
    name = args.project_name
    project_dir = ws.get_path(name)
    if not project_dir.exists():
        print(f"Project '{name}' not found.")
        sys.exit(1)
    s = st.load(project_dir)
    print(f"Project:     {s.project_name}")
    print(f"Description: {s.description}")
    print(f"Phase:       {s.current_phase.value}")
    print(f"Completed:   {', '.join(s.completed_phases) or 'none'}")
    print(f"Sections:    coded={len(s.sections_coded)}  tested={len(s.sections_tested)}")
    if s.error_info:
        print(f"Error:       {s.error_info}")
    print(f"Created:     {s.created_at}")
    print(f"Updated:     {s.updated_at}")


def cmd_logs(args) -> None:
    name = args.project_name
    log_dir = ws.get_path(name) / "logs"
    if not log_dir.exists():
        print("No logs found.")
        return
    logs = sorted(log_dir.glob("session_*.log"), reverse=True)
    if not logs:
        print("No session logs found.")
        return
    latest = logs[0]
    print(f"--- {latest.name} ---")
    subprocess.run(["tail", "-n", str(args.lines), str(latest)])


def main() -> None:
    parser = argparse.ArgumentParser(prog="smooth-bee", description="Multi-AI project orchestrator")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Start a new project")
    p_new.add_argument("description", help="Project description in plain English")
    p_new.add_argument("--name", help="Override auto-generated project name")
    p_new.add_argument("--dry-run", action="store_true", help="Show pipeline steps without calling agents")
    p_new.set_defaults(func=cmd_new)

    p_resume = sub.add_parser("resume", help="Resume an interrupted project")
    p_resume.add_argument("project_name")
    p_resume.add_argument("--phase", help="Restart from this phase (SPEC, FEASIBILITY, etc.)")
    p_resume.set_defaults(func=cmd_resume)

    p_list = sub.add_parser("list", help="List all projects")
    p_list.set_defaults(func=cmd_list)

    p_status = sub.add_parser("status", help="Show project status")
    p_status.add_argument("project_name")
    p_status.set_defaults(func=cmd_status)

    p_logs = sub.add_parser("logs", help="Tail the latest session log")
    p_logs.add_argument("project_name")
    p_logs.add_argument("--lines", type=int, default=50)
    p_logs.set_defaults(func=cmd_logs)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
