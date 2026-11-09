import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from ..models.audit import AuditEntry
from ..models.generation import MessageDraft
from ..models.customer import CustomerProfile


AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "audit_log.json")


def mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    parts = email.split("@")
    user, domain = parts[0], parts[1]
    masked_user = user[:2] + "***" if len(user) > 2 else "***"
    return f"{masked_user}@{domain}"


class AuditService:
    def __init__(self):
        self.log_file = AUDIT_LOG_FILE
        self.entries: List[AuditEntry] = []
        self._load_log()

    def _load_log(self):
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    self.entries = [AuditEntry(**item) for item in raw]
            except Exception:
                self.entries = []

    def _persist(self):
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        try:
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump([e.model_dump() for e in self.entries], f, indent=2)
        except Exception:
            pass

    def record_generation(self, draft: MessageDraft, profile: CustomerProfile) -> AuditEntry:
        audit_id = f"AUD-{uuid.uuid4().hex[:10].upper()}"
        entry = AuditEntry(
            audit_id=audit_id,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            draft_id=draft.draft_id,
            customer_id=profile.customer_id,
            customer_email_masked=mask_email(profile.email),
            primary_segment=draft.primary_segment,
            strategy_objective=draft.strategy_objective,
            model_version=draft.model_version,
            template_version=draft.template_version,
            evidence_fields={
                "tenure_months": profile.engagement.tenure_months,
                "plan_name": profile.engagement.current_plan_name,
                "monthly_spend": profile.engagement.monthly_spend,
                "days_overdue": profile.billing.days_overdue,
                "outstanding_balance": profile.billing.outstanding_balance,
                "loyalty_tier": profile.engagement.loyalty_tier,
                "email_opt_in": profile.communication.email_opt_in
            },
            guardrail_verdict=draft.validation.summary_verdict,
            guardrail_critical_count=draft.validation.critical_count,
            guardrail_warning_count=draft.validation.warning_count,
            reviewer_action=None,
            reviewer_id=None,
            send_status="GENERATED",
            delivery_timestamp=None,
            notes=None
        )
        self.entries.append(entry)
        self._persist()
        return entry

    def record_review_action(
        self, draft_id: str, reviewer_id: str, action: str, notes: Optional[str] = None
    ):
        for entry in self.entries:
            if entry.draft_id == draft_id:
                entry.reviewer_action = action
                entry.reviewer_id = reviewer_id
                entry.notes = notes
                if action == "APPROVE":
                    entry.send_status = "APPROVED_READY_FOR_DELIVERY"
                elif action == "REJECT":
                    entry.send_status = "REJECTED_BY_REVIEWER"
                elif action == "EDIT":
                    entry.send_status = "EDITED_PENDING_REVIEW"
                break
        self._persist()

    def record_delivery(self, draft_id: str, status: str = "DELIVERED"):
        for entry in self.entries:
            if entry.draft_id == draft_id:
                entry.send_status = status
                entry.delivery_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break
        self._persist()

    def get_entries(self, limit: int = 50) -> List[AuditEntry]:
        return sorted(self.entries, key=lambda x: x.timestamp, reverse=True)[:limit]

    def get_observability_metrics(self) -> Dict[str, Any]:
        total = len(self.entries)
        if total == 0:
            return {
                "total_drafts_processed": 0,
                "segment_breakdown": {},
                "guardrail_pass_rate_pct": 100.0,
                "reviewer_approval_rate_pct": 0.0,
                "delivered_count": 0,
                "blocked_refused_count": 0
            }

        segments: Dict[str, int] = {}
        pass_count = 0
        approvals = 0
        reviews = 0
        delivered = 0
        blocked = 0

        for e in self.entries:
            segments[e.primary_segment] = segments.get(e.primary_segment, 0) + 1
            if e.guardrail_critical_count == 0:
                pass_count += 1
            else:
                blocked += 1
            if e.reviewer_action:
                reviews += 1
                if e.reviewer_action == "APPROVE":
                    approvals += 1
            if e.send_status == "DELIVERED":
                delivered += 1

        return {
            "total_drafts_processed": total,
            "segment_breakdown": segments,
            "guardrail_pass_rate_pct": round((pass_count / total) * 100, 1),
            "reviewer_approval_rate_pct": round((approvals / reviews * 100), 1) if reviews > 0 else 0.0,
            "delivered_count": delivered,
            "blocked_refused_count": blocked,
            "human_reviews_logged": reviews
        }
