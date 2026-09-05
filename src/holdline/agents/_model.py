"""Shared builder for the text (non-voice) agents: Planner, Scribe, Supervisor.

All three are ordinary Strands `Agent`s on Amazon Bedrock. Keep construction in
one place so the model target is set once (`TEXT_MODEL_ID`).
"""

from __future__ import annotations

from typing import Any

from holdline.config import get_settings


def text_model() -> Any:
    from strands.models import BedrockModel

    s = get_settings()
    return BedrockModel(model_id=s.text_model_id, region_name=s.aws_region)


def text_agent(system_prompt: str, *, tools: list[Any] | None = None) -> Any:
    from strands import Agent

    return Agent(model=text_model(), system_prompt=system_prompt, tools=tools or [])


__all__ = ["text_agent", "text_model"]
