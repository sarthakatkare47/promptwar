PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS invoices (
    invoice_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT 'local',
    original_filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    file_sha256 TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    processing_status TEXT NOT NULL CHECK(processing_status IN ('queued','extracting','validating','ready','failed')),
    review_status TEXT NOT NULL DEFAULT 'pending' CHECK(review_status IN ('pending','flagged','approved','rejected')),
    extraction_source TEXT CHECK(extraction_source IN ('gemini','mock','manual')),
    extraction_model TEXT,
    document_type TEXT,
    vendor_name TEXT,
    vendor_gstin TEXT,
    buyer_gstin TEXT,
    invoice_number TEXT,
    invoice_date TEXT,
    currency TEXT,
    currency_assumed INTEGER DEFAULT 0,
    taxable_paise INTEGER,
    cgst_paise INTEGER,
    sgst_paise INTEGER,
    igst_paise INTEGER,
    total_paise INTEGER,
    vendor_key TEXT,
    invoice_number_key TEXT,
    uncertain_fields_json TEXT NOT NULL DEFAULT '[]',
    extracted_json TEXT,
    risk_score INTEGER,
    risk_level TEXT CHECK(risk_level IN ('low','medium','high')),
    recommendation TEXT CHECK(recommendation IN ('no_issues_detected','review_recommended','high_priority_review','manual_entry_required')),
    validation_run INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    reviewed_at TEXT,
    UNIQUE (owner_id, file_sha256)
);

CREATE TABLE IF NOT EXISTS line_items (
    line_id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id TEXT NOT NULL REFERENCES invoices(invoice_id) ON DELETE CASCADE,
    line_no INTEGER NOT NULL,
    description TEXT,
    hsn_sac TEXT,
    quantity TEXT,
    unit_price_paise INTEGER,
    amount_paise INTEGER,
    UNIQUE (invoice_id, line_no)
);

CREATE TABLE IF NOT EXISTS findings (
    finding_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(invoice_id) ON DELETE CASCADE,
    validation_run INTEGER NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 1,
    rule_id TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('high','medium','low','info')),
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    explanation TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_calls (
    call_id TEXT PRIMARY KEY,
    invoice_id TEXT REFERENCES invoices(invoice_id) ON DELETE SET NULL,
    purpose TEXT NOT NULL,
    model TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    status TEXT NOT NULL,
    error_code TEXT,
    latency_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_invoices_dup ON invoices(owner_id, vendor_key, invoice_number_key);
CREATE INDEX IF NOT EXISTS ix_invoices_dup3 ON invoices(owner_id, vendor_key, invoice_date, total_paise);
CREATE INDEX IF NOT EXISTS ix_invoices_list ON invoices(owner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_invoices_status ON invoices(owner_id, review_status, risk_level);
CREATE INDEX IF NOT EXISTS ix_findings_inv ON findings(invoice_id, validation_run, is_current);
CREATE INDEX IF NOT EXISTS ix_lines_inv ON line_items(invoice_id);
CREATE INDEX IF NOT EXISTS ix_audit_inv ON audit_events(invoice_id, created_at);
CREATE INDEX IF NOT EXISTS ix_ai_created ON ai_calls(created_at);
