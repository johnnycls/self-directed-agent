"""Bash command execution and tool-call dispatch."""

import asyncio
import codecs
import json
import os
import signal
import subprocess
from typing import Any, Sequence

from amnesia_genius.history import Message, commit_message, truncate_middle

INTERRUPTED_RESULT: str = "error: interrupted by user"
TIMEOUT_EXIT_CODE: int = -1


async def _read_bounded(
    stream: asyncio.StreamReader, max_chars: int
) -> tuple[str, bool]:
    """Drain a pipe while retaining its beginning and end."""
    retention = max_chars * 2
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    head = ""
    tail = ""
    total_chars = 0
    while True:
        chunk = await stream.read(64 * 1024)
        if not chunk:
            break
        text = decoder.decode(chunk)
        total_chars += len(text)
        if len(head) < retention:
            head += text[: retention - len(head)]
        tail = (tail + text)[-retention:]
    final_text = decoder.decode(b"", final=True)
    total_chars += len(final_text)
    if len(head) < retention:
        head += final_text[: retention - len(head)]
    tail = (tail + final_text)[-retention:]
    if total_chars <= retention:
        return head, False
    return head + tail, True


def _process_options() -> dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


async def _terminate_process(proc: asyncio.subprocess.Process) -> None:
    """Terminate the shell and all descendants started for the command."""
    if proc.returncode is not None:
        return
    try:
        if os.name == "nt":
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


def _format_output(
    stdout: str,
    stderr: str,
    truncated: bool,
    max_command_output_chars: int,
) -> str:
    output = (stdout + stderr).strip() or "(no output)"
    if truncated or len(output) > max_command_output_chars:
        output = truncate_middle(output, max_command_output_chars)
    return output


async def run_bash(
    command: str,
    timeout_seconds: float = 120.0,
    max_command_output_chars: int = 20_000,
) -> str:
    proc: asyncio.subprocess.Process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **_process_options(),
    )
    assert proc.stdout is not None
    assert proc.stderr is not None
    stdout_task = asyncio.create_task(
        _read_bounded(proc.stdout, max_command_output_chars)
    )
    stderr_task = asyncio.create_task(
        _read_bounded(proc.stderr, max_command_output_chars)
    )
    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        await _terminate_process(proc)
        stdout, stderr = await asyncio.gather(stdout_task, stderr_task)
        output = _format_output(
            stdout[0],
            stderr[0],
            stdout[1] or stderr[1],
            max_command_output_chars,
        )
        return (
            f"exit code: {TIMEOUT_EXIT_CODE}\n"
            f"output: command timed out after {timeout_seconds:g} seconds\n{output}"
        )
    except asyncio.CancelledError:
        await _terminate_process(proc)
        stdout_task.cancel()
        stderr_task.cancel()
        await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
        raise

    stdout, stderr = await asyncio.gather(stdout_task, stderr_task)
    output = _format_output(
        stdout[0],
        stderr[0],
        stdout[1] or stderr[1],
        max_command_output_chars,
    )
    return f"exit code: {proc.returncode}\noutput: {output}"


def parse_command(raw_arguments: str) -> str:
    arguments: Any = json.loads(raw_arguments)
    if not isinstance(arguments, dict):
        raise TypeError("tool arguments must be a JSON object")
    command: Any = arguments["command"]
    if not isinstance(command, str):
        raise TypeError("'command' must be a string")
    return command


async def run_tool_call(
    call: dict[str, Any],
    timeout_seconds: float = 120.0,
    max_command_output_chars: int = 20_000,
) -> str:
    try:
        command: str = parse_command(call["function"]["arguments"])
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return (
            "error: could not parse tool arguments "
            f"({type(e).__name__}: {e}). "
            'Expected a JSON object with a string "command" field.'
        )
    return await run_bash(
        command, timeout_seconds, max_command_output_chars
    )


def tool_message(call: dict[str, Any], content: str) -> Message:
    return {
        "role": "tool",
        "tool_call_id": call["id"],
        "content": content,
    }


async def execute_tool_calls(
    tool_calls: Sequence[dict[str, Any]],
    max_command_output_chars: int = 20_000,
) -> None:
    """Execute independent calls concurrently and commit results in call order."""
    tasks = [
        asyncio.create_task(
            run_tool_call(call, timeout_seconds, max_command_output_chars)
        )
        for call in tool_calls
    ]
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for call in tool_calls:
            commit_message(tool_message(call, INTERRUPTED_RESULT))
        raise

    first_error: BaseException | None = next(
        (result for result in results if isinstance(result, BaseException)),
        None,
    )
    for call, result in zip(tool_calls, results):
        content = INTERRUPTED_RESULT if isinstance(result, BaseException) else result
        commit_message(tool_message(call, content))
    if first_error is not None:
        raise first_error
