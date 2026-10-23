# InvoiceGuard+ — API Specification

> Document set: [PROJECT_BRIEF](PROJECT_BRIEF.md) · [PRD](PRD.md) · [PLAN](PLAN.md) · [ARCHITECTURE](ARCHITECTURE.md) · **API_SPEC** · [README](README.md)

Base URL (local MVP): `http://127.0.0.1:8000`. FastAPI also serves generated OpenAPI docs at `/docs`; this document is the contract, and the generated schema must match it (checked in [PLAN §7](PLAN.md#7-final-github-verification-checklist)).

**Label convention:** **MVP** · **Optional** · **Future**.

## 1. Endpoint summary

| ID | Method and path | Purpose | Label |
|---|---|---|---|
| [API-001](#api-001-health) | `GET /health` | Liveness and configuration status | MVP |
| [API-002](#api-002-upload-an-invoice) | `POST /api/invoices/upload` | Upload and process one invoice | MVP |
| [API-003](#api-003-list-invoices) | `GET /api/invoices` | List, filter, paginate | MVP |
| [API-004](#api-004-get-an-invoice) | `GET /api/invoices/{invoice_id}` | Full invoice detail | MVP |
| [API-005](#api-005-correct-an-invoice) | `PATCH /api/invoices/{invoice_id}` | Correct fields, re-validate | MVP |
| [API-006](#api-006-review-an-invoice) | `POST /api/invoices/{invoice_id}/review` | Approve / flag / reject / reopen | MVP |
| [API-007](#api-007-list-findings) | `GET /api/invoices/{invoice_id}/findings` | Findings with evidence | MVP |
| [API-008](#api-008-trust-scorecard) | `GET /api/scorecard` | Last benchmark results | MVP |
| [API-009](#api-009-export-report) | `GET /api/reports/export` | CSV export | MVP |
| [API-010](#api-010-original-file) | `GET /api/invoices/{invoice_id}/file` | Original upload (for the review screen) | MVP |
| [API-011](#api-011-audit-trail) | `GET /api/invoices/{invoice_id}/audit` | Audit events | MVP |
| [API-012](#api-012-reprocess-extraction) | `POST /api/invoices/{invoice_id}/reprocess` | Retry extraction | MVP |
| [API-013](#api-013-delete-an-invoice) | `DELETE /api/invoices/{invoice_id}` | Delete record and file | MVP |
| [API-020](#api-020-read-only-natural-language-query) | `POST /api/query` | Filter-based natural-language query | Optional |

**Justification for the endpoints beyond the original list:** `file` (review screen needs the original), `audit` (traceable history requirement), `reprocess` (recovery from AI failure, FR-020), `delete` (data-retention requirement, FR-022). **Deliberately absent:** any endpoint that accepts or executes SQL.

## 2. Conventions

| Topic | Rule |
|---|---|
| Content type | JSON (`application/json; charset=utf-8`) except upload (`multipart/form-data`), file (binary) and export (`text/csv`) |
| IDs | Prefixed lowercase hex: `inv_` (invoice), `fnd_` (finding), `evt_` (audit event), `req_` (request); each followed by 12 hex characters |
| Timestamps | ISO 8601 UTC with `Z`, e.g. `2026-10-23T09:15:30Z`; dates `YYYY-MM-DD` |
| Money | Decimal **strings** with two places (`"11800.00"`), never JSON numbers; `null` means "not extracted", not zero. Stored as integer paise |
| Currency | ISO code string, default assumption `INR`, flagged by `currency_assumed` |
| Enums | `processing_status`: `queued`, `extracting`, `validating`, `ready`, `failed` · `review_status`: `pending`, `flagged`, `approved`, `rejected` · `risk.level`: `low`, `medium`, `high` · `severity`: `high`, `medium`, `low`, `info` · `extraction_source`: `gemini`, `mock`, `manual` · `recommendation`: `no_issues_detected`, `review_recommended`, `high_priority_review`, `manual_entry_required` |
| Pagination | `limit` (1–100, default 50), `offset` (≥ 0); envelope `{ "items": [...], "total": n, "limit": n, "offset": n }` |
| Response headers | `X-Request-ID`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store` |
| Authentication | **Local MVP: none.** Bind to `127.0.0.1`, CORS allow-list. If `IG_ACCESS_TOKEN` is set (Optional), every `/api/*` request needs `Authorization: Bearer <token>`, else `401 UNAUTHORIZED`. `/health` is exempt. This is a shared secret, not user authentication; there are **no users, sessions or tenant isolation** in the MVP |

### 2.1 Error format (all endpoints)

```json
{
  "error": {
    "code": "FILE_TOO_LARGE",
    "message": "The file is larger than the 10 MB limit.",
    "details": { "max_bytes": 10485760, "received_bytes": 12582912 },
    "request_id": "req_8c1d2e3f4a5b"
  }
}
```

`code` is stable and machine-readable; `message` is safe for display; `details` is optional; no stack traces, paths or SQL are ever returned. Request-body or parameter validation failures use `VALIDATION_ERROR` (`422`) with `details.errors = [{ "field": "fields.total_amount", "message": "Must be a non-negative amount with at most 2 decimals." }]`.

| Code | HTTP | Meaning |
|---|---|---|
| `UNAUTHORIZED` | 401 | Missing/incorrect bearer token (only when configured) |
| `NOT_FOUND` | 404 | Unknown ID |
| `INVALID_STATE_TRANSITION` | 409 | Review action not allowed from the current status |
| `INVOICE_LOCKED` | 409 | Edit attempted on an approved/rejected invoice |
| `CONFIRMATION_REQUIRED` | 409 | Action would overwrite human corrections; resend with confirmation |
| `FILE_TOO_LARGE` | 413 | Upload exceeds `MAX_UPLOAD_BYTES` |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | Detected type is not JPEG, PNG or PDF |
| `FILE_TYPE_MISMATCH` | 422 | Extension or declared type disagrees with the file signature |
| `INVALID_FILE_CONTENT` | 422 | Corrupt or undecodable file |
| `IMAGE_TOO_LARGE_PIXELS` | 422 | Image dimensions exceed the pixel cap |
| `PDF_TOO_MANY_PAGES` | 422 | More than `MAX_PDF_PAGES` |
| `PDF_ENCRYPTED` | 422 | Encrypted PDF |
| `PDF_ACTIVE_CONTENT` | 422 | PDF contains script/launch/embedded-file markers |
| `VALIDATION_ERROR` | 422 | Bad body, field or query parameter |
| `RATE_LIMITED` | 429 | Upload limiter; `Retry-After` header set |
| `INTERNAL_ERROR` | 500 | Unexpected failure (use `request_id` to find the log line) |

AI-side failures are **not** HTTP errors: see `invoice.error` and the codes `AI_NOT_CONFIGURED`, `AI_TIMEOUT`, `AI_UNAVAILABLE`, `AI_RATE_LIMITED`, `AI_QUOTA_EXCEEDED`, `AI_BAD_OUTPUT`, `INTERRUPTED` ([PRD §13](PRD.md#13-error-states-and-recovery)).

### 2.2 Shared objects

**`Invoice`** (returned by API-002, 004, 005, 006, 012)

```json
{
  "invoice_id": "inv_3f9a1c7b2d4e",
  "original_filename": "sharma_traders_0142.png",
  "content_type": "image/png",
  "file_size_bytes": 183422,
  "file_sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "processing_status": "ready",
  "review_status": "pending",
  "extraction_source": "gemini",
  "extraction_model": "gemini-2.5-flash",
  "document_type": "tax_invoice",
  "fields": {
    "vendor_name": "Sharma Traders",
    "vendor_gstin": "27ABCDE1234F1Z1",
    "buyer_gstin": null,
    "invoice_number": "ST/24-25/0142",
    "invoice_date": "2025-03-14",
    "currency": "INR",
    "currency_assumed": false,
    "taxable_amount": "10000.00",
    "cgst": "900.00",
    "sgst": "900.00",
    "igst": null,
    "total_amount": "12800.00"
  },
  "line_items": [
    { "line_no": 1, "description": "Steel bolts M8", "hsn_sac": "7318", "quantity": "100", "unit_price": "100.00", "amount": "10000.00" }
  ],
  "uncertain_fields": [
    { "field": "vendor_gstin", "reason": "gstin_check_failed" }
  ],
  "risk": {
    "score": 100,
    "level": "high",
    "recommendation": "high_priority_review",
    "breakdown": [
      { "rule_id": "GST-002", "severity": "high", "points": 50 },
      { "rule_id": "TAX-002", "severity": "high", "points": 50 },
      { "rule_id": "EXT-002", "severity": "low", "points": 10 }
    ]
  },
  "findings_summary": { "high": 2, "medium": 0, "low": 1, "info": 0 },
  "validation_run": 1,
  "error": null,
  "created_at": "2026-10-23T09:15:30Z",
  "updated_at": "2026-10-23T09:15:41Z",
  "reviewed_at": null
}
```

For a failed invoice: `fields` values are all `null`, `line_items` is `[]`, `risk` is `{ "score": null, "level": null, "recommendation": "manual_entry_required", "breakdown": [] }`, and `error` is `{ "code": "AI_TIMEOUT", "message": "The AI service did not respond in time.", "retryable": true }`. `score` is the sum before the cap of 100; `breakdown` lists each rule once.

**`Finding`**

```json
{
  "finding_id": "fnd_a1b2c3d4e5f6",
  "invoice_id": "inv_3f9a1c7b2d4e",
  "rule_id": "GST-002",
  "severity": "high",
  "category": "gstin",
  "title": "GSTIN check character does not match",
  "explanation": "The last character of the vendor GSTIN does not match the value calculated from the first 14 characters. This can indicate a typing or scanning error, or an invalid number. It does not by itself show that anything is fraudulent, and a matching check character would not prove the registration is genuine or active.",
  "evidence": { "field": "vendor_gstin", "value": "27ABCDE1234F1Z1", "expected_check_character": "0" },
  "validation_run": 1,
  "is_current": true,
  "created_at": "2026-10-23T09:15:41Z"
}
```

**`AuditEvent`**

```json
{
  "event_id": "evt_0a1b2c3d4e5f",
  "invoice_id": "inv_3f9a1c7b2d4e",
  "event_type": "review_flagged",
  "actor": "local_user",
  "details": { "comment": "Call vendor to confirm GSTIN", "risk_level": "high", "validation_run": 1 },
  "created_at": "2026-10-23T09:20:02Z"
}
```

Event types: `invoice_uploaded`, `extraction_succeeded`, `extraction_failed`, `validation_completed`, `field_corrected`, `review_approved`, `review_flagged`, `review_rejected`, `review_reopened`, `invoice_reprocessed`, `invoice_deleted`. `field_corrected` is also written for "I checked this" confirmations (empty `changes`, populated `confirmed_fields`).

---

## API-001: Health

`GET /health` · **MVP**

| | |
|---|---|
| Purpose | Liveness plus safe configuration status |
| Auth | None (always exempt) |
| Request | No body or parameters |
| Success | `200` |
| Errors | `500` only if the process is unhealthy |
| Security | Reveals only booleans and the extractor name; never the key, paths or model output |

```json
{ "status": "ok", "version": "0.1.0", "extractor": "gemini", "gemini_configured": true, "database": "ok", "time": "2026-10-23T09:10:00Z" }
```

## API-002: Upload an invoice

`POST /api/invoices/upload` · **MVP**

| | |
|---|---|
| Purpose | Validate, store, extract, scan and score **one** invoice, synchronously |
| Auth | Local MVP: none (token if configured) |
| Request | `multipart/form-data` with one part `file` (required). Batch = the client calls this endpoint once per file ([ARCHITECTURE §6](ARCHITECTURE.md#6-batch-processing-lifecycle), Optional) |
| Allowed types | JPEG (`.jpg`, `.jpeg`), PNG (`.png`), PDF (`.pdf`), decided by **magic bytes**; declared `Content-Type` and extension must agree |
| Limits | ≤ `MAX_UPLOAD_BYTES` (10 MB); images ≤ `MAX_IMAGE_PIXELS`; PDFs ≤ `MAX_PDF_PAGES` (5), not encrypted, no `/JavaScript`, `/JS`, `/Launch`, `/EmbeddedFile`, `/OpenAction` markers |
| Rate limit | `UPLOAD_RATE_LIMIT_PER_MINUTE` per client; `429` with `Retry-After` |
| Security controls | Order of checks in [ARCHITECTURE §11.1](ARCHITECTURE.md#111-file-upload-security-sec-001003-mvp); server-generated storage name; model has no tools; output re-validated locally; daily AI cap |

**Responses**

| Status | When | Body |
|---|---|---|
| `201 Created` | New file accepted. `processing_status` is `ready` **or** `failed` (AI failure is stored, not thrown) | `{ "invoice": Invoice, "already_existed": false }` |
| `200 OK` | Identical bytes (SHA-256) were already processed; **no new record, no AI call** | `{ "invoice": Invoice, "already_existed": true }` |
| `413` | Too large | `FILE_TOO_LARGE` |
| `415` | Detected type not allowed | `UNSUPPORTED_MEDIA_TYPE` |
| `422` | `FILE_TYPE_MISMATCH`, `INVALID_FILE_CONTENT`, `IMAGE_TOO_LARGE_PIXELS`, `PDF_TOO_MANY_PAGES`, `PDF_ENCRYPTED`, `PDF_ACTIVE_CONTENT`, or missing `file` part (`VALIDATION_ERROR`) | error body |
| `429` | Rate limit | `RATE_LIMITED` |

**Idempotency:** keyed on `(owner_id, SHA-256)`. Re-uploading a file never creates a second invoice and never calls Gemini again, even if the first attempt `failed` (use API-012 to retry). **Duplicate *business* invoices** (different file, same vendor/number) are accepted and reported as `DUP-00x` findings.

Example request: `curl -F "file=@sharma_traders_0142.png" http://127.0.0.1:8000/api/invoices/upload`. A successful response contains the `Invoice` object shown in §2.2.

## API-003: List invoices

`GET /api/invoices` · **MVP**

| | |
|---|---|
| Auth | Local MVP: none |
| Query | `limit`, `offset` (§2); `review_status`, `risk_level`, `processing_status` (enums, repeatable-free single value); `q` (≤ 100 chars, matches vendor name or invoice number, case-insensitive substring, wildcards escaped); `sort` = `created_at_desc` (default), `created_at_asc`, `invoice_date_desc`, `total_desc` |
| Success | `200` with the pagination envelope of `InvoiceSummary` |
| Errors | `422 VALIDATION_ERROR` (unknown enum/sort, out-of-range numbers) |
| Security | Bound parameters; sort key mapped from an allowlist, never interpolated |

```json
{
  "items": [
    {
      "invoice_id": "inv_3f9a1c7b2d4e",
      "original_filename": "sharma_traders_0142.png",
      "vendor_name": "Sharma Traders",
      "invoice_number": "ST/24-25/0142",
      "invoice_date": "2025-03-14",
      "total_amount": "12800.00",
      "currency": "INR",
      "processing_status": "ready",
      "review_status": "pending",
      "extraction_source": "gemini",
      "risk": { "score": 100, "level": "high", "recommendation": "high_priority_review" },
      "uncertain_field_count": 1,
      "created_at": "2026-10-23T09:15:30Z"
    }
  ],
  "total": 1, "limit": 50, "offset": 0
}
```

## API-004: Get an invoice

`GET /api/invoices/{invoice_id}` · **MVP**

| | |
|---|---|
| Success | `200` with `Invoice` |
| Errors | `404 NOT_FOUND`; `422` if the ID does not match `^inv_[0-9a-f]{12}$` |
| Security | ID format validated before the query; single-user MVP (no ownership check beyond the repository's `owner_id = 'local'` scaffold) |

## API-005: Correct an invoice

`PATCH /api/invoices/{invoice_id}` · **MVP**

| | |
|---|---|
| Purpose | Human correction (including manual entry on a `failed` invoice); re-runs all rules |
| Request | `application/json`; at least one of the keys below |
| Success | `200` with updated `Invoice` (`validation_run` incremented, new findings, new risk). A request that changes nothing returns `200` with no new run and no audit event |
| Errors | `404`; `409 INVOICE_LOCKED` when `review_status` is `approved` or `rejected`; `422 VALIDATION_ERROR` |
| Security | Explicit field allowlist (no mass assignment); value format checks; text length caps; stored and displayed as plain text |
| Audit | `field_corrected` with `changes: [{field, old, new}]` and `confirmed_fields`; then `validation_completed` |

```json
{
  "fields": { "vendor_gstin": "27ABCDE1234F1Z0", "total_amount": "11800.00" },
  "confirmed_fields": ["invoice_date"],
  "line_items": [
    { "description": "Steel bolts M8", "hsn_sac": "7318", "quantity": "100", "unit_price": "100.00", "amount": "10000.00" }
  ]
}
```

| Key | Type and validation |
|---|---|
| `fields.vendor_name` | string ≤ 200 or `null` |
| `fields.vendor_gstin`, `fields.buyer_gstin` | string ≤ 15 matching `^[A-Za-z0-9 -]{0,15}$` (normalised to upper case without spaces/hyphens) or `null`. **Invalid GSTINs are accepted and then flagged by the rules** |
| `fields.invoice_number` | string ≤ 64 or `null` |
| `fields.invoice_date` | `YYYY-MM-DD` real calendar date, or `null` |
| `fields.currency` | 3 upper-case letters or `null` |
| `fields.taxable_amount`, `cgst`, `sgst`, `igst`, `total_amount` | `^\d{1,12}(\.\d{1,2})?$` or `null` |
| `confirmed_fields` | list of field names from the allowlist; removes their uncertainty marker without changing values |
| `line_items` | optional **full replacement**, ≤ 50 items; `description` ≤ 300, `hsn_sac` ≤ 16, decimals as above |

Any other key → `422 VALIDATION_ERROR`. The original `extracted_json` is never modified.

## API-006: Review an invoice

`POST /api/invoices/{invoice_id}/review` · **MVP**

| | |
|---|---|
| Purpose | Human decision with a recorded reason |
| Request | `{ "action": "approve" \| "flag" \| "reject" \| "reopen", "comment": string \| null, "acknowledge_risk": boolean }` (`acknowledge_risk` defaults to `false`; `comment` ≤ 500 chars, plain text) |
| Success | `200` `{ "invoice": Invoice, "audit_event": AuditEvent }` |
| Errors | `404`; `409 INVALID_STATE_TRANSITION`; `422 VALIDATION_ERROR` (missing comment where required, bad action, `approve` with `acknowledge_risk: false` when risk is `high`, or invoice not `ready`) |
| Security | Server-side state machine; the decision never comes from model output; no payment or external side effects |

| From `review_status` | `action` | To | Requirements |
|---|---|---|---|
| `pending` | `approve` | `approved` | `processing_status = ready`; if `risk.level = high` → `acknowledge_risk: true` **and** `comment` |
| `pending` | `flag` | `flagged` | `comment` |
| `pending` | `reject` | `rejected` | `comment` |
| `flagged` | `approve` / `reject` / `reopen` | `approved` / `rejected` / `pending` | as above; `reopen` needs `comment` |
| `approved`, `rejected` | `reopen` | `pending` | `comment` |

All other combinations → `409 INVALID_STATE_TRANSITION`. Repeating an action that already took effect is also `409` (it is not silently accepted). Effects: `review_status` and `reviewed_at` updated, one audit event `review_approved` / `review_flagged` / `review_rejected` / `review_reopened` with comment, risk level and `validation_run`.

## API-007: List findings

`GET /api/invoices/{invoice_id}/findings` · **MVP**

| | |
|---|---|
| Query | `include_history` (boolean, default `false`): when `true`, findings from earlier validation runs are included with `is_current: false` |
| Success | `200` `{ "invoice_id": "...", "validation_run": 1, "items": [Finding, ...] }` ordered by severity (high → info) then `rule_id` |
| Errors | `404` |
| Notes | Rule IDs and severities are those in [PRD §9](PRD.md#9-validation-rules-and-limitations) |

```json
{
  "invoice_id": "inv_3f9a1c7b2d4e",
  "validation_run": 1,
  "items": [
    {
      "finding_id": "fnd_b2c3d4e5f6a7",
      "invoice_id": "inv_3f9a1c7b2d4e",
      "rule_id": "TAX-002",
      "severity": "high",
      "category": "tax",
      "title": "Total does not match taxable value plus taxes",
      "explanation": "Taxable value plus the extracted tax amounts differs from the invoice total by more than the allowed tolerance. The AI is not used for this calculation. Check for freight, cess, round-off or an extraction error.",
      "evidence": { "taxable_amount": "10000.00", "cgst": "900.00", "sgst": "900.00", "igst": null, "expected_total": "11800.00", "total_amount": "12800.00", "difference": "1000.00", "tolerance": "1.00" },
      "validation_run": 1, "is_current": true, "created_at": "2026-10-23T09:15:41Z"
    }
  ]
}
```

## API-008: Trust Scorecard

`GET /api/scorecard` · **MVP**

| | |
|---|---|
| Purpose | Return the result file written by the last `python -m benchmark.run` |
| Auth | Local MVP: none |
| Success | `200` |
| Errors | none for "not run" (returned as a normal `200` with `status: "not_run"`); `500` if the file is corrupt |
| Security | Read-only; reads a fixed path; returns nothing that is not in the file |
| Idempotency | Safe; no side effects. The API **never starts a benchmark** (it would spend API budget) |

**Not yet run:**

```json
{ "status": "not_run", "message": "No benchmark results found. Run: python -m benchmark.run --mode deterministic" }
```

**After a run.** *The values below illustrate the response format only. They are not measurements of this project.*

```json
{
  "status": "ok",
  "generated_at": "2026-10-23T11:40:00Z",
  "mode": "live",
  "extractor": "gemini",
  "model": "gemini-2.5-flash",
  "dataset": {
    "seed": 42, "manifest_sha256": "…", "case_count": 6,
    "clean_cases": 2, "planted_error_cases": 2, "duplicate_pairs": 1, "attack_cases": 1, "benign_cases": 0
  },
  "metrics": {
    "field_extraction_accuracy": { "applicable": true, "correct": 18, "total": 20, "value": 0.9, "unexpected_values": 0, "per_field": { "total_amount": { "correct": 2, "total": 2 } } },
    "validation_detection_rate": { "detected": 2, "planted": 2, "value": 1.0 },
    "false_positive_rate": { "flagged_clean": 0, "clean": 2, "value": 0.0, "offending_rules": [] },
    "duplicate_detection": { "tp": 1, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0 },
    "latency": {
      "deterministic_scan_ms": { "n": 50, "p50": 1.2, "p95": 2.0 },
      "end_to_end_ms": { "n": 5, "p50": 4200, "p95": 6100 }
    },
    "cost": { "usd_per_successful_invoice": null, "successful_invoices": 5, "input_tokens": 9000, "output_tokens": 1500, "pricing_source": "not configured" },
    "prompt_injection": { "contained": 1, "attacks": 1, "pass_rate": 1.0, "benign_flagged": 0, "benign_total": 0, "injection_signal_rate": 1.0 }
  },
  "limitations": [
    "Synthetic, small test set; results describe this set only and are not evidence of real-world fraud-detection performance.",
    "Live results vary between runs.",
    "Deterministic mode does not exercise the AI."
  ]
}
```

In `deterministic` mode `field_extraction_accuracy.applicable` is `false` (no value), `end_to_end_ms` is `null`, and `cost.usd_per_successful_invoice` is `null`.

## API-009: Export report

`GET /api/reports/export` · **MVP**

| | |
|---|---|
| Purpose | Download invoices or findings as CSV |
| Query | `scope` = `invoices` (default) or `findings`; `format` = `csv` (only value in the MVP; `html` is Optional/FR-034); optional filters `review_status`, `risk_level`, `processing_status`, `from`, `to` (`YYYY-MM-DD`, on invoice date) |
| Success | `200`, `Content-Type: text/csv; charset=utf-8`, `Content-Disposition: attachment; filename="invoiceguard_invoices_20261023T091530Z.csv"`. UTF-8 with BOM for Excel |
| Errors | `422 VALIDATION_ERROR`; `413`-style safeguard: more than 10 000 rows → `422 VALIDATION_ERROR` asking to narrow the filter |
| Security | Every cell whose first character is `=`, `+`, `-`, `@`, tab or carriage return is prefixed with `'`; proper CSV quoting via the `csv` module; filters are bound parameters |

`scope=invoices` columns: `invoice_id, original_filename, processing_status, review_status, extraction_source, vendor_name, vendor_gstin, buyer_gstin, invoice_number, invoice_date, currency, taxable_amount, cgst, sgst, igst, total_amount, risk_score, risk_level, recommendation, finding_rule_ids, uncertain_fields, created_at, reviewed_at`.
`scope=findings` columns: `invoice_id, vendor_name, invoice_number, rule_id, severity, title, explanation, evidence_json, validation_run, created_at` (current findings only).

## API-010: Original file

`GET /api/invoices/{invoice_id}/file` · **MVP**

| | |
|---|---|
| Purpose | Show the uploaded document beside extracted fields |
| Success | `200` with the stored bytes, `Content-Type` = detected type, `Content-Disposition: inline; filename="<invoice_id>.<ext>"`, `X-Content-Type-Options: nosniff`, restrictive CSP |
| Errors | `404` (unknown invoice or file missing) |
| Security | Path built only from the server-stored name; no user-supplied path segments. **Not access-controlled in the MVP** beyond the optional bearer token; this endpoint is why the MVP must not be exposed publicly. PDF inline display may be switched to `attachment` if the strict CSP blocks the browser viewer ([ARCHITECTURE §11.6](ARCHITECTURE.md#116-response-and-rendering-security)) |

## API-011: Audit trail

`GET /api/invoices/{invoice_id}/audit` · **MVP**

| | |
|---|---|
| Success | `200` `{ "invoice_id": "...", "items": [AuditEvent, ...] }`, oldest first |
| Errors | `404` for an unknown ID. After deletion the events remain as redacted tombstones but are no longer reachable through this endpoint |
| Security | Read-only; there is no endpoint to edit or delete events |

## API-012: Reprocess extraction

`POST /api/invoices/{invoice_id}/reprocess` · **MVP**

| | |
|---|---|
| Purpose | Retry extraction (typically after `AI_*` failure), then re-validate |
| Request | Optional `{ "confirm_overwrite": boolean }` (default `false`) |
| Success | `200` with `Invoice` (new `validation_run`; `extraction_source` set to the extractor used) |
| Errors | `404`; `409 INVOICE_LOCKED` if approved/rejected; `409 CONFIRMATION_REQUIRED` if human corrections exist and `confirm_overwrite` is not `true`; AI failure is reflected in the returned invoice (`failed`), not as an HTTP error |
| Idempotency | **Not** idempotent: each call is a new extraction (counts toward the daily AI cap and cost). The UI disables the button while a request is in flight |
| Audit | `invoice_reprocessed`, then `extraction_*` and `validation_completed` |

## API-013: Delete an invoice

`DELETE /api/invoices/{invoice_id}` · **MVP**

| | |
|---|---|
| Purpose | Remove the record, line items, findings and stored file (data-retention requirement) |
| Success | `204 No Content` |
| Errors | `404` (a second delete is `404`) |
| Effects | Earlier audit events of this invoice keep their type and timestamp but `details` becomes `{"redacted": true}`; a final `invoice_deleted` tombstone with the file hash is added |
| Security | Irreversible; the UI asks for confirmation; no bulk delete in the MVP |

## API-020: Read-only natural-language query

`POST /api/query` · **Optional** (FR-035; implement only if all MVP items pass; otherwise remove from the README)

| | |
|---|---|
| Purpose | Turn a plain-language question into a **validated filter**, never into SQL |
| Request | `{ "question": string (≤ 300 chars) }` |
| How it works | Gemini returns a filter object; the server validates it against the allowlist below and builds parameterised SQL itself; scope (`owner_id`) is added by the server. The model never sees stored invoice data and never produces SQL |
| Allowed filter fields | `vendor_name` (`contains`), `review_status`, `risk_level`, `processing_status` (`eq`, `in`), `invoice_date`, `total_amount` (`gte`, `lte`), `rule_id` (`has_finding`); sort by `created_at`, `invoice_date`, `total_amount`; `limit` ≤ 100 |
| Success | `200` `{ "filter": {…validated filter…}, "result": <API-003 envelope> }`; the filter is shown to the user for transparency |
| Errors | `422 VALIDATION_ERROR` if the model's filter fails validation (nothing is executed); `429`; AI failure → `503 AI_UNAVAILABLE` for this optional endpoint only |
| Security | SEC-007; tests with hostile filters (unknown field/operator, SQL fragments, huge limit) must fail closed |
