# harness

A coding agent harness built from scratch — no agent framework, just the
Anthropic Messages API, a tool registry, and a ReAct loop. Built to
understand how agent harnesses actually work under the hood: tool-call
dispatch, cross-session memory, and command sandboxing, rather than to
depend on an existing one.

## What it does

Run `python -m harness.agent` (from the repository root, one level up
from this folder) and you get a terminal chat loop backed by Claude,
with tools to read/write files, run shell commands, inspect git
history, and search the web — all scoped to a single `workspace/`
directory. The agent also maintains its own durable memory
(`workspace/AGENTS.md`) across sessions: decisions, conventions, and
gotchas it records as it works, each one git-committed as it's
written, and consolidated (deduplicated, stale tasks dropped) at the
end of every session.

## Design decisions

**ReAct loop with a step budget.** Each user turn runs a
Reason → Act → Observe loop (text response → `tool_use` blocks → tool
results fed back in) until the model stops calling tools. A
`STEP_BUDGET` (default 25) caps tool-call rounds per turn — if hit, the
harness forces a `tool_choice: none` call so the model summarizes
progress instead of looping indefinitely.

**Defense-in-depth command execution.** The `bash` tool isn't a bare
`subprocess.run` — it's layered:
1. An allow/deny policy check on the first token of every
   `&&`/`||`/`;`/`|`-separated command segment (fast, cheap, but
   bypassable by design — a string check can't stop `$(...)` or
   aliasing).
2. Real containment underneath: every command runs inside a disposable
   Docker container (`harness-sandbox`, see `docker/Dockerfile`) as a
   non-root user, with `--network none`, all capabilities dropped,
   `--pids-limit` (fork-bomb defense), and memory/CPU caps.
3. A hard subprocess timeout, with an explicit `docker kill` on
   expiry — a bare `subprocess.run(timeout=...)` only kills the local
   `docker` CLI client, not the container itself, which otherwise keeps
   running in the daemon until it exits on its own.

The policy check and the sandbox aren't redundant: the policy check is
a fast, legible first filter; the sandbox is what actually holds if
that filter is bypassed.

**Network access is opt-in and single-purpose.** The sandbox runs with
`--network none`, so `bash` has no network access at all. `search_web`
is the one exception — its own dedicated tool, calling exactly one API
(Firecrawl), rather than something routed through `bash`.

**Memory as facts, not instructions.** `AGENTS.md` (auto-created from a
template on first run) holds project facts — decisions, conventions,
gotchas, active tasks — loaded as a second system message every
session. Behavioral instructions (how to act, when to save memory)
live separately in `prompts/prompt_system.txt`. The `remember` tool
appends timestamped, git-committed notes to the section matching each
note's own "save when" criterion; commits are scoped to `AGENTS.md`
alone (not `git add -A`), so the audit trail's commit message always
matches exactly what it changed. At session end (including on
Ctrl-C/EOF), a separate dedicated API call — driven by
`prompts/prompt_consolidate.txt` — rewrites `AGENTS.md` to merge notes
describing the same fact at different points in time and drop
finished active tasks, without inventing or discarding content; it
only writes back if the model returns a non-empty result.

## Tools

| Tool | Description |
|---|---|
| `read` / `write` / `list` / `mkdir` / `delete` | Filesystem access, sandboxed to `workspace/` via a path-resolution guard (rejects any path that escapes the workspace root). |
| `bash` | Run a shell command inside the Docker sandbox described above. No network access. |
| `git_status` / `git_diff` / `git_log` / `git_commit` | Git operations scoped to `workspace/`. |
| `search_web` | Web search via Firecrawl — the only tool with network access, scoped to one API. Requires `FIRECRAWL_API_KEY`. |
| `remember` | Append a timestamped, git-committed note to a section of `AGENTS.md`. |

## Setup

Requires Python 3.11+, an `ANTHROPIC_API_KEY`, and Docker Desktop
running (for the `bash` tool's sandbox). `FIRECRAWL_API_KEY` is
optional — without it, `search_web` returns an error but everything
else still works.

Run these from the repository root (one level up from this folder):

```bash
pip install -r requirements.txt
cp .env.example .env               # add your ANTHROPIC_API_KEY (and optionally FIRECRAWL_API_KEY)
docker build -t harness-sandbox harness/docker
python -m harness.agent
```

## Project structure

```
harness/
  agent.py                # entry point: ReAct loop
  config.py                # model, budgets, sandbox limits, allow/deny lists
  tools/
    registry.py             # @tool decorator, schema generation, dispatch
    filesystem.py            # read/write/list/mkdir/delete
    bash.py                   # sandboxed shell execution
    git.py                     # git tools + internal _run_git helper
    search_web.py               # web search via Firecrawl
  memory/
    agents_md.py                 # AGENTS.md template, load, remember, consolidate
  prompts/
    prompt_system.txt             # behavioral system prompt
    prompt_consolidate.txt         # session-end AGENTS.md consolidation prompt
  docker/
    Dockerfile                     # sandbox image definition
workspace/                          # the agent's sandboxed working directory
```

## What's not here yet

This is a working harness, not a finished product. Known gaps, roughly
in priority order: automated test suite, retry/backoff on API
failures, structured logging and usage metrics, a growth bound on
`AGENTS.md`, and a proper todo tool (the current "Active tasks" section
is an append-only stand-in).
