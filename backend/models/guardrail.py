from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class GuardrailCheck(BaseModel):
    check_name: str = Field(..., description="Unique check identifier")
    category: str = Field(..., description="GROUNDEDNESS, SENSITIVE_DATA, POLICY_TONE, CONSENT, FREQUENCY, OFFER_ELIGIBILITY")
    passed: bool = Field(..., description="Whether the check passed")
    severity: str = Field(default="CRITICAL", description="CRITICAL, WARNING, INFO")
    message: str = Field(..., description="Human-readable result summary")
    detected_evidence: Optional[Dict[str, Any]] = Field(default=None, description="Matched patterns, unverified tokens or diffs")


class ValidationReport(BaseModel):
    is_safe: bool = Field(..., description="Overall safety verdict")
    can_deliver: bool = Field(..., description="True if no CRITICAL failure prevents delivery")
    critical_count: int = Field(default=0)
    warning_count: int = Field(default=0)
    checks: List[GuardrailCheck] = Field(default_factory=list)
    summary_verdict: str = Field(..., description="Concise reviewer alert summary")
