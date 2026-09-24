import json
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

import pytest
from deepagents.backends import CompositeBackend
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from middleware.artifact_links import ArtifactLinksMiddleware, _text
from tools.artifacts import _content_type, _sandbox_name, publish_artifact


def test_sandbox_resolution():
    assert _sandbox_name(None, "/reports/a.html") is None
    assert _sandbox_name(object(), "/reports/a.html") is None
    assert _sandbox_name(SimpleNamespace(id="pending:123"), "/reports/a.html") is None
    bad = Mock(id="abc")
    bad.read.side_effect = OSError("missing")
    assert _sandbox_name(bad, "/reports/a.html") is None
    backend = Mock(id="sandbox-1")
    composite = CompositeBackend(default=backend, routes={})
    assert _sandbox_name(composite, "/reports/a.html") == "sandbox-1"
    backend.read.assert_called_once_with("/reports/a.html", 0, 1)


def test_mime_types():
    assert _content_type("/reports/a.HTML") == "text/html"
    assert _content_type("/reports/a.txt") == "text/plain"
    assert _content_type("/reports/no_extension") == "application/octet-stream"


@pytest.mark.parametrize(
    ("path", "hours", "expected"), [("/reports/a.html", 999, 604800), ("/reports/a.png", -1, 3600)]
)
def test_publish_preserves_url_and_clamps_ttl(monkeypatch, path, hours, expected):
    client = Mock()
    client.generate_download_url.return_value = SimpleNamespace(
        download_url="https://a--dl.smithbox.dev/opaque", expires_at="tomorrow"
    )
    monkeypatch.setattr("tools.artifacts.SandboxClient", lambda: client)
    runtime = SimpleNamespace(backend=SimpleNamespace(id="sandbox-1"))
    result = json.loads(cast("Any", publish_artifact).func(path, "Report", runtime, hours))
    assert result["url"] in result["markdown"]
    assert result["markdown"].startswith("![" if path.endswith("png") else "[")
    assert client.generate_download_url.call_args.kwargs["expires_in_seconds"] == expected
    assert client.generate_download_url.call_args.kwargs["content_disposition"] == "inline"


def test_publish_without_sandbox():
    result = json.loads(
        cast("Any", publish_artifact).func(
            "/reports/a.html", "Report", SimpleNamespace(backend=None)
        )
    )
    assert "error" in result


def published(url="https://a--dl.smithbox.dev/token"):
    return ToolMessage(
        content=json.dumps({"url": url, "markdown": f"[Report]({url})"}),
        name="publish_artifact",
        tool_call_id="1",
    )


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [HumanMessage(content="hi")],
        [AIMessage(content="no artifact")],
        [AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "1"}])],
    ],
)
def test_middleware_noop(messages):
    assert ArtifactLinksMiddleware().after_model({"messages": messages}) is None


async def test_exact_links_replace_model_links_and_only_current_turn():
    middleware = ArtifactLinksMiddleware()
    assert middleware.name == "artifact-links"
    result = await middleware.aafter_model(
        {
            "messages": [
                published("https://old--dl.smithbox.dev/expired"),
                HumanMessage(content="report"),
                ToolMessage(content="not json", name="publish_artifact", tool_call_id="bad"),
                ToolMessage(
                    content='{"error":"missing"}', name="publish_artifact", tool_call_id="missing"
                ),
                published(),
                AIMessage(
                    id="answer",
                    content="Inspect bearing. [bad](https://x--dl.smithbox.dev/bad) https://x--dl.smithbox.dev/bare",
                ),
            ]
        }
    )
    assert result is not None
    answer = result["messages"][0]
    assert answer.id == "answer"
    assert "expired" not in answer.content
    assert "bad" not in answer.content
    assert "bare" not in answer.content
    assert answer.content.endswith("[Report](https://a--dl.smithbox.dev/token)\n")
    assert _text([{"text": "a"}, "b"]) == "ab"
    assert _text(5) == "5"
    assert middleware.after_model(
        {"messages": [published(), AIMessage(content=[{"type": "text", "text": "report"}])]}
    )
