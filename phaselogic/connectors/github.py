import subprocess
from dataclasses import dataclass
from pathlib import Path

from phaselogic.connectors.base import BaseConnector, ConnectorCapability, ConnectorStatus
from phaselogic.permissions import Permission


@dataclass(frozen=True)
class GitHubPublishResult:
    pr_url: str
    ci_output: str = ""


class GitHubConnector(BaseConnector):
    name = "github"
    display_name = "GitHub"

    @classmethod
    def capabilities(cls) -> tuple[ConnectorCapability, ...]:
        return (
            ConnectorCapability(
                "push_branch",
                "Push reviewed generated output to a GitHub branch",
                (Permission.GIT, Permission.NETWORK),
            ),
            ConnectorCapability(
                "open_pr",
                "Open a GitHub pull request after local preflight checks",
                (Permission.GIT, Permission.NETWORK),
            ),
            ConnectorCapability(
                "ci_status",
                "Read GitHub pull request check status",
                (Permission.READ_ONLY, Permission.NETWORK),
            ),
        )

    def health_check(self) -> ConnectorStatus:
        missing = []
        details = []
        for cmd in ("git", "gh"):
            result = _run([cmd, "--version"], check=False)
            if result.returncode != 0:
                missing.append(cmd)
            else:
                details.append(result.stdout.strip().splitlines()[0])

        if missing:
            return ConnectorStatus(
                self.name,
                False,
                f"missing command(s): {', '.join(missing)}",
                self.capabilities(),
            )

        auth = _run(["gh", "auth", "status"], check=False)
        if auth.returncode != 0:
            return ConnectorStatus(
                self.name,
                False,
                "gh is installed but not authenticated; run: gh auth login",
                self.capabilities(),
            )

        details.append("gh authenticated")
        return ConnectorStatus(self.name, True, "; ".join(details), self.capabilities())

    def publish(
        self,
        generated_dir: Path,
        repo: str,
        branch: str,
        base: str,
        title: str,
        body: str,
        watch_ci: bool = False,
    ) -> GitHubPublishResult:
        generated_dir = generated_dir.resolve()
        if not (generated_dir / ".git").exists():
            _run(["git", "init"], cwd=generated_dir)

        _ensure_branch(generated_dir, branch)
        _ensure_origin(generated_dir, repo)

        _run(["git", "add", "."], cwd=generated_dir)
        staged = _run(["git", "diff", "--cached", "--quiet"], cwd=generated_dir, check=False)
        if staged.returncode != 0:
            _run(["git", "commit", "-m", f"PhaseLogic publish: {title}"], cwd=generated_dir)

        _run(["git", "push", "-u", "origin", branch], cwd=generated_dir)
        pr = _run([
            "gh", "pr", "create",
            "--repo", repo,
            "--head", branch,
            "--base", base,
            "--title", title,
            "--body", body,
        ], cwd=generated_dir, check=False)

        if pr.returncode != 0:
            existing = _run(
                ["gh", "pr", "view", branch, "--repo", repo, "--json", "url", "--jq", ".url"],
                cwd=generated_dir,
                check=False,
            )
            if existing.returncode != 0:
                raise RuntimeError(pr.stderr.strip() or pr.stdout.strip())
            pr_url = existing.stdout.strip()
        else:
            pr_url = pr.stdout.strip()

        ci_output = ""
        ci_cmd = ["gh", "pr", "checks", pr_url]
        if watch_ci:
            ci_cmd.append("--watch")
        checks = _run(ci_cmd, cwd=generated_dir, check=False)
        ci_output = (checks.stdout or checks.stderr).strip()

        return GitHubPublishResult(pr_url=pr_url, ci_output=ci_output)


def _ensure_branch(generated_dir: Path, branch: str) -> None:
    current = _run(["git", "branch", "--show-current"], cwd=generated_dir, check=False)
    if current.stdout.strip() != branch:
        _run(["git", "checkout", "-B", branch], cwd=generated_dir)


def _ensure_origin(generated_dir: Path, repo: str) -> None:
    remote_url = f"https://github.com/{repo}.git"
    existing = _run(["git", "remote", "get-url", "origin"], cwd=generated_dir, check=False)
    if existing.returncode == 0:
        if existing.stdout.strip() != remote_url:
            _run(["git", "remote", "set-url", "origin", remote_url], cwd=generated_dir)
    else:
        _run(["git", "remote", "add", "origin", remote_url], cwd=generated_dir)


def _run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{' '.join(cmd)} failed: {detail}")
    return result
