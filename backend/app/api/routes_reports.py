from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Query, Response

from app.errors import AppError
from app.services.export import export_findings_csv, export_invoices_csv

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/export")
async def export_report(
    scope: str = Query("invoices", pattern="^(invoices|findings)$"),
    format: str = Query("csv", pattern="^(csv)$"),
    review_status: Optional[str] = Query(None, pattern="^(pending|flagged|approved|rejected)$"),
    risk_level: Optional[str] = Query(None, pattern="^(low|medium|high)$"),
    processing_status: Optional[str] = Query(None, pattern="^(queued|extracting|validating|ready|failed)$"),
):
    """Exports processed invoices or current findings as CSV with formula neutralisation."""
    now_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if scope == "invoices":
        csv_data = export_invoices_csv(
            review_status=review_status,
            risk_level=risk_level,
            processing_status=processing_status,
        )
        filename = f"invoiceguard_invoices_{now_str}.csv"
    else:
        csv_data = export_findings_csv(
            review_status=review_status,
            risk_level=risk_level,
        )
        filename = f"invoiceguard_findings_{now_str}.csv"

    return Response(
        content=csv_data.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
