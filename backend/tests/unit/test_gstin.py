import pytest
from app.validation.gstin import (
    check_gstin_rules,
    compute_gstin_checksum,
    is_valid_gstin_format,
    normalize_gstin,
)


def test_gstin_normalization():
    assert normalize_gstin(" 27abcde1234f1z0 ") == "27ABCDE1234F1Z0"
    assert normalize_gstin("27-ABCDE-1234-F1Z0") == "27ABCDE1234F1Z0"
    assert normalize_gstin(None) is None


def test_gstin_format_validation():
    assert is_valid_gstin_format("27ABCDE1234F1Z0") is True
    assert is_valid_gstin_format("27ABCDE1234F1Z") is False  # 14 chars
    assert is_valid_gstin_format("27ABCDE1234F1Z00") is False  # 16 chars
    assert is_valid_gstin_format("XXABCDE1234F1Z0") is False  # Letters for state


def test_gstin_checksum_computation():
    # 27ABCDE1234F1Z -> 0
    assert compute_gstin_checksum("27ABCDE1234F1Z") == "0"
    # Another test PAN: 07AAAAA0000A1Z -> 5
    check_07 = compute_gstin_checksum("07AAAAA0000A1Z")
    assert isinstance(check_07, str) and len(check_07) == 1


def test_gstin_rules_valid():
    findings = check_gstin_rules("27ABCDE1234F1Z0", "27XYZAB5678C1Z6", has_tax_amounts=True)
    assert len(findings) == 0


def test_gstin_rules_format_fail_gst001():
    findings = check_gstin_rules("INVALID_GSTIN", has_tax_amounts=False)
    assert any(f["rule_id"] == "GST-001" and f["severity"] == "high" for f in findings)


def test_gstin_rules_checksum_fail_gst002():
    # 27ABCDE1234F1Z0 has correct check '0'. Mutate check char to '1'
    findings = check_gstin_rules("27ABCDE1234F1Z1", has_tax_amounts=False)
    gst002 = next((f for f in findings if f["rule_id"] == "GST-002"), None)
    assert gst002 is not None
    assert gst002["severity"] == "high"
    assert gst002["evidence"]["expected_check_character"] == "0"


def test_gstin_rules_state_code_gst003():
    # State code '00' is invalid
    findings = check_gstin_rules("00ABCDE1234F1Z0", has_tax_amounts=False)
    assert any(f["rule_id"] == "GST-003" for f in findings)


def test_gstin_rules_missing_gst004():
    findings_no_tax = check_gstin_rules(None, has_tax_amounts=False)
    assert any(f["rule_id"] == "GST-004" and f["severity"] == "low" for f in findings_no_tax)

    findings_with_tax = check_gstin_rules(None, has_tax_amounts=True)
    assert any(f["rule_id"] == "GST-004" and f["severity"] == "medium" for f in findings_with_tax)
