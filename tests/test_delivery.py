import pytest
from backend.models.customer import CustomerProfile, BillingInfo, EngagementMetrics, CommunicationHistory
from backend.models.classification import SegmentResult, StrategySelection
from backend.models.generation import MessageDraft, GroundedFacts, ReviewFeedback
from backend.models.guardrail import ValidationReport, GuardrailCheck
from backend.services.mock_delivery import MockDeliveryService
from backend.services.audit_service import AuditService


@pytest.fixture
def audit_service():
    return AuditService()


@pytest.fixture
def delivery_service(audit_service):
    return MockDeliveryService(audit_service)


def make_dummy_draft(status="PENDING_REVIEW", is_safe=True) -> MessageDraft:
    return MessageDraft(
        draft_id="DRF-TEST-99",
        customer_id="CUST-TEST",
        customer_name="Diana Prince",
        recipient_email="diana@amazon.example.com",
        primary_segment="consistent",
        strategy_objective="APPRECIATION_RETENTION",
        tone="WARM_GRATITUDE",
        subject="Thank you Diana",
        body_text="Dear Diana, thank you for being a customer.",
        grounded_facts=GroundedFacts(
            customer_name="Diana Prince",
            plan_name="Warrior 5G",
            tenure_months=12
        ),
        validation=ValidationReport(
            is_safe=is_safe,
            can_deliver=is_safe,
            critical_count=0 if is_safe else 1,
            warning_count=0,
            summary_verdict="PASSED" if is_safe else "FAILED",
            checks=[
                GuardrailCheck(
                    check_name="MOCK_CHECK",
                    category="GROUNDEDNESS",
                    passed=is_safe,
                    severity="CRITICAL",
                    message="OK" if is_safe else "Critical failure"
                )
            ]
        ),
        status=status,
        created_at="2026-11-09 12:00:00"
    )


def test_delivery_blocked_if_not_approved(delivery_service):
    draft = make_dummy_draft(status="PENDING_REVIEW")
    success, msg, receipt = delivery_service.deliver_draft(draft)

    assert success is False
    assert receipt is None
    assert "DELIVERY_REFUSED" in msg
    assert "human supervisor approval" in msg


def test_delivery_blocked_if_guardrail_failed(delivery_service):
    draft = make_dummy_draft(status="APPROVED", is_safe=False)
    success, msg, receipt = delivery_service.deliver_draft(draft)

    assert success is False
    assert receipt is None
    assert "Critical guardrail failure" in msg


def test_delivery_success_when_approved_and_safe(delivery_service):
    draft = make_dummy_draft(status="APPROVED", is_safe=True)
    success, msg, receipt = delivery_service.deliver_draft(draft)

    assert success is True
    assert receipt is not None
    assert receipt.status == "DELIVERED"
    assert "TRK-" in receipt.tracking_id
    assert draft.status == "DELIVERED"
