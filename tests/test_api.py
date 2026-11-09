import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_scenarios_endpoint(client):
    res = client.get("/api/scenarios")
    assert res.status_code == 200
    scenarios = res.json()
    assert len(scenarios) >= 5
    scenario_ids = [s["scenario_id"] for s in scenarios]
    assert "SCENARIO_1_CONSISTENT" in scenario_ids
    assert "SCENARIO_2_LOYALTY_VIP" in scenario_ids
    assert "SCENARIO_5_OVERDUE_STAGE_1" in scenario_ids
    assert "SCENARIO_7_REFUSAL_MISSING_CONSENT" in scenario_ids


def test_generate_and_review_workflow(client):
    # Fetch first scenario
    scenarios = client.get("/api/scenarios").json()
    consistent_sc = next(s for s in scenarios if s["scenario_id"] == "SCENARIO_1_CONSISTENT")
    profile = consistent_sc["profile"]

    # 1. Classify
    res_class = client.post("/api/classify", json=profile)
    assert res_class.status_code == 200
    seg = res_class.json()
    assert seg["primary_segment"] == "consistent"

    # 2. Generate Draft
    res_gen = client.post("/api/generate", json={"profile": profile})
    assert res_gen.status_code == 200
    draft = res_gen.json()
    draft_id = draft["draft_id"]
    assert draft["status"] == "PENDING_REVIEW"
    assert draft["validation"]["can_deliver"] is True

    # 3. Try delivering before approval -> MUST FAIL (422)
    res_deliv_early = client.post(f"/api/drafts/{draft_id}/deliver")
    assert res_deliv_early.status_code == 422

    # 4. Human Approval
    res_app = client.post(
        f"/api/drafts/{draft_id}/approve",
        json={
            "reviewer_id": "auditor_jenny",
            "action": "APPROVE",
            "rating_relevance": 5,
            "rating_clarity": 5,
            "rating_tone": 5,
            "rating_cta": 5,
            "notes": "Verified facts and tone. Ready to deliver."
        }
    )
    assert res_app.status_code == 200
    assert res_app.json()["status"] == "APPROVED"

    # 5. Deliver after approval -> MUST SUCCEED
    res_deliv = client.post(f"/api/drafts/{draft_id}/deliver")
    assert res_deliv.status_code == 200
    assert res_deliv.json()["success"] is True
    assert res_deliv.json()["receipt"]["status"] == "DELIVERED"

    # 6. Audit & Observability
    audit_res = client.get("/api/audit")
    assert audit_res.status_code == 200
    assert len(audit_res.json()) > 0

    obs_res = client.get("/api/observability")
    assert obs_res.status_code == 200
    assert obs_res.json()["delivered_count"] >= 1
