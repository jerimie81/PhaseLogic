import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from phaselogic import workspace as ws


SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", "node_modules", ".venv", "venv",
    "dist", "build", ".next", ".gradle", "target",
}

SECRET_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("private_key", re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |)PRIVATE KEY-----")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("generic_secret_assignment", re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"][^'\"]{12,}['\"]"
    )),
)


@dataclass(frozen=True)
class SecretFinding:
    path: str
    line: int
    kind: str
    snippet: str


@dataclass(frozen=True)
class PublishPreflight:
    project_name: str
    generated_dir: str
    repo: str
    branch: str
    base: str
    file_count: int
    secret_findings: list[SecretFinding]
    diff_preview: str
    test_summary: dict

    @property
    def blocks_publish(self) -> bool:
        if self.secret_findings:
            return True
        
        # Block if any tests failed in Phase 6
        if self.test_summary.get("sections_failed", 0) > 0:
            return True
            
        # Block if critical or high security issues exist
        if self.test_summary.get("security_critical", 0) > 0:
            return True
        if self.test_summary.get("security_high", 0) > 0:
            return True
            
        return False

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def build_preflight(project_name: str, repo: str, branch: str, base: str) -> PublishPreflight:
    project_dir = ws.get_path(project_name)
    generated_dir = ws.get_generated_dir(project_name)
    if not generated_dir.exists():
        raise FileNotFoundError(f"Generated output not found: {generated_dir}")

    file_count, _ = ws.count_generated_files(project_name)
    preflight = PublishPreflight(
        project_name=project_name,
        generated_dir=str(generated_dir),
        repo=repo,
        branch=branch,
        base=base,
        file_count=file_count,
        secret_findings=scan_secrets(generated_dir),
        diff_preview=diff_preview(generated_dir),
        test_summary=ws.summarize_phase6(project_name),
    )
    (project_dir / "publish_preflight.json").write_text(preflight.to_json(), encoding="utf-8")
    return preflight


def scan_secrets(root: Path) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for path in _iter_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = str(path.relative_to(root))
        for line_no, line in enumerate(text.splitlines(), 1):
            for kind, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(SecretFinding(
                        path=rel,
                        line=line_no,
                        kind=kind,
                        snippet=_redact(line.strip()),
                    ))
    return findings


def diff_preview(root: Path) -> str:
    if (root / ".git").exists():
        status = _run(["git", "status", "--short"], cwd=root, check=False)
        diff = _run(["git", "diff", "--stat"], cwd=root, check=False)
        parts = []
        if status.stdout.strip():
            parts.append("STATUS:\n" + status.stdout.strip())
        if diff.stdout.strip():
            parts.append("DIFF STAT:\n" + diff.stdout.strip())
        return "\n\n".join(parts) if parts else "No local changes detected."

    files = [str(path.relative_to(root)) for path in _iter_files(root)]
    sample = "\n".join(f"  {f}" for f in files[:50])
    suffix = f"\n  ... {len(files) - 50} more file(s)" if len(files) > 50 else ""
    return f"Generated directory is not a Git repository yet.\nFILES ({len(files)}):\n{sample}{suffix}"


def format_preflight(preflight: PublishPreflight) -> str:
    lines = [
        "",
        "Publish Preflight",
        "-----------------",
        f"Project:       {preflight.project_name}",
        f"Generated dir: {preflight.generated_dir}",
        f"GitHub repo:   {preflight.repo}",
        f"Branch:        {preflight.branch}",
        f"Base:          {preflight.base}",
        f"Files:         {preflight.file_count}",
        "",
        "Phase 6 summary:",
        f"  Sections: {preflight.test_summary.get('sections_passed', 0)}/"
        f"{preflight.test_summary.get('sections_total', 0)} passed",
        f"  Security: {preflight.test_summary.get('security_critical', 0)} critical, "
        f"{preflight.test_summary.get('security_high', 0)} high",
        "",
        "Secret scan:",
    ]
    if preflight.secret_findings:
        for finding in preflight.secret_findings:
            lines.append(
                f"  BLOCK {finding.path}:{finding.line} "
                f"{finding.kind} {finding.snippet}"
            )
    else:
        lines.append("  No secret-looking values found.")

    lines += [
        "",
        "Diff preview:",
        preflight.diff_preview,
        "",
        "Preflight report written to publish_preflight.json",
    ]
    return "\n".join(lines)


def _iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def _redact(value: str) -> str:
    if len(value) <= 24:
        return "<redacted>"
    return value[:12] + "..." + value[-6:]


def _run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{' '.join(cmd)} failed: {detail}")
    return result
