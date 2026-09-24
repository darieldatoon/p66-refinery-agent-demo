from typing import Any, NotRequired

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langgraph.runtime import Runtime

from middleware.prompt_variant import DemoContext
from refinery_data.repository import IssueRepository
from refinery_data.source import RefineryDataSource


class WorkspaceState(AgentState):
    workspace: NotRequired[dict[str, Any]]


class WorkspaceMiddleware(AgentMiddleware[Any, Any]):
    state_schema = WorkspaceState

    def __init__(self, source: RefineryDataSource) -> None:
        self.source = source

    @hook_config(can_jump_to=["end"])
    async def abefore_agent(
        self, state: WorkspaceState, runtime: Runtime[DemoContext]
    ) -> dict[str, Any] | None:
        context = runtime.context or DemoContext()
        if context.operation not in {"snapshot", "workspace"}:
            return None
        if runtime.store is None:
            raise RuntimeError("The managed Store is required for the refinery workspace")
        return {
            "workspace": await IssueRepository(runtime.store).workspace(
                self.source, context.asset_id
            ),
            "jump_to": "end",
        }
