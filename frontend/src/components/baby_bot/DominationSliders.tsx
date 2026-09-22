import React from 'react';
import { Sliders } from 'lucide-react';
import { soundFX } from '../../utils/audioFX';

interface DominationSlidersProps {
  botParams: Record<string, any>;
  setBotParams: React.Dispatch<React.SetStateAction<Record<string, any>>>;
  activeAssetKey: string;
}

export const DominationSliders: React.FC<DominationSlidersProps> = ({
  botParams,
  setBotParams,
  activeAssetKey,
}) => {
  return (
              <div className="space-y-3.5">
                {/* Header Banner */}
                <div className="p-2.5 rounded-lg bg-gradient-to-r from-emerald-950/40 via-cyan-950/30 to-slate-900 border border-emerald-500/30 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-emerald-400" />
                    <div>
                      <div className="text-[11px] font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                        <span>3-STEP DOMINION V3.2</span>
                        <span className="px-1.5 py-0.2 rounded text-[9px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-mono">
                          QUANT EV SLIDERS
                        </span>
                      </div>
                      <div className="text-[9px] text-slate-400">
                        Institutional Maker Discount Hunter · Microstructure EV Armor · 4-Pillar Harvest Engine
                      </div>
                    </div>
                  </div>
                  <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-bold">
                    EARLY MORNING SWEETSPOTS ACTIVE
                  </span>
                </div>

                {/* DIAL 1: Discount Maker Limit Ceiling Slider ($0.15 - $0.65) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-emerald-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block animate-pulse" />
                      Dial 1: Maker Limit Price Ceiling ($0.15 - $0.65)
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-emerald-500/40 z-50 shadow-2xl leading-snug">
                          <b>Institutional Maker Sniper:</b><br />
                          • <i>What is the maximum price you will pay?</i><br />
                          • Places resting maker orders on the Kalshi CLOB book with <b>$0.00 Maker Fee</b>.<br />
                          • <b>51¢–52¢ Sweetspot:</b> Generates <b>+92% to +96% net ROI</b> on winning $1.00 payout with high fill rate.<br />
                          • Range adjustable up to $0.65 for fast market momentum catching.
                        </div>
                      </div>
                    </label>

                    <div className="flex items-center gap-2">
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-bold">
                        +{(((1 - (botParams.discount_limit_price ?? 0.51)) / (botParams.discount_limit_price ?? 0.51)) * 100).toFixed(0)}% NET ROI
                      </span>
                      <span className="text-xs font-mono font-bold text-emerald-300">
                        ${(botParams.discount_limit_price ?? 0.51).toFixed(2)} ({((botParams.discount_limit_price ?? 0.51) * 100).toFixed(0)}¢)
                      </span>
                    </div>
                  </div>

                  {/* Preset Pills */}
                  <div className="flex items-center gap-1">
                    <span className="text-[8px] font-mono text-slate-500 uppercase mr-1">PRESETS:</span>
                    <div className="grid grid-cols-6 gap-1 flex-1">
                      {[0.48, 0.52, 0.57, 0.62, 0.65, 0.68].map((preset) => {
                        const isCurrent = Math.abs((botParams.discount_limit_price ?? 0.48) - preset) < 0.005;
                        return (
                          <button
                            key={preset}
                            type="button"
                            onClick={() => {
                              soundFX.playClickSound();
                              setBotParams({
                                ...botParams,
                                discount_limit_price: preset,
                                entry_discount_depth: preset,
                                limit_price: preset,
                                limit_price_cents: Math.round(preset * 100),
                              });
                            }}
                            className={`py-1 rounded text-[9px] font-mono font-bold transition-all border cursor-pointer ${
                              isCurrent
                                ? 'bg-emerald-500/25 border-emerald-400 text-emerald-300 shadow-sm shadow-emerald-500/30'
                                : 'bg-[#10141a] border-[#222933] text-slate-400 hover:text-white hover:border-slate-600'
                            }`}
                          >
                            {(preset * 100).toFixed(0)}¢
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Slider Control */}
                  <div className="space-y-1">
                    <input
                      type="range"
                      min="0.15"
                      max="0.68"
                      step="0.01"
                      value={botParams.discount_limit_price ?? 0.48}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setBotParams({
                          ...botParams,
                          discount_limit_price: val,
                          entry_discount_depth: val,
                          limit_price: val,
                          limit_price_cents: Math.round(val * 100),
                        });
                      }}
                      className="w-full accent-emerald-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                    />
                    <div className="flex justify-between text-[8px] text-slate-500 font-mono">
                      <span>$0.15 (Deep Value)</span>
                      <span className="text-emerald-400 font-semibold">$0.48–$0.57 (Winning Sweetspot)</span>
                      <span className="text-amber-400 font-bold">$0.68 Max Cap ($0.70 Hard Veto Wall)</span>
                    </div>
                  </div>

                  {/* Asymmetric Risk/Reward Matrix */}
                  <div className="grid grid-cols-4 gap-1.5 bg-[#0e1318] border border-[#1e2530] rounded p-1.5 text-center">
                    <div>
                      <div className="text-[8px] text-slate-400 font-semibold">MAX RISK</div>
                      <div className="text-[11px] font-mono font-bold text-rose-400">
                        {((botParams.discount_limit_price ?? 0.51) * 100).toFixed(0)}¢
                      </div>
                    </div>
                    <div>
                      <div className="text-[8px] text-slate-400 font-semibold">MAX PROFIT</div>
                      <div className="text-[11px] font-mono font-bold text-emerald-400">
                        {((1 - (botParams.discount_limit_price ?? 0.51)) * 100).toFixed(0)}¢
                      </div>
                    </div>
                    <div>
                      <div className="text-[8px] text-slate-400 font-semibold">PAYOUT ROI</div>
                      <div className="text-[11px] font-mono font-bold text-amber-300">
                        {(((1 - (botParams.discount_limit_price ?? 0.51)) / (botParams.discount_limit_price ?? 0.51))).toFixed(2)}x
                      </div>
                    </div>
                    <div>
                      <div className="text-[8px] text-slate-400 font-semibold">MAKER FEE</div>
                      <div className="text-[11px] font-mono font-bold text-cyan-400">
                        $0.00
                      </div>
                    </div>
                  </div>
                </div>

                {/* DIAL 2: Net Expected Value Hurdle (min_ev_dollars) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2 relative">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-indigo-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-indigo-400 inline-block animate-pulse" />
                      Dial 2: Min Net Expected Value Hurdle ($/ct)
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-indigo-500/40 z-50 shadow-2xl leading-snug">
                          <b>Statistical Profit Gate:</b><br />
                          • EV = P(win) × ($1.00 - Price) - P(loss) × Price - Fees.<br />
                          • <b>+$0.02 to +$0.03 Sweetspot:</b> Requires a net expected edge before risking capital. Rejects coin flips and low-margin noise bets.<br />
                          • <b>Dynamic Scaling:</b> Entry Ceiling dynamically scales up to $0.62 when model conviction exceeds required P_win!
                        </div>
                      </div>
                    </label>
                    <div className="flex items-center gap-1.5">
                      <span className="text-[8px] font-mono px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 font-bold">
                        LINKED TO DIAL 1
                      </span>
                      <span className="text-xs font-mono font-bold text-indigo-300">
                        +${(botParams.min_ev_dollars ?? botParams.min_ev_hurdle_dollars ?? 0.02).toFixed(2)} / ct
                      </span>
                    </div>
                  </div>

                  {/* Dynamic Linked EV Math Formula Banner */}
                  <div className="p-2 rounded bg-indigo-950/40 border border-indigo-500/30 flex items-center justify-between text-[9px] font-mono">
                    <div className="flex items-center gap-1.5 text-indigo-300">
                      <span className="text-amber-400 font-bold">⚡ LINKED MATH:</span>
                      <span className="text-slate-300">P_win Req:</span>
                      <span className="text-emerald-300 font-extrabold text-[10px]">
                        {(((botParams.discount_limit_price ?? 0.51) + (botParams.min_ev_dollars ?? botParams.min_ev_hurdle_dollars ?? 0.02)) * 100).toFixed(1)}%
                      </span>
                    </div>
                    <span className="text-indigo-400 font-bold text-[8px]">
                      (Dynamic Ceiling = P_win - ${(botParams.min_ev_dollars ?? botParams.min_ev_hurdle_dollars ?? 0.02).toFixed(2)})
                    </span>
                  </div>

                  <div className="space-y-1">
                    <input
                      type="range"
                      min="0.01"
                      max="0.20"
                      step="0.01"
                      value={botParams.min_ev_dollars ?? botParams.min_ev_hurdle_dollars ?? 0.02}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setBotParams({
                          ...botParams,
                          min_ev_dollars: val,
                          min_ev_hurdle_dollars: val,
                        });
                      }}
                      className="w-full accent-indigo-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                    />
                    <div className="flex justify-between text-[8px] text-slate-500 font-mono">
                      <span>+$0.01 (Minimal Gate)</span>
                      <span className="text-indigo-400 font-semibold">+$0.02–+$0.03 (Sweetspot Hurdle)</span>
                      <span>+$0.20 (Ultra-Strict Edge)</span>
                    </div>
                  </div>
                </div>

                {/* DIAL 3: Calibrated Win Probability / Conviction Slider */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-cyan-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-cyan-400 inline-block" />
                      Dial 3: Min Conviction Hurdle (Win Probability)
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-cyan-500/40 z-50 shadow-2xl leading-snug">
                          <b>Calibrated Model Conviction Gate:</b><br />
                          • Minimum calibrated AI probability score (50% - 95%) required to enter.<br />
                          • <b>81% Sweetspot:</b> Filters out low-confidence coin flips while capturing high-certainty institutional trends.
                        </div>
                      </div>
                    </label>
                    <span className="text-xs font-mono font-bold text-cyan-300">
                      {Math.round(((botParams.min_confidence ?? 0.81) > 1 ? (botParams.min_confidence ?? 81) : (botParams.min_confidence ?? 0.81) * 100))}% Conviction
                    </span>
                  </div>

                  <div className="space-y-1">
                    <input
                      type="range"
                      min="50"
                      max="95"
                      step="1"
                      value={Math.round(((botParams.min_confidence ?? 0.81) > 1 ? (botParams.min_confidence ?? 81) : (botParams.min_confidence ?? 0.81) * 100))}
                      onChange={(e) => {
                        const val = parseInt(e.target.value, 10);
                        setBotParams({
                          ...botParams,
                          min_confidence: val > 1 ? val / 100 : val,
                          confidence_threshold: val > 1 ? val / 100 : val,
                        });
                      }}
                      className="w-full accent-cyan-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                    />
                    <div className="flex justify-between text-[8px] text-slate-500 font-mono">
                      <span>50% (Coin-Flip)</span>
                      <span className="text-cyan-400 font-semibold">81% (Winning Sweetspot)</span>
                      <span>95% (Ultra-Hurdle)</span>
                    </div>
                  </div>
                </div>

                {/* DIAL 4: Spot Volatility Moat Buffer ($ / Strike Distance) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-purple-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-purple-400 inline-block" />
                      Dial 4: Spot Moat Buffer Zone (min_spot_diff)
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-purple-500/40 z-50 shadow-2xl leading-snug">
                          <b>Proximity Noise Armor:</b><br />
                          • <i>The Buffer Zone:</i> Refuses trades when Bitcoin is right on the strike line.<br />
                          • <b>$21.00 BTC Moat (1.36x Multiplier):</b> Keeps the bot away from 50/50 chop near the strike boundary.
                        </div>
                      </div>
                    </label>
                    <span className="text-xs font-mono font-bold text-purple-300">
                      ${(botParams.min_spot_diff ?? 21.0).toFixed(1)} Moat
                    </span>
                  </div>

                  <div className="space-y-1">
                    <input
                      type="range"
                      min="5"
                      max="60"
                      step="1"
                      value={botParams.min_spot_diff ?? 21.0}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setBotParams({
                          ...botParams,
                          min_spot_diff: val,
                          volatility_moat_dollars: val,
                        });
                      }}
                      className="w-full accent-purple-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                    />
                    <div className="flex justify-between text-[8px] text-slate-500 font-mono">
                      <span>$5.00 (Tight Pin)</span>
                      <span className="text-purple-400 font-semibold">$21.00 (Sweetspot Buffer)</span>
                      <span>$60.00 (Wide Safe Moat)</span>
                    </div>
                  </div>
                </div>

                {/* DIAL 5: VPIN Toxicity Cutoff Slider */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-rose-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-rose-400 inline-block" />
                      Dial 5: VPIN Shark Toxicity Veto Threshold
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-rose-500/40 z-50 shadow-2xl leading-snug">
                          <b>The Shark Detector:</b><br />
                          • Measures volume-synchronized probability of toxicity from institutional whales.<br />
                          • <b>0.60 Sweetspot:</b> Instantly vetoes orders when aggressive orderflow suggests toxic adverse selection.
                        </div>
                      </div>
                    </label>
                    <span className="text-xs font-mono font-bold text-rose-300">
                      {(botParams.vpin_toxic_threshold ?? 0.60).toFixed(2)} VPIN Max
                    </span>
                  </div>

                  <div className="space-y-1">
                    <input
                      type="range"
                      min="0.20"
                      max="0.85"
                      step="0.05"
                      value={botParams.vpin_toxic_threshold ?? 0.60}
                      onChange={(e) => setBotParams({ ...botParams, vpin_toxic_threshold: parseFloat(e.target.value) })}
                      className="w-full accent-rose-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                    />
                    <div className="flex justify-between text-[8px] text-slate-500 font-mono">
                      <span>0.20 (Ultra-Sensitive)</span>
                      <span className="text-rose-400 font-semibold">0.60 (Sweetspot Veto)</span>
                      <span>0.85 (Permissive)</span>
                    </div>
                  </div>
                </div>

                {/* DIAL 6: 4-Pillar Take Profit Ceiling & Trailing Ratchet Harvester */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-amber-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
                      Dial 6: 4-Pillar Harvest & Trailing Ratchet Controls
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-72 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-amber-500/40 z-50 shadow-2xl leading-snug">
                          <b>4-Pillar Harvest Engine:</b><br />
                          • <b>Take Profit Ceiling:</b> Locks in gains at 92¢ (+$41 profit on 51¢ entry).<br />
                          • <b>Trailing Ratchet:</b> Protects open gains with an 8¢ high-water mark buffer.<br />
                          • <b>Rev Gate vs 0-Delay:</b> Toggles requiring adverse reversal confirmation or instant limit exit.
                        </div>
                      </div>
                    </label>

                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => setBotParams({ ...botParams, require_reversal_for_tp_ceiling: !(botParams.require_reversal_for_tp_ceiling ?? false) })}
                        className={`text-[8px] font-bold px-1.5 py-0.5 rounded border transition-colors ${
                          (botParams.require_reversal_for_tp_ceiling ?? false)
                            ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-400'
                            : 'border-amber-500/40 bg-amber-500/10 text-amber-400'
                        }`}
                      >
                        {(botParams.require_reversal_for_tp_ceiling ?? false) ? '🛡️ REV GATE' : '⚡ 0-DELAY HARVEST'}
                      </button>
                      <button
                        type="button"
                        onClick={() => setBotParams({ ...botParams, enable_take_profit_ceiling: !(botParams.enable_take_profit_ceiling ?? true) })}
                        className={`text-[9px] font-bold px-1.5 py-0.5 rounded border transition-colors ${
                          (botParams.enable_take_profit_ceiling ?? true)
                            ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400'
                            : 'border-slate-700 bg-slate-800/40 text-slate-400'
                        }`}
                      >
                        {(botParams.enable_take_profit_ceiling ?? true) ? '🟢 ON' : '⚪ OFF'}
                      </button>
                    </div>
                  </div>

                  {/* Take Profit Ceiling Slider */}
                  <div className="space-y-1">
                    <div className="flex justify-between items-center text-[9px] font-mono text-slate-400">
                      <span>Take Profit Price Ceiling</span>
                      <span className="text-emerald-400 font-bold">${(botParams.take_profit_price_threshold ?? 0.92).toFixed(2)} ({((botParams.take_profit_price_threshold ?? 0.92) * 100).toFixed(0)}¢)</span>
                    </div>
                    <input
                      type="range"
                      min="0.70"
                      max="0.99"
                      step="0.01"
                      value={botParams.take_profit_price_threshold ?? 0.92}
                      onChange={(e) => setBotParams({ ...botParams, take_profit_price_threshold: parseFloat(e.target.value) })}
                      className="w-full accent-amber-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                    />
                    <div className="flex justify-between text-[8px] text-slate-500 font-mono">
                      <span>70¢ (Quick Scalp)</span>
                      <span className="text-amber-400 font-semibold">92¢ (Winning Sweetspot · 80%+ Gain)</span>
                      <span>99¢ (Full Expiration)</span>
                    </div>
                  </div>

                  {/* Trailing Buffer Slider */}
                  <div className="space-y-1 pt-1 border-t border-[#1e2530]">
                    <div className="flex justify-between items-center text-[9px] font-mono text-slate-400">
                      <span>Trailing High-Water Buffer</span>
                      <span className="text-cyan-400 font-bold">${(botParams.trailing_ratchet_buffer ?? 0.08).toFixed(2)} ({((botParams.trailing_ratchet_buffer ?? 0.08) * 100).toFixed(0)}¢)</span>
                    </div>
                    <input
                      type="range"
                      min="0.03"
                      max="0.20"
                      step="0.01"
                      value={botParams.trailing_ratchet_buffer ?? 0.08}
                      onChange={(e) => setBotParams({ ...botParams, trailing_ratchet_buffer: parseFloat(e.target.value) })}
                      className="w-full accent-cyan-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                    />
                    <div className="flex justify-between text-[8px] text-slate-500 font-mono">
                      <span>3¢ (Tight Trail)</span>
                      <span className="text-cyan-400 font-semibold">8¢ (Sweetspot Cushion)</span>
                      <span>20¢ (Wide Leash)</span>
                    </div>
                  </div>
                </div>

                {/* Secondary Microstructure & Execution Parameters Grid */}
                <div className="space-y-1.5 pt-1">
                  <div className="text-[9px] font-mono text-slate-400 uppercase tracking-wider font-bold">
                    SECONDARY MICROSTRUCTURE & DEFENSIVE GATES
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {/* Opening Quarantine */}
                    <div className="space-y-0.5 p-1.5 rounded bg-[#0a0d12] border border-[#1e242d]">
                      <div className="text-[8px] text-slate-400 flex items-center justify-between">
                        <span>Open Quarantine</span>
                        <span className="text-slate-500">⏱️</span>
                      </div>
                      <div className="flex items-center bg-[#10141a] border border-[#252c36] rounded px-1.5 py-0.5">
                        <input
                          type="number"
                          step="5"
                          min="0"
                          max="300"
                          value={botParams.opening_quarantine_seconds ?? 60.0}
                          onChange={(e) => setBotParams({ ...botParams, opening_quarantine_seconds: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-[11px]"
                        />
                        <span className="text-slate-500 text-[10px] ml-1">s</span>
                      </div>
                    </div>

                    {/* Spot Delta Front-Run Threshold */}
                    <div className="space-y-0.5 p-1.5 rounded bg-[#0a0d12] border border-[#1e242d]">
                      <div className="text-[8px] text-slate-400 flex items-center justify-between">
                        <span>Spot Front-Run Δ*</span>
                        <span className="text-amber-400">⚡</span>
                      </div>
                      <div className="flex items-center bg-[#10141a] border border-[#252c36] rounded px-1.5 py-0.5">
                        <span className="text-slate-500 text-[10px] mr-1">$</span>
                        <input
                          type="number"
                          step="1.0"
                          min="0.1"
                          max="50"
                          value={botParams.spot_delta_front_run_threshold ?? (activeAssetKey === 'GOLD' ? 2.50 : activeAssetKey === 'DOGE' ? 0.0005 : activeAssetKey === 'ETH' ? 2.50 : activeAssetKey === 'SOL' ? 0.50 : activeAssetKey === 'HYPER' ? 0.33 : 28.0)}
                          onChange={(e) => setBotParams({ ...botParams, spot_delta_front_run_threshold: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-[11px]"
                        />
                      </div>
                    </div>

                    {/* Silas TWAP Sniper Ceiling */}
                    <div className="space-y-0.5 p-1.5 rounded bg-[#0a0d12] border border-[#1e242d]">
                      <div className="text-[8px] text-slate-400 flex items-center justify-between">
                        <span>TWAP Sniper Ceiling</span>
                        <span className="text-cyan-400">🎯</span>
                      </div>
                      <div className="flex items-center bg-[#10141a] border border-[#252c36] rounded px-1.5 py-0.5">
                        <span className="text-slate-500 text-[10px] mr-1">$</span>
                        <input
                          type="number"
                          step="0.01"
                          min="0.50"
                          max="0.95"
                          value={botParams.twap_immutability_sniper_cents ?? (activeAssetKey === 'DOGE' ? 0.70 : (activeAssetKey === 'SOL' || activeAssetKey === 'HYPER') ? 0.72 : 0.75)}
                          onChange={(e) => setBotParams({ ...botParams, twap_immutability_sniper_cents: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-[11px]"
                        />
                      </div>
                    </div>

                    {/* Max CLOB Spread Corridor */}
                    <div className="space-y-0.5 p-1.5 rounded bg-[#0a0d12] border border-[#1e242d]">
                      <div className="text-[8px] text-slate-400 flex items-center justify-between">
                        <span>Max Spread Cap</span>
                        <span className="text-emerald-400">📏</span>
                      </div>
                      <div className="flex items-center bg-[#10141a] border border-[#252c36] rounded px-1.5 py-0.5">
                        <span className="text-slate-500 text-[10px] mr-1">$</span>
                        <input
                          type="number"
                          step="0.01"
                          min="0.01"
                          max="0.25"
                          value={botParams.max_clob_spread_cents ?? (activeAssetKey === 'DOGE' ? 0.03 : activeAssetKey === 'ETH' ? 0.04 : activeAssetKey === 'SOL' ? 0.06 : 0.05)}
                          onChange={(e) => setBotParams({ ...botParams, max_clob_spread_cents: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-[11px]"
                        />
                      </div>
                    </div>

                    {/* Min Take Profit ROI % */}
                    <div className="space-y-0.5 p-1.5 rounded bg-[#0a0d12] border border-[#1e242d]">
                      <div className="text-[8px] text-slate-400 flex items-center justify-between">
                        <span>Min Harvest ROI</span>
                        <span className="text-emerald-400">%</span>
                      </div>
                      <div className="flex items-center bg-[#10141a] border border-[#252c36] rounded px-1.5 py-0.5">
                        <input
                          type="number"
                          step="5"
                          min="5"
                          max="100"
                          value={botParams.min_take_profit_roi ?? 40.0}
                          onChange={(e) => setBotParams({ ...botParams, min_take_profit_roi: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-[11px]"
                        />
                        <span className="text-slate-500 text-[10px] ml-1">%</span>
                      </div>
                    </div>

                    {/* Reversal Trigger Threshold */}
                    <div className="space-y-0.5 p-1.5 rounded bg-[#0a0d12] border border-[#1e242d]">
                      <div className="text-[8px] text-slate-400 flex items-center justify-between">
                        <span>Reversal Trigger</span>
                        <span className="text-rose-400">🛡️</span>
                      </div>
                      <div className="flex items-center bg-[#10141a] border border-[#252c36] rounded px-1.5 py-0.5">
                        <input
                          type="number"
                          step="1"
                          min="50"
                          max="99"
                          value={botParams.reverse_indicator_threshold ?? 85.0}
                          onChange={(e) => setBotParams({ ...botParams, reverse_indicator_threshold: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-[11px]"
                        />
                        <span className="text-slate-500 text-[10px] ml-1">%</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
  );
};
