import json
import secrets
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.db.connection import get_connection, get_transaction
from app.db.repository import InvoiceRepository
from app.errors import AppError
from app.validation.engine import scan_invoice
from app.validation.money import clean_and_parse_money, format_money


VALID_FIELD_KEYS = {
    "vendor_name",
    "vendor_gstin",
    "buyer_gstin",
    "invoice_number",
    "invoice_date",
    "currency",
    "taxable_amount",
    "cgst",
    "sgst",
    "igst",
    "total_amount",
}


def patch_invoice(
    invoice_id: str,
    fields_patch: Optional[Dict[str, Optional[str]]] = None,
    confirmed_fields: Optional[List[str]] = None,
    line_items_patch: Optional[List[Dict[str, Any]]] = None,
    owner_id: str = "local",
) -> Dict[str, Any]:
    with get_connection() as conn:
        inv = InvoiceRepository.get_by_id(conn, invoice_id, owner_id)
        if not inv:
            raise AppError("NOT_FOUND", f"Invoice '{invoice_id}' not found.", status_code=404)

        if inv["review_status"] in ("approved", "rejected"):
            raise AppError(
                "INVOICE_LOCKED",
                f"Invoice is locked in '{inv['review_status']}' status. Reopen it to make corrections.",
                status_code=409,
            )

    curr_fields = dict(inv["fields"])
    uncertain_fields = list(inv["uncertain_fields"])
    changes: List[Dict[str, Any]] = []

    # Process field corrections
    if fields_patch:
        for k, v in fields_patch.items():
            if k not in VALID_FIELD_KEYS:
                raise AppError(
                    "VALIDATION_ERROR",
                    f"Field '{k}' is not editable.",
                    status_code=422,
                )
            old_val = curr_fields.get(k)
            # Format amounts properly
            if k in ("taxable_amount", "cgst", "sgst", "igst", "total_amount"):
                new_val = format_money(clean_and_parse_money(v)) if v else None
            else:
                new_val = str(v).strip() if v else None

            if old_val != new_val:
                changes.append({"field": k, "old": old_val, "new": new_val})
                curr_fields[k] = new_val
                # Remove uncertainty marker for this field
                uncertain_fields = [u for u in uncertain_fields if u["field"] != k]

    # Process confirmed fields ("I checked this")
    if confirmed_fields:
        for f_name in confirmed_fields:
            if f_name in VALID_FIELD_KEYS:
                uncertain_fields = [u for u in uncertain_fields if u["field"] != f_name]

    # Process line items replacement if provided
    final_line_items = line_items_patch if line_items_patch is not None else inv["line_items"]

    if not changes and not confirmed_fields and line_items_patch is None:
        return inv  # No changes -> no-op

    # Re-run validation rules
    new_run = inv["validation_run"] + 1
    with get_connection() as conn:
        history = InvoiceRepository.get_history_for_duplicate_check(conn, owner_id, exclude_invoice_id=invoice_id)

    scan_res = scan_invoice(
        invoice_id=invoice_id,
        fields=curr_fields,
        line_items=final_line_items,
        history=history,
        uncertain_fields=uncertain_fields,
        document_type=inv.get("document_type"),
        amount_tolerance=settings.AMOUNT_TOLERANCE_INR,
        cgst_sgst_tolerance=settings.CGST_SGST_TOLERANCE_INR,
        old_invoice_days=settings.OLD_INVOICE_DAYS,
    )

    extraction_source = "manual" if inv["processing_status"] == "failed" else None

    with get_transaction() as conn:
        InvoiceRepository.update_fields_revalidate(
            conn=conn,
            invoice_id=invoice_id,
            fields=curr_fields,
            vendor_key=scan_res.vendor_key,
            invoice_number_key=scan_res.invoice_number_key,
            uncertain_fields=uncertain_fields,
            risk_score=scan_res.risk_score,
            risk_level=scan_res.risk_level,
            recommendation=scan_res.recommendation,
            validation_run=new_run,
            line_items=final_line_items,
            findings=scan_res.findings,
            extraction_source=extraction_source,
        )
        # Audit event for field correction
        InvoiceRepository.add_audit_event(
            conn=conn,
            event_id=f"evt_{secrets.token_hex(6)}",
            invoice_id=invoice_id,
            event_type="field_corrected",
            actor="local_user",
            details={
                "changes": changes,
                "confirmed_fields": confirmed_fields or [],
                "validation_run": new_run,
            },
        )
        # Audit event for validation completion
        InvoiceRepository.add_audit_event(
            conn=conn,
            event_id=f"evt_{secrets.token_hex(6)}",
            invoice_id=invoice_id,
            event_type="validation_completed",
            actor="system",
            details={
                "validation_run": new_run,
                "risk_level": scan_res.risk_level,
                "score": scan_res.risk_score,
                "rule_ids": [f["rule_id"] for f in scan_res.findings],
            },
        )

    with get_connection() as conn:
        return InvoiceRepository.get_by_id(conn, invoice_id, owner_id)


def review_invoice(
    invoice_id: str,
    action: str,
    comment: Optional[str] = None,
    acknowledge_risk: bool = False,
    owner_id: str = "local",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    with get_connection() as conn:
        inv = InvoiceRepository.get_by_id(conn, invoice_id, owner_id)
        if not inv:
            raise AppError("NOT_FOUND", f"Invoice '{invoice_id}' not found.", status_code=404)

    curr_status = inv["review_status"]
    proc_status = inv["processing_status"]
    risk_level = inv["risk"]["level"]

    next_status = None
    event_type = None

    if curr_status == "pending":
        if action == "approve":
            if proc_status != "ready":
                raise AppError(
                    "VALIDATION_ERROR",
                    f"Invoice cannot be approved while processing status is '{proc_status}'.",
                    status_code=422,
                )
            if risk_level == "high":
                if not acknowledge_risk:
                    raise AppError(
                        "VALIDATION_ERROR",
                        "High-risk invoice approval requires explicit acknowledge_risk: true.",
                        status_code=422,
                    )
                if not comment or not comment.strip():
                    raise AppError(
                        "VALIDATION_ERROR",
                        "High-risk invoice approval requires an explanation comment.",
                        status_code=422,
                    )
            next_status = "approved"
            event_type = "review_approved"
        elif action == "flag":
            if not comment or not comment.strip():
                raise AppError("VALIDATION_ERROR", "Flagging an invoice requires a comment.", status_code=422)
            next_status = "flagged"
            event_type = "review_flagged"
        elif action == "reject":
            if not comment or not comment.strip():
                raise AppError("VALIDATION_ERROR", "Rejecting an invoice requires a comment.", status_code=422)
            next_status = "rejected"
            event_type = "review_rejected"

    elif curr_status == "flagged":
        if action == "approve":
            if proc_status != "ready":
                raise AppError(
                    "VALIDATION_ERROR",
                    f"Invoice cannot be approved while processing status is '{proc_status}'.",
                    status_code=422,
                )
            if risk_level == "high":
                if not acknowledge_risk:
                    raise AppError(
                        "VALIDATION_ERROR",
                        "High-risk invoice approval requires explicit acknowledge_risk: true.",
                        status_code=422,
                    )
                if not comment or not comment.strip():
                    raise AppError(
                        "VALIDATION_ERROR",
                        "High-risk invoice approval requires an explanation comment.",
                        status_code=422,
                    )
            next_status = "approved"
            event_type = "review_approved"
        elif action == "reject":
            if not comment or not comment.strip():
                raise AppError("VALIDATION_ERROR", "Rejecting an invoice requires a comment.", status_code=422)
            next_status = "rejected"
            event_type = "review_rejected"
        elif action == "reopen":
            if not comment or not comment.strip():
                raise AppError("VALIDATION_ERROR", "Reopening an invoice requires a comment.", status_code=422)
            next_status = "pending"
            event_type = "review_reopened"

    elif curr_status in ("approved", "rejected"):
        if action == "reopen":
            if not comment or not comment.strip():
                raise AppError("VALIDATION_ERROR", "Reopening an invoice requires a comment.", status_code=422)
            next_status = "pending"
            event_type = "review_reopened"

    if not next_status or not event_type:
        raise AppError(
            "INVALID_STATE_TRANSITION",
            f"Action '{action}' is not permitted from review status '{curr_status}'.",
            status_code=409,
        )

    with get_transaction() as conn:
        InvoiceRepository.update_review_status(conn, invoice_id, next_status)
        audit_event = InvoiceRepository.add_audit_event(
            conn=conn,
            event_id=f"evt_{secrets.token_hex(6)}",
            invoice_id=invoice_id,
            event_type=event_type,
            actor="local_user",
            details={
                "comment": comment.strip() if comment else None,
                "risk_level": risk_level,
                "acknowledge_risk": acknowledge_risk,
                "validation_run": inv["validation_run"],
            },
        )

    with get_connection() as conn:
        updated_inv = InvoiceRepository.get_by_id(conn, invoice_id, owner_id)
        return updated_inv, audit_event
