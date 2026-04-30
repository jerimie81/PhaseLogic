"""
Centralised path resolution — works for both dev installs and system .deb installs.

Resolution order:
  prompts   : SMOOTH_BEE_PROMPTS env  → /usr/share/smooth-bee/prompts (deb)  → <pkg-root>/prompts (dev)
  workspace : SMOOTH_BEE_WORKSPACE env → ~/.local/share/smooth-bee/workspace
  config    : SMOOTH_BEE_CONFIG env    → ~/.config/smooth-bee/config.toml
                                       → /etc/smooth-bee/config.toml
"""

import os
from pathlib import Path

# Package source root (two levels up from this file when running from source)
_PKG_ROOT = Path(__file__).parent.parent

# --- prompts ----------------------------------------------------------

def prompts_dir() -> Path:
    if env := os.environ.get("SMOOTH_BEE_PROMPTS"):
        return Path(env)
    system = Path("/usr/share/smooth-bee/prompts")
    if system.exists():
        return system
    return _PKG_ROOT / "prompts"


# --- workspace --------------------------------------------------------

def workspace_root() -> Path:
    if env := os.environ.get("SMOOTH_BEE_WORKSPACE"):
        return Path(env)
    return Path.home() / ".local" / "share" / "smooth-bee" / "workspace"


# --- config -----------------------------------------------------------

def config_path() -> Path:
    if env := os.environ.get("SMOOTH_BEE_CONFIG"):
        return Path(env)
    user_cfg = Path.home() / ".config" / "smooth-bee" / "config.toml"
    if user_cfg.exists():
        return user_cfg
    system_cfg = Path("/etc/smooth-bee/config.toml")
    if system_cfg.exists():
        return system_cfg
    # dev fallback
    return _PKG_ROOT / "config.toml"
