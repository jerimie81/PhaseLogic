"""
Pre-pipeline intake interview.

Asks the user targeted questions to understand what they want to build,
derives the required toolchains, checks availability, and offers to install
missing tools. Returns a structured brief that enriches the Phase 1 prompt.

Aggressiveness levels:
  1 — minimal    : platform + category only (2 questions)
  2 — light      : adds purpose + audience (4 questions)
  3 — balanced   : adds UI + data + language (7 questions, default)
  4 — thorough   : adds connectivity + integrations + priorities (11 questions)
  5 — exhaustive : adds sensitivity + scale + monetization + errors (15 questions)
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional

from smooth_bee import color

# ---------------------------------------------------------------------------
# Question bank
# ---------------------------------------------------------------------------

_QUESTIONS = [
    # ── wave 1 (aggressiveness ≥ 1) ─────────────────────────────────────────
    {
        "id": "app_category",
        "wave": 1,
        "text": "What kind of application do you want to build?",
        "choices": [
            ("mobile",   "Mobile app          — runs on a phone or tablet"),
            ("web",      "Web application     — runs in a browser"),
            ("desktop",  "Desktop application — runs on a computer"),
            ("cli",      "Command-line tool   — runs in a terminal"),
            ("service",  "Background service  — API, daemon, or bot"),
            ("game",     "Game"),
            ("other",    "Other / not sure yet"),
        ],
        "free_text_label": None,
    },
    {
        "id": "target_platforms",
        "wave": 1,
        "text": "Which platforms should the app run on / what should it produce?",
        "multi": True,
        "choices": [
            ("android",  "Android phone/tablet (APK)"),
            ("ios",      "iPhone/iPad (iOS)  ⚠  requires a Mac to compile"),
            ("linux",    "Linux (binary or .deb package)"),
            ("windows",  "Windows (.exe or .msi installer)"),
            ("macos",    "macOS (.app or .dmg)  ⚠  requires a Mac to compile"),
            ("web",      "Web browser — any device"),
            ("server",   "Server / cloud  (Docker, self-hosted)"),
            ("unsure",   "Not sure — let smooth-bee decide"),
        ],
    },

    # ── wave 2 (aggressiveness ≥ 2) ─────────────────────────────────────────
    {
        "id": "core_purpose",
        "wave": 2,
        "text": "In one sentence — what is the single most important thing this app must do?",
        "free_text_label": "Describe it",
    },
    {
        "id": "target_audience",
        "wave": 2,
        "text": "Who will be using this app?",
        "choices": [
            ("personal",      "Just me          — personal tool, no sharing needed"),
            ("small_group",   "Friends / family / small team"),
            ("public",        "General public   — strangers, app store, wide release"),
            ("professional",  "Businesses / professionals / enterprise"),
        ],
    },

    # ── wave 3 (aggressiveness ≥ 3) ─────────────────────────────────────────
    {
        "id": "ui_type",
        "wave": 3,
        "text": "What kind of interface should the app have?",
        "choices": [
            ("none",    "No interface     — runs silently, API, background worker"),
            ("cli",     "Text terminal    — command-line, text menus"),
            ("simple",  "Simple window    — forms, buttons, basic GUI"),
            ("rich",    "Rich UI          — visual design, images, animations"),
            ("web_ui",  "Web interface    — browser-based, any device"),
            ("mobile",  "Mobile touch     — swipe, tap, mobile-first design"),
        ],
    },
    {
        "id": "data_storage",
        "wave": 3,
        "text": "Does the app need to store data?",
        "choices": [
            ("none",       "No data storage  — stateless or disposable"),
            ("files",      "Files            — save/load documents, images, settings"),
            ("local_db",   "Local database   — embedded, works offline (SQLite)"),
            ("cloud_db",   "Cloud database   — sync across devices, multi-user"),
            ("accounts",   "User accounts    — login, profiles, per-user data"),
        ],
    },
    {
        "id": "language",
        "wave": 3,
        "text": "Preferred programming language? (smooth-bee will choose if unsure)",
        "choices": [
            ("python",      "Python          — great for scripts, data, web backends"),
            ("typescript",  "JavaScript/TS   — web front-ends and Node.js back-ends"),
            ("kotlin",      "Kotlin          — modern Android development"),
            ("java",        "Java            — Android, enterprise, cross-platform"),
            ("rust",        "Rust            — fast, memory-safe, systems programming"),
            ("go",          "Go              — simple, fast, ideal for services/APIs"),
            ("swift",       "Swift           — Apple platforms only (iOS/macOS)"),
            ("auto",        "Let smooth-bee choose the best fit"),
        ],
    },

    # ── wave 4 (aggressiveness ≥ 4) ─────────────────────────────────────────
    {
        "id": "connectivity",
        "wave": 4,
        "text": "Does the app need internet access?",
        "choices": [
            ("offline",   "Fully offline   — no internet required"),
            ("optional",  "Optional        — works offline, syncs when connected"),
            ("required",  "Always on       — real-time data, streaming, live updates"),
            ("is_server", "It IS the service — server, API, web app"),
        ],
    },
    {
        "id": "integrations",
        "wave": 4,
        "text": "Should the app connect to any existing services or platforms?",
        "multi": True,
        "choices": [
            ("none",      "None — standalone app"),
            ("social",    "Social login (Google, Facebook, GitHub)"),
            ("payments",  "Payment processing (Stripe, PayPal)"),
            ("maps",      "Maps / location (Google Maps, OpenStreetMap)"),
            ("messaging", "Messaging (email, SMS, push notifications)"),
            ("ai",        "AI / LLM features (beyond smooth-bee itself)"),
            ("custom",    "A specific service — I'll describe it"),
        ],
        "allow_custom": True,
    },
    {
        "id": "must_have",
        "wave": 4,
        "text": "What is the single feature that would make this app absolutely perfect?",
        "free_text_label": "Describe it",
    },
    {
        "id": "must_not",
        "wave": 4,
        "text": "Is there anything the app should specifically NOT include or do?",
        "free_text_label": "Describe (or press Enter to skip)",
        "optional": True,
    },

    # ── wave 5 (aggressiveness ≥ 5) ─────────────────────────────────────────
    {
        "id": "sensitive_data",
        "wave": 5,
        "text": "Will the app handle sensitive information?",
        "choices": [
            ("none",       "No sensitive data"),
            ("personal",   "Personal info (names, addresses, photos)"),
            ("health",     "Health or medical data"),
            ("financial",  "Financial or payment data"),
            ("legal",      "Government or legal documents"),
        ],
    },
    {
        "id": "scale",
        "wave": 5,
        "text": "How many people will use this app at the same time?",
        "choices": [
            ("solo",       "Just me (1 person)"),
            ("small",      "Small group (2–20 people)"),
            ("medium",     "Hundreds of users"),
            ("large",      "Thousands or more"),
            ("unknown",    "Unknown / doesn't matter yet"),
        ],
    },
    {
        "id": "monetization",
        "wave": 5,
        "text": "Will you charge money for this app?",
        "choices": [
            ("free",       "Free — personal use or open source"),
            ("sub",        "Subscription — monthly or annual fee"),
            ("one_time",   "One-time purchase"),
            ("iap",        "In-app purchases or premium features"),
            ("ads",        "Ad-supported"),
            ("unsure",     "Not decided yet"),
        ],
    },
    {
        "id": "error_handling",
        "wave": 5,
        "text": "What should happen when something goes wrong inside the app?",
        "choices": [
            ("friendly",  "Show a friendly error message to the user"),
            ("log",       "Log it quietly and keep running"),
            ("crash",     "Crash with a detailed error (developer tool)"),
            ("retry",     "Retry automatically"),
            ("notify",    "Alert me somehow (email, notification)"),
        ],
    },
    {
        "id": "extra_context",
        "wave": 5,
        "text": "Anything else smooth-bee should know to build this exactly right?",
        "free_text_label": "Extra context (or press Enter to skip)",
        "optional": True,
    },
]


# ---------------------------------------------------------------------------
# Toolchain definitions
# ---------------------------------------------------------------------------

_TOOLCHAINS: dict[str, dict] = {
    "java17": {
        "name": "Java 17 JDK",
        "check_cmd": ["java", "-version"],
        "check_env": "JAVA_HOME",
        "check_paths": [str(Path.home() / ".gemini/tools/openjdk-17/bin/java")],
        "apt": "openjdk-17-jdk",
        "note": "Required for Android and JVM-based projects",
    },
    "android_sdk": {
        "name": "Android SDK",
        "check_cmd": None,
        "check_paths": [str(Path.home() / "Android/Sdk/platform-tools/adb")],
        "manual": "https://developer.android.com/studio#downloads  (Command line tools)",
        "note": "Required to compile Android APKs",
    },
    "gradle": {
        "name": "Gradle",
        "check_cmd": ["gradle", "--version"],
        "apt": "gradle",
        "note": "Build system for Android and JVM projects",
    },
    "nodejs": {
        "name": "Node.js + npm",
        "check_cmd": ["node", "--version"],
        "apt": "nodejs npm",
        "note": "Required for JavaScript/TypeScript projects",
    },
    "rust": {
        "name": "Rust (rustc + cargo)",
        "check_cmd": ["rustc", "--version"],
        "install_cmd": 'curl --proto \'=https\' --tlsv1.2 -sSf https://sh.rustup.rs | sh',
        "note": "Required for Rust projects",
    },
    "golang": {
        "name": "Go",
        "check_cmd": ["go", "version"],
        "apt": "golang-go",
        "note": "Required for Go projects",
    },
    "mingw": {
        "name": "MinGW-w64 (Windows cross-compiler)",
        "check_cmd": ["x86_64-w64-mingw32-gcc", "--version"],
        "apt": "mingw-w64",
        "note": "Required for Windows .exe cross-compilation from Linux",
    },
    "docker": {
        "name": "Docker",
        "check_cmd": ["docker", "--version"],
        "apt": "docker.io",
        "note": "Required for container-based deployment",
    },
    "dpkg_dev": {
        "name": "Debian packaging tools",
        "check_cmd": ["dpkg-buildpackage", "--version"],
        "apt": "dpkg-dev debhelper fakeroot",
        "note": "Required to produce .deb packages",
    },
    "python3": {
        "name": "Python 3.11+",
        "check_cmd": ["python3", "--version"],
        "note": "Required for Python projects (usually pre-installed)",
    },
}


def _derive_toolchains(brief: dict) -> list[str]:
    needed: set[str] = set()
    platforms = set(brief.get("target_platforms", []))
    language = brief.get("language", "auto")
    category = brief.get("app_category", "")
    data = brief.get("data_storage", "")
    connectivity = brief.get("connectivity", "")

    # Language-based
    if language == "python":
        needed.add("python3")
    elif language in ("typescript", "javascript"):
        needed.add("nodejs")
    elif language in ("kotlin", "java"):
        needed.add("java17")
    elif language == "rust":
        needed.add("rust")
    elif language == "go":
        needed.add("golang")

    # Platform-based
    if "android" in platforms:
        needed.update(["java17", "android_sdk", "gradle"])
    if "windows" in platforms:
        needed.add("mingw")
    if "linux" in platforms and category not in ("web", "service"):
        needed.add("dpkg_dev")
    if "web" in platforms or category in ("web", "service"):
        if language not in ("python", "rust", "go"):
            needed.add("nodejs")
    if "server" in platforms or connectivity == "is_server":
        needed.add("docker")

    # Category fallback when language is "auto"
    if language == "auto":
        if category == "cli":
            needed.add("python3")
        elif category in ("web", "service"):
            needed.add("nodejs")
        elif category == "mobile" and "android" in platforms:
            needed.update(["java17", "android_sdk", "gradle"])

    return sorted(needed)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(description: str, aggressiveness: int = 3) -> dict:
    """
    Run the intake interview. Returns a brief dict to be stored as
    phase0_intake.json and injected into the Phase 1 prompt.
    """
    agg = max(1, min(5, aggressiveness))
    print()
    _section_header("Project Discovery Interview")
    print(
        f"  {color.yellow(f'Aggressiveness: {agg}/5')}  "
        f"{'·' * agg}{'·' * (5 - agg)}\n"
        f"  Answer each question — numbers for choices, or type freely.\n"
        f"  Press Enter on any optional question to skip it.\n"
    )

    brief: dict = {"raw_description": description}
    custom_notes: list[str] = []

    for q in _QUESTIONS:
        if q["wave"] > agg:
            continue
        _ask_question(q, brief, custom_notes)

    brief["additional_context"] = "\n".join(custom_notes) if custom_notes else ""
    brief["required_toolchains"] = _derive_toolchains(brief)

    _toolchain_check(brief["required_toolchains"])

    return brief


# ---------------------------------------------------------------------------
# Question rendering
# ---------------------------------------------------------------------------

def _ask_question(q: dict, brief: dict, custom_notes: list) -> None:
    qid = q["id"]
    is_multi = q.get("multi", False)
    is_optional = q.get("optional", False)
    choices = q.get("choices", [])
    free_label = q.get("free_text_label")
    allow_custom = q.get("allow_custom", False)

    print(f"  {color.cyan_bold('▸')} {q['text']}")

    if choices:
        for i, (_, label) in enumerate(choices, 1):
            print(f"      {color.yellow(str(i))}.  {label}")
        hint = "number(s)" if is_multi else "number"
        if free_label:
            hint += " or text"
        optional_hint = "  (Enter to skip)" if is_optional else ""
        print()

        raw = _safe_input(f"    Your answer [{hint}]{optional_hint}: ").strip()
        if not raw and is_optional:
            print()
            return

        if is_multi:
            values = _parse_multi(raw, choices, allow_custom, custom_notes)
            brief[qid] = values
        else:
            value = _parse_single(raw, choices)
            if allow_custom and value == "custom":
                custom = _safe_input("    Describe the service or integration: ").strip()
                if custom:
                    custom_notes.append(f"Integration: {custom}")
            brief[qid] = value

    else:
        # Pure free-text question
        optional_hint = "  (Enter to skip)" if is_optional else ""
        raw = _safe_input(f"    {free_label}{optional_hint}: ").strip()
        if raw:
            brief[qid] = raw
            if qid not in ("core_purpose", "must_not", "extra_context"):
                custom_notes.append(f"{qid}: {raw}")

    print()


def _parse_single(raw: str, choices: list) -> str:
    try:
        idx = int(raw.strip()) - 1
        if 0 <= idx < len(choices):
            return choices[idx][0]
    except ValueError:
        pass
    raw_lower = raw.strip().lower()
    for key, _ in choices:
        if raw_lower == key or raw_lower in key:
            return key
    # Return free text mapped to "other" or first choice
    return choices[0][0] if choices else raw


def _parse_multi(raw: str, choices: list, allow_custom: bool, custom_notes: list) -> list:
    if raw.lower() in ("none", "0"):
        return [choices[0][0]]
    tokens = [t.strip() for t in raw.replace(",", " ").split()]
    values = []
    for token in tokens:
        try:
            idx = int(token) - 1
            if 0 <= idx < len(choices):
                key = choices[idx][0]
                if allow_custom and key == "custom":
                    custom = _safe_input("    Describe the custom service: ").strip()
                    if custom:
                        custom_notes.append(f"Custom integration: {custom}")
                else:
                    values.append(key)
        except ValueError:
            pass
    return values if values else [choices[0][0]]


def _safe_input(prompt: str) -> str:
    if not sys.stdin.isatty():
        return ""
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


# ---------------------------------------------------------------------------
# Toolchain check & install
# ---------------------------------------------------------------------------

def _toolchain_check(needed: list[str]) -> None:
    if not needed:
        return

    _section_header("Toolchain Check")
    print(f"  Based on your answers, smooth-bee needs these tools:\n")

    missing: list[str] = []
    for tid in needed:
        t = _TOOLCHAINS.get(tid)
        if not t:
            continue
        present = _tool_present(t)
        marker = color.green("✓") if present else color.red("✗")
        print(f"  {marker}  {t['name']:<32}  {t['note']}")
        if not present:
            missing.append(tid)

    print()
    if not missing:
        print(color.green("  All required tools are available.\n"))
        return

    print(color.yellow(f"  {len(missing)} tool(s) are missing. smooth-bee can try to install them.\n"))
    for tid in missing:
        _offer_install(_TOOLCHAINS[tid])


def _tool_present(t: dict) -> bool:
    # Check known paths first
    for p in t.get("check_paths", []):
        if Path(p).exists():
            return True
    # Check environment variable
    if env_var := t.get("check_env"):
        import os
        if os.environ.get(env_var):
            return True
    # Check command in PATH
    if cmd := t.get("check_cmd"):
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=5)
            return r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return False


def _offer_install(t: dict) -> None:
    name = t["name"]
    print(f"  {color.cyan_bold(name)}")

    if apt_pkg := t.get("apt"):
        cmd = f"sudo apt install -y {apt_pkg}"
        print(f"  Install command: {color.yellow(cmd)}")
        if _confirm(f"  Run this now? [y/N]: "):
            result = subprocess.run(["sudo", "apt", "install", "-y"] + apt_pkg.split())
            if result.returncode == 0:
                print(color.green(f"  ✓  {name} installed.\n"))
            else:
                print(color.red(f"  Installation failed. Try running manually: {cmd}\n"))
        else:
            print(color.yellow(f"  Skipped. Run manually: {cmd}\n"))

    elif install_cmd := t.get("install_cmd"):
        print(f"  Install command: {color.yellow(install_cmd)}")
        if _confirm(f"  Run this now? [y/N]: "):
            result = subprocess.run(install_cmd, shell=True)
            if result.returncode == 0:
                print(color.green(f"  ✓  {name} installed.\n"))
            else:
                print(color.red(f"  Installation failed. Try running manually:\n  {install_cmd}\n"))
        else:
            print(color.yellow(f"  Skipped.\n"))

    elif manual := t.get("manual"):
        print(f"  Manual install required: {manual}")
        print(color.yellow(f"  Please install {name} before running the pipeline.\n"))

    else:
        print(color.yellow(f"  No automatic install available for {name}. Check your package manager.\n"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _section_header(title: str) -> None:
    sep = color.cyan_bold("─" * 52)
    print(f"{sep}\n  {color.cyan_bold(title)}\n{sep}\n")


def _confirm(prompt: str) -> bool:
    if not sys.stdin.isatty():
        return False
    try:
        return _safe_input(prompt).strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


# ---------------------------------------------------------------------------
# Brief → enriched description for Phase 1
# ---------------------------------------------------------------------------

_PLATFORM_LABELS = {
    "android": "Android (APK)",
    "ios": "iOS (IPA)",
    "linux": "Linux",
    "windows": "Windows",
    "macos": "macOS",
    "web": "Web browser",
    "server": "Server/cloud",
    "unsure": "TBD",
}

_LANG_LABELS = {
    "python": "Python",
    "typescript": "JavaScript/TypeScript",
    "kotlin": "Kotlin",
    "java": "Java",
    "rust": "Rust",
    "go": "Go",
    "swift": "Swift",
    "auto": "smooth-bee's choice",
}


def brief_to_context(brief: dict) -> str:
    """
    Render the intake brief as structured context to inject into the Phase 1 prompt.
    """
    lines = ["## User Interview Summary\n"]

    if v := brief.get("app_category"):
        lines.append(f"App category: {v}")

    if v := brief.get("target_platforms"):
        labels = [_PLATFORM_LABELS.get(p, p) for p in v]
        lines.append(f"Target platforms: {', '.join(labels)}")

    if v := brief.get("core_purpose"):
        lines.append(f"Core purpose: {v}")

    if v := brief.get("target_audience"):
        lines.append(f"Target audience: {v}")

    if v := brief.get("ui_type"):
        lines.append(f"UI type: {v}")

    if v := brief.get("data_storage"):
        lines.append(f"Data storage: {v}")

    if v := brief.get("language"):
        lines.append(f"Preferred language: {_LANG_LABELS.get(v, v)}")

    if v := brief.get("connectivity"):
        lines.append(f"Internet connectivity: {v}")

    if v := brief.get("integrations"):
        lines.append(f"Integrations needed: {', '.join(v)}")

    if v := brief.get("must_have"):
        lines.append(f"Must-have feature: {v}")

    if v := brief.get("must_not"):
        lines.append(f"Explicitly excluded: {v}")

    if v := brief.get("sensitive_data"):
        lines.append(f"Sensitive data: {v}")

    if v := brief.get("scale"):
        lines.append(f"Expected scale: {v}")

    if v := brief.get("monetization"):
        lines.append(f"Monetization: {v}")

    if v := brief.get("error_handling"):
        lines.append(f"Error handling preference: {v}")

    if v := brief.get("extra_context"):
        lines.append(f"Additional context: {v}")

    if v := brief.get("additional_context"):
        lines.append(f"Custom notes: {v}")

    return "\n".join(lines)
