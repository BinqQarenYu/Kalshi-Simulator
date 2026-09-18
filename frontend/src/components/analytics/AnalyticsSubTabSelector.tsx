import React from 'react';
import { Award, CheckCircle2, Cpu, Download, FileSpreadsheet, Layers, ShieldCheck, Trash2 } from 'lucide-react';
import { AIPrediction, HistoricalSettlement, HistoricalTrade, SubTabType } from './AnalyticsTypes';
import { WinLossEventReport } from '../../types';

interface AnalyticsSubTabSelectorProps {
  activeSubTab: SubTabType;
  setActiveSubTab: (tab: SubTabType) => void;
  winLossReports: WinLossEventReport[];
  trades: HistoricalTrade[];
  settlements: HistoricalSettlement[];
  aiPredictions: AIPrediction[];
  selectedIds: Set<string | number>;
  handleDeleteBatch: (type: SubTabType) => void;
  setResetTarget: (target: string) => void;
  setIsResetModalOpen: (open: boolean) => void;
}

export const AnalyticsSubTabSelector: React.FC<AnalyticsSubTabSelectorProps> = ({
  activeSubTab,
  setActiveSubTab,
  winLossReports,
  trades,
  settlements,
  aiPredictions,
  selectedIds,
  handleDeleteBatch,
  setResetTarget,
  setIsResetModalOpen,
}) => {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
      <div className="flex flex-wrap items-center gap-2">
        {/* 15M Win/Loss Event Reports Tab */}
        <button
          onClick={() => setActiveSubTab('15m_reports')}
          className={`px-3.5 py-2 text-xs sm:text-sm font-bold rounded-xl transition flex items-center gap-2 ${
            activeSubTab === '15m_reports'
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800 border border-transparent'
          }`}
        >
          <Award className="w-4 h-4 text-emerald-400" />
          <span>15M Win/Loss Reports</span>
          <span className="px-1.5 py-0.2 text-[10px] font-mono bg-emerald-500/20 border border-emerald-500/30 rounded-full text-emerald-300">
            {winLossReports.length}
          </span>
        </button>

        {/* Trade Journal Tab */}
        <button
          onClick={() => setActiveSubTab('journal')}
          className={`px-3.5 py-2 text-xs sm:text-sm font-bold rounded-xl transition flex items-center gap-2 ${
            activeSubTab === 'journal'
              ? 'bg-blue-500/20 text-blue-300 border border-blue-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800 border border-transparent'
          }`}
        >
          <Layers className="w-4 h-4 text-blue-400" />
          <span>Trade Journal</span>
          <span className="px-1.5 py-0.2 text-[10px] font-mono bg-blue-500/20 border border-blue-500/30 rounded-full text-blue-300">
            {trades.length}
          </span>
        </button>

        {/* Settlements Tab */}
        <button
          onClick={() => setActiveSubTab('settlements')}
          className={`px-3.5 py-2 text-xs sm:text-sm font-bold rounded-xl transition flex items-center gap-2 ${
            activeSubTab === 'settlements'
              ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800 border border-transparent'
          }`}
        >
          <CheckCircle2 className="w-4 h-4 text-purple-400" />
          <span>Settlements</span>
          <span className="px-1.5 py-0.2 text-[10px] font-mono bg-purple-500/20 border border-purple-500/30 rounded-full text-purple-300">
            {settlements.length}
          </span>
        </button>

        {/* AI Decisions Tab */}
        <button
          onClick={() => setActiveSubTab('ai')}
          className={`px-3.5 py-2 text-xs sm:text-sm font-bold rounded-xl transition flex items-center gap-2 ${
            activeSubTab === 'ai'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800 border border-transparent'
          }`}
        >
          <Cpu className="w-4 h-4 text-amber-400" />
          <span>AI Decisions</span>
          <span className="px-1.5 py-0.2 text-[10px] font-mono bg-amber-500/20 border border-amber-500/30 rounded-full text-amber-300">
            {aiPredictions.length}
          </span>
        </button>

        {/* Forward Validation Tab */}
        <button
          onClick={() => setActiveSubTab('validation')}
          className={`px-3.5 py-2 text-xs sm:text-sm font-bold rounded-xl transition flex items-center gap-2 ${
            activeSubTab === 'validation'
              ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800 border border-transparent'
          }`}
        >
          <ShieldCheck className="w-4 h-4 text-indigo-400" />
          <span>100-Cycle Forward Validation</span>
        </button>
      </div>

      {/* Sub-Tab Action Controls (Export, Reset, Delete Selected) */}
      <div className="flex items-center gap-2">
        {/* Delete Selected Button */}
        {selectedIds.size > 0 && activeSubTab !== 'validation' && (
          <button
            onClick={() => handleDeleteBatch(activeSubTab)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold rounded-lg shadow-sm transition animate-in fade-in"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Delete Selected ({selectedIds.size})</span>
          </button>
        )}

        {/* Sub-Tab Dedicated CSV Export */}
        {activeSubTab === '15m_reports' && (
          <a
            href="/api/reports/win-loss/export.csv"
            download="kalshi_15m_win_loss_reports.csv"
            className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition"
          >
            <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400" />
            <span>CSV</span>
          </a>
        )}
        {activeSubTab === 'journal' && (
          <a
            href="/api/history/trades/export.csv"
            download="kalshi_trade_journal.csv"
            className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition"
          >
            <FileSpreadsheet className="w-3.5 h-3.5 text-blue-400" />
            <span>CSV</span>
          </a>
        )}
        {activeSubTab === 'settlements' && (
          <a
            href="/api/history/settlements/export.csv"
            download="kalshi_settlements.csv"
            className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition"
          >
            <FileSpreadsheet className="w-3.5 h-3.5 text-purple-400" />
            <span>CSV</span>
          </a>
        )}
        {activeSubTab === 'ai' && (
          <a
            href="/api/history/ai-predictions/export.csv"
            download="kalshi_ai_decisions.csv"
            className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition"
          >
            <FileSpreadsheet className="w-3.5 h-3.5 text-amber-400" />
            <span>CSV</span>
          </a>
        )}

        {/* Sub-Tab Dedicated JSON Export */}
        {activeSubTab === '15m_reports' && (
          <a
            href="/api/reports/win-loss/export.json"
            download="kalshi_15m_win_loss_reports.json"
            className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition"
          >
            <Download className="w-3.5 h-3.5 text-blue-400" />
            <span>JSON</span>
          </a>
        )}
        {activeSubTab === 'journal' && (
          <a
            href="/api/history/trades/export.json"
            download="kalshi_trade_journal.json"
            className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition"
          >
            <Download className="w-3.5 h-3.5 text-blue-400" />
            <span>JSON</span>
          </a>
        )}
        {activeSubTab === 'settlements' && (
          <a
            href="/api/history/settlements/export.json"
            download="kalshi_settlements.json"
            className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition"
          >
            <Download className="w-3.5 h-3.5 text-purple-400" />
            <span>JSON</span>
          </a>
        )}
        {activeSubTab === 'ai' && (
          <a
            href="/api/history/ai-predictions/export.json"
            download="kalshi_ai_decisions.json"
            className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition"
          >
            <Download className="w-3.5 h-3.5 text-amber-400" />
            <span>JSON</span>
          </a>
        )}

        {/* Reset Current Tab */}
        <button
          onClick={() => {
            setResetTarget(
              activeSubTab === '15m_reports'
                ? '15m_reports'
                : activeSubTab === 'journal'
                ? 'trades'
                : activeSubTab === 'settlements'
                ? 'settlements'
                : activeSubTab === 'ai'
                ? 'ai'
                : 'selected'
            );
            setIsResetModalOpen(true);
          }}
          className="flex items-center gap-1 px-3 py-1.5 bg-rose-950/30 hover:bg-rose-900/50 border border-rose-800/40 text-rose-300 hover:text-white text-xs font-semibold rounded-lg transition"
          title="Reset active table"
        >
          <Trash2 className="w-3.5 h-3.5" />
          <span>Reset View</span>
        </button>
      </div>
    </div>
  );
};
