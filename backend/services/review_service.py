import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from ..models.generation import MessageDraft, ReviewFeedback
from ..models.customer import CustomerProfile
from .guardrails_engine import GuardrailsEngine


class ReviewService:
    def __init__(self):
        self.drafts: Dict[str, MessageDraft] = {}
        self.profiles: Dict[str, CustomerProfile] = {}
        self.guardrails = GuardrailsEngine()

    def register_draft(self, draft: MessageDraft, profile: CustomerProfile):
        self.drafts[draft.draft_id] = draft
        self.profiles[draft.draft_id] = profile

    def get_draft(self, draft_id: str) -> Optional[MessageDraft]:
        return self.drafts.get(draft_id)

    def list_drafts(self, status_filter: Optional[str] = None) -> List[MessageDraft]:
        drafts = list(self.drafts.values())
        if status_filter:
            drafts = [d for d in drafts if d.status == status_filter]
        return sorted(drafts, key=lambda d: d.created_at, reverse=True)

    def approve(self, draft_id: str, feedback: ReviewFeedback) -> MessageDraft:
        draft = self.drafts.get(draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found.")

        # Re-check guardrails before approving
        if not draft.validation.can_deliver:
            raise ValueError(f"Cannot approve draft {draft_id}: critical compliance guardrail failed ({draft.validation.summary_verdict}).")

        draft.status = "APPROVED"
        draft.reviewer_feedback = feedback
        return draft

    def reject(self, draft_id: str, feedback: ReviewFeedback) -> MessageDraft:
        draft = self.drafts.get(draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found.")

        draft.status = "REJECTED"
        draft.reviewer_feedback = feedback
        return draft

    def edit_and_revalidate(
        self, draft_id: str, new_subject: str, new_body: str, reviewer_id: str, notes: Optional[str] = None
    ) -> MessageDraft:
        draft = self.drafts.get(draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found.")

        profile = self.profiles.get(draft_id)
        if not profile:
            raise ValueError(f"Associated customer profile for {draft_id} not found.")

        # Re-run guardrails on the edited content
        new_validation = self.guardrails.validate_draft(
            profile=profile,
            segment=draft.primary_segment,
            subject=new_subject,
            body=new_body,
            offer=draft.offer
        )

        draft.subject = new_subject
        draft.body_text = new_body
        draft.validation = new_validation
        draft.status = "BLOCKED" if not new_validation.can_deliver else "PENDING_REVIEW"
        draft.reviewer_feedback = ReviewFeedback(
            reviewer_id=reviewer_id,
            action="EDIT",
            edited_subject=new_subject,
            edited_body=new_body,
            notes=notes or "Edited by reviewer and re-evaluated by guardrails."
        )
        return draft
