from phaselogic import memory, state as st, workspace as ws
from phaselogic.config import Config
from phaselogic.orchestrator import Orchestrator
from phaselogic.phases import (
    phase1_spec,
    phase2_feasibility,
    phase3_research,
    phase4_architecture,
    phase5_coding,
    phase6_testing,
)


def _quiet_memory(monkeypatch):
    monkeypatch.setattr(memory, "log_phase", lambda *args, **kwargs: None)
    monkeypatch.setattr(memory, "record_project_completion", lambda *args, **kwargs: None)


def test_orchestrator_reaches_done_after_testing(monkeypatch, tmp_path):
    monkeypatch.setenv("PHASELOGIC_WORKSPACE", str(tmp_path))
    _quiet_memory(monkeypatch)
    monkeypatch.setattr(ws, "generate_build_report", lambda name: ws.get_path(name) / "BUILD_REPORT.md")

    for module in (
        phase1_spec,
        phase2_feasibility,
        phase3_research,
        phase4_architecture,
        phase5_coding,
        phase6_testing,
    ):
        monkeypatch.setattr(module, "run", lambda *args, **kwargs: {})

    project_dir = ws.create("demo")
    st.create("demo", "demo project", project_dir)

    Orchestrator("demo", Config(sandbox_enabled=False), interactive=False).run()

    saved = st.load(project_dir)
    assert saved.current_phase == st.Phase.DONE
    assert st.Phase.TESTING in saved.completed_phases


def test_orchestrator_stops_at_repair_when_quality_gate_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("PHASELOGIC_WORKSPACE", str(tmp_path))
    _quiet_memory(monkeypatch)

    project_dir = ws.create("needs-repair")
    state = st.create("needs-repair", "demo project", project_dir)
    state.current_phase = st.Phase.CODING
    st.save(state, project_dir)

    def write_failed_report(state, cfg, logger):
        ws.write_artifact(
            state.project_name,
            "phase6_results/s1_codex.json",
            {
                "section_id": "s1",
                "overall_status": "failed",
                "tests_passed": 0,
                "tests_failed": 1,
                "failures_repaired": 0,
                "security_issues": [],
            },
        )
        return []

    monkeypatch.setattr(phase6_testing, "run", write_failed_report)

    Orchestrator("needs-repair", Config(sandbox_enabled=False), interactive=False).run()

    saved = st.load(project_dir)
    assert saved.current_phase == st.Phase.REPAIR
