export type ReviewStatus = 'pending' | 'flagged' | 'approved' | 'rejected' | 'NEEDS_REVIEW' | 'FLAGGED' | 'APPROVED' | 'REJECTED';
export type RiskLevel = 'low' | 'medium' | 'high' | 'LOW' | 'MEDIUM' | 'HIGH';
export type FindingSeverity = 'high' | 'medium' | 'low' | 'info' | 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

export interface LineItem {
  line_no?: number;
  description?: string | null;
  hsn_sac?: string | null;
  quantity?: string | null;
  unit_price?: string | null;
  tax_rate?: string | null;
  amount?: string | null;
}

export interface ExtractedFields {
  vendor_name?: string | null;
  vendor_gstin?: string | null;
  buyer_gstin?: string | null;
  customer_name?: string | null;
  customer_gstin?: string | null;
  invoice_number?: string | null;
  invoice_date?: string | null;
  currency?: string | null;
  currency_assumed?: boolean;
  taxable_amount?: string | null;
  subtotal?: string | null;
  cgst?: string | null;
  sgst?: string | null;
  igst?: string | null;
  tax_amount?: string | null;
  total_amount?: string | null;
  line_items?: LineItem[];
}

export interface UncertainField {
  field: string;
  reason: string;
  raw_value?: string | null;
}

export interface ValidationFinding {
  finding_id?: string;
  id?: string;
  rule_id: string;
  severity: FindingSeverity;
  category?: string;
  title?: string;
  explanation?: string;
  message?: string;
  evidence: Record<string, unknown>;
  points?: number;
  validation_run?: number;
  is_current?: boolean;
  created_at?: string;
}

export interface RuleContribution {
  rule_id: string;
  name?: string;
  severity?: FindingSeverity;
  points: number;
  triggered?: boolean;
}

export interface RiskAssessment {
  score?: number | null;
  level?: RiskLevel | null;
  recommendation?: string;
  breakdown: RuleContribution[];
  findings?: ValidationFinding[];
}

export interface InvoiceSummary {
  invoice_id: string;
  id?: string;
  original_filename: string;
  filename?: string;
  file_size?: number;
  file_size_bytes?: number;
  mime_type?: string;
  content_type?: string;
  created_at: string;
  updated_at?: string;
  vendor_name?: string | null;
  invoice_number?: string | null;
  invoice_date?: string | null;
  total_amount?: string | null;
  currency?: string | null;
  processing_status?: string;
  review_status: ReviewStatus;
  risk?: RiskAssessment;
  risk_level?: RiskLevel;
  risk_score?: number;
  uncertain_field_count?: number;
  critical_findings_count?: number;
}

export interface InvoiceDetail {
  invoice_id: string;
  id?: string;
  original_filename: string;
  filename?: string;
  file_size_bytes?: number;
  file_size?: number;
  content_type?: string;
  mime_type?: string;
  file_sha256?: string;
  file_hash?: string;
  fields: ExtractedFields;
  line_items?: LineItem[];
  uncertain_fields?: UncertainField[];
  risk: RiskAssessment;
  findings?: ValidationFinding[];
  findings_summary?: Record<string, number>;
  processing_status: string;
  review_status: ReviewStatus;
  review_comment?: string | null;
  reviewer_id?: string | null;
  reviewed_at?: string | null;
  validation_run?: number;
  created_at: string;
  updated_at: string;
}

export interface InvoiceListResponse {
  items: InvoiceSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditLogEntry {
  event_id?: string;
  id?: string;
  invoice_id: string;
  event_type: string;
  actor: string;
  details?: Record<string, unknown>;
  payload?: Record<string, unknown>;
  created_at: string;
}

export interface ReviewActionPayload {
  action: 'approve' | 'flag' | 'reject' | 'reopen';
  comment?: string;
  acknowledge_risk?: boolean;
}

export interface ScorecardMetrics {
  validation_detection_rate?: {
    detected: number;
    planted: number;
    value: number | null;
  };
  false_positive_rate?: {
    flagged_clean: number;
    clean: number;
    value: number | null;
    offending_rules: string[];
  };
  duplicate_detection?: {
    tp: number;
    fp: number;
    fn: number;
    precision: number;
    recall: number;
  };
  latency?: {
    deterministic_scan_ms?: {
      n: number;
      p50: number;
      p95: number;
    };
    end_to_end_ms?: {
      p50?: number;
      p95?: number;
    } | null;
  };
  prompt_injection?: {
    contained: number;
    attacks: number;
    pass_rate: number;
    benign_flagged: number;
    benign_total: number;
  };
}

export interface ScorecardDataset {
  seed: number;
  manifest_sha256: string;
  case_count: number;
  clean_cases: number;
  planted_error_cases: number;
  duplicate_pairs: number;
  attack_cases: number;
  benign_cases: number;
}

export interface ScorecardResponse {
  status: string;
  generated_at?: string;
  mode?: string;
  extractor?: string;
  model?: string;
  dataset?: ScorecardDataset;
  metrics?: ScorecardMetrics;
  limitations?: string[];
  message?: string;
  detail?: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  extractor?: string;
  gemini_configured: boolean;
  database: string;
  time?: string;
  timestamp?: string;
}
