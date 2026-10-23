import type {
  InvoiceListResponse,
  InvoiceDetail,
  ValidationFinding,
  AuditLogEntry,
  ReviewActionPayload,
  ScorecardResponse,
  HealthResponse,
} from './types';

const API_BASE = '';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorMsg = `HTTP Error ${res.status}: ${res.statusText}`;
    try {
      const errorJson = await res.json();
      if (typeof errorJson.detail === 'string') {
        errorMsg = errorJson.detail;
      } else if (Array.isArray(errorJson.detail)) {
        errorMsg = errorJson.detail.map((e: { msg?: string }) => e.msg || JSON.stringify(e)).join(', ');
      }
    } catch {
      // response wasn't JSON
    }
    throw new Error(errorMsg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  async getHealth(): Promise<HealthResponse> {
    const res = await fetch(`${API_BASE}/health`);
    return handleResponse<HealthResponse>(res);
  },

  async getInvoices(params?: {
    review_status?: string;
    risk_level?: string;
    q?: string;
    limit?: number;
    offset?: number;
  }): Promise<InvoiceListResponse> {
    const query = new URLSearchParams();
    if (params?.review_status && params.review_status !== 'ALL') {
      const s = params.review_status.toLowerCase();
      query.set('review_status', s === 'needs_review' ? 'pending' : s);
    }
    if (params?.risk_level && params.risk_level !== 'ALL') {
      query.set('risk_level', params.risk_level.toLowerCase());
    }
    if (params?.q) query.set('q', params.q);
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));

    const res = await fetch(`${API_BASE}/api/invoices?${query.toString()}`);
    return handleResponse<InvoiceListResponse>(res);
  },

  async getInvoice(id: string): Promise<InvoiceDetail> {
    const res = await fetch(`${API_BASE}/api/invoices/${id}`);
    return handleResponse<InvoiceDetail>(res);
  },

  async uploadInvoice(file: File): Promise<InvoiceDetail> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/api/invoices/upload`, {
      method: 'POST',
      body: formData,
    });
    const data = await handleResponse<{ invoice: InvoiceDetail } | InvoiceDetail>(res);
    return 'invoice' in data ? data.invoice : data;
  },

  async updateInvoiceFields(
    id: string,
    updates: Record<string, unknown>,
    _reason?: string
  ): Promise<InvoiceDetail> {
    const res = await fetch(`${API_BASE}/api/invoices/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fields: updates }),
    });
    return handleResponse<InvoiceDetail>(res);
  },

  async reviewInvoice(id: string, payload: ReviewActionPayload): Promise<InvoiceDetail> {
    const res = await fetch(`${API_BASE}/api/invoices/${id}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await handleResponse<{ invoice: InvoiceDetail } | InvoiceDetail>(res);
    return 'invoice' in data ? data.invoice : data;
  },

  async getInvoiceFindings(id: string): Promise<ValidationFinding[]> {
    const res = await fetch(`${API_BASE}/api/invoices/${id}/findings`);
    const data = await handleResponse<{ items: ValidationFinding[] } | ValidationFinding[]>(res);
    return Array.isArray(data) ? data : data.items || [];
  },

  async getInvoiceAudit(id: string): Promise<AuditLogEntry[]> {
    const res = await fetch(`${API_BASE}/api/invoices/${id}/audit`);
    const data = await handleResponse<{ items: AuditLogEntry[] } | AuditLogEntry[]>(res);
    return Array.isArray(data) ? data : data.items || [];
  },

  async deleteInvoice(id: string): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/api/invoices/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      throw new Error(`Failed to delete invoice: ${res.statusText}`);
    }
    return { success: true, message: 'Invoice removed' };
  },

  async getScorecard(): Promise<ScorecardResponse> {
    const res = await fetch(`${API_BASE}/api/scorecard`);
    return handleResponse<ScorecardResponse>(res);
  },

  getFileUrl(id: string): string {
    return `${API_BASE}/api/invoices/${id}/file`;
  },

  getExportCsvUrl(scope: 'invoices' | 'findings' = 'invoices'): string {
    return `${API_BASE}/api/reports/export?scope=${scope}`;
  },
};
