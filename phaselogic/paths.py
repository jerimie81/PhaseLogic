"""
Centralised path resolution — works for both dev installs and system .deb installs.

Resolution order:
  prompts   : PHASELOGIC_PROMPTS env  → /usr/share/phaselogic/prompts (deb)  → <pkg-root>/prompts (dev)
  workspace : PHASELOGIC_WORKSPACE env → ~/.local/share/phaselogic/workspace
  config    : PHASELOGIC_CONFIG env    → ~/.config/phaselogic/config.toml
                                       → /etc/phaselogic/config.toml
  agents    : PHASELOGIC_AGENT_PROFILES env → ~/.config/phaselogic/agents
"""

import os
from pathlib import Path

# Package source root (two levels up from this file when running from source)
_PKG_ROOT = Path(__file__).parent.parent

# --- prompts ----------------------------------------------------------

def prompts_dir() -> Path:
    if env := os.environ.get("PHASELOGIC_PROMPTS"):
        return Path(env)
    system = Path("/usr/share/phaselogic/prompts")
    if system.exists():
        return system
    return _PKG_ROOT / "prompts"


# --- workspace --------------------------------------------------------

def workspace_root() -> Path:
    if env := os.environ.get("PHASELOGIC_WORKSPACE"):
        return Path(env)
    return Path.home() / ".local" / "share" / "phaselogic" / "workspace"


# --- agent profiles ---------------------------------------------------

def agent_profiles_dir() -> Path:
    if env := os.environ.get("PHASELOGIC_AGENT_PROFILES"):
        return Path(env)
    return Path.home() / ".config" / "phaselogic" / "agents"


# --- config -----------------------------------------------------------

def config_path() -> Path:
    if env := os.environ.get("PHASELOGIC_CONFIG"):
        return Path(env)
    user_cfg = Path.home() / ".config" / "phaselogic" / "config.toml"
    if user_cfg.exists():
        return user_cfg
    system_cfg = Path("/etc/phaselogic/config.toml")
    if system_cfg.exists():
        return system_cfg
    # dev fallback
    return _PKG_ROOT / "config.toml"
