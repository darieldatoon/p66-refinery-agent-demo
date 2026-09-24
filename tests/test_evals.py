import pytest

from evals.dataset import build_examples
from evals.evaluators import answer_object, final_text, numeric_accuracy, unit_accuracy
from refinery_data.source import SqliteRefineryDataSource


def test_dataset_references_cover_storylines_and_conversion():
    examples = build_examples(SqliteRefineryDataSource())
    assert len(examples) == 30
    assert len({e["metadata"]["case_id"] for e in examples}) == 30
    assert {e["inputs"]["asset"] for e in examples} == {
        "P-101A",
        "E-205",
        "C-301",
        "K-401",
        "P-102B",
    }
    pressure = examples[18]["outputs"]
    assert pressure["unit"] == "psi"
    assert pressure["value"] == pytest.approx(8.5113 * 14.5037738)
    assert examples[24]["outputs"]["value"] == 0


def test_evaluator_scores_value_not_incidental_number():
    reference = {"value": 123.44596994394, "unit": "psi"}
    assert numeric_accuracy({"answer": '{"value":123.45,"unit":"psi"}'}, reference)["score"]
    assert not numeric_accuracy(
        {"answer": '{"value":8.5113,"unit":"psi","explanation":"123.45"}'}, reference
    )["score"]
    assert not numeric_accuracy({"answer": '{"value":true}'}, reference)["score"]
    assert not numeric_accuracy({"answer": '{"value":NaN}'}, reference)["score"]
    assert not numeric_accuracy({"answer": '{"value":0.01}'}, {"value": 0, "unit": "orders"})[
        "score"
    ]
    assert not unit_accuracy({"answer": '{"value":123.45,"unit":"bar"}'}, reference)
    assert answer_object({"answer": '```json\n{"value": 1}\n```'}) == {"value": 1}
    assert answer_object({"answer": "[]"}) == {}
    assert answer_object({"answer": "not json"}) == {}


def test_final_answer_skips_reasoning_and_tool_calls():
    messages = [
        {
            "type": "ai",
            "content": [
                {"type": "reasoning", "encrypted_content": "opaque"},
                {"type": "text", "text": "answer"},
            ],
        },
        {"type": "ai", "content": "working", "tool_calls": [{"name": "run_sql"}]},
    ]
    assert final_text(messages) == "answer"
    assert final_text([]) == ""


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        ("hourly samples", "samples"),
        ("seal failures", "failures"),
        ("hours", "hours"),
        ("unspecified currency", "unspecified"),
    ],
)
def test_equivalent_count_unit_labels(actual, expected):
    import json

    assert unit_accuracy({"answer": json.dumps({"unit": actual})}, {"unit": expected})
