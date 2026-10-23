import csv
import io
import json
from typing import Any, Dict, List, Optional
from app.db.connection import get_connection
from app.db.repository import InvoiceRepository, paise_to_str
from app.errors import AppError

DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(val: Any) -> str:
    """Neutralises potential formula injection characters by prefixing with a single apostrophe."""
    if val is None:
        return ""
    s = str(val)
    if s.startswith(DANGEROUS_PREFIXES):
        return f"'{s}"
    return s


def export_invoices_csv(
    owner_id: str = "local",
    review_status: Optional[str] = None,
    risk_level: Optional[str] = None,
    processing_status: Optional[str] = None,
) -> str:
    with get_connection() as conn:
        cursor = conn.cursor()
        where = ["owner_id = ?"]
        params: List[Any] = [owner_id]
        if review_status:
            where.append("review_status = ?")
            params.append(review_status)
        if risk_level:
            where.append("risk_level = ?")
            params.append(risk_level)
        if processing_status:
            where.append("processing_status = ?")
            params.append(processing_status)

        where_sql = " AND ".join(where)

        cursor.execute(f"SELECT COUNT(*) FROM invoices WHERE {where_sql}", tuple(params))
        total = cursor.fetchone()[0]
        if total > 10000:
            raise AppError(
                "VALIDATION_ERROR",
                f"Export matches {total} rows (limit 10,000). Please narrow the filter.",
                status_code=422,
            )

        query = f"SELECT * FROM invoices WHERE {where_sql} ORDER BY created_at DESC"
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

    output = io.StringIO()
    # Write UTF-8 BOM
    output.write("\ufeff")
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    headers = [
        "invoice_id", "original_filename", "processing_status", "review_status",
        "extraction_source", "vendor_name", "vendor_gstin", "buyer_gstin",
        "invoice_number", "invoice_date", "currency", "taxable_amount",
        "cgst", "sgst", "igst", "total_amount", "risk_score", "risk_level",
        "recommendation", "finding_rule_ids", "uncertain_fields",
        "created_at", "reviewed_at"
    ]
    writer.writerow(headers)

    for r in rows:
        uncertain = json.loads(r["uncertain_fields_json"] or "[]")
        unc_fields_str = ";".join([u["field"] for u in uncertain])
        
        # Get rule IDs from current findings
        with get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT DISTINCT rule_id FROM findings WHERE invoice_id = ? AND is_current = 1", (r["invoice_id"],))
            rules = [row[0] for row in c.fetchall()]
        rules_str = ";".join(rules)

        row_vals = [
            sanitize_csv_cell(r["invoice_id"]),
            sanitize_csv_cell(r["original_filename"]),
            sanitize_csv_cell(r["processing_status"]),
            sanitize_csv_cell(r["review_status"]),
            sanitize_csv_cell(r["extraction_source"]),
            sanitize_csv_cell(r["vendor_name"]),
            sanitize_csv_cell(r["vendor_gstin"]),
            sanitize_csv_cell(r["buyer_gstin"]),
            sanitize_csv_cell(r["invoice_number"]),
            sanitize_csv_cell(r["invoice_date"]),
            sanitize_csv_cell(r["currency"] or "INR"),
            sanitize_csv_cell(paise_to_str(r["taxable_paise"])),
            sanitize_csv_cell(paise_to_str(r["cgst_paise"])),
            sanitize_csv_cell(paise_to_str(r["sgst_paise"])),
            sanitize_csv_cell(paise_to_str(r["igst_paise"])),
            sanitize_csv_cell(paise_to_str(r["total_paise"])),
            sanitize_csv_cell(r["risk_score"]),
            sanitize_csv_cell(r["risk_level"]),
            sanitize_csv_cell(r["recommendation"]),
            sanitize_csv_cell(rules_str),
            sanitize_csv_cell(unc_fields_str),
            sanitize_csv_cell(r["created_at"]),
            sanitize_csv_cell(r["reviewed_at"]),
        ]
        writer.writerow(row_vals)

    return output.getvalue()


def export_findings_csv(
    owner_id: str = "local",
    review_status: Optional[str] = None,
    risk_level: Optional[str] = None,
) -> str:
    with get_connection() as conn:
        cursor = conn.cursor()
        where = ["i.owner_id = ?", "f.is_current = 1"]
        params: List[Any] = [owner_id]
        if review_status:
            where.append("i.review_status = ?")
            params.append(review_status)
        if risk_level:
            where.append("i.risk_level = ?")
            params.append(risk_level)

        where_sql = " AND ".join(where)

        query = f"""
            SELECT f.*, i.vendor_name, i.invoice_number
            FROM findings f
            JOIN invoices i ON f.invoice_id = i.invoice_id
            WHERE {where_sql}
            ORDER BY f.created_at DESC
        """
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    headers = [
        "invoice_id", "vendor_name", "invoice_number", "rule_id",
        "severity", "title", "explanation", "evidence_json",
        "validation_run", "created_at"
    ]
    writer.writerow(headers)

    for r in rows:
        row_vals = [
            sanitize_csv_cell(r["invoice_id"]),
            sanitize_csv_cell(r["vendor_name"]),
            sanitize_csv_cell(r["invoice_number"]),
            sanitize_csv_cell(r["rule_id"]),
            sanitize_csv_cell(r["severity"]),
            sanitize_csv_cell(r["title"]),
            sanitize_csv_cell(r["explanation"]),
            sanitize_csv_cell(r["evidence_json"]),
            sanitize_csv_cell(r["validation_run"]),
            sanitize_csv_cell(r["created_at"]),
        ]
        writer.writerow(row_vals)

    return output.getvalue()
