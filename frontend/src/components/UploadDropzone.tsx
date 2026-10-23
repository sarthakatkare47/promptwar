import React, { useState, useRef } from 'react';
import {
  Upload,
  FileCheck,
  AlertTriangle,
  FileText,
  Image as ImageIcon,
  CheckCircle2,
  Loader2,
  ShieldAlert,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';
import type { InvoiceDetail } from '../types';
import { api } from '../api';

interface UploadDropzoneProps {
  onUploadSuccess: (invoice: InvoiceDetail) => void;
  onOpenReview: (invoiceId: string) => void;
}

type UploadStage = 'idle' | 'uploading' | 'extracting' | 'validating' | 'success' | 'error';

export const UploadDropzone: React.FC<UploadDropzoneProps> = ({
  onUploadSuccess,
  onOpenReview,
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [stage, setStage] = useState<UploadStage>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [recentInvoice, setRecentInvoice] = useState<InvoiceDetail | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const allowedTypes = ['application/pdf', 'image/jpeg', 'image/png'];
  const maxBytes = 10 * 1024 * 1024; // 10MB

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const validateAndProcessFile = async (file: File) => {
    setErrorMessage(null);
    setRecentInvoice(null);

    // Client-side quick check
    if (!allowedTypes.includes(file.type) && !file.name.match(/\.(pdf|jpe?g|png)$/i)) {
      setErrorMessage('Unsupported file format. Please upload a PDF, PNG, or JPG file.');
      return;
    }

    if (file.size > maxBytes) {
      setErrorMessage(`File size (${(file.size / (1024 * 1024)).toFixed(1)}MB) exceeds maximum limit of 10MB.`);
      return;
    }

    setSelectedFile(file);
    setStage('uploading');

    try {
      const stageTimer1 = setTimeout(() => {
        setStage((prev) => (prev === 'uploading' ? 'extracting' : prev));
      }, 700);

      const stageTimer2 = setTimeout(() => {
        setStage((prev) => (prev === 'extracting' ? 'validating' : prev));
      }, 2200);

      const invoice = await api.uploadInvoice(file);

      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);

      setRecentInvoice(invoice);
      setStage('success');
      onUploadSuccess(invoice);
    } catch (err: unknown) {
      setStage('error');
      const errStr = err instanceof Error ? err.message : 'Upload failed';
      setErrorMessage(errStr);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndProcessFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndProcessFile(e.target.files[0]);
    }
  };

  const resetUpload = () => {
    setSelectedFile(null);
    setStage('idle');
    setErrorMessage(null);
    setRecentInvoice(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const invId = recentInvoice?.invoice_id || recentInvoice?.id || '';
  const filename = recentInvoice?.original_filename || recentInvoice?.filename || '';
  const riskScore = recentInvoice?.risk?.score ?? 0;
  const riskLevel = (recentInvoice?.risk?.level || 'low').toLowerCase();

  return (
    <div className="max-w-3xl mx-auto mb-8">
      <div className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800 shadow-2xl relative overflow-hidden">
        {/* Subtle background glow */}
        <div className="absolute top-0 right-0 -mr-16 -mt-16 w-64 h-64 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="text-center mb-6">
          <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
            Upload Invoice for Audit Scan
          </h2>
          <p className="text-sm text-slate-400 mt-1 max-w-lg mx-auto">
            Upload vendor invoices in PDF, PNG, or JPG format. AI extracts data while 7 deterministic rules check for tax arithmetic, GSTIN validity, stale/future dates, and prompt injections.
          </p>
        </div>

        {stage === 'idle' && (
          <div>
            <div
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-8 sm:p-12 text-center cursor-pointer transition-all ${
                dragActive
                  ? 'border-cyan-400 bg-cyan-950/30 glow-cyan scale-[1.01]'
                  : 'border-slate-700 hover:border-slate-500 hover:bg-slate-900/50'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg"
                className="hidden"
                onChange={handleFileChange}
              />
              <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-slate-800/80 border border-slate-700 flex items-center justify-center text-cyan-400 shadow-inner group-hover:scale-105 transition-transform">
                <Upload className="w-8 h-8" />
              </div>
              <p className="text-base font-semibold text-slate-200">
                Drag and drop your invoice here, or <span className="text-cyan-400 hover:underline">browse files</span>
              </p>
              <p className="text-xs text-slate-400 mt-2">
                Supported formats: PDF, PNG, JPG (Max 10 MB per document)
              </p>

              <div className="flex items-center justify-center space-x-6 mt-6 text-xs text-slate-400">
                <span className="flex items-center space-x-1.5">
                  <FileText className="w-4 h-4 text-rose-400" />
                  <span>PDF Documents</span>
                </span>
                <span className="flex items-center space-x-1.5">
                  <ImageIcon className="w-4 h-4 text-emerald-400" />
                  <span>PNG / JPG Images</span>
                </span>
                <span className="flex items-center space-x-1.5">
                  <FileCheck className="w-4 h-4 text-cyan-400" />
                  <span>Magic Bytes Check</span>
                </span>
              </div>
            </div>

            <div className="mt-4 p-3 rounded-lg bg-slate-900/40 border border-slate-800 text-[11px] text-slate-400 flex items-start space-x-2">
              <span className="text-cyan-400 font-semibold uppercase">Security:</span>
              <span>All uploads undergo magic-byte signature validation, strict input sanitization, and SHA-256 fingerprinting for duplicate detection before processing.</span>
            </div>
          </div>
        )}

        {/* Processing State */}
        {(stage === 'uploading' || stage === 'extracting' || stage === 'validating') && (
          <div className="py-10 text-center">
            <div className="relative w-20 h-20 mx-auto mb-6">
              <div className="absolute inset-0 rounded-full border-4 border-slate-800"></div>
              <div className="absolute inset-0 rounded-full border-4 border-cyan-400 border-t-transparent animate-spin"></div>
              <div className="absolute inset-0 flex items-center justify-center">
                <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
              </div>
            </div>

            <h3 className="text-lg font-semibold text-white mb-2">
              {stage === 'uploading' && 'Uploading document & computing SHA-256...'}
              {stage === 'extracting' && 'Extracting invoice fields via Gemini AI...'}
              {stage === 'validating' && 'Running 7 deterministic audit & security rules...'}
            </h3>

            <p className="text-xs text-slate-400 font-mono mb-6">
              {selectedFile?.name} ({(selectedFile?.size ? selectedFile.size / 1024 : 0).toFixed(1)} KB)
            </p>

            {/* Stage Progress Pills */}
            <div className="max-w-md mx-auto grid grid-cols-3 gap-2 text-xs">
              <div
                className={`p-2 rounded-lg border text-center transition-colors ${
                  stage === 'uploading'
                    ? 'bg-cyan-950/60 border-cyan-500 text-cyan-300 animate-pulse'
                    : 'bg-slate-900 border-emerald-800 text-emerald-400'
                }`}
              >
                1. Upload & Hash
              </div>
              <div
                className={`p-2 rounded-lg border text-center transition-colors ${
                  stage === 'extracting'
                    ? 'bg-cyan-950/60 border-cyan-500 text-cyan-300 animate-pulse'
                    : stage === 'validating'
                    ? 'bg-slate-900 border-emerald-800 text-emerald-400'
                    : 'bg-slate-900/50 border-slate-800 text-slate-500'
                }`}
              >
                2. AI Extraction
              </div>
              <div
                className={`p-2 rounded-lg border text-center transition-colors ${
                  stage === 'validating'
                    ? 'bg-cyan-950/60 border-cyan-500 text-cyan-300 animate-pulse'
                    : 'bg-slate-900/50 border-slate-800 text-slate-500'
                }`}
              >
                3. Audit Engine
              </div>
            </div>
          </div>
        )}

        {/* Success State */}
        {stage === 'success' && recentInvoice && (
          <div className="py-4">
            <div className="p-5 rounded-xl bg-slate-900/90 border border-slate-700 shadow-inner mb-6">
              <div className="flex items-center justify-between pb-4 border-b border-slate-800">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-lg bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                    <CheckCircle2 className="w-6 h-6" />
                  </div>
                  <div>
                    <h4 className="text-base font-semibold text-white">Invoice Processed Successfully</h4>
                    <p className="text-xs text-slate-400 font-mono">{filename}</p>
                  </div>
                </div>

                {/* Risk Level Badge */}
                <div className="text-right">
                  <span
                    className={`inline-block px-3 py-1 rounded-full text-xs font-bold uppercase ${
                      riskLevel === 'high'
                        ? 'bg-rose-950/80 text-rose-300 border border-rose-700'
                        : riskLevel === 'medium'
                        ? 'bg-amber-950/80 text-amber-300 border border-amber-700'
                        : 'bg-emerald-950/80 text-emerald-300 border border-emerald-700'
                    }`}
                  >
                    Risk Score: {riskScore}/100 ({riskLevel})
                  </span>
                </div>
              </div>

              {/* Quick Summary Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4 text-xs">
                <div>
                  <span className="text-slate-400 block">Vendor</span>
                  <span className="font-semibold text-slate-200 truncate block">
                    {recentInvoice.fields?.vendor_name || 'Not detected'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block">Invoice #</span>
                  <span className="font-semibold text-slate-200 truncate block">
                    {recentInvoice.fields?.invoice_number || 'N/A'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block">Total Amount</span>
                  <span className="font-semibold text-slate-200">
                    {recentInvoice.fields?.currency || '₹'} {recentInvoice.fields?.total_amount || '0.00'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block">Risk Evaluation</span>
                  <span
                    className={`font-semibold capitalize ${
                      riskLevel === 'high'
                        ? 'text-rose-400'
                        : riskLevel === 'medium'
                        ? 'text-amber-400'
                        : 'text-emerald-400'
                    }`}
                  >
                    {riskLevel} Risk
                  </span>
                </div>
              </div>

              {/* High risk alert if present */}
              {riskLevel === 'high' && (
                <div className="mt-4 p-3 rounded-lg bg-rose-950/40 border border-rose-800/60 text-xs text-rose-300 flex items-center space-x-2">
                  <AlertTriangle className="w-4 h-4 flex-shrink-0 text-rose-400" />
                  <span>
                    Deterministic validation alerts detected. High-risk override required for approval.
                  </span>
                </div>
              )}
            </div>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <button
                onClick={() => onOpenReview(invId)}
                className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold text-sm flex items-center justify-center space-x-2 shadow-lg shadow-cyan-500/20 transition-colors"
              >
                <span>Open in Review Workspace</span>
                <ArrowRight className="w-4 h-4" />
              </button>

              <button
                onClick={resetUpload}
                className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-sm flex items-center justify-center space-x-2 border border-slate-700 transition-colors"
              >
                <RefreshCw className="w-4 h-4 text-slate-400" />
                <span>Upload Another</span>
              </button>
            </div>
          </div>
        )}

        {/* Error State */}
        {stage === 'error' && (
          <div className="py-6 text-center">
            <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-rose-500/20 border border-rose-500/30 flex items-center justify-center text-rose-400">
              <ShieldAlert className="w-7 h-7" />
            </div>

            <h3 className="text-lg font-semibold text-white mb-2">Scan Processing Failed</h3>
            <div className="p-4 rounded-xl bg-rose-950/50 border border-rose-800/80 max-w-lg mx-auto text-xs text-rose-300 mb-6 font-mono text-left overflow-auto max-h-32">
              {errorMessage || 'Unknown server error during upload.'}
            </div>

            <button
              onClick={resetUpload}
              className="px-6 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-sm inline-flex items-center space-x-2 border border-slate-700 transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              <span>Try Again</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
