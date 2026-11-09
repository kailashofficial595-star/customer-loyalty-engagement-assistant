import pytest
from backend.models.customer import CustomerProfile, BillingInfo, EngagementMetrics, CommunicationHistory
from backend.services.billing_engine import BillingReminderEngine


def make_billing_customer(days_overdue: int, amount: float) -> CustomerProfile:
    return CustomerProfile(
        customer_id="CUST-BILLING-1",
        full_name="Morgan Freeman",
        email="morgan@example.com",
        billing=BillingInfo(
            outstanding_balance=amount,
            days_overdue=days_overdue,
            invoice_number="INV-2026-999",
            due_date="2026-10-15"
        ),
        engagement=EngagementMetrics(
            tenure_months=12,
            current_plan_name="5G Choice",
            monthly_spend=amount
        ),
        communication=CommunicationHistory(email_opt_in=True)
    )


def test_stage_1_courteous_reminder():
    cust = make_billing_customer(days_overdue=7, amount=50.00)
    stage = BillingReminderEngine.evaluate_stage(cust)

    assert stage["is_overdue"] is True
    assert stage["stage"] == "stage_1"
    assert stage["tone"] == "COURTEOUS_RESPECTFUL"
    assert "portal_url" in stage
    assert "support_email" in stage
    assert "dispute_phone" in stage


def test_stage_2_urgent_reminder():
    cust = make_billing_customer(days_overdue=22, amount=120.00)
    stage = BillingReminderEngine.evaluate_stage(cust)

    assert stage["is_overdue"] is True
    assert stage["stage"] == "stage_2"
    assert stage["tone"] == "DIRECT_FIRM"
    assert stage["urgency"] == "MEDIUM"


def test_stage_3_final_notice():
    cust = make_billing_customer(days_overdue=45, amount=300.00)
    stage = BillingReminderEngine.evaluate_stage(cust)

    assert stage["is_overdue"] is True
    assert stage["stage"] == "stage_3"
    assert stage["tone"] == "SERIOUS_URGENT_SUPPORTIVE"
    assert stage["urgency"] == "HIGH"
