# Reproducible Demo Template

This template is a deterministic starting point for evaluating PhaseLogic
without inventing a project prompt from scratch. It is optimized for a short
demo: a non-coder describes a useful app, PhaseLogic plans it through the
six-phase pipeline, and the final artifact is a Build Report plus generated
source code.

## Demo Goal

Build a small REST API for tracking workouts, body metrics, and weekly fitness
goals. The project should be easy to test locally and publish to GitHub.

## Quick Smoke Test

Run a dry run first. This verifies PhaseLogic installation, intake, memory, and
toolchain checks without calling LLM providers.

```bash
phaselogic new \
  --name fitness-api-demo \
  --dry-run \
  --intake-file templates/reproducible-demo/phase0_intake.json
```

## Full Demo Run

After provider credentials are configured:

```bash
phaselogic doctor
phaselogic new \
  --name fitness-api-demo \
  --interactive \
  --intake-file templates/reproducible-demo/phase0_intake.json
```

Expected flow:

1. Phase 1 converts the prompt into a structured API specification.
2. Phase 2 scores feasibility and flags scope risks.
3. Phase 3 selects Python, FastAPI, SQLite, and Pytest.
4. Phase 4 splits the project into build, models, API routes, persistence, and tests.
5. Phase 5 generates the files section by section.
6. Phase 6 writes tests, repairs failures, audits security, and gates completion.

## Demo Artifacts

- [prompt.txt](prompt.txt) is the canonical input prompt.
- [phase0_intake.json](phase0_intake.json) is a reproducible intake seed.
- [expected-build-report.md](expected-build-report.md) is the marketing-quality
  report the finished run should resemble.

## Presentation Script

1. Show the single prompt.
2. Run `phaselogic new ... --dry-run` to prove local setup.
3. Show the six-phase pipeline in the main README.
4. Run the full command when credentials and sandbox prerequisites are ready.
5. Open the generated `BUILD_REPORT.md` and explain the proof-of-work trail.
