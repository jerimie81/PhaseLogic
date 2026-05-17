import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from phaselogic import paths
from phaselogic.permissions import Permission


@dataclass(frozen=True)
class AgentProfile:
    name: str
    provider: str
    model: str
    role: str = ""
    personality: str = ""
    phase_fit: list[str] = field(default_factory=list)
    abilities: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    knowledge_sources: list[str] = field(default_factory=list)
    workspace_permissions: list[str] = field(default_factory=lambda: [Permission.READ_ONLY.value])
    cost_preference: str = "balanced"
    speed_preference: str = "balanced"
    safety_constraints: list[str] = field(default_factory=list)
    source_path: Path | None = None

    @classmethod
    def from_dict(cls, data: dict, source_path: Path | None = None) -> "AgentProfile":
        return cls(
            name=str(data.get("name", "")).strip(),
            provider=str(data.get("provider", "")).strip().lower(),
            model=str(data.get("model", "")).strip(),
            role=str(data.get("role", "")).strip(),
            personality=str(data.get("personality", "")).strip(),
            phase_fit=_string_list(data.get("phase_fit", [])),
            abilities=_string_list(data.get("abilities", [])),
            tools=_string_list(data.get("tools", [])),
            knowledge_sources=_string_list(data.get("knowledge_sources", [])),
            workspace_permissions=_string_list(
                data.get("workspace_permissions", [Permission.READ_ONLY.value])
            ),
            cost_preference=str(data.get("cost_preference", "balanced")).strip(),
            speed_preference=str(data.get("speed_preference", "balanced")).strip(),
            safety_constraints=_string_list(data.get("safety_constraints", [])),
            source_path=source_path,
        )

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        if not self.name:
            errors.append("name is required")
        if not self.provider:
            errors.append("provider is required")
        if not self.model:
            errors.append("model is required")
        for permission in self.workspace_permissions:
            try:
                Permission(permission)
            except ValueError:
                allowed = ", ".join(p.value for p in Permission)
                errors.append(f"unknown workspace permission '{permission}' (allowed: {allowed})")
        return errors

    def to_toml(self) -> str:
        lines = [
            f'name = {_toml_string(self.name)}',
            f'provider = {_toml_string(self.provider)}',
            f'model = {_toml_string(self.model)}',
            f'role = {_toml_string(self.role)}',
            f'personality = {_toml_string(self.personality)}',
            f'phase_fit = {_toml_list(self.phase_fit)}',
            f'abilities = {_toml_list(self.abilities)}',
            f'tools = {_toml_list(self.tools)}',
            f'knowledge_sources = {_toml_list(self.knowledge_sources)}',
            f'workspace_permissions = {_toml_list(self.workspace_permissions)}',
            f'cost_preference = {_toml_string(self.cost_preference)}',
            f'speed_preference = {_toml_string(self.speed_preference)}',
            f'safety_constraints = {_toml_list(self.safety_constraints)}',
            "",
        ]
        return "\n".join(lines)

    def match_score(self, required_capabilities: list[str]) -> float:
        """Calculate how well this agent matches a set of requirements (0.0 to 1.0)."""
        if not required_capabilities:
            return 1.0
        
        matches = 0
        reqs = [r.lower().strip() for r in required_capabilities]
        # Check against both abilities and role
        agent_capabilities = {a.lower().strip() for a in self.abilities}
        if self.role:
            agent_capabilities.add(self.role.lower().strip())
        
        for req in reqs:
            if req in agent_capabilities:
                matches += 1
            else:
                # Check for partial matches (e.g. 'ui' in 'frontend_ui')
                for cap in agent_capabilities:
                    if req in cap or cap in req:
                        matches += 0.5
                        break
        
        return matches / len(reqs)

    def test(self) -> tuple[bool, str]:
        """Test the connection to the agent provider."""
        from phaselogic.config import load
        from phaselogic.agents import get_agent
        
        try:
            cfg = load()

            if self.provider == "gemini":
                cfg.gemini_model = self.model
            elif self.provider == "kimi":
                cfg.kimi_model = self.model
            elif self.provider == "claude":
                cfg.claude_model = self.model
            elif self.provider == "ollama":
                cfg.ollama_model = self.model
            elif self.provider == "codex":
                cfg.codex_model = self.model

            agent = get_agent(self.provider, cfg)
            result = agent.call(
                "Hello, are you there? Respond with only the word READY.",
                system_prompt="Test connection.",
            )
            if "READY" in result.upper():
                return True, "Connection successful."
            return False, f"Unexpected response: {result}"
            
        except Exception as e:
            return False, f"Connection failed: {str(e)}"


def load_profile(path: Path) -> AgentProfile:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return AgentProfile.from_dict(data, source_path=path)


def load_profiles(project_dir: Path | None = None) -> dict[str, AgentProfile]:
    profiles: dict[str, AgentProfile] = {}
    for directory in _profile_dirs(project_dir):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.toml")):
            profile = load_profile(path)
            if profile.name:
                profiles[profile.name] = profile
    return profiles


def find_best_agent(
    required_capabilities: list[str],
    profiles: dict[str, AgentProfile],
    provider_preference: str | None = None
) -> str | None:
    """Return the name of the best matching agent profile."""
    best_name = None
    best_score = -1.0

    for name, profile in profiles.items():
        score = profile.match_score(required_capabilities)
        
        # Apply provider bonus if requested
        if provider_preference and profile.provider.lower() == provider_preference.lower():
            score += 0.1
            
        if score > best_score:
            best_score = score
            best_name = name
            
    if best_score <= 0:
        return None
    return best_name


def create_template(name: str, directory: Path | None = None) -> Path:
    directory = directory or paths.agent_profiles_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{_slugify(name)}.toml"
    if path.exists():
        raise FileExistsError(f"Agent profile already exists: {path}")
    profile = AgentProfile(
        name=name,
        provider="gemini",
        model="gemini-2.0-flash",
        role="coding",
        personality="pragmatic, precise, and concise",
        phase_fit=["coding"],
        abilities=["generate_code", "explain_tradeoffs"],
        workspace_permissions=[Permission.READ_ONLY.value, Permission.GENERATED_WRITE.value],
        safety_constraints=["do not access secrets", "ask before network, git, cloud, or deploy actions"],
    )
    path.write_text(profile.to_toml(), encoding="utf-8")
    return path


def _profile_dirs(project_dir: Path | None) -> list[Path]:
    dirs = [paths.agent_profiles_dir()]
    if project_dir is not None:
        dirs.append(project_dir / ".phaselogic" / "agents")
    return dirs


def _string_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", value.lower()).strip("-")
    return slug or "agent"


def _toml_string(value: str) -> str:
    return json.dumps(value)


def _toml_list(values: list[str]) -> str:
    return "[" + ", ".join(_toml_string(v) for v in values) + "]"
