import React from 'react';
import { Activity, ChevronDown, MoreHorizontal } from 'lucide-react';
import { CryptoAsset } from '../../types';
import { soundFX } from '../../utils/audioFX';

export interface SpotBookRow {
  bidQty: string;
  price: string;
  ask: string;
  vol: string;
  askPct?: number;
  bidPct?: number;
}

export interface SpotBookState {
  asks: SpotBookRow[];
  bids: SpotBookRow[];
  spread: string;
}

interface SpotOrderBookPanelProps {
  currentSpec: {
    name: string;
    symbol: string;
    decimals: number;
    feedId: string;
    unit: string;
  };
  spotPriceFormatted: string;
  strikePriceFormatted: string;
  isDiffPositive: boolean;
  spotDiff: number;
  spotBook: SpotBookState;
  activeAsset: CryptoAsset;
  spotVolumeUnit: 'btc' | 'usd';
  setSpotVolumeUnit: (fn: (prev: 'btc' | 'usd') => 'btc' | 'usd') => void;
  handleSwitchAsset: (asset: CryptoAsset) => void;
}

export const SpotOrderBookPanel: React.FC<SpotOrderBookPanelProps> = ({
  currentSpec,
  spotPriceFormatted,
  strikePriceFormatted,
  isDiffPositive,
  spotDiff,
  spotBook,
  activeAsset,
  spotVolumeUnit,
  setSpotVolumeUnit,
  handleSwitchAsset,
}) => {
  return (
        <aside className="w-80 flex flex-col bg-[#0e131b] shrink-0 min-w-0 select-none overflow-hidden">
          {/* Panel Header */}
          <div className="p-3 border-b border-[#1f2937] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-[#38bdf8]" />
              <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-white">
                {currentSpec.name} ({currentSpec.symbol}) Order Book
              </h2>
            </div>
            <button
              onClick={() => soundFX.playClickSound()}
              className="text-[#64748b] hover:text-white p-1 rounded"
              title="Underlying Order Book Options"
            >
              <MoreHorizontal className="w-4 h-4" />
            </button>
          </div>

          {/* Spot Price Banner with 5Hz Stream Pulse */}
          <div className="px-4 py-3 bg-[#131923] border-b border-[#1f2937] flex items-center justify-between">
            <div>
              <div className="text-xl font-mono font-extrabold text-white tracking-tight flex items-center gap-2">
                <span>{spotPriceFormatted}</span>
                <span className="w-2 h-2 rounded-full bg-[#00c978] animate-pulse" title="5Hz CME CF Benchmarks Feed" />
              </div>
              <div className="text-[10px] font-mono text-[#8c9ba5] mt-0.5">
                Target Strike: <b className="text-white">{strikePriceFormatted}</b>
              </div>
            </div>
            <div className="text-right">
              <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${
                isDiffPositive ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
              }`}>
                {isDiffPositive ? '+' : ''}${Math.abs(spotDiff).toFixed(currentSpec.decimals)}
              </span>
              <div className="text-[9px] font-mono text-[#64748b] mt-1">{currentSpec.feedId}</div>
            </div>
          </div>

          {/* L2 Order Book Table */}
          <div className="flex-1 flex flex-col min-h-0 overflow-y-auto">
            {/* Table Header */}
            <div className="px-3 py-1.5 bg-[#0e131b] grid grid-cols-4 text-[9px] font-mono uppercase text-[#64748b] border-b border-[#1a232e]">
              <span>Bids</span>
              <span className="text-center text-[#10b981]">Price</span>
              <span className="text-center text-[#f43f5e]">Ask</span>
              <span className="text-right">Volume</span>
            </div>

            {/* Asks Ladder (Red) */}
            <div className="divide-y divide-[#151c27] text-xs font-mono">
              {spotBook.asks.map((row, idx) => (
                <div
                  key={idx}
                  onClick={() => soundFX.playClickSound()}
                  className="px-3 py-1.5 grid grid-cols-4 items-center hover:bg-[#17202d] cursor-pointer transition relative"
                >
                  <span className="text-[#8c9ba5] text-[11px]">{row.bidQty}</span>
                  <span className="text-center text-emerald-400 font-medium text-[11px]">{row.price}</span>
                  <span className="text-center text-rose-400 font-medium text-[11px]">{row.ask}</span>
                  <div className="relative flex items-center justify-end">
                    <div
                      className="absolute right-0 top-0 bottom-0 bg-[#f43f5e]/20 rounded-l transition-all duration-300"
                      style={{ width: `${row.askPct}%` }}
                    />
                    <span className="relative z-10 text-white font-medium text-[11px]">{row.vol}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Mid-Market Spread Indicator Divider */}
            <div className="px-3 py-2 bg-[#121822] border-y border-[#1f2937] flex items-center justify-between font-mono text-xs">
              <div className="flex items-center gap-2">
                <span className="text-white font-bold">{spotPriceFormatted}</span>
                <span className="text-[10px] text-[#8c9ba5] uppercase">Mid</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-[#38bdf8] font-bold">Spread: {spotBook.spread}</span>
                <span className="text-[10px] text-[#00c978] font-bold">{activeAsset}</span>
              </div>
            </div>

            {/* Bids Ladder (Green) */}
            <div className="divide-y divide-[#151c27] text-xs font-mono">
              {spotBook.bids.map((row, idx) => (
                <div
                  key={idx}
                  onClick={() => soundFX.playClickSound()}
                  className="px-3 py-1.5 grid grid-cols-4 items-center hover:bg-[#17202d] cursor-pointer transition relative"
                >
                  <span className="text-white font-medium text-[11px]">{row.bidQty}</span>
                  <span className="text-center text-emerald-400 font-medium text-[11px]">{row.price}</span>
                  <span className="text-center text-rose-400 font-medium text-[11px]">{row.ask}</span>
                  <div className="relative flex items-center justify-end">
                    <div
                      className="absolute right-0 top-0 bottom-0 bg-[#10b981]/20 rounded-l transition-all duration-300"
                      style={{ width: `${row.bidPct}%` }}
                    />
                    <span className="relative z-10 text-white font-medium text-[11px]">{row.vol}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right Panel Footer Controls */}
          <div className="p-2.5 bg-[#0e131b] border-t border-[#1f2937] flex items-center justify-between text-xs font-mono">
            {/* Spot Volume Filter */}
            <button
              onClick={() => {
                soundFX.playClickSound();
                setSpotVolumeUnit((prev) => (prev === 'btc' ? 'usd' : 'btc'));
              }}
              className="flex items-center gap-1 px-2 py-1 rounded bg-[#17202d] text-slate-300 hover:text-white border border-[#263342] text-[11px]"
              title={`Toggle Spot Volume format: ${currentSpec.unit} / USD`}
            >
              <span>Volume: {spotVolumeUnit === 'btc' ? currentSpec.unit : 'USD'}</span>
              <ChevronDown className="w-3 h-3 text-[#64748b]" />
            </button>

            {/* Asset Selector Dropdown */}
            <div className="flex items-center gap-1 bg-[#131923] p-0.5 rounded border border-[#1f2937]">
              {(['BTC', 'ETH', 'SOL', 'DOGE'] as const).map((asset) => (
                <button
                  key={asset}
                  onClick={() => handleSwitchAsset(asset)}
                  className={`px-2 py-0.5 rounded text-[10px] font-bold transition ${
                    activeAsset === asset ? 'bg-[#38bdf8] text-black font-extrabold shadow' : 'text-[#8c9ba5] hover:text-white'
                  }`}
                >
                  {asset}
                </button>
              ))}
            </div>

            {/* Ellipsis Menu */}
            <button
              onClick={() => soundFX.playClickSound()}
              className="text-[#64748b] hover:text-white p-1 rounded"
              title="More Options"
            >
              <MoreHorizontal className="w-4 h-4" />
            </button>
          </div>
        </aside>
  );
};
