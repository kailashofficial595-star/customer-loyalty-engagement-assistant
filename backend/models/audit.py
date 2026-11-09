from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class AuditEntry(BaseModel):
    audit_id: str
    timestamp: str
    draft_id: str
    customer_id: str
    customer_email_masked: str
    primary_segment: str
    strategy_objective: str
    model_version: str
    template_version: str
    evidence_fields: Dict[str, Any]
    guardrail_verdict: str
    guardrail_critical_count: int
    guardrail_warning_count: int
    reviewer_action: Optional[str] = None
    reviewer_id: Optional[str] = None
    send_status: str
    delivery_timestamp: Optional[str] = None
    notes: Optional[str] = None


class DeliveryReceipt(BaseModel):
    delivery_id: str
    draft_id: str
    recipient_email: str
    subject: str
    dispatched_at: str
    status: str = "DELIVERED"
    message_size_bytes: int
    tracking_id: str
