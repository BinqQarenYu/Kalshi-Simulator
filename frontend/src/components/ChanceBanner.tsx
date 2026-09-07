import React from 'react';
import { MarketState } from '../types';
import { ArrowDownUp } from 'lucide-react';

interface ChanceBannerProps {
  market: MarketState;
  activeTab: 'trade_up' | 'trade_down' | 'graph' | 'orderbook' | 'ai';
  tradingMode?: 'paper' | 'live';
  onSelectTab: (tab: 'trade_up' | 'trade_down' | 'graph' | 'orderbook' | 'ai') => void;
  onQuickTrade: (side: 'yes' | 'no') => void;
}

export const ChanceBanner: React.FC<ChanceBannerProps> = React.memo(({
  market,
  activeTab,
  tradingMode = 'paper',
  onSelectTab,
  onQuickTrade,
}) => {
  const isLive = tradingMode === 'live';
  return (
    <div className="bg-[#111620] border-b border-[#21262d] px-4 py-3 sm:px-6">
      {/* Probability & Quick Action Pills Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-3">
        <div className="flex items-center gap-6">
          <div>
            <span className="text-xs text-[#8b949e]">Target Price: </span>
            <span className="text-sm font-bold text-white">{market.target_strike_str}</span>
          </div>

          <div className="flex items-baseline gap-2">
            <span className="text-xl sm:text-2xl font-black text-white">
              {(market?.market_chance_pct ?? 0).toFixed(1)}%
            </span>
            <span className="text-xs font-bold text-[#ff4d4d] flex items-center">
              ▼ 45.1
            </span>
          </div>
        </div>

        {/* Quick Action Pill Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => onQuickTrade('yes')}
            className="px-4 py-1.5 rounded-full text-xs font-extrabold bg-[#00d084]/15 hover:bg-[#00d084]/25 text-[#00d084] border border-[#00d084]/40 transition-all shadow-sm active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00d084]"
          >
            Up {market.yes_cents_str}
          </button>
          <button
            onClick={() => onQuickTrade('no')}
            className="px-4 py-1.5 rounded-full text-xs font-extrabold bg-[#ff4d4d]/15 hover:bg-[#ff4d4d]/25 text-[#ff4d4d] border border-[#ff4d4d]/40 transition-all shadow-sm active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ff4d4d]"
          >
            Down {market.no_cents_str}
          </button>
          <button
            className="p-1 text-[#8b949e] hover:text-white transition-colors rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#8b949e]"
            title="Sort or filter options"
            aria-label="Sort or filter options"
          >
            <ArrowDownUp className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Sub Tab Navigation */}
      <div className="flex items-center gap-6 text-xs font-semibold border-t border-[#21262d] pt-2">
        <button
          onClick={() => onSelectTab('orderbook')}
          className={`pb-1 border-b-2 transition-all rounded-sm flex items-center gap-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#f7931a] ${
            activeTab === 'orderbook'
              ? 'border-[#f7931a] text-[#f7931a] font-bold'
              : 'border-transparent text-[#8b949e] hover:text-white'
          }`}
        >
          <span>📊 Level-2 CLOB Ladder</span>
        </button>
        <button
          onClick={() => onSelectTab('tape' as any)}
          className={`pb-1 border-b-2 transition-all rounded-sm flex items-center gap-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00d084] ${
            activeTab === ('tape' as any)
              ? 'border-[#00d084] text-[#00d084] font-bold'
              : 'border-transparent text-[#8b949e] hover:text-white'
          }`}
        >
          <span>⚡ Live Trade Tape</span>
        </button>
        <button
          onClick={() => onSelectTab('positions' as any)}
          className={`pb-1 border-b-2 transition-all rounded-sm flex items-center gap-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#3b82f6] ${
            activeTab === ('positions' as any)
              ? 'border-[#3b82f6] text-[#3b82f6] font-bold'
              : 'border-transparent text-[#8b949e] hover:text-white'
          }`}
        >
          <span>💼 Active Positions & Fills</span>
        </button>
      </div>
    </div>
  );
});
