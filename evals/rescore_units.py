import argparse
import json
from pathlib import Path
from typing import Any

from langsmith import Client

from evals.evaluators import unit_accuracy


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recheck unit labels against current dataset references"
    )
    parser.add_argument("experiment")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    client = Client()
    changes: list[dict[str, Any]] = []
    for run in client.list_runs(project_name=args.experiment, is_root=True):
        if not run.outputs or not run.reference_example_id:
            continue
        example = client.read_example(run.reference_example_id)
        score = unit_accuracy(run.outputs, example.outputs or {})
        for feedback in client.list_feedback(run_ids=[run.id], feedback_key=["unit_accuracy"]):
            if feedback.score == score:
                continue
            changes.append(
                {
                    "run_id": str(run.id),
                    "feedback_id": str(feedback.id),
                    "old_score": feedback.score,
                    "new_score": score,
                }
            )
            if args.apply:
                client.update_feedback(
                    feedback.id,
                    score=score,
                    comment="Rescored using equivalent-unit aliases and the corrected unspecified-currency reference.",
                )
    path = Path(f".scratch/{args.experiment}-unit-corrections.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(changes, indent=2))
    print(f"{'Applied' if args.apply else 'Proposed'} {len(changes)} corrections; {path}")


if __name__ == "__main__":
    main()
