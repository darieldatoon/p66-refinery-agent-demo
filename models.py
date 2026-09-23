"""Model factory. Every model call goes through the LangSmith LLM Gateway.

LANGSMITH_GATEWAY_API_KEY authenticates model calls and is deliberately separate from
LANGSMITH_API_KEY, which authenticates tracing, deployment, and Context Hub. Do not
collapse them: the two keys belong to different LangSmith organizations.
"""

import os
from functools import lru_cache

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

REQUEST_TIMEOUT_SECONDS = 120
DEFAULT_AGENT_MODEL = "langsmith:openai/gpt-5.6-sol"
GATEWAY_PREFIX = "langsmith:"


def _gateway_key() -> str:
    key = os.environ.get("LANGSMITH_GATEWAY_API_KEY", "")
    if not key:
        msg = "LANGSMITH_GATEWAY_API_KEY is empty; export LC_GATEWAY_KEY before starting"
        raise RuntimeError(msg)
    return key


@lru_cache(maxsize=16)
def gateway_model(model: str) -> BaseChatModel:
    """Build a chat model for a `langsmith:{provider}/{model}` gateway spec."""
    if not model.startswith(GATEWAY_PREFIX) or "/" not in model:
        msg = f"model must be 'langsmith:provider/model', got {model!r}"
        raise ValueError(msg)
    # store=False plus encrypted reasoning is the deepagents-recommended Responses API
    # setting for no data retention on the OpenAI side. The gateway rejects `include`
    # for other providers, so gate it on openai/.
    openai_hosted = model.removeprefix(GATEWAY_PREFIX).startswith("openai/")
    retention = (
        {"store": False, "include": ["reasoning.encrypted_content"]} if openai_hosted else {}
    )
    return init_chat_model(
        model,
        api_key=_gateway_key(),
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=2,
        **retention,
    )


def agent_model() -> BaseChatModel:
    return gateway_model(os.environ.get("AGENT_MODEL", DEFAULT_AGENT_MODEL))
