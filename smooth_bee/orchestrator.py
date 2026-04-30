import logging

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


class Orchestrator:
    def __init__(self, project_name: str, cfg: Config):
        self.project_name = project_name
        self.cfg = cfg
        self.workspace_dir = ws.get_path(project_name)
        self.logger = lg.get_logger(project_name)

    def run(self) -> None:
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
                st.advance(state, self.workspace_dir)
                state = st.load(self.workspace_dir)
                memory.log_phase(self.project_name, state.current_phase.value)
            except (AgentError, Exception) as e:
                self.logger.error(f"Phase {state.current_phase.value} failed: {e}")
                st.mark_failed(state, self.workspace_dir, str(e))
                memory.log_phase(self.project_name, "FAILED", str(e))
                raise

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

    def _print_summary(self, state: ProjectState) -> None:
        gen_dir = ws.get_generated_dir(self.project_name)
        self.logger.info(
            f"\n{'='*50}\n"
            f"  BUILD COMPLETE: {self.project_name}\n"
            f"  Generated project: {gen_dir}\n"
            f"  Sections: {len(state.sections_coded)} coded, {len(state.sections_tested)} tested\n"
            f"{'='*50}"
        )
