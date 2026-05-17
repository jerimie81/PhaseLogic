import pytest

from phaselogic.config import Config
from phaselogic.phases import phase5_coding


def test_preferred_agent_uses_section_assignment():
    section = {"section_id": "s1", "assigned_to": "KIMI"}

    assert phase5_coding._preferred_agent_name(section, Config(coding_agent="gemini")) == "kimi"


def test_topological_sort_rejects_missing_dependency():
    sections = [{"section_id": "s1", "dependencies": ["missing"]}]

    with pytest.raises(RuntimeError, match="not defined"):
        phase5_coding._topological_sort(sections)


def test_topological_sort_rejects_cycle():
    sections = [
        {"section_id": "s1", "dependencies": ["s2"]},
        {"section_id": "s2", "dependencies": ["s1"]},
    ]

    with pytest.raises(RuntimeError, match="Circular"):
        phase5_coding._topological_sort(sections)
