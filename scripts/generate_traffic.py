import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from evals.dataset import build_examples
from refinery_data.source import SqliteRefineryDataSource
from scripts.client import run_question


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.count <= 30 or args.concurrency < 1:
        parser.error("count must be 1-30 and concurrency positive")
    examples = build_examples(SqliteRefineryDataSource())[: args.count]
    output = Path(".scratch/traffic.jsonl")
    output.parent.mkdir(exist_ok=True)
    failures = 0
    with output.open("a") as file, ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(run_question, args.url, e["inputs"]): e for e in examples}
        for future in as_completed(futures):
            case = futures[future]["metadata"]["case_id"]
            try:
                result = future.result()
                summary = {"case_id": case, **{k: v for k, v in result.items() if k != "messages"}}
                if result["interrupted"] or not result["answer"]:
                    failures += 1
            except Exception as exc:
                failures += 1
                summary = {"case_id": case, "error_type": type(exc).__name__}
            file.write(json.dumps(summary) + "\n")
            file.flush()
            print(
                f"{case}: {'failed' if 'error_type' in summary else summary['thread_id']}",
                flush=True,
            )
    if failures:
        raise SystemExit(f"{failures} runs failed; see {output}")


if __name__ == "__main__":
    main()
