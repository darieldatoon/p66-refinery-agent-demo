import os
import random
import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

AS_OF = datetime(2026, 9, 23, 12, tzinfo=UTC)
DAYS = 45
SEED = 66
SCHEMA_VERSION = 1
DEFAULT_PATH = Path(__file__).with_name("refinery.db")

SCHEMA = """
CREATE TABLE units (unit_id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE assets (
    asset_id TEXT PRIMARY KEY, unit_id TEXT REFERENCES units, name TEXT NOT NULL,
    equipment_type TEXT NOT NULL, criticality TEXT NOT NULL);
CREATE TABLE sensor_tags (
    tag_id TEXT PRIMARY KEY, asset_id TEXT REFERENCES assets, measurement TEXT NOT NULL,
    unit_of_measure TEXT NOT NULL, alarm_low REAL NOT NULL, alarm_high REAL NOT NULL);
CREATE TABLE sensor_readings (
    tag_id TEXT REFERENCES sensor_tags, timestamp TEXT NOT NULL, value REAL NOT NULL,
    PRIMARY KEY(tag_id, timestamp));
CREATE TABLE work_orders (
    work_order_id TEXT PRIMARY KEY, asset_id TEXT REFERENCES assets, opened_at TEXT NOT NULL,
    completed_at TEXT, work_type TEXT NOT NULL, status TEXT NOT NULL,
    description TEXT NOT NULL, cost REAL NOT NULL, hours REAL NOT NULL);
CREATE TABLE failure_events (
    failure_id TEXT PRIMARY KEY, asset_id TEXT REFERENCES assets, occurred_at TEXT NOT NULL,
    failure_mode TEXT NOT NULL, root_cause TEXT NOT NULL, downtime_hours REAL NOT NULL);
CREATE TABLE inspection_notes (
    note_id TEXT PRIMARY KEY, asset_id TEXT REFERENCES assets, inspected_at TEXT NOT NULL,
    work_order_id TEXT REFERENCES work_orders, note TEXT NOT NULL);
CREATE TABLE spare_parts (
    part_id TEXT PRIMARY KEY, asset_id TEXT REFERENCES assets, description TEXT NOT NULL,
    stock_on_hand INTEGER NOT NULL, reorder_point INTEGER NOT NULL);
CREATE INDEX work_orders_asset ON work_orders(asset_id, opened_at);
CREATE INDEX notes_asset ON inspection_notes(asset_id, inspected_at);
"""


def timestamp(days_ago: int) -> str:
    return (AS_OF - timedelta(days=days_ago)).isoformat()


def asset_rows() -> list[tuple[str, str, str, str, str]]:
    heroes = [
        ("P-101A", "CDU", "Crude charge pump A", "pump", "A"),
        ("E-205", "FCC", "Feed preheat exchanger", "exchanger", "B"),
        ("C-301", "HDT", "Recycle compressor", "compressor", "A"),
        ("K-401", "FCC", "Wet gas compressor", "compressor", "A"),
        ("P-102B", "CDU", "Reflux pump B", "pump", "B"),
    ]
    kinds = (("P", "pump"), ("K", "compressor"), ("E", "exchanger"), ("T", "column"))
    return heroes + [
        (
            f"{kinds[i % 4][0]}-{500 + i}",
            ("CDU", "FCC", "HDT")[i % 3],
            f"{kinds[i % 4][1].title()} {500 + i}",
            kinds[i % 4][1],
            ("A", "B", "C")[i % 3],
        )
        for i in range(35)
    ]


def tag_rows(asset_id: str) -> list[tuple[str, str, str, str, float, float]]:
    if asset_id == "K-401":
        specs = [
            ("PT-1", "pressure", "psi", 0, 150),
            ("PT-2", "pressure", "psi", 0, 150),
            ("PT-3", "pressure", "bar", 0, 10.34213594),
        ]
    elif asset_id == "E-205":
        specs = [
            ("DP", "differential_pressure", "psi", 0, 25),
            ("DUTY", "heat_duty", "MW", 7, 15),
            ("TEMP", "temperature", "degC", 0, 180),
        ]
    else:
        specs = [
            ("VIB", "vibration", "mm/s RMS", 0, 4.5),
            ("TEMP", "temperature", "degC", 0, 100),
            ("PT", "pressure", "psi", 0, 150),
        ]
    return [
        (f"{asset_id}-{suffix}", asset_id, measurement, unit, low, high)
        for suffix, measurement, unit, low, high in specs
    ]


def _reading(tag: tuple[str, str, str, str, float, float], hour: int, noise: float) -> float:
    tag_id, _, measurement, unit, _, _ = tag
    progress = hour / (DAYS * 24 - 1)
    if tag_id == "P-101A-VIB":
        return 1.8 + max(0, (hour - 24 * 24) / (21 * 24 - 1)) * 2.2 + noise * 0.025
    if tag_id == "E-205-DP":
        return 8 + 13 * progress + noise * 0.1
    if tag_id == "E-205-DUTY":
        return 12 - 4 * progress + noise * 0.02
    if unit == "bar":
        return 8.5 + noise * 0.015
    baseline = {"vibration": 1.6, "temperature": 65, "pressure": 120}[measurement]
    return baseline + noise * baseline * 0.01


def seed_database(path: Path) -> None:
    rng = random.Random(SEED)
    assets = asset_rows()
    tags = [tag for asset in assets for tag in tag_rows(asset[0])]
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(SCHEMA)
        db.executemany(
            "INSERT INTO units VALUES (?, ?)",
            [
                ("CDU", "Crude distillation"),
                ("FCC", "Fluid catalytic cracking"),
                ("HDT", "Hydrotreater"),
            ],
        )
        db.executemany("INSERT INTO assets VALUES (?, ?, ?, ?, ?)", assets)
        db.executemany("INSERT INTO sensor_tags VALUES (?, ?, ?, ?, ?, ?)", tags)
        db.executemany(
            "INSERT INTO sensor_readings VALUES (?, ?, ?)",
            (
                (
                    tag[0],
                    (AS_OF - timedelta(hours=DAYS * 24 - 1 - hour)).isoformat(),
                    round(_reading(tag, hour, rng.uniform(-1, 1)), 5),
                )
                for tag in tags
                for hour in range(DAYS * 24)
            ),
        )
        orders = [
            (
                f"WO-{i + 1:04}",
                assets[i % 40][0],
                timestamp(44 - i % 40),
                timestamp(43 - i % 40) if i % 5 else None,
                ("PM", "CM", "EM")[i % 3],
                "completed" if i % 5 else "open",
                "Routine inspection and lubrication",
                float(300 + i * 7),
                float(1 + i % 8),
            )
            for i in range(300)
        ]
        orders[0] = (
            "WO-0001",
            "P-101A",
            timestamp(30),
            timestamp(29),
            "PM",
            "completed",
            "Bearing lubrication; no bearing replacement",
            450.0,
            2.0,
        )
        orders[4] = (
            "WO-0005",
            "P-102B",
            timestamp(9),
            None,
            "CM",
            "cancelled",
            "Replace mechanical seal; cancelled awaiting part",
            0.0,
            0.0,
        )
        db.executemany("INSERT INTO work_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", orders)
        failures = [
            (
                f"F-{i + 1:03}",
                "C-301" if i < 3 else assets[5 + i % 35][0],
                timestamp((38, 22, 6)[i] if i < 3 else 44 - i),
                "seal failure" if i < 3 else "bearing wear",
                "flush line contamination" if i < 3 else "lubrication deficiency",
                float(8 + i % 4),
            )
            for i in range(20)
        ]
        db.executemany("INSERT INTO failure_events VALUES (?, ?, ?, ?, ?, ?)", failures)
        notes = [
            (
                f"N-{i + 1:03}",
                assets[i % 40][0],
                timestamp(i % 40),
                None,
                "Routine visual inspection. No leaks observed.",
            )
            for i in range(120)
        ]
        notes[0] = (
            "N-001",
            "P-101A",
            timestamp(1),
            "WO-0001",
            "Bearing housing noise rising. Recommend bearing inspection before weekend.",
        )
        notes[1] = (
            "N-002",
            "E-205",
            timestamp(1),
            None,
            "Higher differential pressure and lower heat duty suggest fouling; verify flows.",
        )
        notes[2] = (
            "N-003",
            "C-301",
            timestamp(5),
            None,
            "Three seal failures; repeated flush line contamination. Inspect flush system.",
        )
        notes[4] = (
            "N-005",
            "P-102B",
            timestamp(8),
            "WO-0005",
            "Mechanical seal replaced. Shift handover note; verify against work order.",
        )
        db.executemany("INSERT INTO inspection_notes VALUES (?, ?, ?, ?, ?)", notes)
        db.executemany(
            "INSERT INTO spare_parts VALUES (?, ?, ?, ?, ?)",
            (
                (
                    f"SP-{i + 1:03}",
                    assets[i % 40][0],
                    "Bearing kit" if i % 2 == 0 else "Seal kit",
                    i % 7,
                    2,
                )
                for i in range(50)
            ),
        )
        db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def ensure_database(path: Path = DEFAULT_PATH) -> Path:
    if path.exists():
        with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as db:
            if db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                raise ValueError("Fixture schema changed; use a new database path or rebuild it")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=path.parent, suffix=".db")
    os.close(handle)
    temporary = Path(name)
    try:
        seed_database(temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path
