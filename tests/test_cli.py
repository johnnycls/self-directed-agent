import os
import sys
import unittest
from unittest.mock import patch

from amnesia_genius import cli
from amnesia_genius.errors import AgentError


def _raise_with_path() -> None:
    raise AgentError("bad config", path="config.json")


def _raise_without_path() -> None:
    raise AgentError("bad thing")


class CliTests(unittest.TestCase):
    def test_load_or_edit_opens_file_and_exits_for_path_errors(self) -> None:
        with patch.object(cli, "_open_in_editor") as opener:
            with self.assertRaises(SystemExit):
                cli._load_or_edit(_raise_with_path)
        opener.assert_called_once_with("config.json")

    def test_load_or_edit_reraises_errors_without_a_path(self) -> None:
        with self.assertRaises(AgentError):
            cli._load_or_edit(_raise_without_path)

    def test_open_in_editor_uses_the_platform_opener(self) -> None:
        with patch.dict(os.environ):
            os.environ.pop("EDITOR", None)
            with patch.object(cli.subprocess, "run") as run:
                cli._open_in_editor("config.json")
        expected = {
            "win32": ["notepad.exe", "config.json"],
            "darwin": ["open", "-t", "-W", "config.json"],
        }.get(sys.platform, ["xdg-open", "config.json"])
        run.assert_called_once_with(expected, check=False, shell=False)


if __name__ == "__main__":
    unittest.main()
