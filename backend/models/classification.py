from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ReasonCode(BaseModel):
    code: str = Field(..., description="Machine-readable rule reason code (e.g., OVERDUE_BALANCE_ACTIVE)")
    description: str = Field(..., description="Human-readable explanation of why this rule triggered")
    feature: str = Field(..., description="The underlying profile feature evaluated")
    observed_value: Any = Field(..., description="The observed value in customer context")
    threshold_value: Any = Field(..., description="The benchmark or threshold evaluated against")


class SegmentResult(BaseModel):
    primary_segment: str = Field(..., description="Primary assigned segment key")
    display_name: str = Field(..., description="Readable display name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence score")
    reason_codes: List[ReasonCode] = Field(default_factory=list, description="Interpretable classification reason codes")
    secondary_segments: List[str] = Field(default_factory=list, description="Co-occurring segments")
    explanation_summary: str = Field(..., description="Synthesized executive explanation for human reviewer")


class StrategySelection(BaseModel):
    objective: str = Field(..., description="Communication objective (e.g. VIP_REWARD_RECOGNITION)")
    tone: str = Field(..., description="Policy-approved tone archetype")
    reminder_stage: Optional[str] = Field(default=None, description="Billing progression stage if applicable")
    eligible_offer_id: Optional[str] = Field(default=None, description="Approved offer ID if eligible and appropriate")
    guidelines: str = Field(..., description="Policy tone and compliance instructions for generation")
    channel: str = Field(default="EMAIL", description="Target delivery channel")
