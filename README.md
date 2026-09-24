# Refinery Reliability Agent

Synthetic refinery reliability demo for P66: a Python Managed Deep Agent, two
specialists, SQLite evidence, approved work-order drafts, sandbox reports, and
LangSmith traces and evaluations. Every agent model uses the LLM Gateway.

## Run

```sh
sfw uv sync
cp .env.example .env
# Fill the tracing/workspace key and literal gateway key locally.
uv run mda dev
uv run mda deploy --deployment-type dev
```

MDA reads `.env`. Standalone scripts need `uv run --env-file .env`.
`AGENT_MODEL` defaults to `langsmith:openai/gpt-6-sol`; change it to
`langsmith:openai/gpt-5.6-terra` and restart/redeploy for the fallback. Tracing and
Gateway credentials belong to different organizations; keep them separate.

```sh
uv run --env-file .env python -m scripts.run_once --url http://127.0.0.1:2024
uv run --env-file .env python -m scripts.generate_traffic --url <deployment-url>
uv run --env-file .env python -m evals.run_evals --url <deployment-url>
uv run --env-file .env python -m evals.run_evals --url <deployment-url> --variant v2-prompt-cleanup
```

The evaluation commands create real LangSmith experiments over the same 30 examples.
References are computed from SQLite. The intentionally simplified v2 prompt removes
pressure-unit guidance from both the lead and data analyst; it does **not** alter
sensor data, answers or scores. Removing guidance may not cause a regression on every
model: all six pressure cases passed with omission alone in the first comparison.
Both variants scored 29/30 on numeric accuracy. Review the different missed questions
alongside the passing pressure cases; the comparison does not show a pressure regression.

## Demo

1. Ask: **“Is P-101A healthy? Anything I should worry about before the weekend?”**
2. Open the published chart and HTML condition report. The agent transfers queried
   data to the sandbox, writes and runs Python, then publishes both files.
3. Open the trace: data analyst, maintenance planner, SQL, model latency/tokens/cost.
4. Show Gateway usage and the configured model.
5. Ask: **“Draft a work order for the P-101A bearing inspection.”** Approve in Studio.
6. Show `refinery-operator-questions` and compare the two experiments.
7. Show the dashboard, groundedness evaluator and `reliability-sme-review` queue.
8. Show the deployment's instructions and skills in Context Hub.
9. Bridge to the PoV: Azure AI Foundry tracing plus customer data comes next.

The draft is a deterministic synthetic object stored in the conversation, never a
CMMS submission. Approval, edit and rejection are supported. To resume a test run:

```sh
uv run --env-file .env python -m scripts.run_once --url <url> --thread <id> --approve
```

Warm the hero thread, keep its report tab and an approval thread available as
fallbacks. Re-publish the report the morning of the demo; links expire after 24 hours.
Do not claim Engine results from sparse traffic. See `.scratch/demo-status.md` for
this session's resource links and outstanding items.
Copyable questions, including report and chart requests, are in
`.scratch/prompt-examples.md`.

Both specialists use `checkpointer=False`, preserving the pricing demo's fix for
Agent Chat UI follow-ups that fork from the thread checkpoint. Artifact middleware
adds exact HTTPS download links to the final message. Verify both against a deployment:

```sh
uv run --env-file .env python -m scripts.verify_chat_ui --url <deployment-url>
```

This creates a fresh thread, generates a report from a checkpoint follow-up, checks
its HTML/PNG downloads, and confirms both specialists work on a subsequent message.

## Evidence and limits

The seed contains 40 assets, 120 sensor tags, 129,600 hourly readings, 300 work orders,
20 failures, 120 notes and 50 parts across three refinery units. It is frozen at
**2026-09-23 12:00 UTC**, covering 45 days (46 calendar dates with partial boundary days).
A missing database is built atomically when the data source first initializes.

Storylines: P-101A vibration rises below alarm; E-205 differential pressure rises while
heat duty falls; C-301 has three seals fail with the same recorded cause; K-401 mixes
bar and psi; P-102B has a replacement note linked to a cancelled work order.

SQL uses a read-only connection, an authorizer, a 200-row cap and an execution budget.
The tools query SQLite in the agent process; the sandbox has no direct database access.
The fixture's 4.5 mm/s alarm is a demo assumption, separate from illustrative ISO zones.

## Monitoring

Use an existing workspace Gateway model configuration enabled for evaluators:

```sh
uv run --env-file .env python -m scripts.setup_monitoring --playground-settings-id <id>
# Review .scratch/monitoring-config.json, then add --apply.
```

This creates a workspace dashboard, an online groundedness evaluator at 100% sampling,
and an annotation queue. Groundedness compares the final answer with root-level tool
messages, including specialist summaries; it is not an independent equipment diagnosis.
Alert thresholds are prepared locally: error rate > 5% over 5 minutes and average
groundedness < 0.8 over 15 minutes. Alert delivery is intentionally unconfigured;
live alerts are not enabled.

## Validate

```sh
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest -q
uv run mda build
```

Offline tests cover deterministic storylines, SQL boundaries, injected tools,
approval/resume decisions, prompt variants, artifact publication and exact links.
The repository retains its 100% coverage gate for agent/runtime code.
