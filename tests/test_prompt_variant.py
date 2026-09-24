from pathlib import Path
from unittest.mock import Mock

import pytest
from langchain.agents.middleware import ModelRequest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.runtime import Runtime

from middleware.prompt_variant import (
    LEAD_PRESSURE_GUIDANCE,
    PRESSURE_GUIDANCE,
    DemoContext,
    demo_prompt_variant,
)


@pytest.mark.parametrize(
    "context",
    [
        None,
        DemoContext(),
        DemoContext("v2-prompt-cleanup"),
    ],
)
def test_variant_preserves_unit_guidance(context):
    prompt = Path("instructions.md").read_text() + PRESSURE_GUIDANCE
    assert LEAD_PRESSURE_GUIDANCE in prompt
    model = FakeMessagesListChatModel(responses=[AIMessage(content="done")])
    request = ModelRequest(
        model=model,
        messages=[],
        system_message=SystemMessage(prompt),
        runtime=Runtime(context=context),
    )
    handler = Mock()
    demo_prompt_variant.wrap_model_call(request, handler)
    rewritten = handler.call_args.args[0].system_message.text
    assert PRESSURE_GUIDANCE in rewritten
    assert LEAD_PRESSURE_GUIDANCE in rewritten
    assert rewritten == prompt


def test_unknown_prompt_variant_is_rejected():
    with pytest.raises(ValueError, match="Unsupported prompt variant"):
        DemoContext("v2-faulty-unit-assumption")


def test_variant_without_system_prompt():
    model = FakeMessagesListChatModel(responses=[AIMessage(content="done")])
    request = ModelRequest(model=model, messages=[], runtime=Runtime(context=None))
    handler = Mock()
    demo_prompt_variant.wrap_model_call(request, handler)
    assert handler.call_args.args[0].system_message.text == ""
