import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


class Phase(str, Enum):
    INIT = "INIT"
    SPEC = "SPEC"
    FEASIBILITY = "FEASIBILITY"
    RESEARCH = "RESEARCH"
    ARCHITECTURE = "ARCHITECTURE"
    CODING = "CODING"
    TESTING = "TESTING"
    DONE = "DONE"
    FAILED = "FAILED"


_TRANSITIONS = {
    Phase.INIT: Phase.SPEC,
    Phase.SPEC: Phase.FEASIBILITY,
    Phase.FEASIBILITY: Phase.RESEARCH,
    Phase.RESEARCH: Phase.ARCHITECTURE,
    Phase.ARCHITECTURE: Phase.CODING,
    Phase.CODING: Phase.TESTING,
    Phase.TESTING: Phase.DONE,
}


@dataclass
class ProjectState:
    project_name: str
    description: str
    current_phase: Phase = Phase.INIT
    completed_phases: list = field(default_factory=list)
    section_ids: list = field(default_factory=list)
    sections_coded: list = field(default_factory=list)
    sections_tested: list = field(default_factory=list)
    error_info: Optional[str] = None
    created_at: str = field(default_factory=lambda: _now())
    updated_at: str = field(default_factory=lambda: _now())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(workspace_dir: Path) -> Path:
    return workspace_dir / "state.json"


def create(project_name: str, description: str, workspace_dir: Path) -> ProjectState:
    state = ProjectState(project_name=project_name, description=description)
    save(state, workspace_dir)
    return state


def load(workspace_dir: Path) -> ProjectState:
    path = _state_path(workspace_dir)
    data = json.loads(path.read_text())
    data["current_phase"] = Phase(data["current_phase"])
    data["completed_phases"] = [Phase(p) for p in data.get("completed_phases", [])]
    return ProjectState(**data)


def save(state: ProjectState, workspace_dir: Path) -> None:
    path = _state_path(workspace_dir)
    tmp = path.with_suffix(".tmp")
    d = asdict(state)
    d["current_phase"] = state.current_phase.value
    d["completed_phases"] = [p.value if isinstance(p, Phase) else p for p in state.completed_phases]
    tmp.write_text(json.dumps(d, indent=2))
    os.replace(tmp, path)


def advance(state: ProjectState, workspace_dir: Path) -> None:
    next_phase = _TRANSITIONS.get(state.current_phase)
    if next_phase is None:
        raise ValueError(f"No transition from {state.current_phase}")
    state.completed_phases.append(state.current_phase.value)
    state.current_phase = next_phase
    state.updated_at = _now()
    save(state, workspace_dir)


def mark_failed(state: ProjectState, workspace_dir: Path, error: str) -> None:
    state.error_info = error
    state.current_phase = Phase.FAILED
    state.updated_at = _now()
    save(state, workspace_dir)
