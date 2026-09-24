from dataclasses import replace
from typing import Any, cast
from unittest.mock import Mock

import pytest
from langchain.agents import create_agent
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig  # noqa: TC002
from langchain_core.tools import ToolException
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command
from pydantic import ValidationError

from middleware.prompt_variant import DemoContext, demo_prompt_variant
from middleware.workspace import WorkspaceMiddleware
from refinery_data.domain import DraftRequest
from refinery_data.repository import IssueRepository
from refinery_data.source import SqliteRefineryDataSource
from refinery_data.workspace import (
    Assessment,
    PendingProposal,
    ReviewDecision,
    asset_detail,
    decide_proposal,
    evidence_ids,
    get_signal,
    signal_catalog,
    static_evidence,
    static_workspace,
)
from tests.test_agent import ToolModel
from tools.workspace import build_workspace_tools

ISSUE = "p101a-vibration"
ASSESSMENT_ARGS: dict[str, Any] = {
    "issue_id": ISSUE,
    "condition": "watch",
    "priority": "P2",
    "summary": "Vibration rises below the configured alarm.",
    "recommendation": "Inspect the bearing housing and verify lubrication.",
    "uncertainty": "The trend does not establish the root cause.",
    "cited_evidence_ids": ["P-101A-VIB", "N-001", "WO-0001", "SP-001"],
}
PROPOSAL_ARGS: dict[str, Any] = {
    "issue_id": ISSUE,
    "title": "Bearing inspection",
    "priority": "P2",
    "justification": "Rising vibration and the reported bearing noise warrant inspection.",
    "tasks": ["Inspect bearing housing", "Verify lubrication"],
}


@pytest.fixture
def source():
    return SqliteRefineryDataSource()


def runtime_for(source, store=None):
    signal = get_signal(source, ISSUE)
    return ToolRuntime(
        state={},
        context=DemoContext(issue_id=ISSUE),
        config={"configurable": {"thread_id": signal.thread_id}},
        stream_writer=lambda value: None,
        tool_call_id="assessment-1",
        store=store,
    )


async def call_tool(tools, name, args, runtime):
    return await cast("Any", tools[name]).coroutine(**args, runtime=runtime)


def test_fixed_snapshot_signals_and_evidence(source):
    snapshot = static_workspace(source)
    assert len(snapshot["assets"]) == 40
    assert {s["asset_id"] for s in snapshot["signals"]} == {"P-101A", "E-205", "C-301", "P-102B"}
    assert snapshot["synthetic"] is True
    for signal in signal_catalog(source):
        valid = evidence_ids(asset_detail(source, signal.asset_id))
        assert {e.reference_id for e in signal.evidence} <= valid
        assert signal.thread_id == get_signal(source, signal.issue_id).thread_id
    assert "cancelled" in get_signal(source, "p102b-records").summary
    assert [s["priority"] for s in snapshot["signals"]] == ["P1", "P2", "P2", "P3"]
    evidence = static_evidence(source)
    assert len(evidence) == 40
    assert evidence["P-101A"]["spare_parts"][0]["stock_on_hand"] == 0
    with pytest.raises(ValueError, match="Unknown issue"):
        get_signal(source, "missing")
    with pytest.raises(ValueError, match="Unknown asset"):
        asset_detail(source, "'; DROP TABLE assets; --")


def test_issue_evidence_lists_citable_ids(source):
    tool = next(tool for tool in build_workspace_tools(source) if tool.name == "get_issue_evidence")
    evidence = tool.invoke({"issue_id": ISSUE})
    assert "SP-001" in evidence["citable_evidence_ids"]


@pytest.mark.asyncio
async def test_workspace_read_bypasses_model_and_supports_general_chat(source):
    model = ToolModel(responses=[AIMessage(content="hello")])
    middleware = WorkspaceMiddleware(source)
    graph = create_agent(
        model, middleware=[middleware], context_schema=DemoContext, store=InMemoryStore()
    )
    result = await graph.ainvoke({}, context=DemoContext(operation="workspace", asset_id="K-401"))
    assert not result["messages"]
    assert len(result["workspace"]["issues"]) == 4
    assert result["workspace"]["selected_asset"]["asset"]["asset_id"] == "K-401"
    assert all(i["assessment"] is None for i in result["workspace"]["issues"])
    assert (await graph.ainvoke({"messages": [("user", "Hello")]}))["messages"][
        -1
    ].content == "hello"
    with pytest.raises(RuntimeError, match="managed Store"):
        await middleware.abefore_agent(
            {"messages": []}, Runtime(context=DemoContext(operation="workspace"))
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["approve", "reject"])
async def test_issue_review_is_durable_and_never_changes_condition(source, decision):
    store = InMemoryStore()
    tools = build_workspace_tools(source)
    calls = [
        {
            "name": "get_issue_evidence",
            "args": {"issue_id": ISSUE},
            "id": "evidence",
            "type": "tool_call",
        },
        {
            "name": "record_issue_assessment",
            "args": ASSESSMENT_ARGS,
            "id": "assessment",
            "type": "tool_call",
        },
        {
            "name": "propose_issue_work",
            "args": PROPOSAL_ARGS,
            "id": "proposal",
            "type": "tool_call",
        },
    ]
    model = ToolModel(
        responses=[
            *(AIMessage(content="", tool_calls=[c]) for c in calls),
            AIMessage(content="done"),
        ]
    )
    graph = create_agent(
        model, tools, store=store, checkpointer=InMemorySaver(), context_schema=DemoContext
    )
    config: RunnableConfig = {"configurable": {"thread_id": get_signal(source, ISSUE).thread_id}}
    context = DemoContext(issue_id=ISSUE)
    paused = await graph.ainvoke(
        {"messages": [("user", "Investigate and propose work")]}, config, context=context
    )
    pending = paused["__interrupt__"][0].value
    assert pending["kind"] == "work_order_review"
    assert pending["proposal"]["status"] == "pending_review"
    repository = IssueRepository(store)
    before = await repository.workspace(source)
    stored = (await repository.proposals())[0]
    assert "draft" not in stored.model_dump()
    final = await graph.ainvoke(
        Command(resume={"action": decision, "reason": "Operator review"}), config, context=context
    )
    assert not final.get("__interrupt__")
    reviewed = (await repository.proposals())[0]
    assert reviewed.status == ("approved" if decision == "approve" else "rejected")
    assert reviewed.created_at == stored.created_at
    assert reviewed.review.actor == "workspace_operator"
    if decision == "approve":
        assert reviewed.status == "approved"
        assert reviewed.draft.submitted_to_cmms is False
    else:
        assert "draft" not in reviewed.model_dump()
    after = await repository.workspace(source)
    assert [i["assessment"] for i in before["issues"]] == [i["assessment"] for i in after["issues"]]
    runtime = runtime_for(source, store)
    replayed = await call_tool(
        {t.name: t for t in tools}, "propose_issue_work", PROPOSAL_ARGS, runtime
    )
    assert replayed["proposal_id"] == stored.proposal_id
    assert len(await repository.proposals()) == 1


@pytest.mark.asyncio
async def test_assessment_and_proposal_guards(source):
    store = InMemoryStore()
    runtime = runtime_for(source, store)
    tools = {t.name: t for t in build_workspace_tools(source)}
    with pytest.raises(ToolException, match="assessment"):
        await call_tool(tools, "propose_issue_work", PROPOSAL_ARGS, runtime)
    for bad_runtime in [
        replace(runtime, context=None),
        replace(runtime, context=DemoContext(issue_id="wrong")),
        replace(runtime, config={"configurable": {"thread_id": "other"}}),
    ]:
        with pytest.raises(ToolException, match="canonical"):
            await call_tool(tools, "record_issue_assessment", ASSESSMENT_ARGS, bad_runtime)
    with pytest.raises(RuntimeError, match="managed Store"):
        await call_tool(
            tools, "record_issue_assessment", ASSESSMENT_ARGS, replace(runtime, store=None)
        )
    with pytest.raises(
        ToolException, match=r"Unknown evidence IDs for P-101A: \['SP-003'\]"
    ) as error:
        await call_tool(
            tools,
            "record_issue_assessment",
            ASSESSMENT_ARGS | {"cited_evidence_ids": ["SP-003"]},
            runtime,
        )
    assert "Valid IDs:" in str(error.value)
    assert "SP-001" in str(error.value)
    with pytest.raises(ValidationError):
        await call_tool(
            tools, "record_issue_assessment", ASSESSMENT_ARGS | {"cited_evidence_ids": []}, runtime
        )
    first = await call_tool(tools, "record_issue_assessment", ASSESSMENT_ARGS, runtime)
    second = await call_tool(tools, "record_issue_assessment", ASSESSMENT_ARGS, runtime)
    assert first["assessment_id"] == second["assessment_id"]
    assert len(await IssueRepository(store).assessments()) == 1


@pytest.mark.asyncio
async def test_history_paginates_and_latest_assessment_controls_priority(source):
    store = InMemoryStore()
    repo = IssueRepository(store)
    base: dict[str, Any] = dict(ASSESSMENT_ARGS)
    base["evidence_ids"] = base.pop("cited_evidence_ids")
    base["priority"] = "P3"
    for i in range(102):
        await repo.save_assessment(
            Assessment(
                **base,
                assessment_id=f"assessment-{i:03}",
                assessed_at=f"2026-09-24T00:00:{i:03}Z",
                thread_id=get_signal(source, ISSUE).thread_id,
            )
        )
    view = await repo.workspace(source)
    issue = next(i for i in view["issues"] if i["issue_id"] == ISSUE)
    assert len(issue["assessment_history"]) == 102
    assert issue["assessment"]["assessment_id"] == "assessment-101"
    assert view["issues"][0]["issue_id"] != ISSUE


def test_review_decision_requires_explicit_valid_choice():
    with pytest.raises(ValidationError):
        ReviewDecision.model_validate({"action": "maybe"})
    proposal = PendingProposal(
        proposal_id="id",
        issue_id=ISSUE,
        created_at="now",
        thread_id="thread",
        request=DraftRequest(
            asset_id="P-101A", **{k: v for k, v in PROPOSAL_ARGS.items() if k != "issue_id"}
        ),
    )
    rejected = decide_proposal(proposal, ReviewDecision(action="reject"), "later")
    assert rejected.status == "rejected"


def test_issue_prompt_carries_backend_workflow():
    from langchain.agents.middleware import ModelRequest
    from langchain_core.messages import SystemMessage

    request = ModelRequest(
        model=ToolModel(responses=[AIMessage(content="done")]),
        messages=[],
        system_message=SystemMessage(content="Base prompt"),
        runtime=Runtime(context=DemoContext(issue_id=ISSUE)),
    )
    handler = Mock()
    demo_prompt_variant.wrap_model_call(request, handler)
    prompt = handler.call_args.args[0].system_message.text
    assert ISSUE in prompt
    assert "propose_issue_work" in prompt
