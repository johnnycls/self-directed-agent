"""Conversation history persistence, repair, and message assembly."""

import json
from typing import Any

from amnesia_genius import display
from amnesia_genius.config import global_path, read_text
from amnesia_genius.errors import AgentError

Message = dict[str, Any]
VALID_ROLES = {"user", "assistant", "tool"}


def truncate_middle(text: str, max_chars: int) -> str:
    """Keep both ends of text when it exceeds the configured limit."""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    tail = text[-half:] if half else ""
    return f"{text[:half]}\n...\n{tail}"


def history_file() -> str:
    return global_path("history.jsonl")


def load_history() -> list[Message]:
    path: str = history_file()
    messages: list[Message] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, 1):
                try:
                    message: Any = json.loads(line)
                except json.JSONDecodeError as e:
                    raise AgentError(
                        f"Malformed JSON in {path} on line {e.lineno}", path=path
                    ) from e
                validate_message(message, line_number, path)
                messages.append(message)
    except OSError as e:
        raise AgentError(f"Cannot read history file {path}: {e}", path=path) from e
    repaired = repair_history(messages)
    validate_history_sequence(repaired, path)
    return repaired


def validate_message(message: Any, line_number: int, path: str) -> None:
    prefix = f"Invalid history message on line {line_number}"
    if not isinstance(message, dict):
        raise AgentError(f"{prefix}: expected a JSON object.", path=path)
    role = message.get("role")
    if role not in VALID_ROLES:
        raise AgentError(
            f"{prefix}: role must be user, assistant, or tool.", path=path
        )
    content = message.get("content")
    if content is not None and not isinstance(content, str):
        raise AgentError(f"{prefix}: content must be a string or null.", path=path)

    if role == "user" and not isinstance(content, str):
        raise AgentError(f"{prefix}: user content must be a string.", path=path)
    if role == "tool":
        if not isinstance(message.get("tool_call_id"), str):
            raise AgentError(
                f"{prefix}: tool_call_id must be a string.", path=path
            )
        if not isinstance(content, str):
            raise AgentError(f"{prefix}: tool content must be a string.", path=path)
    if role == "assistant" and "tool_calls" in message:
        calls = message["tool_calls"]
        if not isinstance(calls, list):
            raise AgentError(f"{prefix}: tool_calls must be a list.", path=path)
        call_ids: list[str] = []
        for call in calls:
            if not isinstance(call, dict) or not isinstance(call.get("id"), str):
                raise AgentError(
                    f"{prefix}: each tool call needs a string id.", path=path
                )
            call_ids.append(call["id"])
            function = call.get("function")
            if (
                call.get("type") != "function"
                or not isinstance(function, dict)
                or not isinstance(function.get("name"), str)
                or not isinstance(function.get("arguments"), str)
            ):
                raise AgentError(
                    f"{prefix}: tool calls must contain a function name and arguments.",
                    path=path,
                )
        if len(call_ids) != len(set(call_ids)):
            raise AgentError(f"{prefix}: tool call ids must be unique.", path=path)


def tool_call_ids(message: Message) -> list[str]:
    calls: Any = message.get("tool_calls", [])
    return [call["id"] for call in calls if isinstance(call, dict) and "id" in call]


def validate_history_sequence(messages: list[Message], path: str) -> None:
    pending: set[str] = set()
    for index, message in enumerate(messages, 1):
        role = message["role"]
        if role == "tool":
            call_id = message["tool_call_id"]
            if call_id not in pending:
                raise AgentError(
                    f"Invalid history sequence on line {index}: unexpected tool result.",
                    path=path,
                )
            pending.remove(call_id)
        else:
            if pending:
                raise AgentError(
                    f"Invalid history sequence on line {index}: tool results are missing.",
                    path=path,
                )
            if role == "assistant":
                pending = set(tool_call_ids(message))

    if pending:
        raise AgentError(
            "Invalid history sequence: tool results are missing at the end.",
            path=path,
        )


def repair_history(messages: list[Message]) -> list[Message]:
    """Drop an incomplete final assistant/tool transaction after interruption."""
    if not messages:
        return messages

    trailing: list[Message] = []
    for message in reversed(messages):
        if message.get("role") != "tool":
            break
        trailing.append(message)
    head_len = len(messages) - len(trailing)

    if trailing:
        if not head_len:
            return []
        anchor = messages[head_len - 1]
        expected = set(tool_call_ids(anchor))
        collected = [message["tool_call_id"] for message in trailing]
        if expected and len(collected) == len(set(collected)) and set(collected) == expected:
            return messages
        return messages[: head_len - 1] if expected else messages[:head_len]

    expected = set(tool_call_ids(messages[-1]))
    return messages[:-1] if expected else messages


def append_history(message: Message) -> None:
    with open(history_file(), "a", encoding="utf-8") as f:
        f.write(json.dumps(message) + "\n")


def commit_message(message: Message) -> None:
    append_history(message)
    display.print_message(message)


def load_memory() -> str:
    return read_text(global_path("memory.md"))


def build_messages(
    system_prompt: str, history_window: int, max_context_message_chars: int
) -> list[Message]:
    recent: list[Message] = load_history()[-history_window:]
    sliced: list[Message] = []
    for message in recent:
        content: Any = message.get("content")
        if (
            message.get("role") != "user"
            and isinstance(content, str)
            and len(content) > max_context_message_chars
        ):
            message = {
                **message,
                "content": truncate_middle(content, max_context_message_chars),
            }
        sliced.append(message)
    return [
        {"role": "system", "content": f"{system_prompt}\n\n{load_memory()}"},
    ] + sliced
