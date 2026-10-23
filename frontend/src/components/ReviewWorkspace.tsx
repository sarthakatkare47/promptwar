import React, { useState, useEffect } from 'react';
import {
  ArrowLeft,
  CheckCircle2,
  Flag,
  XCircle,
  AlertTriangle,
  FileText,
  Save,
  ShieldCheck,
  ShieldAlert,
  Info,
  ExternalLink,
  History,
  Check,
  AlertCircle,
  HelpCircle,
  RotateCcw,
} from 'lucide-react';
import type {
  InvoiceDetail,
  ValidationFinding,
  AuditLogEntry,
  ExtractedFields,
} from '../types';
import { api } from '../api';

interface ReviewWorkspaceProps {
  invoiceId: string;
  onBack: () => void;
  onInvoiceUpdated: (updated: InvoiceDetail) => void;
}

type TabType = 'fields' | 'findings' | 'audit';

export const ReviewWorkspace: React.FC<ReviewWorkspaceProps> = ({
  invoiceId,
  onBack,
  onInvoiceUpdated,
}) => {
  const [invoice, setInvoice] = useState<InvoiceDetail | null>(null);
  const [findings, setFindings] = useState<ValidationFinding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('fields');

  // Editable fields state
  const [formData, setFormData] = useState<Partial<ExtractedFields>>({});
  const [editReason, setEditReason] = useState('Manual verification correction');
  const [savingFields, setSavingFields] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Review modal state
  const [modalAction, setModalAction] = useState<'approve' | 'flag' | 'reject' | 'reopen' | null>(null);
  const [reviewComment, setReviewComment] = useState('');
  const [acknowledgeRisk, setAcknowledgeRisk] = useState(false);
  const [submittingAction, setSubmittingAction] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Audit log state
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);

  // Load invoice details & findings
  const fetchInvoice = async () => {
    setLoading(true);
    setError(null);
    try {
      const [invData, findingsData] = await Promise.all([
        api.getInvoice(invoiceId),
        api.getInvoiceFindings(invoiceId).catch(() => []),
      ]);
      setInvoice(invData);
      setFormData(invData.fields || {});
      setFindings(findingsData.length > 0 ? findingsData : invData.findings || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch invoice');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInvoice();
  }, [invoiceId]);

  // Load audit log when audit tab opened
  useEffect(() => {
    if (activeTab === 'audit') {
      setLoadingAudit(true);
      api
        .getInvoiceAudit(invoiceId)
        .then((log) => setAuditLog(log))
        .catch(() => {})
        .finally(() => setLoadingAudit(false));
    }
  }, [activeTab, invoiceId]);

  const handleFieldChange = (key: keyof ExtractedFields, value: string) => {
    setFormData((prev) => ({
      ...prev,
      [key]: value,
    }));
    setSaveSuccess(false);
  };

  const handleSaveCorrections = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!invoice) return;

    setSavingFields(true);
    setError(null);
    try {
      const updated = await api.updateInvoiceFields(
        invoice.invoice_id || invoice.id || invoiceId,
        formData as Record<string, unknown>,
        editReason
      );
      setInvoice(updated);
      setFormData(updated.fields || {});
      // Refresh findings
      const newFindings = await api.getInvoiceFindings(invoiceId).catch(() => []);
      setFindings(newFindings.length > 0 ? newFindings : updated.findings || []);
      onInvoiceUpdated(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save field corrections');
    } finally {
      setSavingFields(false);
    }
  };

  const handleReviewActionSubmit = async () => {
    if (!invoice || !modalAction) return;

    const riskLevel = (invoice.risk?.level || 'low').toLowerCase();

    if (modalAction === 'approve' && riskLevel === 'high' && !acknowledgeRisk) {
      setActionError('You must acknowledge the high-risk finding before approving.');
      return;
    }

    if ((modalAction === 'flag' || modalAction === 'reject' || modalAction === 'reopen') && !reviewComment.trim()) {
      setActionError('A comment is required for this action.');
      return;
    }

    setSubmittingAction(true);
    setActionError(null);
    try {
      const targetId = invoice.invoice_id || invoice.id || invoiceId;
      const updated = await api.reviewInvoice(targetId, {
        action: modalAction,
        comment: reviewComment.trim() || 'Approved via Review Workspace',
        acknowledge_risk: acknowledgeRisk,
      });

      setInvoice(updated);
      onInvoiceUpdated(updated);
      setModalAction(null);
      setReviewComment('');
      setAcknowledgeRisk(false);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Action submission failed');
    } finally {
      setSubmittingAction(false);
    }
  };

  if (loading) {
    return (
      <div className="py-24 text-center">
        <div className="w-12 h-12 mx-auto rounded-full border-4 border-slate-800 border-t-cyan-400 animate-spin mb-4" />
        <p className="text-slate-400 text-sm">Loading invoice and deterministic findings...</p>
      </div>
    );
  }

  if (error && !invoice) {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center">
        <div className="w-12 h-12 mx-auto mb-4 rounded-xl bg-rose-500/20 text-rose-400 flex items-center justify-center">
          <AlertCircle className="w-6 h-6" />
        </div>
        <h3 className="text-lg font-semibold text-white">Error Loading Invoice</h3>
        <p className="text-xs text-rose-300 font-mono mt-2 mb-6">{error}</p>
        <button
          onClick={onBack}
          className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs rounded-xl font-medium inline-flex items-center space-x-1.5"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Invoices</span>
        </button>
      </div>
    );
  }

  if (!invoice) return null;

  const currentId = invoice.invoice_id || invoice.id || invoiceId;
  const currentFilename = invoice.original_filename || invoice.filename || 'invoice';
  const rawStatus = (invoice.review_status || 'pending').toLowerCase();
  const isLocked = rawStatus === 'approved' || rawStatus === 'rejected';
  const fileUrl = api.getFileUrl(currentId);
  const mime = invoice.content_type || invoice.mime_type || '';
  const isPdf = mime.includes('pdf');
  const riskScore = invoice.risk?.score ?? 0;
  const riskLevel = (invoice.risk?.level || 'low').toLowerCase();

  return (
    <div className="pb-16 animate-in fade-in duration-200">
      {/* Top Bar Navigation & Header */}
      <div className="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-center space-x-3">
          <button
            onClick={onBack}
            className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 transition-colors"
            title="Back to Invoices List"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg sm:text-xl font-bold text-white tracking-tight">
                {invoice.fields?.invoice_number ? `Invoice #${invoice.fields.invoice_number}` : currentFilename}
              </h1>
              {/* Review Status Badge */}
              <span
                className={`text-xs px-2.5 py-0.5 rounded-full font-bold uppercase border ${
                  rawStatus === 'approved'
                    ? 'bg-emerald-950 text-emerald-300 border-emerald-700'
                    : rawStatus === 'flagged'
                    ? 'bg-purple-950 text-purple-300 border-purple-700'
                    : rawStatus === 'rejected'
                    ? 'bg-rose-950 text-rose-300 border-rose-700'
                    : 'bg-amber-950 text-amber-300 border-amber-700'
                }`}
              >
                {rawStatus === 'pending' ? 'Needs Review' : rawStatus}
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              File: {currentFilename} ({((invoice.file_size_bytes || invoice.file_size || 0) / 1024).toFixed(1)} KB) • ID: {currentId}
            </p>
          </div>
        </div>

        {/* Action Decision Buttons */}
        <div className="flex items-center space-x-2">
          {isLocked ? (
            <div className="flex items-center space-x-2">
              <span className="text-xs text-slate-400 italic">
                Locked ({rawStatus})
              </span>
              <button
                onClick={() => {
                  setModalAction('reopen');
                  setReviewComment('');
                  setActionError(null);
                }}
                className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-600 flex items-center space-x-1.5 transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5 text-cyan-400" />
                <span>Reopen Invoice</span>
              </button>
            </div>
          ) : (
            <>
              {/* Approve Button */}
              <button
                onClick={() => {
                  setModalAction('approve');
                  setReviewComment('');
                  setAcknowledgeRisk(false);
                  setActionError(null);
                }}
                className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center space-x-1.5 transition-colors shadow-lg ${
                  riskLevel === 'high'
                    ? 'bg-amber-600 hover:bg-amber-500 text-white'
                    : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/20'
                }`}
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>{riskLevel === 'high' ? 'Approve with Override' : 'Approve Invoice'}</span>
              </button>

              {/* Flag Button */}
              <button
                onClick={() => {
                  setModalAction('flag');
                  setReviewComment('');
                  setActionError(null);
                }}
                className="px-3.5 py-2 rounded-xl bg-purple-900/60 hover:bg-purple-800/80 text-purple-200 border border-purple-700/60 text-xs font-bold flex items-center space-x-1.5 transition-colors"
              >
                <Flag className="w-4 h-4 text-purple-400" />
                <span>Flag</span>
              </button>

              {/* Reject Button */}
              <button
                onClick={() => {
                  setModalAction('reject');
                  setReviewComment('');
                  setActionError(null);
                }}
                className="px-3.5 py-2 rounded-xl bg-rose-950/70 hover:bg-rose-900 text-rose-300 border border-rose-800/70 text-xs font-bold flex items-center space-x-1.5 transition-colors"
              >
                <XCircle className="w-4 h-4 text-rose-400" />
                <span>Reject</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Main Review Grid: Left = Document Preview, Right = Review Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Side: Document Preview (5 cols) */}
        <div className="lg:col-span-5 flex flex-col">
          <div className="glass-panel rounded-2xl border border-slate-800 p-4 flex-1 flex flex-col min-h-[500px]">
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800 text-xs text-slate-300">
              <span className="font-semibold flex items-center space-x-1.5">
                <FileText className="w-4 h-4 text-cyan-400" />
                <span>Original Document</span>
              </span>
              <a
                href={fileUrl}
                target="_blank"
                rel="noreferrer"
                className="flex items-center space-x-1 text-cyan-400 hover:text-cyan-300 hover:underline"
              >
                <span>Full View</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>

            <div className="flex-1 bg-slate-950/80 rounded-xl border border-slate-900 overflow-hidden flex items-center justify-center relative min-h-[440px]">
              {isPdf ? (
                <iframe
                  src={`${fileUrl}#toolbar=0`}
                  title="PDF Preview"
                  className="w-full h-full min-h-[500px] border-0"
                />
              ) : (
                <img
                  src={fileUrl}
                  alt="Invoice Document"
                  className="max-h-[550px] max-w-full object-contain p-2"
                />
              )}
            </div>

            <div className="mt-3 text-[11px] text-slate-500 flex items-center justify-between">
              <span>MIME: {mime}</span>
              <span className="font-mono text-[10px]">SHA: {(invoice.file_sha256 || invoice.file_hash || '').slice(0, 16)}...</span>
            </div>
          </div>
        </div>

        {/* Right Side: Data, Findings & Audit Tabs (7 cols) */}
        <div className="lg:col-span-7 flex flex-col space-y-4">
          {/* Risk Overview Callout */}
          <div
            className={`p-4 rounded-2xl border flex items-center justify-between ${
              riskLevel === 'high'
                ? 'bg-rose-950/40 border-rose-800/80 glow-rose'
                : riskLevel === 'medium'
                ? 'bg-amber-950/40 border-amber-800/80 glow-amber'
                : 'bg-emerald-950/40 border-emerald-800/80 glow-emerald'
            }`}
          >
            <div className="flex items-center space-x-3">
              <div
                className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-lg ${
                  riskLevel === 'high'
                    ? 'bg-rose-500 text-white'
                    : riskLevel === 'medium'
                    ? 'bg-amber-500 text-slate-950'
                    : 'bg-emerald-500 text-white'
                }`}
              >
                {riskScore}
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-bold text-white uppercase">Risk Level: {riskLevel}</span>
                  <span className="text-xs text-slate-400">({riskScore}/100 points)</span>
                </div>
                <p className="text-xs text-slate-300">
                  {findings.length === 0
                    ? 'All 7 deterministic security & arithmetic rules passed cleanly.'
                    : `${findings.length} rule ${findings.length === 1 ? 'finding' : 'findings'} triggered by audit engine.`}
                </p>
              </div>
            </div>

            {riskLevel === 'high' && (
              <span className="px-2 py-1 rounded bg-rose-600 text-white text-[10px] font-bold uppercase tracking-wider animate-pulse">
                High Risk Alert
              </span>
            )}
          </div>

          {/* Uncertainty Callout */}
          {invoice.uncertain_fields && invoice.uncertain_fields.length > 0 && (
            <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-800/80 text-xs text-amber-200 flex items-start space-x-2.5">
              <HelpCircle className="w-5 h-5 flex-shrink-0 text-amber-400 mt-0.5" />
              <div>
                <span className="font-semibold text-amber-300">AI Flagged Uncertain Extracted Values:</span>
                <ul className="list-disc list-inside mt-1 space-y-0.5 text-amber-200/90 text-[11px]">
                  {invoice.uncertain_fields.map((u, idx) => (
                    <li key={idx}>
                      <span className="font-mono font-medium">{u.field}</span>: {u.reason}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Critical GSTIN Disclaimer Banner */}
          <div className="p-3 rounded-xl bg-slate-900 border border-slate-700/80 text-[11px] text-slate-300 flex items-start space-x-2">
            <Info className="w-4 h-4 text-cyan-400 flex-shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold text-cyan-400">GSTIN Verification Note: </span>
              <span>
                Algorithm checks format and validates checksum modulo-36. <strong>It does NOT query the live GST Portal or prove active tax registration.</strong>
              </span>
            </div>
          </div>

          {/* Workspace Tabs */}
          <div className="glass-panel rounded-2xl border border-slate-800 overflow-hidden flex-1 flex flex-col">
            {/* Tab Headers */}
            <div className="flex border-b border-slate-800 bg-slate-900/60 px-4 pt-2">
              <button
                onClick={() => setActiveTab('fields')}
                className={`px-4 py-2.5 text-xs font-semibold border-b-2 flex items-center space-x-1.5 transition-colors ${
                  activeTab === 'fields'
                    ? 'border-cyan-400 text-cyan-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Extracted Fields & Corrections</span>
              </button>

              <button
                onClick={() => setActiveTab('findings')}
                className={`px-4 py-2.5 text-xs font-semibold border-b-2 flex items-center space-x-1.5 transition-colors relative ${
                  activeTab === 'findings'
                    ? 'border-cyan-400 text-cyan-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <ShieldAlert className="w-3.5 h-3.5" />
                <span>Findings & Evidence</span>
                {findings.length > 0 && (
                  <span className="ml-1.5 px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-600/40">
                    {findings.length}
                  </span>
                )}
              </button>

              <button
                onClick={() => setActiveTab('audit')}
                className={`px-4 py-2.5 text-xs font-semibold border-b-2 flex items-center space-x-1.5 transition-colors ${
                  activeTab === 'audit'
                    ? 'border-cyan-400 text-cyan-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <History className="w-3.5 h-3.5" />
                <span>Audit Trail</span>
              </button>
            </div>

            {/* Tab 1: Extracted Fields Form */}
            {activeTab === 'fields' && (
              <form onSubmit={handleSaveCorrections} className="p-5 space-y-4 flex-1">
                {isLocked && (
                  <div className="p-2.5 rounded-lg bg-slate-800/80 border border-slate-700 text-xs text-slate-300">
                    This invoice is currently <strong>locked ({rawStatus})</strong>. Reopen it to modify fields.
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* Vendor Name */}
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Vendor Name
                    </label>
                    <input
                      type="text"
                      disabled={isLocked}
                      value={formData.vendor_name || ''}
                      onChange={(e) => handleFieldChange('vendor_name', e.target.value)}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 disabled:opacity-60 focus:outline-none focus:border-cyan-500"
                    />
                  </div>

                  {/* Vendor GSTIN */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-medium text-slate-400">
                        Vendor GSTIN
                      </label>
                      {invoice.uncertain_fields?.some((u) => u.field === 'vendor_gstin') && (
                        <span className="text-[10px] text-amber-400 font-semibold">Uncertain</span>
                      )}
                    </div>
                    <input
                      type="text"
                      disabled={isLocked}
                      value={formData.vendor_gstin || ''}
                      onChange={(e) => handleFieldChange('vendor_gstin', e.target.value.toUpperCase())}
                      className={`w-full px-3 py-2 bg-slate-900 border rounded-xl text-xs font-mono text-slate-100 disabled:opacity-60 focus:outline-none focus:border-cyan-500 ${
                        findings.some((f) => f.rule_id.startsWith('RULE-GSTIN'))
                          ? 'border-rose-500/80 bg-rose-950/20'
                          : 'border-slate-700'
                      }`}
                    />
                  </div>

                  {/* Customer / Buyer GSTIN */}
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Buyer / Customer GSTIN
                    </label>
                    <input
                      type="text"
                      disabled={isLocked}
                      value={formData.buyer_gstin || formData.customer_gstin || ''}
                      onChange={(e) => handleFieldChange('buyer_gstin', e.target.value.toUpperCase())}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs font-mono text-slate-100 disabled:opacity-60 focus:outline-none focus:border-cyan-500"
                    />
                  </div>

                  {/* Invoice Number */}
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Invoice Number
                    </label>
                    <input
                      type="text"
                      disabled={isLocked}
                      value={formData.invoice_number || ''}
                      onChange={(e) => handleFieldChange('invoice_number', e.target.value)}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 disabled:opacity-60 focus:outline-none focus:border-cyan-500"
                    />
                  </div>

                  {/* Invoice Date */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-medium text-slate-400">
                        Invoice Date (YYYY-MM-DD)
                      </label>
                      {findings.some((f) => f.rule_id.startsWith('RULE-DATE')) && (
                        <span className="text-[10px] text-rose-400 font-semibold">Date Alert</span>
                      )}
                    </div>
                    <input
                      type="text"
                      disabled={isLocked}
                      placeholder="YYYY-MM-DD"
                      value={formData.invoice_date || ''}
                      onChange={(e) => handleFieldChange('invoice_date', e.target.value)}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs font-mono text-slate-100 disabled:opacity-60 focus:outline-none focus:border-cyan-500"
                    />
                  </div>

                  {/* Taxable Amount / Subtotal */}
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Taxable Amount (Subtotal)
                    </label>
                    <input
                      type="text"
                      disabled={isLocked}
                      value={formData.taxable_amount || formData.subtotal || ''}
                      onChange={(e) => {
                        handleFieldChange('taxable_amount', e.target.value);
                        handleFieldChange('subtotal', e.target.value);
                      }}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs font-mono text-slate-100 disabled:opacity-60 focus:outline-none focus:border-cyan-500"
                    />
                  </div>

                  {/* CGST */}
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      CGST
                    </label>
                    <input
                      type="text"
                      disabled={isLocked}
                      value={formData.cgst || ''}
                      onChange={(e) => handleFieldChange('cgst', e.target.value)}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs font-mono text-slate-100 disabled:opacity-60 focus:outline-none focus:border-cyan-500"
                    />
                  </div>

                  {/* SGST */}
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      SGST
                    </label>
                    <input
                      type="text"
                      disabled={isLocked}
                      value={formData.sgst || ''}
                      onChange={(e) => handleFieldChange('sgst', e.target.value)}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs font-mono text-slate-100 disabled:opacity-60 focus:outline-none focus:border-cyan-500"
                    />
                  </div>

                  {/* Total Amount */}
                  <div className="sm:col-span-2">
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-medium text-slate-300">
                        Total Amount
                      </label>
                      {findings.some((f) => f.rule_id === 'RULE-TAX-001') && (
                        <span className="text-[10px] text-rose-400 font-semibold">Tax Arithmetic Mismatch!</span>
                      )}
                    </div>
                    <div className="relative">
                      <input
                        type="text"
                        disabled={isLocked}
                        value={formData.total_amount || ''}
                        onChange={(e) => handleFieldChange('total_amount', e.target.value)}
                        className={`w-full px-3 py-2 bg-slate-900 border rounded-xl text-sm font-mono font-bold text-slate-100 disabled:opacity-60 focus:outline-none focus:border-cyan-500 ${
                          findings.some((f) => f.rule_id === 'RULE-TAX-001')
                            ? 'border-rose-500 bg-rose-950/20'
                            : 'border-slate-700'
                        }`}
                      />
                    </div>
                  </div>
                </div>

                {/* Reason for change */}
                {!isLocked && (
                  <div className="pt-2">
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Reason for Correction (logged in Audit Trail)
                    </label>
                    <input
                      type="text"
                      value={editReason}
                      onChange={(e) => setEditReason(e.target.value)}
                      placeholder="e.g. Corrected OCR typo in vendor GSTIN"
                      className="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                )}

                {/* Action buttons */}
                {!isLocked && (
                  <div className="pt-2 flex items-center justify-between">
                    <div className="text-[11px] text-slate-400">
                      Saving corrections automatically re-evaluates all deterministic audit rules.
                    </div>
                    <button
                      type="submit"
                      disabled={savingFields}
                      className="px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 font-semibold text-xs flex items-center space-x-1.5 transition-colors shadow-md shadow-cyan-500/20"
                    >
                      {savingFields ? (
                        <span className="animate-spin mr-1">⏳</span>
                      ) : saveSuccess ? (
                        <Check className="w-4 h-4 text-emerald-950" />
                      ) : (
                        <Save className="w-4 h-4" />
                      )}
                      <span>{saveSuccess ? 'Saved & Re-scanned!' : 'Save Corrections'}</span>
                    </button>
                  </div>
                )}
              </form>
            )}

            {/* Tab 2: Findings & Evidence */}
            {activeTab === 'findings' && (
              <div className="p-5 space-y-4 overflow-y-auto max-h-[500px]">
                {findings.length === 0 ? (
                  <div className="py-12 text-center text-slate-400">
                    <ShieldCheck className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
                    <h4 className="text-sm font-semibold text-white">Clean Invoice — Zero Findings</h4>
                    <p className="text-xs text-slate-500 mt-1">
                      Tax arithmetic matches, GSTIN checksum checks out, dates are valid, and no prompt injections detected.
                    </p>
                  </div>
                ) : (
                  findings.map((f, idx) => {
                    const sev = (f.severity || 'low').toLowerCase();
                    return (
                      <div
                        key={idx}
                        className={`p-4 rounded-xl border ${
                          sev === 'critical' || sev === 'high'
                            ? 'bg-rose-950/30 border-rose-700/60'
                            : sev === 'medium'
                            ? 'bg-amber-950/30 border-amber-700/60'
                            : 'bg-slate-900 border-slate-800'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center space-x-2">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                                sev === 'critical' || sev === 'high'
                                  ? 'bg-rose-600 text-white'
                                  : sev === 'medium'
                                  ? 'bg-amber-500 text-slate-950'
                                  : 'bg-slate-700 text-slate-200'
                              }`}
                            >
                              {f.severity}
                            </span>
                            <span className="font-mono text-xs font-semibold text-cyan-400">
                              {f.rule_id}
                            </span>
                          </div>
                          {f.points !== undefined && (
                            <span className="text-xs font-semibold text-rose-400">
                              +{f.points} risk pts
                            </span>
                          )}
                        </div>

                        <p className="text-xs font-medium text-slate-200 mt-2">
                          {f.title || f.message || f.explanation}
                        </p>
                        {f.explanation && f.title && (
                          <p className="text-[11px] text-slate-400 mt-1">{f.explanation}</p>
                        )}

                        {/* Evidence Details */}
                        {f.evidence && Object.keys(f.evidence).length > 0 && (
                          <div className="mt-3 p-2.5 rounded-lg bg-slate-950/80 border border-slate-900 font-mono text-[11px] text-slate-300">
                            <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 font-sans">
                              Calculated Evidence:
                            </div>
                            <div className="space-y-1">
                              {Object.entries(f.evidence).map(([k, v]) => (
                                <div key={k} className="flex justify-between">
                                  <span className="text-slate-400">{k}:</span>
                                  <span className="text-slate-100 font-semibold">{String(v)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })
                )}

                {/* Score Breakdown Section */}
                {invoice.risk?.breakdown && invoice.risk.breakdown.length > 0 && (
                  <div className="mt-6 pt-4 border-t border-slate-800">
                    <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                      Deterministic Rule Trigger Matrix
                    </h4>
                    <div className="space-y-1.5">
                      {invoice.risk.breakdown.map((rule) => (
                        <div
                          key={rule.rule_id}
                          className="flex items-center justify-between text-xs py-1 px-2 rounded bg-slate-900/60"
                        >
                          <span className="text-slate-300 font-mono text-[11px]">
                            {rule.rule_id} ({rule.severity || 'rule'})
                          </span>
                          <span className="font-semibold text-rose-400">
                            +{rule.points} pts
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Tab 3: Audit Trail */}
            {activeTab === 'audit' && (
              <div className="p-5 space-y-4 overflow-y-auto max-h-[500px]">
                {loadingAudit ? (
                  <div className="py-8 text-center text-xs text-slate-400">Loading audit trail...</div>
                ) : auditLog.length === 0 ? (
                  <div className="py-8 text-center text-xs text-slate-500">No audit events recorded yet.</div>
                ) : (
                  <div className="space-y-3 relative before:absolute before:left-3.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
                    {auditLog.map((log, idx) => (
                      <div key={log.event_id || log.id || idx} className="relative pl-8 text-xs">
                        <div className="absolute left-2 top-1.5 w-3 h-3 rounded-full bg-cyan-500/80 border-2 border-slate-900"></div>
                        <div className="flex items-center justify-between text-slate-400 text-[11px] mb-0.5">
                          <span className="font-semibold text-slate-200 uppercase">{log.event_type}</span>
                          <span>{new Date(log.created_at).toLocaleString()}</span>
                        </div>
                        <div className="text-slate-300">
                          Actor: <span className="font-mono text-cyan-400">{log.actor}</span>
                        </div>
                        {(log.details || log.payload) && (
                          <pre className="mt-1 p-2 rounded bg-slate-950 text-[10px] text-slate-400 font-mono overflow-auto max-h-24">
                            {JSON.stringify(log.details || log.payload, null, 2)}
                          </pre>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Action Dialog Modal */}
      {modalAction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="glass-panel-elevated w-full max-w-lg rounded-2xl p-6 border border-slate-700 shadow-2xl">
            <h3 className="text-base font-bold text-white capitalize mb-1">
              {modalAction === 'approve'
                ? 'Approve Invoice for Payment'
                : modalAction === 'flag'
                ? 'Flag Invoice for Manager Escalation'
                : modalAction === 'reject'
                ? 'Reject Invoice'
                : 'Reopen Invoice'}
            </h3>
            <p className="text-xs text-slate-400 mb-4">
              Invoice #{invoice.fields?.invoice_number || currentFilename}
            </p>

            {/* High Risk Acknowledge Alert */}
            {modalAction === 'approve' && riskLevel === 'high' && (
              <div className="p-3.5 rounded-xl bg-rose-950/70 border border-rose-700 text-xs text-rose-200 mb-4 space-y-2">
                <div className="flex items-center space-x-2 font-bold text-rose-400">
                  <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                  <span>HIGH RISK OVERRIDE REQUIRED (Score: {riskScore}/100)</span>
                </div>
                <p className="text-[11px]">
                  This invoice failed deterministic validation checks. To proceed with approval, you must explicitly accept responsibility and provide a justification.
                </p>
                <label className="flex items-center space-x-2 pt-1 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={acknowledgeRisk}
                    onChange={(e) => setAcknowledgeRisk(e.target.checked)}
                    className="w-4 h-4 rounded text-rose-600 bg-slate-900 border-rose-500 focus:ring-0"
                  />
                  <span className="font-semibold text-rose-300 text-xs">
                    I acknowledge the high-risk findings and authorize override
                  </span>
                </label>
              </div>
            )}

            {/* Comment field */}
            <div className="mb-4">
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Decision Comment {modalAction !== 'approve' && <span className="text-rose-400">*</span>}
              </label>
              <textarea
                rows={3}
                value={reviewComment}
                onChange={(e) => setReviewComment(e.target.value)}
                placeholder={
                  modalAction === 'approve'
                    ? 'Optional approval notes (required if high risk)...'
                    : modalAction === 'flag'
                    ? 'Reason for manager escalation...'
                    : modalAction === 'reject'
                    ? 'Reason for rejection (e.g. tax mismatch or invalid GSTIN)...'
                    : 'Reason for reopening...'
                }
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {actionError && (
              <div className="p-2.5 rounded-lg bg-rose-950 border border-rose-800 text-rose-300 text-xs mb-4">
                {actionError}
              </div>
            )}

            {/* Modal Buttons */}
            <div className="flex items-center justify-end space-x-2">
              <button
                onClick={() => setModalAction(null)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleReviewActionSubmit}
                disabled={submittingAction}
                className={`px-5 py-2 rounded-xl text-xs font-bold text-white transition-colors flex items-center space-x-1.5 ${
                  modalAction === 'approve'
                    ? 'bg-emerald-600 hover:bg-emerald-500'
                    : modalAction === 'flag'
                    ? 'bg-purple-600 hover:bg-purple-500'
                    : modalAction === 'reject'
                    ? 'bg-rose-600 hover:bg-rose-500'
                    : 'bg-cyan-600 hover:bg-cyan-500'
                }`}
              >
                {submittingAction && <span className="animate-spin mr-1">⏳</span>}
                <span className="capitalize">{modalAction}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
