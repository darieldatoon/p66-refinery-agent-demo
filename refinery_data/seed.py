import os
import random
import sqlite3
import tempfile
import zlib
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

from refinery_data.fixture import (
    HERO_ASSETS,
    HERO_FAILURES,
    HERO_NOTES,
    HERO_ORDERS,
    HERO_PARTS,
    ROUTINE_NOTES,
    ROUTINE_ORDERS,
    ROUTINE_PARTS,
    SUPPORTING_ASSETS,
    AssetRow,
    OrderRow,
)

AS_OF = datetime(2026, 9, 23, 12, tzinfo=UTC)
DAYS = 45
SEED = 66
# The cached database is rebuilt whenever the code that generates it changes.
FIXTURE_VERSION = (
    zlib.crc32(
        b"".join(Path(__file__).with_name(name).read_bytes() for name in ("seed.py", "fixture.py"))
    )
    & 0x7FFFFFFF
)
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


TagSpec = tuple[str, str, str, float, float, float]
TagRow = tuple[str, str, str, str, float, float]

# Standby, or given a specific shape in _reading; baselines are only defaults.
TAG_OVERRIDES: dict[str, tuple[TagSpec, ...]] = {
    "P-101A": (
        ("VIB", "vibration", "mm/s RMS", 0, 4.5, 1.8),
        ("TEMP", "bearing_temperature", "degC", 0, 85, 61),
        ("PT", "discharge_pressure", "psi", 200, 320, 265),
    ),
    "E-205": (
        ("DP", "differential_pressure", "psi", 0, 25, 8),
        ("DUTY", "heat_duty", "MW", 7, 15, 12),
        ("TEMP", "outlet_temperature", "degC", 0, 180, 65),
    ),
    "C-301": (
        ("VIB", "vibration", "mm/s RMS", 0, 7.1, 2.3),
        ("SEAL-DP", "seal_flush_differential_pressure", "psi", 20, 60, 35),
        ("PT", "discharge_pressure", "psi", 800, 1050, 920),
    ),
    "K-401": (
        ("PT-1", "pressure", "psi", 0, 150, 120),
        ("PT-2", "pressure", "psi", 0, 150, 120),
        ("PT-3", "pressure", "bar", 0, 10.34213594, 8.5),
    ),
    "P-102B": (
        ("VIB", "vibration", "mm/s RMS", 0, 4.5, 1.6),
        ("TEMP", "bearing_temperature", "degC", 0, 85, 58),
        ("PT", "discharge_pressure", "psi", 60, 180, 110),
    ),
    "P-101B": (
        ("VIB", "vibration", "mm/s RMS", 0, 4.5, 0.3),
        ("TEMP", "bearing_temperature", "degC", 0, 85, 31),
        ("PT", "discharge_pressure", "psi", 0, 320, 12),
    ),
}
AUTHORED_HISTORY = frozenset({"P-101A", "P-101B", "E-205", "C-301", "K-401", "P-102B"})
FAILURE_TIMES = tuple(datetime.fromisoformat(row[2]) for row in HERO_FAILURES[:3])
REPAIR_HOURS = tuple(row[5] for row in HERO_FAILURES[:3])


def asset_rows() -> list[AssetRow]:
    return [*HERO_ASSETS, *SUPPORTING_ASSETS]


def _default_specs(equipment_type: str, index: int) -> tuple[TagSpec, ...]:
    if equipment_type == "pump":
        pressure = (150, 180, 240, 310, 120)[index % 5]
        return (
            ("VIB", "vibration", "mm/s RMS", 0, 4.5, 1.3 + 0.2 * (index % 5)),
            ("TEMP", "bearing_temperature", "degC", 0, 85, 52 + 2 * (index % 6)),
            ("PT", "discharge_pressure", "psi", pressure * 0.6, pressure * 1.25, pressure),
        )
    if equipment_type == "compressor":
        pressure = (60, 45, 920, 1450)[index % 4]
        return (
            ("VIB", "vibration", "mm/s RMS", 0, 7.1, 2.0 + 0.2 * (index % 4)),
            ("TEMP", "discharge_temperature", "degC", 0, 160, 115 + 5 * (index % 4)),
            ("PT", "discharge_pressure", "psi", pressure * 0.8, pressure * 1.15, pressure),
        )
    if equipment_type == "exchanger":
        duty = (4, 9, 14, 6, 11)[index % 5]
        outlet = (45, 120, 180, 240, 90)[index % 5]
        return (
            ("DP", "differential_pressure", "psi", 0, 25, 6 + index % 5),
            ("DUTY", "heat_duty", "MW", duty * 0.7, duty * 1.3, duty),
            ("TEMP", "outlet_temperature", "degC", 0, outlet * 1.3, outlet),
        )
    top = (120, 95, 65, 140)[index % 4]
    pressure = (18, 24, 160, 120)[index % 4]
    return (
        ("DP", "tray_differential_pressure", "psi", 0, 8, 2.5 + 0.4 * (index % 4)),
        ("TEMP", "top_temperature", "degC", 0, top * 1.25, top),
        ("PT", "overhead_pressure", "psi", pressure * 0.7, pressure * 1.3, pressure),
    )


def tag_specs(asset: AssetRow, index: int) -> tuple[TagSpec, ...]:
    return TAG_OVERRIDES.get(asset[0]) or _default_specs(asset[3], index)


def tag_rows(asset: AssetRow, index: int) -> list[TagRow]:
    return [
        (f"{asset[0]}-{suffix}", asset[0], measurement, unit, low, high)
        for suffix, measurement, unit, low, high, _ in tag_specs(asset, index)
    ]


def _ramp(hour: int) -> float:
    return max(0, (hour - 24 * 24) / (21 * 24 - 1))


def _seal_flush(moment: datetime) -> float:
    for failed, repair in zip(FAILURE_TIMES, REPAIR_HOURS, strict=True):
        hours_before = (failed - moment).total_seconds() / 3600
        if 0 < hours_before <= 96:
            return 21 + 14 * hours_before / 96
        if 0 <= -hours_before < repair:
            return 0
    # The strainer was not replaced after F-003, so the next decline has started.
    since = (moment - FAILURE_TIMES[-1]).total_seconds() / 3600 - REPAIR_HOURS[-1]
    return 35 - max(0, since - 24) * 0.05 if since > 0 else 35


def _reading(tag_id: str, baseline: float, hour: int, noise: float) -> float:
    if tag_id == "P-101A-VIB":
        return 1.8 + _ramp(hour) * 2.2 + noise * 0.025
    if tag_id == "P-101A-TEMP":
        return 61 + _ramp(hour) * 6 + noise * 0.3
    if tag_id == "E-205-DP":
        return 8 + 13 * hour / (DAYS * 24 - 1) + noise * 0.1
    if tag_id == "E-205-DUTY":
        return 12 - 4 * hour / (DAYS * 24 - 1) + noise * 0.02
    if tag_id == "K-401-PT-3":
        return 8.5 + noise * 0.015
    if tag_id == "C-301-SEAL-DP":
        moment = AS_OF - timedelta(hours=DAYS * 24 - 1 - hour)
        return max(0, _seal_flush(moment) + noise * 0.3)
    return baseline + noise * baseline * 0.01


def _routine_orders(assets: list[AssetRow]) -> list[OrderRow]:
    orders: list[OrderRow] = []
    background = [asset for asset in assets if asset[0] not in AUTHORED_HISTORY]
    for index, (asset_id, _, _, equipment_type, _) in enumerate(background):
        templates = ROUTINE_ORDERS[equipment_type]
        picks = (
            templates[index % 3],
            templates[(index + 1) % 3],
            templates[3 if index % 4 == 0 else (index + 2) % 3],
        )
        for age, (work_type, description, cost, hours) in enumerate(picks):
            opened = AS_OF - timedelta(days=12 + (index * 23) % 70 + age * 97, hours=4)
            is_open = age == 0 and index % 6 == 0
            orders.append(
                (
                    f"WO-{100 + len(orders):04}",
                    asset_id,
                    opened.isoformat(),
                    None if is_open else (opened + timedelta(hours=hours)).isoformat(),
                    work_type,
                    "open" if is_open else "completed",
                    description.split(";")[0] if is_open else description,
                    0.0 if is_open else cost,
                    0.0 if is_open else hours,
                )
            )
    return orders


def seed_database(path: Path) -> None:
    rng = random.Random(SEED)
    assets = asset_rows()
    specs = {
        f"{asset[0]}-{spec[0]}": spec[5]
        for index, asset in enumerate(assets)
        for spec in tag_specs(asset, index)
    }
    tags = [tag for index, asset in enumerate(assets) for tag in tag_rows(asset, index)]
    background = [asset for asset in assets if asset[0] not in AUTHORED_HISTORY]
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
                    round(_reading(tag[0], specs[tag[0]], hour, rng.uniform(-1, 1)), 5),
                )
                for tag in tags
                for hour in range(DAYS * 24)
            ),
        )
        db.executemany(
            "INSERT INTO work_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [*HERO_ORDERS, *_routine_orders(assets)],
        )
        db.executemany("INSERT INTO failure_events VALUES (?, ?, ?, ?, ?, ?)", HERO_FAILURES)
        notes = [
            (
                f"N-{100 + index:03}",
                asset_id,
                (AS_OF - timedelta(days=1 + index % 9, hours=index % 7)).isoformat(),
                None,
                ROUTINE_NOTES[equipment_type],
            )
            for index, (asset_id, _, _, equipment_type, _) in enumerate(background)
        ]
        db.executemany("INSERT INTO inspection_notes VALUES (?, ?, ?, ?, ?)", [*HERO_NOTES, *notes])
        parts = [
            (f"SP-{100 + index:03}", asset_id, ROUTINE_PARTS[equipment_type], 1 + index % 4, 1)
            for index, (asset_id, _, _, equipment_type, _) in enumerate(background)
        ]
        db.executemany("INSERT INTO spare_parts VALUES (?, ?, ?, ?, ?)", [*HERO_PARTS, *parts])
        db.execute(f"PRAGMA user_version = {FIXTURE_VERSION}")


def ensure_database(path: Path = DEFAULT_PATH) -> Path:
    if path.exists():
        with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as db:
            current = db.execute("PRAGMA user_version").fetchone()[0] == FIXTURE_VERSION
        if current:
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
