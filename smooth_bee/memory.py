"""
Persistent memory via /home/redrum/.gemini/memory.db (shared SQLite instance).

Tables used:
  projects        — project registration (already existed)
  conversations   — phase transition log (already existed)
  knowledge_bases — user preferences, agent stats, project history (NEW)
  code_revisions  — interactive artifact edits (NEW)
  file_index      — generated file catalogue (NEW)

All writes are wrapped in try/except so a missing or locked DB never
crashes the pipeline. Reads return safe empty defaults on any error.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path("/home/redrum/.gemini/memory.db")

# Questions whose answers are worth learning across projects
_LEARNABLE_KEYS = {
    "app_category", "target_platforms", "target_audience",
    "ui_type", "data_storage", "language", "connectivity",
    "integrations", "sensitive_data", "scale", "monetization",
    "error_handling",
}

_EXT_TO_TYPE = {
    ".py": "python", ".ts": "typescript", ".js": "javascript",
    ".kt": "kotlin", ".java": "java", ".rs": "rust", ".go": "go",
    ".swift": "swift", ".c": "c", ".cpp": "cpp", ".h": "c-header",
    ".json": "json", ".toml": "toml", ".yaml": "yaml", ".yml": "yaml",
    ".md": "markdown", ".html": "html", ".css": "css", ".sql": "sql",
    ".sh": "shell", ".gradle": "gradle", ".xml": "xml",
}


# ── Internal helpers ─────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _kb_get(name: str) -> dict:
    """Load a knowledge_bases row by name; return parsed dict or {}."""
    try:
        with _conn() as conn:
            row = conn.execute(
                "SELECT content FROM knowledge_bases WHERE name = ?", (name,)
            ).fetchone()
            if row:
                return json.loads(row[0])
    except Exception:
        pass
    return {}


def _kb_set(name: str, data: dict, tags: str = "phaselogic") -> None:
    """Upsert a knowledge_bases entry (INSERT OR UPDATE on name)."""
    try:
        content = json.dumps(data, ensure_ascii=False)
        with _conn() as conn:
            conn.execute(
                "INSERT INTO knowledge_bases (name, content, timestamp, tags) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET "
                "content=excluded.content, timestamp=excluded.timestamp",
                (name, content, _now(), tags),
            )
    except Exception:
        pass


# ── Core project tracking ────────────────────────────────────────────────────

def register_project(name: str, workspace_path: str) -> None:
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO projects "
                "(name, path, language, build_system, last_modified) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                (name, workspace_path, "multi-ai", "phaselogic"),
            )
    except Exception:
        pass


def deregister_project(workspace_path: str) -> None:
    try:
        with _conn() as conn:
            conn.execute("DELETE FROM projects WHERE path = ?", (workspace_path,))
    except Exception:
        pass


def get_project_id(workspace_path: str) -> Optional[int]:
    try:
        with _conn() as conn:
            row = conn.execute(
                "SELECT id FROM projects WHERE path = ?", (workspace_path,)
            ).fetchone()
            return row[0] if row else None
    except Exception:
        return None


def log_phase(project_name: str, phase: str, error: Optional[str] = None) -> None:
    msg = f"PhaseLogic [{project_name}] phase={phase}"
    if error:
        msg += f" error={error[:200]}"
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO conversations (role, content, context_summary) VALUES (?, ?, ?)",
                ("system", msg, f"phaselogic:{project_name}"),
            )
    except Exception:
        pass


# ── User preference learning ─────────────────────────────────────────────────

def load_user_preferences() -> dict:
    """Return accumulated user preference data from past projects."""
    return _kb_get("phaselogic:user-preferences")


def update_user_preferences(brief: dict) -> None:
    """
    Update preference counters from a completed intake session.
    Called at the end of intake.run() with the full brief dict.

    Preference format per question:
      {"value": "python", "count": 4}
    When the same value appears again, count increments.
    When a different value appears, the entry resets to count=1.
    """
    prefs = _kb_get("phaselogic:user-preferences")
    q_prefs: dict = prefs.get("question_prefs", {})

    for key, value in brief.items():
        if key not in _LEARNABLE_KEYS:
            continue
        if not value:
            continue
        existing = q_prefs.get(key)
        if existing and existing.get("value") == value:
            q_prefs[key]["count"] = existing.get("count", 1) + 1
        else:
            q_prefs[key] = {"value": value, "count": 1}

    prefs["question_prefs"] = q_prefs
    prefs["projects_started"] = prefs.get("projects_started", 0) + 1
    prefs["last_updated"] = _now()
    _kb_set("phaselogic:user-preferences", prefs, tags="phaselogic:preferences")


def record_project_completion(project_name: str, summary: dict) -> None:
    """
    Mark a project as completed and append a summary to the history log.
    Also increments projects_completed in the preference store.
    """
    # Increment completion counter in preferences
    prefs = _kb_get("phaselogic:user-preferences")
    prefs["projects_completed"] = prefs.get("projects_completed", 0) + 1
    prefs["last_project"] = project_name
    prefs["last_updated"] = _now()
    _kb_set("phaselogic:user-preferences", prefs, tags="phaselogic:preferences")

    # Append to capped history list
    history = _kb_get("phaselogic:project-history")
    entries: list = history.get("entries", [])
    entry = {"project": project_name, "timestamp": _now()}
    for k in ("file_count", "line_count", "sections_passed",
               "sections_total", "security_critical", "duration_s"):
        if k in summary:
            entry[k] = summary[k]
    entries.append(entry)
    history["entries"] = entries[-20:]  # keep newest 20
    _kb_set("phaselogic:project-history", history, tags="phaselogic:history")


def get_past_projects_summary() -> list[dict]:
    """Brief list of past PhaseLogic projects (name, date, file count)."""
    try:
        with _conn() as conn:
            rows = conn.execute(
                "SELECT p.name, p.last_modified, COUNT(fi.id) "
                "FROM projects p "
                "LEFT JOIN file_index fi ON fi.project_id = p.id "
                "WHERE p.build_system = 'phaselogic' "
                "GROUP BY p.id ORDER BY p.last_modified DESC LIMIT 10"
            ).fetchall()
            return [{"name": r[0], "last_modified": r[1], "file_count": r[2]}
                    for r in rows]
    except Exception:
        return []


# ── Agent performance tracking ───────────────────────────────────────────────

def log_agent_call(agent_name: str, duration_s: float, succeeded: bool) -> None:
    """
    Update the exponential moving average and failure count for an agent.
    Uses alpha=0.2 so recent calls are weighted more without being noisy.
    """
    stats = _kb_get("phaselogic:agent-stats")
    a = stats.get(agent_name, {"avg_s": 0.0, "calls": 0, "failures": 0})

    calls = a["calls"] + 1
    old_avg = a["avg_s"] if a["calls"] > 0 else duration_s
    new_avg = 0.2 * duration_s + 0.8 * old_avg

    a["avg_s"] = round(new_avg, 1)
    a["calls"] = calls
    a["failures"] = a.get("failures", 0) + (0 if succeeded else 1)
    a["last_call"] = _now()

    stats[agent_name] = a
    _kb_set("phaselogic:agent-stats", stats, tags="phaselogic:performance")


def load_agent_stats() -> dict:
    """Return {agent_name: {avg_s, calls, failures}} for all tracked agents."""
    return _kb_get("phaselogic:agent-stats")


def agent_avg_seconds(agent_name: str) -> Optional[float]:
    """
    Return the EMA average call duration for an agent.
    Returns None until at least 3 calls have been observed (too noisy before that).
    """
    stats = _kb_get("phaselogic:agent-stats")
    entry = stats.get(agent_name)
    if entry and entry.get("calls", 0) >= 3:
        return entry["avg_s"]
    return None


# ── Interactive artifact edit logging ────────────────────────────────────────

def log_artifact_edit(project_name: str, phase: str,
                       artifact_name: str, before: str, after: str) -> None:
    """
    Log a user-initiated artifact edit to the code_revisions table.
    Skipped if the content didn't actually change.
    """
    if before == after:
        return
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO code_revisions "
                "(timestamp, file_path, original_snippet, revised_snippet, "
                " user_feedback, agent_notes) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    _now(),
                    f"phaselogic:{project_name}/{artifact_name}",
                    before[:2000],
                    after[:2000],
                    "interactive edit",
                    f"phase={phase} project={project_name}",
                ),
            )
    except Exception:
        pass


# ── Generated file indexing ──────────────────────────────────────────────────

def index_generated_files(project_name: str, workspace_path: str) -> int:
    """
    Walk the project's generated/ directory and upsert every file into
    file_index. Returns the number of files indexed.

    This allows future projects to query what the user has built before,
    giving Claude richer context in Phase 1.
    """
    from smooth_bee import workspace as ws
    gen_dir = ws.get_generated_dir(project_name)
    if not gen_dir.exists():
        return 0

    project_id = get_project_id(workspace_path)
    count = 0
    try:
        with _conn() as conn:
            for f in gen_dir.rglob("*"):
                if not f.is_file():
                    continue
                ext = f.suffix.lower()
                file_type = _EXT_TO_TYPE.get(ext, "other")
                try:
                    conn.execute(
                        "INSERT INTO file_index "
                        "(file_path, file_name, file_type, last_indexed, project_id) "
                        "VALUES (?, ?, ?, ?, ?) "
                        "ON CONFLICT(file_path) DO UPDATE SET "
                        "last_indexed=excluded.last_indexed, "
                        "file_type=excluded.file_type",
                        (str(f), f.name, file_type, _now(), project_id),
                    )
                    count += 1
                except Exception:
                    pass
    except Exception:
        pass
    return count


def search_similar_files(file_type: str, limit: int = 5) -> list[dict]:
    """Find previously generated files of a given type across all projects."""
    try:
        with _conn() as conn:
            rows = conn.execute(
                "SELECT fi.file_path, fi.file_name, p.name "
                "FROM file_index fi "
                "LEFT JOIN projects p ON fi.project_id = p.id "
                "WHERE fi.file_type = ? "
                "ORDER BY fi.last_indexed DESC LIMIT ?",
                (file_type, limit),
            ).fetchall()
            return [{"file_path": r[0], "file_name": r[1], "project": r[2]}
                    for r in rows]
    except Exception:
        return []
