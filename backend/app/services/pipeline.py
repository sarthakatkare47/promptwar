import json
import secrets
from pathlib import Path
from typing import Tuple

from app.config import settings
from app.db.connection import get_connection, get_transaction
from app.db.repository import InvoiceRepository
from app.extraction.base import ExtractionError
from app.extraction.gemini import GeminiExtractor
from app.extraction.mock import MockExtractor
from app.extraction.normalise import normalise_extraction_output
from app.services.upload_validation import validate_upload
from app.validation.engine import scan_invoice


def get_configured_extractor():
    gemini_key = settings.GEMINI_API_KEY.get_secret_value() if settings.GEMINI_API_KEY else ""
    if settings.EXTRACTOR == "mock" or not gemini_key:
        return MockExtractor()
    return GeminiExtractor()


async def process_invoice(
    file_bytes: bytes,
    filename: str,
    declared_content_type: str = "",
    owner_id: str = "local",
    extractor_override=None,
) -> Tuple[dict, bool]:
    """
    Executes the invoice processing pipeline:
    validate upload -> check sha256 -> store file -> extract -> normalise -> validate -> persist.
    Returns: (invoice_dict, already_existed)
    """
    # 1. Validate file upload
    val_res = validate_upload(file_bytes, filename, declared_content_type)

    # 2. Check for SHA-256 idempotency (skips AI call if file identical)
    with get_connection() as conn:
        existing = InvoiceRepository.get_by_sha256(conn, val_res.file_sha256, owner_id)
        if existing:
            return existing, True

    # 3. New file: generate ID and store original
    invoice_id = f"inv_{secrets.token_hex(6)}"
    upload_dir = settings.get_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{invoice_id}{val_res.extension}"
    full_stored_path = upload_dir / stored_filename
    with open(full_stored_path, "wb") as f:
        f.write(file_bytes)

    # Initial insert: status = queued
    with get_transaction() as conn:
        InvoiceRepository.insert_initial_invoice(
            conn=conn,
            invoice_id=invoice_id,
            original_filename=Path(filename).name[:120],
            content_type=val_res.content_type,
            file_size_bytes=val_res.file_size_bytes,
            file_sha256=val_res.file_sha256,
            stored_path=stored_filename,
            owner_id=owner_id,
        )
        InvoiceRepository.add_audit_event(
            conn=conn,
            event_id=f"evt_{secrets.token_hex(6)}",
            invoice_id=invoice_id,
            event_type="invoice_uploaded",
            actor="local_user",
            details={
                "sha256": val_res.file_sha256,
                "content_type": val_res.content_type,
                "size": val_res.file_size_bytes,
            },
        )

    # Check daily AI quota cap
    with get_connection() as conn:
        daily_count = InvoiceRepository.get_daily_ai_call_count(conn)
        if daily_count >= settings.DAILY_AI_CALL_LIMIT:
            with get_transaction() as t_conn:
                InvoiceRepository.update_processing_status(
                    t_conn, invoice_id, "failed",
                    error_code="AI_QUOTA_EXCEEDED",
                    error_message=f"Local daily AI call limit ({settings.DAILY_AI_CALL_LIMIT}) reached.",
                )
                InvoiceRepository.add_audit_event(
                    t_conn, f"evt_{secrets.token_hex(6)}", invoice_id,
                    "extraction_failed", "system",
                    {"error_code": "AI_QUOTA_EXCEEDED"},
                )
            return InvoiceRepository.get_by_id(conn, invoice_id, owner_id), False

    # 4. Extract
    with get_transaction() as conn:
        InvoiceRepository.update_processing_status(conn, invoice_id, "extracting")

    extractor = extractor_override or get_configured_extractor()
    extractor_source_name = "gemini" if isinstance(extractor, GeminiExtractor) else "mock"

    try:
        ext_out = await extractor.extract(file_bytes, val_res.content_type)
        
        # Record AI call log
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
                details={
                    "model": ext_out.model,
                    "latency_ms": ext_out.latency_ms,
                    "tokens": (ext_out.input_tokens or 0) + (ext_out.output_tokens or 0),
                },
            )
    except ExtractionError as ee:
        with get_transaction() as conn:
            InvoiceRepository.record_ai_call(
                conn=conn,
                call_id=f"ai_{secrets.token_hex(6)}",
                invoice_id=invoice_id,
                purpose="extraction",
                model=getattr(extractor, "model_name", "unknown"),
                attempt=1,
                status="error",
                error_code=ee.code,
            )
            InvoiceRepository.add_audit_event(
                conn, f"evt_{secrets.token_hex(6)}", invoice_id,
                "extraction_ai_unavailable_fallback", "system",
                {"error_code": ee.code, "message": ee.message},
            )
        # Graceful fallback to mock extractor so scan pipeline proceeds
        fallback_extractor = MockExtractor()
        ext_out = await fallback_extractor.extract(file_bytes, val_res.content_type)
        extractor_source_name = "mock"

    # 5. Normalise and validate output
    with get_transaction() as conn:
        InvoiceRepository.update_processing_status(conn, invoice_id, "validating")

    try:
        fields, line_items, uncertain_fields, raw_json_str = normalise_extraction_output(ext_out.result)
    except ExtractionError as ee:
        with get_transaction() as conn:
            InvoiceRepository.update_processing_status(
                conn, invoice_id, "failed",
                error_code=ee.code,
                error_message=ee.message,
            )
            InvoiceRepository.add_audit_event(
                conn, f"evt_{secrets.token_hex(6)}", invoice_id,
                "extraction_failed", "system",
                {"error_code": ee.code, "message": ee.message},
            )
        with get_connection() as conn:
            return InvoiceRepository.get_by_id(conn, invoice_id, owner_id), False

    # Load history for duplicate detection
    with get_connection() as conn:
        history = InvoiceRepository.get_history_for_duplicate_check(conn, owner_id, exclude_invoice_id=invoice_id)

    # Run deterministic scan
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

    # 6. Atomic persist of ready invoice + findings + audit
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
            validation_run=1,
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
                "validation_run": 1,
                "risk_level": scan_res.risk_level,
                "score": scan_res.risk_score,
                "rule_ids": [f["rule_id"] for f in scan_res.findings],
            },
        )

    with get_connection() as conn:
        return InvoiceRepository.get_by_id(conn, invoice_id, owner_id), False
