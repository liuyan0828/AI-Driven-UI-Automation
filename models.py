from typing import Literal, Optional
from pydantic import BaseModel, Field

class WebAction(BaseModel):
    """
    Schema for the AI Agent's decision-making process.
    This model enforces structured output for the LLM, ensuring that the reasoning is captured and the actions are type-safe.
    """
    # --- Reasoning Layer ---
    thought: str = Field(description="Internal reasoning: Why this action is chosen based on the goals.")
    # --- Action Selection Layer ---
    action_type: Literal["click", "type", "type_and_click", "scroll", "wait", "finish"] = Field(description="The next atomic action to perform.")
    # --- Parameter Layer ---
    x:Optional[int] = Field(None, description="The X coordinate for click actions.")
    y:Optional[int] = Field(None, description="The Y coordinate for click actions.")
    text:Optional[str] = Field(None, description="The text content for 'type' action.")
