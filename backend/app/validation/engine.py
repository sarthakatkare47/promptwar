from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.validation.dates import check_date_rules
from app.validation.duplicates import (
    check_duplicate_rules,
    derive_invoice_number_key,
    derive_vendor_key,
)
from app.validation.extraction_rules import check_extraction_rules
from app.validation.gstin import check_gstin_rules
from app.validation.injection import check_injection_heuristic
from app.validation.money import str_to_paise
from app.validation.risk import calculate_risk
from app.validation.rules_config import (
    DEFAULT_AMOUNT_TOLERANCE_INR,
    DEFAULT_CGST_SGST_TOLERANCE_INR,
    DEFAULT_OLD_INVOICE_DAYS,
)
from app.validation.tax import check_tax_rules


@dataclass
class ScanResult:
    findings: List[Dict[str, Any]]
    risk_score: int
    risk_level: str
    recommendation: str
    risk_breakdown: List[Dict[str, Any]]
    vendor_key: str
    invoice_number_key: str


def scan_invoice(
    invoice_id: str,
    fields: Dict[str, Any],
    line_items: List[Dict[str, Any]],
    history: List[Dict[str, Any]],
    uncertain_fields: List[Dict[str, str]],
    document_type: Optional[str] = None,
    today: Optional[date] = None,
    amount_tolerance: Decimal = DEFAULT_AMOUNT_TOLERANCE_INR,
    cgst_sgst_tolerance: Decimal = DEFAULT_CGST_SGST_TOLERANCE_INR,
    old_invoice_days: int = DEFAULT_OLD_INVOICE_DAYS,
) -> ScanResult:
    """
    Pure validation function: (invoice, history, config, today) -> findings and risk.
    Has NO side-effects, does NO database or AI operations.
    """
    findings: List[Dict[str, Any]] = []

    # 1. GSTIN Rules (GST-001 ... GST-004)
    has_tax = bool(fields.get("cgst") or fields.get("sgst") or fields.get("igst"))
    findings.extend(
        check_gstin_rules(
            vendor_gstin_raw=fields.get("vendor_gstin"),
            buyer_gstin_raw=fields.get("buyer_gstin"),
            has_tax_amounts=has_tax,
        )
    )

    # 2. Tax Arithmetic Rules (TAX-001 ... TAX-004)
    findings.extend(
        check_tax_rules(
            taxable_val=fields.get("taxable_amount"),
            cgst_val=fields.get("cgst"),
            sgst_val=fields.get("sgst"),
            igst_val=fields.get("igst"),
            total_val=fields.get("total_amount"),
            line_items=line_items,
            amount_tolerance=amount_tolerance,
            cgst_sgst_tolerance=cgst_sgst_tolerance,
        )
    )

    # 3. Date Rules (DATE-002, DATE-003)
    findings.extend(
        check_date_rules(
            invoice_date_raw=fields.get("invoice_date"),
            today=today,
            old_invoice_days=old_invoice_days,
        )
    )

    # 4. Extraction & Uncertainty Rules (EXT-001 ... EXT-003)
    findings.extend(
        check_extraction_rules(
            fields=fields,
            uncertain_fields=uncertain_fields,
            document_type=document_type,
        )
    )

    # 5. Prompt Injection Heuristic (INJ-001)
    findings.extend(
        check_injection_heuristic(
            fields=fields,
            line_items=line_items,
        )
    )

    # 6. Duplicate Detection Rules (DUP-001 ... DUP-003)
    vendor_key = derive_vendor_key(fields.get("vendor_name"), fields.get("vendor_gstin"))
    invoice_number_key = derive_invoice_number_key(fields.get("invoice_number"))
    total_paise = str_to_paise(fields.get("total_amount"))

    findings.extend(
        check_duplicate_rules(
            current_invoice_id=invoice_id,
            vendor_key=vendor_key,
            invoice_number_key=invoice_number_key,
            invoice_date=fields.get("invoice_date"),
            total_paise=total_paise,
            history=history,
        )
    )

    # 7. Transparent Risk Calculation
    score, level, recommendation, breakdown = calculate_risk(findings)

    return ScanResult(
        findings=findings,
        risk_score=score,
        risk_level=level,
        recommendation=recommendation,
        risk_breakdown=breakdown,
        vendor_key=vendor_key,
        invoice_number_key=invoice_number_key,
    )
