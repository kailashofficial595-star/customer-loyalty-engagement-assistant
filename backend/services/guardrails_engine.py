import re
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Tuple
from ..models.customer import CustomerProfile
from ..models.guardrail import GuardrailCheck, ValidationReport
from ..models.generation import OfferSummary


GUARDRAILS_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "guardrails.json")


def load_guardrails_config() -> dict:
    if os.path.exists(GUARDRAILS_CONFIG_PATH):
        with open(GUARDRAILS_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


class GuardrailsEngine:
    def __init__(self):
        self.config = load_guardrails_config()
        self.blocked_terms = self.config.get("blocked_terms", [])
        self.pii_patterns = self.config.get("pii_patterns", [])
        self.min_cooldown_days = self.config.get("min_contact_cooldown_days", 7)

    def validate_draft(
        self,
        profile: CustomerProfile,
        segment: str,
        subject: str,
        body: str,
        offer: OfferSummary = None
    ) -> ValidationReport:
        """
        Executes strict multi-factor compliance and safety checks.
        Implements FR-07 (Safety and compliance checks).
        """
        checks: List[GuardrailCheck] = []
        combined_text = f"{subject}\n{body}"

        # 1. CONSENT CHECK (FR-07)
        if segment != "payment_reminder":
            if not profile.communication.email_opt_in:
                checks.append(
                    GuardrailCheck(
                        check_name="COMMUNICATION_CONSENT",
                        category="CONSENT",
                        passed=False,
                        severity="CRITICAL",
                        message="Customer has opted out of marketing/promotional communications (email_opt_in = False).",
                        detected_evidence={"email_opt_in": False, "channel": "EMAIL"}
                    )
                )
            else:
                checks.append(
                    GuardrailCheck(
                        check_name="COMMUNICATION_CONSENT",
                        category="CONSENT",
                        passed=True,
                        severity="INFO",
                        message="Valid customer opt-in consent verified.",
                        detected_evidence={"email_opt_in": True}
                    )
                )

        # 2. FREQUENCY / COOL-DOWN CHECK (FR-07)
        if profile.communication.last_contact_date:
            try:
                last_dt = datetime.strptime(profile.communication.last_contact_date, "%Y-%m-%d")
                days_since = (datetime.now() - last_dt).days
                if days_since < self.min_cooldown_days:
                    # Overdue billing reminders might have tighter tolerance, but still check
                    is_critical = (segment != "payment_reminder")
                    checks.append(
                        GuardrailCheck(
                            check_name="CONTACT_FREQUENCY_COOLDOWN",
                            category="FREQUENCY",
                            passed=False,
                            severity="CRITICAL" if is_critical else "WARNING",
                            message=f"Last contact was {days_since} days ago. Policy requires a minimum cooldown of {self.min_cooldown_days} days to prevent fatigue.",
                            detected_evidence={"days_since_contact": days_since, "minimum_cooldown": self.min_cooldown_days}
                        )
                    )
                else:
                    checks.append(
                        GuardrailCheck(
                            check_name="CONTACT_FREQUENCY_COOLDOWN",
                            category="FREQUENCY",
                            passed=True,
                            severity="INFO",
                            message=f"Contact frequency policy satisfied ({days_since} days since last outreach).",
                            detected_evidence={"days_since_contact": days_since}
                        )
                    )
            except Exception:
                pass

        # 3. PII & SENSITIVE DATA CHECK (FR-07)
        pii_leaks = []
        for pattern in self.pii_patterns:
            matches = re.findall(pattern["regex"], combined_text)
            if matches:
                pii_leaks.append({"type": pattern["name"], "count": len(matches)})

        if pii_leaks:
            checks.append(
                GuardrailCheck(
                    check_name="SENSITIVE_DATA_LEAKAGE",
                    category="SENSITIVE_DATA",
                    passed=False,
                    severity="CRITICAL",
                    message="Detected prohibited sensitive data pattern in drafted message (e.g. unmasked card or SSN).",
                    detected_evidence={"leaks": pii_leaks}
                )
            )
        else:
            checks.append(
                GuardrailCheck(
                    check_name="SENSITIVE_DATA_LEAKAGE",
                    category="SENSITIVE_DATA",
                    passed=True,
                    severity="INFO",
                    message="No sensitive PII (credit cards, SSNs, passwords) detected in draft.",
                    detected_evidence=None
                )
            )

        # 4. PROHIBITED LANGUAGE & HARSH TONE CHECK (FR-07)
        found_blocked = [term for term in self.blocked_terms if term.lower() in combined_text.lower()]
        if found_blocked:
            checks.append(
                GuardrailCheck(
                    check_name="PROHIBITED_OR_TOXIC_LANGUAGE",
                    category="POLICY_TONE",
                    passed=False,
                    severity="CRITICAL",
                    message=f"Message contains prohibited aggressive, threatening, or misleading terms: {', '.join(found_blocked)}",
                    detected_evidence={"blocked_terms_found": found_blocked}
                )
            )
        else:
            checks.append(
                GuardrailCheck(
                    check_name="PROHIBITED_OR_TOXIC_LANGUAGE",
                    category="POLICY_TONE",
                    passed=True,
                    severity="INFO",
                    message="Tone adheres to professional retail/telecom guidelines with zero prohibited terms.",
                    detected_evidence=None
                )
            )

        # 5. GROUNDEDNESS & HALLUCINATION CHECK (FR-04, FR-07)
        # Extract currency dollar amounts in text
        found_amounts = re.findall(r"\$\s*(\d+(?:\.\d{2})?)", combined_text)
        
        # Build set of permitted verified monetary values
        verified_amounts = {
            f"{profile.billing.outstanding_balance:.2f}",
            f"{int(profile.billing.outstanding_balance)}",
            f"{profile.engagement.monthly_spend:.2f}",
            f"{int(profile.engagement.monthly_spend)}"
        }
        if offer:
            # Extract numbers from offer value description if present
            offer_nums = re.findall(r"\$\s*(\d+(?:\.\d{2})?)", offer.value_description)
            for n in offer_nums:
                verified_amounts.add(n)
                verified_amounts.add(f"{float(n):.2f}")

        # Check each drafted dollar amount against verified customer/campaign facts
        unsupported_amounts = []
        for amt in found_amounts:
            val = float(amt)
            # Allow $0 or exact matches
            if val != 0.0:
                is_supported = any(abs(val - float(v)) < 0.01 for v in verified_amounts if v.replace('.', '', 1).isdigit())
                if not is_supported:
                    unsupported_amounts.append(f"${amt}")

        if unsupported_amounts:
            checks.append(
                GuardrailCheck(
                    check_name="GROUNDEDNESS_FACT_VERIFICATION",
                    category="GROUNDEDNESS",
                    passed=False,
                    severity="CRITICAL",
                    message=f"Detected unverified/hallucinated monetary amounts not present in customer or campaign data: {', '.join(unsupported_amounts)}",
                    detected_evidence={"unsupported_amounts": unsupported_amounts, "verified_amounts": list(verified_amounts)}
                )
            )
        else:
            checks.append(
                GuardrailCheck(
                    check_name="GROUNDEDNESS_FACT_VERIFICATION",
                    category="GROUNDEDNESS",
                    passed=True,
                    severity="INFO",
                    message="All cited monetary amounts and pricing terms are grounded in verified customer or campaign data.",
                    detected_evidence={"verified_amounts": list(verified_amounts)}
                )
            )

        # 6. BILLING REMINDER COMPLIANCE (FR-06)
        if segment == "payment_reminder":
            has_dispute = any(kw in combined_text.lower() for kw in ["dispute", "support", "contact", "hardship", "help"])
            if not has_dispute:
                checks.append(
                    GuardrailCheck(
                        check_name="BILLING_DISPUTE_PATH_MANDATORY",
                        category="POLICY_TONE",
                        passed=False,
                        severity="CRITICAL",
                        message="Payment reminder missing mandatory dispute instructions or customer support contact path.",
                        detected_evidence={"has_dispute_path": False}
                    )
                )
            else:
                checks.append(
                    GuardrailCheck(
                        check_name="BILLING_DISPUTE_PATH_MANDATORY",
                        category="POLICY_TONE",
                        passed=True,
                        severity="INFO",
                        message="Mandatory dispute and support contact instructions verified in draft.",
                        detected_evidence={"has_dispute_path": True}
                    )
                )

            # Rule: Overdue notices must never contain promotional gift offers
            if offer is not None:
                checks.append(
                    GuardrailCheck(
                        check_name="OVERDUE_PROMOTION_PROHIBITION",
                        category="OFFER_ELIGIBILITY",
                        passed=False,
                        severity="CRITICAL",
                        message="Policy violation: Incompatible mix of overdue bill notice with promotional gift offer.",
                        detected_evidence={"offer_attached": offer.offer_id}
                    )
                )

        # Summarize report
        criticals = sum(1 for c in checks if not c.passed and c.severity == "CRITICAL")
        warnings = sum(1 for c in checks if not c.passed and c.severity == "WARNING")
        is_safe = (criticals == 0)
        can_deliver = is_safe

        if criticals > 0:
            verdict = f"FAILED: {criticals} critical safety or compliance violation(s) detected. Draft blocked from delivery."
        elif warnings > 0:
            verdict = f"PASSED WITH WARNINGS: {warnings} advisory warning(s) noted. Requires reviewer review before send."
        else:
            verdict = "PASSED: All compliance, privacy, groundedness, and tone guardrails satisfied."

        return ValidationReport(
            is_safe=is_safe,
            can_deliver=can_deliver,
            critical_count=criticals,
            warning_count=warnings,
            checks=checks,
            summary_verdict=verdict
        )
