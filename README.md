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
  "max_message_chars": 1000
}
```

The agent immediately detects that `model` is not set, prints the error,
and opens this file in your editor. Fill in `model` (and usually `api_key`),
save, close it, and run `self-directed-agent` again.

`model`, `history_window`, and `max_message_chars` are required; missing, empty, or invalid values fail at startup. `api_key`, `base_url`, and `provider_params` are optional — an empty string counts as unset.

Required:

- `model` — LiteLLM provider-prefixed form, e.g. `anthropic/claude-sonnet-4-5`
- `history_window` — how many recent turns are replayed to the model (positive integer)
- `max_message_chars` — tool results longer than this are truncated before entering context (positive integer)

Optional:

- `api_key` / `base_url` — sent with every request when set

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
