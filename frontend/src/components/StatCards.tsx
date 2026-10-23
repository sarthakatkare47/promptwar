import React from 'react';
import { FileText, Clock, AlertTriangle, Flag, CheckCircle2 } from 'lucide-react';
import type { InvoiceSummary } from '../types';

interface StatCardsProps {
  invoices: InvoiceSummary[];
  selectedFilter: string;
  onFilterChange: (statusFilter: string, riskFilter?: string) => void;
}

export const StatCards: React.FC<StatCardsProps> = ({
  invoices,
  selectedFilter,
  onFilterChange,
}) => {
  const total = invoices.length;
  const pending = invoices.filter(
    (i) => i.review_status === 'pending' || i.review_status === 'NEEDS_REVIEW'
  ).length;
  const highRisk = invoices.filter(
    (i) =>
      (i.risk?.level || i.risk_level || '').toLowerCase() === 'high' ||
      (i.risk?.score ?? i.risk_score ?? 0) >= 40
  ).length;
  const flagged = invoices.filter(
    (i) => i.review_status === 'flagged' || i.review_status === 'FLAGGED'
  ).length;
  const approved = invoices.filter(
    (i) => i.review_status === 'approved' || i.review_status === 'APPROVED'
  ).length;

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 md:gap-4 mb-6">
      {/* Total Invoices */}
      <div
        onClick={() => onFilterChange('ALL')}
        className={`p-4 rounded-xl cursor-pointer transition-all border ${
          selectedFilter === 'ALL'
            ? 'bg-slate-800/90 border-cyan-500/50 glow-cyan'
            : 'bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-850'
        }`}
      >
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-medium uppercase tracking-wider">Total Scanned</span>
          <FileText className="w-4 h-4 text-cyan-400" />
        </div>
        <div className="text-2xl font-bold text-white tracking-tight">{total}</div>
        <div className="text-[11px] text-slate-400 mt-1">All processed invoices</div>
      </div>

      {/* Pending Review */}
      <div
        onClick={() => onFilterChange('pending')}
        className={`p-4 rounded-xl cursor-pointer transition-all border ${
          selectedFilter === 'pending' || selectedFilter === 'NEEDS_REVIEW'
            ? 'bg-slate-800/90 border-amber-500/50 glow-amber'
            : 'bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-850'
        }`}
      >
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-medium uppercase tracking-wider">Pending Review</span>
          <Clock className="w-4 h-4 text-amber-400" />
        </div>
        <div className="text-2xl font-bold text-amber-400 tracking-tight">{pending}</div>
        <div className="text-[11px] text-slate-400 mt-1">Awaiting decision</div>
      </div>

      {/* High Risk */}
      <div
        onClick={() => onFilterChange('HIGH_RISK')}
        className={`p-4 rounded-xl cursor-pointer transition-all border ${
          selectedFilter === 'HIGH_RISK'
            ? 'bg-slate-800/90 border-rose-500/50 glow-rose'
            : 'bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-850'
        }`}
      >
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-medium uppercase tracking-wider">High Risk</span>
          <AlertTriangle className="w-4 h-4 text-rose-400" />
        </div>
        <div className="text-2xl font-bold text-rose-400 tracking-tight">{highRisk}</div>
        <div className="text-[11px] text-slate-400 mt-1">Score ≥ 40 or Critical</div>
      </div>

      {/* Flagged */}
      <div
        onClick={() => onFilterChange('flagged')}
        className={`p-4 rounded-xl cursor-pointer transition-all border ${
          selectedFilter === 'flagged' || selectedFilter === 'FLAGGED'
            ? 'bg-slate-800/90 border-purple-500/50'
            : 'bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-850'
        }`}
      >
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-medium uppercase tracking-wider">Escalated</span>
          <Flag className="w-4 h-4 text-purple-400" />
        </div>
        <div className="text-2xl font-bold text-purple-400 tracking-tight">{flagged}</div>
        <div className="text-[11px] text-slate-400 mt-1">Flagged for manager</div>
      </div>

      {/* Approved */}
      <div
        onClick={() => onFilterChange('approved')}
        className={`p-4 rounded-xl cursor-pointer transition-all border col-span-2 md:col-span-1 ${
          selectedFilter === 'approved' || selectedFilter === 'APPROVED'
            ? 'bg-slate-800/90 border-emerald-500/50 glow-emerald'
            : 'bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-850'
        }`}
      >
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-medium uppercase tracking-wider">Approved</span>
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
        </div>
        <div className="text-2xl font-bold text-emerald-400 tracking-tight">{approved}</div>
        <div className="text-[11px] text-slate-400 mt-1">Cleared for payment</div>
      </div>
    </div>
  );
};
