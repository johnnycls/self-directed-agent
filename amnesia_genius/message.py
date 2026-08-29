"""LLM message assembly and memory loading."""

from typing import Any

from amnesia_genius.config import global_path, read_text
from amnesia_genius.history import Message


def truncate_middle(text: str, max_chars: int) -> str:
    """Keep both ends of text within the limit, joined by a middle separator."""
    if len(text) <= max_chars:
        return text
    separator = "\n...\n"
    body = max_chars - len(separator)
    if body < 2:
        return separator[:max_chars]
    half = body // 2
    return f"{text[: body - half]}{separator}{text[-half:]}"


def _load_memory(config_dir: str | None = None) -> str:
    """Read the agent's always-visible memory file (memory.md)."""
    return read_text(global_path("memory.md", config_dir))


def build_messages(
    system_prompt: str,
    user_input: str,
    turn_messages: list[Message],
    max_context_message_chars: int,
    config_dir: str | None = None,
) -> list[Message]:
    """Assemble the per-turn LLM context: system, user input, and turn messages."""
    messages: list[Message] = [
        {"role": "system", "content": f"{system_prompt}\n\n{_load_memory(config_dir)}"},
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
