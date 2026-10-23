import re
import secrets
from typing import Any, Dict, List, Optional
from app.validation.rules_config import VALID_STATE_CODES

GSTIN_REGEX = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def normalize_gstin(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    return re.sub(r"[\s\-]", "", str(val)).upper()


def is_valid_gstin_format(gstin: str) -> bool:
    return bool(GSTIN_REGEX.match(gstin))


def compute_gstin_checksum(first_14: str) -> str:
    total = 0
    for i, c in enumerate(first_14):
        val = CHARS.index(c)
        factor = 1 if (i + 1) % 2 != 0 else 2
        product = val * factor
        total += (product // 36) + (product % 36)
    rem = total % 36
    check_val = (36 - rem) % 36
    return CHARS[check_val]


def check_gstin_rules(
    vendor_gstin_raw: Optional[str],
    buyer_gstin_raw: Optional[str] = None,
    has_tax_amounts: bool = False,
) -> List[Dict[str, Any]]:
    findings = []
    
    # Check vendor GSTIN presence (GST-004)
    vendor_gstin = normalize_gstin(vendor_gstin_raw)
    if not vendor_gstin:
        severity = "medium" if has_tax_amounts else "low"
        findings.append({
            "finding_id": f"fnd_{secrets.token_hex(6)}",
            "rule_id": "GST-004",
            "severity": severity,
            "category": "gstin",
            "title": "Vendor GSTIN is missing",
            "explanation": "No vendor GSTIN was found on the invoice. Unregistered or composition suppliers may legitimately have none, but input tax credit requires a valid registration.",
            "evidence": {"tax_amounts_present": has_tax_amounts},
        })
    else:
        # Check vendor GSTIN format and checksum
        _evaluate_single_gstin("vendor_gstin", vendor_gstin, findings)

    # Check buyer GSTIN if present
    buyer_gstin = normalize_gstin(buyer_gstin_raw)
    if buyer_gstin:
        _evaluate_single_gstin("buyer_gstin", buyer_gstin, findings)

    return findings


def _evaluate_single_gstin(field_name: str, gstin: str, findings: List[Dict[str, Any]]) -> None:
    # GST-001: Format check
    if not is_valid_gstin_format(gstin):
        findings.append({
            "finding_id": f"fnd_{secrets.token_hex(6)}",
            "rule_id": "GST-001",
            "severity": "high",
            "category": "gstin",
            "title": f"{field_name.replace('_', ' ').title()} format is invalid",
            "explanation": "The GSTIN does not match the standard 15-character layout (2 state digits, 10 PAN alphanumerics, 1 entity code, 'Z', and 1 check character).",
            "evidence": {"field": field_name, "value": gstin},
        })
        return  # Format invalid -> skip checksum and state checks

    # GST-002: Checksum check
    expected_check = compute_gstin_checksum(gstin[:14])
    if gstin[14] != expected_check:
        findings.append({
            "finding_id": f"fnd_{secrets.token_hex(6)}",
            "rule_id": "GST-002",
            "severity": "high",
            "category": "gstin",
            "title": "GSTIN check character does not match",
            "explanation": "The last character of the GSTIN does not match the value calculated from the first 14 characters. This can indicate a typing or scanning error, or an invalid number. It does not prove fraud, and a match does not prove active registration.",
            "evidence": {
                "field": field_name,
                "value": gstin,
                "expected_check_character": expected_check,
            },
        })

    # GST-003: State code check
    state_code = gstin[:2]
    if state_code not in VALID_STATE_CODES:
        findings.append({
            "finding_id": f"fnd_{secrets.token_hex(6)}",
            "rule_id": "GST-003",
            "severity": "medium",
            "category": "gstin",
            "title": "GSTIN state code is invalid",
            "explanation": "The first two digits of the GSTIN do not correspond to a valid Indian State or Union Territory code.",
            "evidence": {"field": field_name, "state_code": state_code},
        })
