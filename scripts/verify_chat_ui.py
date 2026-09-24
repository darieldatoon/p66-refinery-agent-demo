import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from langgraph_sdk import get_sync_client

from evals.evaluators import final_text
from scripts.client import GRAPH_ID

REPORT_PROMPT = (
    "Is P-101A healthy? Ask both specialists for evidence, then create and publish "
    "a self-contained HTML condition report and vibration PNG for the full 45 days. "
    "Include the configured alarm limit, maintenance records, and evidence IDs. "
    "Do not draft a work order."
)
FOLLOWUP_PROMPT = (
    "Ask the data analyst for P-101A's latest vibration reading and the maintenance "
    "planner for its most recent work order status. Cite their evidence. "
    "No report or work order draft."
)
DOWNLOAD_LINK = re.compile(r"https://[^\s)\]]+--dl\.smithbox\.dev[^\s)\]]*")


def current_turn(result: Any) -> list[dict[str, Any]]:
    if not isinstance(result, dict) or result.get("__error__") or result.get("__interrupt__"):
        raise RuntimeError("Verification run failed or unexpectedly interrupted")
    messages = result.get("messages", [])
    start = next(
        (i for i in range(len(messages) - 1, -1, -1) if messages[i].get("type") == "human"),
        -1,
    )
    if start < 0:
        raise RuntimeError("No human message in run output")
    return messages[start + 1 :]


def verify_specialists(messages: list[dict[str, Any]]) -> None:
    calls = {
        call["id"]: call["args"].get("subagent_type")
        for message in messages
        for call in message.get("tool_calls", [])
        if call["name"] == "task"
    }
    completed = {
        calls[message["tool_call_id"]]
        for message in messages
        if message.get("type") == "tool"
        and message.get("tool_call_id") in calls
        and message.get("status") != "error"
    }
    if not {"data-analyst", "maintenance-planner"} <= completed:
        raise RuntimeError(f"Missing specialist completions: {completed}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    client = get_sync_client(url=args.url, timeout=600)
    thread = client.threads.create(metadata={"verification": "agent-chat-ui"})["thread_id"]
    initial = client.runs.wait(
        thread, GRAPH_ID, input={"messages": [{"role": "user", "content": "Say hello briefly."}]}
    )
    current_turn(initial)
    checkpoint = client.threads.get_state(thread)["checkpoint"]
    print(f"Thread: {thread}; testing follow-up from checkpoint", flush=True)
    report = client.runs.wait(
        thread,
        GRAPH_ID,
        input={"messages": [{"role": "user", "content": REPORT_PROMPT}]},
        checkpoint=checkpoint,
    )
    messages = current_turn(report)
    verify_specialists(messages)
    artifacts = [
        json.loads(message["content"])
        for message in messages
        if message.get("type") == "tool" and message.get("name") == "publish_artifact"
    ]
    if not {"text/html", "image/png"} <= {artifact.get("content_type") for artifact in artifacts}:
        raise RuntimeError("Report did not publish both HTML and PNG")
    answer_urls = set(DOWNLOAD_LINK.findall(final_text(messages)))
    if answer_urls != {artifact["url"] for artifact in artifacts}:
        raise RuntimeError("Final answer changed or omitted published links")
    for artifact in artifacts:
        with urlopen(artifact["url"], timeout=60) as response:
            body = response.read()
            if (
                response.status != 200
                or response.headers.get_content_type() != artifact["content_type"]
            ):
                raise RuntimeError("Artifact download or content type failed")
        if artifact["content_type"] == "text/html":
            if b"data:image/png;base64," not in body:
                raise RuntimeError("HTML report does not embed its PNG")
            Path(".scratch/hosted-P-101A.html").write_bytes(body)
    print(
        "Checkpoint follow-up: both specialists completed; exact HTML/PNG links return 200",
        flush=True,
    )
    followup = client.runs.wait(
        thread,
        GRAPH_ID,
        input={"messages": [{"role": "user", "content": FOLLOWUP_PROMPT}]},
    )
    verify_specialists(current_turn(followup))
    summary = {
        "thread_id": thread,
        "checkpoint_followup": "passed",
        "plain_followup": "passed",
        "artifacts": "exact links; HTTP 200; embedded PNG",
    }
    Path(".scratch/chat-ui-verification.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("Plain follow-up: both specialists completed", flush=True)


if __name__ == "__main__":
    main()
