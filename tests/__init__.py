"""Test package: stub litellm so the suite runs without the heavy dependency."""

import sys
from types import ModuleType
from unittest.mock import MagicMock


def _stub_litellm() -> None:
    """Provide a lightweight litellm stand-in so agent imports without the dep."""
    if "litellm" in sys.modules:
        return
    fake = ModuleType("litellm")
    fake.validate_environment = MagicMock(return_value={"keys_in_environment": True})
    fake.acompletion = MagicMock()
    sys.modules["litellm"] = fake


_stub_litellm()
