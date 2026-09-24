from deepagents import CompiledSubAgent
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel

from middleware.prompt_variant import PRESSURE_GUIDANCE, DemoContext, demo_prompt_variant
from tools import RefineryTools

DATA_PROMPT = """You are the refinery data analyst. Use get_sensor_trend for trends and run_sql
for aggregates, failure events, spare parts and exact sensor questions. Data is synthetic,
frozen at 2026-09-23T12:00:00+00:00; do not use today's date in SQL.
Return concise evidence with tags, units, time ranges, numbers and queries used.
For a condition report, return ALL daily vibration points (timestamp, value, minimum,
maximum, samples), alarm limits, and native units, not just a narrative summary.
Check truncated; never treat a capped query as a full result. No invented readings.
Distinguish below alarm from healthy: a rising trend can justify inspection.
The lead agent owns recommendations, artifacts and work orders.
"""

MAINTENANCE_PROMPT = """You are the refinery maintenance planner. Fetch maintenance history and
inspection notes for the requested asset. Return work-order and note IDs, dates, statuses,
costs, hours and the relevant note text. A note saying 'replaced' is not proof: cross-check
the linked work order. A cancelled or open order does not establish completed maintenance.
Flag contradictions explicitly. Do not invent repairs, parts or root causes.
You cannot access the SQL fixture's failure_events table. For failure events, root causes,
downtime hours or spare parts, tell the lead to ask data-analyst; do not return a numeric
count as unavailable or zero.
Return full records needed for a condition report, not just a summary. The lead agent
drafts work orders only after human approval. All data is synthetic as of 2026-09-23.
"""


def build_subagents(tools: RefineryTools, model: BaseChatModel) -> list[CompiledSubAgent]:
    return [
        CompiledSubAgent(
            name="data-analyst",
            description="Analyzes sensor trends, failures and spares. Give asset tag.",
            # Do not inherit the managed checkpointer: resumed runs cannot serialize ReplayState.
            runnable=create_agent(
                model,
                tools=[tools.get_sensor_trend, tools.run_sql],
                system_prompt=DATA_PROMPT + PRESSURE_GUIDANCE,
                middleware=[demo_prompt_variant],
                context_schema=DemoContext,
                name="data-analyst",
                checkpointer=False,
            ),
        ),
        CompiledSubAgent(
            name="maintenance-planner",
            description="Handles only work orders and inspection notes. Give asset tag.",
            runnable=create_agent(
                model,
                tools=[tools.get_maintenance_history, tools.search_inspection_notes],
                system_prompt=MAINTENANCE_PROMPT,
                name="maintenance-planner",
                checkpointer=False,
            ),
        ),
    ]
