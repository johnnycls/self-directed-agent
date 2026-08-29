"""Bash command execution and tool-call dispatch."""

import asyncio
import json
import os
import signal
import subprocess
import sys
from collections.abc import Sequence
from typing import Any

from amnesia_genius.history import Message


def _process_options() -> dict[str, Any]:
    """Return subprocess options that start an independent process group."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


async def _terminate_process(proc: asyncio.subprocess.Process) -> None:
    """Terminate the shell and all descendants started for the command."""
    if proc.returncode is not None:
        return
    try:
        if sys.platform == "win32":
            killer = await asyncio.create_subprocess_exec(
                "taskkill",
                "/PID",
                str(proc.pid),
                "/T",
                "/F",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await killer.wait()
            if proc.returncode is None:
                proc.kill()
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    await proc.wait()


async def run_bash(command: str) -> str:
    """Run a shell command and return its exit code plus combined output.

    The command's own timeout and output shaping are the agent's job (e.g. via
    the shell `timeout` and `head` utilities); the harness captures everything.
    """
    proc: asyncio.subprocess.Process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **_process_options(),
    )
    assert proc.stdout is not None
    assert proc.stderr is not None
    try:
        stdout, stderr = await proc.communicate()
    except asyncio.CancelledError:
        await _terminate_process(proc)
        raise
    output: str = (
        stdout.decode("utf-8", "replace") + stderr.decode("utf-8", "replace")
    ).strip() or "(no output)"
    return f"exit code: {proc.returncode}\noutput: {output}"


def _parse_command(raw_arguments: str) -> str:
    """Extract the 'command' string from a tool-call arguments JSON blob."""
    arguments: Any = json.loads(raw_arguments)
    if not isinstance(arguments, dict):
        raise TypeError("tool arguments must be a JSON object")
    command: Any = arguments["command"]
    if not isinstance(command, str):
        raise TypeError("'command' must be a string")
    return command


async def run_tool_call(call: dict[str, Any]) -> str:
    """Parse a tool call and run its bash command, returning the result text."""
    try:
        command: str = _parse_command(call["function"]["arguments"])
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return (
            "error: could not parse tool arguments "
            f"({type(e).__name__}: {e}). "
            'Expected a JSON object with a string "command" field.'
        )
    return await run_bash(command)


def _tool_message(call: dict[str, Any], content: str) -> Message:
    """Build a tool-result message matching the given tool call."""
    return {
        "role": "tool",
        "tool_call_id": call["id"],
        "content": content,
    }


async def execute_tool_calls(
    tool_calls: Sequence[dict[str, Any]],
) -> list[Message]:
    """Execute independent calls concurrently and return results in call order."""
    tasks = [
        asyncio.create_task(run_tool_call(call)) for call in tool_calls
    ]
    try:
        results = await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    return [_tool_message(call, result) for call, result in zip(tool_calls, results)]
