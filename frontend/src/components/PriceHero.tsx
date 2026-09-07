import React, { useState } from 'react';
import { MarketState } from '../types';
import { Info, Hourglass } from 'lucide-react';

interface PriceHeroProps {
  market: MarketState;
}

export const PriceHero: React.FC<PriceHeroProps> = React.memo(({ market }) => {
  const [viewMode, setViewMode] = useState<'$' | '%'>('$');

  const isUp = market.diff >= 0;
  const deltaColor = isUp ? 'text-[#00d084]' : 'text-[#ff4d4d]';
  const decimals = market.active_asset_decimals ?? 2;
  const diffVal = market?.diff ?? 0;
  const diffPctVal = market?.diff_pct ?? 0;
  const formattedDiff = market.diff_str
    ? market.diff_str.split(' ')[0]
    : `${isUp ? '+' : ''}$${Math.abs(diffVal).toFixed(decimals)}`;
  const formattedPct = `${isUp ? '+' : ''}${Math.abs(diffPctVal) < 0.1 ? diffPctVal.toFixed(3) : diffPctVal.toFixed(2)}%`;

  return (
    <div className="bg-[#111620] border-b border-[#21262d] px-4 py-4 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Left: TO BEAT & NOW */}
        <div className="flex items-center gap-8 sm:gap-12">
          {/* TO BEAT Strike */}
          <div>
            <div className="text-[11px] font-bold uppercase tracking-wider text-[#8b949e]">
              TO BEAT
            </div>
            <div className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              {market.target_strike_str}
            </div>
            <div className="text-xs text-[#8b949e] font-medium">{market.target_time_str || 'Expiry Target'}</div>
          </div>

          {/* NOW Spot Price */}
          <div>
            <div className="flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider text-[#8b949e]">
              <span>NOW {market.active_asset || 'BTC'}</span>
              <Info className="h-3 w-3 text-[#8b949e]" />
            </div>
            <div className={`text-2xl sm:text-3xl font-extrabold tracking-tight ${deltaColor}`}>
              {market.current_btc_price_str}
            </div>
            <div className={`text-xs font-semibold flex items-center gap-1 ${deltaColor}`}>
              {viewMode === '$' ? (
                <>
                  <span className="font-bold">{formattedDiff}</span>
                  <span className="opacity-75">({formattedPct})</span>
                </>
              ) : (
                <>
                  <span className="font-bold">{formattedPct}</span>
                  <span className="opacity-75">({formattedDiff})</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Right: Currency Toggle + Brand + Expiry Countdown */}
        <div className="flex items-center gap-4">
          {/* $ / % Toggle */}
          <div
            role="group"
            aria-label="Price change display mode"
            className="flex items-center bg-[#161b22] border border-[#30363d] rounded-lg p-0.5"
          >
            <button
              type="button"
              onClick={() => setViewMode('$')}
              aria-label="Display price change in dollars"
              aria-pressed={viewMode === '$'}
              className={`px-2.5 py-0.5 text-xs font-bold rounded transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00d084] ${
                viewMode === '$' ? 'bg-[#30363d] text-white' : 'text-[#8b949e] hover:text-white'
              }`}
            >
              $
            </button>
            <button
              type="button"
              onClick={() => setViewMode('%')}
              aria-label="Display price change in percent"
              aria-pressed={viewMode === '%'}
              className={`px-2.5 py-0.5 text-xs font-bold rounded transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00d084] ${
                viewMode === '%' ? 'bg-[#30363d] text-white' : 'text-[#8b949e] hover:text-white'
              }`}
            >
              %
            </button>
          </div>

          {/* Kalshi Badge */}
          <span className="text-sm font-bold text-[#00d084] tracking-wider uppercase hidden sm:inline">
            Kalshi Sim
          </span>

          {/* Expiry Countdown Timer Badge */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border shadow-inner ${
            market.timeframe === '5m'
              ? 'bg-[#f59e0b]/15 border-[#f59e0b]/40'
              : 'bg-[#f59e0b]/10 border-[#f59e0b]/30'
          }`}>
            <div className="flex flex-col items-end">
              <span className="text-xl sm:text-2xl font-mono font-extrabold text-[#f59e0b] tracking-wider leading-none">
                {market.expiry_countdown_str}
              </span>
              {market.timeframe === '5m' && (
                <span className="text-[9px] font-mono font-bold text-amber-400/90 uppercase tracking-widest mt-0.5">
                  5M SPRINT (300s)
                </span>
              )}
            </div>
            <Hourglass className="h-4 w-4 text-[#f59e0b] animate-spin" style={{ animationDuration: market.timeframe === '5m' ? '3s' : '6s' }} />
          </div>
        </div>
      </div>
    </div>
  );
});
