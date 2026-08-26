"""LLM message assembly, memory loading, and message commit."""

from typing import Any

from amnesia_genius import display
from amnesia_genius.config import global_path, read_text
from amnesia_genius.history import Message, append_history


def truncate_middle(text: str, max_chars: int) -> str:
    """Keep both ends of text when it exceeds the configured limit."""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    tail = text[-half:] if half else ""
    return f"{text[:half]}\n...\n{tail}"


def _load_memory() -> str:
    """Read the agent's always-visible memory file (memory.md)."""
    return read_text(global_path("memory.md"))


def build_messages(
    system_prompt: str,
    user_input: str,
    turn_messages: list[Message],
    max_context_message_chars: int,
) -> list[Message]:
    """Assemble the per-turn LLM context: system, user input, and turn messages."""
    messages: list[Message] = [
        {"role": "system", "content": f"{system_prompt}\n\n{_load_memory()}"},
        {"role": "user", "content": user_input},
    ]
    for message in turn_messages:
        content: Any = message.get("content")
        if (
            message.get("role") not in ("user", "system")
            and isinstance(content, str)
            and len(content) > max_context_message_chars
        ):
            message = {
                **message,
                "content": truncate_middle(content, max_context_message_chars),
            }
        messages.append(message)
    return messages


def commit_message(message: Message) -> None:
    """Persist a message to the log and render it to the terminal."""
    append_history(message)
    display.print_message(message)
