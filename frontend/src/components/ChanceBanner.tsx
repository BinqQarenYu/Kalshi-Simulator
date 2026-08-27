import React from 'react';
import { MarketState } from '../types';
import { ArrowDownUp } from 'lucide-react';

interface ChanceBannerProps {
  market: MarketState;
  activeTab: 'trade_up' | 'trade_down' | 'graph' | 'orderbook' | 'ai';
  onSelectTab: (tab: 'trade_up' | 'trade_down' | 'graph' | 'orderbook' | 'ai') => void;
  onQuickTrade: (side: 'yes' | 'no') => void;
}

export const ChanceBanner: React.FC<ChanceBannerProps> = ({
  market,
  activeTab,
  onSelectTab,
  onQuickTrade,
}) => {
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
              {market.market_chance_pct.toFixed(1)}%
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
            className="px-4 py-1.5 rounded-full text-xs font-extrabold bg-[#00d084]/15 hover:bg-[#00d084]/25 text-[#00d084] border border-[#00d084]/40 transition-all shadow-sm active:scale-95"
          >
            Up {market.yes_cents_str}
          </button>
          <button
            onClick={() => onQuickTrade('no')}
            className="px-4 py-1.5 rounded-full text-xs font-extrabold bg-[#ff4d4d]/15 hover:bg-[#ff4d4d]/25 text-[#ff4d4d] border border-[#ff4d4d]/40 transition-all shadow-sm active:scale-95"
          >
            Down {market.no_cents_str}
          </button>
          <button className="p-1 text-[#8b949e] hover:text-white transition-colors" title="Sort/Filter">
            <ArrowDownUp className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Sub Tab Navigation */}
      <div className="flex items-center gap-4 text-xs font-semibold border-t border-[#21262d] pt-2">
        <button
          onClick={() => onSelectTab('trade_up')}
          className={`pb-1 border-b-2 transition-all ${
            activeTab === 'trade_up'
              ? 'border-[#00d084] text-[#00d084]'
              : 'border-transparent text-[#8b949e] hover:text-white'
          }`}
        >
          Trade Up
        </button>
        <button
          onClick={() => onSelectTab('trade_down')}
          className={`pb-1 border-b-2 transition-all ${
            activeTab === 'trade_down'
              ? 'border-[#ff4d4d] text-[#ff4d4d]'
              : 'border-transparent text-[#8b949e] hover:text-white'
          }`}
        >
          Trade Down
        </button>
        <button
          onClick={() => onSelectTab('graph')}
          className={`pb-1 border-b-2 transition-all ${
            activeTab === 'graph'
              ? 'border-white text-white'
              : 'border-transparent text-[#8b949e] hover:text-white'
          }`}
        >
          Graph
        </button>
        <button
          onClick={() => onSelectTab('orderbook')}
          className={`pb-1 border-b-2 transition-all ${
            activeTab === 'orderbook'
              ? 'border-[#f7931a] text-[#f7931a]'
              : 'border-transparent text-[#8b949e] hover:text-white'
          }`}
        >
          Level-2 Book
        </button>
        <button
          onClick={() => onSelectTab('ai')}
          className={`pb-1 border-b-2 transition-all flex items-center gap-1 ${
            activeTab === 'ai'
              ? 'border-[#3b82f6] text-[#3b82f6]'
              : 'border-transparent text-[#8b949e] hover:text-white'
          }`}
        >
          <span>AI Microstructure</span>
          <span className="h-1.5 w-1.5 rounded-full bg-[#3b82f6] animate-pulse" />
        </button>
      </div>
    </div>
  );
};
