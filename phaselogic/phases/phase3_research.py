import json
import logging

from jinja2 import Environment, FileSystemLoader

from phaselogic.agents import get_agent
from phaselogic.config import Config
from phaselogic import paths
from phaselogic.state import ProjectState
from phaselogic import workspace as ws

_PROMPTS = paths.prompts_dir()
_SYS = "You are a deep technical researcher. Output only valid JSON with no markdown fences."


def run(state: ProjectState, cfg: Config, logger: logging.Logger) -> dict:
    spec = ws.read_artifact(state.project_name, "phase1_spec.json")
    feasibility = ws.read_artifact(state.project_name, "phase2_feasibility.json")

    env = Environment(loader=FileSystemLoader(str(_PROMPTS)))
    tmpl = env.get_template("phase3_research.j2")
    prompt = tmpl.render(spec=spec, feasibility=feasibility)

    agent = get_agent(cfg.research_agent, cfg)
    agent.phase_label = "phase 3"
    raw = agent.call_with_retry(prompt, _SYS, retries=cfg.max_retries, backoff_base=cfg.retry_backoff_base)

    result = _parse_json(raw, logger)
    ws.write_artifact(state.project_name, "phase3_research.json", result)
    stack = result.get("recommended_stack", {})
    logger.info(f"  Research complete. Stack: {stack.get('framework','?')} / {stack.get('language_version','?')}")
    return result


def _parse_json(raw: str, logger: logging.Logger) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"  Gemini JSON parse error: {e}\nRaw: {raw[:500]}")
        raise
