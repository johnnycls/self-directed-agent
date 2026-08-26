import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from self_directed_agent import config
from self_directed_agent.errors import AgentError
from self_directed_agent.history import build_messages, load_history, repair_history


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

    def test_middle_truncation_handles_odd_and_small_limits(self) -> None:
        from self_directed_agent.history import truncate_middle

        self.assertEqual(truncate_middle("abcdef", 5), "ab\n...\nef")
        self.assertEqual(truncate_middle("abcdef", 1), "\n...\n")

    def test_user_content_is_not_sliced_but_other_content_is(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "history.jsonl").write_text(
                json.dumps({"role": "user", "content": "0123456789"})
                + "\n"
                + json.dumps({"role": "assistant", "content": "abcdefghij"})
                + "\n",
                encoding="utf-8",
            )
            Path(directory, "memory.md").write_text("memory", encoding="utf-8")
            with patch.object(config, "CONFIG_DIR", directory):
                messages = build_messages("prompt", 10, 6)
        self.assertEqual(messages[1]["content"], "0123456789")
        self.assertEqual(messages[2]["content"], "abc\n...\nhij")

    def test_invalid_history_message_returns_agent_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "history.jsonl").write_text("42\n", encoding="utf-8")
            with patch.object(config, "CONFIG_DIR", directory):
                with self.assertRaises(AgentError):
                    load_history()


if __name__ == "__main__":
    unittest.main()
