"""Refinery Reliability Agent. Tools and subagents are added in the build phase."""

from managed_deepagents import define_deep_agent

from models import agent_model

agent = define_deep_agent(
    name="refinery-reliability-agent",
    model=agent_model(),
    tools=[],
    metadata={"demo": "p66-refinery", "domain": "refinery-reliability"},
)
