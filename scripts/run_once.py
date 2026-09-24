import argparse
import json
import re
from pathlib import Path

from langgraph_sdk import get_sync_client

from refinery_data.source import SqliteRefineryDataSource

GRAPH_ID = "refinery-reliability-agent"
HERO_PROMPT = "Is P-101A healthy? Anything I should worry about before the weekend?"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:2024")
    parser.add_argument("--prompt", default=HERO_PROMPT)
    parser.add_argument("--thread")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--output", type=Path, default=Path(".scratch/last-run.json"))
    args = parser.parse_args()
    if args.approve and not args.thread:
        parser.error("--approve requires --thread for the paused run")
    match = re.search(r"[PCEKT]-[0-9]+[A-Z]?", args.prompt)
    asset = SqliteRefineryDataSource().get_asset(match.group() if match else "P-101A")
    client = get_sync_client(url=args.url, timeout=600)
    metadata = {
        "asset": asset.asset_id,
        "unit": asset.unit_id,
        "requester_role": "reliability_engineer",
    }
    if args.thread:
        thread = client.threads.get(args.thread)
        if args.approve:
            metadata = {**metadata, **(thread.get("metadata") or {})}
    else:
        thread = client.threads.create(metadata=metadata)
    thread_id = thread["thread_id"]
    print(f"thread={thread_id}", flush=True)
    if args.approve:
        result = client.runs.wait(
            thread_id,
            GRAPH_ID,
            command={"resume": {"decisions": [{"type": "approve"}]}},
            metadata=metadata,
        )
    else:
        result = client.runs.wait(
            thread_id,
            GRAPH_ID,
            input={"messages": [{"role": "user", "content": args.prompt}]},
            metadata=metadata,
        )
    if not isinstance(result, dict):
        raise TypeError("Expected a state dictionary")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"thread_id": thread_id, "result": result}, indent=2))
    print(f"Saved {args.output}; keys={list(result)}")
    for message in result.get("messages", []):
        if message.get("type") == "ai":
            for call in message.get("tool_calls", []):
                print(f"tool={call['name']}")
    if result.get("__interrupt__"):
        print("Paused for human approval. Resume in Studio or explicitly pass --approve --thread.")


if __name__ == "__main__":
    main()
