from educreator.runtime.base import AgentRequest, Event, RunResult, collect, run
from educreator.runtime.claude_code import ClaudeCodeRuntime
from educreator.runtime.codex import CodexRuntime


def for_provider(provider: str) -> ClaudeCodeRuntime | CodexRuntime:
    if provider == "claude":
        return ClaudeCodeRuntime()
    if provider == "chatgpt":
        return CodexRuntime()
    raise ValueError(f"provider '{provider}' は使えない（claude か chatgpt）")


__all__ = [
    "AgentRequest",
    "ClaudeCodeRuntime",
    "CodexRuntime",
    "Event",
    "RunResult",
    "collect",
    "for_provider",
    "run",
]
