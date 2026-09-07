"""Cross-session memory: the AGENTS.md pattern.

The harness reads AGENTS.md from the workspace at session start and
injects its contents as a second system message. The agent uses its
existing `write` tool to update the file as it learns.
"""

import os
from datetime import date
from pathlib import Path
from harness.tools.filesystem import WORKSPACE
from harness.tools.registry import tool
from harness.tools.git import _run_git

# The single memory file for the workspace.
AGENTS_MD_PATH = WORKSPACE / "AGENTS.md"

# System prompt for the session-end consolidation call — separate from
# prompt_system.txt because this is a one-shot maintenance task, not
# behavior for the chat agent itself.
CONSOLIDATE_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "prompt_consolidate.txt"


# The template written when AGENTS.md doesn't yet exist. The section
# headings and inline hints serve as guidance for the model — both
# when reading (it knows what each section is for) and when writing
# (it knows what kind of content belongs where).
AGENTS_MD_TEMPLATE = """\
# Project Memory

> This file is the agent's durable memory across sessions — facts about
> this project, not instructions about how to behave. It is loaded at
> the start of every session.

## Project context
What this project is, what it does, who it's for. Save when: you learn
a fact about the project's purpose or audience that isn't obvious from
the code. Example: "this is a CLI harness for a course on building
coding agents, not a production service."

## Conventions
Code style, naming patterns, libraries used, tool preferences. Save
when: you notice a repeated pattern the user follows or asks you to
follow. Example: "tool functions always return a string, never raise
uncaught exceptions."

## Decisions
Choices that have been made and the reasoning behind them. Save when:
the user picks one approach over another and states or implies why.
Example: "using atomic writes (temp file + os.replace) for AGENTS.md
to avoid corruption on crash — decided over a plain write() call."

## Gotchas
Non-obvious behavior that could trip up a future session — quirks,
surprising dependencies, common mistakes. Save when: something behaved
unexpectedly and you had to work out why. Example: "registering a tool
twice under the same name silently overwrites the first one — no
error is raised."

## Active tasks
What's currently being worked on. Save when: the user starts a
multi-step piece of work that will span sessions. Clear the entry when
it's done — this section should reflect the present, not history.
"""


def load_agents_md() -> str:
    """Read AGENTS.md from the workspace, creating it from a template if missing.

    Returns the file's full contents as a string, ready to be used as
    the content of a system message.
    """
    # Step 1: ensure the file exists. If not, write the template — this is
    # the hard constraint that guarantees the agent never sees a missing-memory
    # state. Parallel to git's auto-init in 3.3.
    if not AGENTS_MD_PATH.exists():
        AGENTS_MD_PATH.write_text(AGENTS_MD_TEMPLATE)

    # Step 2: read and return the contents. The harness will wrap this in
    # a system message before sending it to the model.
    return AGENTS_MD_PATH.read_text()


@tool
def remember(section: str, note: str) -> str:
    """Append a timestamped note to a section of AGENTS.md, the durable
    cross-session memory file. `section` must exactly match an existing
    '## Heading' in AGENTS.md (e.g. 'Gotchas', 'Decisions').

    Choose the section whose "Save when" criterion in AGENTS.md matches
    this note — a repeated pattern is a Convention, a choice made for a
    reason is a Decision, unexpected behavior you had to debug is a
    Gotcha. Pick exactly one section per note; if none fit, don't call
    this tool.

    `note` should be the fact itself, nothing else — do not include a
    date or timestamp in it, one is added automatically."""
    lines = AGENTS_MD_PATH.read_text().splitlines()

    heading = f"## {section}"
    heading_index = None
    for i, line in enumerate(lines):
        if line == heading:
            heading_index = i
            break

    if heading_index is None:
        return f"error: no section '## {section}' in AGENTS.md"

    boundary_index = len(lines)
    for i in range(heading_index + 1, len(lines)):
        if lines[i].startswith("## "):
            boundary_index = i
            break

    new_line = f"- [{date.today()}] {note}"
    lines.insert(boundary_index, new_line)

    new_content = "\n".join(lines)
    tmp_path = AGENTS_MD_PATH.with_suffix(".tmp")
    tmp_path.write_text(new_content)
    os.replace(tmp_path, AGENTS_MD_PATH)

    # Commit scoped to AGENTS.md only — not `git add -A` — so the audit
    # trail's commit message always matches exactly what it changed, even
    # if other unrelated files are dirty in the workspace at the same time.
    _run_git("add", str(AGENTS_MD_PATH))
    _run_git("commit", "-m", f"remember: [{section}] {note}")

    return f"remembered under '{section}': {note}"


def consolidate_memory(client, model: str) -> None:
    """Rewrite AGENTS.md at session end: merge notes that describe the same
    fact/task at different points in its evolution, and drop finished
    active tasks. Never invents or discards facts — see prompt_consolidate.txt
    for the exact rules. Commits the result, scoped to AGENTS.md only, same
    as `remember`.

    Runs a single dedicated API call — separate from the main chat loop —
    so a bad or empty response can't corrupt AGENTS.md: nothing is written
    unless the model returns non-empty content.
    """
    current_content = AGENTS_MD_PATH.read_text()
    system_prompt = CONSOLIDATE_PROMPT_PATH.read_text()

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": current_content}],
    )

    new_content = "".join(
        block.text for block in response.content if block.type == "text"
    )
    if not new_content.strip():
        return

    tmp_path = AGENTS_MD_PATH.with_suffix(".tmp")
    tmp_path.write_text(new_content)
    os.replace(tmp_path, AGENTS_MD_PATH)

    _run_git("add", str(AGENTS_MD_PATH))
    _run_git("commit", "-m", "memory: session-end consolidation")


