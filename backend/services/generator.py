import uuid
from datetime import datetime
from typing import Optional
from ..models.customer import CustomerProfile
from ..models.classification import SegmentResult, StrategySelection
from ..models.generation import MessageDraft, GroundedFacts, OfferSummary
from .offer_engine import OfferEngine
from .billing_engine import BillingReminderEngine
from .guardrails_engine import GuardrailsEngine


class MessageGenerator:
    """
    Drafts email subject and body using strictly verified facts and policy-approved templates.
    Implements FR-04 (Grounded message generation).
    """

    def __init__(self):
        self.offer_engine = OfferEngine()
        self.guardrails = GuardrailsEngine()

    def generate_draft(
        self,
        profile: CustomerProfile,
        segment_result: SegmentResult,
        strategy: StrategySelection,
        custom_offer: Optional[OfferSummary] = None
    ) -> MessageDraft:
        draft_id = f"DRF-{uuid.uuid4().hex[:8].upper()}"
        segment = segment_result.primary_segment
        offer = custom_offer

        # If no custom offer passed, check strategy eligible offer
        if not offer and strategy.eligible_offer_id:
            offer, _ = self.offer_engine.select_and_validate_offer(profile, segment)

        # Build grounded facts record
        facts = GroundedFacts(
            customer_name=profile.full_name,
            plan_name=profile.engagement.current_plan_name,
            tenure_months=profile.engagement.tenure_months,
            outstanding_balance=profile.billing.outstanding_balance if profile.billing.outstanding_balance > 0 else None,
            due_date=profile.billing.due_date if profile.billing.outstanding_balance > 0 else None,
            loyalty_tier=profile.engagement.loyalty_tier,
            offer_id=offer.offer_id if offer else None,
            offer_value=offer.value_description if offer else None,
            dispute_contact_included=(segment == "payment_reminder"),
            disclaimer_included=True
        )

        subject, body = self._compose_message(profile, segment, strategy, offer)

        # Run guardrail verification on generated draft
        validation = self.guardrails.validate_draft(profile, segment, subject, body, offer)

        # Initial status: BLOCKED if critical failures, else PENDING_REVIEW
        initial_status = "BLOCKED" if not validation.can_deliver else "PENDING_REVIEW"

        return MessageDraft(
            draft_id=draft_id,
            customer_id=profile.customer_id,
            customer_name=profile.full_name,
            recipient_email=profile.email,
            primary_segment=segment,
            strategy_objective=strategy.objective,
            tone=strategy.tone,
            subject=subject,
            body_text=body,
            grounded_facts=facts,
            offer=offer,
            validation=validation,
            status=initial_status,
            model_version="grounded-deterministic-engine-v2.2",
            template_version="telecom-policy-template-v1.4",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

    def _compose_message(
        self,
        profile: CustomerProfile,
        segment: str,
        strategy: StrategySelection,
        offer: Optional[OfferSummary]
    ) -> tuple[str, str]:
        first_name = profile.full_name.split()[0]
        plan = profile.engagement.current_plan_name
        tenure = profile.engagement.tenure_months
        tier = profile.engagement.loyalty_tier

        if segment == "payment_reminder":
            billing_info = BillingReminderEngine.evaluate_stage(profile)
            amt = f"${profile.billing.outstanding_balance:.2f}"
            due = profile.billing.due_date or "Immediate"
            inv = billing_info["invoice_number"]

            if billing_info["stage"] == "stage_1":
                subject = f"Friendly Reminder: Your {plan} Statement {inv} is Due"
                body = (
                    f"Dear {first_name},\n\n"
                    f"Thank you for being our valued customer on the {plan} plan for {tenure} months.\n\n"
                    f"This is a courteous reminder that invoice {inv} for {amt} reached its due date on {due}. "
                    f"If you have already sent this payment in the past 48 hours, please accept our thanks and disregard this email.\n\n"
                    f"To make a quick and secure payment, you may visit your account portal at:\n"
                    f"{billing_info['portal_url']}\n\n"
                    f"Questions or Disputes:\n"
                    f"If you have questions regarding this invoice, need flexible payment arrangements, or believe this balance is in error, "
                    f"please contact our dedicated billing support team immediately at {billing_info['support_email']} or call {billing_info['dispute_phone']}.\n\n"
                    f"Warm regards,\n"
                    f"Customer Billing & Account Care Team\n"
                    f"---\n"
                    f"Account Reference: {profile.customer_id} | Notice Stage: 1 (Courteous)"
                )
            elif billing_info["stage"] == "stage_2":
                subject = f"Important Notice: Overdue Balance of {amt} on Account {profile.customer_id}"
                body = (
                    f"Dear {first_name},\n\n"
                    f"We are writing to follow up regarding your {plan} account statement {inv}. "
                    f"Our records indicate an outstanding balance of {amt} which was due on {due} and is now {profile.billing.days_overdue} days past due.\n\n"
                    f"To avoid potential service restrictions on your {plan} service, please arrange settlement at:\n"
                    f"{billing_info['portal_url']}\n\n"
                    f"Support and Hardship Assistance:\n"
                    f"We understand unexpected circumstances occur. If you are experiencing difficulty or dispute any aspect of this charge, "
                    f"our team is available to assist with flexible payment solutions. Reach us directly at {billing_info['support_email']} "
                    f"or call {billing_info['dispute_phone']}.\n\n"
                    f"Sincerely,\n"
                    f"Customer Accounts Management\n"
                    f"---\n"
                    f"Account ID: {profile.customer_id} | Notice Stage: 2 (Urgent)"
                )
            else:
                subject = f"Urgent: Final Account Notice for Statement {inv} ({amt})"
                body = (
                    f"Dear {first_name},\n\n"
                    f"Please treat this communication with immediate priority. Your account on {plan} has an outstanding balance of {amt} "
                    f"which is now {profile.billing.days_overdue} days past due (original due date: {due}).\n\n"
                    f"Action Required:\n"
                    f"Please visit {billing_info['portal_url']} today to complete payment or schedule a formal payment arrangement.\n\n"
                    f"Dispute & Advocacy Team:\n"
                    f"If you are experiencing hardship or believe an error has occurred, contact our Senior Advocacy Team immediately at "
                    f"{billing_info['support_email']} or {billing_info['dispute_phone']}. We are committed to working with you toward a fair resolution.\n\n"
                    f"Respectfully,\n"
                    f"Customer Financial Services\n"
                    f"---\n"
                    f"Account ID: {profile.customer_id} | Notice Stage: 3 (Final Notice)"
                )
            return subject, body

        if segment == "loyalty_candidate":
            subject = f"A Heartfelt Thank You: Exclusive {tier} Loyalty Reward Inside"
            offer_text = ""
            if offer:
                offer_text = (
                    f"As a special celebration of your loyalty, we are delighted to provide you with:\n"
                    f"★ {offer.name}\n"
                    f"Benefit: {offer.value_description}\n"
                    f"Offer Terms: {offer.terms}\n"
                    f"Claim by: {offer.expiry_date} (Offer Code: {offer.offer_id})\n\n"
                )

            body = (
                f"Dear {first_name},\n\n"
                f"It is our absolute privilege to have you as part of our family for over {tenure} months on our {plan} plan.\n\n"
                f"Your consistent trust and partnership represent the highest tier of our {tier} membership, and we want to take a moment to express our sincere appreciation.\n\n"
                f"{offer_text}"
                f"We are committed to continually enhancing your experience. If there is ever anything we can do to make your service even better, please do not hesitate to reach out.\n\n"
                f"With sincere gratitude,\n"
                f"Executive Loyalty & Customer Experience Team\n"
                f"---\n"
                f"Customer Tier: {tier} | Account ID: {profile.customer_id}\n"
                f"To adjust your notification preferences, visit your customer portal account settings."
            )
            return subject, body

        if segment == "declining_activity":
            subject = f"Checking in on your {plan} experience, {first_name}"
            offer_text = ""
            if offer:
                offer_text = (
                    f"To help you get the most out of your connectivity, we have added a tailored booster for your account:\n"
                    f"• {offer.name}\n"
                    f"• Perk: {offer.value_description}\n"
                    f"• Activation window: Valid through {offer.expiry_date} (Ref: {offer.offer_id})\n"
                    f"• Terms: {offer.terms}\n\n"
                )

            body = (
                f"Dear {first_name},\n\n"
                f"We noticed that your usage on your {plan} plan has shifted recently. As your needs evolve over your {tenure}-month journey with us, we want to ensure you have the best setup for your lifestyle.\n\n"
                f"{offer_text}"
                f"Would you like us to review your current plan to see if a more customized option fits your daily routine? Let us know with a quick reply, or explore options in your account dashboard.\n\n"
                f"Warm regards,\n"
                f"Customer Value & Engagement Team\n"
                f"---\n"
                f"Account Reference: {profile.customer_id} | Notification Preferences Apply"
            )
            return subject, body

        if segment == "dormant":
            subject = f"We miss you, {first_name} - Special welcome-back gift"
            offer_text = ""
            if offer:
                offer_text = (
                    f"To make reconnecting effortless, we have reserved a special credit on your account:\n"
                    f"• Reward: {offer.name}\n"
                    f"• Benefit: {offer.value_description}\n"
                    f"• Available until: {offer.expiry_date} (Code: {offer.offer_id})\n"
                    f"• Details: {offer.terms}\n\n"
                )

            body = (
                f"Dear {first_name},\n\n"
                f"It has been a little while since we last saw activity on your {plan} service. We understand schedules get busy and communication needs change.\n\n"
                f"We value the {tenure} months we have spent serving you, and we would love to understand how we can serve you better.\n\n"
                f"{offer_text}"
                f"If you have 60 seconds, we would genuinely appreciate your feedback on how we can improve. Or if your needs have changed, simply let us know.\n\n"
                f"Warmly,\n"
                f"Customer Care & Community Team\n"
                f"---\n"
                f"Account ID: {profile.customer_id} | You may manage your communication options anytime in your account portal."
            )
            return subject, body

        # Default: Consistent Customer
        subject = f"Thank you for being with us, {first_name}!"
        offer_text = ""
        if offer:
            offer_text = (
                f"As a gesture of our appreciation for your consistent reliability, we are pleased to offer:\n"
                f"• {offer.name}\n"
                f"• Perk: {offer.value_description}\n"
                f"• Valid through: {offer.expiry_date} (Ref: {offer.offer_id})\n"
                f"• Terms: {offer.terms}\n\n"
            )

        body = (
            f"Dear {first_name},\n\n"
            f"Thank you for your ongoing partnership with us on your {plan} plan over the past {tenure} months.\n\n"
            f"Customers like you make our community special. We truly value your consistent loyalty and prompt connection with our services.\n\n"
            f"{offer_text}"
            f"If there is any way we can make your day-to-day experience even smoother, we are always here to help.\n\n"
            f"Sincerely,\n"
            f"Customer Relationship Team\n"
            f"---\n"
            f"Account: {profile.customer_id} | Preferences: To manage notifications, visit your profile portal."
        )
        return subject, body
