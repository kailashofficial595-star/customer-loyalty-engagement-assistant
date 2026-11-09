import os
import json
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .models.customer import CustomerProfile
from .models.classification import SegmentResult, StrategySelection
from .models.generation import MessageDraft, ReviewFeedback
from .models.guardrail import ValidationReport
from .models.audit import AuditEntry, DeliveryReceipt

from .services.classifier import CustomerClassifier
from .services.strategy_selector import StrategySelector
from .services.offer_engine import OfferEngine
from .services.billing_engine import BillingReminderEngine
from .services.guardrails_engine import GuardrailsEngine
from .services.generator import MessageGenerator
from .services.review_service import ReviewService
from .services.audit_service import AuditService
from .services.mock_delivery import MockDeliveryService


app = FastAPI(
    title="Customer Loyalty & Engagement Assistant API",
    version="1.0.0",
    description="GenAI Assistant for Telecom & Retail Customer Classification, Grounded Outreach Generation, Guardrails, and Human-in-the-Loop Review."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize core domain services
classifier = CustomerClassifier()
strategy_selector = StrategySelector()
offer_engine = OfferEngine()
guardrails = GuardrailsEngine()
generator = MessageGenerator()
review_service = ReviewService()
audit_service = AuditService()
delivery_service = MockDeliveryService(audit_service)

# Paths
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")


# Request schemas
class GenerateRequest(BaseModel):
    profile: CustomerProfile
    custom_offer_id: Optional[str] = None


class EditDraftRequest(BaseModel):
    subject: str
    body: str
    reviewer_id: str = "reviewer_operator_1"
    notes: Optional[str] = None


class ValidationRequest(BaseModel):
    profile: CustomerProfile
    segment: str
    subject: str
    body: str
    offer_id: Optional[str] = None


# Endpoints
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "customer-loyalty-engagement-assistant",
        "version": "1.0.0"
    }


@app.get("/api/scenarios")
def get_scenarios() -> List[Dict[str, Any]]:
    """Loads all preloaded evaluation and demonstration customer scenarios."""
    scenarios_file = os.path.join(DATA_DIR, "sample_customers.json")
    if os.path.exists(scenarios_file):
        with open(scenarios_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


@app.get("/api/config")
def get_configurations():
    """Returns transparent policy, campaign, and guardrail configurations."""
    policies_path = os.path.join(CONFIG_DIR, "policies.json")
    campaigns_path = os.path.join(CONFIG_DIR, "campaigns.json")
    guardrails_path = os.path.join(CONFIG_DIR, "guardrails.json")

    policies = json.load(open(policies_path, "r", encoding="utf-8")) if os.path.exists(policies_path) else {}
    campaigns = json.load(open(campaigns_path, "r", encoding="utf-8")) if os.path.exists(campaigns_path) else {}
    guardrail_cfg = json.load(open(guardrails_path, "r", encoding="utf-8")) if os.path.exists(guardrails_path) else {}

    return {
        "policies": policies,
        "campaigns": campaigns,
        "guardrails": guardrail_cfg
    }


@app.post("/api/classify", response_model=SegmentResult)
def classify_customer(profile: CustomerProfile):
    """FR-02: Transparent, interpretable customer classification."""
    return classifier.classify(profile)


@app.post("/api/strategy", response_model=StrategySelection)
def select_strategy(profile: CustomerProfile):
    """FR-03: Deterministic policy-based strategy mapping."""
    segment_res = classifier.classify(profile)
    return strategy_selector.select_strategy(profile, segment_res)


@app.post("/api/generate", response_model=MessageDraft)
def generate_draft(req: GenerateRequest):
    """FR-04: Grounded message generation with deterministic facts and guardrail inspection."""
    profile = req.profile
    segment_res = classifier.classify(profile)
    strategy = strategy_selector.select_strategy(profile, segment_res)

    custom_offer = None
    if req.custom_offer_id:
        for off in offer_engine.campaigns:
            if off["offer_id"] == req.custom_offer_id:
                from .models.generation import OfferSummary
                custom_offer = OfferSummary(
                    offer_id=off["offer_id"],
                    name=off["name"],
                    category=off["category"],
                    value_description=off["value_description"],
                    expiry_date="2026-12-31",
                    terms=off["terms"]
                )
                break

    draft = generator.generate_draft(profile, segment_res, strategy, custom_offer)
    review_service.register_draft(draft, profile)
    audit_service.record_generation(draft, profile)
    return draft


@app.post("/api/guardrails/check", response_model=ValidationReport)
def run_guardrails_check(req: ValidationRequest):
    """FR-07: On-demand safety, PII, hallucination, and compliance inspection."""
    offer = None
    if req.offer_id:
        for off in offer_engine.campaigns:
            if off["offer_id"] == req.offer_id:
                from .models.generation import OfferSummary
                offer = OfferSummary(
                    offer_id=off["offer_id"],
                    name=off["name"],
                    category=off["category"],
                    value_description=off["value_description"],
                    expiry_date="2026-12-31",
                    terms=off["terms"]
                )
                break
    return guardrails.validate_draft(req.profile, req.segment, req.subject, req.body, offer)


@app.get("/api/drafts", response_model=List[MessageDraft])
def list_drafts(status: Optional[str] = Query(default=None)):
    """FR-08: List reviewable drafts filtered by status."""
    return review_service.list_drafts(status)


@app.get("/api/drafts/{draft_id}", response_model=MessageDraft)
def get_draft_by_id(draft_id: str):
    draft = review_service.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@app.post("/api/drafts/{draft_id}/approve", response_model=MessageDraft)
def approve_draft(draft_id: str, feedback: ReviewFeedback):
    """FR-08: Human reviewer approval with quality rubric."""
    try:
        updated = review_service.approve(draft_id, feedback)
        audit_service.record_review_action(draft_id, feedback.reviewer_id, "APPROVE", feedback.notes)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/drafts/{draft_id}/reject", response_model=MessageDraft)
def reject_draft(draft_id: str, feedback: ReviewFeedback):
    """FR-08: Human reviewer rejection."""
    try:
        updated = review_service.reject(draft_id, feedback)
        audit_service.record_review_action(draft_id, feedback.reviewer_id, "REJECT", feedback.rejection_reason)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/drafts/{draft_id}/edit", response_model=MessageDraft)
def edit_draft(draft_id: str, req: EditDraftRequest):
    """FR-08: Human reviewer inline edit with instant guardrail re-validation."""
    try:
        updated = review_service.edit_and_revalidate(
            draft_id=draft_id,
            new_subject=req.subject,
            new_body=req.body,
            reviewer_id=req.reviewer_id,
            notes=req.notes
        )
        audit_service.record_review_action(draft_id, req.reviewer_id, "EDIT", req.notes)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/drafts/{draft_id}/deliver")
def deliver_draft(draft_id: str):
    """FR-10: Controlled delivery gate (blocks unapproved or unsafe drafts)."""
    draft = review_service.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    success, message, receipt = delivery_service.deliver_draft(draft)
    if not success:
        raise HTTPException(status_code=422, detail=message)

    return {
        "success": True,
        "message": message,
        "receipt": receipt
    }


@app.get("/api/audit", response_model=List[AuditEntry])
def get_audit_trail(limit: int = Query(default=50)):
    """FR-09: Anonymized audit trail entries."""
    return audit_service.get_entries(limit)


@app.get("/api/observability")
def get_observability():
    """FR-09: Real-time system health and governance metrics."""
    return audit_service.get_observability_metrics()


# Mount frontend static directory
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
