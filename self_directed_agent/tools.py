"""Bash command execution and tool-call dispatch."""

import asyncio
import json
from typing import Any, Sequence

from self_directed_agent.history import Message, commit_message

INTERRUPTED_RESULT: str = "error: interrupted by user"


async def run_bash(command: str) -> str:
    proc: asyncio.subprocess.Process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout: bytes
        stderr: bytes
        stdout, stderr = await proc.communicate()
    except asyncio.CancelledError:
        proc.kill()
        await proc.wait()
        raise
    output: str = (stdout + stderr).decode(errors="replace").strip() or "(no output)"
    return f"exit code: {proc.returncode}\noutput: {output}"


def parse_command(raw_arguments: str) -> str:
    arguments: dict[str, Any] = json.loads(raw_arguments)
    command: Any = arguments["command"]
    if not isinstance(command, str):
        raise TypeError("'command' must be a string")
    return command


async def run_tool_call(call: dict[str, Any]) -> str:
    try:
        command: str = parse_command(call["function"]["arguments"])
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return (
            "error: could not parse tool arguments "
            f"({type(e).__name__}: {e}). "
            'Expected a JSON object with a string "command" field.'
        )
    return await run_bash(command)


def tool_message(call: dict[str, Any], content: str) -> Message:
    return {
        "role": "tool",
        "tool_call_id": call["id"],
        "content": content,
    }


async def execute_tool_calls(tool_calls: Sequence[dict[str, Any]]) -> None:
    done: set[str] = set()

    async def run_and_commit(call: dict[str, Any]) -> None:
        result: str = await run_tool_call(call)
        commit_message(tool_message(call, result))
        done.add(call["id"])

    tasks = [asyncio.create_task(run_and_commit(call)) for call in tool_calls]
    try:
        await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for call in tool_calls:
            if call["id"] not in done:
                commit_message(tool_message(call, INTERRUPTED_RESULT))
        raise
