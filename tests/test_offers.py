import pytest
from backend.models.customer import CustomerProfile, BillingInfo, EngagementMetrics, CommunicationHistory
from backend.services.offer_engine import OfferEngine


@pytest.fixture
def offer_engine():
    return OfferEngine()


def make_customer(overdue=0.0, tenure=12, spend=60.0, tier="SILVER", opt_in=True) -> CustomerProfile:
    return CustomerProfile(
        customer_id="CUST-OFFER-1",
        full_name="Taylor Swift",
        email="taylor@example.com",
        billing=BillingInfo(outstanding_balance=overdue, days_overdue=10 if overdue > 0 else 0),
        engagement=EngagementMetrics(
            tenure_months=tenure,
            current_plan_name="Unlimited 5G",
            monthly_spend=spend,
            loyalty_tier=tier
        ),
        communication=CommunicationHistory(email_opt_in=opt_in)
    )


def test_offer_refusal_when_overdue(offer_engine):
    # Overdue accounts must NEVER receive promotional rewards
    cust = make_customer(overdue=45.00, tenure=24, spend=100.0, tier="PLATINUM")
    offer, reason = offer_engine.select_and_validate_offer(cust, "loyalty_candidate")

    assert offer is None
    assert "INELIGIBLE_OVERDUE_BALANCE" in reason


def test_offer_refusal_when_opted_out(offer_engine):
    # Customer who opted out must NOT be offered promotions
    cust = make_customer(overdue=0.0, tenure=24, spend=100.0, tier="PLATINUM", opt_in=False)
    offer, reason = offer_engine.select_and_validate_offer(cust, "loyalty_candidate")

    assert offer is None
    assert "INELIGIBLE_OPT_OUT" in reason


def test_vip_reward_qualification(offer_engine):
    # Meets tenure >= 12, spend >= 80, tier Platinum
    cust = make_customer(overdue=0.0, tenure=24, spend=95.0, tier="PLATINUM")
    offer, reason = offer_engine.select_and_validate_offer(cust, "loyalty_candidate")

    assert offer is not None
    assert offer.offer_id in ["OFFER-LOYALTY-5G-DATA-20GB", "OFFER-VIP-STREAMING-PASS"]
    assert "QUALIFIED" in reason
