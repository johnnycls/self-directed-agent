import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from amnesia_genius import config
from amnesia_genius.message import build_messages, truncate_middle


class MessageTests(unittest.TestCase):
    def test_middle_truncation_handles_odd_and_small_limits(self) -> None:
        self.assertEqual(truncate_middle("abcdef", 5), "ab\n...\nef")
        self.assertEqual(truncate_middle("abcdef", 1), "\n...\n")

    def test_user_content_is_not_sliced_but_other_content_is(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "memory.md").write_text("memory", encoding="utf-8")
            with patch.object(config, "CONFIG_DIR", directory):
                messages = build_messages(
                    "prompt",
                    "0123456789",
                    [{"role": "assistant", "content": "abcdefghij"}],
                    6,
                )
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[1]["content"], "0123456789")
        self.assertEqual(messages[2]["content"], "abc\n...\nhij")


if __name__ == "__main__":
    unittest.main()
