import secrets
from decimal import Decimal
from typing import Any, Dict, List, Optional
from app.validation.money import clean_and_parse_money, format_money
from app.validation.rules_config import DEFAULT_AMOUNT_TOLERANCE_INR, DEFAULT_CGST_SGST_TOLERANCE_INR


def check_tax_rules(
    taxable_val: Any,
    cgst_val: Any,
    sgst_val: Any,
    igst_val: Any,
    total_val: Any,
    line_items: List[Dict[str, Any]],
    amount_tolerance: Decimal = DEFAULT_AMOUNT_TOLERANCE_INR,
    cgst_sgst_tolerance: Decimal = DEFAULT_CGST_SGST_TOLERANCE_INR,
) -> List[Dict[str, Any]]:
    findings = []

    taxable = clean_and_parse_money(taxable_val)
    cgst = clean_and_parse_money(cgst_val)
    sgst = clean_and_parse_money(sgst_val)
    igst = clean_and_parse_money(igst_val)
    total = clean_and_parse_money(total_val)

    # TAX-001: Line items sum vs taxable amount
    line_amounts = [clean_and_parse_money(item.get("amount")) for item in line_items]
    valid_line_amounts = [amt for amt in line_amounts if amt is not None]

    if valid_line_amounts and taxable is not None:
        lines_sum = sum(valid_line_amounts, Decimal("0.00"))
        diff = abs(lines_sum - taxable)
        if diff > amount_tolerance:
            findings.append({
                "finding_id": f"fnd_{secrets.token_hex(6)}",
                "rule_id": "TAX-001",
                "severity": "medium",
                "category": "tax",
                "title": "Line item sum does not match taxable value",
                "explanation": "The sum of extracted line item amounts differs from the taxable value by more than the allowed tolerance. Check for line-level discounts, extra charges, or missed items.",
                "evidence": {
                    "line_items_sum": format_money(lines_sum),
                    "taxable_amount": format_money(taxable),
                    "difference": format_money(diff),
                    "tolerance": format_money(amount_tolerance),
                },
            })

    # TAX-002: Taxable + tax components vs Total amount
    if taxable is not None and total is not None:
        components_present = ["taxable_amount"]
        calc_total = taxable
        if cgst is not None:
            calc_total += cgst
            components_present.append("cgst")
        if sgst is not None:
            calc_total += sgst
            components_present.append("sgst")
        if igst is not None:
            calc_total += igst
            components_present.append("igst")

        diff = abs(calc_total - total)
        if diff > amount_tolerance:
            findings.append({
                "finding_id": f"fnd_{secrets.token_hex(6)}",
                "rule_id": "TAX-002",
                "severity": "high",
                "category": "tax",
                "title": "Total does not match taxable value plus taxes",
                "explanation": "Taxable value plus the extracted tax amounts differs from the invoice total by more than the allowed tolerance. The AI is not used for this calculation. Check for freight, cess, round-off or an extraction error.",
                "evidence": {
                    "taxable_amount": format_money(taxable),
                    "cgst": format_money(cgst),
                    "sgst": format_money(sgst),
                    "igst": format_money(igst),
                    "components_present": components_present,
                    "expected_total": format_money(calc_total),
                    "total_amount": format_money(total),
                    "difference": format_money(diff),
                    "tolerance": format_money(amount_tolerance),
                },
            })

    # TAX-003: CGST and SGST balance
    if cgst is not None and sgst is not None:
        diff_cgst_sgst = abs(cgst - sgst)
        if diff_cgst_sgst > cgst_sgst_tolerance:
            findings.append({
                "finding_id": f"fnd_{secrets.token_hex(6)}",
                "rule_id": "TAX-003",
                "severity": "medium",
                "category": "tax",
                "title": "CGST and SGST amounts do not match",
                "explanation": "CGST and SGST on intra-state supplies must be equal at the invoice level. Check for per-item rounding differences or partial tax components.",
                "evidence": {
                    "cgst": format_money(cgst),
                    "sgst": format_money(sgst),
                    "difference": format_money(diff_cgst_sgst),
                    "tolerance": format_money(cgst_sgst_tolerance),
                },
            })

    # TAX-004: Mixed IGST and CGST/SGST
    if igst is not None and igst > Decimal("0.00"):
        has_cgst = cgst is not None and cgst > Decimal("0.00")
        has_sgst = sgst is not None and sgst > Decimal("0.00")
        if has_cgst or has_sgst:
            findings.append({
                "finding_id": f"fnd_{secrets.token_hex(6)}",
                "rule_id": "TAX-004",
                "severity": "medium",
                "category": "tax",
                "title": "Mixed IGST and CGST/SGST on same invoice",
                "explanation": "Invoice contains both inter-state tax (IGST) and intra-state taxes (CGST/SGST). Mixed supplies on one document are unusual.",
                "evidence": {
                    "cgst": format_money(cgst),
                    "sgst": format_money(sgst),
                    "igst": format_money(igst),
                },
            })

    return findings
