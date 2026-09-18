import React from 'react';
import { Sliders, Lock, ShieldCheck } from 'lucide-react';
import { soundFX } from '../../utils/audioFX';

interface DualOnnxDialsProps {
  botParams: Record<string, any>;
  setBotParams: React.Dispatch<React.SetStateAction<Record<string, any>>>;
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
}

export const DualOnnxDials: React.FC<DualOnnxDialsProps> = ({
  botParams,
  setBotParams,
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
}) => {
  return (
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
  );
};
