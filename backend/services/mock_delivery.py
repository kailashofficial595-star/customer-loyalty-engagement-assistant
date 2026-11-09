import uuid
from datetime import datetime
from typing import Dict, Any, Tuple
from ..models.generation import MessageDraft
from ..models.audit import DeliveryReceipt
from .audit_service import AuditService


class MockDeliveryService:
    """
    Controlled mock delivery service.
    Enforces FR-10 (Controlled delivery): Blocks sending when required evidence, eligibility,
    approval or safety checks fail.
    """

    def __init__(self, audit_service: AuditService):
        self.audit_service = audit_service
        self.delivered_receipts: Dict[str, DeliveryReceipt] = {}

    def deliver_draft(self, draft: MessageDraft) -> Tuple[bool, str, DeliveryReceipt | None]:
        # 1. GATE 1: Must be Human Approved
        if draft.status != "APPROVED":
            error_msg = f"DELIVERY_REFUSED: Draft {draft.draft_id} cannot be delivered because it has not received human supervisor approval (current status: {draft.status})."
            return False, error_msg, None

        # 2. GATE 2: Safety & Guardrail Critical Failures
        if not draft.validation.can_deliver or draft.validation.critical_count > 0:
            error_msg = f"DELIVERY_REFUSED: Critical guardrail failure prevents transmission ({draft.validation.summary_verdict})."
            return False, error_msg, None

        # 3. Simulate Successful Dispatch
        delivery_id = f"DLV-{uuid.uuid4().hex[:10].upper()}"
        receipt = DeliveryReceipt(
            delivery_id=delivery_id,
            draft_id=draft.draft_id,
            recipient_email=draft.recipient_email,
            subject=draft.subject,
            dispatched_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status="DELIVERED",
            message_size_bytes=len(draft.body_text.encode("utf-8")),
            tracking_id=f"TRK-{uuid.uuid4().hex[:12].upper()}"
        )

        draft.status = "DELIVERED"
        self.delivered_receipts[draft.draft_id] = receipt
        self.audit_service.record_delivery(draft.draft_id, "DELIVERED")

        return True, f"Mock email dispatched successfully to {draft.recipient_email} (Tracking: {receipt.tracking_id}).", receipt
