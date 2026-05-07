import subprocess
import sys

from smooth_bee import config as cfg_mod, paths


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
        probe = workspace / ".smooth-bee-doctor"
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

    print(f"\nsmooth-bee doctor\n{div}")
    print(header)
    print(f"  {'-'*w_label}  {'-'*8}  {'-'*w_detail}")

    all_ok = True
    for label, ok, detail, hint in checks:
        status = "✓ ok  " if ok else "✗ FAIL"
        print(f"  {label:<{w_label}}  {status}  {detail}")
        if not ok:
            print(f"  {' '*w_label}           → {hint}")
            all_ok = False

    print()
    if all_ok:
        print("All checks passed. smooth-bee is ready.\n")
    else:
        print("Some checks failed. Fix the issues above before running smooth-bee.\n")

    return all_ok
