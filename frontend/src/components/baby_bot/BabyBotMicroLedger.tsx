/**
 * @file BabyBotMicroLedger.tsx
 * @description Dedicated Bot Micro-Report Stream & KPI Strip (Live vs Paper Segregated).
 * Displays win rate, net PnL, cycles count, and recent settlement cards.
 */

import React from 'react';
import {
  RefreshCw,
  ExternalLink,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import {
  WinLossEventReport,
  BotPerformanceSummary,
} from '../../types';
import { BotProfile } from './BabyBotProfiles';

export interface BabyBotMicroLedgerProps {
  activeProfile: BotProfile;
  reportMode: 'live' | 'paper';
  setReportMode: (mode: 'live' | 'paper') => void;
  fetchMicroReports: () => void;
  isLoadingReports: boolean;
  onOpenReports?: () => void;
  botPerformance: BotPerformanceSummary | null;
  recentReports: WinLossEventReport[];
}

export const BabyBotMicroLedger: React.FC<BabyBotMicroLedgerProps> = ({
  activeProfile,
  reportMode,
  setReportMode,
  fetchMicroReports,
  isLoadingReports,
  onOpenReports,
  botPerformance,
  recentReports,
}) => {
  return (
    <div className="border-b border-[#262d35] bg-[#0c1015] p-3 text-xs font-mono">
      {/* Header & Segregated Pill Toggle */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
            <span>✩</span>
            <span className="truncate max-w-[110px] sm:max-w-none">{activeProfile.shortName} Ledger</span>
          </span>
          {/* Live / Paper Pill Toggle */}
          <div className="flex items-center bg-[#171c22] p-0.5 rounded border border-[#262d35] text-[10px]">
            <button
              type="button"
              onClick={() => setReportMode('live')}
              className={`px-2 py-0.5 rounded font-bold transition-all cursor-pointer ${reportMode === 'live' ? 'bg-amber-500 text-black shadow-sm' : 'text-[#8c9ba5] hover:text-white'}`}
            >
              LIVE
            </button>
            <button
              type="button"
              onClick={() => setReportMode('paper')}
              className={`px-2 py-0.5 rounded font-bold transition-all cursor-pointer ${reportMode === 'paper' ? 'bg-purple-500 text-white shadow-sm' : 'text-[#8c9ba5] hover:text-white'}`}
            >
              PAPER
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={fetchMicroReports}
            disabled={isLoadingReports}
            title="Refresh ledger"
            className="text-[#8c9ba5] hover:text-white transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3 h-3 ${isLoadingReports ? 'animate-spin text-[#00bda5]' : ''}`} />
          </button>
          {onOpenReports && (
            <button
              type="button"
              onClick={onOpenReports}
              className="text-[10px] text-[#00bda5] hover:text-[#2dd4bf] hover:underline flex items-center gap-0.5 cursor-pointer"
            >
              <span>Full Ledger</span>
              <ExternalLink className="w-2.5 h-2.5" />
            </button>
          )}
        </div>
      </div>

      {/* Mini KPI Strip */}
      <div className="grid grid-cols-3 gap-1.5 mb-2 bg-[#12171e] p-2 rounded border border-[#262d35]/60">
        <div className="flex flex-col">
          <span className="text-[9px] text-[#8c9ba5] uppercase tracking-wider">Win Rate</span>
          <span className={`text-[12px] font-bold ${(botPerformance?.win_rate_pct ?? 0) >= 50 ? 'text-emerald-400' : (botPerformance?.total_events ?? 0) === 0 ? 'text-[#8c9ba5]' : 'text-rose-400'}`}>
            {botPerformance && botPerformance.total_events > 0 ? `${botPerformance.win_rate_pct.toFixed(1)}%` : '--'}
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[9px] text-[#8c9ba5] uppercase tracking-wider">Net PnL</span>
          <span className={`text-[12px] font-bold ${(botPerformance?.total_pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {botPerformance && botPerformance.total_events > 0 ? `${botPerformance.total_pnl >= 0 ? '+' : ''}$${botPerformance.total_pnl.toFixed(2)}` : '--'}
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[9px] text-[#8c9ba5] uppercase tracking-wider">Cycles</span>
          <span className="text-[12px] font-bold text-white">
            {botPerformance && botPerformance.total_events > 0 ? `${botPerformance.wins}W / ${botPerformance.losses}L` : '--'}
          </span>
        </div>
      </div>

      {/* Recent Settlements List */}
      {recentReports.length > 0 ? (
        <div className="space-y-1">
          {recentReports.map((r, idx) => {
            const isWin = r.outcome.toLowerCase() === 'win';
            const rawPnl = r.pnl !== undefined ? r.pnl : r.net_pnl;
            const pnlNum = typeof rawPnl === 'number' ? rawPnl : parseFloat(String(rawPnl || '0'));
            const displaySide = r.bot_side || r.side || 'YES';
            return (
              <div
                key={r.report_id || idx}
                className={`flex items-center justify-between p-1.5 rounded border text-[10px] ${isWin ? 'bg-emerald-950/20 border-emerald-500/20 text-emerald-300' : 'bg-rose-950/20 border-rose-500/20 text-rose-300'}`}
              >
                <div className="flex items-center gap-1.5 truncate max-w-[65%]">
                  {isWin ? (
                    <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
                  ) : (
                    <XCircle className="w-3 h-3 text-rose-400 shrink-0" />
                  )}
                  <span className="truncate text-white font-medium">
                    {r.ticker.replace('KXBTC15M-', '').replace('KXETH15M-', 'ETH-').replace('KXSOL15M-', 'SOL-')}
                  </span>
                  <span className="text-[8px] text-[#8c9ba5] uppercase px-1 py-0.2 bg-[#171c22] rounded border border-[#262d35]">
                    {displaySide}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0 font-mono">
                  <span className={`font-bold ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {pnlNum >= 0 ? `+$${pnlNum.toFixed(2)}` : `-$${Math.abs(pnlNum).toFixed(2)}`}
                  </span>
                  <span className="text-[9px] text-[#8c9ba5]">
                    {r.timestamp_utc ? r.timestamp_utc.slice(11, 16) : ''}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="py-2 text-center text-[#8c9ba5] text-[10px] bg-[#12171e]/50 rounded border border-[#262d35]/40">
          <span>No {reportMode.toUpperCase()} settlements for {activeProfile.shortName}</span>
        </div>
      )}
    </div>
  );
};
