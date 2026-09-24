import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from langsmith import Client

from evals.evaluators import GROUNDEDNESS_RUBRIC

PROJECT = "refinery-reliability-agent"
SECTION = "P66 refinery reliability"
QUEUE = "reliability-sme-review"
EVALUATOR = "refinery-groundedness"


def request(
    client: Client,
    method: Literal["GET", "POST", "PATCH"],
    path: str,
    body: dict[str, Any] | None = None,
) -> Any:
    return client.request_with_retries(
        method, path, request_kwargs={"json": body} if body is not None else {}
    ).json()


def chart_specs(project_id: str) -> list[dict[str, Any]]:
    root_filter = {
        "source_type": "tracing_project",
        "project_ids": [project_id],
        "run_filter": "eq(is_root, true)",
    }
    return [
        {
            "title": "Cost by refinery unit",
            "chart_type": "bar",
            "series": [
                {
                    "name": "Cost (USD)",
                    "metric_definition": {"type": "sum", "field": "total_cost"},
                    "filter_definition": root_filter,
                    "group_by_definitions": [{"attribute": "metadata", "path": "unit"}],
                }
            ],
        },
        {
            "title": "Subagent latency p95",
            "chart_type": "line",
            "series": [
                {
                    "name": "p95 seconds",
                    "metric_definition": {
                        "type": "percentile",
                        "field": "latency_seconds",
                        "params": {"p": 0.95},
                    },
                    "filter_definition": {
                        **root_filter,
                        "run_filter": 'and(eq(run_type, "chain"), or(eq(name, "data-analyst"), eq(name, "maintenance-planner")))',
                    },
                    "group_by_definitions": [{"attribute": "name"}],
                }
            ],
        },
        {
            "title": "Tokens by requester role",
            "chart_type": "bar",
            "series": [
                {
                    "name": "Tokens",
                    "metric_definition": {"type": "sum", "field": "total_tokens"},
                    "filter_definition": root_filter,
                    "group_by_definitions": [{"attribute": "metadata", "path": "requester_role"}],
                }
            ],
        },
        {
            "title": "Groundedness over time",
            "chart_type": "line",
            "series": [
                {
                    "name": "Groundedness",
                    "metric_definition": {
                        "type": "avg",
                        "field": "feedback_score",
                        "params": {"feedback_key": "groundedness"},
                    },
                    "filter_definition": root_filter,
                    "group_by_definitions": [],
                }
            ],
        },
    ]


def evaluator_spec(project_id: str, playground_settings_id: str) -> dict[str, Any]:
    return {
        "display_name": EVALUATOR,
        "session_id": project_id,
        "is_enabled": True,
        "sampling_rate": 1.0,
        "filter": "eq(is_root, true)",
        "evaluators": [
            {
                "structured": {
                    "prompt": [
                        [
                            "system",
                            GROUNDEDNESS_RUBRIC
                            + " The output is a message history: use tool messages as evidence and score the last assistant answer. Prior-turn tool evidence may support follow-up answers. Ignore reasoning blocks.",
                        ],
                        ["human", "Input: {input}\nOutput: {output}"],
                    ],
                    "schema": {
                        "title": "RefineryGroundedness",
                        "type": "object",
                        "properties": {
                            "reasoning": {
                                "type": "string",
                                "description": "Evidence for the verdict",
                            },
                            "groundedness": {"type": "boolean"},
                        },
                        "required": ["reasoning", "groundedness"],
                    },
                    "variable_mapping": {"input": "input", "output": "output"},
                    "playground_settings_id": playground_settings_id,
                    "template_format": "f-string",
                }
            }
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--playground-settings-id",
        required=True,
        help="Existing gateway model configuration enabled for evaluators",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--update-evaluator", action="store_true")
    args = parser.parse_args()
    client = Client()
    project = client.read_project(project_name=PROJECT)
    project_id = str(project.id)
    specs = {
        "charts": chart_specs(project_id),
        "evaluator": evaluator_spec(project_id, args.playground_settings_id),
        "alerts_pending_destination": [
            {
                "name": "Refinery error rate > 5%",
                "attribute": "error_count",
                "aggregation": "pct",
                "operator": "gt",
                "threshold": 5,
                "window_minutes": 5,
            },
            {
                "name": "Refinery groundedness < 0.8",
                "attribute": "feedback_score",
                "aggregation": "avg",
                "operator": "lt",
                "threshold": 0.8,
                "window_minutes": 15,
            },
        ],
    }
    path = Path(".scratch/monitoring-config.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(specs, indent=2))
    if not args.apply:
        print(f"Review {path}; pass --apply to create resources")
        return
    settings = request(client, "GET", f"/playground-settings/{args.playground_settings_id}")
    if not settings.get("available_in_evaluators"):
        raise ValueError("Selected workspace model configuration is not enabled for evaluators")
    specs["evaluator"]["evaluators"][0]["structured"]["model"] = settings["settings"]
    rules = request(client, "GET", "/runs/rules")
    matching = [
        r for r in rules if r.get("session_id") == project_id and r.get("display_name") == EVALUATOR
    ]
    if not matching:
        matching = [request(client, "POST", "/runs/rules", specs["evaluator"])]
    elif args.update_evaluator:
        if len(matching) != 1:
            raise ValueError("More than one matching evaluator; inspect before updating")
        matching = [
            request(client, "PATCH", f"/runs/rules/{matching[0]['id']}", specs["evaluator"])
        ]
    sections = request(client, "GET", "/charts/section")
    section = next((s for s in sections if s["title"] == SECTION), None)
    if section is None:
        section = request(
            client,
            "POST",
            "/charts/section",
            {
                "title": SECTION,
                "description": "Synthetic refinery demo: cost, latency, tokens and evidence grounding.",
            },
        )
    dashboard = request(
        client,
        "POST",
        "/charts",
        {
            "omit_data": True,
            "end_time": datetime.now(UTC).isoformat(),
            "start_time": (datetime.now(UTC) - timedelta(days=7)).isoformat(),
        },
    )
    charts = [
        c
        for group in dashboard["sections"]
        if group["id"] == section["id"]
        for c in group["charts"]
    ]
    existing_titles = {c["title"] for c in charts}
    for spec in specs["charts"]:
        if spec["title"] not in existing_titles:
            request(client, "POST", "/charts/create", {**spec, "section_id": section["id"]})
    queues = list(client.list_annotation_queues(name=QUEUE))
    queue = next((q for q in queues if q.name == QUEUE), None)
    if queue is None:
        queue = client.create_annotation_queue(
            name=QUEUE,
            description="SME checks synthetic refinery condition assessments and conflicting maintenance evidence.",
        )
    summary = {
        "project_id": project_id,
        "section_id": section["id"],
        "queue_id": str(queue.id),
        "evaluator_rule_ids": [r["id"] for r in matching],
        "alert_status": "thresholds prepared; delivery intentionally unconfigured",
    }
    Path(".scratch/monitoring-resources.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
