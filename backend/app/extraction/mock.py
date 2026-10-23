import hashlib
import json
from pathlib import Path
from typing import Optional
from app.config import settings
from app.extraction.base import ExtractorOutput, ExtractionError
from app.schemas.extraction import ExtractionResult, ExtractedField, ExtractedLineItem


class MockExtractor:
    def __init__(self, forced_error: Optional[str] = None):
        self.forced_error = forced_error

    async def extract(self, file_bytes: bytes, mime_type: str) -> ExtractorOutput:
        if self.forced_error:
            if self.forced_error == "AI_TIMEOUT":
                raise ExtractionError("AI_TIMEOUT", "Simulated extraction timeout.", retryable=True)
            elif self.forced_error == "AI_RATE_LIMITED":
                raise ExtractionError("AI_RATE_LIMITED", "Simulated AI rate limit (429).", retryable=True)
            elif self.forced_error == "AI_BAD_OUTPUT":
                raise ExtractionError("AI_BAD_OUTPUT", "Simulated malformed model output.", retryable=False)
            elif self.forced_error == "AI_NOT_CONFIGURED":
                raise ExtractionError("AI_NOT_CONFIGURED", "Simulated missing API key.", retryable=False)
            elif self.forced_error == "AI_UNAVAILABLE":
                raise ExtractionError("AI_UNAVAILABLE", "Simulated upstream service error (503).", retryable=True)
            else:
                raise ExtractionError(self.forced_error, f"Forced error {self.forced_error}")

        # Check for canned fixture in fixtures dir by file hash
        file_sha256 = hashlib.sha256(file_bytes).hexdigest()
        fixtures_dir = Path(__file__).resolve().parent.parent.parent / settings.MOCK_FIXTURES_DIR
        fixture_file = fixtures_dir / f"{file_sha256}.json"
        
        if fixture_file.exists():
            try:
                with open(fixture_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                res = ExtractionResult.model_validate(data)
                return ExtractorOutput(
                    result=res,
                    model="mock-fixture",
                    latency_ms=15,
                    input_tokens=100,
                    output_tokens=50,
                )
            except Exception:
                pass

        # Check benchmark dataset labels by sha256
        manifest_path = Path(__file__).resolve().parent.parent.parent / "benchmark" / "dataset" / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                for entry in manifest.get("entries", []):
                    if entry.get("image_sha256") == file_sha256:
                        label_file = manifest_path.parent / entry["label_path"]
                        if label_file.exists():
                            with open(label_file, "r", encoding="utf-8") as lf:
                                lbl = json.load(lf)
                            lbl_fields = lbl.get("fields", {})
                            lbl_items = lbl.get("line_items", [])
                            res = ExtractionResult(
                                document_type="tax_invoice",
                                vendor_name=ExtractedField(value=lbl_fields.get("vendor_name"), legibility="clear"),
                                vendor_gstin=ExtractedField(value=lbl_fields.get("vendor_gstin"), legibility="clear"),
                                buyer_gstin=ExtractedField(value=lbl_fields.get("buyer_gstin"), legibility="clear"),
                                invoice_number=ExtractedField(value=lbl_fields.get("invoice_number"), legibility="clear"),
                                invoice_date=ExtractedField(value=lbl_fields.get("invoice_date"), legibility="clear"),
                                currency=ExtractedField(value=lbl_fields.get("currency", "INR"), legibility="clear"),
                                taxable_amount=ExtractedField(value=lbl_fields.get("taxable_amount"), legibility="clear"),
                                cgst=ExtractedField(value=lbl_fields.get("cgst"), legibility="clear"),
                                sgst=ExtractedField(value=lbl_fields.get("sgst"), legibility="clear"),
                                igst=ExtractedField(value=lbl_fields.get("igst"), legibility="clear"),
                                total_amount=ExtractedField(value=lbl_fields.get("total_amount"), legibility="clear"),
                                line_items=[
                                    ExtractedLineItem(
                                        description=it.get("description", "Item"),
                                        quantity=it.get("quantity"),
                                        unit_price=it.get("unit_price"),
                                        amount=it.get("amount"),
                                    )
                                    for it in lbl_items
                                ],
                            )
                            return ExtractorOutput(
                                result=res,
                                model="mock-benchmark-label",
                                latency_ms=10,
                                input_tokens=150,
                                output_tokens=80,
                            )
            except Exception:
                pass

        # Default clean invoice extraction result
        default_result = ExtractionResult(
            document_type="tax_invoice",
            vendor_name=ExtractedField(value="Sharma Traders", legibility="clear", evidence="SHARMA TRADERS"),
            vendor_gstin=ExtractedField(value="27ABCDE1234F1Z0", legibility="clear", evidence="GSTIN: 27ABCDE1234F1Z0"),
            buyer_gstin=ExtractedField(value="27XYZAB5678C1Z6", legibility="clear", evidence="Buyer GSTIN: 27XYZAB5678C1Z6"),
            invoice_number=ExtractedField(value="ST/24-25/0142", legibility="clear", evidence="Invoice No: ST/24-25/0142"),
            invoice_date=ExtractedField(value="2025-03-14", legibility="clear", evidence="Date: 14/03/2025"),
            currency=ExtractedField(value="INR", legibility="clear", evidence="₹"),
            taxable_amount=ExtractedField(value="10000.00", legibility="clear", evidence="Taxable Value: 10,000.00"),
            cgst=ExtractedField(value="900.00", legibility="clear", evidence="CGST 9%: 900.00"),
            sgst=ExtractedField(value="900.00", legibility="clear", evidence="SGST 9%: 900.00"),
            igst=ExtractedField(value=None, legibility="not_found", evidence=None),
            total_amount=ExtractedField(value="11800.00", legibility="clear", evidence="Total Amount: 11,800.00"),
            line_items=[
                ExtractedLineItem(
                    description="Steel bolts M8",
                    hsn_sac="7318",
                    quantity="100",
                    unit_price="100.00",
                    amount="10000.00",
                )
            ],
        )

        return ExtractorOutput(
            result=default_result,
            model="mock-default",
            latency_ms=25,
            input_tokens=500,
            output_tokens=120,
        )
