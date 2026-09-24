"""Publish files the agent wrote in its sandbox as shareable links.

The chat UIs we target render markdown, and their markdown renderers only allow
http(s) URLs: no data URLs, no raw HTML. A LangSmith sandbox can mint a tokenized
download link for one file, served inline with a content type we choose, so an
HTML report opens in a browser tab and a PNG or SVG renders as an inline image.
"""

from __future__ import annotations

import json
import mimetypes
from typing import Any

from deepagents.backends import CompositeBackend
from langchain.tools import tool
from langsmith.sandbox import SandboxClient
from managed_deepagents import ManagedDeepAgentRuntime  # noqa: TC002

DEFAULT_TTL_HOURS = 24
MAX_TTL_HOURS = 24 * 7

# mimetypes on the sandbox image may not know these; be explicit.
_CONTENT_TYPES = {
    ".html": "text/html",
    ".htm": "text/html",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
}


def _sandbox_name(backend: object, path: str) -> str | None:
    """Return the LangSmith sandbox name behind whatever backend the run was given.

    MDA hands tools a lazily resolved wrapper whose `id` is a `pending:` placeholder
    until the first filesystem call, so read the target file once to force
    resolution. That read also proves the file exists in the sandbox we mint from.
    """
    target: Any = backend.default if isinstance(backend, CompositeBackend) else backend
    if target is None:
        return None
    read = getattr(target, "read", None)
    if callable(read):
        try:
            read(path, 0, 1)
        except Exception:
            return None
    sandbox_id = getattr(target, "id", None)
    if isinstance(sandbox_id, str) and sandbox_id and not sandbox_id.startswith("pending:"):
        return sandbox_id
    return None


def _content_type(path: str) -> str:
    suffix = path[path.rfind(".") :].lower() if "." in path else ""
    return _CONTENT_TYPES.get(suffix) or mimetypes.guess_type(path)[0] or "application/octet-stream"


@tool(parse_docstring=True)
def publish_artifact(
    path: str,
    title: str,
    runtime: ManagedDeepAgentRuntime,
    expires_in_hours: int = DEFAULT_TTL_HOURS,
) -> str:
    """Publish a file you already wrote in the sandbox as a shareable link and
    return ready-to-paste markdown. Use it for the HTML condition report and any
    chart image so the reliability engineer can open them from the chat.

    Args:
        path: Absolute path of the file inside the sandbox, for example /reports/P-101A.html.
        title: Short human label for the link or image, for example "P-101A condition report".
        expires_in_hours: How long the link stays valid, 1 to 168. Defaults to 24.
    """
    sandbox_name = _sandbox_name(runtime.backend, path)
    if sandbox_name is None:
        return json.dumps(
            {"error": "No LangSmith sandbox is attached; the file cannot be published as a link."}
        )
    hours = max(1, min(int(expires_in_hours), MAX_TTL_HOURS))
    content_type = _content_type(path)
    # A fresh link per publish: links pin a path, not the contents, so re-mint after edits.
    link = SandboxClient().generate_download_url(
        sandbox_name,
        path,
        expires_in_seconds=hours * 3600,
        content_type=content_type,
        content_disposition="inline",
    )
    url = link.download_url
    is_image = content_type.startswith("image/")
    return json.dumps(
        {
            "url": url,
            "expires_at": link.expires_at,
            "content_type": content_type,
            "markdown": f"![{title}]({url})" if is_image else f"[{title}]({url})",
            "hint": "Images render inline in chat; other files open in a new tab.",
        },
        default=str,
    )
