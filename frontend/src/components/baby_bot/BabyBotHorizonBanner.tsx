/**
 * @file BabyBotHorizonBanner.tsx
 * @description Event Horizon (Target Strike K vs CME Spot S_t), Diff metrics, 5M/15M Countdown and CLOB Inside Touch for BabyBotConsole.
 */

import React from 'react';
import { MarketState } from '../../types';

interface BabyBotHorizonBannerProps {
  market: MarketState;
  is5m: boolean;
  diffColor: string;
  diffBg: string;
  diffVal: number;
  isDiffPositive: boolean;
  phase5m: { label: string; color: string; bar: string } | null;
  remSecs: number;
  progressPct: number;
  yesProb: number;
  noProb: number;
}

export const BabyBotHorizonBanner: React.FC<BabyBotHorizonBannerProps> = ({
  market,
  is5m,
  diffColor,
  diffBg,
  diffVal,
  isDiffPositive,
  phase5m,
  remSecs,
  progressPct,
  yesProb,
  noProb,
}) => {
  return (
    <>
      {/* Target Contract Banner */}
      <div className="px-4 py-1.5 bg-[#12161a] border-b border-[#262d35] flex items-center justify-between text-[11px] font-mono text-[#8c9ba5]">
        <div className="flex items-center gap-2">
          <span className="text-white font-bold">{market.ticker || 'KXBTC15M-CURRENT'}</span>
          <span
            className={`px-1.5 py-0.2 rounded text-[9px] font-bold uppercase ${
              is5m
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                : 'bg-teal-500/20 text-teal-300 border border-teal-500/40'
            }`}
          >
            {is5m ? '5M SPRINT' : '15M CYCLE'}
          </span>
        </div>
        <span className="text-emerald-400">TAPE: OK (5Hz BRTI)</span>
      </div>

      {/* 3. Live Event Horizon: Strike K vs CME Spot S_t */}
      <div className="p-4 bg-[#12161a] border-b border-[#262d35] space-y-3">
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="text-left">
            <div className="text-[10px] uppercase font-mono tracking-wider text-[#8c9ba5]">TO BEAT (K)</div>
            <div className="text-lg font-bold font-mono text-white tracking-tight">
              {market.target_strike_str || '$88,450.00'}
            </div>
            <div className="text-[10px] text-[#8c9ba5]">{market.target_time_str || '10:00 AM ET'}</div>
          </div>

          <div className="text-center">
            <div className="text-[10px] uppercase font-mono tracking-wider text-[#8c9ba5]">NOW (SPOT)</div>
            <div className={`text-lg font-bold font-mono tracking-tight ${diffColor}`}>
              {market.current_btc_price_str || '$88,482.50'}
            </div>
            <div className="text-[10px] text-emerald-400 flex items-center justify-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>CF Benchmarks</span>
            </div>
          </div>

          <div className="text-right">
            <div className="text-[10px] uppercase font-mono tracking-wider text-[#8c9ba5]">SPOT DIFF</div>
            <div className={`text-sm font-bold font-mono tracking-tight ${diffColor}`}>
              {isDiffPositive ? '▲' : '▼'}{' '}
              {market.diff_str
                ? market.diff_str.split(' ')[0]
                : `${isDiffPositive ? '+' : ''}$${Math.abs(diffVal).toFixed(2)}`}
            </div>
            <span
              className={`inline-block px-1.5 py-0.2 rounded text-[10px] font-mono font-bold border mt-0.5 ${diffBg}`}
            >
              {isDiffPositive ? '+' : ''}
              {market.diff_pct?.toFixed(3) ?? '0.037'}%
            </span>
          </div>
        </div>

        {/* Dynamic 5M vs 15M Progress Bar */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[11px] font-mono">
            <span className="text-[#8c9ba5] flex items-center gap-1.5">
              <span>{is5m ? '5M Velocity Window' : '15M Settlement Countdown'}:</span>
              {phase5m && <span className={`font-semibold ${phase5m.color}`}>{phase5m.label}</span>}
            </span>
            <span className="font-bold text-white tracking-wider">
              {market.expiry_countdown_str || '03:02'} ({remSecs}s)
            </span>
          </div>
          <div className="w-full h-2 bg-[#171c22] rounded-full overflow-hidden border border-[#262d35] relative">
            <div
              className={`h-full transition-all duration-300 ${
                is5m ? phase5m?.bar || 'bg-emerald-500' : 'bg-gradient-to-r from-teal-500 to-emerald-400'
              }`}
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      </div>

      {/* 4. CLOB Inside Touch & Implied Probability */}
      <div className="px-4 py-2.5 bg-[#0f1319] border-b border-[#262d35] space-y-2">
        <div className="flex items-center justify-between text-xs font-mono">
          <div className="flex items-center gap-2">
            <span className="text-[#10b981] font-bold">YES</span>
            <span className="text-white font-extrabold">{market.yes_cents_str || '58¢'}</span>
            <span className="text-[10px] text-[#8c9ba5]">(9 cts)</span>
          </div>
          <div className="text-[10px] text-[#8c9ba5] font-semibold uppercase tracking-wider">
            CLOB INSIDE TOUCH
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-[#8c9ba5]">(14 cts)</span>
            <span className="text-white font-extrabold">{market.no_cents_str || '44¢'}</span>
            <span className="text-[#f43f5e] font-bold">NO</span>
          </div>
        </div>

        {/* Probability Split Bar */}
        <div className="w-full h-3 bg-[#171c22] rounded overflow-hidden flex text-[9px] font-mono font-bold leading-3">
          <div
            className="bg-[#10b981] text-black pl-1.5 flex items-center transition-all duration-300"
            style={{ width: `${yesProb}%` }}
          >
            YES {yesProb.toFixed(0)}%
          </div>
          <div
            className="bg-[#f43f5e] text-white pr-1.5 flex items-center justify-end transition-all duration-300"
            style={{ width: `${noProb}%` }}
          >
            {noProb.toFixed(0)}% NO
          </div>
        </div>
      </div>
    </>
  );
};
