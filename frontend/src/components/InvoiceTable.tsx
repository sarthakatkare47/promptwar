import React, { useState } from 'react';
import {
  Search,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Flag,
  XCircle,
  Eye,
  Trash2,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import type { InvoiceSummary } from '../types';

interface InvoiceTableProps {
  invoices: InvoiceSummary[];
  loading: boolean;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  statusFilter: string;
  setStatusFilter: (s: string) => void;
  riskFilter: string;
  setRiskFilter: (r: string) => void;
  onSelectInvoice: (id: string) => void;
  onDeleteInvoice: (id: string) => void;
  onRefresh: () => void;
}

export const InvoiceTable: React.FC<InvoiceTableProps> = ({
  invoices,
  loading,
  searchQuery,
  setSearchQuery,
  statusFilter,
  setStatusFilter,
  riskFilter,
  setRiskFilter,
  onSelectInvoice,
  onDeleteInvoice,
}) => {
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  // Filter client-side
  const filtered = invoices.filter((inv) => {
    const rawStatus = (inv.review_status || '').toLowerCase();
    const rawRisk = (inv.risk?.level || inv.risk_level || 'low').toLowerCase();

    // Status filter
    if (statusFilter !== 'ALL') {
      const target = statusFilter.toLowerCase();
      const normStatus = rawStatus === 'needs_review' ? 'pending' : rawStatus;
      const normTarget = target === 'needs_review' ? 'pending' : target;
      if (normStatus !== normTarget) return false;
    }

    // Risk filter
    if (riskFilter !== 'ALL') {
      if (rawRisk !== riskFilter.toLowerCase()) return false;
    }

    // Search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchVendor = inv.vendor_name?.toLowerCase().includes(q) ?? false;
      const matchNum = inv.invoice_number?.toLowerCase().includes(q) ?? false;
      const filename = inv.original_filename || inv.filename || '';
      const matchFilename = filename.toLowerCase().includes(q);
      if (!matchVendor && !matchNum && !matchFilename) return false;
    }
    return true;
  });

  const totalPages = Math.ceil(filtered.length / pageSize) || 1;
  const paginated = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const getStatusBadge = (status: string) => {
    const s = (status || '').toLowerCase();
    switch (s) {
      case 'approved':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-800">
            <CheckCircle2 className="w-3 h-3" />
            <span>Approved</span>
          </span>
        );
      case 'flagged':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-950/80 text-purple-300 border border-purple-800">
            <Flag className="w-3 h-3" />
            <span>Flagged</span>
          </span>
        );
      case 'rejected':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-950/80 text-rose-300 border border-rose-800">
            <XCircle className="w-3 h-3" />
            <span>Rejected</span>
          </span>
        );
      case 'pending':
      case 'needs_review':
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-950/80 text-amber-300 border border-amber-800">
            <Clock className="w-3 h-3" />
            <span>Needs Review</span>
          </span>
        );
    }
  };

  const getRiskBadge = (inv: InvoiceSummary) => {
    const level = (inv.risk?.level || inv.risk_level || 'low').toLowerCase();
    const score = inv.risk?.score ?? inv.risk_score ?? 0;

    switch (level) {
      case 'high':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md text-xs font-bold bg-rose-950/80 text-rose-400 border border-rose-800">
            <AlertTriangle className="w-3 h-3" />
            <span>{score}/100 High</span>
          </span>
        );
      case 'medium':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md text-xs font-bold bg-amber-950/80 text-amber-400 border border-amber-800">
            <span>{score}/100 Med</span>
          </span>
        );
      case 'low':
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md text-xs font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-800">
            <span>{score}/100 Low</span>
          </span>
        );
    }
  };

  const formatDate = (isoString?: string | null) => {
    if (!isoString) return '—';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="glass-panel rounded-2xl border border-slate-800 shadow-xl overflow-hidden mb-12">
      {/* Controls Bar */}
      <div className="p-4 sm:p-5 border-b border-slate-800 flex flex-col md:flex-row gap-4 items-stretch md:items-center justify-between">
        {/* Search Input */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search vendor, invoice #, filename..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
            className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-colors"
          />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Status Filter */}
          <div className="flex items-center space-x-1.5">
            <span className="text-xs text-slate-400 font-medium hidden sm:inline">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="ALL">All Statuses</option>
              <option value="pending">Needs Review</option>
              <option value="approved">Approved</option>
              <option value="flagged">Flagged</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>

          {/* Risk Filter */}
          <div className="flex items-center space-x-1.5">
            <span className="text-xs text-slate-400 font-medium hidden sm:inline">Risk:</span>
            <select
              value={riskFilter}
              onChange={(e) => {
                setRiskFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="ALL">All Risk Levels</option>
              <option value="low">Low Risk</option>
              <option value="medium">Medium Risk</option>
              <option value="high">High Risk</option>
            </select>
          </div>
        </div>
      </div>

      {/* Desktop Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm text-slate-300">
          <thead className="text-xs uppercase bg-slate-900/90 text-slate-400 border-b border-slate-800">
            <tr>
              <th scope="col" className="px-5 py-3.5">Invoice / File</th>
              <th scope="col" className="px-5 py-3.5">Vendor Name</th>
              <th scope="col" className="px-5 py-3.5">Date</th>
              <th scope="col" className="px-5 py-3.5">Total Amount</th>
              <th scope="col" className="px-5 py-3.5">Risk Score</th>
              <th scope="col" className="px-5 py-3.5">Review Status</th>
              <th scope="col" className="px-5 py-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {loading ? (
              // Loading skeleton rows
              Array.from({ length: 4 }).map((_, i) => (
                <tr key={i} className="animate-pulse">
                  <td className="px-5 py-4"><div className="h-4 bg-slate-800 rounded w-36"></div></td>
                  <td className="px-5 py-4"><div className="h-4 bg-slate-800 rounded w-28"></div></td>
                  <td className="px-5 py-4"><div className="h-4 bg-slate-800 rounded w-20"></div></td>
                  <td className="px-5 py-4"><div className="h-4 bg-slate-800 rounded w-24"></div></td>
                  <td className="px-5 py-4"><div className="h-4 bg-slate-800 rounded w-16"></div></td>
                  <td className="px-5 py-4"><div className="h-4 bg-slate-800 rounded w-24"></div></td>
                  <td className="px-5 py-4 text-right"><div className="h-4 bg-slate-800 rounded w-16 ml-auto"></div></td>
                </tr>
              ))
            ) : paginated.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-5 py-16 text-center text-slate-400">
                  <FileText className="w-12 h-12 mx-auto mb-3 text-slate-600" />
                  <p className="text-base font-semibold text-slate-300">No invoices match your filter</p>
                  <p className="text-xs text-slate-500 mt-1">Upload a new document or adjust search filters above.</p>
                </td>
              </tr>
            ) : (
              paginated.map((inv) => {
                const invId = inv.invoice_id || inv.id || '';
                const filename = inv.original_filename || inv.filename || 'invoice';
                return (
                  <tr
                    key={invId}
                    className="hover:bg-slate-850/50 transition-colors cursor-pointer group"
                    onClick={() => onSelectInvoice(invId)}
                  >
                    {/* File / Invoice # */}
                    <td className="px-5 py-4">
                      <div className="font-medium text-white group-hover:text-cyan-400 transition-colors flex items-center space-x-1.5">
                        <span>{inv.invoice_number || 'Unnamed Invoice'}</span>
                      </div>
                      <div className="text-xs text-slate-500 font-mono truncate max-w-[200px]" title={filename}>
                        {filename}
                      </div>
                    </td>

                    {/* Vendor Name */}
                    <td className="px-5 py-4">
                      <span className="font-medium text-slate-200">
                        {inv.vendor_name || <span className="text-slate-500 italic">Not extracted</span>}
                      </span>
                    </td>

                    {/* Date */}
                    <td className="px-5 py-4 text-xs text-slate-400 whitespace-nowrap">
                      {formatDate(inv.invoice_date || inv.created_at)}
                    </td>

                    {/* Total Amount */}
                    <td className="px-5 py-4 font-mono font-semibold text-slate-100 whitespace-nowrap">
                      {inv.currency || '₹'} {inv.total_amount ? Number(inv.total_amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00'}
                    </td>

                    {/* Risk Badge */}
                    <td className="px-5 py-4 whitespace-nowrap">
                      {getRiskBadge(inv)}
                    </td>

                    {/* Review Status */}
                    <td className="px-5 py-4 whitespace-nowrap">
                      {getStatusBadge(inv.review_status)}
                    </td>

                    {/* Actions */}
                    <td className="px-5 py-4 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end space-x-2" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => onSelectInvoice(invId)}
                          className="p-1.5 rounded-lg bg-slate-800 hover:bg-cyan-950 text-slate-300 hover:text-cyan-400 border border-slate-700 transition-colors"
                          title="Open Review Workspace"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => {
                            if (confirm(`Are you sure you want to delete invoice "${filename}"?`)) {
                              onDeleteInvoice(invId);
                            }
                          }}
                          className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-950 text-slate-400 hover:text-rose-400 border border-slate-700 transition-colors"
                          title="Delete Invoice"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="p-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <div>
            Showing {(currentPage - 1) * pageSize + 1} to{' '}
            {Math.min(currentPage * pageSize, filtered.length)} of {filtered.length} entries
          </div>
          <div className="flex items-center space-x-2">
            <button
              disabled={currentPage === 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed border border-slate-700 text-slate-200"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-2 font-medium text-slate-200">
              Page {currentPage} of {totalPages}
            </span>
            <button
              disabled={currentPage === totalPages}
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed border border-slate-700 text-slate-200"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
