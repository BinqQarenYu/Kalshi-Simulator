import React from 'react';
import { Clock, Cpu, Flame, Info, Sliders } from 'lucide-react';
import { StrategyParameters } from './OnnxConstants';

interface StrategyDialsMatrixProps {
  params: StrategyParameters;
  handleChange: (key: keyof StrategyParameters, value: any) => void;
  setActiveInfo: (infoKey: string) => void;
}

export const StrategyDialsMatrix: React.FC<StrategyDialsMatrixProps> = ({
  params,
  handleChange,
  setActiveInfo,
}) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Quadrant 1: Brain Arbitration & Conviction */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-3.5 space-y-3">
        <div className="flex items-center justify-between border-b border-[#21262d] pb-2">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-cyan-400" />
            <span className="font-bold text-white uppercase text-[11px]">1. Brain Arbitration & Sizing</span>
          </div>
          <span className="text-[10px] text-gray-500">Dial 1 & 2</span>
        </div>

        {/* Brain Priority Mode */}
        <div className="space-y-1">
          <div className="flex justify-between items-center text-[10px] text-[#8c9ba5] font-semibold uppercase">
            <label htmlFor="brain-priority-select" className="flex items-center gap-1.5 cursor-pointer">
              Arbitration Priority Mode
              <button
                type="button"
                aria-label="View Arbitration Priority Mode guidance"
                onClick={() => setActiveInfo('brain_priority')}
                className="text-cyan-400 hover:text-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-400 rounded"
                title="View Parameter Guidance"
              >
                <Info className="w-3 h-3" />
              </button>
            </label>
            <span className="text-cyan-400 font-mono">{params.brain_priority_mode}</span>
          </div>
          <select
            id="brain-priority-select"
            aria-label="Arbitration Priority Mode"
            value={params.brain_priority_mode}
            onChange={(e) => handleChange('brain_priority_mode', e.target.value)}
            className="w-full bg-[#0a0c10] border border-[#262d35] rounded-lg p-2 text-white text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 cursor-pointer"
          >
            <option value="TREND_ALIGNED_SCALP">TREND_ALIGNED_SCALP (Spot Leads, Sweeps / Discounts)</option>
            <option value="SPOT_DOMINANT">SPOT_DOMINANT (Pure Spot Bias)</option>
            <option value="KALSHI_DOMINANT">KALSHI_DOMINANT (Kalshi Inside Touch Bias)</option>
            <option value="CONSERVATIVE_CROSS">CONSERVATIVE_CROSS (Both Brains Must Strictly Agree)</option>
          </select>
        </div>

        {/* Sizing Armor */}
        <div className="space-y-1">
          <div className="flex justify-between items-center text-[10px] text-[#8c9ba5] font-semibold uppercase">
            <label htmlFor="sizing-armor-select" className="flex items-center gap-1.5 cursor-pointer">
              Micro-Bankroll Sizing Armor
              <button
                type="button"
                aria-label="View Micro-Bankroll Sizing Armor guidance"
                onClick={() => setActiveInfo('sizing_armor')}
                className="text-cyan-400 hover:text-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-400 rounded"
                title="View Parameter Guidance"
              >
                <Info className="w-3 h-3" />
              </button>
            </label>
            <span className="text-purple-400 font-mono">1 Contract Hard Cap</span>
          </div>
          <select
            id="sizing-armor-select"
            aria-label="Micro-Bankroll Sizing Armor"
            value={params.contract_scaling_mode || 'TIER_0_STRICT_1'}
            onChange={(e) => handleChange('contract_scaling_mode', e.target.value)}
            className="w-full bg-[#0a0c10] border border-[#262d35] rounded-lg p-2 text-white text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 cursor-pointer"
          >
            <option value="TIER_0_STRICT_1">TIER_0_STRICT_1 (Hard Cap 1 Contract)</option>
            <option value="TIER_1_MICRO_2">TIER_1_MICRO_2 (Bankroll &gt; $75)</option>
          </select>
        </div>

        {/* Min Neural Confidence */}
        <div className="space-y-1">
          <div className="flex justify-between items-center text-[10px] text-[#8c9ba5] font-semibold">
            <label htmlFor="min-confidence-slider" className="flex items-center gap-1.5 uppercase cursor-pointer">
              Min Neural Confidence
              <button
                type="button"
                aria-label="View Min Neural Confidence guidance"
                onClick={() => setActiveInfo('min_confidence')}
                className="text-cyan-400 hover:text-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-400 rounded"
                title="View Parameter Guidance"
              >
                <Info className="w-3 h-3" />
              </button>
            </label>
            <span className="font-mono text-cyan-400">{((params.min_confidence || 0.7) * 100).toFixed(0)}%</span>
          </div>
          <input
            id="min-confidence-slider"
            aria-label="Min Neural Confidence percentage"
            type="range"
            min="0.50"
            max="0.95"
            step="0.01"
            value={params.min_confidence || 0.70}
            onChange={(e) => handleChange('min_confidence', parseFloat(e.target.value))}
            className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-cyan-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
          />
          <div className="flex justify-between text-[9px] text-gray-500">
            <span>50% (Loose)</span>
            <span>70% (Institutional Default)</span>
            <span>95% (Extreme Conviction)</span>
          </div>
        </div>

        {/* Min Net EV ($) */}
        <div className="space-y-1">
          <div className="flex justify-between items-center text-[10px] text-[#8c9ba5] font-semibold">
            <label htmlFor="min-ev-slider" className="flex items-center gap-1.5 uppercase cursor-pointer">
              Min Net Expected Value (EV)
              <button
                type="button"
                aria-label="View Minimum Expected Value guidance"
                onClick={() => setActiveInfo('min_ev')}
                className="text-cyan-400 hover:text-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-400 rounded"
                title="View Parameter Guidance"
              >
                <Info className="w-3 h-3" />
              </button>
            </label>
            <span className="font-mono text-emerald-400">+${(params.min_ev_dollars || 0.02).toFixed(2)}</span>
          </div>
          <input
            id="min-ev-slider"
            aria-label="Minimum Net Expected Value in dollars"
            type="range"
            min="0.01"
            max="0.20"
            step="0.01"
            value={params.min_ev_dollars || 0.02}
            onChange={(e) => handleChange('min_ev_dollars', parseFloat(e.target.value))}
            className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-emerald-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
          />
          <div className="flex justify-between text-[9px] text-gray-500">
            <span>+$0.01 (High Volume)</span>
            <span>+$0.02 (Default)</span>
            <span>+$0.20 (Deep Moat)</span>
          </div>
        </div>
      </div>

      {/* Quadrant 2: Pricing & Spread Execution */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-3.5 space-y-3">
        <div className="flex items-center justify-between border-b border-[#21262d] pb-2">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-amber-400" />
            <span className="font-bold text-white uppercase text-[11px]">2. Pricing & Spread Execution</span>
          </div>
          <span className="text-[10px] text-gray-500">Dial 4</span>
        </div>

        {/* Maker Discount Ceiling */}
        <div className="space-y-1">
          <div className="flex justify-between items-center text-[10px] text-[#8c9ba5] font-semibold">
            <label htmlFor="entry-discount-slider" className="flex items-center gap-1.5 uppercase cursor-pointer">
              Maker Resting Discount Ceiling
              <button
                type="button"
                aria-label="View Entry Discount Depth guidance"
                onClick={() => setActiveInfo('entry_discount')}
                className="text-cyan-400 hover:text-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-400 rounded"
                title="View Parameter Guidance"
              >
                <Info className="w-3 h-3" />
              </button>
            </label>
            <span className="font-mono text-amber-300">${(params.entry_discount_depth || 0.52).toFixed(2)}</span>
          </div>
          <input
            id="entry-discount-slider"
            aria-label="Maker Resting Discount Ceiling in dollars"
            type="range"
            min="0.15"
            max="0.55"
            step="0.01"
            value={params.entry_discount_depth || 0.52}
            onChange={(e) => handleChange('entry_discount_depth', parseFloat(e.target.value))}
            className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-amber-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
          />
          <div className="flex justify-between text-[9px] text-gray-500">
            <span>15¢ (Deep Value)</span>
            <span>52¢ (Institutional Default)</span>
            <span>55¢ (Ceiling)</span>
          </div>
        </div>

        {/* Momentum Max Price */}
        <div className="space-y-1">
          <div className="flex justify-between items-center text-[10px] text-[#8c9ba5] font-semibold">
            <label htmlFor="momentum-max-slider" className="flex items-center gap-1.5 uppercase cursor-pointer">
              Momentum Taker Sweep Ceiling
              <button
                type="button"
                aria-label="View Momentum Max Price Ceiling guidance"
                onClick={() => setActiveInfo('momentum_max')}
                className="text-cyan-400 hover:text-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-400 rounded"
                title="View Parameter Guidance"
              >
                <Info className="w-3 h-3" />
              </button>
            </label>
            <span className="font-mono text-cyan-300">${(params.momentum_max_price || 0.62).toFixed(2)}</span>
          </div>
          <input
            id="momentum-max-slider"
            aria-label="Momentum Taker Sweep Ceiling in dollars"
            type="range"
            min="0.50"
            max="0.75"
            step="0.01"
            value={params.momentum_max_price || 0.62}
            onChange={(e) => handleChange('momentum_max_price', parseFloat(e.target.value))}
            className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-cyan-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
          />
          <div className="flex justify-between text-[9px] text-gray-500">
            <span>50¢ (Even Odds)</span>
            <span>62¢ (Momentum Cap)</span>
            <span>75¢ (Aggressive Sweep)</span>
          </div>
        </div>

        {/* Taker Cross EV Threshold */}
        <div className="space-y-1">
          <div className="flex justify-between items-center text-[10px] text-[#8c9ba5] font-semibold">
            <label htmlFor="taker-ev-slider" className="flex items-center gap-1.5 uppercase cursor-pointer">
              Taker Cross EV Hurdle (CFTC Fee Armor)
              <button
                type="button"
                aria-label="View Taker Cross EV Hurdle guidance"
                onClick={() => setActiveInfo('taker_ev')}
                className="text-cyan-400 hover:text-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-400 rounded"
                title="View Parameter Guidance"
              >
                <Info className="w-3 h-3" />
              </button>
            </label>
            <span className="font-mono text-emerald-300">+${(params.taker_cross_ev_threshold || 0.04).toFixed(2)}</span>
          </div>
          <input
            id="taker-ev-slider"
            aria-label="Taker Cross EV Hurdle in dollars"
            type="range"
            min="0.01"
            max="0.15"
            step="0.01"
            value={params.taker_cross_ev_threshold || 0.04}
            onChange={(e) => handleChange('taker_cross_ev_threshold', parseFloat(e.target.value))}
            className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-emerald-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
          />
          <div className="flex justify-between text-[9px] text-gray-500">
            <span>+$0.01 (Eager Cross)</span>
            <span>+$0.04 (Fee-Armored Default)</span>
            <span>+$0.15 (Extreme Edge)</span>
          </div>
        </div>

        {/* Dynamic Moat Multiplier */}
        <div className="space-y-1">
          <div className="flex justify-between items-center text-[10px] text-[#8c9ba5] font-semibold">
            <label htmlFor="dynamic-moat-slider" className="flex items-center gap-1.5 uppercase cursor-pointer">
              Dynamic Moat Multiplier
              <button
                type="button"
                aria-label="View Dynamic Moat Multiplier guidance"
                onClick={() => setActiveInfo('dynamic_moat')}
                className="text-cyan-400 hover:text-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-400 rounded"
                title="View Parameter Guidance"
              >
                <Info className="w-3 h-3" />
              </button>
            </label>
            <span className="font-mono text-amber-300">{(params.dynamic_moat_multiplier || 1.36).toFixed(2)}x</span>
          </div>
          <input
            id="dynamic-moat-slider"
            aria-label="Dynamic Moat Multiplier"
            type="range"
            min="1.00"
            max="2.50"
            step="0.05"
            value={params.dynamic_moat_multiplier || 1.36}
            onChange={(e) => handleChange('dynamic_moat_multiplier', parseFloat(e.target.value))}
            className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-amber-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
          />
          <div className="flex justify-between text-[9px] text-gray-500">
            <span>1.00x (Neutral)</span>
            <span>1.36x (Default Calibrated)</span>
            <span>2.50x (Ultra Deep Moat)</span>
          </div>
        </div>
      </div>

      {/* Quadrant 3: Temporal & Latency Armor */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-3.5 space-y-3">
        <div className="flex items-center justify-between border-b border-[#21262d] pb-2">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-purple-400" />
            <span className="font-bold text-white uppercase text-[11px]">3. Temporal & Latency Armor</span>
          </div>
          <span className="text-[10px] text-gray-500">Anti-Ghosting</span>
        </div>

        {/* Max Temporal Skew (ms) */}
        <div className="space-y-1">
          <div className="flex justify-between items-center text-[10px] text-[#8c9ba5] font-semibold">
            <label htmlFor="temporal-skew-slider" className="flex items-center gap-1.5 uppercase cursor-pointer">
              Max Cross-Brain Skew Tolerance
              <button
                type="button"
                aria-label="View Cross-Brain Temporal Skew Guard guidance"
                onClick={() => setActiveInfo('temporal_skew')}
                className="text-cyan-400 hover:text-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-400 rounded"
                title="View Parameter Guidance"
              >
                <Info className="w-3 h-3" />
              </button>
            </label>
            <span className="font-mono text-purple-400">{(params.max_temporal_skew_ms || 1000).toFixed(0)}ms</span>
          </div>
          <input
            id="temporal-skew-slider"
            aria-label="Max Cross-Brain Skew Tolerance in milliseconds"
            type="range"
            min="200"
            max="3000"
            step="50"
            value={params.max_temporal_skew_ms || 1000}
            onChange={(e) => handleChange('max_temporal_skew_ms', parseFloat(e.target.value))}
            className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-purple-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400"
          />
          <div className="flex justify-between text-[9px] text-gray-500">
            <span>200ms (High-Frequency)</span>
            <span>1000ms (Institutional Parity)</span>
            <span>3000ms (Loose)</span>
          </div>
        </div>

        {/* Gamma Cliff Seconds */}
        <div className="space-y-1">
          <div className="flex justify-between items-center text-[10px] text-[#8c9ba5] font-semibold">
            <label htmlFor="gamma-cliff-slider" className="flex items-center gap-1.5 uppercase cursor-pointer">
              Gamma Cliff Expiry Cutoff (Anti-Pin Risk)
              <button
                type="button"
                aria-label="View Gamma Cliff Purge Timer guidance"
                onClick={() => setActiveInfo('gamma_cliff')}
                className="text-cyan-400 hover:text-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-400 rounded"
                title="View Parameter Guidance"
              >
                <Info className="w-3 h-3" />
              </button>
            </label>
            <span className="font-mono text-rose-400">{(params.gamma_cliff_seconds || 90).toFixed(0)}s rem</span>
          </div>
          <input
            id="gamma-cliff-slider"
            aria-label="Gamma Cliff Expiry Cutoff in seconds remaining"
            type="range"
            min="30"
            max="180"
            step="5"
            value={params.gamma_cliff_seconds || 90}
            onChange={(e) => handleChange('gamma_cliff_seconds', parseFloat(e.target.value))}
            className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-rose-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400"
          />
          <div className="flex justify-between text-[9px] text-gray-500">
            <span>30s (Aggressive Sniper)</span>
            <span>90s (Institutional Cliff)</span>
            <span>180s (Conservative)</span>
          </div>
        </div>

        {/* Auto Cancel on Veto Toggle */}
        <div className="flex items-center justify-between pt-1">
          <div className="flex flex-col">
            <span id="auto-purge-veto-label" className="text-[10px] font-semibold text-white uppercase">Auto-Purge Resting Orders on Veto</span>
            <span className="text-[9px] text-gray-500">Immediately sweep open maker bids upon any VPIN / Skew breach</span>
          </div>
          <button
            id="auto-purge-veto-switch"
            type="button"
            role="switch"
            aria-checked={params.auto_cancel_on_veto}
            aria-labelledby="auto-purge-veto-label"
            onClick={() => handleChange('auto_cancel_on_veto', !params.auto_cancel_on_veto)}
            className={`w-11 h-6 flex items-center rounded-full p-1 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 ${
              params.auto_cancel_on_veto ? 'bg-cyan-500' : 'bg-gray-700'
            }`}
          >
            <div
              className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform ${
                params.auto_cancel_on_veto ? 'translate-x-5' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Quadrant 4: Volatility & Chaos Filters */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-3.5 space-y-3">
        <div className="flex items-center justify-between border-b border-[#21262d] pb-2">
          <div className="flex items-center gap-2">
            <Flame className="w-4 h-4 text-emerald-400" />
            <span className="font-bold text-white uppercase text-[11px]">4. Volatility & Chaos Filters</span>
          </div>
          <span className="text-[10px] text-gray-500">Dial 3</span>
        </div>

        {/* Dynamic Volatility Mode */}
        <div className="space-y-1">
          <div className="flex justify-between items-center text-[10px] text-[#8c9ba5] font-semibold uppercase">
            <label htmlFor="volatility-mode-select" className="flex items-center gap-1.5 cursor-pointer">
              Diffusion Volatility Mode
              <button
                type="button"
                aria-label="View Dynamic Volatility Engine guidance"
                onClick={() => setActiveInfo('volatility_mode')}
                className="text-cyan-400 hover:text-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-400 rounded"
                title="View Parameter Guidance"
              >
                <Info className="w-3 h-3" />
              </button>
            </label>
            <span className="text-emerald-400 font-mono">{params.dynamic_volatility_mode}</span>
          </div>
          <select
            id="volatility-mode-select"
            aria-label="Diffusion Volatility Mode"
            value={params.dynamic_volatility_mode}
            onChange={(e) => handleChange('dynamic_volatility_mode', e.target.value)}
            className="w-full bg-[#0a0c10] border border-[#262d35] rounded-lg p-2 text-white text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 cursor-pointer"
          >
            <option value="REALIZED_ATR">REALIZED_ATR (Live 15M/5M Rolling Candle ATR)</option>
            <option value="FIXED_STATIC">FIXED_STATIC (Static $14.0/min Anchor)</option>
          </select>
        </div>

        {/* VPIN Toxicity Cutoff */}
        <div className="space-y-1">
          <div className="flex justify-between items-center text-[10px] text-[#8c9ba5] font-semibold">
            <label htmlFor="vpin-toxicity-slider" className="flex items-center gap-1.5 uppercase cursor-pointer">
              VPIN Toxicity Cutoff
              <button
                type="button"
                aria-label="View VPIN Toxicity Cutoff guidance"
                onClick={() => setActiveInfo('vpin_toxicity')}
                className="text-cyan-400 hover:text-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-400 rounded"
                title="View Parameter Guidance"
              >
                <Info className="w-3 h-3" />
              </button>
            </label>
            <span className="font-mono text-cyan-300">{Number(params.vpin_toxic_threshold || 0.70).toFixed(2)}</span>
          </div>
          <input
            id="vpin-toxicity-slider"
            aria-label="VPIN Toxicity Cutoff"
            type="range"
            min="0.50"
            max="0.90"
            step="0.01"
            value={params.vpin_toxic_threshold || 0.70}
            onChange={(e) => handleChange('vpin_toxic_threshold', parseFloat(e.target.value))}
            className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-cyan-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
          />
          <div className="flex justify-between text-[9px] text-gray-500">
            <span>0.50 (Strict Veto)</span>
            <span>0.70 (Institutional Cutoff)</span>
            <span>0.90 (Permissive)</span>
          </div>
        </div>

        {/* Volatility Floor & Ceiling Dual Inputs */}
        <div className="grid grid-cols-2 gap-2 pt-1">
          <div className="space-y-1">
            <label htmlFor="vol-floor-input" className="text-[9px] text-[#8c9ba5] font-semibold uppercase cursor-pointer">Vol Floor ($/min)</label>
            <div className="relative">
              <span className="absolute left-2 top-2 text-gray-500 text-xs" aria-hidden="true">$</span>
              <input
                id="vol-floor-input"
                aria-label="Volatility floor threshold in dollars per minute"
                type="number"
                step="1.0"
                min="2.0"
                max="30.0"
                value={params.volatility_floor || 10.0}
                onChange={(e) => handleChange('volatility_floor', parseFloat(e.target.value))}
                className="w-full bg-[#0a0c10] border border-[#262d35] rounded-lg p-2 pl-5 text-white text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
              />
            </div>
            <span className="text-[8px] text-gray-500 block">Dead Chop Veto</span>
          </div>

          <div className="space-y-1">
            <label htmlFor="vol-ceiling-input" className="text-[9px] text-[#8c9ba5] font-semibold uppercase cursor-pointer">Vol Ceiling ($/min)</label>
            <div className="relative">
              <span className="absolute left-2 top-2 text-gray-500 text-xs" aria-hidden="true">$</span>
              <input
                id="vol-ceiling-input"
                aria-label="Volatility ceiling threshold in dollars per minute"
                type="number"
                step="1.0"
                min="20.0"
                max="200.0"
                value={params.volatility_ceiling || 45.0}
                onChange={(e) => handleChange('volatility_ceiling', parseFloat(e.target.value))}
                className="w-full bg-[#0a0c10] border border-[#262d35] rounded-lg p-2 pl-5 text-white text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
              />
            </div>
            <span className="text-[8px] text-gray-500 block">Chaos / News Veto</span>
          </div>
        </div>
      </div>
    </div>
  );
};
