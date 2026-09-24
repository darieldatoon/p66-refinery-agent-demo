from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, TypeAdapter

from refinery_data.domain import Asset, DraftRequest, Priority, Record, WorkOrderDraft
from refinery_data.seed import AS_OF
from refinery_data.source import RefineryDataSource

SNAPSHOT_ID = "refinery-2026-09-23-v1"
Condition = Literal["needs_attention", "watch", "uncertain"]


class Evidence(Record):
    reference_id: str
    kind: Literal["sensor", "work_order", "note", "failure"]
    description: str


class Signal(Record):
    issue_id: str
    asset_id: str
    title: str
    summary: str
    priority: Priority
    category: Literal["condition", "recurrence", "data_quality"]
    evidence: tuple[Evidence, ...]

    @property
    def thread_id(self) -> str:
        return str(uuid5(NAMESPACE_URL, f"{SNAPSHOT_ID}/issues/{self.issue_id}"))


class Assessment(Record):
    assessment_id: str
    issue_id: str
    condition: Condition
    priority: Priority
    summary: str = Field(min_length=10, max_length=2000)
    recommendation: str = Field(min_length=10, max_length=2000)
    uncertainty: str = Field(min_length=5, max_length=1500)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    assessed_at: str
    thread_id: str


class ReviewDecision(Record):
    action: Literal["approve", "reject"]
    reason: str = Field(default="", max_length=1000)


class Review(ReviewDecision):
    reviewed_at: str
    actor: Literal["workspace_operator"] = "workspace_operator"


class Proposal(Record):
    proposal_id: str
    issue_id: str
    request: DraftRequest
    created_at: str
    thread_id: str


class PendingProposal(Proposal):
    status: Literal["pending_review"] = "pending_review"


class ApprovedProposal(Proposal):
    status: Literal["approved"] = "approved"
    review: Review
    draft: WorkOrderDraft


class RejectedProposal(Proposal):
    status: Literal["rejected"] = "rejected"
    review: Review


WorkProposal = Annotated[
    PendingProposal | ApprovedProposal | RejectedProposal, Field(discriminator="status")
]
PROPOSAL_ADAPTER: TypeAdapter[WorkProposal] = TypeAdapter(WorkProposal)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def proposal_id(issue_id: str, request: DraftRequest) -> str:
    return str(uuid5(NAMESPACE_URL, f"{SNAPSHOT_ID}/{issue_id}/{request.model_dump_json()}"))


def decide_proposal(
    proposal: PendingProposal, decision: ReviewDecision, reviewed_at: str
) -> ApprovedProposal | RejectedProposal:
    fields = proposal.model_dump(exclude={"status"})
    review = Review(**decision.model_dump(), reviewed_at=reviewed_at)
    if decision.action == "reject":
        return RejectedProposal(**fields, review=review)
    draft = WorkOrderDraft(draft_id=f"DRAFT-{proposal.proposal_id[:12]}", request=proposal.request)
    return ApprovedProposal(**fields, review=review, draft=draft)


def signal_catalog(source: RefineryDataSource) -> tuple[Signal, ...]:
    vibration = next(
        trend for trend in source.get_sensor_trend("P-101A") if trend.tag.measurement == "vibration"
    )
    exchanger = {trend.tag.measurement: trend for trend in source.get_sensor_trend("E-205")}
    dp = exchanger["differential_pressure"]
    duty = exchanger["heat_duty"]
    failures = source.run_sql("SELECT * FROM failure_events WHERE asset_id = 'C-301'").rows
    cancelled = next(
        order
        for order in source.get_maintenance_history("P-102B")
        if order.work_order_id == "WO-0005"
    )
    return (
        Signal(
            issue_id="p101a-vibration",
            asset_id="P-101A",
            title="Vibration is trending upward",
            summary=(
                f"Daily mean moved from {vibration.points[0].value:.2f} to "
                f"{vibration.points[-1].value:.2f} {vibration.tag.unit_of_measure}. "
                f"The configured alarm is {vibration.tag.alarm_high:g} "
                f"{vibration.tag.unit_of_measure}."
            ),
            priority="P2",
            category="condition",
            evidence=(
                Evidence(
                    reference_id=vibration.tag.tag_id,
                    kind="sensor",
                    description="45-day vibration trend",
                ),
                Evidence(
                    reference_id="N-001", kind="note", description="Bearing housing noise reported"
                ),
                Evidence(
                    reference_id="WO-0001",
                    kind="work_order",
                    description="Lubrication, not bearing replacement",
                ),
            ),
        ),
        Signal(
            issue_id="e205-fouling",
            asset_id="E-205",
            title="Exchanger performance is drifting",
            summary=(
                f"Differential pressure rose from {dp.points[0].value:.2f} to "
                f"{dp.points[-1].value:.2f} {dp.tag.unit_of_measure}; heat duty fell from "
                f"{duty.points[0].value:.2f} to {duty.points[-1].value:.2f} "
                f"{duty.tag.unit_of_measure}."
            ),
            priority="P2",
            category="condition",
            evidence=(
                Evidence(
                    reference_id=dp.tag.tag_id,
                    kind="sensor",
                    description="Increasing differential pressure",
                ),
                Evidence(
                    reference_id=duty.tag.tag_id, kind="sensor", description="Decreasing heat duty"
                ),
                Evidence(
                    reference_id="N-002",
                    kind="note",
                    description="Fouling suspected; flows need verification",
                ),
            ),
        ),
        Signal(
            issue_id="c301-seals",
            asset_id="C-301",
            title="Seal failures keep recurring",
            summary=(
                f"{len(failures)} recorded seal failures in this 45-day window. "
                "Investigate the recorded flush-system cause."
            ),
            priority="P2",
            category="recurrence",
            evidence=(
                *tuple(
                    Evidence(
                        reference_id=str(row["failure_id"]),
                        kind="failure",
                        description=str(row["root_cause"]),
                    )
                    for row in failures
                ),
                Evidence(
                    reference_id="N-003",
                    kind="note",
                    description="Repeated flush line contamination reported",
                ),
            ),
        ),
        Signal(
            issue_id="p102b-records",
            asset_id="P-102B",
            title="Repair records contradict the handover",
            summary=(
                f"N-005 claims a seal replacement, but linked order WO-0005 is {cancelled.status}. "
                "Completion is unverified."
            ),
            priority="P3",
            category="data_quality",
            evidence=(
                Evidence(
                    reference_id="N-005",
                    kind="note",
                    description="Handover claims seal replacement",
                ),
                Evidence(
                    reference_id="WO-0005",
                    kind="work_order",
                    description="Replacement cancelled awaiting a part",
                ),
            ),
        ),
    )


def get_signal(source: RefineryDataSource, issue_id: str) -> Signal:
    for signal in signal_catalog(source):
        if signal.issue_id == issue_id:
            return signal
    raise ValueError(f"Unknown issue: {issue_id}")


def asset_detail(source: RefineryDataSource, asset_id: str) -> dict[str, Any]:
    asset = source.get_asset(asset_id)
    return {
        "asset": asset.model_dump(),
        "trends": [trend.model_dump() for trend in source.get_sensor_trend(asset_id)],
        "work_orders": [order.model_dump() for order in source.get_maintenance_history(asset_id)],
        "notes": [note.model_dump() for note in source.search_inspection_notes(asset_id)],
        "failures": list(
            source.run_sql(f"SELECT * FROM failure_events WHERE asset_id = '{asset.asset_id}'").rows
        ),
    }


def evidence_ids(detail: dict[str, Any]) -> frozenset[str]:
    return frozenset(
        [trend["tag"]["tag_id"] for trend in detail["trends"]]
        + [order["work_order_id"] for order in detail["work_orders"]]
        + [note["note_id"] for note in detail["notes"]]
        + [event["failure_id"] for event in detail["failures"]]
    )


def static_workspace(source: RefineryDataSource) -> dict[str, Any]:
    assets = source.run_sql("SELECT * FROM assets ORDER BY unit_id, asset_id").rows
    return {
        "snapshot_id": SNAPSHOT_ID,
        "data_as_of": AS_OF.isoformat(),
        "synthetic": True,
        "assets": [Asset.model_validate(asset).model_dump() for asset in assets],
        "units": list(source.run_sql("SELECT * FROM units ORDER BY unit_id").rows),
        "signals": [
            signal.model_dump() | {"thread_id": signal.thread_id}
            for signal in signal_catalog(source)
        ],
    }
