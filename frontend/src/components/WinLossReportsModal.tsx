import React, { useState } from 'react';
import { WinLossEventReport } from '../types';
import { 
  X, 
  Download, 
  TrendingUp, 
  TrendingDown, 
  Award, 
  FileSpreadsheet, 
  CheckCircle2, 
  XCircle, 
  Activity, 
  Play, 
  Loader2,
  Filter
} from 'lucide-react';

interface WinLossReportsModalProps {
  isOpen: boolean;
  onClose: () => void;
  reports?: WinLossEventReport[];
  onTestBot?: () => Promise<any>;
}

export const WinLossReportsModal: React.FC<WinLossReportsModalProps> = ({
  isOpen,
  onClose,
  reports = [],
  onTestBot,
}) => {
  const [filter, setFilter] = useState<'all' | 'win' | 'loss'>('all');
  const [isTesting, setIsTesting] = useState<boolean>(false);
  const [testResultMsg, setTestResultMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  // Filter reports
  const filteredReports = reports.filter((r) => {
    if (filter === 'win') return r.outcome === 'win';
    if (filter === 'loss') return r.outcome === 'loss';
    return true;
  });

  // Calculate aggregate metrics
  const totalEvents = reports.length;
  const wins = reports.filter((r) => r.outcome === 'win').length;
  const losses = reports.filter((r) => r.outcome === 'loss').length;
  const winRate = totalEvents > 0 ? (wins / totalEvents) * 100 : 0;
  const totalPnL = reports.reduce((acc, r) => acc + (r.pnl || 0), 0);
  
  const grossProfits = reports
    .filter((r) => (r.pnl || 0) > 0)
    .reduce((acc, r) => acc + r.pnl, 0);
  const grossLosses = Math.abs(
    reports
      .filter((r) => (r.pnl || 0) < 0)
      .reduce((acc, r) => acc + r.pnl, 0)
  );
  const profitFactor = grossLosses > 0 ? grossProfits / grossLosses : grossProfits > 0 ? 99.9 : 1.0;
  const avgPnL = totalEvents > 0 ? totalPnL / totalEvents : 0;

  const handleRunBotTest = async () => {
    if (!onTestBot || isTesting) return;
    setIsTesting(true);
    setTestResultMsg(null);
    try {
      const res = await onTestBot();
      if (res?.message) {
        setTestResultMsg(res.message);
      }
    } catch (err) {
      setTestResultMsg(`Error running bot test: ${err}`);
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-[#0e121a] border border-[#21262d] rounded-2xl w-full max-w-5xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#21262d] bg-[#111620]">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <Award className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white tracking-wide">
                  15-Minute Event Win/Loss Reports
                </h2>
                <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-blue-500/20 border border-blue-500/30 text-blue-400 rounded-full">
                  15M CYCLES
                </span>
              </div>
              <p className="text-xs text-gray-400">
                Automated trade decisions, settlement payoffs, and quantitative performance per 15-minute event
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="p-1.5 text-gray-400 hover:text-white rounded-lg hover:bg-[#21262d] transition-colors"
              title="Close Report Modal"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Top Summary KPI Banner */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-5 bg-[#141923] border-b border-[#21262d]">
          {/* Win Rate */}
          <div className="bg-[#0e121a] border border-[#21262d] rounded-xl p-3 flex flex-col gap-1">
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
              Win Rate
            </span>
            <div className="flex items-baseline gap-2">
              <span className={`text-xl font-bold font-mono ${winRate >= 50 ? 'text-emerald-400' : 'text-amber-400'}`}>
                {winRate.toFixed(1)}%
              </span>
              <span className="text-xs text-gray-500 font-mono">
                ({wins}W / {losses}L)
              </span>
            </div>
            <div className="w-full bg-[#21262d] h-1.5 rounded-full overflow-hidden mt-1">
              <div
                className="bg-emerald-500 h-full transition-all duration-500"
                style={{ width: `${winRate}%` }}
              />
            </div>
          </div>

          {/* Realized PnL */}
          <div className="bg-[#0e121a] border border-[#21262d] rounded-xl p-3 flex flex-col gap-1">
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
              Total Realized P&L
            </span>
            <div className="flex items-baseline gap-1">
              {totalPnL >= 0 ? (
                <TrendingUp className="h-4 w-4 text-emerald-400 self-center" />
              ) : (
                <TrendingDown className="h-4 w-4 text-rose-400 self-center" />
              )}
              <span className={`text-xl font-bold font-mono ${totalPnL >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {totalPnL >= 0 ? '+' : ''}${totalPnL.toFixed(2)}
              </span>
            </div>
            <span className="text-[10px] text-gray-500 font-mono">
              Total 15M Events: {totalEvents}
            </span>
          </div>

          {/* Profit Factor */}
          <div className="bg-[#0e121a] border border-[#21262d] rounded-xl p-3 flex flex-col gap-1">
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
              Profit Factor
            </span>
            <span className="text-xl font-bold font-mono text-cyan-400">
              {profitFactor.toFixed(2)}x
            </span>
            <span className="text-[10px] text-gray-500 font-mono">
              +${grossProfits.toFixed(2)} / -${grossLosses.toFixed(2)}
            </span>
          </div>

          {/* Avg Return per Event */}
          <div className="bg-[#0e121a] border border-[#21262d] rounded-xl p-3 flex flex-col gap-1">
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
              Avg Event P&L
            </span>
            <span className={`text-xl font-bold font-mono ${avgPnL >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {avgPnL >= 0 ? '+' : ''}${avgPnL.toFixed(2)}
            </span>
            <span className="text-[10px] text-gray-500 font-mono">
              per 15-min cycle
            </span>
          </div>
        </div>

        {/* Action Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 border-b border-[#21262d] bg-[#111620]">
          {/* Filter Pills */}
          <div className="flex items-center gap-1.5 bg-[#0e121a] p-1 rounded-xl border border-[#21262d]">
            <button
              onClick={() => setFilter('all')}
              className={`px-3 py-1 text-xs font-semibold rounded-lg transition-colors ${
                filter === 'all'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              All Events ({reports.length})
            </button>
            <button
              onClick={() => setFilter('win')}
              className={`px-3 py-1 text-xs font-semibold rounded-lg flex items-center gap-1 transition-colors ${
                filter === 'win'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-emerald-400'
              }`}
            >
              <CheckCircle2 className="h-3 w-3" />
              Wins ({wins})
            </button>
            <button
              onClick={() => setFilter('loss')}
              className={`px-3 py-1 text-xs font-semibold rounded-lg flex items-center gap-1 transition-colors ${
                filter === 'loss'
                  ? 'bg-rose-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-rose-400'
              }`}
            >
              <XCircle className="h-3 w-3" />
              Losses ({losses})
            </button>
          </div>

          {/* Test Bot & Export Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleRunBotTest}
              disabled={isTesting}
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-blue-500/20 transition-all active:scale-95 disabled:opacity-50"
            >
              {isTesting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Play className="h-3.5 w-3.5 fill-current" />
              )}
              <span>{isTesting ? 'Running Bot Test...' : '🧪 Test Bot (15M)'}</span>
            </button>

            <a
              href="/api/reports/win-loss/export.csv"
              download="kalshi_15m_win_loss_reports.csv"
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#161b22] hover:bg-[#21262d] border border-[#30363d] text-gray-300 hover:text-white text-xs font-semibold rounded-xl transition-colors"
            >
              <FileSpreadsheet className="h-3.5 w-3.5 text-emerald-400" />
              <span>CSV</span>
            </a>

            <a
              href="/api/reports/win-loss/export.json"
              download="kalshi_15m_win_loss_reports.json"
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#161b22] hover:bg-[#21262d] border border-[#30363d] text-gray-300 hover:text-white text-xs font-semibold rounded-xl transition-colors"
            >
              <Download className="h-3.5 w-3.5 text-blue-400" />
              <span>JSON</span>
            </a>
          </div>
        </div>

        {/* Live Test Feedback Banner */}
        {testResultMsg && (
          <div className="mx-5 my-2 p-2.5 bg-blue-500/10 border border-blue-500/30 rounded-xl text-xs text-blue-300 flex items-center gap-2 animate-in fade-in">
            <Activity className="h-4 w-4 text-blue-400 shrink-0" />
            <span className="font-mono">{testResultMsg}</span>
          </div>
        )}

        {/* Reports Table */}
        <div className="flex-1 overflow-y-auto p-5">
          {filteredReports.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-500 gap-2">
              <Award className="h-10 w-10 text-gray-600" />
              <p className="text-sm font-medium">No 15-minute event reports recorded yet</p>
              <p className="text-xs text-gray-600">
                Click &quot;🧪 Test Bot (15M)&quot; above to simulate an immediate AI trade event.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto border border-[#21262d] rounded-xl">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-[#161b22] text-[#8b949e] border-b border-[#21262d] uppercase text-[10px] tracking-wider font-semibold">
                    <th className="py-3 px-3.5">Cycle Window (ET)</th>
                    <th className="py-3 px-3">Contract / Strike</th>
                    <th className="py-3 px-3 text-center">Bot Action</th>
                    <th className="py-3 px-3 text-right">Entry $\to$ Settle</th>
                    <th className="py-3 px-3 text-center">Outcome</th>
                    <th className="py-3 px-3 text-right">Realized P&L</th>
                    <th className="py-3 px-3">AI Rationale & Metrics</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#21262d] font-mono">
                  {filteredReports.map((report) => {
                    const isWin = report.outcome === 'win';
                    const diffStrike = (report.settlement_btc_price || 0) - (report.strike_price || 0);

                    return (
                      <tr
                        key={report.report_id}
                        className="hover:bg-[#161b22]/70 transition-colors"
                      >
                        {/* 15m Cycle Window */}
                        <td className="py-3 px-3.5 whitespace-nowrap">
                          <div className="font-sans font-semibold text-gray-200 text-[11px]">
                            {report.cycle_time}
                          </div>
                          <div className="text-[10px] text-gray-500 font-mono">
                            {report.report_id}
                          </div>
                        </td>

                        {/* Ticker & Strike */}
                        <td className="py-3 px-3 whitespace-nowrap">
                          <div className="text-gray-300 font-bold text-xs">
                            ${report.strike_price ? report.strike_price.toLocaleString('en-US', { minimumFractionDigits: 2 }) : '0.00'}
                          </div>
                          <div className="text-[10px] text-gray-400">
                            Spot: ${report.settlement_btc_price ? report.settlement_btc_price.toLocaleString('en-US', { minimumFractionDigits: 2 }) : '0.00'}
                            <span className={diffStrike >= 0 ? ' text-emerald-400' : ' text-rose-400'}>
                              {' '}({diffStrike >= 0 ? '+' : ''}${diffStrike.toFixed(2)})
                            </span>
                          </div>
                        </td>

                        {/* Bot Action */}
                        <td className="py-3 px-3 text-center whitespace-nowrap">
                          <span
                            className={`inline-block px-2.5 py-1 rounded-md text-[11px] font-bold uppercase ${
                              report.bot_side === 'yes'
                                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-sm shadow-emerald-500/10'
                                : 'bg-rose-500/20 text-rose-400 border border-rose-500/40 shadow-sm shadow-rose-500/10'
                            }`}
                          >
                            {report.bot_side.toUpperCase()} ({report.contracts} cts)
                          </span>
                        </td>

                        {/* Entry -> Settlement Price */}
                        <td className="py-3 px-3 text-right whitespace-nowrap">
                          <div className="text-gray-200 text-xs">
                            {(report.entry_price * 100).toFixed(1)}¢ $\to$ ${(report.settlement_price).toFixed(2)}
                          </div>
                          <div className="text-[10px] text-gray-500">
                            Cost: ${(report.entry_price * report.contracts).toFixed(2)}
                          </div>
                        </td>

                        {/* Outcome Badge */}
                        <td className="py-3 px-3 text-center whitespace-nowrap">
                          <span
                            className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                              isWin
                                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                            }`}
                          >
                            {isWin ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                            {report.outcome.toUpperCase()}
                          </span>
                        </td>

                        {/* Realized PnL & ROI */}
                        <td className="py-3 px-3 text-right whitespace-nowrap">
                          <div className={`text-xs font-bold ${report.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {report.pnl >= 0 ? '+' : ''}${report.pnl.toFixed(2)}
                          </div>
                          <div className={`text-[10px] ${report.roi_pct >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                            {report.roi_pct >= 0 ? '+' : ''}{report.roi_pct.toFixed(1)}% ROI
                          </div>
                        </td>

                        {/* AI Rationale & Metrics */}
                        <td className="py-3 px-3 font-sans text-gray-300 text-[11px] max-w-xs">
                          <div className="font-semibold text-gray-200 truncate" title={report.ai_rationale}>
                            {report.ai_rationale}
                          </div>
                          <div className="text-[10px] text-gray-500 font-mono flex items-center gap-2 mt-0.5">
                            <span>Conf: {(report.ai_confidence * 100).toFixed(1)}%</span>
                            <span>•</span>
                            <span>VPIN: {report.vpin_score.toFixed(2)}</span>
                            <span>•</span>
                            <span>Edge: {(report.ev_edge * 100).toFixed(1)}%</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-[#21262d] bg-[#111620] text-xs text-gray-400">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>Autonomous 15M Evaluation Engine Active</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-[#21262d] hover:bg-[#30363d] text-white rounded-xl transition-colors font-semibold"
          >
            Close Report
          </button>
        </div>
      </div>
    </div>
  );
};
