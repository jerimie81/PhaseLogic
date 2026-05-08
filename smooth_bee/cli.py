import argparse
import datetime
import re
import shutil
import subprocess
import sys
from pathlib import Path

from smooth_bee import color, config, state as st, workspace as ws, memory

_PHASE_LABELS = [
    ("SPEC",         "SPEC — specification (Claude)"),
    ("FEASIBILITY",  "FEASIBILITY — feasibility check (Kimi)"),
    ("RESEARCH",     "RESEARCH — research & planning (Gemini)"),
    ("ARCHITECTURE", "ARCHITECTURE — design (Claude)"),
    ("CODING",       "CODING — code generation (Gemini + Kimi)"),
    ("TESTING",      "TESTING — test generation (Codex)"),
]


def _check_config(cfg) -> None:
    checks = config.validate(cfg)
    failures = [(label, note) for label, ok, note in checks if not ok]
    if failures:
        print(color.red_bold("smooth-bee: configuration error(s) — cannot start pipeline:"))
        for label, note in failures:
            print(f"  {color.red('✗')}  {label}: {note}")
        hint = color.yellow("Run 'smooth-bee doctor' for full diagnostics.")
        print(f"\n{hint}")
        sys.exit(1)


def _fmt_date(iso: str) -> str:
    if not iso:
        return "-"
    try:
        dt = datetime.datetime.fromisoformat(iso)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso[:16]


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text)
    return text[:40].strip("-")


def cmd_new(args) -> None:
    from smooth_bee import onboarding
    onboarding.run_if_needed()
    cfg = config.load()
    description = args.description
    if not description:
        if not sys.stdin.isatty():
            print("Error: description is required when stdin is not a TTY.")
            sys.exit(1)
        description = input("Project description: ").strip()
        if not description:
            print("Error: description cannot be empty.")
            sys.exit(1)
    name = args.name if args.name else _slugify(description)

    project_dir = ws.get_path(name)
    if project_dir.exists():
        print(f"Project '{name}' already exists. Use: smooth-bee resume {name}")
        sys.exit(1)

    print(f"Starting project: {color.cyan_bold(name)}")
    print(f"Description: {description}")

    if args.dry_run:
        print("\n[DRY RUN] Would execute pipeline phases:")
        for i, phase in enumerate(["SPEC (Claude)", "FEASIBILITY (Kimi)", "RESEARCH (Gemini)",
                                    "ARCHITECTURE (Claude)", "CODING (Gemini+Kimi)", "TESTING (Codex)"], 1):
            print(f"  Phase {i}: {phase}")
        print(f"\nWorkspace would be: {project_dir}")
        return

    _check_config(cfg)

    ws.create(name)
    state = st.create(name, description, project_dir)
    memory.register_project(name, str(project_dir))

    from smooth_bee.orchestrator import Orchestrator
    Orchestrator(name, cfg, interactive=args.interactive).run()


def cmd_resume(args) -> None:
    from smooth_bee import onboarding
    onboarding.run_if_needed()
    cfg = config.load()
    _check_config(cfg)
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
    Orchestrator(name, cfg, interactive=args.interactive).run()


def cmd_list(args) -> None:
    projects = ws.list_projects()
    if not projects:
        print("No projects found.")
        return
    w = max((len(p["name"]) for p in projects), default=12)
    w = max(w, 12)
    header = f"{'PROJECT':<{w}}  {'PHASE':<14}  {'STATUS':<8}  {'STARTED':<17}  OUTPUT"
    print(header)
    print("-" * len(header))
    for p in projects:
        gen_dir = Path(p["path"]) / "generated"
        output = str(gen_dir) if gen_dir.exists() else p["path"]
        status = p.get('status', '-')
        # Apply color but preserve column width (color codes are invisible)
        if status == 'done':
            status_col = color.green(status) + " " * (8 - len(status))
        elif status == 'failed':
            status_col = color.red(status) + " " * (8 - len(status))
        else:
            status_col = f"{status:<8}"
        print(
            f"{p['name']:<{w}}  "
            f"{p['phase']:<14}  "
            f"{status_col}  "
            f"{_fmt_date(p.get('created_at', '')):<17}  "
            f"{output}"
        )


def cmd_status(args) -> None:
    name = args.project_name
    project_dir = ws.get_path(name)
    if not project_dir.exists():
        print(f"Project '{name}' not found.")
        sys.exit(1)
    s = st.load(project_dir)
    gen_dir = project_dir / "generated"

    print(f"\nProject:     {color.cyan_bold(s.project_name)}")
    print(f"Description: {s.description}")
    print(f"Phase:       {s.current_phase.value}")
    print(f"Created:     {_fmt_date(s.created_at)}")
    print(f"Updated:     {_fmt_date(s.updated_at)}")
    print(f"Output:      {gen_dir}")

    completed_values = {p.value if isinstance(p, st.Phase) else p for p in s.completed_phases}
    current_val = s.current_phase.value
    print("\nPhases:")
    for phase_val, label in _PHASE_LABELS:
        if phase_val in completed_values:
            marker = color.green("✓")
        elif current_val == phase_val:
            marker = color.yellow("→")
        else:
            marker = " "
        print(f"  {marker}  {label}")

    if s.sections_coded:
        print(f"\nSections coded:  {len(s.sections_coded)}")
    if s.sections_tested:
        print(f"Sections tested: {len(s.sections_tested)}")
    if s.error_info:
        print(f"\n{color.red_bold('Error:')} {s.error_info}")
    print()


def cmd_doctor(args) -> None:
    from smooth_bee import doctor
    ok = doctor.run()
    if not ok:
        sys.exit(1)


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


def cmd_delete(args) -> None:
    name = args.project_name
    project_dir = ws.get_path(name)

    if not project_dir.exists():
        print(f"{color.red_bold('Error:')} Project '{name}' not found.")
        sys.exit(1)

    # Load state info for display
    import json
    phase = "unknown"
    created_at = ""
    status = "unknown"
    state_file = project_dir / "state.json"
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text())
            phase = data.get("current_phase", "unknown")
            created_at = _fmt_date(data.get("created_at", ""))
            if phase == "DONE":
                status = "done"
            elif phase == "FAILED":
                status = "failed"
            else:
                status = "running"
        except Exception:
            pass

    print(f"\nProject to delete:")
    print(f"  Name:    {color.cyan_bold(name)}")
    print(f"  Path:    {project_dir}")
    print(f"  Phase:   {phase}")
    print(f"  Status:  {status}")
    print(f"  Created: {created_at}")
    print()

    if not args.yes:
        if not sys.stdin.isatty():
            print("Error: --yes required when stdin is not a TTY.")
            sys.exit(1)
        answer = input(f"Delete project '{name}'? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return

    try:
        shutil.rmtree(project_dir)
    except OSError as e:
        print(f"{color.red_bold('Error:')} Could not delete {project_dir}: {e}")
        sys.exit(1)

    memory.deregister_project(str(project_dir))
    print(color.green(f"Deleted project '{name}'."))


def cmd_clean(args) -> None:
    projects = ws.list_projects()
    failed = [p for p in projects if p.get("status") == "failed"]

    if not failed:
        print("No failed projects found.")
        return

    print(f"Failed projects ({len(failed)}):")
    for p in failed:
        print(f"  {color.red(p['name']):<30}  {_fmt_date(p.get('created_at', ''))}")
    print()

    if not args.yes:
        if not sys.stdin.isatty():
            print("Error: --yes required when stdin is not a TTY.")
            sys.exit(1)
        answer = input(f"Delete all {len(failed)} failed projects? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return

    for p in failed:
        path = Path(p["path"])
        try:
            if path.exists():
                shutil.rmtree(path)
            memory.deregister_project(p["path"])
            print(f"  Deleted: {p['name']}")
        except OSError as e:
            print(f"  {color.red('Failed:')} {p['name']}: {e}")

    print(color.green(f"\nCleaned {len(failed)} failed projects."))


def main() -> None:
    parser = argparse.ArgumentParser(prog="smooth-bee", description="Multi-AI project orchestrator")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Start a new project")
    p_new.add_argument("description", nargs="?", default=None,
                       help="Project description in plain English (prompted if omitted)")
    p_new.add_argument("--name", help="Override auto-generated project name")
    p_new.add_argument("--dry-run", action="store_true", help="Show pipeline steps without calling agents")
    p_new.add_argument("--interactive", action="store_true",
                       help="Pause after each phase to review output before continuing")
    p_new.set_defaults(func=cmd_new)

    p_resume = sub.add_parser("resume", help="Resume an interrupted project")
    p_resume.add_argument("project_name")
    p_resume.add_argument("--phase", help="Restart from this phase (SPEC, FEASIBILITY, etc.)")
    p_resume.add_argument("--interactive", action="store_true",
                          help="Pause after each phase to review output before continuing")
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

    p_doctor = sub.add_parser("doctor", help="Check environment and configuration")
    p_doctor.set_defaults(func=cmd_doctor)

    p_delete = sub.add_parser("delete", help="Delete a project and its workspace")
    p_delete.add_argument("project_name")
    p_delete.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    p_delete.set_defaults(func=cmd_delete)

    p_clean = sub.add_parser("clean", help="Delete all failed projects")
    p_clean.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    p_clean.set_defaults(func=cmd_clean)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
