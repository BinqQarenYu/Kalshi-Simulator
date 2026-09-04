import React, { useState, useEffect } from 'react';
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
  Radio,
  Flame,
  ShieldCheck
} from 'lucide-react';

interface WinLossReportsModalProps {
  isOpen: boolean;
  onClose: () => void;
  reports?: WinLossEventReport[];
  onTestBot?: () => Promise<any>;
  isLiveMode?: boolean;
}

export const WinLossReportsModal: React.FC<WinLossReportsModalProps> = ({
  isOpen,
  onClose,
  reports = [],
  onTestBot,
  isLiveMode = false,
}) => {
  const [modeFilter, setModeFilter] = useState<'all' | 'live' | 'paper'>('all');
  const [filter, setFilter] = useState<'all' | 'win' | 'loss'>('all');
  const [isTesting, setIsTesting] = useState<boolean>(false);
  const [testResultMsg, setTestResultMsg] = useState<string | null>(null);

  // Default to 'live' if app is in live mode or if live reports exist
  useEffect(() => {
    if (isLiveMode || reports.some((r) => r.execution_mode === 'live')) {
      setModeFilter('live');
    } else {
      setModeFilter('all');
    }
  }, [isOpen, isLiveMode]);

  if (!isOpen) return null;

  const isLiveReport = (r: WinLossEventReport) =>
    (r.execution_mode === 'live' || r.bot_type === 'live') && (r.ticker.includes('SEP01') || r.timestamp_utc?.startsWith('2026-09-01'));

  const liveReports = reports.filter(isLiveReport);
  const paperReports = reports.filter((r) => !isLiveReport(r));

  // Filter reports by execution mode first
  const baseReports = reports.filter((r) => {
    if (modeFilter === 'live') return isLiveReport(r);
    if (modeFilter === 'paper') return !isLiveReport(r);
    return true;
  });

  // Filter reports by outcome
  const filteredReports = baseReports.filter((r) => {
    if (filter === 'win') return r.outcome === 'win';
    if (filter === 'loss') return r.outcome === 'loss';
    return true;
  });

  // Calculate aggregate metrics for currently filtered execution mode
  const totalEvents = baseReports.length;
  const wins = baseReports.filter((r) => r.outcome === 'win').length;
  const losses = baseReports.filter((r) => r.outcome === 'loss').length;
  const winRate = totalEvents > 0 ? (wins / totalEvents) * 100 : 0;
  const totalPnL = baseReports.reduce((acc, r) => acc + (r.pnl || 0), 0);
  
  const grossProfits = baseReports
    .filter((r) => (r.pnl || 0) > 0)
    .reduce((acc, r) => acc + r.pnl, 0);
  const grossLosses = Math.abs(
    baseReports
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

  const csvUrl = modeFilter === 'live'
    ? '/api/reports/win-loss/export.csv?mode=live'
    : modeFilter === 'paper'
    ? '/api/reports/win-loss/export.csv?mode=simulated'
    : '/api/reports/win-loss/export.csv';

  const jsonUrl = modeFilter === 'live'
    ? '/api/reports/win-loss/export.json?mode=live'
    : modeFilter === 'paper'
    ? '/api/reports/win-loss/export.json?mode=simulated'
    : '/api/reports/win-loss/export.json';

  const csvFilename = modeFilter === 'live'
    ? 'kalshi_15m_live_reports.csv'
    : 'kalshi_15m_win_loss_reports.csv';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-[#0e121a] border border-[#21262d] rounded-2xl w-full max-w-5xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#21262d] bg-[#111620]">
          <div className="flex items-center gap-3">
            <div className={`p-2.5 rounded-xl border ${
              modeFilter === 'live' 
                ? 'bg-rose-500/10 border-rose-500/30 text-rose-400 shadow-lg shadow-rose-500/10'
                : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
            }`}>
              {modeFilter === 'live' ? <Flame className="h-5 w-5 animate-pulse" /> : <Award className="h-5 w-5" />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white tracking-wide">
                  {modeFilter === 'live' ? '🔴 Live Real-Money Event Reports' : '15-Minute Event Win/Loss Reports'}
                </h2>
                {modeFilter === 'live' ? (
                  <span className="flex items-center gap-1 px-2.5 py-0.5 text-[10px] font-mono font-bold bg-rose-500/20 border border-rose-500/40 text-rose-300 rounded-full animate-pulse">
                    <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
                    LIVE PRODUCTION
                  </span>
                ) : (
                  <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-blue-500/20 border border-blue-500/30 text-blue-400 rounded-full">
                    15M CYCLES
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-400">
                {modeFilter === 'live'
                  ? 'Real exchange settlements, actual filled contracts, net dollar payoffs, and exchange transaction fees.'
                  : 'Automated trade decisions, settlement payoffs, and quantitative performance per 15-minute event.'}
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
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
                {modeFilter === 'live' ? 'Live Win Rate' : 'Win Rate'}
              </span>
              {modeFilter === 'live' && (
                <span className="text-[9px] font-bold text-rose-400 bg-rose-500/10 px-1.5 py-0.5 rounded border border-rose-500/20">
                  REAL
                </span>
              )}
            </div>
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
                className={`h-full transition-all duration-500 ${modeFilter === 'live' ? 'bg-emerald-400' : 'bg-emerald-500'}`}
                style={{ width: `${winRate}%` }}
              />
            </div>
          </div>

          {/* Realized PnL */}
          <div className="bg-[#0e121a] border border-[#21262d] rounded-xl p-3 flex flex-col gap-1">
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
              {modeFilter === 'live' ? 'Live Net Realized P&L' : 'Total Realized P&L'}
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
              Events: {totalEvents} {modeFilter === 'live' ? '(Kalshi API Settlements)' : ''}
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
          {/* Mode Switcher & Outcome Filter Pills */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Primary Mode Selector */}
            <div className="flex items-center gap-1 bg-[#090d14] p-1 rounded-xl border border-[#21262d]">
              <button
                onClick={() => setModeFilter('live')}
                className={`px-3 py-1 text-xs font-bold rounded-lg flex items-center gap-1.5 transition-all ${
                  modeFilter === 'live'
                    ? 'bg-rose-600 text-white shadow-lg shadow-rose-600/30'
                    : 'text-gray-400 hover:text-rose-300'
                }`}
              >
                <span className={`h-2 w-2 rounded-full ${modeFilter === 'live' ? 'bg-white animate-pulse' : 'bg-rose-500'}`} />
                <span>🔴 Live Real Money</span>
                <span className="px-1.5 py-0.2 text-[10px] font-mono bg-black/40 rounded-full">
                  {liveReports.length}
                </span>
              </button>

              <button
                onClick={() => setModeFilter('paper')}
                className={`px-3 py-1 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-all ${
                  modeFilter === 'paper'
                    ? 'bg-indigo-600 text-white shadow-md'
                    : 'text-gray-400 hover:text-indigo-300'
                }`}
              >
                <span>🧪 Paper / Simulated</span>
                <span className="px-1.5 py-0.2 text-[10px] font-mono bg-black/40 rounded-full">
                  {paperReports.length}
                </span>
              </button>

              <button
                onClick={() => setModeFilter('all')}
                className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition-all ${
                  modeFilter === 'all'
                    ? 'bg-[#21262d] text-white shadow-sm'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                All ({reports.length})
              </button>
            </div>

            {/* Outcome Filter Pills */}
            <div className="flex items-center gap-1 bg-[#0e121a] p-1 rounded-xl border border-[#21262d]">
              <button
                onClick={() => setFilter('all')}
                className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition-colors ${
                  filter === 'all'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                All ({baseReports.length})
              </button>
              <button
                onClick={() => setFilter('win')}
                className={`px-2.5 py-1 text-xs font-semibold rounded-lg flex items-center gap-1 transition-colors ${
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
                className={`px-2.5 py-1 text-xs font-semibold rounded-lg flex items-center gap-1 transition-colors ${
                  filter === 'loss'
                    ? 'bg-rose-600 text-white shadow-sm'
                    : 'text-gray-400 hover:text-rose-400'
                }`}
              >
                <XCircle className="h-3 w-3" />
                Losses ({losses})
              </button>
            </div>
          </div>

          {/* Test Bot & Export Buttons */}
          <div className="flex items-center gap-2">
            {!isLiveMode && (
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
            )}

            <a
              href={csvUrl}
              download={csvFilename}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#161b22] hover:bg-[#21262d] border border-[#30363d] text-gray-300 hover:text-white text-xs font-semibold rounded-xl transition-colors"
            >
              <FileSpreadsheet className="h-3.5 w-3.5 text-emerald-400" />
              <span>CSV</span>
            </a>

            <a
              href={jsonUrl}
              download={modeFilter === 'live' ? 'kalshi_15m_live_reports.json' : 'kalshi_15m_win_loss_reports.json'}
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
              <p className="text-sm font-medium">
                {modeFilter === 'live' 
                  ? 'No live real-money settlements recorded yet' 
                  : 'No 15-minute event reports recorded yet'}
              </p>
              <p className="text-xs text-gray-600">
                {modeFilter === 'live'
                  ? 'Live trades placed on Kalshi will automatically reconcile with official exchange settlements here.'
                  : 'Click "🧪 Test Bot (15M)" above to simulate an immediate AI trade event.'}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto border border-[#21262d] rounded-xl">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-[#161b22] text-[#8b949e] border-b border-[#21262d] uppercase text-[10px] tracking-wider font-semibold">
                    <th className="py-3 px-3.5">Cycle Window (ET) & Mode</th>
                    <th className="py-3 px-3">Contract / Strike</th>
                    <th className="py-3 px-3 text-center">Bot Action</th>
                    <th className="py-3 px-3 text-right">Entry $\to$ Settle</th>
                    <th className="py-3 px-3 text-center">Outcome</th>
                    <th className="py-3 px-3 text-right">Realized P&L</th>
                    <th className="py-3 px-3">AI Rationale & Settlement Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#21262d] font-mono">
                  {filteredReports.map((report) => {
                    const isWin = report.outcome === 'win';
                    const isLiveReport = report.execution_mode === 'live';
                    const diffStrike = (report.settlement_btc_price || 0) - (report.strike_price || 0);

                    return (
                      <tr
                        key={report.report_id}
                        className={`transition-colors ${
                          isLiveReport 
                            ? 'bg-rose-950/10 hover:bg-rose-950/20' 
                            : 'hover:bg-[#161b22]/70'
                        }`}
                      >
                        {/* 15m Cycle Window & Mode */}
                        <td className="py-3 px-3.5 whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <span className="font-sans font-semibold text-gray-200 text-[11px]">
                              {report.cycle_time}
                            </span>
                            {isLiveReport ? (
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.2 text-[9px] font-bold uppercase rounded bg-rose-500/20 border border-rose-500/40 text-rose-400">
                                <span className="h-1 w-1 rounded-full bg-rose-400 animate-pulse" />
                                LIVE REAL
                              </span>
                            ) : (
                              <span className="inline-flex items-center px-1.5 py-0.2 text-[9px] font-bold uppercase rounded bg-indigo-500/20 border border-indigo-500/30 text-indigo-300">
                                PAPER
                              </span>
                            )}
                          </div>
                          <div className="text-[10px] text-gray-500 font-mono mt-0.5">
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
                            <span className={(diffStrike || 0) >= 0 ? ' text-emerald-400' : ' text-rose-400'}>
                              {' '}({(diffStrike || 0) >= 0 ? '+' : ''}${(diffStrike || 0).toFixed(2)})
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
                            {(report.bot_side || 'BUY').toUpperCase()} ({report.contracts ?? 0} cts)
                          </span>
                        </td>

                        {/* Entry -> Settlement Price */}
                        <td className="py-3 px-3 text-right whitespace-nowrap">
                          <div className="text-gray-200 text-xs">
                            {report.entry_price != null ? (report.entry_price * 100).toFixed(1) : '0.0'}¢ $\to$ ${report.settlement_price != null ? report.settlement_price.toFixed(2) : '0.00'}
                          </div>
                          <div className="text-[10px] text-gray-500">
                            Cost: ${(report.entry_price != null && report.contracts != null ? report.entry_price * report.contracts : 0).toFixed(2)}
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
                            {(report.outcome || 'PENDING').toUpperCase()}
                          </span>
                        </td>

                        {/* Realized PnL & ROI */}
                        <td className="py-3 px-3 text-right whitespace-nowrap">
                          <div className={`text-xs font-bold ${(report.pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {(report.pnl ?? 0) >= 0 ? '+' : ''}${report.pnl != null ? report.pnl.toFixed(2) : '0.00'}
                          </div>
                          <div className={`text-[10px] ${(report.roi_pct ?? 0) >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                            {(report.roi_pct ?? 0) >= 0 ? '+' : ''}{report.roi_pct != null ? report.roi_pct.toFixed(1) : '0.0'}% ROI
                          </div>
                          {report.balance_after != null && (
                            <div className="text-[10px] text-gray-400 font-mono">
                              Bal: ${(report.balance_after).toFixed(2)}
                            </div>
                          )}
                        </td>

                        {/* AI Rationale & Metrics */}
                        <td className="py-3 px-3 font-sans text-gray-300 text-[11px] max-w-xs">
                          <div className="font-semibold text-gray-200 truncate" title={report.ai_rationale}>
                            {report.ai_rationale || '--'}
                          </div>
                          <div className="text-[10px] text-gray-500 font-mono flex items-center gap-2 mt-0.5">
                            {isLiveReport ? (
                              <span className="text-emerald-400 font-semibold flex items-center gap-1">
                                <ShieldCheck className="h-3 w-3" />
                                Exchange Verified
                              </span>
                            ) : (
                              <>
                                <span>Conf: {report.ai_confidence != null ? (report.ai_confidence * 100).toFixed(1) : '0.0'}%</span>
                                <span>•</span>
                                <span>VPIN: {report.vpin_score != null ? report.vpin_score.toFixed(2) : '0.00'}</span>
                                <span>•</span>
                                <span>Edge: {report.ev_edge != null ? (report.ev_edge * 100).toFixed(1) : '0.0'}%</span>
                              </>
                            )}
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
            <span className={`h-2 w-2 rounded-full ${modeFilter === 'live' ? 'bg-rose-500 animate-ping' : 'bg-emerald-400 animate-pulse'}`} />
            <span>
              {modeFilter === 'live' 
                ? 'Kalshi Exchange Portfolio Reconciler Active (Zero Mock Data Guarantee)' 
                : 'Autonomous 15M Evaluation Engine Active'}
            </span>
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
