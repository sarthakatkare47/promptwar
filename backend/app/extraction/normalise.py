import re
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.extraction.base import ExtractionError
from app.schemas.extraction import ExtractionResult
from app.validation.dates import parse_iso_date
from app.validation.money import clean_and_parse_money, format_money


DATE_AMBIGUOUS_REGEX = re.compile(r"\b(0?[1-9]|1[0-2])[/\-\.](0?[1-9]|1[0-2])[/\-\.](20\d\d|\d\d)\b")


def normalise_extraction_output(raw_output: Any) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, str]], str]:
    """
    Validates raw model output with Pydantic and applies local normalization.
    Returns:
    (fields_dict, line_items_list, uncertain_fields_list, raw_json_string)
    """
    if isinstance(raw_output, str):
        try:
            model_res = ExtractionResult.model_validate_json(raw_output)
            raw_json_str = raw_output
        except Exception as e:
            raise ExtractionError(
                code="AI_BAD_OUTPUT",
                message="Model output could not be parsed into the expected extraction schema.",
            )
    elif isinstance(raw_output, dict):
        try:
            model_res = ExtractionResult.model_validate(raw_output)
            raw_json_str = model_res.model_dump_json()
        except Exception as e:
            raise ExtractionError(
                code="AI_BAD_OUTPUT",
                message="Model output could not be validated against the extraction schema.",
            )
    elif isinstance(raw_output, ExtractionResult):
        model_res = raw_output
        raw_json_str = model_res.model_dump_json()
    else:
        raise ExtractionError(
            code="AI_BAD_OUTPUT",
            message=f"Unsupported raw model output type: {type(raw_output).__name__}",
        )

    uncertain_fields: List[Dict[str, str]] = []

    def process_text_field(field_name: str, extracted) -> Optional[str]:
        if not extracted or extracted.value is None:
            return None
        val_str = str(extracted.value).strip()
        if not val_str:
            return None

        # Check legibility
        if extracted.legibility == "unclear":
            uncertain_fields.append({"field": field_name, "reason": "legibility_unclear"})
        elif not extracted.evidence or not extracted.evidence.strip():
            uncertain_fields.append({"field": field_name, "reason": "no_evidence"})

        return val_str

    # 1. Text fields
    v_name = process_text_field("vendor_name", model_res.vendor_name)
    if v_name:
        v_name = " ".join(v_name.split())[:200]

    v_gstin = process_text_field("vendor_gstin", model_res.vendor_gstin)
    if v_gstin:
        v_gstin = re.sub(r"[\s\-]", "", v_gstin).upper()[:15]

    b_gstin = process_text_field("buyer_gstin", model_res.buyer_gstin)
    if b_gstin:
        b_gstin = re.sub(r"[\s\-]", "", b_gstin).upper()[:15]

    inv_num = process_text_field("invoice_number", model_res.invoice_number)
    if inv_num:
        inv_num = inv_num[:64]

    # 2. Date field
    inv_date_str = process_text_field("invoice_date", model_res.invoice_date)
    final_date_str = None
    if inv_date_str:
        parsed_d = parse_iso_date(inv_date_str)
        if parsed_d:
            final_date_str = parsed_d.isoformat()
            # Check ambiguous date heuristic
            ev = (model_res.invoice_date.evidence or "")
            if DATE_AMBIGUOUS_REGEX.search(ev):
                uncertain_fields.append({"field": "invoice_date", "reason": "ambiguous_date"})
        else:
            uncertain_fields.append({"field": "invoice_date", "reason": "unparseable"})

    # 3. Currency
    currency_assumed = False
    curr_val = process_text_field("currency", model_res.currency)
    if not curr_val or curr_val.upper() not in ("INR", "USD", "EUR", "GBP"):
        curr_val = "INR"
        currency_assumed = True

    # 4. Monetary amounts
    def process_money_field(field_name: str, extracted) -> Optional[str]:
        raw_val = process_text_field(field_name, extracted)
        if raw_val is None:
            return None
        parsed_m = clean_and_parse_money(raw_val)
        if parsed_m is None:
            uncertain_fields.append({"field": field_name, "reason": "unparseable"})
            return None
        return format_money(parsed_m)

    taxable = process_money_field("taxable_amount", model_res.taxable_amount)
    cgst = process_money_field("cgst", model_res.cgst)
    sgst = process_money_field("sgst", model_res.sgst)
    igst = process_money_field("igst", model_res.igst)
    total = process_money_field("total_amount", model_res.total_amount)

    # 5. Line items
    line_items: List[Dict[str, Any]] = []
    if len(model_res.line_items) >= 50:
        uncertain_fields.append({"field": "line_items", "reason": "line_items_truncated"})

    for idx, item in enumerate(model_res.line_items[:50], start=1):
        d_val = clean_and_parse_money(item.amount) if item.amount else None
        u_val = clean_and_parse_money(item.unit_price) if item.unit_price else None
        line_items.append({
            "line_no": idx,
            "description": str(item.description or "").strip()[:300] or None,
            "hsn_sac": str(item.hsn_sac or "").strip()[:16] or None,
            "quantity": str(item.quantity or "").strip() if item.quantity else None,
            "unit_price": format_money(u_val) if u_val else None,
            "amount": format_money(d_val) if d_val else None,
        })

    fields = {
        "vendor_name": v_name,
        "vendor_gstin": v_gstin,
        "buyer_gstin": b_gstin,
        "invoice_number": inv_num,
        "invoice_date": final_date_str,
        "currency": curr_val,
        "currency_assumed": currency_assumed,
        "taxable_amount": taxable,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "total_amount": total,
    }

    return fields, line_items, uncertain_fields, raw_json_str
