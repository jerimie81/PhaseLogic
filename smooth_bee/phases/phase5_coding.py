import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from smooth_bee.agents.gemini_agent import GeminiAgent
from smooth_bee.agents.kimi_agent import KimiAgent
from smooth_bee.config import Config
from smooth_bee import paths
from smooth_bee.state import ProjectState
from smooth_bee import workspace as ws

_PROMPTS = paths.prompts_dir()
_SYS = "You are an expert software engineer. Output only valid JSON with no markdown fences."


def run(state: ProjectState, cfg: Config, logger: logging.Logger) -> None:
    arch = ws.read_artifact(state.project_name, "phase4_architecture.json")
    spec = ws.read_artifact(state.project_name, "phase1_spec.json")
    research = ws.read_artifact(state.project_name, "phase3_research.json")

    sections = arch.get("sections", [])
    ordered = _topological_sort(sections)

    already_coded = set(state.sections_coded)
    gemini_queue = [s for s in ordered if s["assigned_to"] == "gemini" and s["section_id"] not in already_coded]
    kimi_queue = [s for s in ordered if s["assigned_to"] == "kimi" and s["section_id"] not in already_coded]

    if not gemini_queue and not kimi_queue:
        logger.info("  All sections already coded. Skipping.")
        return

    logger.info(f"  Coding {len(gemini_queue)} Gemini sections + {len(kimi_queue)} Kimi sections in parallel...")

    gemini_agent = GeminiAgent(cfg)
    kimi_agent = KimiAgent(cfg)
    env = Environment(loader=FileSystemLoader(str(_PROMPTS)))

    coded_cache: dict = {}

    def _load_coded() -> dict:
        cache = {}
        p5_dir = ws.get_phase5_dir(state.project_name)
        for f in p5_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                cache[data["section_id"]] = data
            except Exception:
                pass
        return cache

    def _run_section(section: dict, agent, template_name: str) -> dict:
        coded_cache.update(_load_coded())
        deps = {}
        for dep_id in section.get("dependencies", []):
            if dep_id in coded_cache:
                deps[dep_id] = coded_cache[dep_id]

        tmpl = env.get_template(template_name)
        prompt = tmpl.render(spec=spec, research=research, section=section, coded_dependencies=deps)
        raw = agent.call_with_retry(prompt, _SYS, retries=cfg.max_retries, backoff_base=cfg.retry_backoff_base)

        result = _parse_json(raw, logger, section["section_id"])
        _write_section_files(state.project_name, result, logger)

        agent_tag = "gemini" if agent.name == "gemini" else "kimi"
        ws.write_artifact(state.project_name, f"phase5_sections/{section['section_id']}_{agent_tag}.json", result)
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {}

        def _submit_queue(queue, agent, tmpl_name):
            # submit in dependency order — wait for deps that are in the other queue
            for section in queue:
                fut = pool.submit(_run_section, section, agent, tmpl_name)
                futures[fut] = section["section_id"]

        _submit_queue(gemini_queue, gemini_agent, "phase5_gemini_code.j2")
        _submit_queue(kimi_queue, kimi_agent, "phase5_kimi_code.j2")

        for fut in as_completed(futures):
            sid = futures[fut]
            try:
                fut.result()
                state.sections_coded.append(sid)
                logger.info(f"  Coded: {sid}")
            except Exception as e:
                logger.error(f"  Failed to code {sid}: {e}")
                raise


def _write_section_files(project_name: str, result: dict, logger: logging.Logger) -> None:
    for file_entry in result.get("files", []):
        path = file_entry.get("path", "")
        content = file_entry.get("content", "")
        if path:
            ws.write_generated_file(project_name, path, content)
            logger.debug(f"    Wrote: {path}")


def _topological_sort(sections: list) -> list:
    id_map = {s["section_id"]: s for s in sections}
    visited = set()
    order = []

    def _visit(sid):
        if sid in visited:
            return
        visited.add(sid)
        for dep in id_map.get(sid, {}).get("dependencies", []):
            _visit(dep)
        order.append(id_map[sid])

    for s in sections:
        _visit(s["section_id"])
    return order


def _parse_json(raw: str, logger: logging.Logger, section_id: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"  JSON parse error for {section_id}: {e}\nRaw: {raw[:500]}")
        raise
