# Refinery Reliability Agent

A Managed Deep Agents demo of the LangSmith platform for Phillips 66, built around a
refinery preventative maintenance use case. Synthetic data in SQLite, every model call
through the LangSmith LLM Gateway, traces to the Deployed Engineering workspace.

## Setup

```sh
uv sync
uv run lefthook install
cp .env.example .env          # add a workspace API key for LANGSMITH_API_KEY
export LC_GATEWAY_KEY=...     # gateway service key, expanded into .env
```

## Run

```sh
uv run mda dev                              # local server plus Studio, traces to *-local project
uv run mda deploy --deployment-type dev     # hosted, traces to the deployment's project
```

## Check

```sh
uv run ruff format --check . && uv run ruff check . && uv run ty check
uv run pytest -q                            # fails under 100% coverage
```

## Layout

| Path | Role |
| --- | --- |
| `agent.py` | `define_deep_agent` wiring |
| `instructions.md` | System prompt, synced to Context Hub |
| `models.py` | Gateway model factory |
| `tools/` | Tools over an injected data source |
| `refinery_data/` | Domain types, deterministic SQLite seed, data source protocol |
| `skills/` | Shared skills the agent loads on demand |
| `evals/` | Dataset and evaluators |
| `scripts/` | Traffic generator and one-off runs |
