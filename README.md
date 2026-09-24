# Refinery Reliability Agent

Synthetic refinery reliability demo for P66: a Python Managed Deep Agent, two
specialists, SQLite evidence, approved work-order drafts, sandbox reports, and
LangSmith traces and evaluations. Every agent model uses the LLM Gateway.

## Collaboration workspace

Open [the refinery workspace](https://darieldatoon.github.io/p66-refinery-agent-demo/).
The public preview shows four ranked issues, 40 assets, and every asset's sensor trends,
notes, work orders and spares from the fixed synthetic snapshot. Connect with a LangSmith
key for the deployment workspace to investigate. The browser keeps the key in memory only;
reconnect after a reload. The UI follows the system theme; the header toggles light/dark.

1. P-101A is first in the queue. Choose **Investigate with the agent**. Both specialists
   contribute, and the agent saves a structured assessment with citations and uncertainty.
2. Choose **Propose work**. Review the exact proposed tasks and approve or reject them.
3. Open **Work & Review** to see the saved decision. Approval creates a synthetic draft,
   never a CMMS submission, repair, or equipment operation.
4. Choose **Create report** for a sandbox HTML artifact. Published links expire after
   24 hours; the artifact card uses the publishing tool's exact URL.

Equipment without an assessment is **unassessed**. Work review does not change an
equipment assessment. K-401's mixed pressure units are a data characteristic, not a fault.
The **Equipment** view groups assets by unit; it is not a piping diagram or a simulation.

Reset saved assessments, proposals and issue threads before a demo:

```sh
mise run reset --url <deployment-url>          # dry run
mise run reset --url <deployment-url> --apply
```

The React/Vite+/Macaw frontend calls MDA directly with `useStream`. On completion it
reloads the saved checkpoint, which includes final-message middleware changes that
can be absent from streaming projections. Each issue has one deterministic thread.
Assessments and review records live in the managed LangGraph Store, independent of
browser state. A middleware command returns the board without calling a model.
Both specialist agents retain `checkpointer=False` for Agent Chat UI compatibility.

This is a shared presenter demo: a workspace key grants broad deployment access,
reviewers are recorded as `workspace_operator`, and the Store is not a transactional
ticket database. It does not implement individual user permissions or multiuser locking.

### Local development

[mise](https://mise.jdx.dev) pins uv, Node, pnpm and lefthook in `mise.toml`; CI installs
the same versions. Installs go through Socket Firewall (`sfw`).

```sh
mise install          # pinned tools
mise run setup        # locked dependencies, git hooks, snapshot
mise run dev          # local agent on :2124 and frontend on :5173, wired together
mise run check        # everything CI checks; also runs on git push
mise tasks            # all tasks
```

Open http://localhost:5173/p66-refinery-agent-demo/ and connect with any key text; the
local agent does not check it. `mda dev` reads `.env` for the Gateway key. Its store is in
memory, so a restart clears saved assessments. Change `AGENT_PORT` or `WEB_PORT` in
`mise.toml` if they are taken. Run `mise run snapshot` and commit the result after changing
fixture data; `check` fails on a stale snapshot. A plain `pnpm --dir frontend run dev`
targets the hosted agent; set `VITE_MDA_API_URL` to use another endpoint.

### GitHub Actions deployment

`.github/workflows/deploy.yml` validates Python and TypeScript, deploys MDA, then
publishes GitHub Pages. Only pushes to `main` deploy; other branches and pull requests
validate without deployment secrets. Test changes locally before merging. Pages must use
**GitHub Actions** as its publishing source, with `main` allowed by the `github-pages`
environment. Deployment runs are serialized.

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
References are computed from SQLite. Both supported prompt variants preserve pressure-unit
guidance, while the data layer normalizes pressure values and alarm limits to psi and
retains native evidence. The pressure view is available to SQL analyses that aggregate or
compare readings from mixed-unit sensors.

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

The seed contains 40 assets, 120 sensor tags, 129,600 hourly readings, 131 work orders,
6 failures, 47 notes and 42 parts across three refinery units. It is frozen at
**2026-09-23 12:00 UTC**. Sensor readings cover 45 days (46 calendar dates with partial
boundary days); maintenance history goes back to 2024. Hero records are hand-authored in
`refinery_data/fixture.py`. Keep the values the evals reference unchanged.
A missing database is built atomically when the data source first initializes.

Storylines: P-101A vibration and bearing temperature rise below alarm, bearings are 2.6
years old, the bearing kit is out of stock, and standby P-101B passed a run test; E-205
differential pressure rises while heat duty nears its low alarm; C-301 has three seal
failures 16 days apart, seal flush pressure drops before each, and the strainer that would
fix it is out of stock; K-401 mixes bar and psi after a transmitter swap; P-102B has a
replacement note linked to a cancelled work order and a later note that the leak persists.

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
mise run check
uv run mda build
```

Offline tests cover deterministic storylines, SQL boundaries, injected tools,
approval/resume decisions, prompt variants, artifact publication and exact links.
The repository retains its 100% coverage gate for agent/runtime code.
