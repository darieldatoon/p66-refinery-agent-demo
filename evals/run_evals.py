import argparse
import json
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from langsmith import Client
from langsmith.evaluation import evaluate

from evals.dataset import DATASET_NAME, build_examples
from evals.evaluators import (
    make_groundedness_judge,
    numeric_accuracy,
    successful_run,
    unit_accuracy,
)
from models import DEFAULT_AGENT_MODEL
from refinery_data.source import SqliteRefineryDataSource
from scripts.client import run_question


def ensure_dataset(client: Client) -> str:
    examples = build_examples(SqliteRefineryDataSource())
    if not client.has_dataset(dataset_name=DATASET_NAME):
        client.create_dataset(
            DATASET_NAME,
            description="30 synthetic refinery questions; references computed from frozen SQLite. v2 is an intentionally simplified demo prompt.",
        )
    existing = {str(e.id): e for e in client.list_examples(dataset_name=DATASET_NAME)}
    for example in examples:
        example_id = str(
            uuid5(NAMESPACE_URL, f"p66/{DATASET_NAME}/{example['metadata']['case_id']}")
        )
        if example_id in existing:
            old = existing[example_id]
            if old.inputs != example["inputs"] or old.outputs != example["outputs"]:
                raise ValueError("Remote example differs; review dataset changes before updating")
        else:
            client.create_example(**example, dataset_name=DATASET_NAME, example_id=example_id)
    return DATASET_NAME


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument(
        "--variant",
        choices=["baseline", "v2-prompt-cleanup"],
        default="baseline",
    )
    parser.add_argument("--max-examples", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--skip-judge", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.max_examples <= 30 or args.concurrency < 1:
        parser.error("max-examples must be 1-30 and concurrency positive")
    client = Client()
    name = ensure_dataset(client)
    data = sorted(
        client.list_examples(dataset_name=name), key=lambda e: (e.metadata or {})["case_id"]
    )[: args.max_examples]

    def target(inputs: dict[str, Any]) -> dict[str, Any]:
        return run_question(args.url, inputs, args.variant)

    evaluators: list[Any] = [numeric_accuracy, unit_accuracy, successful_run]
    if not args.skip_judge:
        evaluators.append(make_groundedness_judge(DEFAULT_AGENT_MODEL))
    results = evaluate(
        target,
        data=data,
        evaluators=evaluators,
        experiment_prefix="baseline-gpt-6-sol" if args.variant == "baseline" else args.variant,
        description="Synthetic refinery demo. Cleanup removes pressure-unit guidance. Scores are measured; no regression is assumed.",
        max_concurrency=args.concurrency,
        client=client,
        metadata={"prompt_variant": args.variant, "model": DEFAULT_AGENT_MODEL, "synthetic": True},
    )
    rows = [
        {
            "example_id": str(row["example"].id),
            "feedback": [r.model_dump() for r in row["evaluation_results"]["results"]],
        }
        for row in results
    ]
    path = Path(f".scratch/{args.variant}-scores.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, default=str))
    print(f"Experiment: {results.experiment_name}; scores: {path}")


if __name__ == "__main__":
    main()
