import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from amnesia_genius import config
from amnesia_genius.errors import AgentError
from amnesia_genius.history import load_history, repair_history


def assistant_with_call(call_id: str) -> dict[str, object]:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": "bash", "arguments": '{"command":"echo ok"}'},
            }
        ],
    }


class HistoryTests(unittest.TestCase):
    def test_incomplete_final_tool_transaction_is_removed(self) -> None:
        assistant = assistant_with_call("call-1")
        messages = [
            {"role": "user", "content": "run it"},
            assistant,
        ]
        self.assertEqual(repair_history(messages), messages[:1])

    def test_complete_tool_transaction_is_preserved(self) -> None:
        assistant = assistant_with_call("call-1")
        messages = [
            {"role": "user", "content": "run it"},
            assistant,
            {"role": "tool", "tool_call_id": "call-1", "content": "ok"},
        ]
        self.assertEqual(repair_history(messages), messages)

    def test_invalid_history_message_returns_agent_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "history.jsonl").write_text("42\n", encoding="utf-8")
            with patch.object(config, "CONFIG_DIR", directory):
                with self.assertRaises(AgentError):
                    load_history()

    def test_midfile_corruption_returns_agent_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines = (
                '{"role": "user", "content": "hi"}\n'
                "not-json\n"
                '{"role": "user", "content": "bye"}\n'
            )
            Path(directory, "history.jsonl").write_text(lines, encoding="utf-8")
            with patch.object(config, "CONFIG_DIR", directory):
                with self.assertRaises(AgentError):
                    load_history()

    def test_trailing_incomplete_transaction_is_repaired(self) -> None:
        assistant = assistant_with_call("call-1")
        lines = (
            json.dumps({"role": "user", "content": "run it"})
            + "\n"
            + json.dumps(assistant)
            + "\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "history.jsonl").write_text(lines, encoding="utf-8")
            with patch.object(config, "CONFIG_DIR", directory):
                repaired = load_history()
        self.assertEqual(repaired, [{"role": "user", "content": "run it"}])


if __name__ == "__main__":
    unittest.main()
