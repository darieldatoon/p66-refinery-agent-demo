import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from langchain.tools import tool
from langchain_core.tools import BaseTool, ToolException

from refinery_data.domain import DraftRequest, Priority, WorkOrderDraft
from refinery_data.seed import AS_OF
from refinery_data.source import RefineryDataSource


def _recoverable_tool(function: Callable[..., Any]) -> BaseTool:
    @wraps(function)
    def invoke(*args: Any, **kwargs: Any) -> Any:
        try:
            return function(*args, **kwargs)
        except ValueError as exc:
            raise ToolException(json.dumps({"error": str(exc), "message": str(exc)})) from exc

    registered = tool(invoke)
    registered.handle_tool_error = True
    return registered


@dataclass(frozen=True)
class RefineryTools:
    get_asset: BaseTool
    get_sensor_trend: BaseTool
    run_sql: BaseTool
    get_maintenance_history: BaseTool
    search_inspection_notes: BaseTool
    draft_work_order: BaseTool


def build_tools(source: RefineryDataSource) -> RefineryTools:
    @_recoverable_tool
    def get_asset(asset_id: str) -> dict[str, Any]:
        """Look up an exact refinery asset tag, its unit and criticality."""
        return {
            **source.get_asset(asset_id).model_dump(),
            "synthetic": True,
            "data_as_of": AS_OF.isoformat(),
        }

    @_recoverable_tool
    def get_sensor_trend(asset_id: str, days: int = 45) -> dict[str, Any]:
        """Get daily means, min/max, counts, native units and alarm limits for all asset sensors.

        days is 1-45 relative to the fixture's data_as_of, not the wall clock.
        """
        return {
            "data_as_of": AS_OF.isoformat(),
            "aggregation": "daily",
            "trends": [trend.model_dump() for trend in source.get_sensor_trend(asset_id, days)],
        }

    @_recoverable_tool
    def run_sql(query: str) -> dict[str, Any]:
        """Run one read-only SELECT with a 200-row cap; check truncated before drawing conclusions.

        Tables: units(unit_id,name); assets(asset_id,unit_id,name,equipment_type,criticality);
        sensor_tags(tag_id,asset_id,measurement,unit_of_measure,alarm_low,alarm_high);
        sensor_readings(tag_id,timestamp,value);
        work_orders(work_order_id,asset_id,opened_at,completed_at,work_type,status,description,cost,hours);
        failure_events(failure_id,asset_id,occurred_at,failure_mode,root_cause,downtime_hours);
        inspection_notes(note_id,asset_id,inspected_at,work_order_id,note);
        spare_parts(part_id,asset_id,description,stock_on_hand,reorder_point).
        Timestamps are ISO UTC. Use aggregates for large results. No PRAGMA, CTE or writes.
        """
        return source.run_sql(query).model_dump()

    @_recoverable_tool
    def get_maintenance_history(asset_id: str) -> list[dict[str, Any]]:
        """Get all work orders including cancelled/open status; only completed proves completion."""
        return [order.model_dump() for order in source.get_maintenance_history(asset_id)]

    @_recoverable_tool
    def search_inspection_notes(asset_id: str, query: str = "") -> list[dict[str, Any]]:
        """Search an asset's inspection notes by literal substring; empty query returns all notes.

        Notes are unverified observations. Reconcile replacement claims with work-order status.
        """
        return [note.model_dump() for note in source.search_inspection_notes(asset_id, query)]

    @_recoverable_tool
    def draft_work_order(
        asset_id: str, title: str, priority: Priority, justification: str, tasks: list[str]
    ) -> dict[str, Any]:
        """Create a synthetic work-order draft after human approval; never submits to a CMMS.

        Priority: P1 immediate, P2 within 48h, P3 within 7d, P4 next planned outage.
        Include evidence in justification and specific inspection tasks.
        """
        source.get_asset(asset_id)
        request = DraftRequest(
            asset_id=asset_id,
            title=title,
            priority=priority,
            justification=justification,
            tasks=tuple(tasks),
        )
        draft_id = f"DRAFT-{str(uuid5(NAMESPACE_URL, request.model_dump_json()))[:12]}"
        return WorkOrderDraft(draft_id=draft_id, request=request).model_dump()

    return RefineryTools(
        get_asset,
        get_sensor_trend,
        run_sql,
        get_maintenance_history,
        search_inspection_notes,
        draft_work_order,
    )
