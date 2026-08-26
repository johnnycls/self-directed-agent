# self-directed-agent

> **Give a clever model a shell — and get out of its way.**

A minimal agent harness built on one belief: **a sufficiently clever LLM needs almost no harness at all.**

## Why

Today's agent frameworks keep growing: plan mode, goal mode, auto memory compaction, sub-agents, agent teams, skills, guardrails... Every one of these features exists because models weren't smart enough to manage themselves. And every one of them constrains the model — it forces a prescribed workflow when the model might have a better one. As models get smarter, these harnesses stop being scaffolding and start being straitjackets.

Bash is Turing complete. It can install packages, call APIs, edit files, compile code — do anything a computer can do. So an agent doesn't need dozens of bespoke tools; it needs **one tool that can do everything**, and the freedom to use it.

self-directed-agent takes this to its logical conclusion. The LLM decides _everything_:

- **Its own memory** — what to remember, how to organize it, when to read it back
- **Its own capabilities** — need OCR? Install tesseract. Need embeddings? pip install something. Can't see images? Ask the user for a multimodal API key. Nothing is impossible; some things are just not installed yet
- **Its own program** — it can read and edit this agent's own source code, so future runs run on software it improved itself

The harness's only jobs: relay messages, execute bash, persist history, fail loudly when something breaks. No hidden prompts beyond one editable file, no silent retries, no magic.

## Install

```
pip install .
```

Requires Python >=3.10,<3.15.

## Configure

First launch seeds `~/.self-directed-agent/config.json`:

```json
{
  "model": "",
  "api_key": "",
  "base_url": "",
  "provider_params": {},
  "history_window": 50,
  "max_context_message_chars": 1000,
  "command_timeout_seconds": 120,
  "max_command_output_chars": 20000
}
```

The agent immediately detects that `model` is not set, prints the error,
and opens this file in your editor. Fill in `model` (and usually `api_key`),
save, close it, and run `self-directed-agent` again. Other invalid configuration
files are handled the same way.

The configuration file is read at startup and the editable files are reloaded
before each new user input. Invalid values print an error and open the relevant
file in your editor. Which provider settings are required depends on the selected
model and provider. Positive limits are measured in characters.

| Setting | Purpose |
| --- | --- |
| `model` | LiteLLM provider-prefixed model, such as `anthropic/claude-sonnet-4-5` |
| `api_key` | API key passed to LiteLLM when set |
| `base_url` | API base URL passed to LiteLLM when set |
| `provider_params` | Additional provider-specific LiteLLM parameters |
| `history_window` | Number of recent history messages replayed to the model |
| `max_context_message_chars` | Limit for non-user history content sent to the model |
| `command_timeout_seconds` | Maximum time allowed for one shell command; defaults to `120` |
| `max_command_output_chars` | Limit for command output retained in history/context; defaults to `20000` |

When either character limit is exceeded, the agent keeps the first half and last
half of the text with `\n...\n` between them. User messages are never truncated;
`max_context_message_chars` applies to non-user history content only.

Provider-specific parameters (AWS credentials, Vertex projects, Azure deployments, sampling settings...) go in `provider_params`, a free-form object splatted into every request:

```json
{
  "model": "bedrock/us.anthropic.claude-sonnet-4-5",
  "provider_params": {
    "aws_access_key_id": "AKIA...",
    "aws_secret_access_key": "...",
    "aws_region_name": "us-east-1"
  }
}
```

Alternatively rely on each SDK's standard environment variables (`AWS_ACCESS_KEY_ID`, `GOOGLE_APPLICATION_CREDENTIALS`, ...); anything LiteLLM accepts works. You know your provider — configure it your way.

## Run

```
self-directed-agent
```

Type a task; the agent runs bash, remembers across sessions in `~/.self-directed-agent/`, and keeps going until you interrupt it (Ctrl+C is safe anytime).

## Editing the agent

Everything the agent knows about itself ships as editable templates in `~/.self-directed-agent/`: `system_prompt.md`, `memory.md`, `bash_tool.json`, `config.json`. All of them are reloaded every turn — the agent's own edits apply from its next message. It can even edit this agent's source code (Python changes apply after restart).
