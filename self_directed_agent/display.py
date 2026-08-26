"""Pretty terminal rendering of conversation messages."""

import json
import re
import sys
from typing import Any

MAX_TOOL_LINES: int = 20

EXIT_PATTERN = re.compile(r"exit code: (-?\d+)")

ENABLE_VIRTUAL_TERMINAL_PROCESSING: int = 0x0004


def _enable_ansi() -> None:
    if sys.platform != "win32":
        return
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-11)
    mode = ctypes.c_uint32()
    if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        kernel32.SetConsoleMode(
            handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
        )


_enable_ansi()


def clear() -> None:
    sys.stdout.write("\x1b[2J\x1b[1H")
    sys.stdout.flush()


def erase_line() -> None:
    sys.stdout.write("\x1b[2K\r")
    sys.stdout.flush()


def bold(text: str) -> str:
    return f"\x1b[1m{text}\x1b[0m"


def dim(text: str) -> str:
    return f"\x1b[2m{text}\x1b[0m"


def green(text: str) -> str:
    return f"\x1b[32m{text}\x1b[0m"


def red(text: str) -> str:
    return f"\x1b[31m{text}\x1b[0m"


def cyan(text: str) -> str:
    return f"\x1b[36m{text}\x1b[0m"


def print_user(text: str) -> None:
    print(f"{cyan('user')}: {text}")


def _tool_command(call: dict[str, Any]) -> str:
    raw: Any = call.get("function", {}).get("arguments", "")
    try:
        arguments: Any = json.loads(raw)
        command: Any = arguments["command"]
        if isinstance(command, str):
            return command
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return str(raw)


def print_assistant(message: dict[str, Any]) -> None:
    content: str = message.get("content") or ""
    calls: list[dict[str, Any]] = message.get("tool_calls") or []
    if content:
        print(bold(content))
    for call in calls:
        print(dim(f"$ {_tool_command(call)}"))


def print_tool(content: str) -> None:
    lines: list[str] = content.splitlines()
    match = EXIT_PATTERN.match(lines[0]) if lines else None
    if match is None:
        print(dim(content))
        return
    code: int = int(match.group(1))
    status: str = green(f"exit code {code}") if code == 0 else red(f"exit code {code}")
    print(status)
    body: list[str] = lines[1:]
    for line in body[:MAX_TOOL_LINES]:
        print(dim(f"  {line}"))
    hidden: int = len(body) - MAX_TOOL_LINES
    if hidden > 0:
        print(dim(f"  ... ({hidden} more lines — full text in history.jsonl)"))


def print_message(message: dict[str, Any]) -> None:
    role: str = message["role"]
    if role == "user":
        print_user(message.get("content") or "")
    elif role == "assistant":
        print_assistant(message)
    elif role == "tool":
        print_tool(message.get("content") or "")


def print_history(messages: list[dict[str, Any]]) -> None:
    for message in messages:
        print_message(message)
