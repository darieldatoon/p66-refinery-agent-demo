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


@dynamic_prompt
def demo_prompt_variant(request: ModelRequest[Any]) -> str:
    context = request.runtime.context or DemoContext()
    prompt = request.system_message.text if request.system_message else ""
    if context.prompt_variant == "v2-prompt-cleanup":
        return prompt.replace(PRESSURE_GUIDANCE, "").replace(LEAD_PRESSURE_GUIDANCE, "")
    return prompt
