import React, { useState } from 'react';
import { IntegrityStatus, IntegrityCheckItem } from '../types';

interface IntegrityModalProps {
  isOpen: boolean;
  onClose: () => void;
  integrityStatus?: IntegrityStatus;
  onRunAuditNow: () => Promise<void>;
  isLoadingAudit: boolean;
}

export const IntegrityModal: React.FC<IntegrityModalProps> = ({
  isOpen,
  onClose,
  integrityStatus,
  onRunAuditNow,
  isLoadingAudit,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [auditFeedback, setAuditFeedback] = useState<string | null>(null);

  if (!isOpen) return null;

  const score = integrityStatus?.score ?? 100.0;
  const status = integrityStatus?.status ?? 'HEALTHY';
  const checks = integrityStatus?.checks ?? [];

  const filteredChecks = selectedCategory === 'all'
    ? checks
    : checks.filter((c) => c.category === selectedCategory);

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

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'math':
        return '📐';
      case 'microstructure':
        return '📖';
      case 'latency':
        return '⚡';
      case 'truth':
        return '🎯';
      case 'connection':
        return '🌐';
      default:
        return '🛡️';
    }
  };

  const handleAuditClick = async () => {
    setAuditFeedback('Running deep invariant audit...');
    try {
      await onRunAuditNow();
      setAuditFeedback('✓ Deep audit completed. All invariants evaluated.');
      setTimeout(() => setAuditFeedback(null), 3000);
    } catch {
      setAuditFeedback('✗ Audit scan failed to reach server.');
      setTimeout(() => setAuditFeedback(null), 3000);
    }
  };

  const handleExportJson = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(integrityStatus, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `kalshi_integrity_audit_${new Date().toISOString().replace(/[:.]/g, '-')}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-5xl bg-[#0d1117] border border-slate-700/60 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-[#161b22]">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-xl font-bold border ${
              status === 'HEALTHY'
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : status === 'WARNING'
                ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-400 animate-pulse'
            }`}>
              🛡️
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-slate-100 font-mono tracking-tight">
                  Agent_integrity_check Suite
                </h2>
                <span className={`px-2 py-0.5 text-xs font-mono font-bold rounded border ${
                  status === 'HEALTHY'
                    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                    : status === 'WARNING'
                    ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                    : 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                }`}>
                  {status} • {score.toFixed(1)}% INTEGRITY
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Continuous autonomous guardian loop enforcing mathematical rigor, sub-50ms latency, and zero data leakage.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleExportJson}
              className="px-3 py-1.5 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded-lg transition-colors flex items-center gap-1.5"
              title="Download Full Audit JSON"
            >
              📥 Export JSON
            </button>
            <button
              onClick={onClose}
              aria-label="Close integrity modal"
              className="text-slate-400 hover:text-slate-200 p-1.5 hover:bg-slate-800 rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Top KPI Banner */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 p-5 bg-[#090d13] border-b border-slate-800/80">
          <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-lg">
            <div className="text-[10px] uppercase font-mono tracking-wider text-slate-400 font-semibold">Integrity Score</div>
            <div className={`text-2xl font-mono font-bold mt-0.5 ${
              score >= 95 ? 'text-emerald-400' : score >= 80 ? 'text-amber-400' : 'text-rose-400'
            }`}>
              {score.toFixed(1)}%
            </div>
            <div className="text-[10px] text-slate-400 mt-1">
              {integrityStatus?.passed ?? 0}/{integrityStatus?.total_checks ?? 0} Invariants Passing
            </div>
          </div>

          <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-lg">
            <div className="text-[10px] uppercase font-mono tracking-wider text-slate-400 font-semibold">Audits Executed</div>
            <div className="text-2xl font-mono font-bold text-cyan-400 mt-0.5">
              {integrityStatus?.audit_count ?? 0}
            </div>
            <div className="text-[10px] text-slate-400 mt-1">2.0s Guardian Interval</div>
          </div>

          <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-lg">
            <div className="text-[10px] uppercase font-mono tracking-wider text-slate-400 font-semibold">Flaws Intercepted</div>
            <div className="text-2xl font-mono font-bold text-purple-400 mt-0.5">
              {integrityStatus?.total_flaws_caught ?? 0}
            </div>
            <div className="text-[10px] text-slate-400 mt-1">Zero Mathematical Drift</div>
          </div>

          <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-lg">
            <div className="text-[10px] uppercase font-mono tracking-wider text-slate-400 font-semibold">Scan Duration</div>
            <div className="text-2xl font-mono font-bold text-amber-400 mt-0.5">
              {(integrityStatus?.scan_duration_ms ?? 0.8).toFixed(2)} ms
            </div>
            <div className="text-[10px] text-slate-400 mt-1">Low-Overhead In-Memory</div>
          </div>

          <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-lg col-span-2 sm:col-span-1 flex flex-col justify-center">
            <button
              onClick={handleAuditClick}
              disabled={isLoadingAudit}
              className={`w-full py-2 px-3 rounded-lg text-xs font-mono font-bold border transition-all flex items-center justify-center gap-1.5 shadow-md ${
                isLoadingAudit
                  ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40 cursor-wait'
                  : 'bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white border-cyan-400/40 shadow-cyan-500/20'
              }`}
            >
              {isLoadingAudit ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-cyan-300 border-t-transparent rounded-full animate-spin"></span>
                  Scanning...
                </>
              ) : (
                <>
                  ⚡ Deep Scan Now
                </>
              )}
            </button>
            {auditFeedback && (
              <span className="text-[10px] text-center font-mono mt-1 text-cyan-400 animate-fade-in">
                {auditFeedback}
              </span>
            )}
          </div>
        </div>

        {/* Category Filters */}
        <div className="flex items-center gap-2 px-6 py-2.5 bg-[#12171f] border-b border-slate-800 text-xs font-medium overflow-x-auto">
          <span className="text-slate-400 text-xs mr-1 font-mono uppercase">Filter Domain:</span>
          {[
            { id: 'all', label: 'All Invariants', icon: '🔍' },
            { id: 'math', label: 'Math Rigor', icon: '📐' },
            { id: 'microstructure', label: 'CLOB & L2', icon: '📖' },
            { id: 'latency', label: 'Latency & Streams', icon: '⚡' },
            { id: 'truth', label: 'Ground Truth', icon: '🎯' },
            { id: 'connection', label: 'Connectivity', icon: '🌐' },
          ].map((cat) => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-3 py-1 rounded-md transition-colors flex items-center gap-1.5 font-mono text-xs ${
                selectedCategory === cat.id
                  ? 'bg-cyan-600/30 text-cyan-300 border border-cyan-500/50 font-bold'
                  : 'bg-slate-800/60 text-slate-400 hover:text-slate-200 border border-transparent'
              }`}
            >
              <span>{cat.icon}</span>
              <span>{cat.label}</span>
            </button>
          ))}
        </div>

        {/* Checks Table */}
        <div className="flex-1 overflow-y-auto p-6 space-y-3">
          {filteredChecks.length === 0 ? (
            <div className="text-center py-12 text-slate-400 font-mono text-xs">
              No invariant checks recorded for category '{selectedCategory}'.
            </div>
          ) : (
            <div className="overflow-x-auto border border-slate-800/80 rounded-lg">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-[#161b22] text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                  <tr>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Category</th>
                    <th className="px-4 py-3">Invariant Check</th>
                    <th className="px-4 py-3">Observed Metric</th>
                    <th className="px-4 py-3">Safety Threshold</th>
                    <th className="px-4 py-3">Diagnostic Description</th>
                    <th className="px-4 py-3">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 bg-[#0d1117]">
                  {filteredChecks.map((chk, idx) => (
                    <tr
                      key={idx}
                      className={`hover:bg-slate-800/40 transition-colors ${
                        chk.status === 'FAIL'
                          ? 'bg-rose-950/20'
                          : chk.status === 'WARN'
                          ? 'bg-amber-950/10'
                          : ''
                      }`}
                    >
                      <td className="px-4 py-3 whitespace-nowrap">
                        {getStatusBadge(chk.status)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="flex items-center gap-1.5 text-slate-300 font-medium capitalize">
                          <span>{getCategoryIcon(chk.category)}</span>
                          <span>{chk.category}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap font-bold text-slate-200">
                        {chk.name}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap font-mono text-cyan-400">
                        {chk.metric_value ?? '—'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap font-mono text-slate-400">
                        {chk.threshold ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-slate-300 min-w-[240px]">
                        {chk.message}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-slate-400 text-[10px]">
                        {chk.timestamp.slice(11, 19)} UTC
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-[#161b22] flex items-center justify-between text-xs text-slate-400 font-mono">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
            <span>Agent_integrity_check actively guarding real money & execution invariants</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold rounded-lg transition-colors border border-slate-700"
          >
            Close Dashboard
          </button>
        </div>
      </div>
    </div>
  );
};
