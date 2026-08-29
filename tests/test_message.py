import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from amnesia_genius import config
from amnesia_genius.message import build_messages, truncate_middle


class MessageTests(unittest.TestCase):
    def test_middle_truncation_respects_the_limit(self) -> None:
        self.assertEqual(truncate_middle("abcdef", 6), "abcdef")
        self.assertEqual(truncate_middle("abcdefghij", 8), "ab\n...\nj")
        self.assertEqual(truncate_middle("abcdefghij", 7), "a\n...\nj")
        self.assertEqual(truncate_middle("abcdefghij", 5), "\n...\n")
        self.assertEqual(truncate_middle("abcdefghij", 1), "\n")

    def test_truncation_never_exceeds_the_limit(self) -> None:
        for limit in range(1, 30):
            result = truncate_middle("x" * 100, limit)
            self.assertLessEqual(len(result), max(limit, 5))

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
        self.assertEqual(messages[2]["content"], "\n...\n")


if __name__ == "__main__":
    unittest.main()
