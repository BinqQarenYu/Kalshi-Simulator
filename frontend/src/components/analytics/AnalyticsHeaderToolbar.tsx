import React from 'react';
import { Activity, BarChart3, Download, FileSpreadsheet, FileText, Loader2, Play, RefreshCw, Trash2 } from 'lucide-react';

interface AnalyticsHeaderToolbarProps {
  handleRunBotTest: (botType?: any) => void;
  isTestingBot: boolean;
  testBotType: 'both' | 'macro_onnx' | 'macro_trend_dominion' | 'dominion_2_bot' | '3_step_domination_bot' | 'onnx_ml_bot';
  setTestBotType: (type: 'both' | 'macro_onnx' | 'macro_trend_dominion' | 'dominion_2_bot' | '3_step_domination_bot' | 'onnx_ml_bot') => void;
  fetchAllData: () => void;
  loading: boolean;
  isExportMenuOpen: boolean;
  setIsExportMenuOpen: (open: boolean) => void;
  setIsResetModalOpen: (open: boolean) => void;
  testResultMsg: string | null;
  setTestResultMsg: (msg: string | null) => void;
}

export const AnalyticsHeaderToolbar: React.FC<AnalyticsHeaderToolbarProps> = ({
  handleRunBotTest,
  isTestingBot,
  testBotType,
  setTestBotType,
  fetchAllData,
  loading,
  isExportMenuOpen,
  setIsExportMenuOpen,
  setIsResetModalOpen,
  testResultMsg,
  setTestResultMsg,
}) => {
  return (
    <>
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
              <BarChart3 className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-xl sm:text-2xl font-black tracking-tight text-white flex items-center gap-2">
                <span>Institutional Performance Analytics & Trade Journal</span>
                <span className="px-2 py-0.5 text-[10px] font-mono bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 rounded-full font-bold">
                  UNIFIED REPORTING HUB
                </span>
              </h2>
              <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
                Consolidated 15M Event Reports • Executions Ledger • Settlements • AI Inference • SQLite WAL Sync
              </p>
            </div>
          </div>
        </div>

        {/* Global Action Toolbar */}
        <div className="flex flex-wrap items-center gap-2.5 w-full lg:w-auto">
          {/* Test Bot Trigger with Multi-Bot Selector */}
          <div className="flex items-center bg-slate-900 border border-slate-700 rounded-xl p-0.5 shadow-sm">
            <button
              onClick={() => handleRunBotTest(testBotType)}
              disabled={isTestingBot}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs sm:text-sm font-bold rounded-lg shadow-md transition-all active:scale-95 disabled:opacity-50"
              title="Execute immediate 15M cycle trade test and record report"
            >
              {isTestingBot ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
              <span>{isTestingBot ? 'Testing...' : '🧪 Run 15M Test'}</span>
            </button>
            <div className="flex items-center px-1 gap-1">
              <button
                onClick={() => {
                  setTestBotType('both');
                  handleRunBotTest('both');
                }}
                className={`px-2 py-1 text-[10px] font-bold rounded-md transition ${
                  testBotType === 'both' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'
                }`}
                title="Run test trade for Both Domination and ONNX ML bots"
              >
                🚀 Both
              </button>
              <button
                onClick={() => {
                  setTestBotType('macro_onnx');
                  handleRunBotTest('macro_onnx');
                }}
                className={`px-2 py-1 text-[10px] font-bold rounded-md transition ${
                  testBotType === 'macro_onnx' ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-white'
                }`}
                title="Run test trade for Macro ONNX Bot (Champion)"
              >
                🧠 Macro ONNX
              </button>
              <button
                onClick={() => {
                  setTestBotType('macro_trend_dominion');
                  handleRunBotTest('macro_trend_dominion');
                }}
                className={`px-2 py-1 text-[10px] font-bold rounded-md transition ${
                  testBotType === 'macro_trend_dominion' ? 'bg-cyan-600 text-white' : 'text-slate-400 hover:text-white'
                }`}
                title="Run test trade for Macro Trend Dominion"
              >
                📈 Macro Trend
              </button>
              <button
                onClick={() => {
                  setTestBotType('dominion_2_bot');
                  handleRunBotTest('dominion_2_bot');
                }}
                className={`px-2 py-1 text-[10px] font-bold rounded-md transition ${
                  testBotType === 'dominion_2_bot' ? 'bg-emerald-600 text-white' : 'text-slate-400 hover:text-white'
                }`}
                title="Run test trade for Dominion 2 Bot (Anti-Pin Scalper)"
              >
                👑 Dominion 2
              </button>
              <button
                onClick={() => {
                  setTestBotType('3_step_domination_bot');
                  handleRunBotTest('3_step_domination_bot');
                }}
                className={`px-2 py-1 text-[10px] font-bold rounded-md transition ${
                  testBotType === '3_step_domination_bot' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-white'
                }`}
                title="Run test trade for 3-Step Domination Bot"
              >
                ⚡ Domination
              </button>
              <button
                onClick={() => {
                  setTestBotType('onnx_ml_bot');
                  handleRunBotTest('onnx_ml_bot');
                }}
                className={`px-2 py-1 text-[10px] font-bold rounded-md transition ${
                  testBotType === 'onnx_ml_bot' ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-white'
                }`}
                title="Run test trade for ONNX ML Ensemble"
              >
                🧠 ONNX
              </button>
            </div>
          </div>

          {/* Refresh Button */}
          <button
            onClick={fetchAllData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs sm:text-sm font-semibold rounded-xl transition border border-slate-700 shadow-sm"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
            <span>Refresh</span>
          </button>

          {/* Global Export Menu */}
          <div className="relative">
            <button
              onClick={() => setIsExportMenuOpen(!isExportMenuOpen)}
              className="flex items-center gap-1.5 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs sm:text-sm font-semibold rounded-xl transition border border-slate-700 shadow-sm"
            >
              <Download className="w-4 h-4 text-blue-400" />
              <span>Export All</span>
            </button>

            {isExportMenuOpen && (
              <div className="absolute right-0 mt-2 w-64 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl p-2 z-50 animate-in fade-in space-y-1 text-xs font-sans">
                <div className="px-2.5 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                  Download Reports
                </div>
                <a
                  href="/api/reports/executive-summary/export.json"
                  download="kalshi_executive_audit_summary.json"
                  onClick={() => setIsExportMenuOpen(false)}
                  className="flex items-center gap-2 px-2.5 py-2 rounded-lg hover:bg-slate-800 text-slate-200 hover:text-white transition"
                >
                  <FileText className="w-4 h-4 text-emerald-400" />
                  <span>Executive Audit Summary (JSON)</span>
                </a>
                <a
                  href="/api/reports/win-loss/export.csv"
                  download="kalshi_15m_win_loss_reports.csv"
                  onClick={() => setIsExportMenuOpen(false)}
                  className="flex items-center gap-2 px-2.5 py-2 rounded-lg hover:bg-slate-800 text-slate-200 hover:text-white transition"
                >
                  <FileSpreadsheet className="w-4 h-4 text-emerald-400" />
                  <span>15M Event Reports (CSV)</span>
                </a>
                <a
                  href="/api/history/trades/export.csv"
                  download="kalshi_trade_journal.csv"
                  onClick={() => setIsExportMenuOpen(false)}
                  className="flex items-center gap-2 px-2.5 py-2 rounded-lg hover:bg-slate-800 text-slate-200 hover:text-white transition"
                >
                  <FileSpreadsheet className="w-4 h-4 text-blue-400" />
                  <span>Trade Journal (CSV)</span>
                </a>
                <a
                  href="/api/history/settlements/export.csv"
                  download="kalshi_settlements.csv"
                  onClick={() => setIsExportMenuOpen(false)}
                  className="flex items-center gap-2 px-2.5 py-2 rounded-lg hover:bg-slate-800 text-slate-200 hover:text-white transition"
                >
                  <FileSpreadsheet className="w-4 h-4 text-purple-400" />
                  <span>Settlements Ledger (CSV)</span>
                </a>
                <a
                  href="/api/history/ai-predictions/export.csv"
                  download="kalshi_ai_decisions.csv"
                  onClick={() => setIsExportMenuOpen(false)}
                  className="flex items-center gap-2 px-2.5 py-2 rounded-lg hover:bg-slate-800 text-slate-200 hover:text-white transition"
                >
                  <FileSpreadsheet className="w-4 h-4 text-amber-400" />
                  <span>AI Inferences (CSV)</span>
                </a>
              </div>
            )}
          </div>

          {/* Delete / Reset Button */}
          <button
            onClick={() => setIsResetModalOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 hover:text-rose-100 text-xs sm:text-sm font-semibold rounded-xl transition border border-rose-800/60 shadow-sm"
          >
            <Trash2 className="w-4 h-4 text-rose-400" />
            <span>Reset Ledger</span>
          </button>
        </div>
      </div>

      {/* Live Test Feedback Banner */}
      {testResultMsg && (
        <div className="p-3 bg-blue-500/15 border border-blue-500/30 rounded-xl text-xs text-blue-300 flex items-center justify-between gap-2 animate-in fade-in">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-blue-400 shrink-0 animate-pulse" />
            <span className="font-mono">{testResultMsg}</span>
          </div>
          <button onClick={() => setTestResultMsg(null)} className="text-slate-400 hover:text-white text-xs">
            ✕
          </button>
        </div>
      )}
    </>
  );
};
