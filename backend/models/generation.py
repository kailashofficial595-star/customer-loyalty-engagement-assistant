from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from .guardrail import ValidationReport


class OfferSummary(BaseModel):
    offer_id: str
    name: str
    category: str
    value_description: str
    expiry_date: str
    terms: str


class GroundedFacts(BaseModel):
    customer_name: str
    plan_name: str
    tenure_months: int
    outstanding_balance: Optional[float] = None
    due_date: Optional[str] = None
    loyalty_tier: Optional[str] = None
    offer_id: Optional[str] = None
    offer_value: Optional[str] = None
    dispute_contact_included: bool = False
    disclaimer_included: bool = False


class ReviewFeedback(BaseModel):
    reviewer_id: str = Field(default="reviewer_operator_1")
    action: str = Field(..., description="APPROVE, REJECT, EDIT, REGENERATE")
    edited_subject: Optional[str] = None
    edited_body: Optional[str] = None
    rejection_reason: Optional[str] = None
    rating_relevance: Optional[int] = Field(default=5, ge=1, le=5)
    rating_clarity: Optional[int] = Field(default=5, ge=1, le=5)
    rating_tone: Optional[int] = Field(default=5, ge=1, le=5)
    rating_cta: Optional[int] = Field(default=5, ge=1, le=5)
    notes: Optional[str] = None


class MessageDraft(BaseModel):
    draft_id: str
    customer_id: str
    customer_name: str
    recipient_email: str
    primary_segment: str
    strategy_objective: str
    tone: str
    subject: str
    body_text: str
    grounded_facts: GroundedFacts
    offer: Optional[OfferSummary] = None
    validation: ValidationReport
    status: str = Field(default="PENDING_REVIEW", description="PENDING_REVIEW, APPROVED, REJECTED, DELIVERED, BLOCKED")
    model_version: str = Field(default="gemini-grounded-engine-v2.1")
    template_version: str = Field(default="telecom-policy-template-v1.4")
    created_at: str
    reviewer_feedback: Optional[ReviewFeedback] = None
