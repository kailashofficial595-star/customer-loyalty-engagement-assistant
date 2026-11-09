import json
import os
from typing import Tuple, List
from ..models.customer import CustomerProfile
from ..models.classification import SegmentResult, ReasonCode


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "policies.json")


def load_policies() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


class CustomerClassifier:
    def __init__(self):
        self.policies = load_policies()

    def classify(self, profile: CustomerProfile) -> SegmentResult:
        """
        Classifies customer into interpretable segments with deterministic reason codes and confidence.
        Implements FR-02 (Transparent classification).
        """
        billing = profile.billing
        eng = profile.engagement
        reasons: List[ReasonCode] = []
        secondary: List[str] = []

        # 1. Critical Check: Overdue Payment
        if billing.outstanding_balance > 0.0 and billing.days_overdue > 0:
            reasons.append(
                ReasonCode(
                    code="BILLING_OVERDUE_BALANCE",
                    description=f"Account has an active unpaid balance of ${billing.outstanding_balance:.2f} overdue by {billing.days_overdue} days.",
                    feature="billing.outstanding_balance",
                    observed_value=billing.outstanding_balance,
                    threshold_value=0.0
                )
            )
            reasons.append(
                ReasonCode(
                    code="BILLING_DAYS_PAST_DUE",
                    description=f"Invoice due date passed {billing.days_overdue} days ago (due: {billing.due_date or 'N/A'}).",
                    feature="billing.days_overdue",
                    observed_value=billing.days_overdue,
                    threshold_value=0
                )
            )

            # Determine stage for explanation
            stage_str = "Stage 1 (Courteous)" if billing.days_overdue <= 15 else ("Stage 2 (Urgent)" if billing.days_overdue <= 30 else "Stage 3 (Final)")
            
            return SegmentResult(
                primary_segment="payment_reminder",
                display_name="Payment Follow-up / Overdue",
                confidence=0.99,
                reason_codes=reasons,
                secondary_segments=[],
                explanation_summary=f"Customer has ${billing.outstanding_balance:.2f} past due by {billing.days_overdue} days. Route immediately to Billing Reminder Progression ({stage_str}). Promotional messaging is strictly prohibited."
            )

        # 2. Loyalty Candidate Check
        is_loyalty = False
        loyalty_reasons = []
        if eng.tenure_months >= 12 and (eng.monthly_spend >= 75.0 or eng.loyalty_tier in ["GOLD", "PLATINUM", "DIAMOND"]):
            is_loyalty = True
            loyalty_reasons.append(
                ReasonCode(
                    code="TENURE_LOYALTY_QUALIFIED",
                    description=f"Customer tenure of {eng.tenure_months} months meets the 12+ month threshold.",
                    feature="engagement.tenure_months",
                    observed_value=eng.tenure_months,
                    threshold_value=12
                )
            )
            loyalty_reasons.append(
                ReasonCode(
                    code="TIER_SPEND_QUALIFIED",
                    description=f"Loyalty tier is {eng.loyalty_tier} with monthly spend of ${eng.monthly_spend:.2f} (qualifying threshold: $75.00 or Gold+).",
                    feature="engagement.monthly_spend",
                    observed_value=eng.monthly_spend,
                    threshold_value=75.0
                )
            )
            if eng.csat_score and eng.csat_score >= 8.0:
                loyalty_reasons.append(
                    ReasonCode(
                        code="CSAT_HIGH_SATISFACTION",
                        description=f"CSAT score is {eng.csat_score}/10 indicating high brand affinity.",
                        feature="engagement.csat_score",
                        observed_value=eng.csat_score,
                        threshold_value=8.0
                    )
                )

        # 3. Dormant / Inactive Check
        if eng.days_since_last_activity > 45:
            reasons.append(
                ReasonCode(
                    code="INACTIVITY_THRESHOLD_EXCEEDED",
                    description=f"Customer has had no activity for {eng.days_since_last_activity} days (> 45 days limit).",
                    feature="engagement.days_since_last_activity",
                    observed_value=eng.days_since_last_activity,
                    threshold_value=45
                )
            )
            if is_loyalty:
                secondary.append("loyalty_candidate")
            
            return SegmentResult(
                primary_segment="dormant",
                display_name="Dormant / Inactive Customer",
                confidence=0.92,
                reason_codes=reasons,
                secondary_segments=secondary,
                explanation_summary=f"Customer has shown zero account or plan activity for {eng.days_since_last_activity} days. Recommended win-back survey and low-friction reactivation incentive."
            )

        # 4. Declining Activity Check
        if eng.usage_trend_pct <= -20.0:
            reasons.append(
                ReasonCode(
                    code="USAGE_TREND_DECLINE",
                    description=f"Usage declined by {abs(eng.usage_trend_pct):.1f}% over the past 90 days (drop threshold: -20%).",
                    feature="engagement.usage_trend_pct",
                    observed_value=eng.usage_trend_pct,
                    threshold_value=-20.0
                )
            )
            reasons.append(
                ReasonCode(
                    code="ACTIVE_RECENTLY",
                    description=f"Customer was active {eng.days_since_last_activity} days ago, indicating current reachability.",
                    feature="engagement.days_since_last_activity",
                    observed_value=eng.days_since_last_activity,
                    threshold_value=45
                )
            )
            if is_loyalty:
                secondary.append("loyalty_candidate")

            return SegmentResult(
                primary_segment="declining_activity",
                display_name="Declining Activity",
                confidence=0.90,
                reason_codes=reasons,
                secondary_segments=secondary,
                explanation_summary=f"Significant {abs(eng.usage_trend_pct):.1f}% drop in service consumption detected while account remains in good standing. Suitable for value re-engagement and data/plan boosters."
            )

        # 5. If Loyalty qualified without decline or dormancy
        if is_loyalty:
            return SegmentResult(
                primary_segment="loyalty_candidate",
                display_name="Loyalty & VIP Candidate",
                confidence=0.96,
                reason_codes=loyalty_reasons,
                secondary_segments=["consistent"],
                explanation_summary=f"Long-term high-value customer ({eng.tenure_months} months tenure, {eng.loyalty_tier} tier) with zero overdue balance and stellar engagement history. Ideal for exclusive VIP recognition."
            )

        # 6. Default: Consistent Customer
        reasons.append(
            ReasonCode(
                code="STABLE_ENGAGEMENT",
                description=f"Customer exhibits consistent account usage (trend: {eng.usage_trend_pct:+.1f}%), {eng.tenure_months} months tenure, and zero overdue balance.",
                feature="engagement.usage_trend_pct",
                observed_value=eng.usage_trend_pct,
                threshold_value=-20.0
            )
        )
        reasons.append(
            ReasonCode(
                code="TIMELY_PAYMENT_HISTORY",
                description=f"Account has 0 overdue invoices and regular payment timeliness.",
                feature="billing.outstanding_balance",
                observed_value=billing.outstanding_balance,
                threshold_value=0.0
            )
        )

        return SegmentResult(
            primary_segment="consistent",
            display_name="Consistent & Reliable Customer",
            confidence=0.88,
            reason_codes=reasons,
            secondary_segments=[],
            explanation_summary=f"Customer maintains healthy, steady engagement with on-time payments across {eng.tenure_months} months. Recommended strategy: warm gratitude, relationship reinforcement, and loyalty add-on."
        )
