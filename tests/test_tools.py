import asyncio
import os
import shlex
import subprocess
import sys
import unittest
from unittest.mock import AsyncMock, patch

from amnesia_genius.tools import execute_tool_calls, run_bash


def python_command(source: str) -> str:
    args = [sys.executable, "-c", source]
    return subprocess.list2cmdline(args) if os.name == "nt" else shlex.join(args)


class ToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_output_is_returned(self) -> None:
        command = python_command("print('x' * 100)")
        result = await run_bash(command)
        self.assertIn("x" * 100, result)
        self.assertIn("exit code: 0", result)
        self.assertNotIn("...", result)

    async def test_tool_calls_run_concurrently_and_return_in_order(self) -> None:
        calls = [
            {"id": "one", "function": {"arguments": '{"command":"one"}'}},
            {"id": "two", "function": {"arguments": '{"command":"two"}'}},
        ]
        observed: list[str] = []
        all_started = asyncio.Event()

        async def fake_run(call: dict[str, object], *args: object) -> str:
            observed.append(str(call["id"]))
            if len(observed) == len(calls):
                all_started.set()
            await all_started.wait()
            return f"result-{call['id']}"

        with patch("amnesia_genius.tools.run_tool_call", new=AsyncMock(side_effect=fake_run)):
            messages = await asyncio.wait_for(execute_tool_calls(calls), timeout=1)

        self.assertEqual(set(observed), {"one", "two"})
        self.assertEqual(
            [message["tool_call_id"] for message in messages], ["one", "two"]
        )
        self.assertEqual(
            [message["content"] for message in messages], ["result-one", "result-two"]
        )


if __name__ == "__main__":
    unittest.main()
