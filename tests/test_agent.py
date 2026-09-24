import importlib
from typing import Any, cast
from unittest.mock import Mock

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig  # noqa: TC002
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from refinery_data.domain import Asset
from tools import build_tools


class ToolModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def test_agent_wiring(monkeypatch):
    import models

    model = ToolModel(responses=[AIMessage(content="done")])
    monkeypatch.setattr(models, "init_chat_model", lambda *a, **kw: model)
    models.gateway_model.cache_clear()
    module = importlib.import_module("agent")
    assert module.agent.config["interrupt_on"] == {"draft_work_order": True}
    assert {t.name for t in cast("Any", module.agent.config["tools"])} == {
        "get_asset",
        "draft_work_order",
        "publish_artifact",
    }
    assert {s["name"] for s in cast("Any", module.agent.config["subagents"])} == {
        "data-analyst",
        "maintenance-planner",
    }
    assert all(
        s["runnable"].checkpointer is False for s in cast("Any", module.agent.config["subagents"])
    )


@pytest.mark.parametrize("decision", ["approve", "reject", "edit"])
def test_draft_pauses_before_tool_and_resumes(decision):
    source = Mock()
    source.get_asset.return_value = Asset(
        asset_id="P-101A", unit_id="CDU", name="Pump", equipment_type="pump", criticality="A"
    )
    tool = build_tools(source).draft_work_order
    args = dict(
        asset_id="P-101A",
        title="Bearing inspection",
        priority="P2",
        justification="Vibration rising below alarm",
        tasks=["Inspect bearing"],
    )
    model = ToolModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "draft_work_order", "args": args, "id": "call-1", "type": "tool_call"}
                ],
            ),
            AIMessage(content="done"),
        ]
    )
    graph = create_agent(
        model,
        [tool],
        middleware=[HumanInTheLoopMiddleware(interrupt_on={"draft_work_order": True})],
        checkpointer=InMemorySaver(),
    )
    config: RunnableConfig = {"configurable": {"thread_id": decision}}
    paused = graph.invoke({"messages": [("user", "Draft inspection")]}, config)
    assert paused["__interrupt__"]
    source.get_asset.assert_not_called()
    response = {"type": decision}
    if decision == "edit":
        response["edited_action"] = {"name": "draft_work_order", "args": {**args, "priority": "P3"}}
    final = graph.invoke(Command(resume={"decisions": [response]}), config)
    assert not final.get("__interrupt__")
    assert source.get_asset.call_count == (0 if decision == "reject" else 1)
    if decision == "edit":
        assert '"priority": "P3"' in final["messages"][-2].content
