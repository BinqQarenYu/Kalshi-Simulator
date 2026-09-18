import React from 'react';
import { Award, Bot, Calendar, ExternalLink, Shield, TrendingDown, TrendingUp } from 'lucide-react';
import { TraderCategory, getTraderBadge, WinLossReportsModal } from '../WinLossReportsModal';
import { soundFX } from '../../utils/audioFX';

export interface JournalExecutionItem {
  id: string;
  time: string;
  bot: string;
  category: TraderCategory;
  badge: any;
  tf: string;
  asset: string;
  strike: string;
  spotPrice?: string;
  side: string;
  price: string;
  outcome: string;
  pnl: string;
  pnlNum: number;
  tag: string;
  isLive: boolean;
  isToday: boolean;
  executionMode: string;
  rawReport: any;
}

export interface JournalStats {
  filtered: { total: number; wins: number; losses: number; winRate: number; netPnl: number };
  today: { total: number; wins: number; losses: number; winRate: number; netPnl: number };
  live: { total: number; wins: number; losses: number; winRate: number; netPnl: number };
  botStatsMap: Record<TraderCategory, { count: number; wins: number; pnl: number }>;
}

interface TradeJournalViewProps {
  journalSubNav: 'trades' | 'settlements' | 'reports';
  journalDateScope: 'all' | 'today';
  setJournalDateScope: (val: 'all' | 'today') => void;
  journalAssetFilter: 'ALL' | 'BTC' | 'ETH' | 'SOL' | 'DOGE';
  setJournalAssetFilter: (val: 'ALL' | 'BTC' | 'ETH' | 'SOL' | 'DOGE') => void;
  journalTimeframeFilter: 'ALL' | '5M' | '15M';
  setJournalTimeframeFilter: (val: 'ALL' | '5M' | '15M') => void;
  journalBotFilter: TraderCategory;
  setJournalBotFilter: (val: TraderCategory) => void;
  journalStats: JournalStats;
  filteredExecutions: JournalExecutionItem[];
  isWinLossModalOpen: boolean;
  setIsWinLossModalOpen: (val: boolean) => void;
}

export const TradeJournalView: React.FC<TradeJournalViewProps> = ({
  journalSubNav,
  journalDateScope,
  setJournalDateScope,
  journalAssetFilter,
  setJournalAssetFilter,
  journalTimeframeFilter,
  setJournalTimeframeFilter,
  journalBotFilter,
  setJournalBotFilter,
  journalStats,
  filteredExecutions,
  isWinLossModalOpen,
  setIsWinLossModalOpen,
}) => {
  return (
    <div className="space-y-6">
      {/* Journal Sub-Header with Date Scope, Asset, Timeframe Filters, and Full Modal Trigger */}
      <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-4 flex flex-wrap items-center justify-between gap-3 font-mono">
        <div className="flex flex-wrap items-center gap-4">
          {/* Date Scope Filter */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase font-bold text-[#8c9ba5] flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5 text-emerald-400" />
              Scope:
            </span>
            <div className="flex items-center gap-1 bg-[#171c22] p-0.5 rounded-lg border border-[#262d35]">
              <button
                onClick={() => {
                  soundFX.playClickSound();
                  setJournalDateScope('today');
                }}
                className={`px-2.5 py-1 rounded text-[11px] font-bold transition flex items-center gap-1.5 ${
                  (journalSubNav === 'trades' ? journalDateScope !== 'all' : journalDateScope === 'today')
                    ? 'bg-emerald-500 text-black shadow-sm font-extrabold'
                    : 'text-[#8c9ba5] hover:text-white'
                }`}
              >
                <span>📅 Today's Report</span>
              </button>
              <button
                onClick={() => {
                  soundFX.playClickSound();
                  setJournalDateScope('all');
                }}
                className={`px-2.5 py-1 rounded text-[11px] font-bold transition flex items-center gap-1.5 ${
                  (journalSubNav === 'trades' ? journalDateScope === 'all' : journalDateScope !== 'today')
                    ? 'bg-[#1e293b] text-white shadow-sm font-extrabold'
                    : 'text-[#8c9ba5] hover:text-white'
                }`}
              >
                <span>🌐 All History</span>
              </button>
            </div>
          </div>

          {/* Asset Filter */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase font-bold text-[#8c9ba5]">Asset:</span>
            <div className="flex items-center gap-1 bg-[#171c22] p-0.5 rounded-lg border border-[#262d35]">
              {(['ALL', 'BTC', 'ETH', 'SOL', 'DOGE'] as const).map((a) => (
                <button
                  key={a}
                  onClick={() => {
                    soundFX.playClickSound();
                    setJournalAssetFilter(a);
                  }}
                  className={`px-2.5 py-1 rounded text-[11px] font-bold transition ${
                    journalAssetFilter === a
                      ? 'bg-[#00bda5] text-black shadow-sm font-extrabold'
                      : 'text-[#8c9ba5] hover:text-white'
                  }`}
                >
                  {a}
                </button>
              ))}
            </div>
          </div>

          {/* Timeframe Filter */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase font-bold text-[#8c9ba5]">Cycle:</span>
            <div className="flex items-center gap-1 bg-[#171c22] p-0.5 rounded-lg border border-[#262d35]">
              {(['ALL', '5M', '15M'] as const).map((tf) => (
                <button
                  key={tf}
                  onClick={() => {
                    soundFX.playClickSound();
                    setJournalTimeframeFilter(tf);
                  }}
                  className={`px-2.5 py-1 rounded text-[11px] font-bold transition ${
                    journalTimeframeFilter === tf
                      ? 'bg-[#d9a752] text-black shadow-sm font-extrabold'
                      : 'text-[#8c9ba5] hover:text-white'
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Modal Trigger */}
        <button
          onClick={() => setIsWinLossModalOpen(true)}
          className="px-3.5 py-1.5 rounded-lg bg-[#00bda5]/15 text-[#2dd4bf] hover:bg-[#00bda5]/25 border border-[#00bda5]/30 text-xs font-bold flex items-center gap-1.5 transition cursor-pointer shadow-sm"
        >
          <span>📋 Full 15M Win/Loss Audit Modal</span>
          <ExternalLink className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Institutional KPI Summary Header Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 font-mono">
        {/* 1. Filtered Win Rate */}
        <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#8c9ba5] text-xs">
            <span className="uppercase font-bold">Filtered Win Rate</span>
            <Award className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-white">
              {journalStats.filtered.winRate.toFixed(1)}%
            </span>
            <span className="text-xs text-[#8c9ba5]">
              ({journalStats.filtered.wins}W / {journalStats.filtered.losses}L)
            </span>
          </div>
          <div className="mt-2 w-full bg-[#1e242b] h-1.5 rounded-full overflow-hidden">
            <div
              className="bg-emerald-400 h-full rounded-full transition-all duration-500"
              style={{ width: `${Math.min(100, journalStats.filtered.winRate)}%` }}
            />
          </div>
        </div>

        {/* 2. Filtered Realized P&L */}
        <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#8c9ba5] text-xs">
            <span className="uppercase font-bold">Filtered Net P&L</span>
            {journalStats.filtered.netPnl >= 0 ? (
              <TrendingUp className="w-4 h-4 text-emerald-400" />
            ) : (
              <TrendingDown className="w-4 h-4 text-rose-400" />
            )}
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className={`text-2xl font-black ${
              journalStats.filtered.netPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
            }`}>
              {journalStats.filtered.netPnl >= 0 ? '+' : '−'}$
              {Math.abs(journalStats.filtered.netPnl).toFixed(2)}
            </span>
            <span className="text-xs text-[#8c9ba5]">
              ({journalStats.filtered.total} trades)
            </span>
          </div>
          <div className="mt-2 text-[10px] text-[#8c9ba5] flex items-center justify-between">
            <span>1 contract micro-sizing</span>
            <span className="text-emerald-400">$0.48 entry cap</span>
          </div>
        </div>

        {/* 3. Today's Report Card (Interactive) */}
        <button
          type="button"
          onClick={() => {
            soundFX.playClickSound();
            setJournalDateScope('today');
          }}
          aria-label="Filter journal by Today's Trades"
          aria-pressed={journalSubNav === 'trades' ? journalDateScope !== 'all' : journalDateScope === 'today'}
          className={`border rounded-xl p-4 flex flex-col justify-between transition cursor-pointer text-left w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 ${
            (journalSubNav === 'trades' ? journalDateScope !== 'all' : journalDateScope === 'today')
              ? 'bg-emerald-950/20 border-emerald-500/50 shadow-md shadow-emerald-950/30'
              : 'bg-[#12161a] border-[#262d35] hover:border-emerald-500/30'
          }`}
          title="Click to view Today's Trades exclusively"
        >
          <div className="flex items-center justify-between text-xs">
            <span className="uppercase font-bold text-emerald-300 flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5" />
              📅 Today's Report
            </span>
            {(journalSubNav === 'trades' ? journalDateScope !== 'all' : journalDateScope === 'today') && (
              <span className="text-[10px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded border border-emerald-500/40 font-bold">
                ACTIVE
              </span>
            )}
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className={`text-2xl font-black ${
              journalStats.today.netPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
            }`}>
              {journalStats.today.netPnl >= 0 ? '+' : '−'}$
              {Math.abs(journalStats.today.netPnl).toFixed(2)}
            </span>
            <span className="text-xs text-[#8c9ba5]">
              ({journalStats.today.winRate.toFixed(0)}% WR)
            </span>
          </div>
          <div className="mt-2 text-[10px] text-[#8c9ba5] flex items-center justify-between">
            <span>{journalStats.today.total} trades today (ET)</span>
            <span className="text-emerald-300 underline text-[10px]">Filter Today &rsaquo;</span>
          </div>
        </button>

        {/* 4. Total Live Report Card (Interactive) */}
        <button
          type="button"
          onClick={() => {
            soundFX.playClickSound();
            setJournalBotFilter(journalBotFilter === 'live' ? 'all' : 'live');
          }}
          aria-label="Filter journal by Total Live Execution Report"
          aria-pressed={journalBotFilter === 'live'}
          className={`border rounded-xl p-4 flex flex-col justify-between transition cursor-pointer text-left w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 ${
            journalBotFilter === 'live'
              ? 'bg-rose-950/20 border-rose-500/50 shadow-md shadow-rose-950/30'
              : 'bg-[#12161a] border-[#262d35] hover:border-rose-500/30'
          }`}
          title="Click to toggle Total Live Execution Report"
        >
          <div className="flex items-center justify-between text-xs">
            <span className="uppercase font-bold text-rose-300 flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5" />
              🔴 Total Live Report
            </span>
            {journalBotFilter === 'live' && (
              <span className="text-[10px] bg-rose-500/20 text-rose-300 px-1.5 py-0.5 rounded border border-rose-500/40 font-bold">
                FILTERED
              </span>
            )}
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className={`text-2xl font-black ${
              journalStats.live.netPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
            }`}>
              {journalStats.live.netPnl >= 0 ? '+' : '−'}$
              {Math.abs(journalStats.live.netPnl).toFixed(2)}
            </span>
            <span className="text-xs text-[#8c9ba5]">
              ({journalStats.live.winRate.toFixed(0)}% WR)
            </span>
          </div>
          <div className="mt-2 text-[10px] text-[#8c9ba5] flex items-center justify-between">
            <span>{journalStats.live.total} real Kalshi fills</span>
            <span className="text-rose-300">$0.00 Maker fee</span>
          </div>
        </button>
      </div>

      {/* "Who Traded" Strategy Performance Breakdown Bar */}
      <div className="p-3 bg-[#12161a] rounded-xl border border-[#262d35] space-y-2 font-mono">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-[#00bda5]" />
            <span className="text-xs font-bold uppercase tracking-wider text-white">
              Who Traded — Bot & Strategy Breakdown
            </span>
          </div>
          <span className="text-[10px] text-[#8c9ba5]">
            Click strategy to filter executions
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {(['all', '3_step_dom', 'macro_onnx', 'dominion_2', 'macro_trend', 'onnx_ml', 'live'] as TraderCategory[]).map((cat) => {
            const badge = getTraderBadge(cat);
            const st = journalStats.botStatsMap[cat] || { count: 0, wins: 0, pnl: 0 };
            const isSelected = journalBotFilter === cat;
            const wr = st.count > 0 ? ((st.wins / st.count) * 100).toFixed(0) : '0';
            return (
              <button
                key={cat}
                onClick={() => {
                  soundFX.playClickSound();
                  setJournalBotFilter(cat);
                }}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition flex items-center gap-2 border cursor-pointer ${
                  isSelected
                    ? 'bg-[#00bda5] text-black border-[#00bda5] shadow-sm font-extrabold'
                    : 'bg-[#171c22] text-[#8c9ba5] hover:text-white border-[#262d35]'
                }`}
              >
                <span>{cat === 'all' ? '🌐 ALL' : `${badge.icon} ${badge.short}`}</span>
                <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                  isSelected ? 'bg-black/20 text-black' : 'bg-[#12161a] text-[#2dd4bf]'
                }`}>
                  {st.count}
                </span>
                {st.count > 0 && (
                  <span className={`text-[10px] font-mono ${
                    isSelected
                      ? 'text-black font-extrabold'
                      : st.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  }`}>
                    {st.pnl >= 0 ? '+' : '−'}${Math.abs(st.pnl).toFixed(2)} ({wr}%)
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Journal Table Card */}
      <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold uppercase tracking-wider text-white flex items-center gap-2">
            <span>
              {journalSubNav === 'settlements'
                ? 'Historical Contract Settlements Ledger'
                : journalSubNav === 'reports'
                ? '15-Minute Event Outcome Reports'
                : "Today's Trade Executions Ledger"}
            </span>
            {journalBotFilter !== 'all' && (
              <span className="text-[10px] px-2 py-0.5 rounded bg-[#00bda5]/20 text-[#2dd4bf] border border-[#00bda5]/40 font-mono font-bold">
                Filter: {getTraderBadge(journalBotFilter).short}
              </span>
            )}
          </h2>
          <div className="text-xs font-mono text-[#8c9ba5]">
            Showing {filteredExecutions.length} records
          </div>
        </div>

        <div className="overflow-x-auto rounded-lg border border-[#262d35]">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-[#171c22] text-[10px] uppercase text-[#8c9ba5] border-b border-[#262d35]">
              <tr>
                <th className="py-2.5 px-4">Record ID</th>
                <th className="py-2.5 px-4">Time (ET)</th>
                <th className="py-2.5 px-4">Who Traded (Strategy)</th>
                <th className="py-2.5 px-4">Mode</th>
                <th className="py-2.5 px-4">Cycle</th>
                <th className="py-2.5 px-4">Asset</th>
                <th className="py-2.5 px-4">Strike</th>
                {journalSubNav === 'settlements' && <th className="py-2.5 px-4">Spot Settlement</th>}
                <th className="py-2.5 px-4">Side</th>
                <th className="py-2.5 px-4 text-right">Entry</th>
                <th className="py-2.5 px-4 text-center">Outcome</th>
                <th className="py-2.5 px-4 text-right">PnL</th>
                <th className="py-2.5 px-4">Tag</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1f262d]">
              {filteredExecutions.map((t, idx) => (
                <tr key={idx} className={idx % 2 === 0 ? 'bg-[#171c22]/40' : 'bg-[#13171c]/40'}>
                  <td className="py-2 px-4 text-[#8c9ba5] font-mono">{t.id}</td>
                  <td className="py-2 px-4 text-[#8c9ba5]">{t.time}</td>
                  <td className="py-2 px-4">
                    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-bold border ${t.badge.color}`}>
                      <span>{t.badge.icon}</span>
                      <span>{t.badge.short}</span>
                    </span>
                  </td>
                  <td className="py-2 px-4">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-extrabold ${
                      t.isLive
                        ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                        : 'bg-slate-700/40 text-slate-300 border border-slate-600/30'
                    }`}>
                      {t.isLive ? 'LIVE' : 'PAPER'}
                    </span>
                  </td>
                  <td className="py-2 px-4">
                    <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                      t.tf === '5M' ? 'bg-[#d9a752]/20 text-[#d9a752]' : 'bg-[#00bda5]/20 text-[#2dd4bf]'
                    }`}>
                      {t.tf}
                    </span>
                  </td>
                  <td className="py-2 px-4 font-bold text-white">{t.asset}</td>
                  <td className="py-2 px-4 text-[#8c9ba5]">{t.strike}</td>
                  {journalSubNav === 'settlements' && (
                    <td className="py-2 px-4 text-white font-mono">{t.spotPrice || 'Pending'}</td>
                  )}
                  <td className="py-2 px-4 font-bold">
                    <span className={t.side === 'YES' ? 'text-[#34d399]' : 'text-[#f43f5e]'}>
                      {t.side}
                    </span>
                  </td>
                  <td className="py-2 px-4 text-right text-white">{t.price}</td>
                  <td className="py-2 px-4 text-center">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      t.outcome === 'WIN' ? 'bg-[#34d399]/15 text-[#34d399]' : 'bg-[#f43f5e]/15 text-[#f43f5e]'
                    }`}>
                      {t.outcome}
                    </span>
                  </td>
                  <td className={`py-2 px-4 text-right font-bold ${
                    t.outcome === 'WIN' ? 'text-[#34d399]' : 'text-[#f43f5e]'
                  }`}>
                    {t.pnl}
                  </td>
                  <td className="py-2 px-4">
                    <span className="px-2 py-0.5 rounded text-[10px] bg-[#1a2128] text-[#8c9ba5] border border-[#262d35]">
                      {t.tag}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Full WinLossReportsModal */}
      <WinLossReportsModal
        isOpen={isWinLossModalOpen}
        onClose={() => setIsWinLossModalOpen(false)}
      />
    </div>
  );
};
