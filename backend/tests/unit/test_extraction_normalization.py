import pytest
from app.extraction.base import ExtractionError
from app.extraction.normalise import normalise_extraction_output
from app.schemas.extraction import ExtractionResult, ExtractedField, ExtractedLineItem


def test_normalise_valid_extraction():
    res = ExtractionResult(
        document_type="tax_invoice",
        vendor_name=ExtractedField(value="  Sharma   Traders  ", legibility="clear", evidence="SHARMA TRADERS"),
        vendor_gstin=ExtractedField(value="27-abcde-1234-f1z0", legibility="clear", evidence="27ABCDE1234F1Z0"),
        invoice_number=ExtractedField(value="ST/0142", legibility="clear", evidence="ST/0142"),
        invoice_date=ExtractedField(value="2025-03-14", legibility="clear", evidence="14/03/2025"),
        currency=ExtractedField(value="INR", legibility="clear", evidence="₹"),
        taxable_amount=ExtractedField(value="10,000.00", legibility="clear", evidence="10,000.00"),
        cgst=ExtractedField(value="900.00", legibility="clear", evidence="900.00"),
        sgst=ExtractedField(value="900.00", legibility="clear", evidence="900.00"),
        total_amount=ExtractedField(value="₹ 11,800.00", legibility="clear", evidence="11,800.00"),
    )

    fields, lines, uncertain, raw_json = normalise_extraction_output(res)
    assert fields["vendor_name"] == "Sharma Traders"  # Whitespace collapsed
    assert fields["vendor_gstin"] == "27ABCDE1234F1Z0"  # Hyphens removed, uppercased
    assert fields["taxable_amount"] == "10000.00"  # Commas stripped
    assert fields["total_amount"] == "11800.00"
    assert len(uncertain) == 0


def test_normalise_unclear_field_uncertainty():
    res = ExtractionResult(
        vendor_name=ExtractedField(value="Unclear Vendor", legibility="unclear", evidence="..."),
        total_amount=ExtractedField(value="100.00", legibility="clear", evidence=""),  # no evidence
    )
    fields, lines, uncertain, _ = normalise_extraction_output(res)
    assert any(u["field"] == "vendor_name" and u["reason"] == "legibility_unclear" for u in uncertain)
    assert any(u["field"] == "total_amount" and u["reason"] == "no_evidence" for u in uncertain)


def test_normalise_unparseable_date_and_money():
    raw_dict = {
        "invoice_date": {"value": "not-a-date", "legibility": "clear", "evidence": "bad date"},
        "total_amount": {"value": "invalid-amount", "legibility": "clear", "evidence": "bad total"},
    }
    fields, lines, uncertain, _ = normalise_extraction_output(raw_dict)
    assert fields["invoice_date"] is None
    assert fields["total_amount"] is None
    assert any(u["field"] == "invoice_date" and u["reason"] == "unparseable" for u in uncertain)
    assert any(u["field"] == "total_amount" and u["reason"] == "unparseable" for u in uncertain)


def test_normalise_malformed_string_fails_safely():
    with pytest.raises(ExtractionError) as exc:
        normalise_extraction_output("This is plain English prose, not JSON at all.")
    assert exc.value.code == "AI_BAD_OUTPUT"
