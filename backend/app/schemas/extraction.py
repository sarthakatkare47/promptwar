from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class ExtractedField(BaseModel):
    value: Optional[str] = None
    legibility: Literal["clear", "unclear", "not_found"] = "not_found"
    evidence: Optional[str] = Field(default=None, max_length=200)


class ExtractedLineItem(BaseModel):
    description: Optional[str] = Field(default=None, max_length=300)
    hsn_sac: Optional[str] = Field(default=None, max_length=16)
    quantity: Optional[str] = None
    unit_price: Optional[str] = None
    amount: Optional[str] = None


class ExtractionResult(BaseModel):
    document_type: Literal["tax_invoice", "bill_of_supply", "other", "not_an_invoice"] = "tax_invoice"
    vendor_name: ExtractedField = Field(default_factory=ExtractedField)
    vendor_gstin: ExtractedField = Field(default_factory=ExtractedField)
    buyer_gstin: ExtractedField = Field(default_factory=ExtractedField)
    invoice_number: ExtractedField = Field(default_factory=ExtractedField)
    invoice_date: ExtractedField = Field(default_factory=ExtractedField)
    currency: ExtractedField = Field(default_factory=lambda: ExtractedField(value="INR", legibility="clear", evidence="₹"))
    taxable_amount: ExtractedField = Field(default_factory=ExtractedField)
    cgst: ExtractedField = Field(default_factory=ExtractedField)
    sgst: ExtractedField = Field(default_factory=ExtractedField)
    igst: ExtractedField = Field(default_factory=ExtractedField)
    total_amount: ExtractedField = Field(default_factory=ExtractedField)
    line_items: List[ExtractedLineItem] = Field(default_factory=list, max_length=50)
