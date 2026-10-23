import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple


def paise_to_str(paise: Optional[int]) -> Optional[str]:
    if paise is None:
        return None
    d = Decimal(paise) / Decimal(100)
    return f"{d:.2f}"


def str_to_paise(val: Optional[str]) -> Optional[int]:
    if val is None or val == "":
        return None
    try:
        clean = str(val).replace(",", "").replace("₹", "").replace("Rs.", "").strip()
        d = Decimal(clean)
        return int(round(d * 100))
    except (InvalidOperation, ValueError):
        return None


def row_to_invoice_dict(row: sqlite3.Row, line_rows: List[sqlite3.Row] = None) -> Dict[str, Any]:
    uncertain_fields = json.loads(row["uncertain_fields_json"] or "[]")
    
    risk_breakdown = []
    if row["risk_score"] is not None or row["risk_level"] is not None:
        pass  # Will be populated with findings or defaults

    lines = []
    if line_rows:
        for lr in line_rows:
            lines.append({
                "line_no": lr["line_no"],
                "description": lr["description"],
                "hsn_sac": lr["hsn_sac"],
                "quantity": lr["quantity"],
                "unit_price": paise_to_str(lr["unit_price_paise"]),
                "amount": paise_to_str(lr["amount_paise"]),
            })

    error_obj = None
    if row["error_code"]:
        error_obj = {
            "code": row["error_code"],
            "message": row["error_message"] or "",
            "retryable": row["error_code"] in ("AI_TIMEOUT", "AI_RATE_LIMITED", "AI_UNAVAILABLE", "AI_NOT_CONFIGURED", "INTERRUPTED"),
        }

    return {
        "invoice_id": row["invoice_id"],
        "original_filename": row["original_filename"],
        "content_type": row["content_type"],
        "file_size_bytes": row["file_size_bytes"],
        "file_sha256": row["file_sha256"],
        "processing_status": row["processing_status"],
        "review_status": row["review_status"],
        "extraction_source": row["extraction_source"],
        "extraction_model": row["extraction_model"],
        "document_type": row["document_type"],
        "fields": {
            "vendor_name": row["vendor_name"],
            "vendor_gstin": row["vendor_gstin"],
            "buyer_gstin": row["buyer_gstin"],
            "invoice_number": row["invoice_number"],
            "invoice_date": row["invoice_date"],
            "currency": row["currency"] or "INR",
            "currency_assumed": bool(row["currency_assumed"]),
            "taxable_amount": paise_to_str(row["taxable_paise"]),
            "cgst": paise_to_str(row["cgst_paise"]),
            "sgst": paise_to_str(row["sgst_paise"]),
            "igst": paise_to_str(row["igst_paise"]),
            "total_amount": paise_to_str(row["total_paise"]),
        },
        "line_items": lines,
        "uncertain_fields": uncertain_fields,
        "risk": {
            "score": row["risk_score"],
            "level": row["risk_level"],
            "recommendation": row["recommendation"] or ("manual_entry_required" if row["processing_status"] == "failed" else "no_issues_detected"),
            "breakdown": [],
        },
        "findings_summary": {"high": 0, "medium": 0, "low": 0, "info": 0},
        "validation_run": row["validation_run"],
        "error": error_obj,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "reviewed_at": row["reviewed_at"],
    }


def row_to_summary_dict(row: sqlite3.Row) -> Dict[str, Any]:
    uncertain_fields = json.loads(row["uncertain_fields_json"] or "[]")
    return {
        "invoice_id": row["invoice_id"],
        "original_filename": row["original_filename"],
        "vendor_name": row["vendor_name"],
        "invoice_number": row["invoice_number"],
        "invoice_date": row["invoice_date"],
        "total_amount": paise_to_str(row["total_paise"]),
        "currency": row["currency"] or "INR",
        "processing_status": row["processing_status"],
        "review_status": row["review_status"],
        "extraction_source": row["extraction_source"],
        "risk": {
            "score": row["risk_score"],
            "level": row["risk_level"],
            "recommendation": row["recommendation"] or ("manual_entry_required" if row["processing_status"] == "failed" else "no_issues_detected"),
            "breakdown": [],
        },
        "uncertain_field_count": len(uncertain_fields),
        "created_at": row["created_at"],
    }


class InvoiceRepository:
    @staticmethod
    def get_by_sha256(conn: sqlite3.Connection, file_sha256: str, owner_id: str = "local") -> Optional[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM invoices WHERE owner_id = ? AND file_sha256 = ?",
            (owner_id, file_sha256),
        )
        row = cursor.fetchone()
        if not row:
            return None
        
        cursor.execute("SELECT * FROM line_items WHERE invoice_id = ? ORDER BY line_no ASC", (row["invoice_id"],))
        lines = cursor.fetchall()
        inv_dict = row_to_invoice_dict(row, lines)
        InvoiceRepository._populate_findings_and_risk(conn, inv_dict)
        return inv_dict

    @staticmethod
    def get_by_id(conn: sqlite3.Connection, invoice_id: str, owner_id: str = "local") -> Optional[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM invoices WHERE owner_id = ? AND invoice_id = ?",
            (owner_id, invoice_id),
        )
        row = cursor.fetchone()
        if not row:
            return None
        
        cursor.execute("SELECT * FROM line_items WHERE invoice_id = ? ORDER BY line_no ASC", (invoice_id,))
        lines = cursor.fetchall()
        inv_dict = row_to_invoice_dict(row, lines)
        InvoiceRepository._populate_findings_and_risk(conn, inv_dict)
        return inv_dict

    @staticmethod
    def _populate_findings_and_risk(conn: sqlite3.Connection, inv_dict: Dict[str, Any]) -> None:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT severity, rule_id, evidence_json FROM findings WHERE invoice_id = ? AND is_current = 1",
            (inv_dict["invoice_id"],),
        )
        findings = cursor.fetchall()
        summary = {"high": 0, "medium": 0, "low": 0, "info": 0}
        breakdown = []
        rule_points = {"high": 50, "medium": 25, "low": 10, "info": 0}
        
        seen_rules = set()
        for f in findings:
            sev = f["severity"]
            summary[sev] = summary.get(sev, 0) + 1
            if f["rule_id"] not in seen_rules:
                seen_rules.add(f["rule_id"])
                breakdown.append({
                    "rule_id": f["rule_id"],
                    "severity": sev,
                    "points": rule_points.get(sev, 0),
                })
        inv_dict["findings_summary"] = summary
        inv_dict["risk"]["breakdown"] = breakdown

    @staticmethod
    def insert_initial_invoice(
        conn: sqlite3.Connection,
        invoice_id: str,
        original_filename: str,
        content_type: str,
        file_size_bytes: int,
        file_sha256: str,
        stored_path: str,
        owner_id: str = "local",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO invoices (
                invoice_id, owner_id, original_filename, content_type,
                file_size_bytes, file_sha256, stored_path,
                processing_status, review_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', 'pending', ?, ?)
            """,
            (
                invoice_id, owner_id, original_filename, content_type,
                file_size_bytes, file_sha256, stored_path, now, now,
            ),
        )

    @staticmethod
    def update_processing_status(
        conn: sqlite3.Connection,
        invoice_id: str,
        status: str,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE invoices
            SET processing_status = ?, error_code = ?, error_message = ?, updated_at = ?
            WHERE invoice_id = ?
            """,
            (status, error_code, error_message, now, invoice_id),
        )

    @staticmethod
    def update_invoice_extraction(
        conn: sqlite3.Connection,
        invoice_id: str,
        extraction_source: str,
        extraction_model: str,
        document_type: str,
        fields: Dict[str, Any],
        vendor_key: str,
        invoice_number_key: str,
        uncertain_fields: List[Dict[str, str]],
        extracted_json: str,
        risk_score: int,
        risk_level: str,
        recommendation: str,
        validation_run: int,
        line_items: List[Dict[str, Any]],
        findings: List[Dict[str, Any]],
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()

        # Update invoices table
        cursor.execute(
            """
            UPDATE invoices SET
                processing_status = 'ready',
                extraction_source = ?,
                extraction_model = ?,
                document_type = ?,
                vendor_name = ?,
                vendor_gstin = ?,
                buyer_gstin = ?,
                invoice_number = ?,
                invoice_date = ?,
                currency = ?,
                currency_assumed = ?,
                taxable_paise = ?,
                cgst_paise = ?,
                sgst_paise = ?,
                igst_paise = ?,
                total_paise = ?,
                vendor_key = ?,
                invoice_number_key = ?,
                uncertain_fields_json = ?,
                extracted_json = ?,
                risk_score = ?,
                risk_level = ?,
                recommendation = ?,
                validation_run = ?,
                error_code = NULL,
                error_message = NULL,
                updated_at = ?
            WHERE invoice_id = ?
            """,
            (
                extraction_source,
                extraction_model,
                document_type,
                fields.get("vendor_name"),
                fields.get("vendor_gstin"),
                fields.get("buyer_gstin"),
                fields.get("invoice_number"),
                fields.get("invoice_date"),
                fields.get("currency") or "INR",
                1 if fields.get("currency_assumed") else 0,
                str_to_paise(fields.get("taxable_amount")),
                str_to_paise(fields.get("cgst")),
                str_to_paise(fields.get("sgst")),
                str_to_paise(fields.get("igst")),
                str_to_paise(fields.get("total_amount")),
                vendor_key,
                invoice_number_key,
                json.dumps(uncertain_fields),
                extracted_json,
                risk_score,
                risk_level,
                recommendation,
                validation_run,
                now,
                invoice_id,
            ),
        )

        # Replace line items
        cursor.execute("DELETE FROM line_items WHERE invoice_id = ?", (invoice_id,))
        for idx, item in enumerate(line_items, start=1):
            cursor.execute(
                """
                INSERT INTO line_items (invoice_id, line_no, description, hsn_sac, quantity, unit_price_paise, amount_paise)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_id,
                    idx,
                    item.get("description"),
                    item.get("hsn_sac"),
                    item.get("quantity"),
                    str_to_paise(item.get("unit_price")),
                    str_to_paise(item.get("amount")),
                ),
            )

        # Mark prior findings as is_current = 0
        cursor.execute("UPDATE findings SET is_current = 0 WHERE invoice_id = ?", (invoice_id,))
        # Insert new findings
        for f in findings:
            cursor.execute(
                """
                INSERT INTO findings (
                    finding_id, invoice_id, validation_run, is_current,
                    rule_id, severity, category, title, explanation,
                    evidence_json, created_at
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f["finding_id"],
                    invoice_id,
                    validation_run,
                    f["rule_id"],
                    f["severity"],
                    f["category"],
                    f["title"],
                    f["explanation"],
                    json.dumps(f["evidence"]),
                    now,
                ),
            )

    @staticmethod
    def update_fields_revalidate(
        conn: sqlite3.Connection,
        invoice_id: str,
        fields: Dict[str, Any],
        vendor_key: str,
        invoice_number_key: str,
        uncertain_fields: List[Dict[str, str]],
        risk_score: int,
        risk_level: str,
        recommendation: str,
        validation_run: int,
        line_items: Optional[List[Dict[str, Any]]],
        findings: List[Dict[str, Any]],
        extraction_source: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()

        sql = """
            UPDATE invoices SET
                processing_status = 'ready',
                vendor_name = ?,
                vendor_gstin = ?,
                buyer_gstin = ?,
                invoice_number = ?,
                invoice_date = ?,
                currency = ?,
                currency_assumed = ?,
                taxable_paise = ?,
                cgst_paise = ?,
                sgst_paise = ?,
                igst_paise = ?,
                total_paise = ?,
                vendor_key = ?,
                invoice_number_key = ?,
                uncertain_fields_json = ?,
                risk_score = ?,
                risk_level = ?,
                recommendation = ?,
                validation_run = ?,
                updated_at = ?
        """
        params = [
            fields.get("vendor_name"),
            fields.get("vendor_gstin"),
            fields.get("buyer_gstin"),
            fields.get("invoice_number"),
            fields.get("invoice_date"),
            fields.get("currency") or "INR",
            1 if fields.get("currency_assumed") else 0,
            str_to_paise(fields.get("taxable_amount")),
            str_to_paise(fields.get("cgst")),
            str_to_paise(fields.get("sgst")),
            str_to_paise(fields.get("igst")),
            str_to_paise(fields.get("total_amount")),
            vendor_key,
            invoice_number_key,
            json.dumps(uncertain_fields),
            risk_score,
            risk_level,
            recommendation,
            validation_run,
            now,
        ]

        if extraction_source:
            sql += ", extraction_source = ?"
            params.append(extraction_source)

        sql += " WHERE invoice_id = ?"
        params.append(invoice_id)
        cursor.execute(sql, tuple(params))

        if line_items is not None:
            cursor.execute("DELETE FROM line_items WHERE invoice_id = ?", (invoice_id,))
            for idx, item in enumerate(line_items, start=1):
                cursor.execute(
                    """
                    INSERT INTO line_items (invoice_id, line_no, description, hsn_sac, quantity, unit_price_paise, amount_paise)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        invoice_id,
                        idx,
                        item.get("description"),
                        item.get("hsn_sac"),
                        item.get("quantity"),
                        str_to_paise(item.get("unit_price")),
                        str_to_paise(item.get("amount")),
                    ),
                )

        # Update findings
        cursor.execute("UPDATE findings SET is_current = 0 WHERE invoice_id = ?", (invoice_id,))
        for f in findings:
            cursor.execute(
                """
                INSERT INTO findings (
                    finding_id, invoice_id, validation_run, is_current,
                    rule_id, severity, category, title, explanation,
                    evidence_json, created_at
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f["finding_id"],
                    invoice_id,
                    validation_run,
                    f["rule_id"],
                    f["severity"],
                    f["category"],
                    f["title"],
                    f["explanation"],
                    json.dumps(f["evidence"]),
                    now,
                ),
            )

    @staticmethod
    def update_review_status(
        conn: sqlite3.Connection,
        invoice_id: str,
        review_status: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE invoices
            SET review_status = ?, reviewed_at = ?, updated_at = ?
            WHERE invoice_id = ?
            """,
            (review_status, now if review_status in ("approved", "flagged", "rejected") else None, now, invoice_id),
        )

    @staticmethod
    def list_invoices(
        conn: sqlite3.Connection,
        owner_id: str = "local",
        limit: int = 50,
        offset: int = 0,
        review_status: Optional[str] = None,
        risk_level: Optional[str] = None,
        processing_status: Optional[str] = None,
        q: Optional[str] = None,
        sort: str = "created_at_desc",
    ) -> Tuple[List[Dict[str, Any]], int]:
        cursor = conn.cursor()
        where_clauses = ["owner_id = ?"]
        params: List[Any] = [owner_id]

        if review_status:
            where_clauses.append("review_status = ?")
            params.append(review_status)
        if risk_level:
            where_clauses.append("risk_level = ?")
            params.append(risk_level)
        if processing_status:
            where_clauses.append("processing_status = ?")
            params.append(processing_status)
        if q:
            # Escape LIKE wildcards for security
            escaped_q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            where_clauses.append("(vendor_name LIKE ? ESCAPE '\\' OR invoice_number LIKE ? ESCAPE '\\')")
            pattern = f"%{escaped_q}%"
            params.extend([pattern, pattern])

        where_sql = " AND ".join(where_clauses)

        # Count total
        count_query = f"SELECT COUNT(*) FROM invoices WHERE {where_sql}"
        cursor.execute(count_query, tuple(params))
        total = cursor.fetchone()[0]

        # Sorting allowlist
        sort_map = {
            "created_at_desc": "created_at DESC",
            "created_at_asc": "created_at ASC",
            "invoice_date_desc": "invoice_date DESC",
            "total_desc": "total_paise DESC",
        }
        sort_sql = sort_map.get(sort, "created_at DESC")

        query = f"""
            SELECT * FROM invoices
            WHERE {where_sql}
            ORDER BY {sort_sql}
            LIMIT ? OFFSET ?
        """
        exec_params = list(params) + [limit, offset]
        cursor.execute(query, tuple(exec_params))
        rows = cursor.fetchall()

        items = [row_to_summary_dict(r) for r in rows]
        return items, total

    @staticmethod
    def get_findings(
        conn: sqlite3.Connection,
        invoice_id: str,
        current_only: bool = True,
    ) -> List[Dict[str, Any]]:
        cursor = conn.cursor()
        sql = "SELECT * FROM findings WHERE invoice_id = ?"
        params = [invoice_id]
        if current_only:
            sql += " AND is_current = 1"
        
        # Sort by severity (high -> info) then rule_id
        sql += " ORDER BY CASE severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END, rule_id ASC"
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            result.append({
                "finding_id": r["finding_id"],
                "invoice_id": r["invoice_id"],
                "rule_id": r["rule_id"],
                "severity": r["severity"],
                "category": r["category"],
                "title": r["title"],
                "explanation": r["explanation"],
                "evidence": json.loads(r["evidence_json"] or "{}"),
                "validation_run": r["validation_run"],
                "is_current": bool(r["is_current"]),
                "created_at": r["created_at"],
            })
        return result

    @staticmethod
    def add_audit_event(
        conn: sqlite3.Connection,
        event_id: str,
        invoice_id: str,
        event_type: str,
        actor: str,
        details: Dict[str, Any],
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO audit_events (event_id, invoice_id, event_type, actor, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, invoice_id, event_type, actor, json.dumps(details), now),
        )
        return {
            "event_id": event_id,
            "invoice_id": invoice_id,
            "event_type": event_type,
            "actor": actor,
            "details": details,
            "created_at": now,
        }

    @staticmethod
    def get_audit_events(conn: sqlite3.Connection, invoice_id: str) -> List[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM audit_events WHERE invoice_id = ? ORDER BY created_at ASC",
            (invoice_id,),
        )
        rows = cursor.fetchall()
        return [
            {
                "event_id": r["event_id"],
                "invoice_id": r["invoice_id"],
                "event_type": r["event_type"],
                "actor": r["actor"],
                "details": json.loads(r["details_json"] or "{}"),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    @staticmethod
    def record_ai_call(
        conn: sqlite3.Connection,
        call_id: str,
        invoice_id: Optional[str],
        purpose: str,
        model: str,
        attempt: int,
        status: str,
        error_code: Optional[str] = None,
        latency_ms: Optional[int] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO ai_calls (
                call_id, invoice_id, purpose, model, attempt,
                status, error_code, latency_ms, input_tokens, output_tokens, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                call_id, invoice_id, purpose, model, attempt,
                status, error_code, latency_ms, input_tokens, output_tokens, now
            ),
        )

    @staticmethod
    def get_daily_ai_call_count(conn: sqlite3.Connection) -> int:
        cursor = conn.cursor()
        # Count AI calls made today (UTC)
        today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d") + "%"
        cursor.execute("SELECT COUNT(*) FROM ai_calls WHERE created_at LIKE ?", (today_prefix,))
        row = cursor.fetchone()
        return row[0] if row else 0

    @staticmethod
    def get_history_for_duplicate_check(
        conn: sqlite3.Connection,
        owner_id: str = "local",
        exclude_invoice_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        cursor = conn.cursor()
        sql = "SELECT invoice_id, vendor_key, invoice_number_key, invoice_date, total_paise, review_status FROM invoices WHERE owner_id = ?"
        params = [owner_id]
        if exclude_invoice_id:
            sql += " AND invoice_id != ?"
            params.append(exclude_invoice_id)
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        return [
            {
                "invoice_id": r["invoice_id"],
                "vendor_key": r["vendor_key"],
                "invoice_number_key": r["invoice_number_key"],
                "invoice_date": r["invoice_date"],
                "total_paise": r["total_paise"],
                "review_status": r["review_status"],
            }
            for r in rows
        ]

    @staticmethod
    def delete_invoice(conn: sqlite3.Connection, invoice_id: str, owner_id: str = "local") -> Optional[str]:
        """Deletes invoice record, line items, findings and scrubs audit events. Returns file_sha256 if found."""
        cursor = conn.cursor()
        cursor.execute("SELECT file_sha256, stored_path FROM invoices WHERE invoice_id = ? AND owner_id = ?", (invoice_id, owner_id))
        row = cursor.fetchone()
        if not row:
            return None
        file_sha256 = row["file_sha256"]
        stored_path = row["stored_path"]

        # Delete invoice (cascades to line_items and findings)
        cursor.execute("DELETE FROM invoices WHERE invoice_id = ?", (invoice_id,))

        # Scrub prior audit events to metadata only
        cursor.execute(
            """
            UPDATE audit_events
            SET details_json = '{"redacted": true}'
            WHERE invoice_id = ?
            """,
            (invoice_id,),
        )
        return stored_path

    @staticmethod
    def recover_interrupted_invoices(conn: sqlite3.Connection) -> int:
        """FR-024: Mark invoices left in queued/extracting/validating as failed with INTERRUPTED."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE invoices
            SET processing_status = 'failed', error_code = 'INTERRUPTED',
                error_message = 'Process was interrupted before completing.', updated_at = ?
            WHERE processing_status IN ('queued', 'extracting', 'validating')
            """,
            (now,),
        )
        return cursor.rowcount
