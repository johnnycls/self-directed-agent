"""Conversation history persistence, repair, and message assembly."""

import json
from typing import Any

from self_directed_agent import display
from self_directed_agent.config import global_path, read_text
from self_directed_agent.errors import AgentError

Message = dict[str, Any]


def history_file() -> str:
    return global_path("history.jsonl")


def load_history() -> list[Message]:
    path: str = history_file()
    try:
        with open(path, "r", encoding="utf-8") as f:
            messages: list[Message] = [json.loads(line) for line in f]
    except OSError as e:
        raise AgentError(f"Cannot read history file {path}: {e}", path=path) from e
    except json.JSONDecodeError as e:
        raise AgentError(
            f"Malformed JSON in {path} on line {e.lineno}", path=path
        ) from e
    return repair_history(messages)


def tool_call_ids(message: Message) -> list[str]:
    return [call["id"] for call in message.get("tool_calls", [])]


def repair_history(messages: list[Message]) -> list[Message]:
    if not messages:
        return messages
    trailing: list[Message] = []
    for message in reversed(messages):
        if message.get("role") != "tool":
            break
        trailing.append(message)
    head_len: int = len(messages) - len(trailing)
    if not trailing:
        expected: set[str] = set(tool_call_ids(messages[-1]))
        if expected:
            return messages[:-1]
        return messages
    expected = set(tool_call_ids(messages[head_len - 1])) if head_len else set()
    collected: set[str] = {message["tool_call_id"] for message in trailing}
    if expected and collected == expected:
        return messages
    if expected:
        return messages[:head_len - 1]
    return messages[:head_len]


def append_history(message: Message) -> None:
    with open(history_file(), "a", encoding="utf-8") as f:
        f.write(json.dumps(message) + "\n")


def commit_message(message: Message) -> None:
    append_history(message)
    display.print_message(message)


def load_memory() -> str:
    return read_text(global_path("memory.md"))


def build_messages(
    system_prompt: str, history_window: int, max_message_chars: int
) -> list[Message]:
    recent: list[Message] = load_history()[-history_window:]
    sliced: list[Message] = []
    for message in recent:
        content: Any = message.get("content")
        if isinstance(content, str) and len(content) > max_message_chars:
            message = {**message, "content": content[:max_message_chars] + "..."}
        sliced.append(message)
    return [
        {"role": "system", "content": f"{system_prompt}\n\n{load_memory()}"},
    ] + sliced
