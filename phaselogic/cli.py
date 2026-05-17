import argparse
import datetime
import re
import shutil
import subprocess
import sys
from pathlib import Path

from phaselogic import color, config, state as st, workspace as ws, memory

_PHASE_LABELS = [
    ("SPEC",         "SPEC — specification"),
    ("FEASIBILITY",  "FEASIBILITY — feasibility check"),
    ("RESEARCH",     "RESEARCH — research & planning"),
    ("ARCHITECTURE", "ARCHITECTURE — design"),
    ("CODING",       "CODING — code generation"),
    ("TESTING",      "TESTING — test generation"),
    ("REPAIR",       "REPAIR — quality gate repair needed"),
]


def _check_config(cfg) -> None:
    checks = config.validate(cfg)
    failures = [(label, note) for label, ok, note in checks if not ok]
    if failures:
        print(color.red_bold("PhaseLogic: configuration error(s) — cannot start pipeline:"))
        for label, note in failures:
            print(f"  {color.red('✗')}  {label}: {note}")
        hint = color.yellow("Run 'phaselogic doctor' for full diagnostics.")
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
    from phaselogic import onboarding, intake as intake_mod
    if not args.dry_run:
        onboarding.run_if_needed()
    cfg = config.load()

    # Collect description — from arg, or prompt if at a TTY
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
        print(f"Project '{name}' already exists. Use: phaselogic resume {name}")
        sys.exit(1)

    # Run intake interview (respects --aggressiveness flag or config default)
    agg = args.aggressiveness if args.aggressiveness is not None else cfg.intake_aggressiveness
    brief = intake_mod.run(description, aggressiveness=agg)

    if not intake_mod.confirm_assumptions(brief, interactive=args.interactive):
        sys.exit(0)

    print(f"\nStarting project: {color.cyan_bold(name)}")
    print(f"Description: {description}")

    if args.dry_run:
        print("\n[DRY RUN] Would execute pipeline phases:")
        for i, phase in enumerate(["SPEC", "FEASIBILITY", "RESEARCH",
                                    "ARCHITECTURE", "CODING", "TESTING"], 1):
            print(f"  Phase {i}: {phase}")
        print(f"\nWorkspace would be: {project_dir}")
        if brief.get("required_toolchains"):
            print(f"Required toolchains: {', '.join(brief['required_toolchains'])}")
        return

    _check_config(cfg)

    ws.create(name)
    state = st.create(name, description, project_dir)
    ws.write_artifact(name, "phase0_intake.json", brief)
    memory.register_project(name, str(project_dir))

    from phaselogic.orchestrator import Orchestrator
    Orchestrator(name, cfg, interactive=args.interactive).run()


def cmd_resume(args) -> None:
    from phaselogic import onboarding
    onboarding.run_if_needed()
    cfg = config.load()
    _check_config(cfg)
    name = args.project_name
    project_dir = ws.get_path(name)

    if not project_dir.exists():
        print(f"Project '{name}' not found. Use: phaselogic new \"<description>\"")
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

    from phaselogic.orchestrator import Orchestrator
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
    from phaselogic import doctor
    ok = doctor.run()
    if not ok:
        sys.exit(1)


def cmd_integrations(args) -> None:
    from phaselogic.connectors import get_connector, list_connectors

    if args.integration_command == "list":
        print("Available integrations:")
        for connector in list_connectors():
            status = connector.health_check()
            marker = color.green("✓") if status.connected else color.yellow("!")
            print(f"  {marker}  {connector.name:<12} {connector.display_name:<20} {status.detail}")
        return

    connector = get_connector(args.name)
    if args.integration_command == "status":
        status = connector.health_check()
    elif args.integration_command == "connect":
        status = connector.connect()
    else:
        raise ValueError(f"Unknown integrations command: {args.integration_command}")

    marker = color.green("connected") if status.connected else color.red("unavailable")
    print(f"\nIntegration: {connector.display_name} ({connector.name})")
    print(f"Status:      {marker}")
    print(f"Detail:      {status.detail}")
    if status.capabilities:
        print("\nCapabilities:")
        for cap in status.capabilities:
            perms = ", ".join(p.value for p in cap.permissions) or "none"
            print(f"  - {cap.name:<12} {cap.description} [{perms}]")
    print()


def cmd_agents(args) -> None:
    from phaselogic import agent_profiles

    project_dir = Path(args.project).expanduser() if getattr(args, "project", None) else None

    if args.agent_command == "create-template":
        try:
            path = agent_profiles.create_template(args.name)
        except (FileExistsError, OSError) as e:
            print(f"{color.red_bold('Error:')} {e}")
            sys.exit(1)
        print(color.green(f"Created agent profile template: {path}"))
        return

    profiles = agent_profiles.load_profiles(project_dir)

    if args.agent_command == "list":
        if not profiles:
            print("No agent profiles found.")
            return
        print("Agent profiles:")
        for profile in sorted(profiles.values(), key=lambda p: p.name):
            source = f"  ({profile.source_path})" if profile.source_path else ""
            print(f"  {profile.name:<20} {profile.provider:<10} {profile.model}{source}")
        return

    if args.agent_command == "show":
        profile = profiles.get(args.name)
        if profile is None:
            print(f"Agent profile '{args.name}' not found.")
            sys.exit(1)
        print(profile.to_toml(), end="")
        return

    if args.agent_command == "validate":
        target = Path(args.target).expanduser()
        if target.exists():
            profile = agent_profiles.load_profile(target)
        else:
            profile = profiles.get(args.target)
            if profile is None:
                print(f"Agent profile '{args.target}' not found.")
                sys.exit(1)
        errors = profile.validation_errors()
        if errors:
            print(color.red_bold(f"Agent profile '{profile.name}' is invalid:"))
            for err in errors:
                print(f"  - {err}")
            sys.exit(1)
        print(color.green(f"Agent profile '{profile.name}' is valid."))
        return

    if args.agent_command == "test":
        profile = profiles.get(args.name)
        if profile is None:
            print(f"Agent profile '{args.name}' not found.")
            sys.exit(1)
        
        print(f"Testing connectivity for '{profile.name}' ({profile.provider}/{profile.model})...")
        ok, msg = profile.test()
        if ok:
            print(f"{color.green('✓')} {msg}")
        else:
            print(f"{color.red('✗')} {msg}")
            sys.exit(1)
        return

    raise ValueError(f"Unknown agents command: {args.agent_command}")


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


def cmd_publish(args) -> None:
    from phaselogic import publish
    from phaselogic.connectors.github import GitHubConnector

    name = args.project_name
    project_dir = ws.get_path(name)
    generated_dir = ws.get_generated_dir(name)
    if not project_dir.exists():
        print(f"{color.red_bold('Error:')} Project '{name}' not found.")
        sys.exit(1)
    if not generated_dir.exists():
        print(f"{color.red_bold('Error:')} Generated output not found: {generated_dir}")
        sys.exit(1)

    if args.provider != "github":
        print(f"{color.red_bold('Error:')} Unsupported publish provider: {args.provider}")
        sys.exit(1)
    if not args.repo:
        print(f"{color.red_bold('Error:')} --repo owner/name is required for GitHub publishing.")
        sys.exit(1)

    branch = args.branch or f"phaselogic/{name}"
    title = args.title or f"PhaseLogic generated project: {name}"
    body = args.body or (
        f"Generated by PhaseLogic from project `{name}`.\n\n"
        "This PR was created after local preflight checks."
    )

    preflight = publish.build_preflight(name, args.repo, branch, args.base)
    print(publish.format_preflight(preflight))

    if preflight.blocks_publish and not args.allow_secret_findings:
        print()
        print(color.red_bold("Publish blocked: secret-looking values were found."))
        print("Review publish_preflight.json or rerun with --allow-secret-findings for false positives.")
        sys.exit(1)

    if args.dry_run:
        print(color.yellow("\nDry run complete. No GitHub changes were made."))
        return

    if not args.yes:
        if not sys.stdin.isatty():
            print("Error: --yes required when stdin is not a TTY.")
            sys.exit(1)
        answer = input("\nPush branch and open GitHub PR? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return

    connector = GitHubConnector()
    status = connector.health_check()
    if not status.connected:
        print(f"{color.red_bold('Error:')} GitHub integration unavailable: {status.detail}")
        sys.exit(1)

    try:
        result = connector.publish(
            generated_dir=generated_dir,
            repo=args.repo,
            branch=branch,
            base=args.base,
            title=title,
            body=body,
            watch_ci=args.watch_ci,
        )
    except Exception as e:
        print(f"{color.red_bold('Error:')} Publish failed: {e}")
        sys.exit(1)

    print(color.green(f"\nPull request: {result.pr_url}"))
    if result.ci_output:
        print("\nCI status:")
        print(result.ci_output)


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
            elif phase == "REPAIR":
                status = "needs-repair"
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
    parser = argparse.ArgumentParser(prog="phaselogic", description="Multi-AI project orchestrator")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Start a new project")
    p_new.add_argument("description", nargs="?", default=None,
                       help="Project description in plain English (prompted if omitted)")
    p_new.add_argument("--name", help="Override auto-generated project name")
    p_new.add_argument("--dry-run", action="store_true", help="Show pipeline steps without calling agents")
    p_new.add_argument("--interactive", action="store_true",
                       help="Pause after each phase to review output before continuing")
    p_new.add_argument("--aggressiveness", type=int, choices=range(1, 6), metavar="1-5",
                       default=None,
                       help="Interview depth: 1=minimal  3=balanced (default)  5=exhaustive")
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

    p_publish = sub.add_parser("publish", help="Publish generated output through a lifecycle connector")
    p_publish.add_argument("project_name")
    p_publish.add_argument("--provider", default="github", choices=["github"])
    p_publish.add_argument("--repo", help="GitHub repository in owner/name form")
    p_publish.add_argument("--branch", help="Branch to push (default: phaselogic/<project>)")
    p_publish.add_argument("--base", default="main", help="Base branch for the pull request")
    p_publish.add_argument("--title", help="Pull request title")
    p_publish.add_argument("--body", help="Pull request body")
    p_publish.add_argument("--allow-secret-findings", action="store_true",
                           help="Allow publish when the preflight secret scan has findings")
    p_publish.add_argument("--watch-ci", action="store_true", help="Wait for GitHub PR checks")
    p_publish.add_argument("--dry-run", action="store_true", help="Run preflight only")
    p_publish.add_argument("--yes", "-y", action="store_true", help="Skip publish confirmation")
    p_publish.set_defaults(func=cmd_publish)

    p_integrations = sub.add_parser("integrations", help="Manage lifecycle integrations")
    si = p_integrations.add_subparsers(dest="integration_command", required=True)
    si.add_parser("list", help="List available integrations").set_defaults(func=cmd_integrations)
    for cmd_name in ("status", "connect"):
        p = si.add_parser(cmd_name, help=f"{cmd_name.title()} an integration")
        p.add_argument("name", help="Integration name, e.g. git")
        p.set_defaults(func=cmd_integrations)

    p_agents = sub.add_parser("agents", help="Manage saved agent profiles")
    sa = p_agents.add_subparsers(dest="agent_command", required=True)
    p_agents_list = sa.add_parser("list", help="List agent profiles")
    p_agents_list.add_argument("--project", help="Include project-local .phaselogic/agents profiles")
    p_agents_list.set_defaults(func=cmd_agents)
    p_agents_show = sa.add_parser("show", help="Show an agent profile")
    p_agents_show.add_argument("name")
    p_agents_show.add_argument("--project", help="Include project-local .phaselogic/agents profiles")
    p_agents_show.set_defaults(func=cmd_agents)
    p_agents_validate = sa.add_parser("validate", help="Validate an agent profile by name or path")
    p_agents_validate.add_argument("target")
    p_agents_validate.add_argument("--project", help="Include project-local .phaselogic/agents profiles")
    p_agents_validate.set_defaults(func=cmd_agents)
    p_agents_test = sa.add_parser("test", help="Test connectivity of an agent profile")
    p_agents_test.add_argument("name")
    p_agents_test.add_argument("--project", help="Include project-local .phaselogic/agents profiles")
    p_agents_test.set_defaults(func=cmd_agents)
    p_agents_template = sa.add_parser("create-template", help="Create an editable agent profile template")
    p_agents_template.add_argument("name")
    p_agents_template.set_defaults(func=cmd_agents)

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
