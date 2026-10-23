from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

ProcessingStatus = Literal["queued", "extracting", "validating", "ready", "failed"]
ReviewStatus = Literal["pending", "flagged", "approved", "rejected"]
RiskLevel = Literal["low", "medium", "high"]
Severity = Literal["high", "medium", "low", "info"]
Recommendation = Literal["no_issues_detected", "review_recommended", "high_priority_review", "manual_entry_required"]
ExtractionSource = Literal["gemini", "mock", "manual"]


class InvoiceFields(BaseModel):
    vendor_name: Optional[str] = None
    vendor_gstin: Optional[str] = None
    buyer_gstin: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    currency: Optional[str] = "INR"
    currency_assumed: bool = False
    taxable_amount: Optional[str] = None
    cgst: Optional[str] = None
    sgst: Optional[str] = None
    igst: Optional[str] = None
    total_amount: Optional[str] = None


class LineItem(BaseModel):
    line_no: int
    description: Optional[str] = None
    hsn_sac: Optional[str] = None
    quantity: Optional[str] = None
    unit_price: Optional[str] = None
    amount: Optional[str] = None


class UncertainField(BaseModel):
    field: str
    reason: str


class RiskBreakdownItem(BaseModel):
    rule_id: str
    severity: Severity
    points: int


class RiskResult(BaseModel):
    score: Optional[int] = None
    level: Optional[RiskLevel] = None
    recommendation: Recommendation = "no_issues_detected"
    breakdown: List[RiskBreakdownItem] = Field(default_factory=list)


class Finding(BaseModel):
    finding_id: str
    invoice_id: str
    rule_id: str
    severity: Severity
    category: str
    title: str
    explanation: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    validation_run: int
    is_current: bool = True
    created_at: str


class AuditEvent(BaseModel):
    event_id: str
    invoice_id: str
    event_type: str
    actor: str
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class InvoiceError(BaseModel):
    code: str
    message: str
    retryable: bool = False


class Invoice(BaseModel):
    invoice_id: str
    original_filename: str
    content_type: str
    file_size_bytes: int
    file_sha256: str
    processing_status: ProcessingStatus
    review_status: ReviewStatus
    extraction_source: Optional[str] = None
    extraction_model: Optional[str] = None
    document_type: Optional[str] = None
    fields: InvoiceFields
    line_items: List[LineItem] = Field(default_factory=list)
    uncertain_fields: List[UncertainField] = Field(default_factory=list)
    risk: RiskResult
    findings_summary: Dict[str, int] = Field(default_factory=lambda: {"high": 0, "medium": 0, "low": 0, "info": 0})
    validation_run: int = 0
    error: Optional[InvoiceError] = None
    created_at: str
    updated_at: str
    reviewed_at: Optional[str] = None


class InvoiceSummary(BaseModel):
    invoice_id: str
    original_filename: str
    vendor_name: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    total_amount: Optional[str] = None
    currency: Optional[str] = "INR"
    processing_status: ProcessingStatus
    review_status: ReviewStatus
    extraction_source: Optional[str] = None
    risk: RiskResult
    uncertain_field_count: int = 0
    created_at: str
