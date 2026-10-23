from decimal import Decimal
import pytest
from app.validation.tax import check_tax_rules


def test_tax_rules_clean_case():
    findings = check_tax_rules(
        taxable_val="10000.00",
        cgst_val="900.00",
        sgst_val="900.00",
        igst_val=None,
        total_val="11800.00",
        line_items=[{"amount": "10000.00"}],
    )
    assert len(findings) == 0


def test_tax_001_line_sum_mismatch():
    findings = check_tax_rules(
        taxable_val="10000.00",
        cgst_val="900.00",
        sgst_val="900.00",
        igst_val=None,
        total_val="11800.00",
        line_items=[{"amount": "5000.00"}, {"amount": "4000.00"}],  # sum is 9000 != 10000
    )
    assert any(f["rule_id"] == "TAX-001" and f["severity"] == "medium" for f in findings)


def test_tax_002_boundary_tolerance():
    # Tolerance is 1.00 INR
    # Diff = 1.00 passes
    findings_pass = check_tax_rules(
        taxable_val="10000.00",
        cgst_val="900.00",
        sgst_val="900.00",
        igst_val=None,
        total_val="11801.00",  # diff exactly 1.00
        line_items=[],
    )
    assert not any(f["rule_id"] == "TAX-002" for f in findings_pass)

    # Diff = 1.01 fails
    findings_fail = check_tax_rules(
        taxable_val="10000.00",
        cgst_val="900.00",
        sgst_val="900.00",
        igst_val=None,
        total_val="11801.01",  # diff 1.01
        line_items=[],
    )
    tax002 = next((f for f in findings_fail if f["rule_id"] == "TAX-002"), None)
    assert tax002 is not None
    assert tax002["severity"] == "high"


def test_tax_003_cgst_sgst_mismatch_boundary():
    # CGST/SGST tolerance is 0.05
    findings_pass = check_tax_rules(
        taxable_val="1000.00",
        cgst_val="90.00",
        sgst_val="90.05",  # diff 0.05
        igst_val=None,
        total_val="1180.05",
        line_items=[],
    )
    assert not any(f["rule_id"] == "TAX-003" for f in findings_pass)

    findings_fail = check_tax_rules(
        taxable_val="1000.00",
        cgst_val="90.00",
        sgst_val="90.06",  # diff 0.06
        igst_val=None,
        total_val="1180.06",
        line_items=[],
    )
    assert any(f["rule_id"] == "TAX-003" for f in findings_fail)


def test_tax_004_mixed_igst_and_cgst():
    findings = check_tax_rules(
        taxable_val="10000.00",
        cgst_val="500.00",
        sgst_val=None,
        igst_val="1000.00",
        total_val="11500.00",
        line_items=[],
    )
    assert any(f["rule_id"] == "TAX-004" and f["severity"] == "medium" for f in findings)
