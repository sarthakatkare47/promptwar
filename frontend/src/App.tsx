import { useState, useEffect, useCallback } from 'react';
import { Navbar } from './components/Navbar';
import { StatCards } from './components/StatCards';
import { UploadDropzone } from './components/UploadDropzone';
import { InvoiceTable } from './components/InvoiceTable';
import { ReviewWorkspace } from './components/ReviewWorkspace';
import { ScorecardView } from './components/ScorecardView';
import { Toast } from './components/Toast';
import type { ToastMessage } from './components/Toast';
import type { InvoiceSummary, InvoiceDetail, HealthResponse } from './types';
import { api } from './api';

export default function App() {
  const [activeTab, setActiveTab] = useState<'invoices' | 'upload' | 'scorecard'>('invoices');
  const [selectedInvoiceId, setSelectedInvoiceId] = useState<string | null>(null);

  // Invoices & Dashboard State
  const [invoices, setInvoices] = useState<InvoiceSummary[]>([]);
  const [loadingInvoices, setLoadingInvoices] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [riskFilter, setRiskFilter] = useState('ALL');

  // Backend Health State
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);

  // Toast notifications
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = (type: 'success' | 'error' | 'info', message: string) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, type, message }]);
  };

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Fetch health
  const checkHealth = useCallback(async () => {
    setHealthLoading(true);
    try {
      const data = await api.getHealth();
      setHealth(data);
    } catch {
      setHealth(null);
    } finally {
      setHealthLoading(false);
    }
  }, []);

  // Fetch invoices
  const loadInvoices = useCallback(async () => {
    setLoadingInvoices(true);
    try {
      const res = await api.getInvoices({ limit: 100 });
      setInvoices(res.items || []);
    } catch (err: unknown) {
      addToast('error', err instanceof Error ? err.message : 'Failed to load invoices');
    } finally {
      setLoadingInvoices(false);
    }
  }, []);

  // Initial mount
  useEffect(() => {
    checkHealth();
    loadInvoices();

    // Health poll every 30s
    const timer = setInterval(checkHealth, 30000);
    return () => clearInterval(timer);
  }, [checkHealth, loadInvoices]);

  // Handle invoice upload completed
  const handleUploadSuccess = (newInvoice: InvoiceDetail) => {
    loadInvoices();
    const filename = newInvoice.original_filename || newInvoice.filename || 'invoice';
    const riskLvl = newInvoice.risk?.level || 'low';
    addToast('success', `Scanned ${filename} — Risk: ${riskLvl}`);
  };

  // Handle review workspace open
  const handleOpenReview = (id: string) => {
    setSelectedInvoiceId(id);
  };

  // Handle invoice updated from review
  const handleInvoiceUpdated = (updated: InvoiceDetail) => {
    const targetId = updated.invoice_id || updated.id;
    setInvoices((prev) =>
      prev.map((i) =>
        (i.invoice_id || i.id) === targetId
          ? {
              ...i,
              vendor_name: updated.fields?.vendor_name,
              invoice_number: updated.fields?.invoice_number,
              invoice_date: updated.fields?.invoice_date,
              total_amount: updated.fields?.total_amount,
              review_status: updated.review_status,
              risk: updated.risk,
            }
          : i
      )
    );
    addToast('success', `Invoice status updated to ${updated.review_status}`);
  };

  // Handle delete invoice
  const handleDeleteInvoice = async (id: string) => {
    try {
      await api.deleteInvoice(id);
      setInvoices((prev) => prev.filter((i) => (i.invoice_id || i.id) !== id));
      if (selectedInvoiceId === id) {
        setSelectedInvoiceId(null);
      }
      addToast('info', 'Invoice removed successfully');
    } catch (err: unknown) {
      addToast('error', err instanceof Error ? err.message : 'Failed to delete invoice');
    }
  };

  // Handle StatCards filter selection
  const handleStatCardFilter = (statFilter: string) => {
    if (statFilter === 'HIGH_RISK') {
      setStatusFilter('ALL');
      setRiskFilter('high');
    } else {
      setStatusFilter(statFilter);
      setRiskFilter('ALL');
    }
    setActiveTab('invoices');
  };

  return (
    <div className="min-h-screen bg-navy-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500 selection:text-white">
      {/* Top Navigation */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={(tab) => {
          setActiveTab(tab);
          setSelectedInvoiceId(null);
        }}
        health={health}
        healthLoading={healthLoading}
        onRefreshHealth={checkHealth}
      />

      {/* Main Content Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 pt-8">
        {/* If an invoice is currently open in review, show ReviewWorkspace */}
        {selectedInvoiceId ? (
          <ReviewWorkspace
            invoiceId={selectedInvoiceId}
            onBack={() => {
              setSelectedInvoiceId(null);
              loadInvoices();
            }}
            onInvoiceUpdated={handleInvoiceUpdated}
          />
        ) : (
          <>
            {/* View 1: Upload tab */}
            {activeTab === 'upload' && (
              <UploadDropzone
                onUploadSuccess={handleUploadSuccess}
                onOpenReview={handleOpenReview}
              />
            )}

            {/* View 2: Scorecard tab */}
            {activeTab === 'scorecard' && <ScorecardView />}

            {/* View 3: Dashboard & Invoices list (default) */}
            {activeTab === 'invoices' && (
              <div>
                {/* Dashboard Stats */}
                <StatCards
                  invoices={invoices}
                  selectedFilter={
                    riskFilter === 'high' ? 'HIGH_RISK' : statusFilter
                  }
                  onFilterChange={handleStatCardFilter}
                />

                {/* Quick Upload Banner if no invoices exist */}
                {invoices.length === 0 && !loadingInvoices && (
                  <div className="mb-8">
                    <UploadDropzone
                      onUploadSuccess={handleUploadSuccess}
                      onOpenReview={handleOpenReview}
                    />
                  </div>
                )}

                {/* Invoices List Table */}
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="text-lg font-bold text-white tracking-tight">Invoice Audit Register</h2>
                    <p className="text-xs text-slate-400">
                      All scanned documents, validation statuses, and review decisions
                    </p>
                  </div>
                  <button
                    onClick={() => setActiveTab('upload')}
                    className="px-3.5 py-1.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold text-xs transition-colors shadow-sm shadow-cyan-500/20"
                  >
                    + Scan New Invoice
                  </button>
                </div>

                <InvoiceTable
                  invoices={invoices}
                  loading={loadingInvoices}
                  searchQuery={searchQuery}
                  setSearchQuery={setSearchQuery}
                  statusFilter={statusFilter}
                  setStatusFilter={setStatusFilter}
                  riskFilter={riskFilter}
                  setRiskFilter={setRiskFilter}
                  onSelectInvoice={handleOpenReview}
                  onDeleteInvoice={handleDeleteInvoice}
                  onRefresh={loadInvoices}
                />
              </div>
            )}
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-navy-950/80 py-6 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-slate-300">InvoiceGuard+</span>
            <span>•</span>
            <span>Automated Pre-Payment Defense</span>
          </div>
          <div className="text-[11px] text-slate-400">
            Deterministic Engine + Google Gemini AI • Modulo-36 GSTIN • Decimal Financial Precision
          </div>
        </div>
      </footer>

      {/* Toast Notification Container */}
      <Toast toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
