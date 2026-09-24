import asyncio
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from langchain.tools import ToolRuntime, tool
from langchain_core.tools import BaseTool, ToolException
from langgraph.types import interrupt

from middleware.prompt_variant import DemoContext
from refinery_data.domain import DraftRequest, Priority
from refinery_data.repository import IssueRepository
from refinery_data.source import RefineryDataSource
from refinery_data.workspace import (
    Assessment,
    Condition,
    PendingProposal,
    ReviewDecision,
    Signal,
    asset_detail,
    decide_proposal,
    evidence_ids,
    get_signal,
    proposal_id,
    utc_now,
)


def _repository(runtime: ToolRuntime[DemoContext], signal: Signal) -> IssueRepository:
    context = runtime.context or DemoContext()
    thread_id = runtime.config.get("configurable", {}).get("thread_id")
    if context.issue_id != signal.issue_id or thread_id != signal.thread_id:
        raise ToolException(
            "Open this issue's canonical investigation thread before saving changes."
        )
    if runtime.store is None:
        raise RuntimeError("The managed Store is required for issue changes")
    return IssueRepository(runtime.store)


def build_workspace_tools(source: RefineryDataSource) -> list[BaseTool]:
    @tool
    def get_issue_evidence(issue_id: str) -> dict[str, Any]:
        """Read an issue signal and its sensor, maintenance and failure evidence."""
        signal = get_signal(source, issue_id)
        detail = asset_detail(source, signal.asset_id)
        return {
            "signal": signal.model_dump(),
            "detail": detail,
            "citable_evidence_ids": sorted(evidence_ids(detail)),
        }

    @tool
    async def record_issue_assessment(
        issue_id: str,
        condition: Condition,
        priority: Priority,
        summary: str,
        recommendation: str,
        uncertainty: str,
        cited_evidence_ids: list[str],
        runtime: ToolRuntime[DemoContext],
    ) -> dict[str, Any]:
        """Cite this asset's tag, work-order, note, failure, or spare-part IDs."""
        signal = await asyncio.to_thread(get_signal, source, issue_id)
        repository = _repository(runtime, signal)
        valid_ids = evidence_ids(await asyncio.to_thread(asset_detail, source, signal.asset_id))
        unknown_ids = sorted(set(cited_evidence_ids) - valid_ids)
        if unknown_ids:
            raise ToolException(
                f"Unknown evidence IDs for {signal.asset_id}: {unknown_ids}. "
                f"Valid IDs: {sorted(valid_ids)}"
            )
        assessment = Assessment(
            assessment_id=str(uuid5(NAMESPACE_URL, f"{signal.thread_id}/{runtime.tool_call_id}")),
            issue_id=issue_id,
            condition=condition,
            priority=priority,
            summary=summary,
            recommendation=recommendation,
            uncertainty=uncertainty,
            evidence_ids=tuple(cited_evidence_ids),
            assessed_at=utc_now(),
            thread_id=signal.thread_id,
        )
        await repository.save_assessment(assessment)
        return assessment.model_dump(mode="json")

    @tool
    async def propose_issue_work(
        issue_id: str,
        title: str,
        priority: Priority,
        justification: str,
        tasks: list[str],
        runtime: ToolRuntime[DemoContext],
    ) -> dict[str, Any]:
        """Propose synthetic work for an assessed issue and pause for human approve/reject.

        Saves the exact proposal before pausing. Approval creates a synthetic draft only;
        rejection creates no draft. Never operates equipment or submits to a CMMS.
        """
        signal = await asyncio.to_thread(get_signal, source, issue_id)
        repository = _repository(runtime, signal)
        if not any(a.issue_id == issue_id for a in await repository.assessments()):
            raise ToolException("Investigate and save an assessment before proposing work.")
        request = DraftRequest(
            asset_id=signal.asset_id,
            title=title,
            priority=priority,
            justification=justification,
            tasks=tuple(tasks),
        )
        identifier = proposal_id(issue_id, request)
        existing = await repository.get_proposal(identifier)
        if existing is not None and not isinstance(existing, PendingProposal):
            return existing.model_dump(mode="json")
        proposal = (
            existing
            if isinstance(existing, PendingProposal)
            else PendingProposal(
                proposal_id=identifier,
                issue_id=issue_id,
                request=request,
                created_at=utc_now(),
                thread_id=signal.thread_id,
            )
        )
        # This write must remain idempotent: resuming an interrupt replays the tool.
        await repository.save_proposal(proposal)
        response = interrupt(
            {"kind": "work_order_review", "proposal": proposal.model_dump(mode="json")}
        )
        decision = ReviewDecision.model_validate(response)
        reviewed = decide_proposal(proposal, decision, utc_now())
        await repository.save_proposal(reviewed)
        return reviewed.model_dump(mode="json")

    tools = [get_issue_evidence, record_issue_assessment, propose_issue_work]
    for registered in tools:
        registered.handle_tool_error = True
    return tools
