import json
import tempfile
import unittest
from pathlib import Path

from amnesia_genius.errors import AgentError
from amnesia_genius.kernel import Agent

SEEDED_FILES = (
    "config.json",
    "system_prompt.md",
    "bash_tool.json",
    "memory.md",
    "history.jsonl",
)


class KernelTests(unittest.TestCase):
    def test_setup_seeds_the_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = Agent(config_dir=directory)
            agent.setup()
            for name in SEEDED_FILES:
                self.assertTrue(Path(directory, name).exists(), name)

    def test_reload_raises_on_unconfigured_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = Agent(config_dir=directory)
            agent.setup()
            with self.assertRaises(AgentError):
                agent.reload()

    def test_reload_populates_context_from_the_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = Agent(config_dir=directory)
            agent.setup()
            Path(directory, "config.json").write_text(
                json.dumps({"model": "openai/test", "max_context_message_chars": 1000}),
                encoding="utf-8",
            )
            agent.reload()
            assert agent._context is not None
            self.assertEqual(agent._context.config.model, "openai/test")
            self.assertTrue(agent._context.system_prompt.strip())
            self.assertEqual(agent._context.bash_tool["function"]["name"], "bash")

    def test_turn_requires_reload_first(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = Agent(config_dir=directory)
            with self.assertRaises(AgentError):
                agent.turn("hi")


if __name__ == "__main__":
    unittest.main()
