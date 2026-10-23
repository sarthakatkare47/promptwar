import json
import secrets
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, File, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.db.connection import get_connection, get_transaction
from app.db.repository import InvoiceRepository
from app.errors import AppError
from app.schemas.api import (
    AuditListResponse,
    FindingsListResponse,
    InvoiceListResponse,
    PatchInvoiceRequest,
    ReprocessRequest,
    ReviewInvoiceRequest,
    ReviewInvoiceResponse,
    UploadResponse,
)
from app.schemas.invoice import Invoice
from app.security import upload_rate_limiter
from app.services.pipeline import get_configured_extractor, process_invoice
from app.services.review import patch_invoice, review_invoice

router = APIRouter(prefix="/api/invoices", tags=["Invoices"])


@router.post("", response_model=UploadResponse)
@router.post("/upload", response_model=UploadResponse)
async def upload_invoice(
    request: Request,
    file: UploadFile = File(...),
):
    """API-002: Validate, store, extract, scan, and score one invoice synchronously."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not upload_rate_limiter.is_allowed(client_ip):
        raise AppError(
            "RATE_LIMITED",
            "Upload rate limit exceeded. Please wait before retrying.",
            status_code=429,
            headers={"Retry-After": "60"},
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise AppError("INVALID_FILE_CONTENT", "Uploaded file is empty (0 bytes).", status_code=422)

    inv_dict, already_existed = await process_invoice(
        file_bytes=file_bytes,
        filename=file.filename or "invoice.png",
        declared_content_type=file.content_type or "",
    )

    status_code = status.HTTP_200_OK if already_existed else status.HTTP_201_CREATED
    return JSONResponse(
        status_code=status_code,
        content={"invoice": inv_dict, "already_existed": already_existed},
    )


@router.get("", response_model=InvoiceListResponse)
async def list_invoices(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    review_status: Optional[str] = Query(None, pattern="^(pending|flagged|approved|rejected)$"),
    risk_level: Optional[str] = Query(None, pattern="^(low|medium|high)$"),
    processing_status: Optional[str] = Query(None, pattern="^(queued|extracting|validating|ready|failed)$"),
    q: Optional[str] = Query(None, max_length=100),
    sort: str = Query("created_at_desc", pattern="^(created_at_desc|created_at_asc|invoice_date_desc|total_desc)$"),
):
    """API-003: List, filter, and paginate invoices."""
    with get_connection() as conn:
        items, total = InvoiceRepository.list_invoices(
            conn=conn,
            limit=limit,
            offset=offset,
            review_status=review_status,
            risk_level=risk_level,
            processing_status=processing_status,
            q=q,
            sort=sort,
        )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{invoice_id}", response_model=Invoice)
async def get_invoice(invoice_id: str):
    """API-004: Get full invoice details."""
    if not invoice_id.startswith("inv_"):
        raise AppError("VALIDATION_ERROR", "Invalid invoice ID format.", status_code=422)

    with get_connection() as conn:
        inv = InvoiceRepository.get_by_id(conn, invoice_id)
        if not inv:
            raise AppError("NOT_FOUND", f"Invoice '{invoice_id}' not found.", status_code=404)
        return inv


@router.patch("/{invoice_id}", response_model=Invoice)
@router.patch("/{invoice_id}/fields", response_model=Invoice)
async def correct_invoice(invoice_id: str, body: PatchInvoiceRequest):
    """API-005: Human field correction or manual entry; re-runs rules and recalculates risk."""
    if not invoice_id.startswith("inv_"):
        raise AppError("VALIDATION_ERROR", "Invalid invoice ID format.", status_code=422)

    updated_inv = patch_invoice(
        invoice_id=invoice_id,
        fields_patch=body.fields,
        confirmed_fields=body.confirmed_fields,
        line_items_patch=body.line_items,
    )
    return updated_inv


@router.post("/{invoice_id}/review", response_model=ReviewInvoiceResponse)
async def review_invoice_endpoint(invoice_id: str, body: ReviewInvoiceRequest):
    """API-006: Approve, flag, reject, or reopen an invoice with comment audit trail."""
    if not invoice_id.startswith("inv_"):
        raise AppError("VALIDATION_ERROR", "Invalid invoice ID format.", status_code=422)

    updated_inv, audit_event = review_invoice(
        invoice_id=invoice_id,
        action=body.action,
        comment=body.comment,
        acknowledge_risk=body.acknowledge_risk,
    )
    return {"invoice": updated_inv, "audit_event": audit_event}


@router.get("/{invoice_id}/findings", response_model=FindingsListResponse)
async def get_invoice_findings(
    invoice_id: str,
    include_history: bool = Query(False),
):
    """API-007: List validation findings with evidence."""
    if not invoice_id.startswith("inv_"):
        raise AppError("VALIDATION_ERROR", "Invalid invoice ID format.", status_code=422)

    with get_connection() as conn:
        inv = InvoiceRepository.get_by_id(conn, invoice_id)
        if not inv:
            raise AppError("NOT_FOUND", f"Invoice '{invoice_id}' not found.", status_code=404)

        findings = InvoiceRepository.get_findings(
            conn=conn,
            invoice_id=invoice_id,
            current_only=not include_history,
        )
    return {
        "invoice_id": invoice_id,
        "validation_run": inv["validation_run"],
        "items": findings,
    }


@router.get("/{invoice_id}/file")
async def get_invoice_file(invoice_id: str):
    """API-010: Stream the original uploaded document for side-by-side review."""
    if not invoice_id.startswith("inv_"):
        raise AppError("VALIDATION_ERROR", "Invalid invoice ID format.", status_code=422)

    with get_connection() as conn:
        inv = InvoiceRepository.get_by_id(conn, invoice_id)
        if not inv:
            raise AppError("NOT_FOUND", f"Invoice '{invoice_id}' not found.", status_code=404)

        cursor = conn.cursor()
        cursor.execute("SELECT stored_path, content_type FROM invoices WHERE invoice_id = ?", (invoice_id,))
        row = cursor.fetchone()
        if not row:
            raise AppError("NOT_FOUND", "File record not found.", status_code=404)

        stored_rel_path = row["stored_path"]
        content_type = row["content_type"]

    full_path = settings.get_upload_dir() / stored_rel_path
    if not full_path.exists():
        raise AppError("NOT_FOUND", "Original file is missing from disk.", status_code=404)

    return FileResponse(
        path=full_path,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{stored_rel_path}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
        },
    )


@router.get("/{invoice_id}/audit", response_model=AuditListResponse)
async def get_invoice_audit_trail(invoice_id: str):
    """API-011: Get append-only audit trail events."""
    if not invoice_id.startswith("inv_"):
        raise AppError("VALIDATION_ERROR", "Invalid invoice ID format.", status_code=422)

    with get_connection() as conn:
        inv = InvoiceRepository.get_by_id(conn, invoice_id)
        if not inv:
            raise AppError("NOT_FOUND", f"Invoice '{invoice_id}' not found.", status_code=404)
        events = InvoiceRepository.get_audit_events(conn, invoice_id)

    return {"invoice_id": invoice_id, "items": events}


@router.post("/{invoice_id}/reprocess", response_model=Invoice)
async def reprocess_invoice(invoice_id: str, body: ReprocessRequest = ReprocessRequest()):
    """API-012: Retry extraction and re-validation."""
    if not invoice_id.startswith("inv_"):
        raise AppError("VALIDATION_ERROR", "Invalid invoice ID format.", status_code=422)

    with get_connection() as conn:
        inv = InvoiceRepository.get_by_id(conn, invoice_id)
        if not inv:
            raise AppError("NOT_FOUND", f"Invoice '{invoice_id}' not found.", status_code=404)

        if inv["review_status"] in ("approved", "rejected"):
            raise AppError(
                "INVOICE_LOCKED",
                f"Cannot reprocess invoice in locked status '{inv['review_status']}'.",
                status_code=409,
            )

        # If human corrections exist and not confirmed overwrite
        if inv["validation_run"] > 1 and not body.confirm_overwrite:
            raise AppError(
                "CONFIRMATION_REQUIRED",
                "Human corrections exist on this invoice. Resend with confirm_overwrite: true to overwrite.",
                status_code=409,
            )

        cursor = conn.cursor()
        cursor.execute("SELECT stored_path, content_type FROM invoices WHERE invoice_id = ?", (invoice_id,))
        row = cursor.fetchone()
        stored_rel = row["stored_path"]
        content_type = row["content_type"]

    full_path = settings.get_upload_dir() / stored_rel
    if not full_path.exists():
        raise AppError("NOT_FOUND", "Original invoice file missing from storage.", status_code=404)

    with open(full_path, "rb") as f:
        file_bytes = f.read()

    with get_transaction() as conn:
        InvoiceRepository.add_audit_event(
            conn=conn,
            event_id=f"evt_{secrets.token_hex(6)}",
            invoice_id=invoice_id,
            event_type="invoice_reprocessed",
            actor="local_user",
            details={"previous_run": inv["validation_run"]},
        )
        InvoiceRepository.update_processing_status(conn, invoice_id, "extracting")

    extractor = get_configured_extractor()
    extractor_source_name = "gemini" if extractor.__class__.__name__ == "GeminiExtractor" else "mock"

    try:
        ext_out = await extractor.extract(file_bytes, content_type)
        with get_transaction() as conn:
            InvoiceRepository.record_ai_call(
                conn=conn,
                call_id=f"ai_{secrets.token_hex(6)}",
                invoice_id=invoice_id,
                purpose="extraction",
                model=ext_out.model,
                attempt=1,
                status="success",
                latency_ms=ext_out.latency_ms,
                input_tokens=ext_out.input_tokens,
                output_tokens=ext_out.output_tokens,
            )
            InvoiceRepository.add_audit_event(
                conn=conn,
                event_id=f"evt_{secrets.token_hex(6)}",
                invoice_id=invoice_id,
                event_type="extraction_succeeded",
                actor="system",
                details={"model": ext_out.model, "latency_ms": ext_out.latency_ms},
            )
            InvoiceRepository.update_processing_status(conn, invoice_id, "validating")

        fields, line_items, uncertain_fields, raw_json_str = normalise_extraction_output(ext_out.result)

        with get_connection() as conn:
            history = InvoiceRepository.get_history_for_duplicate_check(conn, exclude_invoice_id=invoice_id)

        scan_res = scan_invoice(
            invoice_id=invoice_id,
            fields=fields,
            line_items=line_items,
            history=history,
            uncertain_fields=uncertain_fields,
            document_type=ext_out.result.document_type,
            amount_tolerance=settings.AMOUNT_TOLERANCE_INR,
            cgst_sgst_tolerance=settings.CGST_SGST_TOLERANCE_INR,
            old_invoice_days=settings.OLD_INVOICE_DAYS,
        )

        new_run = inv["validation_run"] + 1
        with get_transaction() as conn:
            InvoiceRepository.update_invoice_extraction(
                conn=conn,
                invoice_id=invoice_id,
                extraction_source=extractor_source_name,
                extraction_model=ext_out.model,
                document_type=ext_out.result.document_type,
                fields=fields,
                vendor_key=scan_res.vendor_key,
                invoice_number_key=scan_res.invoice_number_key,
                uncertain_fields=uncertain_fields,
                extracted_json=raw_json_str,
                risk_score=scan_res.risk_score,
                risk_level=scan_res.risk_level,
                recommendation=scan_res.recommendation,
                validation_run=new_run,
                line_items=line_items,
                findings=scan_res.findings,
            )
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
    except Exception as e:
        code = getattr(e, "code", "AI_UNAVAILABLE")
        msg = getattr(e, "message", str(e))
        with get_transaction() as conn:
            InvoiceRepository.update_processing_status(conn, invoice_id, "failed", error_code=code, error_message=msg)
            InvoiceRepository.add_audit_event(
                conn=conn,
                event_id=f"evt_{secrets.token_hex(6)}",
                invoice_id=invoice_id,
                event_type="extraction_failed",
                actor="system",
                details={"error_code": code, "message": msg},
            )

    with get_connection() as conn:
        return InvoiceRepository.get_by_id(conn, invoice_id)


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(invoice_id: str):
    """API-013: Delete invoice record, line items, findings, disk file, and redact audit events."""
    if not invoice_id.startswith("inv_"):
        raise AppError("VALIDATION_ERROR", "Invalid invoice ID format.", status_code=422)

    with get_transaction() as conn:
        stored_path = InvoiceRepository.delete_invoice(conn, invoice_id)
        if not stored_path:
            raise AppError("NOT_FOUND", f"Invoice '{invoice_id}' not found.", status_code=404)

        # Add tombstone event
        InvoiceRepository.add_audit_event(
            conn=conn,
            event_id=f"evt_{secrets.token_hex(6)}",
            invoice_id=invoice_id,
            event_type="invoice_deleted",
            actor="local_user",
            details={"invoice_id": invoice_id},
        )

    # Delete physical file
    full_path = settings.get_upload_dir() / stored_path
    if full_path.exists():
        try:
            full_path.unlink()
        except Exception:
            pass

    return Response(status_code=status.HTTP_204_NO_CONTENT)
