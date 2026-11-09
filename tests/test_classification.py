import pytest
from backend.models.customer import CustomerProfile, BillingInfo, EngagementMetrics, CommunicationHistory
from backend.services.classifier import CustomerClassifier


@pytest.fixture
def classifier():
    return CustomerClassifier()


def make_profile(
    tenure=12,
    spend=60.0,
    tier="STANDARD",
    overdue_amt=0.0,
    overdue_days=0,
    trend=0.0,
    days_inactive=2,
    csat=8.5,
    email_opt_in=True
) -> CustomerProfile:
    return CustomerProfile(
        customer_id="TEST-001",
        full_name="Alex Mercer",
        email="alex.mercer@example.com",
        account_type="POSTPAID_MOBILE",
        billing=BillingInfo(
            outstanding_balance=overdue_amt,
            days_overdue=overdue_days,
            due_date="2026-11-30" if overdue_days > 0 else None,
            late_payment_count_12m=0
        ),
        engagement=EngagementMetrics(
            tenure_months=tenure,
            current_plan_name="5G Unlimited Pro",
            monthly_spend=spend,
            loyalty_tier=tier,
            csat_score=csat,
            usage_trend_pct=trend,
            days_since_last_activity=days_inactive
        ),
        communication=CommunicationHistory(
            last_contact_date="2026-10-01",
            email_opt_in=email_opt_in
        )
    )


def test_payment_reminder_classification(classifier):
    # Customer with overdue balance
    profile = make_profile(overdue_amt=75.50, overdue_days=10)
    result = classifier.classify(profile)

    assert result.primary_segment == "payment_reminder"
    assert result.confidence >= 0.95
    assert any(rc.code == "BILLING_OVERDUE_BALANCE" for rc in result.reason_codes)
    assert any(rc.code == "BILLING_DAYS_PAST_DUE" for rc in result.reason_codes)


def test_loyalty_candidate_classification(classifier):
    # Customer with long tenure, high spend, high CSAT, zero overdue
    profile = make_profile(tenure=24, spend=95.0, tier="PLATINUM", csat=9.2, overdue_amt=0.0)
    result = classifier.classify(profile)

    assert result.primary_segment == "loyalty_candidate"
    assert result.confidence >= 0.90
    assert any(rc.code == "TENURE_LOYALTY_QUALIFIED" for rc in result.reason_codes)
    assert any(rc.code == "TIER_SPEND_QUALIFIED" for rc in result.reason_codes)


def test_declining_activity_classification(classifier):
    # Usage dropped 35%, still active 5 days ago
    profile = make_profile(tenure=10, spend=50.0, trend=-35.0, days_inactive=5, overdue_amt=0.0)
    result = classifier.classify(profile)

    assert result.primary_segment == "declining_activity"
    assert any(rc.code == "USAGE_TREND_DECLINE" for rc in result.reason_codes)


def test_dormant_customer_classification(classifier):
    # Inactive for 60 days
    profile = make_profile(tenure=8, spend=30.0, days_inactive=60, overdue_amt=0.0)
    result = classifier.classify(profile)

    assert result.primary_segment == "dormant"
    assert any(rc.code == "INACTIVITY_THRESHOLD_EXCEEDED" for rc in result.reason_codes)


def test_consistent_customer_classification(classifier):
    # Standard healthy customer
    profile = make_profile(tenure=8, spend=50.0, trend=2.0, days_inactive=3, overdue_amt=0.0)
    result = classifier.classify(profile)

    assert result.primary_segment == "consistent"
    assert any(rc.code == "STABLE_ENGAGEMENT" for rc in result.reason_codes)
