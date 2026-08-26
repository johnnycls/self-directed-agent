"""Pretty terminal rendering of conversation messages."""

import json
import re
import sys
from typing import Any

MAX_TOOL_LINES: int = 4

EXIT_PATTERN = re.compile(r"exit code: (-?\d+)")

ENABLE_VIRTUAL_TERMINAL_PROCESSING: int = 0x0004


def _enable_ansi() -> None:
    """Enable ANSI escape processing on Windows consoles."""
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
    """Clear the terminal screen."""
    sys.stdout.write("\x1b[2J\x1b[1H")
    sys.stdout.flush()


def _bold(text: str) -> str:
    """Wrap text in a bold ANSI escape sequence."""
    return f"\x1b[1m{text}\x1b[0m"


def _dim(text: str) -> str:
    """Wrap text in a dim ANSI escape sequence."""
    return f"\x1b[2m{text}\x1b[0m"


def _green(text: str) -> str:
    """Wrap text in a green ANSI escape sequence."""
    return f"\x1b[32m{text}\x1b[0m"


def _red(text: str) -> str:
    """Wrap text in a red ANSI escape sequence."""
    return f"\x1b[31m{text}\x1b[0m"


def _tool_command(call: dict[str, Any]) -> str:
    """Extract the bash command string from a tool-call argument blob."""
    raw: Any = call.get("function", {}).get("arguments", "")
    try:
        arguments: Any = json.loads(raw)
        command: Any = arguments["command"]
        if isinstance(command, str):
            return command
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return str(raw)


def _print_assistant(message: dict[str, Any]) -> None:
    """Render an assistant message (text and tool commands) to the terminal."""
    content: str = message.get("content") or ""
    calls: list[dict[str, Any]] = message.get("tool_calls") or []
    if content:
        print(_bold(content))
    for call in calls:
        print(_dim(f"$ {_tool_command(call)}"))


def _print_tool(content: str) -> None:
    """Render a tool result, highlighting the exit code and printing both ends of long output."""
    lines: list[str] = content.splitlines()
    match = EXIT_PATTERN.match(lines[0]) if lines else None
    if match is None:
        print(_dim(content))
        return
    code: int = int(match.group(1))
    status: str = _green(f"exit code {code}") if code == 0 else _red(f"exit code {code}")
    print(status)
    body: list[str] = lines[1:]
    if len(body) <= MAX_TOOL_LINES:
        for line in body:
            print(_dim(f"  {line}"))
        return
    half = MAX_TOOL_LINES // 2
    for line in body[:half]:
        print(_dim(f"  {line}"))
    print(_dim(f"..."))
    for line in body[-half:]:
        print(_dim(f"  {line}"))


def print_message(message: dict[str, Any]) -> None:
    """Render a single message based on its role."""
    role: str = message["role"]
    if role == "assistant":
        _print_assistant(message)
    elif role == "tool":
        _print_tool(message.get("content") or "")
