"""Conversation history persistence.

history.jsonl is write-only for the harness: messages are appended as JSON
lines and the model reads the file itself through bash, so the harness never
loads, validates, or repairs it.
"""

import json
from typing import Any

from amnesia_genius.config import global_path

Message = dict[str, Any]


def append_history(message: Message, config_dir: str | None = None) -> None:
    """Append a single message as one JSON line to the conversation log."""
    with open(global_path("history.jsonl", config_dir), "a", encoding="utf-8") as f:
        f.write(json.dumps(message) + "\n")
