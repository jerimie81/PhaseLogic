import json
import logging

from jinja2 import Environment, FileSystemLoader

from smooth_bee.agents.kimi_agent import KimiAgent
from smooth_bee.config import Config, SMOOTH_BEE_ROOT
from smooth_bee.state import ProjectState
from smooth_bee import workspace as ws

_PROMPTS = SMOOTH_BEE_ROOT / "prompts"
_SYS = "You are a technical feasibility analyst. Output only valid JSON with no markdown fences."


def run(state: ProjectState, cfg: Config, logger: logging.Logger) -> dict:
    spec = ws.read_artifact(state.project_name, "phase1_spec.json")

    env = Environment(loader=FileSystemLoader(str(_PROMPTS)))
    tmpl = env.get_template("phase2_kimi_feasibility.j2")
    prompt = tmpl.render(spec=spec)

    agent = KimiAgent(cfg)
    logger.info("  Calling Kimi for feasibility assessment...")
    raw = agent.call_with_retry(prompt, _SYS, retries=cfg.max_retries, backoff_base=cfg.retry_backoff_base)

    result = _parse_json(raw, logger)
    ws.write_artifact(state.project_name, "phase2_feasibility.json", result)
    score = result.get("feasibility_score", "?")
    complexity = result.get("estimated_complexity", "?")
    logger.info(f"  Feasibility score: {score}/10 | Complexity: {complexity}")
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
        logger.error(f"  Kimi JSON parse error: {e}\nRaw: {raw[:500]}")
        raise
