import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path("/home/redrum/.gemini/memory.db")


def _conn():
    return sqlite3.connect(DB_PATH)


def register_project(name: str, workspace_path: str) -> None:
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO projects (name, path, language, build_system, last_modified) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                (name, workspace_path, "multi-ai", "smooth-bee"),
            )
    except Exception:
        pass


def deregister_project(workspace_path: str) -> None:
    try:
        with _conn() as conn:
            conn.execute("DELETE FROM projects WHERE path = ?", (workspace_path,))
    except Exception:
        pass


def log_phase(project_name: str, phase: str, error: Optional[str] = None) -> None:
    msg = f"smooth-bee [{project_name}] phase={phase}"
    if error:
        msg += f" error={error[:200]}"
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO conversations (role, content, context_summary) VALUES (?, ?, ?)",
                ("system", msg, f"smooth-bee:{project_name}"),
            )
    except Exception:
        pass
