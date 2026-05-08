import subprocess
import sys

from smooth_bee import config as cfg_mod, memory, paths, color


def run() -> bool:
    cfg = cfg_mod.load()
    checks: list[tuple[str, bool, str, str]] = []  # label, ok, detail, hint

    # Python version
    vi = sys.version_info
    ok = vi >= (3, 11)
    checks.append(("Python >= 3.11", ok, f"{vi.major}.{vi.minor}.{vi.micro}", "upgrade Python" if not ok else ""))

    # Jinja2
    try:
        import importlib.metadata
        ver = importlib.metadata.version("jinja2")
        ok = True
    except Exception:
        ok = False
        ver = "not installed"
    checks.append(("Jinja2", ok, ver, "pip install jinja2" if not ok else ""))

    # config.toml
    cfg_path = paths.config_path()
    ok = cfg_path.exists()
    checks.append(("config.toml", ok, str(cfg_path), f"create at {cfg_path}" if not ok else ""))

    # Claude CLI
    try:
        r = subprocess.run(["claude", "--version"], capture_output=True, timeout=5)
        ok = r.returncode == 0
        detail = r.stdout.decode().strip().split("\n")[0] if ok else "non-zero exit"
    except FileNotFoundError:
        ok = False
        detail = "not in PATH"
    except subprocess.TimeoutExpired:
        ok = False
        detail = "timed out"
    checks.append(("Claude CLI", ok, detail, "install Claude Code from https://claude.ai/code" if not ok else ""))

    # Gemini API key
    ok = bool(cfg.gemini_api_key)
    checks.append(("Gemini API key", ok, "present" if ok else "missing",
                   "set GEMINI_API_KEY or [gemini] api_key in config.toml" if not ok else ""))

    # Kimi API key
    ok = bool(cfg.kimi_api_key)
    checks.append(("Kimi API key", ok, "present" if ok else "missing",
                   "set KIMI_API_KEY or [kimi] api_key in config.toml" if not ok else ""))

    # Codex/OpenAI key
    ok = bool(cfg.openai_api_key)
    checks.append(("Codex/OpenAI key", ok, "present" if ok else "missing",
                   "set OPENAI_API_KEY, [codex] api_key, or ~/.codex/API-key" if not ok else ""))

    # Workspace writable
    workspace = paths.workspace_root()
    workspace.mkdir(parents=True, exist_ok=True)
    try:
        probe = workspace / ".phaselogic-doctor"
        probe.touch()
        probe.unlink()
        ok = True
        detail = str(workspace)
    except OSError as e:
        ok = False
        detail = str(e)
    checks.append(("Workspace writable", ok, detail, "check directory permissions" if not ok else ""))

    w_label = max(len(c[0]) for c in checks)
    w_detail = max(len(c[2]) for c in checks)
    header = f"  {'CHECK':<{w_label}}  {'STATUS':<8}  DETAIL"
    div = "-" * (len(header) + w_detail)

    print(f"\nPhaseLogic doctor\n{div}")
    print(header)
    print(f"  {'-'*w_label}  {'-'*8}  {'-'*w_detail}")

    all_ok = True
    for label, ok, detail, hint in checks:
        if ok:
            status = color.green("✓ ok  ")
        else:
            status = color.red_bold("✗ FAIL")
        print(f"  {label:<{w_label}}  {status}  {detail}")
        if not ok:
            print(f"  {' '*w_label}           {color.yellow(f'→ {hint}')}")
            all_ok = False

    print()
    if all_ok:
        print(color.green("All checks passed. PhaseLogic is ready."))
    else:
        print(color.red("Some checks failed. Fix the issues above before running PhaseLogic."))

    # Agent performance stats from memory.db
    stats = memory.load_agent_stats()
    if stats:
        print(f"\n{'─'*42}")
        print("  Agent performance (lifetime):")
        print(f"  {'AGENT':<12}  {'CALLS':>5}  {'AVG':>8}  {'FAILS':>5}")
        print(f"  {'─'*12}  {'─'*5}  {'─'*8}  {'─'*5}")
        for agent_name, s in sorted(stats.items()):
            calls = s.get("calls", 0)
            avg_s = s.get("avg_s", 0.0)
            fails = s.get("failures", 0)
            avg_str = f"{avg_s:.1f}s" if calls >= 3 else "—"
            fail_str = color.red(str(fails)) if fails > 0 else color.green("0")
            print(f"  {agent_name:<12}  {calls:>5}  {avg_str:>8}  {fail_str}")
        print()

    return all_ok
