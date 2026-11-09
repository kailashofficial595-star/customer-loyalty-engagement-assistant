from typing import Optional
from ..models.customer import CustomerProfile
from ..models.classification import SegmentResult, StrategySelection
from .offer_engine import OfferEngine
from .billing_engine import BillingReminderEngine


class StrategySelector:
    def __init__(self):
        self.offer_engine = OfferEngine()

    def select_strategy(self, profile: CustomerProfile, segment_result: SegmentResult) -> StrategySelection:
        """
        Maps segment result and verified customer facts to policy-approved objective and tone.
        Implements FR-03 (Policy-based strategy selection).
        """
        segment = segment_result.primary_segment

        if segment == "payment_reminder":
            billing_stage = BillingReminderEngine.evaluate_stage(profile)
            return StrategySelection(
                objective="PAYMENT_REMINDER_PROGRESSION",
                tone=billing_stage["tone"],
                reminder_stage=billing_stage["stage_label"],
                eligible_offer_id=None,  # Hard policy: no offers on overdue bills
                guidelines=(
                    "Strictly state verified invoice amount and due date. "
                    "Maintain a courteous, non-threatening professional tone. "
                    "Must include payment portal link and clear dispute/hardship support path."
                ),
                channel="EMAIL"
            )

        if segment == "loyalty_candidate":
            offer, _ = self.offer_engine.select_and_validate_offer(profile, segment)
            return StrategySelection(
                objective="VIP_REWARD_RECOGNITION",
                tone="CELEBRATORY_PRESTIGIOUS",
                reminder_stage=None,
                eligible_offer_id=offer.offer_id if offer else None,
                guidelines=(
                    "Express sincere gratitude for customer milestone tenure and VIP loyalty. "
                    "Highlight exclusive tier benefits and present verified approved reward details. "
                    "Keep tone celebratory, appreciative, and dignified."
                ),
                channel="EMAIL"
            )

        if segment == "declining_activity":
            offer, _ = self.offer_engine.select_and_validate_offer(profile, segment)
            return StrategySelection(
                objective="VALUE_REENGAGEMENT",
                tone="HELPFUL_ENCOURAGING",
                reminder_stage=None,
                eligible_offer_id=offer.offer_id if offer else None,
                guidelines=(
                    "Acknowledge changing usage patterns without being accusatory or intrusive. "
                    "Suggest value-maximizing plan features and introduce the approved bonus data offer. "
                    "Encourage two-way communication."
                ),
                channel="EMAIL"
            )

        if segment == "dormant":
            offer, _ = self.offer_engine.select_and_validate_offer(profile, segment)
            return StrategySelection(
                objective="WINBACK_SURVEY",
                tone="LOW_PRESSURE_SUPPORTIVE",
                reminder_stage=None,
                eligible_offer_id=offer.offer_id if offer else None,
                guidelines=(
                    "Warm, low-pressure check-in inquiring if their needs have changed. "
                    "Offer straightforward feedback link and provide reactivation incentive. "
                    "Reassure customer their account preferences are respected."
                ),
                channel="EMAIL"
            )

        # Default: Consistent
        offer, _ = self.offer_engine.select_and_validate_offer(profile, segment)
        return StrategySelection(
            objective="APPRECIATION_RETENTION",
            tone="WARM_GRATITUDE",
            reminder_stage=None,
            eligible_offer_id=offer.offer_id if offer else None,
            guidelines=(
                "Thank customer for their steady relationship and on-time consistency. "
                "Reinforce current plan value and offer complimentary loyalty boost if eligible."
            ),
            channel="EMAIL"
        )
