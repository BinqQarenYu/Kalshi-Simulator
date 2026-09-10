/**
 * @file ComplianceModal.tsx
 * @description Agent_law_order — CFTC, Exchange & API Regulatory Compliance Guardian Modal.
 * Displays live compliance audits, pre-trade wash-trade guardrails, rate limit metrics,
 * CFTC Rule 1.31 audit trail, and interactive Legal Dos and Don'ts handbook.
 */

import React, { useState, useEffect } from 'react';
import { ComplianceStatus, ComplianceCheckItem, LegalHandbookResponse } from '../types';
import { 
  Scale, 
  ShieldCheck, 
  ShieldAlert, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  FileText, 
  BookOpen, 
  History, 
  Lock, 
  Zap, 
  Ban, 
  Check, 
  Download, 
  RefreshCw, 
  ExternalLink 
} from 'lucide-react';

interface ComplianceModalProps {
  isOpen: boolean;
  onClose: () => void;
  complianceStatus?: ComplianceStatus;
  onRefresh?: () => Promise<void>;
}

export const ComplianceModal: React.FC<ComplianceModalProps> = ({
  isOpen,
  onClose,
  complianceStatus,
  onRefresh,
}) => {
  const [activeTab, setActiveTab] = useState<'checks' | 'handbook' | 'audit_trail'>('checks');
  const [handbook, setHandbook] = useState<LegalHandbookResponse | null>(null);
  const [isLoadingHandbook, setIsLoadingHandbook] = useState<boolean>(false);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  useEffect(() => {
    if (isOpen && !handbook) {
      fetchHandbook();
    }
  }, [isOpen]);

  const fetchHandbook = async () => {
    setIsLoadingHandbook(true);
    try {
      const res = await fetch('/api/compliance/dos-and-donts');
      if (res.ok) {
        const data = await res.json();
        setHandbook(data);
      }
    } catch (err) {
      console.error('Failed to load legal handbook:', err);
    } finally {
      setIsLoadingHandbook(false);
    }
  };

  const handleRefresh = async () => {
    if (!onRefresh || isRefreshing) return;
    setIsRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleExportJSON = () => {
    if (!complianceStatus) return;
    const blob = new Blob([JSON.stringify(complianceStatus, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `cftc_compliance_audit_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!isOpen) return null;

  const score = complianceStatus?.score ?? 100.0;
  const status = complianceStatus?.status ?? 'COMPLIANT';
  const checks = complianceStatus?.checks ?? [];

  const getStatusBadge = (checkStatus: 'PASS' | 'WARN' | 'FAIL') => {
    switch (checkStatus) {
      case 'PASS':
        return (
          <span className="px-2 py-0.5 text-xs font-mono font-bold rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
            PASS
          </span>
        );
      case 'WARN':
        return (
          <span className="px-2 py-0.5 text-xs font-mono font-bold rounded bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span>
            WARN
          </span>
        );
      case 'FAIL':
        return (
          <span className="px-2 py-0.5 text-xs font-mono font-bold rounded bg-rose-500/20 text-rose-400 border border-rose-500/30 flex items-center gap-1 animate-pulse">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-400"></span>
            FAIL
          </span>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="relative w-full max-w-5xl max-h-[90vh] flex flex-col bg-[#0d1117] border border-[#30363d] rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#21262d] bg-[#161b22]/70">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/20 border border-purple-500/40 text-purple-400">
              <Scale className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white tracking-tight">Agent_law_order</h2>
                <span className="px-2 py-0.5 text-[10px] font-mono font-bold rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                  CFTC & API COMPLIANCE GUARDIAN
                </span>
              </div>
              <p className="text-xs text-[#8b949e]">
                Commodity Exchange Act (CEA) rules, Wash Trading Prevention, and Kalshi API Terms Governor
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleRefresh}
              disabled={isRefreshing}
              aria-label="Refresh compliance telemetry"
              title="Refresh Compliance Telemetry"
              className="p-2 text-[#8b949e] hover:text-white bg-[#21262d] hover:bg-[#30363d] rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500"
            >
              <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin text-purple-400' : ''}`} />
            </button>
            <button
              type="button"
              onClick={handleExportJSON}
              aria-label="Export compliance audit as JSON"
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-[#8b949e] hover:text-white bg-[#21262d] hover:bg-[#30363d] rounded-lg transition-colors border border-[#30363d] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500"
            >
              <Download className="h-3.5 w-3.5" />
              <span>Export JSON</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close compliance modal"
              className="p-2 text-[#8b949e] hover:text-white rounded-lg hover:bg-[#21262d] transition-colors text-lg font-bold leading-none ml-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Top Metric Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 p-4 bg-[#161b22]/30 border-b border-[#21262d]">
          {/* Score */}
          <div className="flex flex-col p-3 rounded-xl bg-[#161b22] border border-[#30363d]">
            <span className="text-[11px] font-semibold text-[#8b949e] uppercase tracking-wider">Compliance Score</span>
            <div className="flex items-baseline gap-1.5 mt-1">
              <span className={`text-2xl font-black font-mono ${
                score >= 90 ? 'text-emerald-400' : score >= 70 ? 'text-amber-400' : 'text-rose-400'
              }`}>
                {score.toFixed(1)}%
              </span>
              <span className="text-xs font-bold text-gray-400 uppercase">({status})</span>
            </div>
          </div>

          {/* Active Checks */}
          <div className="flex flex-col p-3 rounded-xl bg-[#161b22] border border-[#30363d]">
            <span className="text-[11px] font-semibold text-[#8b949e] uppercase tracking-wider">Active Guardrails</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-xl font-bold font-mono text-white">
                {complianceStatus?.passed ?? 6} / {complianceStatus?.total_checks ?? 6}
              </span>
              <span className="text-xs text-emerald-400 font-semibold">Passing</span>
            </div>
          </div>

          {/* Pre-Trade Checks */}
          <div className="flex flex-col p-3 rounded-xl bg-[#161b22] border border-[#30363d]">
            <span className="text-[11px] font-semibold text-[#8b949e] uppercase tracking-wider">Pre-Trade Gate</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-xl font-bold font-mono text-cyan-400">
                {complianceStatus?.pre_trade_checks_total ?? 0}
              </span>
              <span className="text-xs text-[#8b949e]">
                ({complianceStatus?.pre_trade_rejections ?? 0} rejected)
              </span>
            </div>
          </div>

          {/* Rate Limit Governor */}
          <div className="flex flex-col p-3 rounded-xl bg-[#161b22] border border-[#30363d]">
            <span className="text-[11px] font-semibold text-[#8b949e] uppercase tracking-wider">API Rate Governor</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-xl font-bold font-mono text-purple-400">30 req/s</span>
              <span className="text-xs text-emerald-400 font-semibold">0 Throttles</span>
            </div>
          </div>

          {/* Violations */}
          <div className="flex flex-col p-3 rounded-xl bg-[#161b22] border border-[#30363d]">
            <span className="text-[11px] font-semibold text-[#8b949e] uppercase tracking-wider">Flaws / Violations</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className={`text-xl font-bold font-mono ${
                (complianceStatus?.recent_violations_count ?? 0) === 0 ? 'text-emerald-400' : 'text-rose-400'
              }`}>
                {complianceStatus?.recent_violations_count ?? 0}
              </span>
              <span className="text-xs text-[#8b949e]">Zero Tolerance</span>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div role="tablist" aria-label="Compliance sections" className="flex items-center gap-2 px-6 pt-3 border-b border-[#21262d] bg-[#0d1117]">
          <button
            type="button"
            role="tab"
            id="tab-compliance-checks"
            aria-selected={activeTab === 'checks'}
            aria-controls="panel-compliance-checks"
            onClick={() => setActiveTab('checks')}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-bold border-b-2 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500 ${
              activeTab === 'checks'
                ? 'border-purple-500 text-purple-400 bg-purple-500/10'
                : 'border-transparent text-[#8b949e] hover:text-white'
            }`}
          >
            <ShieldCheck className="h-4 w-4" />
            <span>Active Guardrails ({checks.length})</span>
          </button>

          <button
            type="button"
            role="tab"
            id="tab-compliance-handbook"
            aria-selected={activeTab === 'handbook'}
            aria-controls="panel-compliance-handbook"
            onClick={() => setActiveTab('handbook')}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-bold border-b-2 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500 ${
              activeTab === 'handbook'
                ? 'border-purple-500 text-purple-400 bg-purple-500/10'
                : 'border-transparent text-[#8b949e] hover:text-white'
            }`}
          >
            <BookOpen className="h-4 w-4" />
            <span>Legal Dos & Don'ts Handbook</span>
          </button>

          <button
            type="button"
            role="tab"
            id="tab-compliance-audit"
            aria-selected={activeTab === 'audit_trail'}
            aria-controls="panel-compliance-audit"
            onClick={() => setActiveTab('audit_trail')}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-bold border-b-2 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500 ${
              activeTab === 'audit_trail'
                ? 'border-purple-500 text-purple-400 bg-purple-500/10'
                : 'border-transparent text-[#8b949e] hover:text-white'
            }`}
          >
            <History className="h-4 w-4" />
            <span>CFTC Rule 1.31 Audit Trail</span>
          </button>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {/* TAB 1: ACTIVE CHECKS */}
          {activeTab === 'checks' && (
            <div id="panel-compliance-checks" role="tabpanel" aria-labelledby="tab-compliance-checks" className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {checks.map((c, i) => (
                <div
                  key={i}
                  className="flex flex-col justify-between p-4 rounded-xl bg-[#161b22] border border-[#30363d] hover:border-purple-500/40 transition-all"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="text-base">
                          {c.category === 'cftc_conduct' ? '⚖️' : c.category === 'security' ? '🔒' : c.category === 'rate_limits' ? '⚡' : '🛡️'}
                        </span>
                        <h4 className="text-sm font-bold text-white tracking-tight">{c.name}</h4>
                      </div>
                      {getStatusBadge(c.status)}
                    </div>

                    <p className="text-xs text-[#8b949e] mt-2 leading-relaxed">{c.message}</p>
                  </div>

                  <div className="mt-4 pt-3 border-t border-[#21262d] flex items-center justify-between text-[11px] font-mono">
                    <span className="text-purple-400 font-semibold">{c.authority}</span>
                    {c.rule_reference && (
                      <span className="text-[#8b949e] bg-[#21262d] px-2 py-0.5 rounded">
                        {c.rule_reference}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* TAB 2: DOS & DON'TS HANDBOOK */}
          {activeTab === 'handbook' && (
            <div id="panel-compliance-handbook" role="tabpanel" aria-labelledby="tab-compliance-handbook" className="space-y-6">
              {/* THE DOS */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <div className="p-1 rounded bg-emerald-500/20 text-emerald-400">
                    <Check className="h-4 w-4" />
                  </div>
                  <h3 className="text-sm font-bold text-emerald-400 uppercase tracking-wider">
                    The Dos — Mandatory Compliance Obligations
                  </h3>
                </div>

                <div className="space-y-3">
                  {(handbook?.dos ?? []).map((item, idx) => (
                    <div
                      key={idx}
                      className="p-4 rounded-xl bg-[#161b22] border border-emerald-500/30 hover:border-emerald-500/60 transition-all"
                    >
                      <div className="flex items-center justify-between">
                        <h4 className="text-sm font-bold text-white flex items-center gap-2">
                          <span className="text-emerald-400 font-mono">#{idx + 1}</span>
                          {item.title}
                        </h4>
                        <span className="text-[11px] font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/30">
                          {item.authority}
                        </span>
                      </div>
                      <p className="text-xs text-gray-300 mt-2">{item.description}</p>
                      <div className="mt-3 text-[11px] text-[#8b949e] bg-[#0d1117] p-2.5 rounded-lg border border-[#21262d]">
                        <span className="text-emerald-400 font-semibold">Simulator Implementation: </span>
                        {item.app_enforcement}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* THE DON'TS */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <div className="p-1 rounded bg-rose-500/20 text-rose-400">
                    <Ban className="h-4 w-4" />
                  </div>
                  <h3 className="text-sm font-bold text-rose-400 uppercase tracking-wider">
                    The Don'ts — Prohibited Market Conduct & Legal Liabilities
                  </h3>
                </div>

                <div className="space-y-3">
                  {(handbook?.donts ?? []).map((item, idx) => (
                    <div
                      key={idx}
                      className="p-4 rounded-xl bg-[#161b22] border border-rose-500/30 hover:border-rose-500/60 transition-all"
                    >
                      <div className="flex items-center justify-between">
                        <h4 className="text-sm font-bold text-white flex items-center gap-2">
                          <span className="text-rose-400 font-mono">#{idx + 1}</span>
                          {item.title}
                        </h4>
                        <span className="text-[11px] font-mono font-bold text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/30">
                          {item.authority}
                        </span>
                      </div>
                      <p className="text-xs text-gray-300 mt-2">{item.description}</p>
                      <div className="mt-3 text-[11px] text-rose-300 bg-rose-950/40 p-2.5 rounded-lg border border-rose-500/30">
                        <span className="font-bold text-rose-400">Legal Consequence: </span>
                        {item.consequence}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: AUDIT TRAIL */}
          {activeTab === 'audit_trail' && (
            <div id="panel-compliance-audit" role="tabpanel" aria-labelledby="tab-compliance-audit" className="space-y-4">
              <div className="p-4 rounded-xl bg-[#161b22] border border-[#30363d]">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-[#8b949e]">
                    CFTC Rule 1.31 Append-Only Audit Ledger
                  </h4>
                  <span className="text-xs font-mono text-purple-400 font-semibold">
                    {complianceStatus?.recent_violations?.length ?? 0} Recorded Violations
                  </span>
                </div>
                <p className="text-xs text-[#8b949e] mt-1">
                  Every order submission, cancellation, wash trade veto, and rate limit acquisition is recorded in durable memory.
                </p>
              </div>

              {(complianceStatus?.recent_violations ?? []).length === 0 ? (
                <div className="flex flex-col items-center justify-center p-8 bg-[#161b22]/50 border border-dashed border-[#30363d] rounded-xl text-center">
                  <CheckCircle2 className="h-10 w-10 text-emerald-400 mb-2" />
                  <h4 className="text-sm font-bold text-white">Clean Regulatory Record</h4>
                  <p className="text-xs text-[#8b949e] mt-1 max-w-sm">
                    No CFTC violations, wash trade attempts, or rate limit overflows have been detected during this session.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {complianceStatus?.recent_violations?.map((v, i) => (
                    <div
                      key={i}
                      className="p-3 rounded-lg bg-rose-950/30 border border-rose-500/30 flex items-start justify-between gap-3 text-xs"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-rose-400">{v.rule_name}</span>
                          <span className="text-[10px] font-mono text-[#8b949e]">({v.authority})</span>
                        </div>
                        <p className="text-gray-300 mt-1">{v.description}</p>
                      </div>
                      <span className="text-[10px] font-mono text-[#8b949e] whitespace-nowrap">
                        {v.timestamp.split('T')[1]?.slice(0, 8)} UTC
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-[#21262d] bg-[#161b22]/50 flex items-center justify-between text-xs text-[#8b949e]">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-purple-400 animate-ping"></span>
            <span>Agent_law_order active in background</span>
          </div>
          <span className="font-mono text-[11px]">
            Kalshi Regulated Exchange API v2
          </span>
        </div>
      </div>
    </div>
  );
};
