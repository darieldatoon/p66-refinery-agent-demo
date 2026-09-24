from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Priority = Literal["P1", "P2", "P3", "P4"]


class Record(BaseModel):
    model_config = ConfigDict(frozen=True)


class Asset(Record):
    asset_id: str
    unit_id: str
    name: str
    equipment_type: str
    criticality: Literal["A", "B", "C"]


class SensorTag(Record):
    tag_id: str
    asset_id: str
    measurement: str
    unit_of_measure: str
    alarm_low: float
    alarm_high: float
    source_unit_of_measure: str | None = None
    source_alarm_low: float | None = None
    source_alarm_high: float | None = None


class TrendPoint(Record):
    timestamp: str
    value: float
    minimum: float
    maximum: float
    samples: int
    source_value: float | None = None
    source_minimum: float | None = None
    source_maximum: float | None = None


class SensorTrend(Record):
    tag: SensorTag
    points: tuple[TrendPoint, ...]


class WorkOrder(Record):
    work_order_id: str
    asset_id: str
    opened_at: str
    completed_at: str | None
    work_type: Literal["PM", "CM", "EM"]
    status: Literal["completed", "open", "cancelled"]
    description: str
    cost: float
    hours: float


class InspectionNote(Record):
    note_id: str
    asset_id: str
    inspected_at: str
    work_order_id: str | None
    note: str


class QueryResult(Record):
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    truncated: bool
    row_limit: int


class DraftRequest(Record):
    asset_id: str
    title: str = Field(min_length=5, max_length=160)
    priority: Priority
    justification: str = Field(min_length=10, max_length=2000)
    tasks: tuple[str, ...] = Field(min_length=1, max_length=20)


class WorkOrderDraft(Record):
    draft_id: str
    request: DraftRequest
    status: Literal["draft"] = "draft"
    synthetic: Literal[True] = True
    submitted_to_cmms: Literal[False] = False
