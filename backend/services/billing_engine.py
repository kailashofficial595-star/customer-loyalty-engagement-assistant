from typing import Dict, Any, Tuple
from ..models.customer import CustomerProfile


class BillingReminderEngine:
    """
    Configurable reminder progression based on verified billing status.
    Implements FR-06 (Billing-reminder controls).
    """

    SUPPORT_EMAIL = "billing-support@telecom-retail.example.com"
    DISPUTE_PHONE = "1-800-555-0199"
    PAYMENT_PORTAL_URL = "https://pay.telecom-retail.example.com/portal"

    @classmethod
    def evaluate_stage(cls, profile: CustomerProfile) -> Dict[str, Any]:
        days = profile.billing.days_overdue
        amount = profile.billing.outstanding_balance

        if amount <= 0.0 or days <= 0:
            return {
                "is_overdue": False,
                "stage": None,
                "tone": "N/A",
                "urgency": "NONE",
                "dispute_path": None
            }

        if days <= 15:
            stage_key = "stage_1"
            label = "Stage 1: Courteous Reminder"
            tone = "COURTEOUS_RESPECTFUL"
            urgency = "LOW"
            action_message = "Please review your statement and submit payment at your earliest convenience."
        elif days <= 30:
            stage_key = "stage_2"
            label = "Stage 2: Urgent Notice"
            tone = "DIRECT_FIRM"
            urgency = "MEDIUM"
            action_message = "To ensure uninterrupted service, prompt settlement or payment arrangement is required within 5 business days."
        else:
            stage_key = "stage_3"
            label = "Stage 3: Final Resolution & Hardship Assistance"
            tone = "SERIOUS_URGENT_SUPPORTIVE"
            urgency = "HIGH"
            action_message = "Immediate resolution is required. Our customer advocacy team is ready to discuss flexible payment schedules or hardship support."

        return {
            "is_overdue": True,
            "stage": stage_key,
            "stage_label": label,
            "days_overdue": days,
            "outstanding_balance": amount,
            "due_date": profile.billing.due_date or "Immediate",
            "invoice_number": profile.billing.invoice_number or f"INV-{profile.customer_id[-4:]}-2026",
            "tone": tone,
            "urgency": urgency,
            "action_message": action_message,
            "support_email": cls.SUPPORT_EMAIL,
            "dispute_phone": cls.DISPUTE_PHONE,
            "portal_url": f"{cls.PAYMENT_PORTAL_URL}?inv={profile.customer_id}",
            "dispute_instructions": f"If you believe this charge is inaccurate or have already paid, email {cls.SUPPORT_EMAIL} or call {cls.DISPUTE_PHONE} quoting your invoice number."
        }
