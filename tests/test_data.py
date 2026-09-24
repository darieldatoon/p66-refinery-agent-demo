import sqlite3

import pytest

from refinery_data.seed import ensure_database, seed_database
from refinery_data.source import ROW_LIMIT, SqliteRefineryDataSource


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    return SqliteRefineryDataSource(tmp_path_factory.mktemp("fixture") / "refinery.db")


def test_seed_counts_and_repeatability(source, tmp_path):
    other = tmp_path / "other.db"
    seed_database(other)
    assert source.path.read_bytes() == other.read_bytes()
    for table, count in {
        "units": 3,
        "assets": 40,
        "sensor_tags": 120,
        "sensor_readings": 129600,
        "work_orders": 300,
        "failure_events": 20,
        "inspection_notes": 120,
        "spare_parts": 50,
    }.items():
        assert source.run_sql(f"SELECT count(*) AS n FROM {table}").rows[0]["n"] == count
    assert ensure_database(source.path) == source.path
    with sqlite3.connect(other) as db:
        db.execute("PRAGMA user_version = 999")
    with pytest.raises(ValueError, match="schema changed"):
        ensure_database(other)


def test_atomic_seed_failure_cleans_up(tmp_path, monkeypatch):
    def fail(path):
        raise OSError("disk full")

    monkeypatch.setattr("refinery_data.seed.seed_database", fail)
    with pytest.raises(OSError, match="disk full"):
        ensure_database(tmp_path / "fail.db")
    assert not list(tmp_path.iterdir())


def test_hero_rises_for_three_weeks_but_never_alarms(source):
    assert source.get_asset("P-101A").unit_id == "CDU"
    trend = next(t for t in source.get_sensor_trend("P-101A") if t.tag.measurement == "vibration")
    assert sum(p.samples for p in trend.points) == 1080
    assert trend.points[-1].value - trend.points[-22].value > 2
    assert max(p.maximum for p in trend.points) < trend.tag.alarm_high == 4.5
    assert sum(p.samples for p in source.get_sensor_trend("P-101A", 1)[0].points) == 24


def test_other_storylines(source):
    trends = {t.tag.measurement: t for t in source.get_sensor_trend("E-205")}
    assert (
        trends["differential_pressure"].points[-1].value
        > trends["differential_pressure"].points[0].value
    )
    assert trends["heat_duty"].points[-1].value < trends["heat_duty"].points[0].value
    failures = source.run_sql("SELECT * FROM failure_events WHERE asset_id = 'C-301'").rows
    assert len(failures) == 3
    assert {f["root_cause"] for f in failures} == {"flush line contamination"}
    tags = source.get_sensor_trend("K-401")
    assert [t.tag.unit_of_measure for t in tags] == ["psi", "psi", "bar"]
    assert tags[2].points[-1].value * 14.5037738 > tags[0].points[-1].value
    note = source.search_inspection_notes("P-102B", "REPLACED")[0]
    order = next(
        w for w in source.get_maintenance_history("P-102B") if w.work_order_id == note.work_order_id
    )
    assert order.status == "cancelled"
    assert order.completed_at is None
    assert source.search_inspection_notes("P-102B", "%") == ()


@pytest.mark.parametrize(
    "method",
    ["get_asset", "get_sensor_trend", "get_maintenance_history", "search_inspection_notes"],
)
def test_unknown_asset(source, method):
    with pytest.raises(ValueError, match="Unknown asset"):
        getattr(source, method)("bogus")


@pytest.mark.parametrize("days", [0, 46])
def test_bad_window(source, days):
    with pytest.raises(ValueError, match="days"):
        source.get_sensor_trend("P-101A", days)


@pytest.mark.parametrize(
    "query",
    [
        "",
        "DELETE FROM assets",
        "PRAGMA table_info(assets)",
        "WITH x AS (SELECT 1) SELECT * FROM x",
        "SELECT * FROM sqlite_master",
        "SELECT load_extension('/tmp/x')",
        "SELECT 1; DELETE FROM assets",
        "SELECT * FROM missing",
        "SELECT count(*) FROM sensor_readings a, sensor_readings b",
    ],
)
def test_sql_boundary(source, query):
    with pytest.raises(ValueError, match=r"Only SELECT|Query rejected"):
        source.run_sql(query)
    assert source.get_asset("P-101A").asset_id == "P-101A"


def test_query_cap_and_aggregates(source):
    result = source.run_sql("SELECT * FROM sensor_readings")
    assert result.truncated
    assert len(result.rows) == ROW_LIMIT
    assert result.columns == ("tag_id", "timestamp", "value")
    assert not source.run_sql("select avg(value) AS mean FROM sensor_readings").truncated
