import json
import os
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from ..models.customer import CustomerProfile
from ..models.generation import OfferSummary


CAMPAIGNS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "campaigns.json")


def load_campaigns() -> dict:
    if os.path.exists(CAMPAIGNS_PATH):
        with open(CAMPAIGNS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"approved_offers": []}


class OfferEngine:
    def __init__(self):
        self.campaigns = load_campaigns().get("approved_offers", [])

    def select_and_validate_offer(
        self, profile: CustomerProfile, segment: str
    ) -> Tuple[Optional[OfferSummary], str]:
        """
        Deterministically evaluates offer catalog against customer facts.
        Enforces FR-05 (Offer and reward controls).
        """
        # CRITICAL HARD RULE: No offers or rewards for overdue accounts!
        if profile.billing.outstanding_balance > 0 or profile.billing.days_overdue > 0:
            return None, "INELIGIBLE_OVERDUE_BALANCE: Promotional offers are prohibited when an overdue balance exists."

        # Customers who opted out of marketing
        if not profile.communication.email_opt_in:
            return None, "INELIGIBLE_OPT_OUT: Customer has opted out of promotional communications."

        candidates = []
        for offer in self.campaigns:
            # 1. Segment eligibility
            if segment not in offer.get("eligible_segments", []):
                continue

            # 2. Tenure check
            if profile.engagement.tenure_months < offer.get("min_tenure_months", 0):
                continue

            # 3. Monthly spend check
            if profile.engagement.monthly_spend < offer.get("min_monthly_spend", 0.0):
                continue

            # 4. VIP Tier requirement
            if offer.get("requires_gold_plus", False):
                if profile.engagement.loyalty_tier not in ["GOLD", "PLATINUM", "DIAMOND"]:
                    continue

            candidates.append(offer)

        if not candidates:
            return None, "NO_MATCHING_OFFER: No approved campaign matches current tenure, tier, or segment criteria."

        # Pick best eligible offer (e.g. first matching prioritized campaign)
        chosen = candidates[0]
        
        # Calculate expiry date from today
        expiry_days = chosen.get("expiry_days", 30)
        expiry_date = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d")

        summary = OfferSummary(
            offer_id=chosen["offer_id"],
            name=chosen["name"],
            category=chosen["category"],
            value_description=chosen["value_description"],
            expiry_date=expiry_date,
            terms=chosen["terms"]
        )

        return summary, f"QUALIFIED: Met all criteria for {chosen['name']} (ID: {chosen['offer_id']})."
