import subprocess
from harness.tools.filesystem import WORKSPACE
from harness.tools.registry import tool

def _run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout.strip() or result.stderr.strip()
    if result.returncode != 0:
        return f"[git exit {result.returncode}] {output}"
    return output or "(no output)"


if not (WORKSPACE / ".git").exists():
    _run_git("init")
    _run_git("config", "user.name", "agent")
    _run_git("config", "user.email", "agent@harness.local")


@tool
def git_status() -> str:
    """Show the current working-tree status — modified, staged, and untracked files."""
    return _run_git("status", "--short")


@tool
def git_diff(path: str = "") -> str:
    """Show unstaged changes in the workspace. Optionally restrict to a single path."""
    args = ["diff"]
    if path:
        args.append(path)
    return _run_git(*args)


@tool
def git_log(limit: int = 10) -> str:
    """Show recent commit history. Defaults to the last 10 commits."""
    return _run_git("log", f"--max-count={limit}", "--oneline")


@tool
def git_commit(message: str) -> str:
    """Stage all current changes and commit them with the given message.
    Returns the commit hash on success, or an error on failure (e.g., nothing to commit)."""
    _run_git("add", "-A")
    return _run_git("commit", "-m", message)