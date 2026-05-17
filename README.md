# PhaseLogic

**Build professional software from a plain English description.**

PhaseLogic coordinates four specialized AI agents through a six-phase pipeline — from idea to tested, production-ready code — with no programming knowledge required.

---

## How it works

You describe what you want to build. PhaseLogic runs it through six automated phases:

| Phase | Default Agent | What happens |
|-------|---------------|--------------|
| 1 — Spec | Claude (Sonnet) | Turns your description into a structured technical specification |
| 2 — Feasibility | Gemini (Flash) | Assesses scope, flags risks, confirms the plan is buildable |
| 3 — Research | Gemini (Flash) | Identifies the best frameworks, libraries, and toolchains |
| 4 — Architecture | Claude (Sonnet) | Designs the file structure and assigns sections to agents |
| 5 — Coding | Gemini (Flash) | Generates all source files in parallel |
| 6 — Testing | Codex (GPT-4o) | Writes tests, fixes bugs, and audits for security |

*Note: All agents are configurable. You can swap any phase to use Claude, Gemini, Codex, or local models via Ollama.*

Each phase produces a reviewable artifact. Run with `--interactive` to inspect and edit outputs between phases.

---

## Requirements

- Python 3.11+
- [Claude Code CLI](https://claude.ai/code) (free, browser login)
- Gemini API key — [get one free](https://aistudio.google.com/app/apikey)
- OpenAI API key — [platform.openai.com](https://platform.openai.com/api-keys)
- (Optional) [Ollama](https://ollama.com/) for local LLM support

---

## Installation

**From source (recommended for now):**

```bash
git clone https://github.com/jerimie81/PhaseLogic.git
cd PhaseLogic
pip install -e .
```

**Debian/Ubuntu (.deb):**

```bash
./build_deb.sh
sudo dpkg -i phaselogic_0.1.0_all.deb
```

---

## Setup

On first run, PhaseLogic walks you through entering your API keys:

```bash
phaselogic new "my project idea"
```

Or check your environment manually:

```bash
phaselogic doctor
```

Keys can also be set via environment variables:

```bash
export GEMINI_API_KEY=...
export KIMI_API_KEY=...
export OPENAI_API_KEY=...
```

Or in a config file at `~/.config/phaselogic/config.toml` (see `config.toml` for the full schema).

---

## Usage

```bash
# Start a new project
phaselogic new "a REST API for tracking personal fitness goals"

# With interactive phase review (pause and edit between phases)
phaselogic new "a budget tracker app" --interactive

# Control how many questions are asked before building
phaselogic new "a web scraper" --aggressiveness 1   # minimal (2 questions)
phaselogic new "a web scraper" --aggressiveness 5   # exhaustive (15 questions)

# Resume an interrupted project
phaselogic resume my-project-name

# Resume from a specific phase
phaselogic resume my-project-name --phase CODING

# List all projects
phaselogic list

# Show project status and phase progress
phaselogic status my-project-name

# Tail the latest session log
phaselogic logs my-project-name

# Delete a project
phaselogic delete my-project-name

# Delete all failed projects
phaselogic clean
```

---

## Configuration

`~/.config/phaselogic/config.toml` (user) or `/etc/phaselogic/config.toml` (system):

```toml
[claude]
model = "claude-sonnet-4-6"

[gemini]
api_key = ""          # or GEMINI_API_KEY env var
model = "gemini-2.0-flash"

[kimi]
api_key = ""          # or KIMI_API_KEY env var
model = "moonshot-v1-32k"
base_url = "https://api.moonshot.ai/v1"

[codex]
api_key = ""          # or OPENAI_API_KEY env var
model = "gpt-4o"

[ollama]
base_url = "http://localhost:11434"
model = "llama3"

[phases]
# Assign agents to specific phases (claude, gemini, kimi, codex, or ollama)
spec = "claude"
feasibility = "gemini"
research = "gemini"
architecture = "claude"
coding = "gemini"
testing = "codex"

[orchestration]
timeout_seconds = 120
max_retries = 3
retry_backoff_base = 2.0

[sandbox]
enabled = true
required = true
image = "python:3.11-slim"
allow_network = false
memory = "2g"
cpus = "2"
timeout_seconds = 300

[intake]
# 1=minimal  2=light  3=balanced (default)  4=thorough  5=exhaustive
aggressiveness = 3
```

### Agent profiles

Reusable agent profiles live in `~/.config/phaselogic/agents/*.toml`.

```bash
phaselogic agents create-template backend-builder
phaselogic agents list
phaselogic agents validate backend-builder
phaselogic agents show backend-builder
```

Profiles define provider/model, role, personality, phase fit, abilities, knowledge
sources, workspace permissions, cost/speed preferences, and safety constraints.

### Integrations

Lifecycle integrations are managed separately from LLM agents:

```bash
phaselogic integrations list
phaselogic integrations status git
phaselogic integrations connect git
phaselogic integrations status github
```

The initial connector foundation includes local Git and GitHub capability
metadata. GitHub publishing uses the local `git` and `gh` CLIs.

### Publishing

Publish generated output to GitHub through a preflight gate:

```bash
phaselogic publish my-project \
  --provider github \
  --repo owner/repo \
  --branch phaselogic/my-project \
  --base main
```

Before pushing, PhaseLogic writes `publish_preflight.json`, scans for
secret-looking values, shows a diff/file preview, summarizes Phase 6 results,
and asks for confirmation. In non-interactive environments use `--yes`.
Use `--dry-run` to run the gate without touching GitHub.

### Sandboxing

PhaseLogic creates `.phaselogic/run_in_sandbox.sh` inside generated projects
during Phase 6. Testing agents must run dependency installation, build, test,
lint, and audit commands through this wrapper. The default sandbox has no
network, bounded CPU/memory, and a single generated-project workspace mount.

---

## Output

Generated files are written to:

```
~/.local/share/phaselogic/workspace/<project-name>/generated/
```

Each project workspace also contains phase artifacts (spec, architecture, test results) and session logs.

---

## Cross-project learning

PhaseLogic remembers your preferences across projects using a local SQLite database (`~/.gemini/memory.db`). After a few projects it will:

- Pre-fill answers based on your past choices
- Skip redundant questions at low aggressiveness settings
- Show estimated agent call times based on observed performance
- Index generated files so future projects can reference prior work

---

## License

MIT
