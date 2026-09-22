import React from 'react';
import { Sliders, Brain } from 'lucide-react';
import { soundFX } from '../../utils/audioFX';

interface MacroDominionDialsProps {
  botParams: Record<string, any>;
  setBotParams: React.Dispatch<React.SetStateAction<Record<string, any>>>;
}

export const MacroDominionDials: React.FC<MacroDominionDialsProps> = ({
  botParams,
  setBotParams,
}) => {
  return (
              <div className="space-y-3.5">
                {/* Header Banner */}
                <div className="p-2.5 rounded-lg bg-gradient-to-r from-cyan-950/40 via-teal-950/30 to-slate-900 border border-cyan-500/30 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-cyan-400" />
                    <div>
                      <div className="text-[11px] font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                        <span>MACRO TREND DOMINION</span>
                        <span className="px-1.5 py-0.2 rounded text-[9px] bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-mono">
                          9 DIALS COCKPIT
                        </span>
                      </div>
                      <div className="text-[9px] text-slate-400">
                        15M Triple-Brain Consensus · 1¢–89¢ Sweetspot · Online Mistake Learning
                      </div>
                    </div>
                  </div>
                  <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                    SWEETSPOTS ACTIVE
                  </span>
                </div>

                {/* DIAL 1: Macro Consensus Agreement (min_macro_agreement) */}
                <div className="space-y-1.5 p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d]">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-cyan-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-cyan-400 inline-block animate-pulse" />
                      Dial 1: 1H Macro Trend & HMM Agreement
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-cyan-500/40 z-50 shadow-2xl leading-snug">
                          <b>Higher-Timeframe Alignment Filter:</b><br />
                          • <b>Strict Consensus (Sweetspot):</b> Demands 1-Hour Spot Trend and 5m HMM Markov Regime agree before taking directional trades.<br />
                          • <b>Why it matters:</b> Eliminates taking counter-trend bets into dominant institutional flow.
                        </div>
                      </div>
                    </label>
                    <span className="text-[9px] font-mono text-cyan-400 font-bold">
                      {botParams.min_macro_agreement !== false ? 'STRICT CONSENSUS' : 'ALLOW DIVERGENCE'}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-1.5">
                    {[
                      { val: true, label: 'Strict Consensus', badge: 'Sweetspot', desc: '1H Spot & HMM Must Agree' },
                      { val: false, label: 'Allow Divergence', badge: 'Aggressive', desc: 'Trade on ONNX alone' },
                    ].map((opt) => {
                      const isActive = (botParams.min_macro_agreement !== false) === opt.val;
                      return (
                        <button
                          key={String(opt.val)}
                          type="button"
                          onClick={() => {
                            soundFX.playClickSound();
                            setBotParams({ ...botParams, min_macro_agreement: opt.val });
                          }}
                          className={`p-2 rounded border text-left transition-all cursor-pointer ${
                            isActive
                              ? 'bg-cyan-500/15 border-cyan-400 text-white shadow-lg shadow-cyan-500/10 ring-1 ring-cyan-400/40'
                              : 'bg-[#10141b] border-[#222933] text-slate-400 hover:border-slate-600 hover:text-slate-200'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-bold">{opt.label}</span>
                            <span className={`text-[8px] font-mono px-1 rounded ${
                              isActive ? 'bg-cyan-400/20 text-cyan-300 font-semibold' : 'bg-slate-800 text-slate-400'
                            }`}>
                              {opt.badge}
                            </span>
                          </div>
                          <div className="text-[8px] text-slate-400 mt-0.5 truncate">{opt.desc}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* DIAL 2: HMM Risk-Off Regime Veto (enable_hmm_risk_off_veto) */}
                <div className="space-y-1.5 p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d]">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-amber-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
                      Dial 2: 5m HMM Risk-Off Veto
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-amber-500/40 z-50 shadow-2xl leading-snug">
                          <b>Markov Volatility Protection:</b><br />
                          • <b>Veto Active (Sweetspot):</b> Hard stop on trading when HMM enters RISK_OFF, high volatility entropy, or unanchored churn.<br />
                          • <b>Why it matters:</b> Prevents catastrophic drawdown during unpredictable regime transitions.
                        </div>
                      </div>
                    </label>
                    <span className="text-[9px] font-mono text-amber-400 font-bold">
                      {botParams.enable_hmm_risk_off_veto !== false ? 'VETO ACTIVE' : 'VETO BYPASSED'}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-1.5">
                    {[
                      { val: true, label: 'Veto Active', badge: 'Sweetspot', desc: 'Halt in RISK_OFF / Churn' },
                      { val: false, label: 'Bypass Veto', badge: 'Risky', desc: 'Ignore Markov regime' },
                    ].map((opt) => {
                      const isActive = (botParams.enable_hmm_risk_off_veto !== false) === opt.val;
                      return (
                        <button
                          key={String(opt.val)}
                          type="button"
                          onClick={() => {
                            soundFX.playClickSound();
                            setBotParams({ ...botParams, enable_hmm_risk_off_veto: opt.val });
                          }}
                          className={`p-2 rounded border text-left transition-all cursor-pointer ${
                            isActive
                              ? 'bg-amber-500/15 border-amber-400 text-white shadow ring-1 ring-amber-400/40'
                              : 'bg-[#10141b] border-[#222933] text-slate-400 hover:border-slate-600 hover:text-slate-200'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-bold">{opt.label}</span>
                            <span className={`text-[8px] font-mono px-1 rounded ${
                              isActive ? 'bg-amber-400/20 text-amber-300 font-semibold' : 'bg-slate-800 text-slate-400'
                            }`}>
                              {opt.badge}
                            </span>
                          </div>
                          <div className="text-[8px] text-slate-400 mt-0.5 truncate">{opt.desc}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* DIAL 3: Calibrated Win Probability Hurdle (min_confidence / confidence_threshold) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-cyan-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-cyan-400 inline-block" />
                      Dial 3: Calibrated Win Probability Hurdle
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-cyan-500/40 z-50 shadow-2xl leading-snug">
                          <b>Calibrated Conviction Gate:</b><br />
                          • Minimum calibrated AI probability score (0.50 - 0.95) to place resting order.<br />
                          • <b>65% Sweetspot:</b> Filters out low-conviction noise bets while capturing institutional trend cycles.
                        </div>
                      </div>
                    </label>
                    <span className="text-xs font-mono font-bold text-cyan-300">
                      {Math.round(((botParams.confidence_threshold ?? botParams.min_confidence ?? 0.65)) * 100)}% Conviction
                    </span>
                  </div>

                  <div className="space-y-1">
                    <input
                      type="range"
                      min="0.50"
                      max="0.95"
                      step="0.01"
                      value={botParams.confidence_threshold ?? botParams.min_confidence ?? 0.65}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setBotParams({ ...botParams, confidence_threshold: val, min_confidence: val });
                      }}
                      className="w-full accent-cyan-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                    />
                    <div className="flex justify-between text-[8px] text-slate-500 font-mono">
                      <span>50% (Coin-Flip)</span>
                      <span className="text-cyan-400 font-semibold">65% (Sweetspot)</span>
                      <span>95% (Ultra-Hurdle)</span>
                    </div>
                  </div>
                </div>

                {/* DIAL 4: Resting Limit Sweet Spot (limit_price_cents: 1¢ - 89¢) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-emerald-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" />
                      Dial 4: Resting Limit Sweet Spot (1¢–89¢)
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-emerald-500/40 z-50 shadow-2xl leading-snug">
                          <b>The Maker Limit Ceiling:</b><br />
                          • <i>What is the maximum price you will pay?</i><br />
                          • Places resting maker orders on Kalshi book with <b>$0.00 Maker Fee</b>.<br />
                          • <b>48¢–52¢ Sweetspot:</b> Generates <b>+92% to +108% net ROI</b> on winning $1.00 binary payout.<br />
                          • Parameter adjustable from 1¢ up to 89¢.
                        </div>
                      </div>
                    </label>

                    <div className="flex items-center gap-2">
                      <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-bold">
                        +{(((100 - (botParams.limit_price_cents ?? 52)) / (botParams.limit_price_cents ?? 52)) * 100).toFixed(0)}% ROI
                      </span>
                      <span className="text-xs font-mono font-bold text-emerald-300">
                        {botParams.limit_price_cents ?? 52}¢ (${((botParams.limit_price_cents ?? 52) / 100).toFixed(2)})
                      </span>
                    </div>
                  </div>

                  {/* Range Slider (1 - 89 cents) */}
                  <div className="space-y-1">
                    <input
                      type="range"
                      min="1"
                      max="89"
                      step="1"
                      value={botParams.limit_price_cents ?? 52}
                      onChange={(e) => {
                        const val = parseInt(e.target.value, 10);
                        setBotParams({
                          ...botParams,
                          limit_price_cents: val,
                          limit_price: val / 100,
                          discount_limit_price: val / 100,
                          entry_discount_depth: val / 100,
                        });
                      }}
                      className="w-full accent-emerald-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                    />
                    <div className="flex justify-between text-[8px] text-slate-500 font-mono">
                      <span>1¢ (Deep Penny)</span>
                      <span className="text-emerald-400 font-semibold">48¢–52¢ (Sweetspot · +92% to +108% ROI)</span>
                      <span>89¢ (Max Cap)</span>
                    </div>
                  </div>

                  {/* Preset Pills */}
                  <div className="grid grid-cols-4 gap-1 pt-1">
                    {[
                      { cents: 35, label: '35¢ Deep' },
                      { cents: 48, label: '48¢ Maker' },
                      { cents: 52, label: '52¢ Sweet' },
                      { cents: 62, label: '62¢ Mom' },
                    ].map((p) => {
                      const isSel = (botParams.limit_price_cents ?? 52) === p.cents;
                      return (
                        <button
                          key={p.cents}
                          type="button"
                          onClick={() => {
                            soundFX.playClickSound();
                            setBotParams({
                              ...botParams,
                              limit_price_cents: p.cents,
                              limit_price: p.cents / 100,
                              discount_limit_price: p.cents / 100,
                              entry_discount_depth: p.cents / 100,
                            });
                          }}
                          className={`py-1 rounded text-[9px] font-mono font-bold transition-all border cursor-pointer ${
                            isSel
                              ? 'bg-emerald-500/20 text-emerald-300 border-emerald-400 shadow-sm'
                              : 'bg-[#10141a] text-slate-400 border-[#222933] hover:text-white'
                          }`}
                        >
                          {p.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* DIAL 5: Net Expected Value Hurdle (min_ev_dollars) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-indigo-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-indigo-400 inline-block" />
                      Dial 5: Net Expected Value Hurdle ($/ct)
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-indigo-500/40 z-50 shadow-2xl leading-snug">
                          <b>Expected Return Gate:</b><br />
                          • EV = P(win) * ($1 - Price) - P(loss) * Price - Fees.<br />
                          • <b>+$0.03 Sweetspot:</b> Rejects paper-thin edges; guarantees long-term statistical profitability.
                        </div>
                      </div>
                    </label>
                    <span className="text-xs font-mono font-bold text-indigo-300">
                      +${(botParams.min_ev_dollars ?? 0.03).toFixed(2)} / ct
                    </span>
                  </div>

                  <div className="flex items-center bg-[#10141a] border border-indigo-500/30 rounded px-2 py-1">
                    <span className="text-indigo-400 mr-1">$</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0.01"
                      max="0.25"
                      value={botParams.min_ev_dollars ?? 0.03}
                      onChange={(e) => setBotParams({ ...botParams, min_ev_dollars: parseFloat(e.target.value) })}
                      className="w-full bg-transparent text-white font-mono outline-none text-xs"
                    />
                  </div>
                </div>

                {/* DIAL 6: Adverse Selection Guard (adverse_selection_guard) */}
                <div className="space-y-1.5 p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d]">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-rose-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-rose-400 inline-block" />
                      Dial 6: Adverse Selection Guard
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-rose-500/40 z-50 shadow-2xl leading-snug">
                          <b>High-Velocity Spike Shield:</b><br />
                          • When Bitcoin spot velocity |ΔSpot| &gt; $15, protects against toxic fills by applying +$0.01 drift offset.<br />
                          • <b>Why it matters:</b> Prevents high-frequency bots from picking off resting limit orders ahead of crashes.
                        </div>
                      </div>
                    </label>
                    <span className="text-[9px] font-mono text-rose-400 font-bold">
                      {botParams.adverse_selection_guard !== false ? 'GUARD ACTIVE' : 'BYPASS'}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-1.5">
                    {[
                      { val: true, label: 'Guard Active', badge: '+$0.01 Shield', desc: 'Hold when |ΔSpot| > $15' },
                      { val: false, label: 'Bypass Guard', badge: 'No Offset', desc: 'Accept toxic fills' },
                    ].map((opt) => {
                      const isActive = (botParams.adverse_selection_guard !== false) === opt.val;
                      return (
                        <button
                          key={String(opt.val)}
                          type="button"
                          onClick={() => {
                            soundFX.playClickSound();
                            setBotParams({ ...botParams, adverse_selection_guard: opt.val });
                          }}
                          className={`p-2 rounded border text-left transition-all cursor-pointer ${
                            isActive
                              ? 'bg-rose-500/15 border-rose-400 text-white shadow ring-1 ring-rose-400/40'
                              : 'bg-[#10141b] border-[#222933] text-slate-400 hover:border-slate-600 hover:text-slate-200'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-bold">{opt.label}</span>
                            <span className={`text-[8px] font-mono px-1 rounded ${
                              isActive ? 'bg-rose-400/20 text-rose-300 font-semibold' : 'bg-slate-800 text-slate-400'
                            }`}>
                              {opt.badge}
                            </span>
                          </div>
                          <div className="text-[8px] text-slate-400 mt-0.5 truncate">{opt.desc}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* DIAL 7: Volatility Moat Multiplier (volatility_moat_multiplier) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-purple-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-purple-400 inline-block" />
                      Dial 7: Volatility Moat Multiplier
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-purple-500/40 z-50 shadow-2xl leading-snug">
                          <b>Dynamic Strike Buffer:</b><br />
                          • Multiplies base moat ($21 BTC) based on market volatility: ${(21.0 * (botParams.volatility_moat_multiplier ?? 1.20)).toFixed(2)} active buffer.<br />
                          • Refuses trades when Bitcoin is hovering too close to strike K at expiration.
                        </div>
                      </div>
                    </label>
                    <span className="text-xs font-mono font-bold text-purple-300">
                      {(botParams.volatility_moat_multiplier ?? 1.20).toFixed(2)}x (${(21.0 * (botParams.volatility_moat_multiplier ?? 1.20)).toFixed(2)})
                    </span>
                  </div>

                  <div className="space-y-1">
                    <input
                      type="range"
                      min="0.5"
                      max="3.0"
                      step="0.05"
                      value={botParams.volatility_moat_multiplier ?? 1.20}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setBotParams({ ...botParams, volatility_moat_multiplier: val, dynamic_moat_multiplier: val });
                      }}
                      className="w-full accent-purple-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                    />
                    <div className="flex justify-between text-[8px] text-slate-500 font-mono">
                      <span>0.5x ($10.50)</span>
                      <span className="text-purple-400 font-semibold">1.2x ($25.20 Sweetspot)</span>
                      <span>3.0x ($63.00 Heavy)</span>
                    </div>
                  </div>
                </div>

                {/* DIAL 8: Online Mistake Learning (enable_mistake_learning) */}
                <div className="space-y-1.5 p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d]">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-teal-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <Brain className="w-3.5 h-3.5 text-teal-400" />
                      Dial 8: Online Mistake-Learning Engine
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-teal-500/40 z-50 shadow-2xl leading-snug">
                          <b>Online Feedback Adaptation:</b><br />
                          • Records both Paper & Live cycle outcomes.<br />
                          • Dynamically applies Brier shrinkage to overconfident guesses and prunes persistent negative-EV deciles.
                        </div>
                      </div>
                    </label>
                    <span className="text-[9px] font-mono text-teal-400 font-bold">
                      {botParams.enable_mistake_learning !== false ? 'ONLINE LEARNING ACTIVE' : 'OFFLINE STATIC'}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-1.5">
                    {[
                      { val: true, label: 'Online Learning', badge: 'Paper & Live', desc: 'Calibrate after every cycle' },
                      { val: false, label: 'Static Mode', badge: 'No Learning', desc: 'Zero probability updates' },
                    ].map((opt) => {
                      const isActive = (botParams.enable_mistake_learning !== false) === opt.val;
                      return (
                        <button
                          key={String(opt.val)}
                          type="button"
                          onClick={() => {
                            soundFX.playClickSound();
                            setBotParams({ ...botParams, enable_mistake_learning: opt.val });
                          }}
                          className={`p-2 rounded border text-left transition-all cursor-pointer ${
                            isActive
                              ? 'bg-teal-500/15 border-teal-400 text-white shadow ring-1 ring-teal-400/40'
                              : 'bg-[#10141b] border-[#222933] text-slate-400 hover:border-slate-600 hover:text-slate-200'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-bold">{opt.label}</span>
                            <span className={`text-[8px] font-mono px-1 rounded ${
                              isActive ? 'bg-teal-400/20 text-teal-300 font-semibold' : 'bg-slate-800 text-slate-400'
                            }`}>
                              {opt.badge}
                            </span>
                          </div>
                          <div className="text-[8px] text-slate-400 mt-0.5 truncate">{opt.desc}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* DIAL 9: Brier Shrinkage Factor (brier_shrinkage_factor) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-teal-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-teal-400 inline-block" />
                      Dial 9: Mistake Shrinkage Factor (Brier Rate)
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-teal-500/40 z-50 shadow-2xl leading-snug">
                          <b>Overconfidence Dampener:</b><br />
                          • When a prediction fails at settlement, confidence is shrunk by this rate.<br />
                          • <b>0.15 Sweetspot:</b> Sufficient to avoid revenge trading streaks while maintaining responsiveness to trend changes.
                        </div>
                      </div>
                    </label>
                    <span className="text-xs font-mono font-bold text-teal-300">
                      {Math.round(((botParams.brier_shrinkage_factor ?? 0.15)) * 100)}% Shrinkage
                    </span>
                  </div>

                  <div className="space-y-1">
                    <input
                      type="range"
                      min="0.01"
                      max="0.50"
                      step="0.01"
                      value={botParams.brier_shrinkage_factor ?? 0.15}
                      onChange={(e) => setBotParams({ ...botParams, brier_shrinkage_factor: parseFloat(e.target.value) })}
                      className="w-full accent-teal-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                    />
                    <div className="flex justify-between text-[8px] text-slate-500 font-mono">
                      <span>1% (Minimal)</span>
                      <span className="text-teal-400 font-semibold">15% (Sweetspot)</span>
                      <span>50% (Heavy Dampening)</span>
                    </div>
                  </div>
                </div>
              </div>
  );
};
