from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from refinery_data.domain import (
    Asset,
    InspectionNote,
    QueryResult,
    SensorTag,
    SensorTrend,
    WorkOrder,
)
from refinery_data.source import RefineryDataSource, SqliteRefineryDataSource
from tools import build_tools


@pytest.fixture
def fake():
    source = Mock(spec=RefineryDataSource)
    source.get_asset.return_value = Asset(
        asset_id="P-101A", unit_id="CDU", name="Pump", equipment_type="pump", criticality="A"
    )
    source.get_sensor_trend.return_value = (
        SensorTrend(
            tag=SensorTag(
                tag_id="VIB",
                asset_id="P-101A",
                measurement="vibration",
                unit_of_measure="mm/s RMS",
                alarm_low=0,
                alarm_high=4.5,
            ),
            points=(),
        ),
    )
    source.run_sql.return_value = QueryResult(
        columns=("n",), rows=({"n": 3},), truncated=False, row_limit=200
    )
    source.get_maintenance_history.return_value = (
        WorkOrder(
            work_order_id="WO-1",
            asset_id="P-101A",
            opened_at="2026-09-01",
            completed_at=None,
            work_type="CM",
            status="cancelled",
            description="Seal",
            cost=0,
            hours=0,
        ),
    )
    source.search_inspection_notes.return_value = (
        InspectionNote(
            note_id="N-1",
            asset_id="P-101A",
            inspected_at="2026-09-01",
            work_order_id="WO-1",
            note="replaced",
        ),
    )
    return source


def test_tools_delegate_and_preserve_evidence(fake):
    tools = build_tools(fake)
    assert tools.get_asset.invoke({"asset_id": "P-101A"})["synthetic"] is True
    assert (
        tools.get_sensor_trend.invoke({"asset_id": "P-101A", "days": 7})["trends"][0]["tag"][
            "unit_of_measure"
        ]
        == "mm/s RMS"
    )
    fake.get_sensor_trend.assert_called_once_with("P-101A", 7)
    assert tools.run_sql.invoke({"query": "SELECT 3 AS n"})["rows"] == ({"n": 3},)
    assert tools.get_maintenance_history.invoke({"asset_id": "P-101A"})[0]["status"] == "cancelled"
    assert (
        tools.search_inspection_notes.invoke({"asset_id": "P-101A", "query": "seal"})[0][
            "work_order_id"
        ]
        == "WO-1"
    )
    fake.search_inspection_notes.assert_called_once_with("P-101A", "seal")


def test_draft_is_repeatable_and_does_not_submit(fake):
    tools = build_tools(fake)
    args = dict(
        asset_id="P-101A",
        title="Bearing inspection",
        priority="P2",
        justification="Vibration rising below alarm",
        tasks=["Inspect bearing"],
    )
    draft = tools.draft_work_order.invoke(args)
    assert draft == tools.draft_work_order.invoke(args)
    assert draft["status"] == "draft"
    assert draft["submitted_to_cmms"] is False
    assert draft["synthetic"] is True
    assert "tasks" in tools.draft_work_order.invoke({**args, "tasks": []})
    with pytest.raises(ValidationError):
        tools.draft_work_order.invoke({**args, "priority": "urgent"})


def test_bad_lookup_returns_recoverable_tool_error(fake):
    fake.get_asset.side_effect = ValueError("Unknown asset: K-401-PT-3; use an asset tag")
    assert "Unknown asset" in build_tools(fake).get_asset.invoke({"asset_id": "K-401-PT-3"})


def test_sensor_tag_resolves_to_parent_asset(tmp_path):
    tools = build_tools(SqliteRefineryDataSource(tmp_path / "refinery.db"))
    result = tools.get_asset.invoke({"asset_id": "K-401-PT-3"})
    assert result["asset_id"] == "K-401"
    assert result["resolved_from_tag"] == "K-401-PT-3"


def test_unknown_asset_returns_tool_message(tmp_path):
    tools = build_tools(SqliteRefineryDataSource(tmp_path / "refinery.db"))
    result = tools.get_asset.invoke({"asset_id": "bogus"})
    assert "Unknown asset or sensor tag: bogus" in result
    assert "K-401" in result
