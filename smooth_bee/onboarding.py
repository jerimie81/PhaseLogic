"""
First-launch onboarding: collect API keys and explain smooth-bee.

Runs automatically before `new` and `resume` when any integration is missing.
Saves entered keys to ~/.config/smooth-bee/config.toml.
"""

import subprocess
import sys
from pathlib import Path

from smooth_bee import color
from smooth_bee import config as cfg_mod


_PITCH = """
  Have an idea for an app but not sure how to build it?
  smooth-bee turns your vision into real, working software — automatically.

  You describe what you want in plain English.
  smooth-bee coordinates a team of specialized AI agents that do the rest:

    {claude}  writes the specification and designs the architecture
    {gemini}  researches the best tools, frameworks, and approach
    {kimi}    checks feasibility and generates the source code
    {codex}   writes tests, finds bugs, and audits for security

  The result is a complete, professional-grade project — structured,
  documented, and ready to publish. No coding experience required.
  No computer science degree needed. If you can describe your dream,
  smooth-bee can build it.

  To start a project:

    smooth-bee new "describe your app idea here"

"""


def run_if_needed() -> None:
    """Run the setup wizard if any required integration is missing."""
    cfg = cfg_mod.load()
    checks = cfg_mod.validate(cfg)
    if all(ok for _, ok, _ in checks):
        return
    _run(cfg)


def _run(cfg: cfg_mod.Config) -> None:
    _banner()
    print(color.yellow("  One or more AI integrations need to be set up before you can build.\n"))
    print(f"  {color.cyan_bold('Step 1 of 4 — Claude (specification + architecture)')}")
    print("  Claude Code is a free CLI tool from Anthropic.")
    print("  It uses browser-based login — no API key needed.\n")

    _setup_claude()

    print(f"\n  {color.cyan_bold('Step 2 of 4 — Google Gemini (research + planning)')}")
    gemini_key = _prompt_key(
        display_name="Gemini",
        env_var="GEMINI_API_KEY",
        get_key_url="https://aistudio.google.com/app/apikey",
        current=cfg.gemini_api_key,
        hint="Free tier available — no credit card required.",
    )

    print(f"\n  {color.cyan_bold('Step 3 of 4 — Moonshot Kimi (feasibility + code generation)')}")
    kimi_key = _prompt_key(
        display_name="Kimi",
        env_var="KIMI_API_KEY",
        get_key_url="https://platform.moonshot.cn/console/api-keys",
        current=cfg.kimi_api_key,
        hint="Requires a Moonshot account (free registration).",
    )

    print(f"\n  {color.cyan_bold('Step 4 of 4 — OpenAI (testing + security review)')}")
    openai_key = _prompt_key(
        display_name="OpenAI",
        env_var="OPENAI_API_KEY",
        get_key_url="https://platform.openai.com/api-keys",
        current=cfg.openai_api_key,
        hint="Requires an OpenAI account. Usage is billed per run.",
    )

    # Save any newly entered keys to user config
    new_keys = {}
    if gemini_key:
        new_keys["gemini_api_key"] = gemini_key
    if kimi_key:
        new_keys["kimi_api_key"] = kimi_key
    if openai_key:
        new_keys["openai_api_key"] = openai_key

    if new_keys:
        _write_user_config(cfg, new_keys)
        saved_path = Path.home() / ".config" / "smooth-bee" / "config.toml"
        print(color.green(f"\n  Keys saved → {saved_path}"))

    # Final status check
    cfg2 = cfg_mod.load()
    checks2 = cfg_mod.validate(cfg2)
    still_missing = [label for label, ok, _ in checks2 if not ok]

    print()
    if not still_missing:
        _ready_banner()
    else:
        print(color.yellow(f"  Still missing: {', '.join(still_missing)}"))
        print("  You can complete setup anytime — run:  smooth-bee doctor\n")
        if _confirm("  Continue anyway with available agents? [y/N]: "):
            return
        sys.exit(0)


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------

def _setup_claude() -> None:
    ok = _claude_in_path()
    if ok:
        print(color.green("  ✓  Claude CLI is installed and ready."))
        return

    print(color.yellow("  ✗  Claude CLI not found in PATH."))
    if not sys.stdin.isatty():
        print("  Install Claude Code from: https://claude.ai/code")
        return

    print("  Install Claude Code from: https://claude.ai/code")
    print("  Once installed, run:  claude auth login  (opens your browser)\n")

    if _confirm("  Run browser login now? [y/N]: "):
        _run_claude_login()
    else:
        print(color.yellow("  Skipping — remember to install and authenticate Claude before running."))


def _run_claude_login() -> None:
    try:
        result = subprocess.run(["claude", "auth", "login"])
        if result.returncode == 0 and _claude_in_path():
            print(color.green("  ✓  Claude authenticated successfully."))
        else:
            print(color.yellow("  Claude login may not have completed. Run 'claude auth login' manually."))
    except FileNotFoundError:
        print(color.red("  Claude CLI still not found — install it first from https://claude.ai/code"))


def _prompt_key(
    display_name: str,
    env_var: str,
    get_key_url: str,
    current: str,
    hint: str,
) -> str:
    if current:
        print(color.green(f"  ✓  {display_name} API key already configured."))
        return ""

    print(f"  Get your API key at: {get_key_url}")
    print(f"  {hint}")
    print(f"  (or set the {env_var} environment variable instead)\n")

    if not sys.stdin.isatty():
        return ""

    try:
        key = input(f"  Paste your {display_name} API key (Enter to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""

    if key:
        print(color.green(f"  ✓  {display_name} key accepted."))
    else:
        print(color.yellow(f"  Skipped — you can add this later in config.toml or via {env_var}."))
    return key


def _write_user_config(cfg: cfg_mod.Config, updates: dict) -> None:
    user_cfg_path = Path.home() / ".config" / "smooth-bee" / "config.toml"
    user_cfg_path.parent.mkdir(parents=True, exist_ok=True)

    gemini_key = updates.get("gemini_api_key", cfg.gemini_api_key)
    kimi_key   = updates.get("kimi_api_key",   cfg.kimi_api_key)
    openai_key = updates.get("openai_api_key",  cfg.openai_api_key)

    content = (
        f'[claude]\n'
        f'model = "{cfg.claude_model}"\n'
        f'\n'
        f'[gemini]\n'
        f'api_key = "{gemini_key}"\n'
        f'model = "{cfg.gemini_model}"\n'
        f'\n'
        f'[kimi]\n'
        f'api_key = "{kimi_key}"\n'
        f'model = "{cfg.kimi_model}"\n'
        f'base_url = "{cfg.kimi_base_url}"\n'
        f'\n'
        f'[codex]\n'
        f'api_key = "{openai_key}"\n'
        f'model = "{cfg.codex_model}"\n'
        f'\n'
        f'[orchestration]\n'
        f'timeout_seconds = {cfg.timeout_seconds}\n'
        f'max_retries = {cfg.max_retries}\n'
        f'retry_backoff_base = {cfg.retry_backoff_base}\n'
    )
    user_cfg_path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------

def _banner() -> None:
    sep = color.cyan_bold("=" * 54)
    title = color.cyan_bold("  smooth-bee  —  setup wizard")
    print(f"\n{sep}\n{title}\n{sep}\n")


def _ready_banner() -> None:
    sep = color.cyan_bold("━" * 54)
    print(sep)
    print(color.cyan_bold("  smooth-bee is ready. Here's how it works:\n"))
    print(_PITCH.format(
        claude=color.cyan_bold("Claude "),
        gemini=color.cyan_bold("Gemini "),
        kimi=color.cyan_bold("Kimi   "),
        codex=color.cyan_bold("Codex  "),
    ))
    print(sep)
    print()


def _claude_in_path() -> bool:
    try:
        r = subprocess.run(["claude", "--version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _confirm(prompt: str) -> bool:
    if not sys.stdin.isatty():
        return False
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False
