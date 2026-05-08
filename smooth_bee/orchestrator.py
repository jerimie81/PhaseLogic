import json
import logging
import os
import subprocess
import sys

from smooth_bee import state as st, workspace as ws, logger as lg
from smooth_bee.agents.base import AgentError
from smooth_bee.config import Config
from smooth_bee.state import Phase, ProjectState
from smooth_bee.phases import (
    phase1_spec,
    phase2_feasibility,
    phase3_research,
    phase4_architecture,
    phase5_coding,
    phase6_testing,
)
from smooth_bee import memory


_REVIEW_ARTIFACTS: dict[Phase, str] = {
    Phase.INIT: "phase1_spec.json",
    Phase.SPEC: "phase2_feasibility.json",
    Phase.FEASIBILITY: "phase3_research.json",
    Phase.RESEARCH: "phase4_architecture.json",
}


class Orchestrator:
    def __init__(self, project_name: str, cfg: Config, interactive: bool = False):
        self.project_name = project_name
        self.cfg = cfg
        self.interactive = interactive
        self.workspace_dir = ws.get_path(project_name)
        self.logger = lg.get_logger(project_name)

    def run(self) -> None:
        lg.start_run()
        state = st.load(self.workspace_dir)
        self.logger.info(f"Resuming {self.project_name} from phase: {state.current_phase.value}")

        _PHASE_MAP = {
            Phase.INIT: self._run_spec,
            Phase.SPEC: self._run_feasibility,
            Phase.FEASIBILITY: self._run_research,
            Phase.RESEARCH: self._run_architecture,
            Phase.ARCHITECTURE: self._run_coding,
            Phase.CODING: self._run_testing,
        }

        while state.current_phase not in (Phase.DONE, Phase.FAILED):
            handler = _PHASE_MAP.get(state.current_phase)
            if handler is None:
                break
            try:
                handler(state)
            except (AgentError, Exception) as e:
                self.logger.error(f"Phase {state.current_phase.value} failed: {e}")
                st.mark_failed(state, self.workspace_dir, str(e))
                memory.log_phase(self.project_name, "FAILED", str(e))
                raise
            if self.interactive:
                self._interactive_review(state)
            st.advance(state, self.workspace_dir)
            state = st.load(self.workspace_dir)
            memory.log_phase(self.project_name, state.current_phase.value)

        if state.current_phase == Phase.DONE:
            self._print_summary(state)
            memory.log_phase(self.project_name, "DONE")

    def _run_spec(self, state: ProjectState) -> None:
        lg.phase_banner(self.logger, 1, "SPEC (Claude)")
        phase1_spec.run(state, self.cfg, self.logger)

    def _run_feasibility(self, state: ProjectState) -> None:
        lg.phase_banner(self.logger, 2, "FEASIBILITY (Kimi)")
        phase2_feasibility.run(state, self.cfg, self.logger)

    def _run_research(self, state: ProjectState) -> None:
        lg.phase_banner(self.logger, 3, "RESEARCH (Gemini)")
        phase3_research.run(state, self.cfg, self.logger)

    def _run_architecture(self, state: ProjectState) -> None:
        lg.phase_banner(self.logger, 4, "ARCHITECTURE (Claude)")
        phase4_architecture.run(state, self.cfg, self.logger)

    def _run_coding(self, state: ProjectState) -> None:
        lg.phase_banner(self.logger, 5, "CODING (Gemini + Kimi parallel)")
        phase5_coding.run(state, self.cfg, self.logger)

    def _run_testing(self, state: ProjectState) -> None:
        lg.phase_banner(self.logger, 6, "TESTING (Codex)")
        phase6_testing.run(state, self.cfg, self.logger)

    def _interactive_review(self, state: ProjectState) -> None:
        artifact_name = _REVIEW_ARTIFACTS.get(state.current_phase)
        phase_label = state.current_phase.value

        if artifact_name:
            artifact_path = self.workspace_dir / artifact_name
            try:
                content = json.loads(artifact_path.read_text())
                text = json.dumps(content, indent=2)
                truncated = len(text) > 3000
                print(f"\n--- {phase_label} output ({artifact_name}) ---")
                print(text[:3000])
                if truncated:
                    print(f"  … (truncated — full file: {artifact_path})")
                print("--- end output ---")
            except Exception:
                pass

        if not sys.stdin.isatty():
            return

        while True:
            choice = input(
                f"\nPhase {phase_label} complete. Continue? "
                "[Enter=yes / e=edit artifact / q=quit]: "
            ).strip().lower()
            if choice in ("", "y", "yes"):
                return
            elif choice == "e":
                if artifact_name:
                    editor = os.environ.get("EDITOR", "vi")
                    path = str(self.workspace_dir / artifact_name)
                    subprocess.run([editor, path])
                else:
                    print("  No editable artifact for this phase.")
                return
            elif choice in ("q", "quit", "abort"):
                print(f"Aborted. State saved. Resume with: smooth-bee resume {self.project_name}")
                sys.exit(0)

    def _print_summary(self, state: ProjectState) -> None:
        from smooth_bee import color

        gen_dir = ws.get_generated_dir(self.project_name)
        summary = ws.summarize_phase6(self.project_name)
        file_count, line_count = ws.count_generated_files(self.project_name)

        secs = lg.elapsed_seconds()
        mins, s = divmod(secs, 60)
        duration = f"{mins}m {s}s" if mins else f"{s}s"

        sep = color.cyan_bold("━" * 42)
        ck = color.green("✓")
        cr = color.red("✗")
        warn = color.yellow("⚠")

        lines = [
            "",
            sep,
            color.cyan_bold("  smooth-bee: PROJECT COMPLETE"),
            sep,
            f"  Project:   {self.project_name}",
            f"  Duration:  {duration}",
            f"  Output:    {gen_dir}",
            "",
            "  Code generated:",
            f"    {file_count} files  |  {line_count} lines",
        ]

        if summary["sections_total"] > 0:
            lines += [
                "",
                "  Tests (phase 6):",
                f"    {summary['sections_total']} sections tested",
                f"    {ck} {summary['sections_passed']} passed   "
                f"{cr} {summary['sections_failed']} failed   "
                f"~ {summary['sections_repaired']} repaired",
            ]
            if summary["security_critical"] == 0 and summary["security_high"] == 0:
                lines += ["", f"  Security:  {ck} No critical issues found"]
                if summary["security_warnings"] > 0:
                    lines.append(
                        f"             {warn} {summary['security_warnings']} warnings"
                        f" — see phase6_results/security_final.json"
                    )
            else:
                lines += [
                    "",
                    f"  Security:  {cr} {summary['security_critical']} critical,"
                    f" {summary['security_high']} high"
                    f" — see phase6_results/security_final.json",
                ]

        lines += [
            "",
            f"  smooth-bee logs {self.project_name}",
            sep,
            "",
        ]

        print("\n".join(lines))
        self.logger.info(
            f"BUILD COMPLETE: {self.project_name} | {file_count} files | "
            f"{summary['sections_passed']}/{summary['sections_total']} tests passed"
        )
