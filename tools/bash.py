import subprocess
import uuid
from harness.tools.filesystem import WORKSPACE
from harness.tools.registry import tool
from harness.config import (
    ALLOW_LIST,
    DENY_LIST,
    BASH_CPU_LIMIT,
    BASH_MEMORY_LIMIT,
    BASH_PIDS_LIMIT,
    DOCKER_IMAGE,
    BASH_TIMEOUT,
)



# Characters that separate chained commands in bash. We check the first
# token of every segment, so `pip install foo && rm -rf /` gets both
# `pip` and `rm` checked, not just `pip`.
_CHAIN_SEPARATORS = ("&&", "||", ";", "|")


def _first_token(segment: str) -> str:
    """Return the first whitespace-separated token of a command segment."""
    segment = segment.strip()
    if not segment:
        return ""
    return segment.split()[0]


def _segments(command: str) -> list[str]:
    """Split a shell command on chain separators into its segments."""
    segments = [command]
    for sep in _CHAIN_SEPARATORS:
        segments = [piece for seg in segments for piece in seg.split(sep)]
    return segments


def _check_policy(command: str) -> str | None:
    """Check the command against the allow-list and deny-list.

    Returns None if the command is permitted, or an error string if not.
    Deny-list wins on conflict — a command on both lists is rejected.
    """
    tokens = [_first_token(s) for s in _segments(command)]
    tokens = [t for t in tokens if t]

    if DENY_LIST:
        for token in tokens:
            if token in DENY_LIST:
                return f"[policy] '{token}' is on the deny-list — refusing to run."

    if ALLOW_LIST:
        for token in tokens:
            if token not in ALLOW_LIST:
                return (
                    f"[policy] '{token}' is not on the allow-list — refusing to run. "
                    f"Allow-list currently permits: {', '.join(sorted(ALLOW_LIST))}."
                )

    return None


@tool
def bash(command: str) -> str:
    """Execute a shell command in the workspace directory. Returns combined
    stdout and stderr. Supports pipes, redirects, and command chaining."""
    policy_error = _check_policy(command)
    if policy_error:
        return policy_error

    container_name = f"harness-bash-{uuid.uuid4().hex[:12]}"

    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--name", container_name,
                "-v", f"{WORKSPACE}:/workspace",
                "-w", "/workspace",
                "--network", "none",
                "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges",
                "--memory", BASH_MEMORY_LIMIT,
                "--cpus", BASH_CPU_LIMIT,
                "--pids-limit", BASH_PIDS_LIMIT,
                DOCKER_IMAGE,
                "sh", "-c", command,
            ],
            capture_output=True,
            text=True,
            timeout=BASH_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        # subprocess's timeout only kills the local `docker run` client — the
        # container itself keeps running in the daemon until it exits on its
        # own, since we never told the daemon to stop it. `docker kill` does
        # that; `--rm` then removes the container once it's stopped.
        subprocess.run(
            ["docker", "kill", container_name],
            capture_output=True,
            text=True,
        )
        return f"[timeout] command exceeded {BASH_TIMEOUT}s — killed."

    output = result.stdout + result.stderr
    return output if output else f"(no output, exit code {result.returncode})"

