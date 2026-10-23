import pytest
from app.validation.duplicates import (
    check_duplicate_rules,
    derive_invoice_number_key,
    derive_vendor_key,
)


def test_derive_keys():
    # Valid GSTIN takes precedence
    assert derive_vendor_key("Sharma Traders Pvt Ltd", "27ABCDE1234F1Z0") == "27ABCDE1234F1Z0"
    # Fallback to normalized name with suffixes stripped
    assert derive_vendor_key("Sharma Traders Pvt. Ltd.", None) == "sharma"
    # Invoice number key strips punctuation, keeps case and leading zeros
    assert derive_invoice_number_key("ST/24-25/00142") == "ST242500142"
    assert derive_invoice_number_key("00142") == "00142"


def test_dup_001_exact_duplicate():
    history = [
        {
            "invoice_id": "inv_prior_1",
            "vendor_key": "27ABCDE1234F1Z0",
            "invoice_number_key": "INV001",
            "invoice_date": "2025-03-14",
            "total_paise": 1180000,
            "review_status": "approved",
        }
    ]

    findings = check_duplicate_rules(
        current_invoice_id="inv_current",
        vendor_key="27ABCDE1234F1Z0",
        invoice_number_key="INV001",
        invoice_date="2025-03-14",
        total_paise=1180000,
        history=history,
    )
    dup001 = next((f for f in findings if f["rule_id"] == "DUP-001"), None)
    assert dup001 is not None
    assert dup001["severity"] == "high"
    assert dup001["evidence"]["matched_invoice_id"] == "inv_prior_1"


def test_dup_002_reused_number_diff_total():
    history = [
        {
            "invoice_id": "inv_prior_2",
            "vendor_key": "27ABCDE1234F1Z0",
            "invoice_number_key": "INV001",
            "invoice_date": "2025-03-14",
            "total_paise": 500000,  # Different total
            "review_status": "pending",
        }
    ]

    findings = check_duplicate_rules(
        current_invoice_id="inv_current",
        vendor_key="27ABCDE1234F1Z0",
        invoice_number_key="INV001",
        invoice_date="2025-03-14",
        total_paise=1180000,
        history=history,
    )
    assert any(f["rule_id"] == "DUP-002" and f["severity"] == "medium" for f in findings)


def test_dup_003_same_purchase_diff_number():
    history = [
        {
            "invoice_id": "inv_prior_3",
            "vendor_key": "27ABCDE1234F1Z0",
            "invoice_number_key": "INV999",  # Different number
            "invoice_date": "2025-03-14",
            "total_paise": 1180000,
            "review_status": "flagged",
        }
    ]

    findings = check_duplicate_rules(
        current_invoice_id="inv_current",
        vendor_key="27ABCDE1234F1Z0",
        invoice_number_key="INV001",
        invoice_date="2025-03-14",
        total_paise=1180000,
        history=history,
    )
    assert any(f["rule_id"] == "DUP-003" and f["severity"] == "medium" for f in findings)


def test_duplicate_different_vendor_not_flagged():
    history = [
        {
            "invoice_id": "inv_prior_4",
            "vendor_key": "DIFFERENT_VENDOR",
            "invoice_number_key": "INV001",  # Same number
            "invoice_date": "2025-03-14",
            "total_paise": 1180000,  # Same total
            "review_status": "approved",
        }
    ]

    findings = check_duplicate_rules(
        current_invoice_id="inv_current",
        vendor_key="27ABCDE1234F1Z0",
        invoice_number_key="INV001",
        invoice_date="2025-03-14",
        total_paise=1180000,
        history=history,
    )
    assert len(findings) == 0  # No duplicate finding across different vendors
