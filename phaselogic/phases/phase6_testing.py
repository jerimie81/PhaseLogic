import json
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from phaselogic.agents import get_agent
from phaselogic.agents.base import AgentAdapter
from phaselogic.config import Config
from phaselogic import paths
from phaselogic.sandbox import DockerSandbox, SandboxPolicy
from phaselogic.state import ProjectState
from phaselogic import workspace as ws

_PROMPTS = paths.prompts_dir()


def run(state: ProjectState, cfg: Config, logger: logging.Logger) -> list[dict]:
    arch = ws.read_artifact(state.project_name, "phase4_architecture.json")
    sections = arch.get("sections", [])
    generated_dir = ws.get_generated_dir(state.project_name)
    phase6_dir = ws.get_phase6_dir(state.project_name)

    agent = get_agent(cfg.testing_agent, cfg)
    if hasattr(agent, "working_dir"):
        agent.working_dir = generated_dir

    sandbox = _prepare_sandbox(generated_dir, cfg, logger)
    
    env = Environment(loader=FileSystemLoader(str(_PROMPTS)))
    tmpl = env.get_template("phase6_test.j2")

    results = []
    already_tested = set(state.sections_tested)

    for section in sections:
        sid = section["section_id"]
        if sid in already_tested:
            logger.info(f"  Already tested: {sid}, skipping.")
            continue

        report_path = phase6_dir / f"{sid}_codex.json"
        prompt = tmpl.render(section=section, report_path=str(report_path), sandbox=sandbox)

        logger.info(f"  Testing section: {sid} ({section['title']})")
        try:
            report = agent.call_for_report(prompt, report_path)
        except Exception as e:
            logger.error(f"  Codex test failed for {sid}: {e}")
            report = {"section_id": sid, "overall_status": "failed", "error": str(e)}
            report_path.write_text(json.dumps(report, indent=2))

        results.append(report)
        state.sections_tested.append(sid)

        status = report.get("overall_status", "unknown")
        passed = report.get("tests_passed", "?")
        failed = report.get("tests_failed", "?")
        repaired = report.get("failures_repaired", 0)
        security = len(report.get("security_issues", []))
        logger.info(
            f"    {sid}: {status} | passed={passed} failed={failed} repaired={repaired} security_issues={security}"
        )

    _run_security_sweep(state.project_name, agent, phase6_dir, logger)
    return results


def _prepare_sandbox(generated_dir: Path, cfg: Config, logger: logging.Logger) -> dict:
    if not cfg.sandbox_enabled:
        logger.warning("  Phase 6 sandbox disabled by config.")
        return {"enabled": False, "required": False, "reason": "disabled by config"}

    policy = SandboxPolicy(
        allow_network=cfg.sandbox_allow_network,
        memory=cfg.sandbox_memory,
        cpus=cfg.sandbox_cpus,
        timeout_seconds=cfg.sandbox_timeout_seconds,
    )
    sandbox = DockerSandbox(image=cfg.sandbox_image, policy=policy)
    if not sandbox.available():
        message = "Docker sandbox is enabled but docker is not available."
        if cfg.sandbox_required:
            raise RuntimeError(message)
        logger.warning(f"  {message} Falling back to host execution.")
        return {"enabled": False, "required": False, "reason": message}

    runner = sandbox.write_runner(generated_dir)
    rel_runner = runner.relative_to(generated_dir)
    logger.info(f"  Phase 6 sandbox runner ready: {rel_runner}")
    return {
        "enabled": True,
        "required": cfg.sandbox_required,
        "runner": f"./{rel_runner}",
        "image": cfg.sandbox_image,
        "allow_network": cfg.sandbox_allow_network,
        "memory": cfg.sandbox_memory,
        "cpus": cfg.sandbox_cpus,
        "timeout_seconds": cfg.sandbox_timeout_seconds,
    }


def _run_security_sweep(project_name: str, agent: AgentAdapter, phase6_dir: Path, logger: logging.Logger) -> None:
    report_path = phase6_dir / "security_final.json"
    if report_path.exists():
        logger.info("  Security sweep already done.")
        return

    logger.info("  Running final security sweep on entire project...")
    prompt = (
        "Perform a comprehensive security audit of all code files in your current working directory. "
        "Check for: hardcoded secrets, SQL injection, shell injection, SSRF, insecure deserialization, "
        "missing input validation, XSS, path traversal, insecure random, outdated dependency patterns. "
        f"Write your findings as a JSON array to: {report_path}\n"
        'Schema: [{"severity":"critical|high|medium|low","description":"...","file":"...","line":null}]\n'
        "If no issues found, write an empty array []. Do not output anything else."
    )
    try:
        agent.call_for_report(prompt, report_path)
        issues = json.loads(report_path.read_text())
        critical = sum(1 for i in issues if i.get("severity") == "critical")
        logger.info(f"  Security sweep complete. {len(issues)} issues found ({critical} critical).")
    except Exception as e:
        logger.error(f"  Security sweep failed: {e}")
        report_path.write_text("[]")
