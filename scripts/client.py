import time
from typing import Any

from langgraph_sdk import get_sync_client

from evals.evaluators import final_text

GRAPH_ID = "refinery-reliability-agent"


def run_question(url: str, inputs: dict[str, Any], variant: str = "baseline") -> dict[str, Any]:
    client = get_sync_client(url=url, timeout=600)
    metadata = {key: inputs[key] for key in ("asset", "unit", "requester_role")}
    metadata["prompt_variant"] = variant
    thread = client.threads.create(metadata=metadata)
    start = time.monotonic()
    result = client.runs.wait(
        thread["thread_id"],
        GRAPH_ID,
        input={"messages": [{"role": "user", "content": inputs["prompt"]}]},
        metadata=metadata,
        context={"prompt_variant": variant},
    )
    if not isinstance(result, dict):
        raise TypeError("Agent returned a non-dictionary state")
    if result.get("__error__"):
        raise RuntimeError(str(result["__error__"]))
    messages = result.get("messages", [])
    return {
        "thread_id": thread["thread_id"],
        "messages": messages,
        "answer": final_text(messages),
        "interrupted": bool(result.get("__interrupt__")),
        "elapsed_seconds": round(time.monotonic() - start, 2),
    }
