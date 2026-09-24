# Refinery Reliability Agent

Synthetic refinery reliability demo for P66: a Python Managed Deep Agent, two
specialists, SQLite evidence, approved work-order drafts, sandbox reports, and
LangSmith traces and evaluations. Every agent model uses the LLM Gateway.

## Collaboration workspace

Open [the refinery workspace](https://darieldatoon.github.io/p66-refinery-agent-demo/).
The public preview shows 40 assets and four signals from the fixed synthetic snapshot.
Connect with a LangSmith key for the deployment workspace to investigate a signal,
inspect sensor and maintenance evidence, and discuss the recommendation with the agent.
The browser keeps the key in memory only; reconnect after a reload.

1. Select P-101A and choose **Investigate issue**. Both specialists contribute, and the
   agent saves a structured assessment with evidence citations and uncertainty.
2. Choose **Propose work**. Review the exact proposed tasks and approve or reject them.
3. Open **Work & review** to see the saved decision. Approval creates a synthetic draft,
   never a CMMS submission, repair, or equipment operation.
4. Choose **Create report** for a sandbox HTML artifact. Published links expire after
   24 hours; the artifact card uses the publishing tool's exact URL.

Equipment without an assessment is **unassessed**. Work review does not change an
equipment assessment. K-401's mixed pressure units are a data characteristic, not a fault.
This is a schematic equipment overview, not physical piping topology or a simulation.

The React/Vite+/Macaw frontend calls MDA directly with `useStream`. On completion it
reloads the saved checkpoint, which includes final-message middleware changes that
can be absent from streaming projections. Each issue has one deterministic thread.
Assessments and review records live in the managed LangGraph Store, independent of
browser state. A middleware command returns the board without calling a model.
Both specialist agents retain `checkpointer=False` for Agent Chat UI compatibility.

This is a shared presenter demo: a workspace key grants broad deployment access,
reviewers are recorded as `workspace_operator`, and the Store is not a transactional
ticket database. It does not implement individual user permissions or multiuser locking.

### Local frontend

```sh
sfw pnpm --dir frontend install --frozen-lockfile
uv run --no-sync python -m scripts.export_snapshot
pnpm --dir frontend run dev
```

The frontend defaults to the hosted MDA. Set `VITE_MDA_API_URL` to use another endpoint.
`PAGES_BASE_PATH` defaults to `/p66-refinery-agent-demo/`.

### GitHub Actions deployment

`.github/workflows/deploy.yml` validates Python and TypeScript, deploys MDA, then
publishes GitHub Pages. Pushes to `main` and `feat/refinery-workspace` deploy the same
demo environment; pull requests validate without deployment secrets. Pages must use
**GitHub Actions** as its publishing source, with both branches allowed by the
`github-pages` environment. Deployment runs are serialized.

Configure these GitHub repository secrets using `gh secret set`:

| Secret | Purpose |
| --- | --- |
| `LANGSMITH_API_KEY` | Deployment authentication |
| `LANGSMITH_GATEWAY_API_KEY` | Agent model calls through the LLM Gateway |

Repository variables: `LANGSMITH_WORKSPACE_ID`, `MDA_DEPLOYMENT_NAME`,
`MDA_DEPLOYMENT_TYPE`, `MDA_API_URL`, `AGENT_MODEL`, and `PAGES_BASE_PATH`.
These are already configured for this demo. The two keys belong to different
organizations and must stay separate. No key is included in the static build.

The deploy script stages only runtime files, injects runtime model configuration,
and uses `--context-strategy overwrite` so repository instructions and skills are
authoritative in Context Hub. Make persistent instruction edits in this repository.
Pages publishes only `frontend/dist`, after the agent deployment succeeds.

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
