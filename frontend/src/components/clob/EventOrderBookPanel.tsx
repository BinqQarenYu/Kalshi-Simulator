import React from 'react';
import { ChevronDown, Info, Layers, MoreHorizontal, Shield } from 'lucide-react';
import { MarketState } from '../../types';
import { soundFX } from '../../utils/audioFX';

export interface TopBookRow {
  vol: string;
  volPct: number;
  yesBid: string;
  noAsk: string;
  yesCents: number;
  size: string;
  sizePct: number;
}

export interface CumulativeLadderRow {
  price: string;
  rawPrice: number;
  buyCum: string;
  buyPct: number;
  sellCum: string;
  sellPct: number;
}

interface EventOrderBookPanelProps {
  market: MarketState;
  currentSpec: {
    name: string;
    symbol: string;
    decimals: number;
  };
  strikePriceFormatted: string;
  isDiffPositive: boolean;
  spotDiff: number;
  topBookRows: TopBookRow[];
  cumulativeLadderRows: CumulativeLadderRow[];
  volumeUnit: 'lots' | 'usd' | 'cumulative';
  setVolumeUnit: (fn: (prev: 'lots' | 'usd' | 'cumulative') => 'lots' | 'usd' | 'cumulative') => void;
  isOrderSizeTooltipOpen: boolean;
  setIsOrderSizeTooltipOpen: (val: boolean | ((prev: boolean) => boolean)) => void;
  setOrderLimitPrice: (price: number) => void;
  setIsTradingPanelOpen: (val: boolean) => void;
}

export const EventOrderBookPanel: React.FC<EventOrderBookPanelProps> = ({
  market,
  currentSpec,
  strikePriceFormatted,
  isDiffPositive,
  spotDiff,
  topBookRows,
  cumulativeLadderRows,
  volumeUnit,
  setVolumeUnit,
  isOrderSizeTooltipOpen,
  setIsOrderSizeTooltipOpen,
  setOrderLimitPrice,
  setIsTradingPanelOpen,
}) => {
  return (
        <aside className="w-80 flex flex-col bg-[#0e131b] shrink-0 min-w-0 select-none overflow-hidden">
          {/* Panel Header */}
          <div className="p-3 border-b border-[#1f2937] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-[#00c978]" />
              <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-white">
                Kalshi Event Order Book (15min)
              </h2>
            </div>
            <button
              onClick={() => soundFX.playClickSound()}
              className="text-[#64748b] hover:text-white p-1 rounded"
              title="Event Order Book Options"
            >
              <MoreHorizontal className="w-4 h-4" />
            </button>
          </div>

          {/* Active Contract Header Banner */}
          <div className="px-3 py-2 bg-[#131923] border-b border-[#1f2937]">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-white leading-tight">
                {market?.title || `${currentSpec.name}: Price Above ${strikePriceFormatted} at ${market?.target_time_str || '3:00 PM EST'}`}
              </span>
            </div>
            <div className="flex items-center justify-between mt-1 text-[10px] font-mono text-[#8c9ba5]">
              <span>Ticker: <b className="text-[#38bdf8]">{market?.ticker || 'KXBTC15M'}</b></span>
              <span className={isDiffPositive ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                Diff: {isDiffPositive ? '+' : ''}${Math.abs(spotDiff).toFixed(currentSpec.decimals)}
              </span>
            </div>
          </div>

          {/* Sub-Table 1: Top of Book (Buy YES / Sell NO) */}
          <div className="flex-1 flex flex-col min-h-0 overflow-y-auto">
            <div className="px-3 py-1.5 bg-[#0e131b] border-b border-[#1a232e] grid grid-cols-3 text-[10px] font-mono uppercase tracking-wider">
              <span className="text-[#10b981] font-bold">Buy (Yes)</span>
              <span className="text-center text-[#8c9ba5] font-semibold">Price</span>
              <span className="text-right text-[#f43f5e] font-bold">Sell (No)</span>
            </div>

            {/* Sub-Headers */}
            <div className="px-3 py-1 bg-[#121822] grid grid-cols-3 text-[9px] font-mono text-[#64748b] border-b border-[#1a232e]">
              <span>Volume</span>
              <span className="text-center">Bid / Ask</span>
              <span className="text-right">Order Size</span>
            </div>

            {/* Top Book Rows (Live Streaming Ladder) */}
            <div className="divide-y divide-[#151c27] text-xs font-mono">
              {topBookRows.map((row, idx) => (
                <div
                  key={idx}
                  onClick={() => {
                    soundFX.playClickSound();
                    if (row.yesCents > 0) setOrderLimitPrice(row.yesCents);
                    setIsTradingPanelOpen(true);
                  }}
                  className="px-3 py-1.5 grid grid-cols-3 items-center hover:bg-[#17202d] cursor-pointer transition relative group"
                >
                  {/* Left Volume with Green Bar */}
                  <div className="relative flex items-center">
                    <div
                      className="absolute left-0 top-0 bottom-0 bg-[#10b981]/20 rounded-r transition-all duration-300"
                      style={{ width: `${row.volPct}%` }}
                    />
                    <span className="relative z-10 text-white font-medium text-[11px]">{row.vol}</span>
                  </div>

                  {/* Center Price: Green Bid / Red Ask */}
                  <div className="text-center flex items-center justify-center gap-1.5">
                    <span className="text-[#10b981] font-bold">{row.yesBid}</span>
                    <span className="text-[#475569]">/</span>
                    <span className="text-[#f43f5e] font-bold">{row.noAsk}</span>
                  </div>

                  {/* Right Order Size with Red Bar */}
                  <div className="relative flex items-center justify-end">
                    <div
                      className="absolute right-0 top-0 bottom-0 bg-[#f43f5e]/20 rounded-l transition-all duration-300"
                      style={{ width: `${row.sizePct}%` }}
                    />
                    <span className="relative z-10 text-white font-medium text-[11px]">{row.size}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Sub-Table 2: Deep Cumulative Liquidity Ladder */}
            <div className="mt-2 pt-2 border-t border-[#1f2937]">
              <div className="px-3 py-1 bg-[#121822] grid grid-cols-3 text-[9px] font-mono text-[#64748b] border-b border-[#1a232e]">
                <span className="text-[#10b981] font-bold">Buy (Yes)</span>
                <span className="text-center">Cumulative Depth</span>
                <span className="text-right text-[#f43f5e] font-bold">Sell (No)</span>
              </div>

              <div className="divide-y divide-[#151c27] text-xs font-mono">
                {cumulativeLadderRows.map((row, idx) => (
                  <div
                    key={idx}
                    onClick={() => {
                      soundFX.playClickSound();
                      if (row.rawPrice > 0) setOrderLimitPrice(row.rawPrice);
                      setIsTradingPanelOpen(true);
                    }}
                    className="px-3 py-1.5 grid grid-cols-3 items-center hover:bg-[#17202d] cursor-pointer transition relative"
                  >
                    {/* Buy Depth */}
                    <div className="relative flex items-center">
                      <div
                        className="absolute left-0 top-0 bottom-0 bg-[#10b981]/25 rounded-r transition-all duration-300"
                        style={{ width: `${row.buyPct}%` }}
                      />
                      <span className="relative z-10 text-emerald-300 font-bold text-[11px]">{row.buyCum}</span>
                    </div>

                    {/* Price */}
                    <div className="text-center text-[#8c9ba5] font-semibold text-[11px]">
                      {row.price}
                    </div>

                    {/* Sell Depth */}
                    <div className="relative flex items-center justify-end">
                      <div
                        className="absolute right-0 top-0 bottom-0 bg-[#f43f5e]/25 rounded-l transition-all duration-300"
                        style={{ width: `${row.sellPct}%` }}
                      />
                      <span className="relative z-10 text-rose-300 font-bold text-[11px]">{row.sellCum}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Left Panel Footer Controls */}
          <div className="p-2.5 bg-[#0e131b] border-t border-[#1f2937] flex items-center justify-between text-xs font-mono">
            {/* Volume Filter Dropdown */}
            <div className="relative">
              <button
                onClick={() => {
                  soundFX.playClickSound();
                  setVolumeUnit((prev) => (prev === 'lots' ? 'usd' : prev === 'usd' ? 'cumulative' : 'lots'));
                }}
                className="flex items-center gap-1 px-2 py-1 rounded bg-[#17202d] text-slate-300 hover:text-white border border-[#263342] text-[11px]"
                title="Toggle Volume format: Lots / USD / Cumulative"
              >
                <span>Volume: {volumeUnit.toUpperCase()}</span>
                <ChevronDown className="w-3 h-3 text-[#64748b]" />
              </button>
            </div>

            {/* Order Size Info Tooltip Button */}
            <div className="relative">
              <button
                onClick={() => {
                  soundFX.playClickSound();
                  setIsOrderSizeTooltipOpen(!isOrderSizeTooltipOpen);
                }}
                className="flex items-center gap-1 text-[11px] text-[#8c9ba5] hover:text-[#00c978] transition"
                title="Micro-Bankroll Sizing Armor Specs"
              >
                <span>Order Size</span>
                <Info className="w-3.5 h-3.5" />
              </button>

              {/* Popover */}
              {isOrderSizeTooltipOpen && (
                <div className="absolute bottom-8 left-[-60px] w-64 bg-[#17202d] border border-[#2d3d52] rounded-lg p-3 shadow-2xl z-50 text-[11px] font-mono text-slate-200">
                  <div className="font-bold text-[#00c978] flex items-center gap-1.5 mb-1">
                    <Shield className="w-3.5 h-3.5" />
                    <span>Micro-Bankroll Armor</span>
                  </div>
                  <p className="text-[#8c9ba5] leading-relaxed">
                    Sizing is strictly hard-capped to <b>1 contract per trade</b> for accounts under $75. Opposing positions (YES vs NO) are strictly blocked by LiveCoordinator.
                  </p>
                </div>
              )}
            </div>

            {/* Ellipsis Menu */}
            <button
              onClick={() => soundFX.playClickSound()}
              className="text-[#64748b] hover:text-white p-1 rounded"
              title="More Actions"
            >
              <MoreHorizontal className="w-4 h-4" />
            </button>
          </div>
        </aside>
  );
};
