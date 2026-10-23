import React, { useState } from 'react';
import { Shield, Upload, FileText, Award, Download, AlertCircle, RefreshCw } from 'lucide-react';
import type { HealthResponse } from '../types';
import { api } from '../api';

interface NavbarProps {
  activeTab: 'invoices' | 'upload' | 'scorecard';
  setActiveTab: (tab: 'invoices' | 'upload' | 'scorecard') => void;
  health: HealthResponse | null;
  healthLoading: boolean;
  onRefreshHealth: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  health,
  healthLoading,
  onRefreshHealth,
}) => {
  const [showExportMenu, setShowExportMenu] = useState(false);
  const isHealthy = health?.status === 'ok' || health?.status === 'healthy';

  return (
    <header className="sticky top-0 z-40 w-full border-b border-surface-border bg-navy-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab('invoices')}>
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Shield className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xl font-bold tracking-tight text-white">InvoiceGuard<span className="text-cyan-400">+</span></span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-950/80 text-cyan-300 border border-cyan-800 font-medium">Enterprise</span>
            </div>
            <p className="text-xs text-slate-400 hidden sm:block">Automated Pre-Payment Audit & Fraud Defense</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center space-x-1 sm:space-x-2">
          <button
            onClick={() => setActiveTab('invoices')}
            className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'invoices'
                ? 'bg-slate-800 text-cyan-400 border border-slate-700 shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-slate-900/60'
            }`}
          >
            <FileText className="w-4 h-4" />
            <span className="hidden sm:inline">Invoices</span>
          </button>

          <button
            onClick={() => setActiveTab('upload')}
            className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'upload'
                ? 'bg-slate-800 text-cyan-400 border border-slate-700 shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-slate-900/60'
            }`}
          >
            <Upload className="w-4 h-4" />
            <span className="hidden sm:inline">Upload</span>
          </button>

          <button
            onClick={() => setActiveTab('scorecard')}
            className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'scorecard'
                ? 'bg-slate-800 text-cyan-400 border border-slate-700 shadow-sm'
                : 'text-slate-300 hover:text-white hover:bg-slate-900/60'
            }`}
          >
            <Award className="w-4 h-4" />
            <span className="hidden sm:inline">Trust Scorecard</span>
          </button>
        </nav>

        {/* Status & Actions */}
        <div className="flex items-center space-x-3">
          {/* CSV Export Dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowExportMenu(!showExportMenu)}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
              title="Export CSV Reports"
            >
              <Download className="w-3.5 h-3.5 text-slate-400" />
              <span className="hidden md:inline">Export</span>
            </button>

            {showExportMenu && (
              <div
                className="absolute right-0 mt-2 w-48 rounded-xl bg-slate-900 border border-slate-700 shadow-xl py-1 z-50 animate-in fade-in slide-in-from-top-2 duration-150"
                onClick={() => setShowExportMenu(false)}
              >
                <a
                  href={api.getExportCsvUrl('invoices')}
                  download="invoices_export.csv"
                  className="block px-4 py-2 text-xs text-slate-300 hover:bg-slate-800 hover:text-cyan-400"
                >
                  Export Invoices CSV
                </a>
                <a
                  href={api.getExportCsvUrl('findings')}
                  download="findings_export.csv"
                  className="block px-4 py-2 text-xs text-slate-300 hover:bg-slate-800 hover:text-cyan-400"
                >
                  Export Findings CSV
                </a>
              </div>
            )}
          </div>

          {/* Backend Health Indicator */}
          <div
            className="flex items-center space-x-2 px-2.5 py-1.5 rounded-lg bg-slate-900/90 border border-slate-800 text-xs cursor-pointer group"
            onClick={onRefreshHealth}
            title={`Status: ${health?.status || 'Unknown'}. DB: ${health?.database || 'Unknown'}. Gemini: ${health?.gemini_configured ? 'Active' : 'Unconfigured'}`}
          >
            {healthLoading ? (
              <RefreshCw className="w-3.5 h-3.5 text-slate-400 animate-spin" />
            ) : isHealthy ? (
              <div className="flex items-center space-x-1.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span className="text-slate-300 hidden lg:inline font-mono text-[11px]">API Online</span>
                {health?.gemini_configured && (
                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-cyan-950 text-cyan-400 border border-cyan-800 hidden xl:inline">AI Active</span>
                )}
              </div>
            ) : (
              <div className="flex items-center space-x-1.5 text-rose-400">
                <AlertCircle className="w-3.5 h-3.5" />
                <span className="font-mono text-[11px]">Offline</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
