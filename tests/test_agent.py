import importlib


def test_agent_module_exports_named_agent(monkeypatch):
    import models

    monkeypatch.setattr(models, "init_chat_model", lambda m, **kw: object())
    models.gateway_model.cache_clear()
    module = importlib.import_module("agent")
    assert module.agent is not None
