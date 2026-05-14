import json
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from phaselogic.agents import get_agent
from phaselogic.config import Config
from phaselogic import paths
from phaselogic.state import ProjectState
from phaselogic import workspace as ws

_PROMPTS = paths.prompts_dir()
_SYS = "You are the lead software architect. Output only valid JSON with no markdown fences."


def run(state: ProjectState, cfg: Config, logger: logging.Logger) -> dict:
    spec = ws.read_artifact(state.project_name, "phase1_spec.json")
    feasibility = ws.read_artifact(state.project_name, "phase2_feasibility.json")
    research = ws.read_artifact(state.project_name, "phase3_research.json")

    env = Environment(loader=FileSystemLoader(str(_PROMPTS)))
    tmpl = env.get_template("phase4_architecture.j2")
    prompt = tmpl.render(spec=spec, feasibility=feasibility, research=research)

    agent = get_agent(cfg.architecture_agent, cfg)
    agent.phase_label = "phase 4"
    raw = agent.call_with_retry(prompt, _SYS, retries=cfg.max_retries, backoff_base=cfg.retry_backoff_base)

    arch = _parse_json(raw, logger)
    ws.write_artifact(state.project_name, "phase4_architecture.json", arch)

    _create_dir_tree(state.project_name, arch.get("directory_tree", {}), logger)
    _write_bootstrap_files(state.project_name, arch.get("bootstrap_files", []), logger)

    sections = arch.get("sections", [])
    logger.info(f"  Architecture done. {len(sections)} sections defined.")
    for s in sections:
        logger.info(f"    {s['section_id']} [{s['assigned_to']}] — {s['title']}")

    return arch


def _create_dir_tree(project_name: str, tree: dict, logger: logging.Logger, prefix: str = "") -> None:
    gen_dir = ws.get_generated_dir(project_name)
    _recurse_tree(tree, gen_dir, logger)


def _recurse_tree(node: dict, base: Path, logger: logging.Logger) -> None:
    for name, children in node.items():
        path = base / name
        if children is None:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.touch()
        else:
            path.mkdir(parents=True, exist_ok=True)
            if isinstance(children, dict):
                _recurse_tree(children, path, logger)


def _write_bootstrap_files(project_name: str, files: list, logger: logging.Logger) -> None:
    for entry in files:
        rel = entry.get("path", "")
        content = entry.get("content", "")
        if rel:
            ws.write_generated_file(project_name, rel, content)
            logger.debug(f"  Bootstrap: {rel}")


def _parse_json(raw: str, logger: logging.Logger) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"  Claude architecture JSON parse error: {e}\nRaw: {raw[:500]}")
        raise
