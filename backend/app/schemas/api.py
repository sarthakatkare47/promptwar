from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from app.schemas.invoice import Invoice, InvoiceSummary, AuditEvent


class UploadResponse(BaseModel):
    invoice: Invoice
    already_existed: bool


class InvoiceListResponse(BaseModel):
    items: List[InvoiceSummary]
    total: int
    limit: int
    offset: int


class PatchInvoiceRequest(BaseModel):
    fields: Optional[Dict[str, Optional[str]]] = None
    confirmed_fields: Optional[List[str]] = None
    line_items: Optional[List[Dict[str, Any]]] = None


class ReviewInvoiceRequest(BaseModel):
    action: Literal["approve", "flag", "reject", "reopen"]
    comment: Optional[str] = Field(default=None, max_length=500)
    acknowledge_risk: bool = False


class ReviewInvoiceResponse(BaseModel):
    invoice: Invoice
    audit_event: AuditEvent


class ReprocessRequest(BaseModel):
    confirm_overwrite: bool = False


class FindingsListResponse(BaseModel):
    invoice_id: str
    validation_run: int
    items: List[Any]


class AuditListResponse(BaseModel):
    invoice_id: str
    items: List[AuditEvent]


class HealthResponse(BaseModel):
    status: str
    version: str
    extractor: str
    gemini_configured: bool
    database: str
    time: str
