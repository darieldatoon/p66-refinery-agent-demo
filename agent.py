from managed_deepagents import define_deep_agent

from middleware.artifact_links import ArtifactLinksMiddleware
from middleware.prompt_variant import DemoContext, demo_prompt_variant
from models import agent_model
from refinery_data.source import SqliteRefineryDataSource
from subagents import build_subagents
from tools import build_tools
from tools.artifacts import publish_artifact

model = agent_model()
tools = build_tools(SqliteRefineryDataSource())

agent = define_deep_agent(
    name="refinery-reliability-agent",
    model=model,
    tools=[tools.get_asset, tools.draft_work_order, publish_artifact],
    subagents=build_subagents(tools, model),
    middleware=[demo_prompt_variant, ArtifactLinksMiddleware()],
    context_schema=DemoContext,
    interrupt_on={"draft_work_order": True},
    metadata={"demo": "p66-refinery", "domain": "refinery-reliability"},
)
