from typing import Optional, List
from pydantic import BaseModel, Field


class BillingInfo(BaseModel):
    outstanding_balance: float = Field(default=0.0, ge=0.0, description="Current unpaid balance in USD")
    days_overdue: int = Field(default=0, ge=0, description="Days since last invoice due date")
    invoice_number: Optional[str] = Field(default=None, description="Current invoice identifier")
    due_date: Optional[str] = Field(default=None, description="Due date for current balance (YYYY-MM-DD)")
    last_payment_date: Optional[str] = Field(default=None, description="Date of last settled payment")
    last_payment_amount: Optional[float] = Field(default=None, ge=0.0)
    payment_method_on_file: bool = Field(default=True, description="Whether active auto-pay/card is on file")
    late_payment_count_12m: int = Field(default=0, ge=0, description="Number of late invoices in past 12 months")


class EngagementMetrics(BaseModel):
    tenure_months: int = Field(..., ge=0, description="Customer account tenure in months")
    current_plan_name: str = Field(..., description="Active subscription plan or retail tier name")
    monthly_spend: float = Field(..., ge=0.0, description="Average monthly billing spend in USD")
    loyalty_tier: str = Field(default="STANDARD", description="Loyalty tier: STANDARD, SILVER, GOLD, PLATINUM, DIAMOND")
    csat_score: Optional[float] = Field(default=8.5, ge=1.0, le=10.0, description="CSAT score out of 10")
    nps_category: Optional[str] = Field(default="PROMOTER", description="PROMOTER, PASSIVE, DETRACTOR")
    usage_trend_pct: float = Field(default=0.0, description="Percent change in usage vs 90d baseline")
    days_since_last_activity: int = Field(default=2, ge=0, description="Days since last active usage/login")
    data_allowance_gb: float = Field(default=50.0, ge=0.0)
    data_used_gb: float = Field(default=35.0, ge=0.0)


class CommunicationHistory(BaseModel):
    last_contact_date: Optional[str] = Field(default=None, description="Date of last customer outreach (YYYY-MM-DD)")
    last_contact_channel: Optional[str] = Field(default="EMAIL", description="Channel of previous outreach")
    last_contact_category: Optional[str] = Field(default=None, description="Type of last outreach message")
    contact_count_last_30d: int = Field(default=0, ge=0, description="Messages sent within last 30 days")
    email_opt_in: bool = Field(default=True, description="GDPR/TCPA consent flag for promotional emails")
    sms_opt_in: bool = Field(default=True, description="Consent flag for SMS notifications")


class CustomerProfile(BaseModel):
    customer_id: str = Field(..., description="Unique anonymized customer identifier")
    full_name: str = Field(..., description="Customer full name")
    email: str = Field(..., description="Customer destination email address")
    account_type: str = Field(default="POSTPAID_MOBILE", description="Service category")
    billing: BillingInfo
    engagement: EngagementMetrics
    communication: CommunicationHistory
    tags: List[str] = Field(default_factory=list)
