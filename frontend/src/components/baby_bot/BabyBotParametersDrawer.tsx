import React from 'react';
import { Sliders, Lock, ShieldCheck, RefreshCw, Save, Zap, Brain } from 'lucide-react';
import { soundFX } from '../../utils/audioFX';
import { BotProfile } from './BabyBotProfiles';

export interface BabyBotParametersDrawerProps {
  isMacroDominion: boolean;
  activeProfile: BotProfile;
  botParams: Record<string, any>;
  setBotParams: React.Dispatch<React.SetStateAction<Record<string, any>>>;
  activeAssetKey: string;
  currentAtr: number;
  volFloor: number;
  volCeil: number;
  isSafeVol: boolean;
  isDeadChop: boolean;
  entryDiscount: number;
  maxWinRoi: string;
  tapeStreak: number;
  reqTapeTicks: number;
  isTapeConfirmed: boolean;
  saveSuccessMsg: string | null;
  isSavingParams: boolean;
  handleResetDefaults: () => void;
  handleSaveParameters: () => Promise<void> | void;
  handlePromoteToLive: () => Promise<void> | void;
}

export const BabyBotParametersDrawer: React.FC<BabyBotParametersDrawerProps> = ({
  isMacroDominion,
  activeProfile,
  botParams,
  setBotParams,
  activeAssetKey,
  currentAtr,
  volFloor,
  volCeil,
  isSafeVol,
  isDeadChop,
  entryDiscount,
  maxWinRoi,
  tapeStreak,
  reqTapeTicks,
  isTapeConfirmed,
  saveSuccessMsg,
  isSavingParams,
  handleResetDefaults,
  handleSaveParameters,
  handlePromoteToLive,
}) => {
  return (
          <div className="p-4 bg-[#12161a] border-t border-[#1f262d] space-y-3 font-mono text-xs">
            {isMacroDominion ? (
              /* MACRO TREND DOMINION — 9 STRATEGY DIALS COCKPIT */
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
            ) : activeProfile.telemetryType === 'onnx' ? (
              /* THE ONNX STRATEGY — 5 STRATEGY DIALS COCKPIT MATRIX */
              <div className="space-y-3.5">
                {/* Header Banner */}
                <div className="p-2.5 rounded-lg bg-gradient-to-r from-cyan-950/40 via-purple-950/30 to-slate-900 border border-cyan-500/30 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-cyan-400" />
                    <div>
                      <div className="text-[11px] font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                        <span>THE ONNX STRATEGY</span>
                        <span className="px-1.5 py-0.2 rounded text-[9px] bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-mono">
                          5 DIALS COCKPIT
                        </span>
                      </div>
                      <div className="text-[9px] text-slate-400">
                        Dual-Brain Spot Lead vs Kalshi Lag CLOB · Microstructure Arbitrage
                      </div>
                    </div>
                  </div>
                  <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    SWEETSPOTS ACTIVE
                  </span>
                </div>

                {/* DIAL 1: Brain Priority Mode (Full Width Segmented Selector) */}
                <div className="space-y-1.5 p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d]">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-cyan-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-cyan-400 inline-block animate-pulse" />
                      Dial 1: Brain Priority Mode
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-cyan-500/40 z-50 shadow-2xl leading-snug">
                          <b>Quant Arbitration Arbiter:</b><br />
                          • <b>Trend Aligned Scalp (Sweetspot):</b> QuoLas Binance Spot Microscope leads; Kalshi binary CLOB lags. Exploits directional momentum.<br />
                          • <b>Contradiction Sniper:</b> Strict divergence required. Spot and Kalshi must oppose to snipe mispriced discount contracts.<br />
                          • <b>Unanimous Consensus:</b> Both models must agree 100% on direction (ultra-safe).
                        </div>
                      </div>
                    </label>
                    <span className="text-[9px] font-mono text-cyan-400 font-bold">
                      {(botParams.brain_priority_mode || 'TREND_ALIGNED_SCALP').replace(/_/g, ' ')}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-1.5">
                    {[
                      {
                        mode: 'TREND_ALIGNED_SCALP',
                        label: 'Trend Scalp',
                        badge: 'Sweetspot',
                        desc: 'Spot Lead · CLOB Lag',
                      },
                      {
                        mode: 'CONTRADICTION_SNIPER',
                        label: 'Contradiction',
                        badge: 'Divergence',
                        desc: 'Discount Hunter',
                      },
                      {
                        mode: 'UNANIMOUS_CONSENSUS',
                        label: 'Consensus',
                        badge: 'Ultra-Safe',
                        desc: '100% Agreement',
                      },
                    ].map((opt) => {
                      const isActive = (botParams.brain_priority_mode || 'TREND_ALIGNED_SCALP') === opt.mode;
                      return (
                        <button
                          key={opt.mode}
                          type="button"
                          onClick={() => {
                            soundFX.playClickSound();
                            setBotParams({ ...botParams, brain_priority_mode: opt.mode });
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

                {/* DIAL 2: Micro-Bankroll Sizing Armor */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-amber-400 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <Lock className="w-3.5 h-3.5 text-amber-400" />
                      Dial 2: Sizing Mode & Bankroll Armor
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-amber-500/40 z-50 shadow-2xl leading-snug">
                          <b>Micro-Bankroll Sizing Armor:</b><br />
                          Enforces exactly 1 contract per trade for bankrolls &lt; $75 to guarantee zero drawdown blowup.<br />
                          Tier 1 (2 contracts) unlocks conditionally only when bankroll reaches $75+, AI confidence ≥ 75%, and Net EV ≥ +$0.06.
                        </div>
                      </div>
                    </label>
                    <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 font-bold flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3 text-amber-400" />
                      &lt; $75 ARMOR LOCKED
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div className="p-2 rounded border bg-amber-500/10 border-amber-500/40 text-amber-300 flex items-center justify-between">
                      <div>
                        <div className="text-[10px] font-bold flex items-center gap-1">
                          <Lock className="w-3 h-3 text-amber-400" />
                          TIER 0: STRICT 1-CT
                        </div>
                        <div className="text-[8px] text-amber-400/80">Micro-Bankroll Armor (Enforced)</div>
                      </div>
                      <span className="text-xs font-bold font-mono px-2 py-0.5 bg-amber-400 text-black rounded font-black">
                        1 CT
                      </span>
                    </div>

                    <div className="p-2 rounded border bg-[#0e1217] border-slate-800 text-slate-500 flex items-center justify-between opacity-60">
                      <div>
                        <div className="text-[10px] font-semibold flex items-center gap-1">
                          <span>TIER 1: CONVICTION 2-CT</span>
                        </div>
                        <div className="text-[8px] text-slate-500">Unlocks at &ge; $75 Bankroll</div>
                      </div>
                      <span className="text-[9px] font-mono px-1.5 py-0.5 bg-slate-800 text-slate-400 rounded">
                        LOCKED
                      </span>
                    </div>
                  </div>
                </div>

                {/* DIAL 3: Volatility Regime Window (Floor & Ceiling) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-purple-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-purple-400 inline-block" />
                      Dial 3: Volatility Regime Window (1m ATR)
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-purple-500/40 z-50 shadow-2xl leading-snug">
                          <b>Regime Window Protection:</b><br />
                          • <b>Floor ($10):</b> Dead chop shield. Refuses entry in flat, stationary order flow.<br />
                          • <b>Ceiling ($45):</b> News panic shield. Halts orders during violent spike chaos where adverse selection is extreme.
                        </div>
                      </div>
                    </label>

                    {/* Live ATR Badge */}
                    <div className="flex items-center gap-1.5">
                      <span className="text-[9px] font-mono text-slate-400">
                        1m ATR: <b className="text-white font-mono">${currentAtr.toFixed(1)}</b>
                      </span>
                      <span className={`text-[8px] font-mono px-1.5 py-0.5 rounded border font-bold ${
                        isSafeVol
                          ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                          : isDeadChop
                          ? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                          : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                      }`}>
                        {isSafeVol ? 'SAFE REGIME' : isDeadChop ? 'CHOP VETO' : 'PANIC VETO'}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <div className="text-[9px] text-slate-400 flex items-center justify-between">
                        <span>Floor (Dead Chop Cutoff)</span>
                        <span className="text-purple-400 font-mono">${volFloor.toFixed(0)}</span>
                      </div>
                      <div className="flex items-center bg-[#10141a] border border-purple-500/30 rounded px-2 py-1">
                        <span className="text-purple-400 mr-1">$</span>
                        <input
                          type="number"
                          step="1.0"
                          min="0"
                          max="50"
                          value={botParams.volatility_floor ?? 10.0}
                          onChange={(e) => setBotParams({ ...botParams, volatility_floor: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-xs"
                        />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="text-[9px] text-slate-400 flex items-center justify-between">
                        <span>Ceiling (News Spike Cutoff)</span>
                        <span className="text-purple-400 font-mono">${volCeil.toFixed(0)}</span>
                      </div>
                      <div className="flex items-center bg-[#10141a] border border-purple-500/30 rounded px-2 py-1">
                        <span className="text-purple-400 mr-1">$</span>
                        <input
                          type="number"
                          step="1.0"
                          min="20"
                          max="200"
                          value={botParams.volatility_ceiling ?? 45.0}
                          onChange={(e) => setBotParams({ ...botParams, volatility_ceiling: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-xs"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* DIAL 4: Entry Discount Depth Ceiling ($0.35 - $0.65) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-cyan-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-cyan-400 inline-block" />
                      Dial 4: Entry Discount Depth Ceiling ($0.35 - $0.65)
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-cyan-500/40 z-50 shadow-2xl leading-snug">
                          <b>Asymmetric Discount Hunter:</b><br />
                          Resting maker order price ceiling (e.g. $0.48, max $0.65).<br />
                          • Guarantees <b>$0.00 Maker Fee</b> on Kalshi.<br />
                          • At $0.48 entry, winning $1.00 binary yields <b>+{maxWinRoi}% net ROI</b>.<br />
                          • Up to <b>$0.65</b> ceiling allows capturing fills during rapid momentum shifts.
                        </div>
                      </div>
                    </label>

                    <div className="flex items-center gap-2">
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-bold">
                        +{maxWinRoi}% MAX ROI
                      </span>
                      <span className="text-xs font-mono font-bold text-cyan-300">
                        ${entryDiscount.toFixed(2)} ({(entryDiscount * 100).toFixed(0)}¢)
                      </span>
                    </div>
                  </div>

                  {/* Slider Control */}
                  <div className="space-y-1">
                    <input
                      type="range"
                      min="0.35"
                      max="0.65"
                      step="0.01"
                      value={entryDiscount}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setBotParams({
                          ...botParams,
                          entry_discount_depth: val,
                          discount_limit_price: val,
                        });
                      }}
                      className="w-full accent-cyan-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                    />
                    <div className="flex justify-between text-[8px] text-slate-500 font-mono">
                      <span>$0.35 (Deep Discount · +185% ROI)</span>
                      <span className="text-cyan-400 font-semibold">$0.48 (Sweetspot · +108% ROI)</span>
                      <span>$0.65 (Maker Ceiling Max · +54% ROI)</span>
                    </div>
                  </div>
                </div>

                {/* DIAL 5: Orderflow Tape Confirmation (Anti-Spoofing Shield) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-indigo-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-indigo-400 inline-block" />
                      Dial 5: Orderflow Tape Confirmation
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-indigo-500/40 z-50 shadow-2xl leading-snug">
                          <b>Anti-Spoofing Tape Shield:</b><br />
                          Requires consecutive confirmed market trade prints in the directional impulse before placing orders.<br />
                          Filters out phantom ghost bids and resting order spoofing.
                        </div>
                      </div>
                    </label>

                    {/* Streak indicator */}
                    <span className={`text-[9px] font-mono px-2 py-0.5 rounded border font-bold ${
                      isTapeConfirmed
                        ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                        : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                    }`}>
                      {tapeStreak} / {reqTapeTicks} PRINTS CONFIRMED
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-1.5">
                    {[
                      { ticks: 1, label: '1 Tick', sub: 'Fast Entry' },
                      { ticks: 2, label: '2 Ticks', sub: 'Sweetspot (300ms)' },
                      { ticks: 3, label: '3 Ticks', sub: 'Heavy Armor' },
                    ].map((opt) => {
                      const isSel = (botParams.tape_confirmation_ticks ?? 2) === opt.ticks;
                      return (
                        <button
                          key={opt.ticks}
                          type="button"
                          onClick={() => {
                            soundFX.playClickSound();
                            setBotParams({ ...botParams, tape_confirmation_ticks: opt.ticks });
                          }}
                          className={`p-1.5 rounded border text-center transition-all cursor-pointer ${
                            isSel
                              ? 'bg-indigo-500/20 border-indigo-400 text-white shadow ring-1 ring-indigo-400/40'
                              : 'bg-[#10141a] border-[#222933] text-slate-400 hover:text-white'
                          }`}
                        >
                          <div className="text-[10px] font-bold">{opt.label}</div>
                          <div className="text-[8px] text-slate-400">{opt.sub}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Secondary Pre-Flight Guardrails Grid */}
                <div className="space-y-1.5 pt-1">
                  <div className="text-[9px] font-mono text-slate-400 uppercase tracking-wider font-bold">
                    PRE-FLIGHT GUARDRAILS & EV THRESHOLDS
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {/* Taker Cross EV Gate */}
                    <div className="space-y-0.5 p-1.5 rounded bg-[#0a0d12] border border-[#1e242d]">
                      <div className="text-[8px] text-slate-400">Taker Cross EV</div>
                      <div className="flex items-center bg-[#10141a] border border-[#252c36] rounded px-1.5 py-0.5">
                        <span className="text-slate-500 text-[10px] mr-1">$</span>
                        <input
                          type="number"
                          step="0.01"
                          min="0.01"
                          max="0.30"
                          value={botParams.taker_cross_ev_threshold ?? 0.08}
                          onChange={(e) => setBotParams({ ...botParams, taker_cross_ev_threshold: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-[11px]"
                        />
                      </div>
                    </div>

                    {/* Dynamic Moat Multiplier */}
                    <div className="space-y-0.5 p-1.5 rounded bg-[#0a0d12] border border-[#1e242d]">
                      <div className="text-[8px] text-slate-400">Dynamic Moat</div>
                      <div className="flex items-center bg-[#10141a] border border-[#252c36] rounded px-1.5 py-0.5">
                        <input
                          type="number"
                          step="0.05"
                          min="0.5"
                          max="2.5"
                          value={botParams.dynamic_moat_multiplier ?? 1.15}
                          onChange={(e) => setBotParams({ ...botParams, dynamic_moat_multiplier: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-[11px]"
                        />
                        <span className="text-slate-500 text-[10px] ml-1">x</span>
                      </div>
                    </div>

                    {/* Min Conviction */}
                    <div className="space-y-0.5 p-1.5 rounded bg-[#0a0d12] border border-[#1e242d]">
                      <div className="text-[8px] text-slate-400">Min Conviction</div>
                      <div className="flex items-center bg-[#10141a] border border-[#252c36] rounded px-1.5 py-0.5">
                        <input
                          type="number"
                          step="0.01"
                          min="0.50"
                          max="0.99"
                          value={botParams.min_confidence ?? 0.81}
                          onChange={(e) => setBotParams({ ...botParams, min_confidence: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-[11px]"
                        />
                      </div>
                    </div>

                    {/* Min EV */}
                    <div className="space-y-0.5 p-1.5 rounded bg-[#0a0d12] border border-[#1e242d]">
                      <div className="text-[8px] text-slate-400">Min Net EV</div>
                      <div className="flex items-center bg-[#10141a] border border-[#252c36] rounded px-1.5 py-0.5">
                        <span className="text-slate-500 text-[10px] mr-1">$</span>
                        <input
                          type="number"
                          step="0.01"
                          min="0.01"
                          max="0.50"
                          value={botParams.min_ev_dollars ?? 0.02}
                          onChange={(e) => setBotParams({ ...botParams, min_ev_dollars: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-[11px]"
                        />
                      </div>
                    </div>

                    {/* VPIN Cutoff */}
                    <div className="space-y-0.5 p-1.5 rounded bg-[#0a0d12] border border-[#1e242d]">
                      <div className="text-[8px] text-slate-400">VPIN Shark Veto</div>
                      <div className="flex items-center bg-[#10141a] border border-[#252c36] rounded px-1.5 py-0.5">
                        <input
                          type="number"
                          step="0.05"
                          min="0.10"
                          max="0.95"
                          value={botParams.vpin_toxic_threshold ?? 0.60}
                          onChange={(e) => setBotParams({ ...botParams, vpin_toxic_threshold: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-[11px]"
                        />
                      </div>
                    </div>

                    {/* Take Profit Price */}
                    <div className="space-y-0.5 p-1.5 rounded bg-[#0a0d12] border border-[#1e242d]">
                      <div className="text-[8px] text-slate-400">Take Profit Cap</div>
                      <div className="flex items-center bg-[#10141a] border border-[#252c36] rounded px-1.5 py-0.5">
                        <span className="text-slate-500 text-[10px] mr-1">$</span>
                        <input
                          type="number"
                          step="0.01"
                          min="0.50"
                          max="0.99"
                          value={botParams.take_profit_price_threshold ?? 0.92}
                          onChange={(e) => setBotParams({ ...botParams, take_profit_price_threshold: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-[11px]"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              /* 3-STEP DOMINION — INSTITUTIONAL EV & SLIDER COCKPIT */
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
                      {[0.35, 0.40, 0.45, 0.48, 0.51, 0.52].map((preset) => {
                        const isCurrent = Math.abs((botParams.discount_limit_price ?? 0.51) - preset) < 0.005;
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
                      max="0.65"
                      step="0.01"
                      value={botParams.discount_limit_price ?? 0.51}
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
                      <span>$0.15 (Deep Value · +567% ROI)</span>
                      <span className="text-emerald-400 font-semibold">$0.51–$0.52 (Winning Sweetspot · +96% ROI)</span>
                      <span>$0.65 (Momentum Cap · +54% ROI)</span>
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
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-indigo-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-indigo-400 inline-block" />
                      Dial 2: Min Net Expected Value Hurdle ($/ct)
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-indigo-500/40 z-50 shadow-2xl leading-snug">
                          <b>Statistical Profit Gate:</b><br />
                          • EV = P(win) × ($1.00 - Price) - P(loss) × Price - Fees.<br />
                          • <b>+$0.02 to +$0.03 Sweetspot:</b> Requires a net expected edge before risking capital. Rejects coin flips and low-margin noise bets.
                        </div>
                      </div>
                    </label>
                    <span className="text-xs font-mono font-bold text-indigo-300">
                      +${(botParams.min_ev_dollars ?? 0.02).toFixed(2)} / ct
                    </span>
                  </div>

                  <div className="space-y-1">
                    <input
                      type="range"
                      min="0.01"
                      max="0.20"
                      step="0.01"
                      value={botParams.min_ev_dollars ?? 0.02}
                      onChange={(e) => setBotParams({ ...botParams, min_ev_dollars: parseFloat(e.target.value) })}
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
            )}

            {/* Footer with Reset Defaults & Apply & Save */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2 border-t border-[#1f262d]">
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-[#8c9ba5] flex items-center gap-1">
                  <span>Target:</span>
                  <span className="text-white font-semibold">{activeProfile.name}</span>
                </span>
                {saveSuccessMsg && (
                  <span className="text-[10px] font-mono text-emerald-400 font-bold animate-pulse">
                    {saveSuccessMsg}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleResetDefaults}
                  type="button"
                  title="Reset to recommended quant sweetspots"
                  className="px-2.5 py-1.5 rounded bg-[#171c22] hover:bg-[#222933] text-amber-300 hover:text-amber-200 border border-amber-500/30 text-[10px] font-bold transition-all cursor-pointer flex items-center gap-1"
                >
                  <span>🎯</span>
                  <span>{activeProfile.telemetryType === 'macro_dominion' ? 'Reset Macro Sweetspots' : activeProfile.telemetryType === 'onnx' ? 'Reset Quant Sweetspots' : 'Sweetspots Preset'}</span>
                </button>
                <button
                  onClick={handleSaveParameters}
                  disabled={isSavingParams}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#00bda5] text-black font-bold text-xs hover:bg-[#2dd4bf] transition-all shadow cursor-pointer disabled:opacity-50"
                >
                  {isSavingParams ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                  <span>{activeProfile.telemetryType === 'macro_dominion' || activeProfile.telemetryType === 'onnx' ? 'Apply Strategy Dials' : 'Apply & Save as Default'}</span>
                </button>

                <button
                  onClick={handlePromoteToLive}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-red-600 text-white font-bold text-xs hover:bg-red-500 transition-all shadow cursor-pointer"
                >
                  <Zap className="w-3.5 h-3.5" />
                  <span>PROMOTE TO LIVE</span>
                </button>
              </div>
            </div>
          </div>
  );
};
