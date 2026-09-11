import React, { useState, useEffect, useMemo } from 'react';
import { WinLossEventReport, BotPerformanceSummary } from '../types';
import {
  TrendingUp,
  TrendingDown,
  Download,
  Filter,
  CheckCircle2,
  XCircle,
  Activity,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
  Flame,
  Award,
} from 'lucide-react';
import { soundFX } from '../utils/audioFX';

interface BotReportsDeckProps {
  botId: string;
  activeAsset?: string;
  tradingMode?: 'live' | 'paper';
  onOpenFullReports?: () => void;
}

const BOT_DISPLAY_NAMES: Record<string, { name: string; tag: string; icon: string; color: string }> = {
  '3_step_domination_bot': {
    name: '3-Step Dominion v3.2',
    tag: 'Live Alpha Lead',
    icon: '⚡',
    color: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
  },
  'onnx_macro_v2': {
    name: 'The ONNX Strategy (Dual-Brain)',
    tag: 'Dual-Brain Alpha',
    icon: '🧠',
    color: 'text-purple-400 border-purple-500/30 bg-purple-500/10',
  },
  'the_onnx_strategy': {
    name: 'The ONNX Strategy (Dual-Brain)',
    tag: 'Dual-Brain Alpha',
    icon: '🧠',
    color: 'text-purple-400 border-purple-500/30 bg-purple-500/10',
  },
  'dual_onnx': {
    name: 'The ONNX Strategy (Dual-Brain)',
    tag: 'Dual-Brain Alpha',
    icon: '🧠',
    color: 'text-purple-400 border-purple-500/30 bg-purple-500/10',
  },
  'macro_onnx': {
    name: 'The ONNX Strategy (Dual-Brain)',
    tag: 'Dual-Brain Alpha',
    icon: '🧠',
    color: 'text-purple-400 border-purple-500/30 bg-purple-500/10',
  },
  'dominion_2_bot': {
    name: 'Dominion 2 (Anti-Pin Scalper)',
    tag: 'Value Hunter',
    icon: '👑',
    color: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
  },
  'macro_trend_dominion': {
    name: 'Macro Trend Dominion',
    tag: '1-Hour Macro Trend',
    icon: '📈',
    color: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/10',
  },
  'ofi_sprint_scalper': {
    name: 'OFI Sprint Scalper',
    tag: '5M Velocity Scalp',
    icon: '⚡',
    color: 'text-blue-400 border-blue-500/30 bg-blue-500/10',
  },
};

export const BotReportsDeck: React.FC<BotReportsDeckProps> = ({
  botId,
  activeAsset: _activeAsset,
  tradingMode = 'live',
  onOpenFullReports,
}) => {
  const [modeFilter, setModeFilter] = useState<'all' | 'live' | 'paper'>(tradingMode);
  const [assetFilter, setAssetFilter] = useState<'all' | 'BTC' | 'ETH' | 'SOL'>('all');
  const [outcomeFilter, setOutcomeFilter] = useState<'all' | 'win' | 'loss'>('all');
  const [reports, setReports] = useState<WinLossEventReport[]>([]);
  const [botSummary, setBotSummary] = useState<BotPerformanceSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const meta = BOT_DISPLAY_NAMES[botId] || {
    name: botId.replace(/_/g, ' ').toUpperCase(),
    tag: 'Autonomous Bot',
    icon: '🤖',
    color: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/10',
  };

  const fetchReports = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const params = new URLSearchParams();
      params.set('bot_id', botId);
      params.set('limit', '50');
      if (modeFilter !== 'all') params.set('mode', modeFilter);
      if (assetFilter !== 'all') params.set('asset', assetFilter);

      const res = await fetch(`/api/reports/win-loss?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      setReports(Array.isArray(data.reports) ? data.reports : []);
      if (data.bot_summary) {
        setBotSummary(data.bot_summary);
      } else if (data.summary) {
        setBotSummary({
          bot_id: botId,
          bot_name: meta.name,
          execution_mode: modeFilter,
          total_events: data.summary.total_events,
          wins: data.summary.wins,
          losses: data.summary.losses,
          win_rate_pct: data.summary.win_rate_pct,
          total_pnl: data.summary.total_pnl,
          profit_factor: data.summary.profit_factor,
          avg_pnl_per_cycle: data.summary.avg_pnl_per_cycle,
        });
      }
    } catch (err: any) {
      console.debug('Failed fetching bot reports:', err);
      setErrorMsg('Failed loading bot reports.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [botId, modeFilter, assetFilter]);

  // Client-side outcome filter
  const displayedReports = useMemo(() => {
    if (outcomeFilter === 'all') return reports;
    return reports.filter((r) => r.outcome === outcomeFilter);
  }, [reports, outcomeFilter]);

  const winRate = botSummary?.win_rate_pct ?? 0;
  const totalPnl = botSummary?.total_pnl ?? 0;
  const isPnlPositive = totalPnl >= 0;

  return (
    <div className="space-y-4 font-mono select-none">
      {/* 1. Header with Bot Identification & Filters */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#0e1117] border border-[#262d35] rounded-xl p-3.5 shadow-sm">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[#171c22] border border-[#262d35] flex items-center justify-center text-lg shrink-0">
            {meta.icon}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xs font-bold text-white uppercase tracking-wider">{meta.name}</h2>
              <span className={`px-2 py-0.2 text-[9px] font-bold rounded-full border ${meta.color}`}>
                {meta.tag}
              </span>
            </div>
            <p className="text-[10px] text-[#8c9ba5] mt-0.5">
              Dedicated Institutional Ledger · Segregated Live & Paper Performance
            </p>
          </div>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Live vs Paper Segmented Toggle */}
          <div className="flex rounded-lg bg-[#14181f] p-0.5 border border-[#262d35]">
            {(['all', 'live', 'paper'] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => {
                  soundFX.playClickSound();
                  setModeFilter(m);
                }}
                className={`px-2.5 py-1 text-[10px] font-bold rounded transition-all cursor-pointer ${
                  modeFilter === m
                    ? m === 'live'
                      ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40 shadow-sm'
                      : m === 'paper'
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                      : 'bg-slate-700 text-white shadow-sm'
                    : 'text-[#8c9ba5] hover:text-white'
                }`}
              >
                {m === 'all' ? 'ALL MODES' : m === 'live' ? '🔴 LIVE REAL' : '🧪 PAPER SHADOW'}
              </button>
            ))}
          </div>

          {/* Asset Filter */}
          <div className="flex rounded-lg bg-[#14181f] p-0.5 border border-[#262d35]">
            {(['all', 'BTC', 'ETH', 'SOL'] as const).map((ast) => (
              <button
                key={ast}
                type="button"
                onClick={() => {
                  soundFX.playClickSound();
                  setAssetFilter(ast);
                }}
                className={`px-2 py-1 text-[10px] font-bold rounded transition-all cursor-pointer ${
                  assetFilter === ast ? 'bg-[#00bda5] text-black shadow-sm' : 'text-[#8c9ba5] hover:text-white'
                }`}
              >
                {ast}
              </button>
            ))}
          </div>

          {/* Refresh button */}
          <button
            type="button"
            onClick={fetchReports}
            disabled={isLoading}
            className="p-1.5 rounded-lg bg-[#14181f] hover:bg-[#1a2128] text-[#8c9ba5] hover:text-white border border-[#262d35] transition-all cursor-pointer disabled:opacity-50"
            title="Refresh Ledger"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-cyan-400' : ''}`} />
          </button>

          {/* Export CSV */}
          <a
            href={`/api/reports/win-loss/export.csv?bot_type=${botId}${modeFilter !== 'all' ? `&mode=${modeFilter}` : ''}`}
            download
            className="px-2 py-1 rounded-lg bg-[#14181f] hover:bg-[#1a2128] text-[#8c9ba5] hover:text-emerald-400 border border-[#262d35] text-[10px] font-bold flex items-center gap-1 transition-all"
            title="Export CSV"
          >
            <Download className="w-3 h-3" />
            <span>CSV</span>
          </a>
        </div>
      </div>

      {/* 2. KPI Summary Ribbon */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        {/* KPI 1: Win Rate */}
        <div className="p-3 rounded-xl bg-[#0e1117] border border-[#262d35]">
          <div className="text-[10px] text-[#8c9ba5] uppercase font-bold flex items-center justify-between">
            <span>Win Rate</span>
            <Award className="w-3 h-3 text-amber-400" />
          </div>
          <div className="flex items-baseline gap-2 mt-1">
            <span
              className={`text-xl font-extrabold ${
                winRate >= 60 ? 'text-[#34d399]' : winRate >= 50 ? 'text-amber-400' : 'text-[#f43f5e]'
              }`}
            >
              {winRate.toFixed(1)}%
            </span>
            <span className="text-[10px] text-slate-400">
              ({botSummary?.wins ?? 0}W / {botSummary?.losses ?? 0}L)
            </span>
          </div>
        </div>

        {/* KPI 2: Net Realized PnL */}
        <div className="p-3 rounded-xl bg-[#0e1117] border border-[#262d35]">
          <div className="text-[10px] text-[#8c9ba5] uppercase font-bold flex items-center justify-between">
            <span>Net Realized PnL</span>
            {isPnlPositive ? <TrendingUp className="w-3 h-3 text-emerald-400" /> : <TrendingDown className="w-3 h-3 text-rose-400" />}
          </div>
          <div className="flex items-baseline gap-2 mt-1">
            <span className={`text-xl font-extrabold ${isPnlPositive ? 'text-[#34d399]' : 'text-[#f43f5e]'}`}>
              {isPnlPositive ? '+' : ''}${totalPnl.toFixed(2)}
            </span>
            <span className="text-[10px] text-slate-400">USD</span>
          </div>
        </div>

        {/* KPI 3: Profit Factor */}
        <div className="p-3 rounded-xl bg-[#0e1117] border border-[#262d35]">
          <div className="text-[10px] text-[#8c9ba5] uppercase font-bold flex items-center justify-between">
            <span>Profit Factor</span>
            <Flame className="w-3 h-3 text-cyan-400" />
          </div>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-xl font-extrabold text-cyan-300">
              {(botSummary?.profit_factor ?? 1.0).toFixed(2)}x
            </span>
            <span className="text-[10px] text-slate-400">
              Avg ${(botSummary?.avg_pnl_per_cycle ?? 0).toFixed(2)}/cyc
            </span>
          </div>
        </div>

        {/* KPI 4: Settled Cycles */}
        <div className="p-3 rounded-xl bg-[#0e1117] border border-[#262d35]">
          <div className="text-[10px] text-[#8c9ba5] uppercase font-bold flex items-center justify-between">
            <span>Settled Cycles</span>
            <ShieldCheck className="w-3 h-3 text-purple-400" />
          </div>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-xl font-extrabold text-white">
              {botSummary?.total_events ?? reports.length}
            </span>
            <span className="text-[10px] text-slate-400 font-semibold uppercase">
              {modeFilter === 'all' ? 'Combined' : modeFilter}
            </span>
          </div>
        </div>
      </div>

      {/* 3. Filter Pills for Outcome */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-slate-400 font-bold uppercase flex items-center gap-1">
            <Filter className="w-3 h-3 text-slate-500" />
            Outcome:
          </span>
          {(['all', 'win', 'loss'] as const).map((out) => (
            <button
              key={out}
              type="button"
              onClick={() => setOutcomeFilter(out)}
              className={`px-2 py-0.5 rounded text-[10px] font-bold transition-all cursor-pointer ${
                outcomeFilter === out
                  ? out === 'win'
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                    : out === 'loss'
                    ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                    : 'bg-slate-700 text-white'
                  : 'text-slate-400 hover:text-white bg-[#14181f] border border-transparent'
              }`}
            >
              {out.toUpperCase()}
            </button>
          ))}
        </div>

        {onOpenFullReports && (
          <button
            type="button"
            onClick={onOpenFullReports}
            className="text-[10px] text-[#00bda5] hover:underline flex items-center gap-1 cursor-pointer font-semibold"
          >
            <span>Launch Full Inspector Modal</span>
            <ExternalLink className="w-3 h-3" />
          </button>
        )}
      </div>

      {/* 4. Ledger Table */}
      <div className="bg-[#0e1117] border border-[#262d35] rounded-xl overflow-hidden shadow-sm">
        {isLoading ? (
          <div className="p-8 text-center text-xs text-slate-400 flex flex-col items-center justify-center gap-2">
            <RefreshCw className="w-5 h-5 text-cyan-400 animate-spin" />
            <span>Synchronizing {meta.name} settlement records...</span>
          </div>
        ) : errorMsg ? (
          <div className="p-6 text-center text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20">
            {errorMsg}
          </div>
        ) : displayedReports.length === 0 ? (
          <div className="p-10 text-center space-y-2">
            <div className="w-8 h-8 rounded-full bg-slate-800/80 border border-slate-700 flex items-center justify-center mx-auto text-slate-400">
              <Activity className="w-4 h-4 text-cyan-400 animate-pulse" />
            </div>
            <div className="text-xs font-bold text-white uppercase">No Settled Cycles Recorded</div>
            <p className="text-[10px] text-[#8c9ba5] max-w-sm mx-auto">
              No settlements found for <b>{meta.name}</b> in <b>{modeFilter.toUpperCase()}</b> mode with the current filters.
              As cycles expire at :00, :15, :30, and :45, trades will automatically populate here.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[380px] overflow-y-auto">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 z-10 bg-[#12161d] border-b border-[#262d35] text-[10px] uppercase text-[#8c9ba5]">
                <tr>
                  <th className="py-2.5 px-3">Time (ET)</th>
                  <th className="py-2.5 px-3">Ticker / Asset</th>
                  <th className="py-2.5 px-3">Lane & Mode</th>
                  <th className="py-2.5 px-3">Side</th>
                  <th className="py-2.5 px-3 text-right">Entry → Settle</th>
                  <th className="py-2.5 px-3 text-center">Outcome</th>
                  <th className="py-2.5 px-3 text-right">PnL</th>
                  <th className="py-2.5 px-3">Playbook / Rationale</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1e252e]">
                {displayedReports.map((r, idx) => {
                  const isWin = r.outcome === 'win';
                  const isLive = r.execution_mode === 'live' || r.bot_type === 'live' || r.report_id?.startsWith('WLR-LIVE-');
                  const pnlVal = r.pnl ?? 0;
                  const pnlPos = pnlVal >= 0;

                  return (
                    <tr key={r.report_id || idx} className="hover:bg-[#141922] transition-colors">
                      {/* Time */}
                      <td className="py-2.5 px-3 text-slate-300 text-[11px] whitespace-nowrap">
                        {r.cycle_time || r.timestamp_utc?.slice(11, 19) || '—'}
                      </td>

                      {/* Ticker */}
                      <td className="py-2.5 px-3 whitespace-nowrap">
                        <span className="font-bold text-white text-[11px]">{r.ticker}</span>
                        {r.asset && (
                          <span className="ml-1.5 px-1.5 py-0.2 text-[9px] rounded bg-slate-800 text-slate-300 border border-slate-700">
                            {r.asset}
                          </span>
                        )}
                      </td>

                      {/* Lane & Mode */}
                      <td className="py-2.5 px-3 whitespace-nowrap">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${
                            isLive
                              ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                              : 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                          }`}
                        >
                          {isLive ? '🔴 LIVE (L1)' : '🧪 PAPER (L2)'}
                        </span>
                      </td>

                      {/* Side */}
                      <td className="py-2.5 px-3 whitespace-nowrap">
                        <span
                          className={`px-1.5 py-0.5 rounded font-bold text-[10px] ${
                            r.bot_side === 'yes'
                              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                              : 'bg-rose-500/20 text-rose-400 border border-rose-500/40'
                          }`}
                        >
                          BUY {r.bot_side?.toUpperCase()}
                        </span>
                        <span className="ml-1 text-[10px] text-slate-400">×{r.contracts ?? 1}</span>
                      </td>

                      {/* Entry -> Settle */}
                      <td className="py-2.5 px-3 text-right whitespace-nowrap text-slate-300 text-[11px]">
                        ${(r.entry_price ?? 0).toFixed(2)} → ${(r.settlement_price ?? 0).toFixed(2)}
                      </td>

                      {/* Outcome */}
                      <td className="py-2.5 px-3 text-center whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-extrabold uppercase border ${
                            isWin
                              ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                              : 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                          }`}
                        >
                          {isWin ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                          <span>{isWin ? 'WIN' : 'LOSS'}</span>
                        </span>
                      </td>

                      {/* PnL */}
                      <td className="py-2.5 px-3 text-right whitespace-nowrap">
                        <span className={`font-extrabold text-[11px] ${pnlPos ? 'text-[#34d399]' : 'text-[#f43f5e]'}`}>
                          {pnlPos ? '+' : ''}${pnlVal.toFixed(2)}
                        </span>
                        {r.roi_pct != null && (
                          <div className="text-[9px] text-slate-500">
                            {r.roi_pct >= 0 ? '+' : ''}{r.roi_pct.toFixed(0)}% ROI
                          </div>
                        )}
                      </td>

                      {/* Playbook / Rationale */}
                      <td className="py-2.5 px-3 text-[10px] text-[#8c9ba5] max-w-xs truncate" title={r.ai_rationale}>
                        {r.ai_rationale || 'Settled on cycle expiry.'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
