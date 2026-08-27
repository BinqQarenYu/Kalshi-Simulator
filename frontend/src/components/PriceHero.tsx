import React, { useState } from 'react';
import { MarketState } from '../types';
import { Info, Hourglass } from 'lucide-react';

interface PriceHeroProps {
  market: MarketState;
}

export const PriceHero: React.FC<PriceHeroProps> = ({ market }) => {
  const [viewMode, setViewMode] = useState<'$' | '%'>('$');

  const isUp = market.diff >= 0;
  const deltaColor = isUp ? 'text-[#00d084]' : 'text-[#ff4d4d]';

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
            <div className="text-xs text-[#8b949e] font-medium">10:00am ET</div>
          </div>

          {/* NOW Spot BTC Price */}
          <div>
            <div className="flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider text-[#8b949e]">
              <span>NOW</span>
              <Info className="h-3 w-3 text-[#8b949e]" />
            </div>
            <div className={`text-2xl sm:text-3xl font-extrabold tracking-tight ${deltaColor}`}>
              {market.current_btc_price_str}
            </div>
            <div className={`text-xs font-semibold flex items-center gap-1 ${deltaColor}`}>
              <span>{isUp ? '+' : ''}${market.diff.toFixed(2)}</span>
              <span>({isUp ? '+' : ''}{market.diff_pct.toFixed(2)}%)</span>
            </div>
          </div>
        </div>

        {/* Right: Currency Toggle + Brand + Expiry Countdown */}
        <div className="flex items-center gap-4">
          {/* $ / % Toggle */}
          <div className="flex items-center bg-[#161b22] border border-[#30363d] rounded-lg p-0.5">
            <button
              onClick={() => setViewMode('$')}
              className={`px-2 py-0.5 text-xs font-bold rounded ${
                viewMode === '$' ? 'bg-[#30363d] text-white' : 'text-[#8b949e] hover:text-white'
              }`}
            >
              $
            </button>
            <button
              onClick={() => setViewMode('%')}
              className={`px-2 py-0.5 text-xs font-bold rounded ${
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

          {/* Expiry Countdown Timer Badge (matching the image) */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#f59e0b]/10 border border-[#f59e0b]/30 shadow-inner">
            <span className="text-xl sm:text-2xl font-mono font-extrabold text-[#f59e0b] tracking-wider">
              {market.expiry_countdown_str}
            </span>
            <Hourglass className="h-4 w-4 text-[#f59e0b] animate-spin" style={{ animationDuration: '6s' }} />
          </div>
        </div>
      </div>
    </div>
  );
};
