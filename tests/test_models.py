import pytest

import models


def test_gateway_model_openai_spec_sets_retention(monkeypatch):
    models.gateway_model.cache_clear()
    seen = {}

    def fake_init(model, **kwargs):
        seen.update(model=model, **kwargs)
        return object()

    monkeypatch.setattr(models, "init_chat_model", fake_init)
    models.gateway_model("langsmith:openai/gpt-5.6-sol")
    assert seen["model"] == "langsmith:openai/gpt-5.6-sol"
    assert seen["store"] is False
    assert seen["api_key"] == "test-gateway-key"


def test_gateway_model_non_openai_spec_has_no_retention(monkeypatch):
    models.gateway_model.cache_clear()
    seen = {}
    monkeypatch.setattr(models, "init_chat_model", lambda m, **kw: seen.update(kw) or object())
    models.gateway_model("langsmith:anthropic/claude-sonnet-5")
    assert "store" not in seen


def test_gateway_model_rejects_bad_spec():
    with pytest.raises(ValueError, match="langsmith:provider/model"):
        models.gateway_model("gpt-5.6-sol")


def test_missing_gateway_key_is_an_error(monkeypatch):
    models.gateway_model.cache_clear()
    monkeypatch.setenv("LANGSMITH_GATEWAY_API_KEY", "")
    with pytest.raises(RuntimeError, match="LC_GATEWAY_KEY"):
        models.gateway_model("langsmith:openai/gpt-5.6-sol")


def test_agent_model_reads_env(monkeypatch):
    models.gateway_model.cache_clear()
    monkeypatch.setenv("AGENT_MODEL", "langsmith:openai/gpt-5.6-sol")
    monkeypatch.setattr(models, "init_chat_model", lambda m, **kw: m)
    assert models.agent_model() == "langsmith:openai/gpt-5.6-sol"
