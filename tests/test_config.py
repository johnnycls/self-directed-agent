import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from amnesia_genius import config
from amnesia_genius.errors import AgentError


class ConfigTests(unittest.TestCase):
    def write_config(self, directory: str, **updates: object) -> None:
        values: dict[str, object] = {
            "model": "openai/test",
            "max_context_message_chars": 1000,
        }
        values.update(updates)
        Path(directory, "config.json").write_text(json.dumps(values), encoding="utf-8")

    def test_model_must_be_a_non_empty_string(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.write_config(directory, model=42)
            with patch.object(config, "CONFIG_DIR", directory):
                with self.assertRaises(AgentError):
                    config.load_config()

    def test_bash_tool_schema_is_checked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "bash_tool.json").write_text(
                json.dumps({"type": "function", "function": {"name": "bash"}}),
                encoding="utf-8",
            )
            with patch.object(config, "CONFIG_DIR", directory):
                with self.assertRaises(AgentError):
                    config.load_bash_tool()


if __name__ == "__main__":
    unittest.main()
