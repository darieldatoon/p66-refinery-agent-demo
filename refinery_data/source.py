import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any, Literal, Protocol

from refinery_data.domain import (
    Asset,
    InspectionNote,
    QueryResult,
    SensorTag,
    SensorTrend,
    TrendPoint,
    WorkOrder,
)
from refinery_data.seed import AS_OF, DEFAULT_PATH, ensure_database

ROW_LIMIT = 200
BAR_TO_PSI = 14.5037738
TABLES = frozenset(
    {
        "units",
        "assets",
        "sensor_tags",
        "sensor_readings",
        "pressure_readings_psi",
        "work_orders",
        "failure_events",
        "inspection_notes",
        "spare_parts",
    }
)


class RefineryDataSource(Protocol):
    def get_asset(self, asset_id: str) -> Asset: ...
    def get_sensor_trend(self, asset_id: str, days: int = 45) -> tuple[SensorTrend, ...]: ...
    def get_maintenance_history(self, asset_id: str) -> tuple[WorkOrder, ...]: ...
    def search_inspection_notes(
        self, asset_id: str, query: str = ""
    ) -> tuple[InspectionNote, ...]: ...
    def run_sql(self, query: str) -> QueryResult: ...


def _authorize(action: int, arg1: str | None, arg2: str | None, *_: object) -> int:
    if action == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ and arg1 in TABLES:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION and arg2 not in {
        "load_extension",
        "writefile",
        "readfile",
    }:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def _normalize_pressure(value: float, unit_of_measure: str) -> float:
    return value * BAR_TO_PSI if unit_of_measure == "bar" else value


def _normalized_pressure_tag(tag: dict[str, Any]) -> SensorTag:
    unit = tag["unit_of_measure"]
    if unit not in {"bar", "psi"}:
        return SensorTag.model_validate(tag)
    return SensorTag(
        **{
            **tag,
            "unit_of_measure": "psi",
            "alarm_low": _normalize_pressure(tag["alarm_low"], unit),
            "alarm_high": _normalize_pressure(tag["alarm_high"], unit),
            "source_unit_of_measure": unit,
            "source_alarm_low": tag["alarm_low"],
            "source_alarm_high": tag["alarm_high"],
        }
    )


class SqliteRefineryDataSource:
    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self.path = ensure_database(path)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    def _rows(self, sql: str, parameters: tuple[Any, ...] = ()) -> tuple[dict[str, Any], ...]:
        with self._connection() as db:
            return tuple(dict(row) for row in db.execute(sql, parameters))

    def get_asset(self, asset_id: str) -> Asset:
        rows = self._rows("SELECT * FROM assets WHERE asset_id = ?", (asset_id,))
        if not rows:
            raise ValueError(f"Unknown asset: {asset_id}")
        return Asset.model_validate(rows[0])

    def get_sensor_trend(self, asset_id: str, days: int = 45) -> tuple[SensorTrend, ...]:
        self.get_asset(asset_id)
        if not 1 <= days <= 45:
            raise ValueError("days must be between 1 and 45")
        tags = self._rows(
            "SELECT * FROM sensor_tags WHERE asset_id = ? ORDER BY tag_id", (asset_id,)
        )
        cutoff = (AS_OF - timedelta(days=days)).isoformat()
        return tuple(
            SensorTrend(
                tag=_normalized_pressure_tag(tag),
                points=tuple(
                    self._normalized_pressure_point(row, tag["unit_of_measure"])
                    for row in self._rows(
                        "SELECT substr(timestamp, 1, 10) AS timestamp, avg(value) AS value, "
                        "min(value) AS minimum, max(value) AS maximum, count(*) AS samples "
                        "FROM sensor_readings WHERE tag_id = ? AND timestamp > ? "
                        "GROUP BY substr(timestamp, 1, 10) ORDER BY timestamp",
                        (tag["tag_id"], cutoff),
                    )
                ),
            )
            for tag in tags
        )

    @staticmethod
    def _normalized_pressure_point(row: dict[str, Any], unit_of_measure: str) -> TrendPoint:
        point = TrendPoint.model_validate(row)
        if unit_of_measure not in {"bar", "psi"}:
            return point
        return TrendPoint(
            timestamp=point.timestamp,
            value=_normalize_pressure(point.value, unit_of_measure),
            minimum=_normalize_pressure(point.minimum, unit_of_measure),
            maximum=_normalize_pressure(point.maximum, unit_of_measure),
            samples=point.samples,
            source_value=point.value,
            source_minimum=point.minimum,
            source_maximum=point.maximum,
        )

    def get_maintenance_history(self, asset_id: str) -> tuple[WorkOrder, ...]:
        self.get_asset(asset_id)
        return tuple(
            WorkOrder.model_validate(row)
            for row in self._rows(
                "SELECT * FROM work_orders WHERE asset_id = ? "
                "ORDER BY opened_at DESC, work_order_id",
                (asset_id,),
            )
        )

    def search_inspection_notes(self, asset_id: str, query: str = "") -> tuple[InspectionNote, ...]:
        self.get_asset(asset_id)
        return tuple(
            InspectionNote.model_validate(row)
            for row in self._rows(
                "SELECT * FROM inspection_notes WHERE asset_id = ? "
                "AND instr(lower(note), lower(?)) > 0 "
                "ORDER BY inspected_at DESC, note_id",
                (asset_id, query),
            )
        )

    def run_sql(self, query: str) -> QueryResult:
        if not query.strip() or query.lstrip().split(maxsplit=1)[0].upper() != "SELECT":
            raise ValueError("Only SELECT statements are allowed")
        with self._connection() as db:
            db.set_authorizer(_authorize)
            steps = 0

            def budget() -> Literal[0, 1]:
                nonlocal steps
                steps += 1
                return 1 if steps > 2000 else 0

            db.set_progress_handler(budget, 1000)
            try:
                cursor = db.execute(query)
                rows = tuple(dict(row) for row in cursor.fetchmany(ROW_LIMIT + 1))
                return QueryResult(
                    columns=tuple(col[0] for col in cursor.description),
                    rows=rows[:ROW_LIMIT],
                    truncated=len(rows) > ROW_LIMIT,
                    row_limit=ROW_LIMIT,
                )
            except sqlite3.Error as exc:
                raise ValueError(f"Query rejected: {exc}") from exc
