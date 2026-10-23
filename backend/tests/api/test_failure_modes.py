import asyncio
import io
from PIL import Image
import pytest
from app.db.connection import get_connection, get_transaction
from app.db.repository import InvoiceRepository
from app.extraction.mock import MockExtractor
from app.services.pipeline import process_invoice


def make_png() -> bytes:
    bio = io.BytesIO()
    img = Image.new("RGB", (100, 100), color="red")
    img.save(bio, format="PNG")
    return bio.getvalue()


def test_ai_timeout_failure_mode_and_manual_recovery():
    async def _run():
        png_bytes = make_png()
        mock_extractor = MockExtractor(forced_error="AI_TIMEOUT")

        inv_dict, _ = await process_invoice(
            file_bytes=png_bytes,
            filename="timeout_invoice.png",
            extractor_override=mock_extractor,
        )

        assert inv_dict["processing_status"] == "failed"
        assert inv_dict["error"]["code"] == "AI_TIMEOUT"
        assert inv_dict["error"]["retryable"] is True

        from app.services.review import patch_invoice
        recovered_inv = patch_invoice(
            invoice_id=inv_dict["invoice_id"],
            fields_patch={
                "vendor_name": "Manual Vendor",
                "invoice_number": "MAN-01",
                "invoice_date": "2025-03-14",
                "total_amount": "5000.00",
            },
        )

        assert recovered_inv["processing_status"] == "ready"
        assert recovered_inv["extraction_source"] == "manual"
        assert recovered_inv["fields"]["vendor_name"] == "Manual Vendor"

    asyncio.run(_run())


def test_startup_recovery_interrupted_invoices():
    # Insert dummy invoice left in 'extracting'
    with get_transaction() as conn:
        InvoiceRepository.insert_initial_invoice(
            conn=conn,
            invoice_id="inv_interrupted_test",
            original_filename="interrupted.png",
            content_type="image/png",
            file_size_bytes=100,
            file_sha256="dummy_sha_interrupted",
            stored_path="dummy.png",
        )
        InvoiceRepository.update_processing_status(conn, "inv_interrupted_test", "extracting")

    # Run startup recovery
    with get_connection() as conn:
        recovered = InvoiceRepository.recover_interrupted_invoices(conn)
        assert recovered >= 1

        inv = InvoiceRepository.get_by_id(conn, "inv_interrupted_test")
        assert inv["processing_status"] == "failed"
        assert inv["error"]["code"] == "INTERRUPTED"
