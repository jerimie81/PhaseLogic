import importlib


def test_phase_modules_import():
    modules = [
        "phaselogic.phases.phase1_spec",
        "phaselogic.phases.phase2_feasibility",
        "phaselogic.phases.phase3_research",
        "phaselogic.phases.phase4_architecture",
        "phaselogic.phases.phase5_coding",
        "phaselogic.phases.phase6_testing",
    ]

    for module in modules:
        importlib.import_module(module)


def test_agent_modules_import():
    modules = [
        "phaselogic.agents.claude_agent",
        "phaselogic.agents.codex_agent",
        "phaselogic.agents.gemini_agent",
        "phaselogic.agents.kimi_agent",
        "phaselogic.agents.ollama_agent",
    ]

    for module in modules:
        importlib.import_module(module)
