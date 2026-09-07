"""Runtime configuration for the harness."""

# -- Model configuration --
MODEL: str = "claude-haiku-4-5"

# Max tokens per model response. Needs headroom for tool calls whose
# arguments include real content (e.g. `write`'s `content` field) —
# too low a value truncates mid-tool-call, producing malformed input.
MAX_TOKENS: int = 8192


# -- ReAct loop bounds --
# Maximum number of tool-call rounds per user turn. When hit, the harness
# forces the model to summarize what it did and hand control back to the
# user, instead of looping indefinitely.
STEP_BUDGET: int = 25

# Message injected when STEP_BUDGET is hit, telling the model to stop
# calling tools and summarize instead of continuing indefinitely.
BUDEGET_HIT_MESSAGE = """\
you have reached the step budget for this turn. do not make any more
tool calls. Instead, respond directly to the user with what you
accomplished, what remains, and what to ask next."""

ALLOW_LIST: set[str] = set()
DENY_LIST= ["pip", "pip3"]

DOCKER_IMAGE = "harness-sandbox"
BASH_TIMEOUT = 30          # seconds, hard cap on one command's runtime
BASH_MEMORY_LIMIT = "512m"
BASH_CPU_LIMIT = "1"
BASH_PIDS_LIMIT = "64"
