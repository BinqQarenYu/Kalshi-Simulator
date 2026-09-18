import React from 'react';
import { Bot, Cpu, Crown, Layers, Radio, TrendingUp, Zap } from 'lucide-react';
import { SystemFilter } from './AnalyticsTypes';

interface BotSystemFilterSelectorProps {
  selectedSystem: SystemFilter;
  setSelectedSystem: (sys: SystemFilter) => void;
  assetFilter: 'ALL' | 'BTC' | 'ETH' | 'SOL' | 'DOGE';
  setAssetFilter: (asset: 'ALL' | 'BTC' | 'ETH' | 'SOL' | 'DOGE') => void;
  timeframeFilter: 'ALL' | '5M' | '15M';
  setTimeframeFilter: (tf: 'ALL' | '5M' | '15M') => void;
}

export const BotSystemFilterSelector: React.FC<BotSystemFilterSelectorProps> = ({
  selectedSystem,
  setSelectedSystem,
  assetFilter,
  setAssetFilter,
  timeframeFilter,
  setTimeframeFilter,
}) => {
  return (
    <>
      {/* 3. Bot & System Isolated Drilldown Selector */}
      <div className="bg-slate-900/90 border border-slate-800 p-3 rounded-xl flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Active Isolated Drilldown:</span>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 bg-slate-950 p-1 rounded-lg border border-slate-800">
          <button
            onClick={() => setSelectedSystem('all')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition ${
              selectedSystem === 'all'
                ? 'bg-slate-800 text-white shadow-sm border border-slate-700'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-blue-400" />
            All Combined
          </button>

          <button
            onClick={() => setSelectedSystem('macro_onnx')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition ${
              selectedSystem === 'macro_onnx'
                ? 'bg-purple-500/20 text-purple-300 shadow-sm border border-purple-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Cpu className="w-3.5 h-3.5 text-purple-400" />
            Macro ONNX Bot (Champ)
          </button>

          <button
            onClick={() => setSelectedSystem('macro_trend_dominion')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition ${
              selectedSystem === 'macro_trend_dominion'
                ? 'bg-cyan-500/20 text-cyan-300 shadow-sm border border-cyan-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <TrendingUp className="w-3.5 h-3.5 text-cyan-400" />
            Macro Trend Dominion (Paper)
          </button>

          <button
            onClick={() => setSelectedSystem('dominion_2_bot')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition ${
              selectedSystem === 'dominion_2_bot'
                ? 'bg-emerald-500/20 text-emerald-300 shadow-sm border border-emerald-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Crown className="w-3.5 h-3.5 text-emerald-400" />
            Dominion 2 Bot (Paper)
          </button>

          <button
            onClick={() => setSelectedSystem('3_step_domination_bot')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition ${
              selectedSystem === '3_step_domination_bot'
                ? 'bg-amber-500/20 text-amber-300 shadow-sm border border-amber-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            3-Step Domination (Paper)
          </button>

          <button
            onClick={() => setSelectedSystem('onnx_ml_bot')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition ${
              selectedSystem === 'onnx_ml_bot'
                ? 'bg-purple-500/20 text-purple-300 shadow-sm border border-purple-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Cpu className="w-3.5 h-3.5 text-purple-400" />
            ONNX ML Ensemble (Paper)
          </button>

          <button
            onClick={() => setSelectedSystem('live')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition ${
              selectedSystem === 'live'
                ? 'bg-rose-500/20 text-rose-300 shadow-sm border border-rose-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Radio className="w-3.5 h-3.5 text-rose-400 animate-pulse" />
            Live Trading (Real Capital)
          </button>
        </div>
      </div>

      {/* 3B. Multi-Asset & Multi-Timeframe Institutional Filter */}
      <div className="bg-slate-900/90 border border-slate-800 p-3 rounded-xl flex flex-wrap items-center justify-between gap-3 font-mono">
        <div className="flex items-center gap-3">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[#8c9ba5]">Asset Class:</span>
          <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
            {(['ALL', 'BTC', 'ETH', 'SOL', 'DOGE'] as const).map((a) => (
              <button
                key={a}
                onClick={() => setAssetFilter(a)}
                className={`px-3 py-1 rounded text-xs font-bold transition ${
                  assetFilter === a
                    ? 'bg-emerald-500 text-black shadow-sm font-black'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {a}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[#8c9ba5]">Cycle Horizon:</span>
          <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
            {(['ALL', '5M', '15M'] as const).map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframeFilter(tf)}
                className={`px-3 py-1 rounded text-xs font-bold transition ${
                  timeframeFilter === tf
                    ? 'bg-amber-500 text-black shadow-sm font-black'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>
      </div>
    </>
  );
};
