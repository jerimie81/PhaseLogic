import json
import logging
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from jinja2 import Environment, FileSystemLoader

from phaselogic.agents import get_agent
from phaselogic.agent_profiles import load_profiles, find_best_agent
from phaselogic.config import Config
from phaselogic import color, memory, paths
from phaselogic.state import ProjectState
from phaselogic import workspace as ws

_PROMPTS = paths.prompts_dir()
_SYS = "You are an expert software engineer. Output only valid JSON with no markdown fences."


@dataclass
class _SectionStatus:
    section_id: str
    agent: str
    status: str = "pending"
    start_time: float = field(default_factory=time.monotonic)
    end_time: float = 0.0

    def elapsed(self) -> float:
        if self.status == "pending":
            return 0.0
        ref = self.end_time if self.end_time else time.monotonic()
        return ref - self.start_time


class _TableUpdater(threading.Thread):
    def __init__(self, statuses: dict, lock: threading.Lock):
        super().__init__(daemon=True)
        self._statuses = statuses
        self._lock = lock
        self._stop_event = threading.Event()
        self._lines_drawn = 0
        self._active = sys.stderr.isatty()

    def run(self) -> None:
        if not self._active:
            return
        while not self._stop_event.is_set():
            self._draw()
            self._stop_event.wait(0.5)
        self._draw(final=True)

    def stop(self) -> None:
        self._stop_event.set()
        self.join(timeout=2.0)

    def _draw(self, final: bool = False) -> None:
        if not self._active:
            return
        if self._lines_drawn > 0:
            sys.stderr.write(f"\033[{self._lines_drawn}A")

        with self._lock:
            rows = list(self._statuses.values())

        n_agents = len({r.agent for r in rows})
        lines = [f"Coding {len(rows)} sections across {n_agents} agents:"]

        for s in rows:
            marker_map = {"done": "✓", "failed": "✗", "coding": "→"}
            marker = marker_map.get(s.status, " ")
            sid_col = f"{s.section_id:<24}"
            agent_col = f"{s.agent:<8}"
            status_col = f"{s.status:<8}"
            elapsed = f"{s.elapsed():.1f}s" if s.status != "pending" else ""

            if color._STDERR_ENABLED:
                if s.status == "done":
                    marker = color.s_green(marker)
                elif s.status == "failed":
                    marker = color.s_red(marker)
                elif s.status == "coding":
                    marker = color.s_yellow(marker)

            lines.append(f"  {marker}  {sid_col} {agent_col} {status_col} {elapsed}")

        sys.stderr.write("\n".join(lines) + "\n")
        sys.stderr.flush()
        self._lines_drawn = len(lines)


def run(state: ProjectState, cfg: Config, logger: logging.Logger) -> None:
    arch = ws.read_artifact(state.project_name, "phase4_architecture.json")
    spec = ws.read_artifact(state.project_name, "phase1_spec.json")
    research = ws.read_artifact(state.project_name, "phase3_research.json")

    profiles = load_profiles()
    sections = arch.get("sections", [])
    ordered = _topological_sort(sections)

    already_coded = set(state.sections_coded)
    queue = [s for s in ordered if s["section_id"] not in already_coded]

    if not queue:
        logger.info("  All sections already coded. Skipping.")
        return

    # Build shared status table
    statuses: dict[str, _SectionStatus] = {}
    for s in queue:
        agent_name = _select_agent_for_section(s, cfg, profiles)
        statuses[s["section_id"]] = _SectionStatus(
            s["section_id"],
            agent_name,
        )

    lock = threading.Lock()
    table = _TableUpdater(statuses, lock)

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

    def _build_agent(section: dict):
        sid = section["section_id"]
        preferred = _select_agent_for_section(section, cfg, profiles)
        candidates: list[str] = []
        fallback_agents = [
            str(name).strip().lower()
            for name in section.get("fallback_agents", [])
            if str(name).strip()
        ]
        for name in [preferred, *fallback_agents, cfg.coding_agent]:
            if name and name not in candidates:
                candidates.append(name)

        last_error: Exception | None = None
        for name in candidates:
            try:
                agent = get_agent(name, cfg)
            except Exception as e:
                last_error = e
                if name == preferred and name != cfg.coding_agent:
                    logger.warning(
                        f"  Agent '{name}' unavailable for {sid}; "
                        f"falling back to '{cfg.coding_agent}'. Reason: {e}"
                    )
                continue

            # Disable per-call spinners — the live table provides status instead
            agent.phase_label = "phase 5"
            agent.spinner_enabled = False
            with lock:
                statuses[sid].agent = name
            return agent, name

        raise RuntimeError(
            f"No coding agent available for {sid}. Last error: {last_error}"
        )

    def _run_section(section: dict, template_name: str) -> dict:
        sid = section["section_id"]
        with lock:
            statuses[sid].status = "coding"
            statuses[sid].start_time = time.monotonic()
        try:
            agent, agent_name = _build_agent(section)
            coded_cache.update(_load_coded())
            deps = {dep_id: coded_cache[dep_id]
                    for dep_id in section.get("dependencies", [])
                    if dep_id in coded_cache}

            tmpl = env.get_template(template_name)
            prompt = tmpl.render(spec=spec, research=research, section=section, coded_dependencies=deps)
            raw = agent.call_with_retry(prompt, _SYS, retries=cfg.max_retries, backoff_base=cfg.retry_backoff_base)

            result = _parse_json(raw, logger, sid)
            _write_section_files(state.project_name, result, logger)

            ws.write_artifact(state.project_name, f"phase5_sections/{sid}_{agent_name}.json", result)

            with lock:
                statuses[sid].status = "done"
                statuses[sid].end_time = time.monotonic()
            return result
        except Exception:
            with lock:
                statuses[sid].status = "failed"
                statuses[sid].end_time = time.monotonic()
            raise

    table.start()
    completed_sids: list[str] = []
    failed = False

    try:
        pending = {s["section_id"]: s for s in queue}
        completed = set(already_coded)

        while pending:
            ready = [
                s for s in pending.values()
                if set(s.get("dependencies", [])).issubset(completed)
            ]
            if not ready:
                blocked = ", ".join(sorted(pending))
                raise RuntimeError(
                    "No code sections are ready to run. "
                    f"Check for circular or missing dependencies: {blocked}"
                )

            with ThreadPoolExecutor(max_workers=min(3, len(ready))) as pool:
                futures = {
                    pool.submit(_run_section, section, "phase5_code.j2"): section["section_id"]
                    for section in ready
                }
                for fut in as_completed(futures):
                    sid = futures[fut]
                    try:
                        fut.result()
                        completed_sids.append(sid)
                        completed.add(sid)
                        pending.pop(sid, None)
                    except Exception as e:
                        logger.error(f"  Failed to code {sid}: {e}")
                        failed = True
                        raise
    finally:
        table.stop()

    # Emit per-section summary after the table freezes
    for sid in completed_sids:
        state.sections_coded.append(sid)
        logger.info(f"  Coded: {sid}")

    if not failed:
        n = memory.index_generated_files(
            state.project_name, str(ws.get_path(state.project_name))
        )
        if n:
            logger.debug(f"  Indexed {n} generated files in memory.db")

    if failed:
        raise RuntimeError("One or more sections failed to code.")


def _write_section_files(project_name: str, result: dict, logger: logging.Logger) -> None:
    for file_entry in result.get("files", []):
        path = file_entry.get("path", "")
        content = file_entry.get("content", "")
        if path:
            ws.write_generated_file(project_name, path, content)
            logger.debug(f"    Wrote: {path}")


def _select_agent_for_section(section: dict, cfg: Config, profiles: dict) -> str:
    # 1. Use explicitly assigned profile if it exists in profiles
    assigned = str(section.get("assigned_to") or "").strip().lower()
    if assigned in profiles:
        return assigned

    # 2. Match by capabilities
    reqs = section.get("required_capabilities") or section.get("capabilities", [])
    pref_provider = section.get("preferred_provider")
    best = find_best_agent(reqs, profiles, provider_preference=pref_provider)
    if best:
        return best

    # 3. Fallback to assigned name (if it was just a provider name like 'gemini') or config default
    return assigned or cfg.coding_agent


def _preferred_agent_name(section: dict, cfg: Config) -> str:
    return _select_agent_for_section(section, cfg, {})


def _topological_sort(sections: list) -> list:
    id_map = {s["section_id"]: s for s in sections}
    visited = set()
    visiting = set()
    order = []

    def _visit(sid):
        if sid in visited:
            return
        if sid in visiting:
            raise RuntimeError(f"Circular section dependency detected at {sid}")
        if sid not in id_map:
            raise RuntimeError(f"Section dependency '{sid}' is not defined")

        visiting.add(sid)
        for dep in id_map[sid].get("dependencies", []):
            _visit(dep)
        visiting.remove(sid)
        visited.add(sid)
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
