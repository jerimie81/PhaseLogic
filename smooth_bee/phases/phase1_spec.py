import json
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from smooth_bee.agents.claude_agent import ClaudeAgent
from smooth_bee.config import Config
from smooth_bee import paths
from smooth_bee.state import ProjectState
from smooth_bee import workspace as ws

_PROMPTS = paths.prompts_dir()
_SYS = "You are a software architect. Output only valid JSON with no markdown fences."


def run(state: ProjectState, cfg: Config, logger: logging.Logger) -> dict:
    logger.info("  Rendering phase 1 prompt...")
    env = Environment(loader=FileSystemLoader(str(_PROMPTS)))
    tmpl = env.get_template("phase1_claude_spec.j2")
    prompt = tmpl.render(description=state.description)

    agent = ClaudeAgent(cfg)
    logger.debug("  Calling Claude...")
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
