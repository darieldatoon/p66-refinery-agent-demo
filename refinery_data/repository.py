import asyncio
from typing import Any

from langgraph.store.base import BaseStore

from refinery_data.source import RefineryDataSource
from refinery_data.workspace import (
    PROPOSAL_ADAPTER,
    SNAPSHOT_ID,
    Assessment,
    WorkProposal,
    asset_detail,
    issue_rank,
    static_workspace,
)


class IssueRepository:
    def __init__(self, store: BaseStore) -> None:
        self.store = store
        self.namespace = ("refinery-workspace", SNAPSHOT_ID)

    async def _list(self, kind: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        while True:
            page = await self.store.asearch((*self.namespace, kind), limit=100, offset=len(records))
            records.extend(item.value for item in page)
            if len(page) < 100:
                return records

    async def assessments(self) -> list[Assessment]:
        return [Assessment.model_validate(value) for value in await self._list("assessments")]

    async def save_assessment(self, assessment: Assessment) -> None:
        await self.store.aput(
            (*self.namespace, "assessments"),
            assessment.assessment_id,
            assessment.model_dump(mode="json"),
        )

    async def proposals(self) -> list[WorkProposal]:
        return [PROPOSAL_ADAPTER.validate_python(value) for value in await self._list("proposals")]

    async def get_proposal(self, proposal_id: str) -> WorkProposal | None:
        item = await self.store.aget((*self.namespace, "proposals"), proposal_id)
        return PROPOSAL_ADAPTER.validate_python(item.value) if item else None

    async def save_proposal(self, proposal: WorkProposal) -> None:
        await self.store.aput(
            (*self.namespace, "proposals"),
            proposal.proposal_id,
            proposal.model_dump(mode="json"),
        )

    async def workspace(
        self, source: RefineryDataSource, selected_asset: str | None = None
    ) -> dict[str, Any]:
        snapshot = await asyncio.to_thread(static_workspace, source)
        criticality = {asset["asset_id"]: asset["criticality"] for asset in snapshot["assets"]}
        assessments = await self.assessments()
        proposals = await self.proposals()
        issues = []
        for signal in snapshot.pop("signals"):
            history = sorted(
                [a for a in assessments if a.issue_id == signal["issue_id"]],
                key=lambda a: (a.assessed_at, a.assessment_id),
                reverse=True,
            )
            work = sorted(
                [p for p in proposals if p.issue_id == signal["issue_id"]],
                key=lambda p: (p.created_at, p.proposal_id),
                reverse=True,
            )
            issues.append(
                signal
                | {
                    "assessment": history[0].model_dump(mode="json") if history else None,
                    "assessment_history": [a.model_dump(mode="json") for a in history],
                    "proposals": [p.model_dump(mode="json") for p in work],
                }
            )
        return snapshot | {
            "issues": sorted(
                issues,
                key=lambda i: issue_rank(
                    (i["assessment"] or i)["priority"], criticality[i["asset_id"]], i["issue_id"]
                ),
            ),
            "selected_asset": (
                await asyncio.to_thread(asset_detail, source, selected_asset)
                if selected_asset
                else None
            ),
        }
