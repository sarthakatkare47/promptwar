import re
import secrets
from typing import Any, Dict, List, Optional
from app.validation.gstin import is_valid_gstin_format, normalize_gstin

VENDOR_SUFFIXES = [
    r"\bprivate\s+limited\b",
    r"\bpvt\.?\s*ltd\.?\b",
    r"\blimited\b",
    r"\bltd\.?\b",
    r"\bllp\b",
    r"\benterprises\b",
    r"\btraders\b",
    r"\bcompany\b",
    r"\bco\.?\b",
]


def derive_vendor_key(vendor_name: Optional[str], vendor_gstin: Optional[str]) -> str:
    gstin = normalize_gstin(vendor_gstin)
    if gstin and is_valid_gstin_format(gstin):
        return gstin

    if not vendor_name:
        return ""

    s = vendor_name.lower().strip()
    for suffix in VENDOR_SUFFIXES:
        s = re.sub(suffix, "", s, flags=re.IGNORECASE)
    
    # Strip non-alphanumerics
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def derive_invoice_number_key(invoice_number: Optional[str]) -> str:
    if not invoice_number:
        return ""
    # Retain all alphanumerics in uppercase, keeping leading zeros
    return re.sub(r"[^A-Za-z0-9]", "", str(invoice_number)).upper()


def check_duplicate_rules(
    current_invoice_id: str,
    vendor_key: str,
    invoice_number_key: str,
    invoice_date: Optional[str],
    total_paise: Optional[int],
    history: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    findings = []
    if not vendor_key:
        return findings

    for prior in history:
        prior_id = prior.get("invoice_id")
        if prior_id == current_invoice_id:
            continue

        p_vendor = prior.get("vendor_key")
        if not p_vendor or p_vendor != vendor_key:
            continue  # Different vendor -> never a duplicate

        p_num = prior.get("invoice_number_key")
        p_date = prior.get("invoice_date")
        p_total = prior.get("total_paise")
        p_status = prior.get("review_status", "pending")

        # DUP-001: Exact duplicate business key (same vendor, number, date, total)
        if invoice_number_key and p_num and invoice_number_key == p_num:
            if invoice_date and p_date and invoice_date == p_date and total_paise is not None and p_total == total_paise:
                findings.append({
                    "finding_id": f"fnd_{secrets.token_hex(6)}",
                    "rule_id": "DUP-001",
                    "severity": "high",
                    "category": "duplicate",
                    "title": "Exact duplicate invoice details detected",
                    "explanation": f"An invoice with the same vendor, invoice number, date, and total was previously processed (Invoice ID: {prior_id}, Status: {p_status}). Review before paying twice.",
                    "evidence": {
                        "matched_invoice_id": prior_id,
                        "matched_review_status": p_status,
                        "vendor_key": vendor_key,
                        "invoice_number_key": invoice_number_key,
                    },
                })
                break  # Don't duplicate flags for the same invoice

            # DUP-002: Same vendor and number, but different date or total
            elif (invoice_date != p_date) or (total_paise != p_total):
                findings.append({
                    "finding_id": f"fnd_{secrets.token_hex(6)}",
                    "rule_id": "DUP-002",
                    "severity": "medium",
                    "category": "duplicate",
                    "title": "Invoice number reuse with differing date or total",
                    "explanation": f"The invoice number was previously used by this vendor with a different date or total (Invoice ID: {prior_id}). Invoice numbers may restart each financial year, or this may be a re-issued document.",
                    "evidence": {
                        "matched_invoice_id": prior_id,
                        "matched_review_status": p_status,
                        "vendor_key": vendor_key,
                        "invoice_number_key": invoice_number_key,
                    },
                })
                break

        # DUP-003: Same vendor, date, total, but different invoice number
        elif invoice_number_key and p_num and invoice_number_key != p_num:
            if invoice_date and p_date and invoice_date == p_date and total_paise is not None and p_total == total_paise:
                findings.append({
                    "finding_id": f"fnd_{secrets.token_hex(6)}",
                    "rule_id": "DUP-003",
                    "severity": "medium",
                    "category": "duplicate",
                    "title": "Identical supplier purchase with different invoice number",
                    "explanation": f"Another invoice from the same vendor on the same date for the exact same amount exists under a different invoice number (Invoice ID: {prior_id}). Could indicate two purchases or a re-issued bill.",
                    "evidence": {
                        "matched_invoice_id": prior_id,
                        "matched_review_status": p_status,
                        "vendor_key": vendor_key,
                    },
                })
                break

    return findings
