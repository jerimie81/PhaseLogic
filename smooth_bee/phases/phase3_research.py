import json
import logging

from jinja2 import Environment, FileSystemLoader

from smooth_bee.agents.gemini_agent import GeminiAgent
from smooth_bee.config import Config, SMOOTH_BEE_ROOT
from smooth_bee.state import ProjectState
from smooth_bee import workspace as ws

_PROMPTS = SMOOTH_BEE_ROOT / "prompts"
_SYS = "You are a deep technical researcher. Output only valid JSON with no markdown fences."


def run(state: ProjectState, cfg: Config, logger: logging.Logger) -> dict:
    spec = ws.read_artifact(state.project_name, "phase1_spec.json")
    feasibility = ws.read_artifact(state.project_name, "phase2_feasibility.json")

    env = Environment(loader=FileSystemLoader(str(_PROMPTS)))
    tmpl = env.get_template("phase3_gemini_research.j2")
    prompt = tmpl.render(spec=spec, feasibility=feasibility)

    agent = GeminiAgent(cfg)
    logger.info("  Calling Gemini for deep research...")
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
