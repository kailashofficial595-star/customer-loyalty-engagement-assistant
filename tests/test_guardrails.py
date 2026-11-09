import pytest
from backend.models.customer import CustomerProfile, BillingInfo, EngagementMetrics, CommunicationHistory
from backend.models.generation import OfferSummary
from backend.services.guardrails_engine import GuardrailsEngine


@pytest.fixture
def guardrails():
    return GuardrailsEngine()


@pytest.fixture
def base_customer():
    return CustomerProfile(
        customer_id="CUST-SAFE-01",
        full_name="Bruce Wayne",
        email="bruce@wayne-enterprises.com",
        billing=BillingInfo(outstanding_balance=0.0, days_overdue=0),
        engagement=EngagementMetrics(
            tenure_months=24,
            current_plan_name="Wayne 5G Elite",
            monthly_spend=100.0,
            loyalty_tier="DIAMOND"
        ),
        communication=CommunicationHistory(email_opt_in=True, last_contact_date="2026-09-01")
    )


def test_guardrail_passes_clean_draft(guardrails, base_customer):
    subject = "Thank you for being with us, Bruce!"
    body = "Dear Bruce, thank you for your 24 months with us on Wayne 5G Elite. Manage preferences anytime in your account portal."

    report = guardrails.validate_draft(base_customer, "consistent", subject, body)
    assert report.is_safe is True
    assert report.can_deliver is True
    assert report.critical_count == 0


def test_guardrail_catches_hallucinated_dollar_amount(guardrails, base_customer):
    subject = "Special surprise reward!"
    body = "Dear Bruce, congratulations! You have been granted a $499.99 instant cash refund on your account!"

    report = guardrails.validate_draft(base_customer, "consistent", subject, body)
    assert report.is_safe is False
    assert report.can_deliver is False
    assert any(c.check_name == "GROUNDEDNESS_FACT_VERIFICATION" and not c.passed for c in report.checks)


def test_guardrail_catches_prohibited_threatening_language(guardrails, base_customer):
    subject = "Notice regarding your status"
    body = "Dear Bruce, we will seize your property unless you act within 1 hour."

    report = guardrails.validate_draft(base_customer, "consistent", subject, body)
    assert report.is_safe is False
    assert any(c.check_name == "PROHIBITED_OR_TOXIC_LANGUAGE" and not c.passed for c in report.checks)


def test_guardrail_catches_pii_credit_card(guardrails, base_customer):
    subject = "Your account confirmation"
    body = "Dear Bruce, please confirm your card number 4111111111111111 for auto-debit."

    report = guardrails.validate_draft(base_customer, "consistent", subject, body)
    assert report.is_safe is False
    assert any(c.check_name == "SENSITIVE_DATA_LEAKAGE" and not c.passed for c in report.checks)


def test_guardrail_catches_missing_marketing_consent(guardrails, base_customer):
    base_customer.communication.email_opt_in = False
    subject = "Exclusive reward inside!"
    body = "Dear Bruce, here is your reward."

    report = guardrails.validate_draft(base_customer, "loyalty_candidate", subject, body)
    assert report.is_safe is False
    assert any(c.check_name == "COMMUNICATION_CONSENT" and not c.passed for c in report.checks)


def test_guardrail_catches_overdue_with_promotional_offer(guardrails, base_customer):
    base_customer.billing.outstanding_balance = 85.0
    base_customer.billing.days_overdue = 12

    offer = OfferSummary(
        offer_id="OFFER-TEST",
        name="Bonus 10GB",
        category="PROMOTION",
        value_description="10GB Free",
        expiry_date="2026-12-31",
        terms="Test terms"
    )

    subject = "Payment reminder"
    body = "Dear Bruce, your bill of $85.00 is due. Contact support for dispute. Here is your free gift."

    report = guardrails.validate_draft(base_customer, "payment_reminder", subject, body, offer=offer)
    assert report.is_safe is False
    assert any(c.check_name == "OVERDUE_PROMOTION_PROHIBITION" and not c.passed for c in report.checks)
