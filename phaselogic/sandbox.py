import subprocess
from dataclasses import dataclass
from pathlib import Path
from shlex import quote


@dataclass(frozen=True)
class SandboxPolicy:
    allow_network: bool = False
    memory: str = "2g"
    cpus: str = "2"
    timeout_seconds: int = 300
    workdir: str = "/workspace"


class DockerSandbox:
    def __init__(self, image: str = "python:3.11-slim", policy: SandboxPolicy | None = None):
        self.image = image
        self.policy = policy or SandboxPolicy()

    def available(self) -> bool:
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    def command(self, project_dir: Path, command: list[str]) -> list[str]:
        project_dir = project_dir.resolve()
        network = "bridge" if self.policy.allow_network else "none"
        return [
            "docker",
            "run",
            "--rm",
            "--network",
            network,
            "--memory",
            self.policy.memory,
            "--cpus",
            self.policy.cpus,
            "--workdir",
            self.policy.workdir,
            "--mount",
            f"type=bind,src={project_dir},dst={self.policy.workdir},rw",
            self.image,
            *command,
        ]

    def shell_command(self, project_dir: Path, command: str) -> list[str]:
        return self.command(project_dir, ["sh", "-lc", command])

    def runner_script(self, project_dir: Path) -> str:
        project_dir = project_dir.resolve()
        network = "bridge" if self.policy.allow_network else "none"
        return "\n".join([
            "#!/usr/bin/env sh",
            "set -eu",
            'if [ "$#" -eq 0 ]; then',
            '  echo "usage: ./.phaselogic/run_in_sandbox.sh <command>" >&2',
            "  exit 2",
            "fi",
            "docker run --rm \\",
            f"  --network {quote(network)} \\",
            f"  --memory {quote(self.policy.memory)} \\",
            f"  --cpus {quote(self.policy.cpus)} \\",
            f"  --workdir {quote(self.policy.workdir)} \\",
            f"  --mount {quote(f'type=bind,src={project_dir},dst={self.policy.workdir},rw')} \\",
            f"  {quote(self.image)} sh -lc \"$*\"",
            "",
        ])

    def write_runner(self, project_dir: Path) -> Path:
        target = project_dir / ".phaselogic" / "run_in_sandbox.sh"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.runner_script(project_dir), encoding="utf-8")
        target.chmod(0o755)
        return target
