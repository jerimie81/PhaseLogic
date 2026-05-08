import json
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from phaselogic.agents.claude_agent import ClaudeAgent
from phaselogic.config import Config
from phaselogic import paths
from phaselogic.state import ProjectState
from phaselogic import workspace as ws

_PROMPTS = paths.prompts_dir()
_SYS = "You are a software architect. Output only valid JSON with no markdown fences."


def run(state: ProjectState, cfg: Config, logger: logging.Logger) -> dict:
    logger.info("  Rendering phase 1 prompt...")

    # Load intake brief if one was collected before the pipeline started
    intake_context: str = ""
    try:
        from phaselogic.intake import brief_to_context
        brief = ws.read_artifact(state.project_name, "phase0_intake.json")
        intake_context = brief_to_context(brief)
        logger.info("  Intake brief loaded — enriching spec prompt.")
    except Exception:
        pass

    env = Environment(loader=FileSystemLoader(str(_PROMPTS)))
    tmpl = env.get_template("phase1_claude_spec.j2")
    prompt = tmpl.render(description=state.description, intake=intake_context)

    agent = ClaudeAgent(cfg)
    agent.phase_label = "phase 1"
    raw = agent.call_with_retry(prompt, _SYS, retries=cfg.max_retries, backoff_base=cfg.retry_backoff_base)

    spec = _parse_json(raw, logger)
    ws.write_artifact(state.project_name, "phase1_spec.json", spec)
    logger.info(f"  Spec saved. Project type: {spec.get('project_type')} | Lang: {spec.get('primary_language')}")
    return spec


def _parse_json(raw: str, logger: logging.Logger) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"  Failed to parse Claude JSON: {e}\nRaw: {raw[:500]}")
        raise
