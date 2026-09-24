"""Attach published artifact links to the final answer verbatim.

Sandbox download links are ~800-character opaque tokens. A model asked to copy one
into prose drops or alters characters often enough that the link 403s, so the
model never transcribes them: this hook reads the exact URLs back out of the
`publish_artifact` tool results for the current turn and appends them itself.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage

PUBLISH_TOOL_NAME = "publish_artifact"
_LINK_HOST = "--dl.smithbox.dev"
# A markdown link or image whose target is a sandbox download URL, however mangled.
_MODEL_WRITTEN_LINK = re.compile(
    r"!?\[[^\]]*\]\(https?://[^)\s]*" + re.escape(_LINK_HOST) + r"[^)\s]*\)"
)
_BARE_LINK = re.compile(r"https?://\S*" + re.escape(_LINK_HOST) + r"\S*")


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content)


def _published_this_turn(messages: list[AnyMessage]) -> list[dict[str, str]]:
    """Artifacts published since the last human message, in publish order."""
    start = 0
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            start = i
            break
    found: list[dict[str, str]] = []
    for m in messages[start:]:
        if not (isinstance(m, ToolMessage) and m.name == PUBLISH_TOOL_NAME):
            continue
        try:
            payload = json.loads(_text(m.content))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("url") and payload.get("markdown"):
            found.append({"url": str(payload["url"]), "markdown": str(payload["markdown"])})
    return found


def _with_artifacts(answer: str, artifacts: list[dict[str, str]]) -> str:
    # Drop anything the model wrote that points at a download link; it cannot be trusted.
    cleaned = _MODEL_WRITTEN_LINK.sub("", answer)
    cleaned = _BARE_LINK.sub("", cleaned).rstrip()
    block = "\n\n".join(a["markdown"] for a in artifacts)
    return f"{cleaned}\n\n**Artifacts**\n\n{block}\n"


class ArtifactLinksMiddleware(AgentMiddleware[Any, Any]):
    @property
    def name(self) -> str:
        return "artifact-links"

    def after_model(self, state: Any, runtime: Any = None) -> dict[str, Any] | None:
        messages: list[AnyMessage] = list(state.get("messages") or [])
        if not messages:
            return None
        last = messages[-1]
        if not isinstance(last, AIMessage) or last.tool_calls:
            return None
        artifacts = _published_this_turn(messages)
        if not artifacts:
            return None
        rewritten = AIMessage(id=last.id, content=_with_artifacts(_text(last.content), artifacts))
        return {"messages": [rewritten]}

    async def aafter_model(self, state: Any, runtime: Any = None) -> dict[str, Any] | None:
        return self.after_model(state, runtime)
