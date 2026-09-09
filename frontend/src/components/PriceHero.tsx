import React, { useState } from 'react';
import { MarketState, PreflightGates } from '../types';
import { Info, Hourglass, ShieldAlert, ShieldCheck } from 'lucide-react';

interface PriceHeroProps {
  market: MarketState;
  preflightGates?: PreflightGates;
}

export const PriceHero: React.FC<PriceHeroProps> = React.memo(({ market, preflightGates }) => {
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

  const moatFloor = preflightGates?.moat_gate?.floor ?? 40.25;
  const moatSweetSpot = preflightGates?.moat_gate?.sweet_spot ?? 47.60;
  const moatCeiling = preflightGates?.moat_gate?.ceiling ?? 75.25;
  const isClearOfMoat = Math.abs(diffVal) >= moatFloor;

  return (
    <div className="bg-[#111620] border-b border-[#21262d] px-4 py-2.5 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Left: TO BEAT & NOW */}
        <div className="flex items-center gap-6 sm:gap-10">
          {/* TO BEAT Strike */}
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-[#8b949e]">
              TO BEAT
            </div>
            <div className="text-xl sm:text-2xl font-extrabold text-white tracking-tight font-mono">
              {market.target_strike_str}
            </div>
            <div className="text-[11px] text-[#8b949e] font-medium">{market.target_time_str || 'Expiry Target'}</div>
          </div>

          {/* NOW Spot Price */}
          <div>
            <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-[#8b949e]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>NOW {market.active_asset || 'BTC'}</span>
              <Info className="h-3 w-3 text-[#8b949e]" />
            </div>
            <div className={`text-xl sm:text-2xl font-extrabold tracking-tight font-mono ${deltaColor}`}>
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

        {/* Dynamic Volatility Moat Tunnel Visualizer (Pillar 3) */}
        <div className="w-full mt-2 pt-2 border-t border-[#1e242e] flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] font-mono">
            <div className="flex items-center gap-2 text-gray-400">
              <span className="text-[9px] uppercase font-bold text-gray-400 tracking-wider flex items-center gap-1">
                {isClearOfMoat ? (
                  <ShieldCheck className="h-3 w-3 text-emerald-400" />
                ) : (
                  <ShieldAlert className="h-3 w-3 text-rose-400 animate-pulse" />
                )}
                Moat Tunnel Horizon
              </span>
              <span className="text-gray-600">·</span>
              <span>1.15x Floor: <strong className="text-rose-400">${moatFloor.toFixed(2)}</strong></span>
              <span className="text-gray-600">·</span>
              <span>1.36x Sweet Spot: <strong className="text-amber-400">${moatSweetSpot.toFixed(2)}</strong></span>
              <span className="text-gray-600">·</span>
              <span>2.15x Ceiling: <strong className="text-cyan-400">${moatCeiling.toFixed(2)}</strong></span>
            </div>
            <div className="flex items-center gap-2">
              <span className={`px-2 py-0.5 text-[9px] font-bold rounded-full uppercase tracking-wider ${
                isClearOfMoat
                  ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                  : 'bg-rose-500/15 text-rose-300 border border-rose-500/30 animate-pulse'
              }`}>
                {isClearOfMoat ? 'CLEAR OF STRIKE NOISE' : 'TRAPPED IN NOISE CHOP'}
              </span>
              <span className="text-gray-400">
                Diff: <strong className={deltaColor}>{formattedDiff}</strong>
              </span>
            </div>
          </div>

          {/* Horizontal Gauge Bar */}
          <div className="relative h-3.5 bg-[#0a0d12] rounded-full overflow-hidden border border-[#262d35] flex items-center shadow-inner">
            {/* Center 0.00 Strike Target Anchor */}
            <div className="absolute left-1/2 top-0 bottom-0 w-0.5 bg-gray-400 z-10 -translate-x-1/2 shadow" title="Target Strike K ($0.00)" />
            
            {/* Left Dead Zone (-$40.25 to 0) */}
            <div 
              className="absolute top-0 bottom-0 bg-rose-500/20 border-r border-rose-500/40"
              style={{ left: '25%', width: '25%' }}
              title={`Downside Strike Noise Trap (< $${moatFloor.toFixed(2)})`}
            />
            
            {/* Right Dead Zone (0 to +$40.25) */}
            <div 
              className="absolute top-0 bottom-0 bg-rose-500/20 border-l border-rose-500/40"
              style={{ left: '50%', width: '25%' }}
              title={`Upside Strike Noise Trap (< $${moatFloor.toFixed(2)})`}
            />

            {/* Sweet Spot Calibration Notches at -1.36x and +1.36x */}
            <div className="absolute top-0 bottom-0 w-0.5 bg-amber-400 z-10 shadow" style={{ left: '18%' }} title={`Downside Sweet Spot (-$${moatSweetSpot.toFixed(2)})`} />
            <div className="absolute top-0 bottom-0 w-0.5 bg-amber-400 z-10 shadow" style={{ left: '82%' }} title={`Upside Sweet Spot (+$${moatSweetSpot.toFixed(2)})`} />

            {/* Live Spot Price Dot */}
            <div 
              className={`absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3.5 h-3.5 rounded-full border-2 border-white shadow-xl transition-all duration-300 z-20 ${
                isClearOfMoat ? 'bg-emerald-400 shadow-emerald-400/50' : 'bg-rose-500 shadow-rose-500/50 animate-pulse'
              }`}
              style={{ 
                left: `${Math.max(4, Math.min(96, 50 + (diffVal / 100.0) * 50))}%` 
              }}
              title={`Live Spot Separation: ${formattedDiff}`}
            />
          </div>
        </div>
      </div>
    </div>
  );
});
