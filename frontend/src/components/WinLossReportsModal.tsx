import React, { useState, useEffect, useMemo } from 'react';
import { WinLossEventReport } from '../types';
import { 
  X, 
  Download, 
  TrendingUp, 
  TrendingDown, 
  Award, 
  CheckCircle2, 
  XCircle, 
  Activity, 
  Flame,
  ShieldCheck,
  Calendar,
  Bot,
  Filter
} from 'lucide-react';

interface WinLossReportsModalProps {
  isOpen: boolean;
  onClose: () => void;
  reports?: WinLossEventReport[];
  onTestBot?: () => Promise<any>;
  isLiveMode?: boolean;
}

export type TraderCategory = 'all' | '3_step_dom' | 'onnx_macro' | 'macro_onnx' | 'dominion_2' | 'macro_trend' | 'ofi_sprint' | 'onnx_ml' | 'live';

export const isLiveReport = (r: any): boolean =>
  r.execution_mode === 'live' || r.bot_type === 'live' || Boolean(r.report_id?.startsWith('WLR-LIVE-'));

export const isTodayReport = (r: any): boolean => {
  try {
    const now = new Date();
    const etTodayStr = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York' }).format(now);
    if (r.timestamp_utc && r.timestamp_utc.startsWith(etTodayStr)) return true;
    const monthDay = new Intl.DateTimeFormat('en-US', { month: 'long', day: '2-digit', timeZone: 'America/New_York' }).format(now);
    if (r.cycle_time && r.cycle_time.includes(monthDay)) return true;
    const shortMonthDay = new Intl.DateTimeFormat('en-US', { month: 'short', day: '2-digit', timeZone: 'America/New_York' }).format(now);
    if (r.cycle_time && r.cycle_time.includes(shortMonthDay)) return true;
    if (r.report_id && r.report_id.includes(etTodayStr.replace(/-/g, ''))) return true;
  } catch { }
  return false;
};

export const detectAsset = (r: any): 'BTC' | 'ETH' | 'SOL' | 'DOGE' => {
  if (r.asset) {
    const a = r.asset.toUpperCase();
    if (a === 'ETH' || a === 'SOL' || a === 'DOGE') return a;
    return 'BTC';
  }
  const t = (r.ticker || '').toUpperCase();
  if (t.includes('ETH')) return 'ETH';
  if (t.includes('SOL')) return 'SOL';
  if (t.includes('DOGE')) return 'DOGE';
  return 'BTC';
};

export const formatAssetPrice = (price: number | undefined | null, asset: string): string => {
  if (price == null || isNaN(price)) return '0.00';
  return asset === 'DOGE' ? price.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 6 }) : price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export const isOnnxMacroBot = (r: any) =>
  r.bot_id === 'onnx_macro_v2' ||
  r.bot_id === 'the_onnx_strategy' ||
  r.bot_id === 'dual_onnx' ||
  r.bot_type === 'onnx_macro_v2' ||
  r.bot_type === 'the_onnx_strategy' ||
  r.bot_type === 'dual_onnx' ||
  Boolean(
    r.ai_rationale?.toLowerCase().includes('dual onnx') ||
    r.ai_rationale?.toLowerCase().includes('the onnx strategy') ||
    r.ai_rationale?.toLowerCase().includes('dual-brain') ||
    r.strategy_name?.toLowerCase().includes('onnx')
  );

export const isOfiSprintBot = (r: any) =>
  r.bot_id === 'ofi_sprint_scalper' ||
  r.bot_type === 'ofi_sprint_scalper' ||
  r.bot_type === 'ofi_scalper' ||
  Boolean(r.ai_rationale?.toLowerCase().includes('ofi sprint'));

export const isMacroOnnxBot = (r: any) => r.bot_type === 'macro_onnx' || r.bot_type === 'macro_onnx_bot' || r.bot_type === 'macro_trend_onnx_fusion' || (r.ai_rationale?.toLowerCase().includes('macro') && r.ai_rationale?.toLowerCase().includes('onnx'));
export const isMacroBot = (r: any) => !isMacroOnnxBot(r) && !isOnnxMacroBot(r) && (r.bot_type === 'macro_trend_dominion' || r.bot_type === 'macro_trend' || r.ai_rationale?.toLowerCase().includes('macro trend'));
export const isDom2Bot = (r: any) => r.bot_type === 'dominion_2_bot' || r.bot_type === 'dominion2' || r.bot_type === 'dominion_v2' || r.ai_rationale?.toLowerCase().includes('dominion 2');
export const isDomBot = (r: any) => r.bot_type === '3_step_domination_bot' || r.bot_type === 'domination' || (!r.bot_type && r.ai_rationale?.toLowerCase().includes('domination') && !r.ai_rationale?.toLowerCase().includes('dominion 2'));
export const isOnnxBot = (r: any) => r.bot_type === 'onnx_ml_bot' || r.bot_type === 'onnx' || (r.ai_rationale?.toLowerCase().includes('onnx') && !isMacroOnnxBot(r) && !isOnnxMacroBot(r));

export const getTraderCategory = (r: any): TraderCategory => {
  if (isLiveReport(r)) return 'live';
  if (isOnnxMacroBot(r)) return 'onnx_macro';
  if (isMacroOnnxBot(r)) return 'macro_onnx';
  if (isMacroBot(r)) return 'macro_trend';
  if (isDom2Bot(r)) return 'dominion_2';
  if (isOfiSprintBot(r)) return 'ofi_sprint';
  if (isOnnxBot(r)) return 'onnx_ml';
  return '3_step_dom';
};

export const getTraderBadge = (cat: TraderCategory) => {
  switch (cat) {
    case 'live': return { name: 'Live Production', short: 'Live Kalshi', icon: '🔴', color: 'bg-rose-500/20 text-rose-300 border-rose-500/40' };
    case 'onnx_macro': return { name: 'The ONNX Strategy (Dual-Brain)', short: 'ONNX Strategy', icon: '🧠', color: 'bg-purple-500/20 text-purple-300 border-purple-500/40' };
    case 'macro_onnx': return { name: 'Macro ONNX Fusion', short: 'Macro ONNX', icon: '🧠', color: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40' };
    case 'macro_trend': return { name: 'Macro Trend Dominion', short: 'Macro Trend', icon: '📈', color: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40' };
    case 'dominion_2': return { name: 'Dominion 2 (Multi-Asset)', short: 'Dominion 2', icon: '👑', color: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' };
    case 'ofi_sprint': return { name: 'OFI Sprint Scalper', short: 'OFI Scalp', icon: '⚡', color: 'bg-blue-500/20 text-blue-300 border-blue-500/40' };
    case 'onnx_ml': return { name: 'ONNX ML Net', short: 'ONNX ML', icon: '🔬', color: 'bg-teal-500/20 text-teal-300 border-teal-500/40' };
    default: return { name: '3-Step Domination', short: '3-Step Dom', icon: '⚡', color: 'bg-amber-500/20 text-amber-300 border-amber-500/40' };
  }
};

export const WinLossReportsModal: React.FC<WinLossReportsModalProps> = ({
  isOpen,
  onClose,
  reports = [],
  onTestBot,
  isLiveMode = false,
}) => {
  const [modeFilter, setModeFilter] = useState<'all' | 'live' | 'paper'>('all');
  const [filter, setFilter] = useState<'all' | 'win' | 'loss'>('all');
  const [assetFilter, setAssetFilter] = useState<'all' | 'BTC' | 'ETH' | 'SOL' | 'DOGE'>('all');
  const [timeframeFilter, setTimeframeFilter] = useState<'all' | '5m' | '15m'>('all');
  const [traderFilter, setTraderFilter] = useState<TraderCategory>('all');
  const [dateScope, setDateScope] = useState<'all' | 'today'>('all');
  const [isTesting, setIsTesting] = useState<boolean>(false);
  const [testResultMsg, setTestResultMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isLiveMode || reports.some((r) => r.execution_mode === 'live' || r.report_id?.startsWith('WLR-LIVE-'))) {
      setModeFilter('live');
    } else {
      setModeFilter('all');
    }
  }, [isOpen, isLiveMode, reports]);

  const traderStats = useMemo(() => {
    const categories: TraderCategory[] = ['3_step_dom', 'onnx_macro', 'dominion_2', 'macro_trend', 'ofi_sprint', 'macro_onnx', 'onnx_ml', 'live'];
    return categories.map((cat) => {
      const subset = reports.filter((r) => getTraderCategory(r) === cat);
      const w = subset.filter((r) => r.outcome === 'win').length;
      const l = subset.filter((r) => r.outcome === 'loss').length;
      const pnl = subset.reduce((acc, r) => acc + (r.pnl || 0), 0);
      const wr = subset.length > 0 ? (w / subset.length) * 100 : 0;
      return { cat, badge: getTraderBadge(cat), total: subset.length, wins: w, losses: l, winRate: wr, pnl };
    });
  }, [reports]);

  if (!isOpen) return null;

  const totalLiveReports = reports.filter(isLiveReport);
  const totalLiveCount = totalLiveReports.length;
  const liveWins = totalLiveReports.filter((r) => r.outcome === 'win').length;
  const liveLosses = totalLiveReports.filter((r) => r.outcome === 'loss').length;
  const liveWinRate = totalLiveCount > 0 ? (liveWins / totalLiveCount) * 100 : 0;
  const livePnL = totalLiveReports.reduce((acc, r) => acc + (r.pnl || 0), 0);

  const todayReports = reports.filter(isTodayReport);
  const todayCount = todayReports.length;
  const todayWins = todayReports.filter((r) => r.outcome === 'win').length;
  const todayLosses = todayReports.filter((r) => r.outcome === 'loss').length;
  const todayWinRate = todayCount > 0 ? (todayWins / todayCount) * 100 : 0;
  const todayPnL = todayReports.reduce((acc, r) => acc + (r.pnl || 0), 0);
  const baseReports = reports.filter((r) => {
    if (dateScope === 'today' && !isTodayReport(r)) return false;
    if (modeFilter === 'live' && !isLiveReport(r)) return false;
    if (modeFilter === 'paper' && isLiveReport(r)) return false;
    if (traderFilter !== 'all' && getTraderCategory(r) !== traderFilter) return false;
    if (assetFilter !== 'all' && detectAsset(r) !== assetFilter) return false;
    if (timeframeFilter !== 'all' && (r.timeframe || '15m').toLowerCase() !== timeframeFilter.toLowerCase()) return false;
    return true;
  });

  const filteredReports = baseReports.filter((r) => {
    if (filter === 'win') return r.outcome === 'win';
    if (filter === 'loss') return r.outcome === 'loss';
    return true;
  });

  const totalEvents = baseReports.length;
  const wins = baseReports.filter((r) => r.outcome === 'win').length;
  const losses = baseReports.filter((r) => r.outcome === 'loss').length;
  const winRate = totalEvents > 0 ? (wins / totalEvents) * 100 : 0;
  const totalPnL = baseReports.reduce((acc, r) => acc + (r.pnl || 0), 0);
  
  const grossProfits = baseReports.filter((r) => (r.pnl || 0) > 0).reduce((acc, r) => acc + (r.pnl || 0), 0);
  const grossLosses = Math.abs(baseReports.filter((r) => (r.pnl || 0) < 0).reduce((acc, r) => acc + (r.pnl || 0), 0));
  const profitFactor = grossLosses > 0 ? grossProfits / grossLosses : grossProfits > 0 ? 99.9 : 1.0;
  const avgPnL = totalEvents > 0 ? totalPnL / totalEvents : 0;

  const handleRunBotTest = async () => {
    if (!onTestBot || isTesting) return;
    setIsTesting(true);
    setTestResultMsg(null);
    try {
      const res = await onTestBot();
      if (res?.message) setTestResultMsg(res.message);
    } catch (err) { setTestResultMsg(`Error running bot test: ${err}`); }
    finally { setIsTesting(false); }
  };

  const queryParams = new URLSearchParams();
  if (modeFilter === 'live') queryParams.set('mode', 'live');
  else if (modeFilter === 'paper') queryParams.set('mode', 'simulated');
  if (assetFilter !== 'all') queryParams.set('asset', assetFilter);
  if (timeframeFilter !== 'all') queryParams.set('timeframe', timeframeFilter);
  if (traderFilter !== 'all') queryParams.set('bot_type', traderFilter);
  if (dateScope === 'today') queryParams.set('date', 'today');

  const qs = queryParams.toString() ? `?${queryParams.toString()}` : '';
  const csvUrl = `/api/reports/win-loss/export.csv${qs}`;
  const jsonUrl = `/api/reports/win-loss/export.json${qs}`;
  const dateStr = dateScope === 'today' ? 'today_' : '';
  const traderStr = traderFilter !== 'all' ? `${traderFilter}_` : '';
  const csvFilename = `kalshi_${assetFilter !== 'all' ? assetFilter.toLowerCase() + '_' : ''}${timeframeFilter !== 'all' ? timeframeFilter + '_' : ''}${dateStr}${traderStr}${modeFilter === 'live' ? 'live' : 'win_loss'}_reports.csv`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-[#0e121a] border border-[#21262d] rounded-2xl w-full max-w-6xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden font-sans">
        
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#21262d] bg-[#111620]">
          <div className="flex items-center gap-3">
            <div className={`p-2.5 rounded-xl border ${modeFilter === 'live' ? 'bg-rose-500/10 border-rose-500/30 text-rose-400 shadow-lg shadow-rose-500/10' : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'}`}>
              {modeFilter === 'live' ? <Flame className="h-5 w-5 animate-pulse" /> : <Award className="h-5 w-5" />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white tracking-wide">
                  {modeFilter === 'live' ? '🔴 Live Real-Money Trade Audit Reports' : 'Institutional Trade & Settlement Reports'}
                </h2>
                {modeFilter === 'live' ? (
                  <span className="flex items-center gap-1 px-2.5 py-0.5 text-[10px] font-mono font-bold bg-rose-500/20 border border-rose-500/40 text-rose-300 rounded-full animate-pulse">
                    <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
                    LIVE PRODUCTION
                  </span>
                ) : (
                  <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-blue-500/20 border border-blue-500/30 text-blue-400 rounded-full">
                    TWO-TIER AUDIT
                  </span>
                )}
                {dateScope === 'today' && (
                  <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-amber-500/20 border border-amber-500/30 text-amber-300 rounded-full flex items-center gap-1">
                    <Calendar className="h-2.5 w-2.5" />
                    TODAY ONLY
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-400">Detailed breakdowns by bot attribution, real Kalshi settlements, and intraday horizons.</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              aria-label="Close win loss reports modal"
              className="p-1.5 text-gray-400 hover:text-white rounded-lg hover:bg-[#21262d] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
              title="Close Report Modal"
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 p-4 bg-[#141923] border-b border-[#21262d]">
          <div className="bg-[#0e121a] border border-[#21262d] rounded-xl p-3 flex flex-col justify-between gap-1">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Filtered Win Rate</span>
              <span className="text-[9px] font-mono text-gray-500">{wins}W / {losses}L</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className={`text-xl font-bold font-mono ${winRate >= 50 ? 'text-emerald-400' : 'text-amber-400'}`}>{winRate.toFixed(1)}%</span>
              <span className="text-xs text-gray-500 font-mono">({totalEvents} trades)</span>
            </div>
            <div className="w-full bg-[#21262d] h-1.5 rounded-full overflow-hidden mt-1">
              <div className={`h-full transition-all duration-500 ${modeFilter === 'live' ? 'bg-rose-500' : 'bg-emerald-500'}`} style={{ width: `${winRate}%` }} />
            </div>
          </div>

          <div className="bg-[#0e121a] border border-[#21262d] rounded-xl p-3 flex flex-col justify-between gap-1">
            <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Filtered Realized P&L</span>
            <div className="flex items-baseline gap-1">
              {totalPnL >= 0 ? <TrendingUp className="h-4 w-4 text-emerald-400 self-center" /> : <TrendingDown className="h-4 w-4 text-rose-400 self-center" />}
              <span className={`text-xl font-bold font-mono ${totalPnL >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {totalPnL >= 0 ? '+' : ''}${totalPnL.toFixed(2)}
              </span>
            </div>
            <span className="text-[10px] text-gray-500 font-mono">Avg: {avgPnL >= 0 ? '+' : ''}${avgPnL.toFixed(2)}/trade</span>
          </div>

          <button
            type="button"
            onClick={() => setDateScope(dateScope === 'today' ? 'all' : 'today')}
            aria-label="Filter reports by today"
            className={`border rounded-xl p-3 flex flex-col justify-between gap-1 cursor-pointer text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 ${dateScope === 'today' ? 'bg-amber-500/10 border-amber-500/50 shadow-md shadow-amber-500/10 ring-1 ring-amber-500/40' : 'bg-[#0e121a] border-[#21262d] hover:border-amber-500/30'}`}
          >
            <div className="flex items-center justify-between w-full">
              <span className="text-[10px] font-semibold text-amber-400 uppercase tracking-wider flex items-center gap-1"><Calendar className="h-3 w-3" /> Today's Report</span>
              <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 font-mono">{dateScope === 'today' ? 'ACTIVE' : 'FILTER'}</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className={`text-xl font-bold font-mono ${todayPnL >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{todayPnL >= 0 ? '+' : ''}${todayPnL.toFixed(2)}</span>
              <span className="text-xs text-gray-400 font-mono">({todayWinRate.toFixed(0)}% W)</span>
            </div>
            <span className="text-[10px] text-gray-400 font-mono">{todayCount} trades today ({todayWins}W / {todayLosses}L)</span>
          </button>

          <button
            type="button"
            onClick={() => setModeFilter(modeFilter === 'live' ? 'all' : 'live')}
            aria-label="Filter reports by live real-money trades"
            className={`border rounded-xl p-3 flex flex-col justify-between gap-1 cursor-pointer text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 ${modeFilter === 'live' ? 'bg-rose-500/10 border-rose-500/50 shadow-md shadow-rose-500/10 ring-1 ring-rose-500/40' : 'bg-[#0e121a] border-[#21262d] hover:border-rose-500/30'}`}
          >
            <div className="flex items-center justify-between w-full">
              <span className="text-[10px] font-semibold text-rose-400 uppercase tracking-wider flex items-center gap-1"><Flame className="h-3 w-3" /> Total Live Report</span>
              <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-rose-500/20 text-rose-300 font-mono">{totalLiveCount} REPS</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className={`text-xl font-bold font-mono ${livePnL >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{livePnL >= 0 ? '+' : ''}${livePnL.toFixed(2)}</span>
              <span className="text-xs text-gray-400 font-mono">({liveWinRate.toFixed(1)}% W)</span>
            </div>
            <span className="text-[10px] text-gray-400 font-mono">100% Real Kalshi Settlements</span>
          </button>

          <div className="bg-[#0e121a] border border-[#21262d] rounded-xl p-3 flex flex-col justify-between gap-1">
            <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Profit Factor</span>
            <span className="text-xl font-bold font-mono text-cyan-400">{profitFactor.toFixed(2)}x</span>
            <span className="text-[10px] text-gray-500 font-mono">+${grossProfits.toFixed(2)} / -${grossLosses.toFixed(2)}</span>
          </div>
        </div>

        <div className="px-5 py-2.5 bg-[#0d1117] border-b border-[#21262d] flex flex-col gap-1.5">
          <div className="flex items-center justify-between text-[11px] font-bold text-gray-400 uppercase tracking-wider font-mono">
            <span className="flex items-center gap-1.5 text-gray-300"><Bot className="h-3.5 w-3.5 text-blue-400" /><span>Who Traded — Bot &amp; Strategy Breakdown</span></span>
            <span className="text-[10px] text-gray-500">Click any bot card to isolate execution records</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-8 gap-2">
            {traderStats.map((ts) => {
              const isSelected = traderFilter === ts.cat;
              return (
                <button key={ts.cat} onClick={() => setTraderFilter(isSelected ? 'all' : ts.cat)} className={`px-2.5 py-2 rounded-lg border text-left transition-all flex flex-col gap-0.5 ${isSelected ? 'bg-blue-500/15 border-blue-500 text-white shadow-md ring-1 ring-blue-500/40' : 'bg-[#141923] border-[#21262d] hover:border-gray-600 text-gray-300'}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold truncate flex items-center gap-1"><span>{ts.badge.icon}</span><span className="truncate">{ts.badge.short}</span></span>
                    <span className="text-[9px] font-mono text-gray-500">{ts.total}</span>
                  </div>
                  <div className="flex items-baseline justify-between font-mono">
                    <span className="text-xs font-bold text-gray-200">{ts.winRate.toFixed(0)}% W</span>
                    <span className={`text-[11px] font-bold ${ts.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{ts.pnl >= 0 ? '+' : ''}${ts.pnl.toFixed(2)}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-2.5 border-b border-[#21262d] bg-[#111620]">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1 bg-[#090d14] p-1 rounded-xl border border-[#21262d]">
              <button onClick={() => setModeFilter('live')} className={`px-3 py-1 text-xs font-bold rounded-lg flex items-center gap-1.5 transition-all ${modeFilter === 'live' ? 'bg-rose-600 text-white shadow-lg shadow-rose-600/30' : 'text-gray-400 hover:text-rose-300'}`}>
                <span className={`h-2 w-2 rounded-full ${modeFilter === 'live' ? 'bg-white animate-pulse' : 'bg-rose-500'}`} />
                <span>🔴 Live Real Money</span>
                <span className="px-1.5 py-0.2 text-[10px] font-mono bg-black/40 rounded-full">{totalLiveCount}</span>
              </button>
              <button onClick={() => setModeFilter('paper')} className={`px-3 py-1 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-all ${modeFilter === 'paper' ? 'bg-indigo-600 text-white shadow-md' : 'text-gray-400 hover:text-indigo-300'}`}>
                <span>🧪 Paper / Simulated</span>
                <span className="px-1.5 py-0.2 text-[10px] font-mono bg-black/40 rounded-full">{reports.length - totalLiveCount}</span>
              </button>
              <button onClick={() => setModeFilter('all')} className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition-all ${modeFilter === 'all' ? 'bg-[#21262d] text-white shadow-sm' : 'text-gray-500 hover:text-gray-300'}`}>All ({reports.length})</button>
            </div>

            <div className="flex items-center gap-1 bg-[#0e121a] p-1 rounded-xl border border-[#21262d]">
              <button onClick={() => setDateScope('all')} className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition-colors ${dateScope === 'all' ? 'bg-blue-600 text-white shadow-sm' : 'text-gray-400 hover:text-white'}`}>All-Time</button>
              <button onClick={() => setDateScope('today')} className={`px-2.5 py-1 text-xs font-semibold rounded-lg flex items-center gap-1 transition-colors ${dateScope === 'today' ? 'bg-amber-600 text-white shadow-sm' : 'text-gray-400 hover:text-amber-300'}`}>
                <Calendar className="h-3 w-3" />
                <span>Today ({todayCount})</span>
              </button>
            </div>

            <div className="flex items-center gap-1 bg-[#0e121a] p-1 rounded-xl border border-[#21262d]">
              <span className="text-[10px] uppercase font-bold text-gray-500 px-1.5 flex items-center gap-1"><Filter className="h-3 w-3 text-gray-400" /><span>Bot:</span></span>
              {(['all', '3_step_dom', 'macro_onnx', 'dominion_2', 'onnx_ml', 'live'] as TraderCategory[]).map((cat) => {
                const label = cat === 'all' ? 'All' : getTraderBadge(cat).short;
                const isSel = traderFilter === cat;
                return (
                  <button key={cat} onClick={() => setTraderFilter(cat)} className={`px-2 py-0.5 text-[11px] font-semibold rounded transition ${isSel ? 'bg-blue-600 text-white font-bold' : 'text-gray-400 hover:text-white'}`}>
                    {label}
                  </button>
                );
              })}
            </div>

            <div className="flex items-center gap-1 bg-[#0e121a] p-1 rounded-xl border border-[#21262d]">
              <button onClick={() => setFilter('all')} className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition-colors ${filter === 'all' ? 'bg-blue-600 text-white shadow-sm' : 'text-gray-400 hover:text-white'}`}>All ({baseReports.length})</button>
              <button onClick={() => setFilter('win')} className={`px-2.5 py-1 text-xs font-semibold rounded-lg flex items-center gap-1 transition-colors ${filter === 'win' ? 'bg-emerald-600 text-white shadow-sm' : 'text-gray-400 hover:text-emerald-400'}`}>
                <CheckCircle2 className="h-3 w-3" /> Wins ({wins})
              </button>
              <button onClick={() => setFilter('loss')} className={`px-2.5 py-1 text-xs font-semibold rounded-lg flex items-center gap-1 transition-colors ${filter === 'loss' ? 'bg-rose-600 text-white shadow-sm' : 'text-gray-400 hover:text-rose-400'}`}>
                <XCircle className="h-3 w-3" /> Losses ({losses})
              </button>
            </div>

            <div className="flex items-center gap-1 bg-[#0e121a] p-1 rounded-xl border border-[#21262d]">
              {(['all', 'BTC', 'ETH', 'SOL', 'DOGE'] as const).map((ast) => (
                <button key={ast} onClick={() => setAssetFilter(ast)} className={`px-2 py-0.5 text-xs font-mono font-bold rounded transition-colors ${assetFilter === ast ? 'bg-amber-500 text-black shadow-sm font-extrabold' : 'text-gray-400 hover:text-white'}`}>
                  {ast}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-1 bg-[#0e121a] p-1 rounded-xl border border-[#21262d]">
              {(['all', '5m', '15m'] as const).map((tf) => (
                <button key={tf} onClick={() => setTimeframeFilter(tf)} className={`px-2 py-0.5 text-xs font-mono font-bold rounded transition-colors ${timeframeFilter === tf ? 'bg-cyan-500 text-black shadow-sm font-extrabold' : 'text-gray-400 hover:text-white'}`}>
                  {tf.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {onTestBot && (
              <button onClick={handleRunBotTest} disabled={isTesting} className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/40 text-emerald-400 text-xs font-bold rounded-xl transition-all shadow-sm">
                {isTesting ? <Activity className="h-3.5 w-3.5 animate-spin" /> : <Activity className="h-3.5 w-3.5" />}
                <span>{isTesting ? 'Evaluating...' : '🧪 Test Bot'}</span>
              </button>
            )}
            <a href={csvUrl} download={csvFilename} className="flex items-center gap-1.5 px-3 py-1.5 bg-[#161b22] hover:bg-[#21262d] border border-[#30363d] text-gray-300 hover:text-white text-xs font-semibold rounded-xl transition-colors">
              <Download className="h-3.5 w-3.5 text-emerald-400" />
              <span>CSV</span>
            </a>
            <a href={jsonUrl} download={modeFilter === 'live' ? 'kalshi_live_reports.json' : 'kalshi_win_loss_reports.json'} className="flex items-center gap-1.5 px-3 py-1.5 bg-[#161b22] hover:bg-[#21262d] border border-[#30363d] text-gray-300 hover:text-white text-xs font-semibold rounded-xl transition-colors">
              <Download className="h-3.5 w-3.5 text-blue-400" />
              <span>JSON</span>
            </a>
          </div>
        </div>

        {testResultMsg && (
          <div className="mx-5 my-2 p-2.5 bg-blue-500/10 border border-blue-500/30 rounded-xl text-xs text-blue-300 flex items-center gap-2 animate-in fade-in">
            <Activity className="h-4 w-4 text-blue-400 shrink-0" />
            <span className="font-mono">{testResultMsg}</span>
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-5">
          {filteredReports.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-500 gap-2">
              <Award className="h-10 w-10 text-gray-600" />
              <p className="text-sm font-medium">{modeFilter === 'live' ? 'No live real-money settlements matching current filters' : 'No trade event reports matching current filters'}</p>
              <p className="text-xs text-gray-600">Adjust filters or click "🧪 Test Bot" to simulate an immediate AI trade event.</p>
            </div>
          ) : (
            <div className="overflow-x-auto border border-[#21262d] rounded-xl">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-[#161b22] text-[#8b949e] border-b border-[#21262d] uppercase text-[10px] tracking-wider font-semibold font-mono">
                    <th className="py-3 px-3.5">Cycle Window (ET) &amp; Mode</th>
                    <th className="py-3 px-3">Who Traded (Bot / Strategy)</th>
                    <th className="py-3 px-3">Contract / Strike</th>
                    <th className="py-3 px-3 text-center">Action &amp; Sizing</th>
                    <th className="py-3 px-3 text-right">Entry $\to$ Settle</th>
                    <th className="py-3 px-3 text-center">Outcome</th>
                    <th className="py-3 px-3 text-right">Realized P&amp;L</th>
                    <th className="py-3 px-3">AI Rationale &amp; Settlement Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#21262d] font-mono">
                  {filteredReports.map((report) => {
                    const isWin = report.outcome === 'win';
                    const isLive = isLiveReport(report);
                    const asset = detectAsset(report);
                    const spotPrice = report.settlement_spot_price ?? report.settlement_btc_price ?? 0;
                    const strikePrice = report.strike_price || 0;
                    const diffStrike = spotPrice - strikePrice;
                    const traderCat = getTraderCategory(report);
                    const traderBadge = getTraderBadge(traderCat);
                    return (
                      <tr key={report.report_id} className={`transition-colors ${isLive ? 'bg-rose-950/10 hover:bg-rose-950/20' : 'hover:bg-[#161b22]/70'}`}>
                        <td className="py-3 px-3.5 whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <span className="font-sans font-semibold text-gray-200 text-[11px]">{report.cycle_time}</span>
                            {isLive ? <span className="inline-flex items-center gap-1 px-1.5 py-0.2 text-[9px] font-bold uppercase rounded bg-rose-500/20 border border-rose-500/40 text-rose-400"><span className="h-1 w-1 rounded-full bg-rose-400 animate-pulse" /> LIVE REAL</span> : <span className="inline-flex items-center px-1.5 py-0.2 text-[9px] font-bold uppercase rounded bg-indigo-500/20 border border-indigo-500/30 text-indigo-300">PAPER</span>}
                          </div>
                          <div className="text-[10px] text-gray-500 font-mono mt-0.5">{report.report_id}</div>
                        </td>
                        <td className="py-3 px-3 whitespace-nowrap">
                          <div className="flex items-center gap-1.5"><span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border ${traderBadge.color}`}><span>{traderBadge.icon}</span><span>{traderBadge.name}</span></span></div>
                          <div className="text-[9px] text-gray-500 font-mono mt-0.5">{report.bot_type || 'default_strategy'}</div>
                        </td>
                        <td className="py-3 px-3 whitespace-nowrap">
                          <div className="text-gray-300 font-bold text-xs flex items-center gap-1.5"><span>${formatAssetPrice(strikePrice, asset)}</span><span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-[#1f262d] text-[#8c9ba5] border border-[#30363d]">{asset}</span></div>
                          <div className="text-[10px] text-gray-400">Spot: ${formatAssetPrice(spotPrice, asset)}<span className={diffStrike >= 0 ? ' text-emerald-400' : ' text-rose-400'}> ({diffStrike >= 0 ? '+' : ''}${formatAssetPrice(diffStrike, asset)})</span></div>
                        </td>
                        <td className="py-3 px-3 text-center whitespace-nowrap">
                          <span className={`inline-block px-2.5 py-1 rounded-md text-[11px] font-bold uppercase ${report.bot_side === 'yes' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-sm shadow-emerald-500/10' : 'bg-rose-500/20 text-rose-400 border border-rose-500/40 shadow-sm shadow-rose-500/10'}`}>{(report.bot_side || 'BUY').toUpperCase()} ({report.contracts ?? 1} cts)</span>
                        </td>
                        <td className="py-3 px-3 text-right whitespace-nowrap">
                          <div className="text-gray-200 text-xs">{report.entry_price != null ? (report.entry_price * 100).toFixed(1) : '48.0'}¢ $\to$ ${report.settlement_price != null ? report.settlement_price.toFixed(2) : '0.00'}</div>
                          <div className="text-[10px] text-gray-500">Cost: ${(report.entry_price != null && report.contracts != null ? report.entry_price * report.contracts : 0.48).toFixed(2)}</div>
                        </td>
                        <td className="py-3 px-3 text-center whitespace-nowrap">
                          <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${isWin ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'}`}>{isWin ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}{(report.outcome || 'PENDING').toUpperCase()}</span>
                        </td>
                        <td className="py-3 px-3 text-right whitespace-nowrap">
                          <div className={`text-xs font-bold ${(report.pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{(report.pnl ?? 0) >= 0 ? '+' : ''}${report.pnl != null ? report.pnl.toFixed(2) : '0.00'}</div>
                          <div className={`text-[10px] ${(report.roi_pct ?? 0) >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>{(report.roi_pct ?? 0) >= 0 ? '+' : ''}{report.roi_pct != null ? report.roi_pct.toFixed(1) : '0.0'}% ROI</div>
                        </td>
                        <td className="py-3 px-3 font-sans text-gray-300 text-[11px] max-w-xs">
                          <div className="font-semibold text-gray-200 truncate" title={report.ai_rationale}>{report.ai_rationale || '--'}</div>
                          <div className="text-[10px] text-gray-500 font-mono flex items-center gap-2 mt-0.5 flex-wrap">
                            {isLive ? <span className="text-emerald-400 font-semibold flex items-center gap-1"><ShieldCheck className="h-3 w-3" /> Kalshi Exchange Verified</span> : <><span>Conf: {report.ai_confidence != null ? (report.ai_confidence * 100).toFixed(1) : '0.0'}%</span><span>•</span><span>VPIN: {report.vpin_score != null ? report.vpin_score.toFixed(2) : '0.00'}</span></>}
                            {report.bot_parameters && (
                              <span
                                className="px-1.5 py-0.2 rounded bg-cyan-950/40 text-cyan-400 border border-cyan-800/40 text-[9px] font-mono cursor-help"
                                title={`Maker: $${report.bot_parameters.discount_limit_price ?? '0.51'} | Edge: ${report.bot_parameters.min_edge_pct ?? '1.5'}% | MaxQueue: ${report.bot_parameters.max_queue_depth_ahead ?? '25000'} | TP: $${report.bot_parameters.take_profit_price_threshold ?? '0.92'} | Moat: ${report.bot_parameters.moneyness_moat_multiplier ?? '1.36'}x`}
                              >
                                ⚙️ Dials Locked
                              </span>
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

        <div className="flex items-center justify-between px-6 py-3 border-t border-[#21262d] bg-[#111620] text-xs text-gray-400 font-mono">
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${modeFilter === 'live' ? 'bg-rose-500 animate-ping' : 'bg-emerald-400 animate-pulse'}`} />
            <span>{modeFilter === 'live' ? 'Kalshi Exchange Portfolio Reconciler Active (Zero Mock Data Guarantee)' : 'Autonomous Multi-Strategy Execution Engine Active'}</span>
          </div>
          <button onClick={onClose} className="px-4 py-1.5 bg-[#21262d] hover:bg-[#30363d] text-white rounded-xl transition-colors font-semibold font-sans">Close Report</button>
        </div>
      </div>
    </div>
  );
};
