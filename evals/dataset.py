import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from refinery_data.source import RefineryDataSource, SqliteRefineryDataSource

DATASET_NAME = "refinery-operator-questions"
PSI_PER_BAR = 14.5037738
OUTPUT_INSTRUCTION = (
    " Return one JSON object with keys value (number), unit (string), "
    "explanation (string), evidence (array of IDs). No report or work order."
)


@dataclass(frozen=True)
class Case:
    case_id: str
    asset: str
    question: str
    query: str
    unit: str
    expected_explanation: str


def cases() -> tuple[Case, ...]:
    result: list[Case] = []

    def add(asset: str, question: str, query: str, unit: str, explanation: str) -> None:
        result.append(Case(f"case-{len(result) + 1:02}", asset, question, query, unit, explanation))

    vib = "FROM sensor_readings WHERE tag_id = 'P-101A-VIB'"
    for question, query, unit in [
        (
            "latest hourly vibration",
            f"SELECT value {vib} ORDER BY timestamp DESC LIMIT 1",
            "mm/s RMS",
        ),
        ("maximum hourly vibration over all 45 days", f"SELECT max(value) {vib}", "mm/s RMS"),
        ("mean hourly vibration over all 45 days", f"SELECT avg(value) {vib}", "mm/s RMS"),
        (
            "number of hourly vibration samples over all 45 days",
            f"SELECT count(*) {vib}",
            "samples",
        ),
        (
            "configured high vibration alarm",
            "SELECT alarm_high FROM sensor_tags WHERE tag_id='P-101A-VIB'",
            "mm/s RMS",
        ),
        (
            "number of hourly vibration samples at or above 4.5 mm/s RMS",
            f"SELECT count(*) {vib} AND value >= 4.5",
            "samples",
        ),
    ]:
        add(
            "P-101A",
            f"For P-101A, what is the {question}?",
            query,
            unit,
            "Vibration rises over the last three weeks but remains below the configured 4.5 alarm; inspection is warranted, not a confirmed bearing failure.",
        )

    for tag, measurement, unit in [
        ("DP", "differential pressure", "psi"),
        ("DUTY", "heat duty", "MW"),
    ]:
        for word, order in [("latest", "DESC"), ("earliest", "ASC")]:
            add(
                "E-205",
                f"What is the {word} hourly {measurement} for E-205 in the 45-day fixture?",
                f"SELECT value FROM sensor_readings WHERE tag_id='E-205-{tag}' ORDER BY timestamp {order} LIMIT 1",
                unit,
                "Rising differential pressure and falling heat duty suggest fouling; verify operating conditions.",
            )
        add(
            "E-205",
            f"What is the mean {measurement} for E-205 over all 45 days?",
            f"SELECT avg(value) FROM sensor_readings WHERE tag_id='E-205-{tag}'",
            unit,
            "These are synthetic observations, not proof of fouling.",
        )

    failures = "FROM failure_events WHERE asset_id='C-301'"
    for question, query, unit in [
        (
            "How many seal failures did C-301 have in the fixture?",
            f"SELECT count(*) {failures}",
            "failures",
        ),
        (
            "What total downtime did C-301 failures cause?",
            f"SELECT sum(downtime_hours) {failures}",
            "hours",
        ),
        (
            "What was mean downtime per C-301 failure?",
            f"SELECT avg(downtime_hours) {failures}",
            "hours",
        ),
        (
            "What was the longest C-301 failure downtime?",
            f"SELECT max(downtime_hours) {failures}",
            "hours",
        ),
        (
            "How many C-301 failures list flush line contamination as root cause?",
            f"SELECT count(*) {failures} AND root_cause='flush line contamination'",
            "failures",
        ),
        (
            "How many different root causes appear in C-301 failure records?",
            f"SELECT count(DISTINCT root_cause) {failures}",
            "causes",
        ),
    ]:
        add(
            "C-301",
            question,
            query,
            unit,
            "Three recorded seal failures share flush line contamination; investigate the flush system, not just repeated seal replacement.",
        )

    pressure = "FROM sensor_readings WHERE tag_id='K-401-PT-3'"
    for label, expr, suffix in [
        ("latest", "value", "ORDER BY timestamp DESC LIMIT 1"),
        ("mean over all 45 days", "avg(value)", ""),
        ("maximum over all 45 days", "max(value)", ""),
        ("minimum over all 45 days", "min(value)", ""),
    ]:
        add(
            "K-401",
            f"What is the {label} K-401-PT-3 pressure in psi?",
            f"SELECT {expr} * {PSI_PER_BAR} {pressure} {suffix}",
            "psi",
            "PT-3 is stored in bar and must be converted using 1 bar = 14.5037738 psi.",
        )
    add(
        "K-401",
        "What is the mean pressure across all three K-401 pressure tags over 45 days, in psi?",
        f"SELECT avg(r.value * CASE WHEN t.unit_of_measure='bar' THEN {PSI_PER_BAR} ELSE 1 END) FROM sensor_readings r JOIN sensor_tags t USING(tag_id) WHERE t.asset_id='K-401'",
        "psi",
        "Normalize each tag before averaging; one tag is bar and the other two are psi.",
    )
    add(
        "K-401",
        "How much greater is the latest K-401-PT-3 pressure than the latest K-401-PT-1 pressure, in psi?",
        f"SELECT (SELECT value*{PSI_PER_BAR} FROM sensor_readings WHERE tag_id='K-401-PT-3' ORDER BY timestamp DESC LIMIT 1) - (SELECT value FROM sensor_readings WHERE tag_id='K-401-PT-1' ORDER BY timestamp DESC LIMIT 1)",
        "psi",
        "PT-3 must be converted from bar before subtracting PT-1 in psi.",
    )

    for question, query, unit in [
        (
            "How many completed work orders support the P-102B seal replacement claimed by N-005?",
            "SELECT count(*) FROM work_orders WHERE work_order_id='WO-0005' AND status='completed'",
            "orders",
        ),
        (
            "How many cancelled orders are linked from note N-005 for P-102B?",
            "SELECT count(*) FROM work_orders WHERE work_order_id='WO-0005' AND status='cancelled'",
            "orders",
        ),
        (
            "What cost is recorded on P-102B work order WO-0005?",
            "SELECT cost FROM work_orders WHERE work_order_id='WO-0005'",
            "unspecified",
        ),
        (
            "What labor hours are recorded on P-102B work order WO-0005?",
            "SELECT hours FROM work_orders WHERE work_order_id='WO-0005'",
            "hours",
        ),
        (
            "How many P-102B inspection notes literally mention replaced?",
            "SELECT count(*) FROM inspection_notes WHERE asset_id='P-102B' AND instr(lower(note),'replaced')>0",
            "notes",
        ),
        (
            "How many work orders exist for P-102B, all statuses?",
            "SELECT count(*) FROM work_orders WHERE asset_id='P-102B'",
            "orders",
        ),
    ]:
        add(
            "P-102B",
            question,
            query,
            unit,
            "N-005 claims the seal was replaced but WO-0005 was cancelled, so replacement is unverified.",
        )
    return tuple(result)


def build_examples(source: RefineryDataSource) -> list[dict[str, Any]]:
    return [
        {
            "inputs": {
                "prompt": case.question + OUTPUT_INSTRUCTION,
                "asset": case.asset,
                "unit": source.get_asset(case.asset).unit_id,
                "requester_role": ("operator", "reliability_engineer", "supervisor")[i % 3],
            },
            "outputs": {
                "value": float(next(iter(source.run_sql(case.query).rows[0].values()))),
                "unit": case.unit,
                "explanation": case.expected_explanation,
            },
            "metadata": {"case_id": case.case_id, "reference_sql": case.query, "synthetic": True},
        }
        for i, case in enumerate(cases())
    ]


if __name__ == "__main__":
    path = Path(__file__).with_name("dataset.json")
    path.write_text(json.dumps(build_examples(SqliteRefineryDataSource()), indent=2) + "\n")
    print(f"Wrote {path}")
