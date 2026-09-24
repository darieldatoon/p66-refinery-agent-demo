from dataclasses import dataclass
from typing import Any, Literal

from langchain.agents.middleware import ModelRequest, dynamic_prompt

PRESSURE_GUIDANCE = """Always inspect unit_of_measure before combining pressure readings.
Normalize bar to psi using 1 bar = 14.5037738 psi, including alarm limits.
Use native sensor units only when explicitly requested, and label every value.
"""
LEAD_PRESSURE_GUIDANCE = (
    "Preserve measurement units. Convert bar to psi (1 bar = 14.5037738 psi) before\n"
    "comparing or aggregating pressures."
)


@dataclass(frozen=True)
class DemoContext:
    prompt_variant: Literal["baseline", "v2-prompt-cleanup"] = "baseline"
    operation: Literal["chat", "workspace"] = "chat"
    issue_id: str | None = None
    asset_id: str | None = None


@dynamic_prompt
def demo_prompt_variant(request: ModelRequest[Any]) -> str:
    context = request.runtime.context or DemoContext()
    prompt = request.system_message.text if request.system_message else ""
    if context.prompt_variant == "v2-prompt-cleanup":
        return prompt.replace(PRESSURE_GUIDANCE, "").replace(LEAD_PRESSURE_GUIDANCE, "")
    if context.issue_id:
        return prompt + (
            f"\nCurrent workspace issue: {context.issue_id}. Fetch get_issue_evidence first. "
            "Save conclusions with record_issue_assessment. Use propose_issue_work for work "
            "on this issue; it pauses for review and persists both decisions. Do not use "
            "draft_work_order for issue work."
        )
    return prompt
