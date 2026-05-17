import subprocess

from phaselogic.connectors.base import BaseConnector, ConnectorCapability, ConnectorStatus
from phaselogic.permissions import Permission


class LocalGitConnector(BaseConnector):
    name = "git"
    display_name = "Local Git"

    @classmethod
    def capabilities(cls) -> tuple[ConnectorCapability, ...]:
        return (
            ConnectorCapability(
                "init_repo",
                "Initialize generated output as a local Git repository",
                (Permission.GIT, Permission.GENERATED_WRITE),
            ),
            ConnectorCapability(
                "commit",
                "Create reviewed commits for generated output",
                (Permission.GIT,),
            ),
            ConnectorCapability(
                "status",
                "Inspect repository state without modifying files",
                (Permission.READ_ONLY,),
            ),
        )

    def health_check(self) -> ConnectorStatus:
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return ConnectorStatus(
                self.name,
                False,
                f"git unavailable: {e}",
                self.capabilities(),
            )

        if result.returncode != 0:
            detail = result.stderr.strip() or "git returned non-zero status"
            return ConnectorStatus(self.name, False, detail, self.capabilities())

        return ConnectorStatus(
            self.name,
            True,
            result.stdout.strip(),
            self.capabilities(),
        )
