import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from amnesia_genius import config
from amnesia_genius.agent import _assistant_message, _request_kwargs, agent_turn
from amnesia_genius.config import Config
from amnesia_genius.events import AssistantMessage, Delta, ToolResult


def chunk(content: str | None = None, tool_calls: list[Any] | None = None) -> Any:
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def call_delta(
    index: int,
    call_id: str | None = None,
    name: str | None = None,
    arguments: str | None = None,
) -> Any:
    function = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(index=index, id=call_id, function=function)


async def stream(*chunks: Any) -> Any:
    for item in chunks:
        yield item


def make_config() -> Config:
    return Config(
        model="openai/test",
        api_key=None,
        base_url=None,
        provider_params=None,
        max_context_message_chars=1000,
    )


class AssistantMessageTests(unittest.TestCase):
    def test_assembles_content_and_ordered_tool_calls(self) -> None:
        calls = {
            1: {"id": "c2", "function": {"name": "bash", "arguments": "{}"}},
            0: {"id": "c1", "function": {"name": "bash", "arguments": '{"command":"ls"}'}},
        }
        message = _assistant_message(["Hel", "lo"], calls)
        self.assertEqual(message["content"], "Hello")
        self.assertEqual([call["id"] for call in message["tool_calls"]], ["c1", "c2"])

    def test_omits_tool_calls_key_when_absent(self) -> None:
        self.assertEqual(
            _assistant_message(["hi"], {}), {"role": "assistant", "content": "hi"}
        )


class AgentTurnTests(unittest.IsolatedAsyncioTestCase):
    async def test_turn_yields_events_and_stops_on_plain_reply(self) -> None:
        calls: list[dict[str, Any]] = []
        responses: list[Any] = [
            stream(
                chunk(
                    tool_calls=[
                        call_delta(
                            0, call_id="c1", name="bash", arguments='{"command":"ls"}'
                        )
                    ]
                )
            ),
            stream(chunk(content="all "), chunk(content="done")),
        ]

        async def fake_completion(**kwargs: Any) -> Any:
            calls.append(kwargs)
            return responses.pop(0)

        tool_message: dict[str, Any] = {
            "role": "tool",
            "tool_call_id": "c1",
            "content": "out",
        }
        config_value = make_config()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(config, "CONFIG_DIR", directory):
                Path(directory, "memory.md").write_text("memory", encoding="utf-8")
                with (
                    patch("amnesia_genius.agent.acompletion", new=fake_completion),
                    patch(
                        "amnesia_genius.agent.execute_tool_calls",
                        new=AsyncMock(return_value=[tool_message]),
                    ) as execute,
                ):
                    events = [
                        event
                        async for event in agent_turn(
                            config_value, {}, "system prompt", "hi"
                        )
                    ]
                history_roles = [
                    json.loads(line)["role"]
                    for line in Path(directory, "history.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                ]

        self.assertEqual(
            [type(event) for event in events],
            [AssistantMessage, ToolResult, Delta, Delta, AssistantMessage],
        )
        self.assertEqual(events[0].message["tool_calls"][0]["id"], "c1")
        self.assertEqual(events[1].message, tool_message)
        self.assertEqual(events[4].message["content"], "all done")
        execute.assert_awaited_once()

        self.assertEqual(len(calls), 2)
        first_messages = calls[0]["messages"]
        self.assertEqual(first_messages[0]["role"], "system")
        self.assertIn("system prompt", first_messages[0]["content"])
        self.assertIn("memory", first_messages[0]["content"])
        self.assertEqual(first_messages[1], {"role": "user", "content": "hi"})
        second_messages = calls[1]["messages"]
        self.assertEqual(len(second_messages), 4)
        self.assertEqual(second_messages[3], tool_message)

        self.assertEqual(history_roles, ["user", "assistant", "tool", "assistant"])

    async def test_request_kwargs_give_config_priority_over_provider_params(self) -> None:
        config_value = Config(
            model="openai/test",
            api_key="key",
            base_url="https://example.com",
            provider_params={"model": "sneaky", "temperature": 0.5},
            max_context_message_chars=1000,
        )
        kwargs = _request_kwargs(config_value, messages=[], tools=[])
        self.assertEqual(kwargs["model"], "openai/test")
        self.assertEqual(kwargs["api_key"], "key")
        self.assertEqual(kwargs["api_base"], "https://example.com")
        self.assertEqual(kwargs["temperature"], 0.5)


if __name__ == "__main__":
    unittest.main()
