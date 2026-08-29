import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from amnesia_genius import config
from amnesia_genius.history import append_history


class HistoryTests(unittest.TestCase):
    def test_append_history_writes_one_json_line_per_message(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(config, "CONFIG_DIR", directory):
                append_history({"role": "user", "content": "hi"})
                append_history({"role": "assistant", "content": "ok"})
            lines = (
                Path(directory, "history.jsonl").read_text(encoding="utf-8").splitlines()
            )
        self.assertEqual(
            [json.loads(line) for line in lines],
            [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "ok"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
