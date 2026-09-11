import React, { useState, useEffect } from 'react';
import {
  Cpu,
  Layers,
  Shield,
  Activity,
  Save,
  RefreshCw,
  Clock,
  Zap,
  Sliders,
  Check,
  AlertTriangle,
  Flame,
  Info,
  X,
} from 'lucide-react';

interface StrategyParameters {
  strategy_id?: string;
  strategy_name?: string;
  brain_priority_mode?: string;
  contract_scaling_mode?: string;
  entry_discount_depth?: number;
  discount_limit_price?: number;
  momentum_max_price?: number;
  min_confidence?: number;
  min_ev_dollars?: number;
  taker_cross_ev_threshold?: number;
  max_temporal_skew_ms?: number;
  gamma_cliff_seconds?: number;
  auto_cancel_on_veto?: boolean;
  dynamic_volatility_mode?: string;
  volatility_floor?: number;
  volatility_ceiling?: number;
  vpin_toxic_threshold?: number;
  dynamic_moat_multiplier?: number;
  current_atr?: number;
  cross_brain_skew_ms?: number;
  is_temporally_synced?: boolean;
  slower_brain?: string;
  hmm_regime?: string;
  max_contracts?: number;
  [key: string]: any;
}

interface ParamDoc {
  title: string;
  symbol: string;
  formula: string;
  mechanism: string;
  recommendation: string;
  warning: string;
}

const PARAM_DOCS: Record<string, ParamDoc> = {
  brain_priority: {
    title: 'Brain Priority Arbitration Mode',
    symbol: 'B_mode ∈ {TREND_ALIGNED_SCALP, SPOT_DOMINANT, KALSHI_DOMINANT, CONSERVATIVE_CROSS}',
    formula: 'Decision = f(QuoLas_Spot, Kalshi_CLOB, Mode)\nTREND_ALIGNED_SCALP: Spot Orderflow leads directional bias; Kalshi CLOB governs maker entry safety.',
    mechanism: 'Resolves conflicting signals between Brain 1 (Binance Spot aggTrade + L2) and Brain 2 (Kalshi L2 inside touch). In TREND_ALIGNED_SCALP, high-velocity spot momentum dictates directional bias while the Kalshi book confirms fill depth. CONSERVATIVE_CROSS enforces strict 100% agreement before any order submission.',
    recommendation: 'TREND_ALIGNED_SCALP (Default institutional lead-lag configuration).',
    warning: 'CONSERVATIVE_CROSS drastically lowers trade frequency (<1 trade/hour). KALSHI_DOMINANT exposes maker quotes to adverse selection from external spot price leads.'
  },
  sizing_armor: {
    title: 'Micro-Bankroll Sizing Armor',
    symbol: 'C_trade = min(1, Kelly(Edge)) ≤ C_max = 1',
    formula: 'C_size = 1 contract per 15M cycle (Hard Capped for Bankrolls < $75.00)',
    mechanism: 'Institutional risk preservation armor implementing Rule 1 Trading Invariants. Synchronously reserves in-flight intent locks and clamps contract size strictly to 1 contract, eliminating mathematical probability of gambler\'s ruin during initial bankroll building.',
    recommendation: 'TIER_0_STRICT_1 (Hard cap 1 contract, mandatory for bankrolls < $75).',
    warning: 'Attempting to increase contract count on micro-bankrolls violates quantitative invariants and will be rejected pre-trade by Agent Guardrails.'
  },
  min_confidence: {
    title: 'Neural Conviction Hurdle',
    symbol: 'P_min = 70.0% (Softmax Hurdle)',
    formula: 'max(P_QuoLas, P_Kalshi) ≥ P_min\nEmit HOLD if max(P_QuoLas, P_Kalshi) < P_min',
    mechanism: 'Minimum softmax probability threshold required from the ONNX neural networks before trade inception. Filters out ambiguous, low-conviction chop and ensures the strategy only deploys capital on high-probability directional regimes.',
    recommendation: '70% (Optimal balance between high win-rate and statistically sufficient cycle participation).',
    warning: 'Lowering below 65% exponentially increases false positive entries in choppy sideways markets.'
  },
  min_ev: {
    title: 'Minimum Expected Value (EV)',
    symbol: 'EV_min = +$0.02 / contract',
    formula: 'EV = P_win × ($1.00 - P_entry) - (1 - P_win) × P_entry - Fee ≥ EV_min',
    mechanism: 'Guarantees that every trade dispatched possesses positive mathematical expectancy net of CFTC-compliant Kalshi exchange taker/maker fee schedules ($0.00 maker, up to $0.02 taker).',
    recommendation: '+$0.02 (Ensures consistent positive drift over thousands of executed cycles).',
    warning: 'Setting EV_min ≤ $0.00 will cause negative compounding due to spread slippage and execution drag.'
  },
  entry_discount: {
    title: 'Entry Discount Depth (Maker Moat)',
    symbol: 'D_depth = $0.48 (Limit Price Ceiling)',
    formula: 'P_limit = min(FairValue - D_depth, BestBid)\nP_limit ≤ $0.48',
    mechanism: 'Locks in a maker fill discount by posting resting limit orders at or below $0.48. Rested orders receive $0.00 taker fee, capturing the full edge between contract payout ($1.00) and entry cost while securing a margin of safety.',
    recommendation: '$0.48 (Rests inside the touch below median $0.50 binary value).',
    warning: 'Setting above $0.55 degrades the favorable risk-to-reward asymmetry of the binary contract.'
  },
  momentum_max: {
    title: 'Momentum Max Price Ceiling',
    symbol: 'P_max_mom = $0.62 (Anti-FOMO Cap)',
    formula: 'P_order ≤ P_max_mom = $0.62\nVeto trade if best available price > $0.62',
    mechanism: 'Anti-FOMO execution armor. Prevents the bot from chasing late breakouts near the cycle boundary where implied odds are already stretched and risk-reward is asymmetrically unfavorable (e.g. risking $0.80 to make $0.20).',
    recommendation: '$0.62 (Allows dynamic momentum participation while eliminating late-stage bag holding).',
    warning: 'Setting > $0.75 subjects the bankroll to severe 3:1 negative asymmetry where a single loss erases 3 consecutive wins.'
  },
  taker_ev: {
    title: 'Taker Cross EV Hurdle',
    symbol: 'EV_cross = +$0.04 / contract',
    formula: 'EV_taker ≥ EV_cross = +$0.04\nWhere Fee_taker = ceil(0.07 × C × P × (1 - P))',
    mechanism: 'Restricts spread crossing to only ultra-high-conviction events. The strategy operates primarily as a maker ($0.00 fee); it will only execute an immediate market taker cross if the calculated edge easily absorbs Kalshi taker fees and still yields at least $0.04 net EV.',
    recommendation: '+$0.04 (Preserves maker dominance while allowing high-conviction momentum sweeps).',
    warning: 'Lowering below $0.02 causes excessive taker fee leakage and degrades the strategy\'s Sharpe ratio.'
  },
  gamma_cliff: {
    title: 'Gamma Cliff Purge Timer',
    symbol: 'T_cliff = 90 seconds',
    formula: 'If T_rem ≤ T_cliff ⇒ HALT new orders & SWEEP all resting maker bids',
    mechanism: 'Protects against binary option pin risk. In the final 90 seconds of a 15-minute contract, binary gamma (Γ → ∞) approaches infinity, causing single-dollar spot fluctuations to trigger 0¢-to-100¢ price volatility. The engine automatically halts entries and sweeps resting orders.',
    recommendation: '90 seconds (Institutional standard for KXBTC15M contracts).',
    warning: 'Lowering below 45 seconds exposes capital to terminal pin-risk and potential exchange matching engine freezes near settlement.'
  },
  temporal_skew: {
    title: 'Cross-Brain Temporal Skew Guard',
    symbol: 'Δt_skew = |τ_spot - τ_kalshi| ≤ 1000 ms',
    formula: 'If |τ_spot - τ_kalshi| > 1000 ms ⇒ Emit DESYNCHRONIZED Veto',
    mechanism: 'Monitors WebSocket heartbeat and timestamp deltas between Binance Spot and Kalshi CLOB. If either feed lags by more than 1000ms, the strategy enters a safety hold to prevent trading on stale or desynchronized quotes.',
    recommendation: '1000 ms (Tolerates minor internet jitter while preventing stale-quote execution).',
    warning: 'Values > 2000 ms risk routing orders against outdated market prices during rapid spot breakouts.'
  },
  volatility_mode: {
    title: 'Dynamic Volatility Engine',
    symbol: 'σ_mode ∈ {REALIZED_ATR, FIXED_STATIC}',
    formula: 'REALIZED_ATR: σ = ATR_1m(15 rolling 1m Binance candles)\nFIXED_STATIC: σ = $14.00 / min',
    mechanism: 'Determines whether entry discount moats and moneyness calculations adapt dynamically to live spot velocity or remain anchored to a fixed $14.00/min baseline. Realized ATR continuously adapts to market volatility regimes.',
    recommendation: 'REALIZED_ATR (Dynamic adaptation to sudden market velocity changes).',
    warning: 'FIXED_STATIC fails to widen discount buffers during high-impact macroeconomic events (CPI, FOMC).'
  },
  vpin_toxicity: {
    title: 'VPIN Toxicity Cutoff',
    symbol: 'VPIN_veto = 0.70 (Informed Orderflow)',
    formula: 'VPIN = Σ|V_buy - V_sell| / (V_bucket × N) ≥ 0.70 ⇒ VETO ENTRY',
    mechanism: 'Volume-Synchronized Probability of Toxicity. Measures toxicity and informed trading intensity from real-time volume buckets. When VPIN exceeds 0.70, it signals aggressive informed institutional positioning, triggering an immediate maker quote retreat to prevent adverse selection.',
    recommendation: '0.70 (70% orderflow imbalance toxicity cutoff).',
    warning: 'Setting < 0.55 triggers excessive false-alarm trading halts; setting > 0.85 fails to shield against aggressive institutional market sweeps.'
  },
  dynamic_moat: {
    title: 'Dynamic Moat Multiplier',
    symbol: 'M_expand = 1.36x',
    formula: 'Moat = BaseMoat × max(1.0, σ_realized / σ_base) × M_expand',
    mechanism: 'Expands the required entry discount buffer proportionally when realized volatility exceeds baseline levels. Ensures the bot demands wider margins of safety and deeper discounts during stormy market conditions.',
    recommendation: '1.36 (Empirically calibrated for optimal fill probability during volatility surges).',
    warning: 'Multipliers > 2.0x cause limit prices to be set too far below the market, preventing order fills.'
  }
};

export const ONNXSettingsPanel: React.FC = () => {
  const [params, setParams] = useState<StrategyParameters | null>(null);
  const [activeInfo, setActiveInfo] = useState<string | null>(null);
  const [saving, setSaving] = useState<boolean>(false);
  const [success, setSuccess] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchParams = () => {
    fetch('/api/bot/parameters')
      .then((r) => r.json())
      .then((d) => {
        const p = d.parameters || d;
        setParams({
          brain_priority_mode: p.brain_priority_mode || 'TREND_ALIGNED_SCALP',
          contract_scaling_mode: p.contract_scaling_mode || 'TIER_0_STRICT_1',
          entry_discount_depth: p.entry_discount_depth ?? p.discount_limit_price ?? 0.52,
          discount_limit_price: p.discount_limit_price ?? p.entry_discount_depth ?? 0.52,
          momentum_max_price: p.momentum_max_price ?? 0.62,
          min_confidence: p.min_confidence ?? 0.70,
          min_ev_dollars: p.min_ev_dollars ?? 0.02,
          taker_cross_ev_threshold: p.taker_cross_ev_threshold ?? 0.04,
          max_temporal_skew_ms: p.max_temporal_skew_ms ?? 1000.0,
          gamma_cliff_seconds: p.gamma_cliff_seconds ?? 90.0,
          auto_cancel_on_veto: p.auto_cancel_on_veto !== undefined ? p.auto_cancel_on_veto : true,
          dynamic_volatility_mode: p.dynamic_volatility_mode || 'REALIZED_ATR',
          volatility_floor: p.volatility_floor ?? 10.0,
          volatility_ceiling: p.volatility_ceiling ?? 45.0,
          vpin_toxic_threshold: p.vpin_toxic_threshold ?? 0.70,
          dynamic_moat_multiplier: p.dynamic_moat_multiplier ?? 1.36,
          current_atr: p.current_atr ?? 14.0,
          cross_brain_skew_ms: p.cross_brain_skew_ms ?? 0.0,
          is_temporally_synced: p.is_temporally_synced !== undefined ? p.is_temporally_synced : true,
          slower_brain: p.slower_brain || 'IN_SYNC',
          hmm_regime: p.hmm_regime || 'NONE',
          max_contracts: 1,
        });
      })
      .catch((err) => {
        console.error('Error fetching ONNX parameters:', err);
      });
  };

  useEffect(() => {
    fetchParams();
    const interval = setInterval(fetchParams, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleChange = (key: keyof StrategyParameters, value: any) => {
    if (!params) return;
    setParams({ ...params, [key]: value });
  };

  const saveParams = async () => {
    if (!params) return;
    setSaving(true);
    setSuccess(false);
    setErrorMsg(null);
    try {
      const payload = {
        brain_priority_mode: params.brain_priority_mode,
        contract_scaling_mode: params.contract_scaling_mode,
        entry_discount_depth: Number(params.entry_discount_depth),
        discount_limit_price: Number(params.entry_discount_depth),
        momentum_max_price: Number(params.momentum_max_price),
        min_confidence: Number(params.min_confidence),
        min_ev_dollars: Number(params.min_ev_dollars),
        taker_cross_ev_threshold: Number(params.taker_cross_ev_threshold),
        max_temporal_skew_ms: Number(params.max_temporal_skew_ms),
        gamma_cliff_seconds: Number(params.gamma_cliff_seconds),
        auto_cancel_on_veto: Boolean(params.auto_cancel_on_veto),
        dynamic_volatility_mode: params.dynamic_volatility_mode,
        volatility_floor: Number(params.volatility_floor),
        volatility_ceiling: Number(params.volatility_ceiling),
        vpin_toxic_threshold: Number(params.vpin_toxic_threshold),
        dynamic_moat_multiplier: Number(params.dynamic_moat_multiplier),
      };

      const res = await fetch('/api/bot/parameters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: Failed to update parameters`);
      }

      setSuccess(true);
      setTimeout(() => setSuccess(false), 2500);
    } catch (e: any) {
      console.error(e);
      setErrorMsg(e.message || 'Failed saving parameters');
      setTimeout(() => setErrorMsg(null), 4000);
    } finally {
      setSaving(false);
    }
  };

  if (!params) {
    return (
      <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-6 font-mono text-slate-400 flex items-center justify-center gap-2">
        <RefreshCw className="w-4 h-4 animate-spin text-[#00bda5]" />
        <span>Loading Institutional ONNX Parameter Matrix...</span>
      </div>
    );
  }

  return (
    <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-5 font-mono text-xs shadow-xl">
      {/* Top Header & Save Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#262d35] pb-4">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center shrink-0">
            <Layers className="w-4 h-4 text-cyan-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                The ONNX Strategy — Institutional Cockpit Dials
              </h2>
              <span className="px-1.5 py-0.2 text-[9px] font-mono bg-cyan-500/25 text-cyan-300 border border-cyan-500/40 rounded-full font-bold">
                Dual-Brain Live Engine
              </span>
            </div>
            <p className="text-[11px] text-[#8c9ba5] mt-0.5">
              Fine-tune high-frequency contradiction arbitrage, lead-lag synchronization, and gamma cutoff shields.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-auto">
          <button
            onClick={fetchParams}
            title="Reload from Live Engine"
            className="p-1.5 rounded-lg border border-[#262d35] bg-[#161b22] text-gray-400 hover:text-white transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={saveParams}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-[#12161a] bg-[#00bda5] hover:bg-[#2dd4bf] rounded-lg transition-all shadow-md active:scale-95 disabled:opacity-50 cursor-pointer"
          >
            {saving ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            <span>{saving ? 'Syncing...' : 'Apply & Save Dials'}</span>
          </button>
        </div>
      </div>

      {/* Live Telemetry Status Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 bg-[#0a0c10] border border-[#21262d] rounded-lg p-2.5">
        <div className="flex items-center gap-2">
          <Clock className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
          <div>
            <div className="text-[9px] text-[#8c9ba5] uppercase">Cross-Brain Skew</div>
            <div className={`font-bold font-mono ${params.cross_brain_skew_ms! > params.max_temporal_skew_ms! ? 'text-rose-400' : 'text-cyan-300'}`}>
              {params.cross_brain_skew_ms?.toFixed(1)}ms {params.is_temporally_synced ? '✅' : '⚠️'}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <div>
            <div className="text-[9px] text-[#8c9ba5] uppercase">Realized 1M Vol (σ)</div>
            <div className="font-bold font-mono text-emerald-300">
              ${params.current_atr?.toFixed(2)}/min
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Shield className="w-3.5 h-3.5 text-amber-400 shrink-0" />
          <div>
            <div className="text-[9px] text-[#8c9ba5] uppercase">Markov Macro</div>
            <div className="font-bold font-mono text-amber-300">
              {params.hmm_regime || 'STABLE_RANGE'}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Zap className="w-3.5 h-3.5 text-purple-400 shrink-0" />
          <div>
            <div className="text-[9px] text-[#8c9ba5] uppercase">Sizing Armor</div>
            <div className="font-bold font-mono text-purple-300">
              STRICT 1 CT ($0-$75)
            </div>
          </div>
        </div>
      </div>

      {/* Feedback Banner */}
      {success && (
        <div className="text-xs text-emerald-400 bg-emerald-500/10 p-2.5 rounded-lg border border-emerald-500/30 flex items-center gap-2 animate-in fade-in">
          <Check className="w-4 h-4 text-emerald-400" />
          <span>Institutional parameter matrix successfully committed to live execution daemon.</span>
        </div>
      )}

      {errorMsg && (
        <div className="text-xs text-rose-400 bg-rose-500/10 p-2.5 rounded-lg border border-rose-500/30 flex items-center gap-2 animate-in fade-in">
          <AlertTriangle className="w-4 h-4 text-rose-400" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* 4-Quadrant Control Matrix */}
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
              <span className="flex items-center gap-1.5">
                Arbitration Priority Mode
                <button
                  type="button"
                  onClick={() => setActiveInfo('brain_priority')}
                  className="text-cyan-400 hover:text-white"
                  title="View Parameter Guidance"
                >
                  <Info className="w-3 h-3" />
                </button>
              </span>
              <span className="text-cyan-400 font-mono">{params.brain_priority_mode}</span>
            </div>
            <select
              value={params.brain_priority_mode}
              onChange={(e) => handleChange('brain_priority_mode', e.target.value)}
              className="w-full bg-[#0a0c10] border border-[#262d35] rounded-lg p-2 text-white text-xs focus:outline-none focus:border-cyan-500 cursor-pointer"
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
              <span className="flex items-center gap-1.5">
                Micro-Bankroll Sizing Armor
                <button
                  type="button"
                  onClick={() => setActiveInfo('sizing_armor')}
                  className="text-cyan-400 hover:text-white"
                  title="View Parameter Guidance"
                >
                  <Info className="w-3 h-3" />
                </button>
              </span>
              <span className="text-purple-400 font-mono">1 Contract Hard Cap</span>
            </div>
            <select
              value={params.contract_scaling_mode || 'TIER_0_STRICT_1'}
              onChange={(e) => handleChange('contract_scaling_mode', e.target.value)}
              className="w-full bg-[#0a0c10] border border-[#262d35] rounded-lg p-2 text-white text-xs focus:outline-none focus:border-cyan-500 cursor-pointer"
            >
              <option value="TIER_0_STRICT_1">TIER_0_STRICT_1 (Hard Cap 1 Contract)</option>
              <option value="TIER_1_MICRO_2">TIER_1_MICRO_2 (Bankroll &gt; $75)</option>
            </select>
          </div>

          {/* Min Neural Confidence */}
          <div className="space-y-1">
            <div className="flex justify-between items-center text-[10px] text-[#8c9ba5] font-semibold">
              <span className="flex items-center gap-1.5 uppercase">
                Min Neural Confidence
                <button
                  type="button"
                  onClick={() => setActiveInfo('min_confidence')}
                  className="text-cyan-400 hover:text-white"
                  title="View Parameter Guidance"
                >
                  <Info className="w-3 h-3" />
                </button>
              </span>
              <span className="font-mono text-cyan-400">{((params.min_confidence || 0.7) * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min="0.50"
              max="0.95"
              step="0.01"
              value={params.min_confidence || 0.70}
              onChange={(e) => handleChange('min_confidence', parseFloat(e.target.value))}
              className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-cyan-400"
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
              <span className="flex items-center gap-1.5 uppercase">
                Min Net Expected Value (EV)
                <button
                  type="button"
                  onClick={() => setActiveInfo('min_ev')}
                  className="text-cyan-400 hover:text-white"
                  title="View Parameter Guidance"
                >
                  <Info className="w-3 h-3" />
                </button>
              </span>
              <span className="font-mono text-emerald-400">+${(params.min_ev_dollars || 0.02).toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.01"
              max="0.20"
              step="0.01"
              value={params.min_ev_dollars || 0.02}
              onChange={(e) => handleChange('min_ev_dollars', parseFloat(e.target.value))}
              className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-emerald-400"
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
              <span className="flex items-center gap-1.5 uppercase">
                Maker Resting Discount Ceiling
                <button
                  type="button"
                  onClick={() => setActiveInfo('entry_discount')}
                  className="text-cyan-400 hover:text-white"
                  title="View Parameter Guidance"
                >
                  <Info className="w-3 h-3" />
                </button>
              </span>
              <span className="font-mono text-amber-300">${(params.entry_discount_depth || 0.52).toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.15"
              max="0.55"
              step="0.01"
              value={params.entry_discount_depth || 0.52}
              onChange={(e) => handleChange('entry_discount_depth', parseFloat(e.target.value))}
              className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-amber-400"
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
              <span className="flex items-center gap-1.5 uppercase">
                Momentum Taker Sweep Ceiling
                <button
                  type="button"
                  onClick={() => setActiveInfo('momentum_max')}
                  className="text-cyan-400 hover:text-white"
                  title="View Parameter Guidance"
                >
                  <Info className="w-3 h-3" />
                </button>
              </span>
              <span className="font-mono text-cyan-300">${(params.momentum_max_price || 0.62).toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.50"
              max="0.75"
              step="0.01"
              value={params.momentum_max_price || 0.62}
              onChange={(e) => handleChange('momentum_max_price', parseFloat(e.target.value))}
              className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-cyan-400"
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
              <span className="flex items-center gap-1.5 uppercase">
                Taker Cross EV Hurdle (CFTC Fee Armor)
                <button
                  type="button"
                  onClick={() => setActiveInfo('taker_ev')}
                  className="text-cyan-400 hover:text-white"
                  title="View Parameter Guidance"
                >
                  <Info className="w-3 h-3" />
                </button>
              </span>
              <span className="font-mono text-emerald-300">+${(params.taker_cross_ev_threshold || 0.04).toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.01"
              max="0.15"
              step="0.01"
              value={params.taker_cross_ev_threshold || 0.04}
              onChange={(e) => handleChange('taker_cross_ev_threshold', parseFloat(e.target.value))}
              className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-emerald-400"
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
              <span className="flex items-center gap-1.5 uppercase">
                Dynamic Moat Multiplier
                <button
                  type="button"
                  onClick={() => setActiveInfo('dynamic_moat')}
                  className="text-cyan-400 hover:text-white"
                  title="View Parameter Guidance"
                >
                  <Info className="w-3 h-3" />
                </button>
              </span>
              <span className="font-mono text-amber-300">{(params.dynamic_moat_multiplier || 1.36).toFixed(2)}x</span>
            </div>
            <input
              type="range"
              min="1.00"
              max="2.50"
              step="0.05"
              value={params.dynamic_moat_multiplier || 1.36}
              onChange={(e) => handleChange('dynamic_moat_multiplier', parseFloat(e.target.value))}
              className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-amber-400"
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
              <span className="flex items-center gap-1.5 uppercase">
                Max Cross-Brain Skew Tolerance
                <button
                  type="button"
                  onClick={() => setActiveInfo('temporal_skew')}
                  className="text-cyan-400 hover:text-white"
                  title="View Parameter Guidance"
                >
                  <Info className="w-3 h-3" />
                </button>
              </span>
              <span className="font-mono text-purple-400">{(params.max_temporal_skew_ms || 1000).toFixed(0)}ms</span>
            </div>
            <input
              type="range"
              min="200"
              max="3000"
              step="50"
              value={params.max_temporal_skew_ms || 1000}
              onChange={(e) => handleChange('max_temporal_skew_ms', parseFloat(e.target.value))}
              className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-purple-400"
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
              <span className="flex items-center gap-1.5 uppercase">
                Gamma Cliff Expiry Cutoff (Anti-Pin Risk)
                <button
                  type="button"
                  onClick={() => setActiveInfo('gamma_cliff')}
                  className="text-cyan-400 hover:text-white"
                  title="View Parameter Guidance"
                >
                  <Info className="w-3 h-3" />
                </button>
              </span>
              <span className="font-mono text-rose-400">{(params.gamma_cliff_seconds || 90).toFixed(0)}s rem</span>
            </div>
            <input
              type="range"
              min="30"
              max="180"
              step="5"
              value={params.gamma_cliff_seconds || 90}
              onChange={(e) => handleChange('gamma_cliff_seconds', parseFloat(e.target.value))}
              className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-rose-400"
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
              <span className="text-[10px] font-semibold text-white uppercase">Auto-Purge Resting Orders on Veto</span>
              <span className="text-[9px] text-gray-500">Immediately sweep open maker bids upon any VPIN / Skew breach</span>
            </div>
            <button
              type="button"
              onClick={() => handleChange('auto_cancel_on_veto', !params.auto_cancel_on_veto)}
              className={`w-11 h-6 flex items-center rounded-full p-1 transition-colors cursor-pointer ${
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
              <span className="flex items-center gap-1.5">
                Diffusion Volatility Mode
                <button
                  type="button"
                  onClick={() => setActiveInfo('volatility_mode')}
                  className="text-cyan-400 hover:text-white"
                  title="View Parameter Guidance"
                >
                  <Info className="w-3 h-3" />
                </button>
              </span>
              <span className="text-emerald-400 font-mono">{params.dynamic_volatility_mode}</span>
            </div>
            <select
              value={params.dynamic_volatility_mode}
              onChange={(e) => handleChange('dynamic_volatility_mode', e.target.value)}
              className="w-full bg-[#0a0c10] border border-[#262d35] rounded-lg p-2 text-white text-xs focus:outline-none focus:border-emerald-500 cursor-pointer"
            >
              <option value="REALIZED_ATR">REALIZED_ATR (Live 15M/5M Rolling Candle ATR)</option>
              <option value="FIXED_STATIC">FIXED_STATIC (Static $14.0/min Anchor)</option>
            </select>
          </div>

          {/* VPIN Toxicity Cutoff */}
          <div className="space-y-1">
            <div className="flex justify-between items-center text-[10px] text-[#8c9ba5] font-semibold">
              <span className="flex items-center gap-1.5 uppercase">
                VPIN Toxicity Cutoff
                <button
                  type="button"
                  onClick={() => setActiveInfo('vpin_toxicity')}
                  className="text-cyan-400 hover:text-white"
                  title="View Parameter Guidance"
                >
                  <Info className="w-3 h-3" />
                </button>
              </span>
              <span className="font-mono text-cyan-300">{Number(params.vpin_toxic_threshold || 0.70).toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.50"
              max="0.90"
              step="0.01"
              value={params.vpin_toxic_threshold || 0.70}
              onChange={(e) => handleChange('vpin_toxic_threshold', parseFloat(e.target.value))}
              className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-cyan-400"
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
              <label className="text-[9px] text-[#8c9ba5] font-semibold uppercase">Vol Floor ($/min)</label>
              <div className="relative">
                <span className="absolute left-2 top-2 text-gray-500 text-xs">$</span>
                <input
                  type="number"
                  step="1.0"
                  min="2.0"
                  max="30.0"
                  value={params.volatility_floor || 10.0}
                  onChange={(e) => handleChange('volatility_floor', parseFloat(e.target.value))}
                  className="w-full bg-[#0a0c10] border border-[#262d35] rounded-lg p-2 pl-5 text-white text-xs focus:outline-none focus:border-emerald-500"
                />
              </div>
              <span className="text-[8px] text-gray-500 block">Dead Chop Veto</span>
            </div>

            <div className="space-y-1">
              <label className="text-[9px] text-[#8c9ba5] font-semibold uppercase">Vol Ceiling ($/min)</label>
              <div className="relative">
                <span className="absolute left-2 top-2 text-gray-500 text-xs">$</span>
                <input
                  type="number"
                  step="1.0"
                  min="20.0"
                  max="200.0"
                  value={params.volatility_ceiling || 45.0}
                  onChange={(e) => handleChange('volatility_ceiling', parseFloat(e.target.value))}
                  className="w-full bg-[#0a0c10] border border-[#262d35] rounded-lg p-2 pl-5 text-white text-xs focus:outline-none focus:border-emerald-500"
                />
              </div>
              <span className="text-[8px] text-gray-500 block">Chaos / News Veto</span>
            </div>
          </div>
        </div>

      </div>

      {/* Deep (i) Parameter Inspection Modal */}
      {activeInfo && PARAM_DOCS[activeInfo] && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in"
          onClick={() => setActiveInfo(null)}
        >
          <div
            className="bg-[#0f131d] border border-[#28324a] rounded-xl max-w-lg w-full p-5 space-y-3.5 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-[#262d35] pb-2.5">
              <div className="flex items-center gap-2">
                <span className="font-bold text-white text-sm">{PARAM_DOCS[activeInfo].title}</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                  {PARAM_DOCS[activeInfo].symbol}
                </span>
              </div>
              <button
                onClick={() => setActiveInfo(null)}
                className="text-gray-400 hover:text-white p-1 rounded-lg hover:bg-white/5 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-1">
              <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Quantitative Mathematical Formulation</div>
              <div className="text-xs font-mono text-cyan-300 bg-[#090c14] p-2.5 rounded-lg border border-white/5 whitespace-pre-line">
                {PARAM_DOCS[activeInfo].formula}
              </div>
            </div>

            <div className="space-y-1">
              <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Institutional Mechanism &amp; Role</div>
              <div className="text-xs text-slate-300 bg-[#090c14] p-2.5 rounded-lg border border-white/5 leading-relaxed">
                {PARAM_DOCS[activeInfo].mechanism}
              </div>
            </div>

            <div className="space-y-1">
              <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Recommended Institutional Calibration</div>
              <div className="text-xs text-emerald-300 bg-[#090c14] p-2.5 rounded-lg border border-white/5 font-mono">
                {PARAM_DOCS[activeInfo].recommendation}
              </div>
            </div>

            <div className="text-xs text-rose-300 bg-rose-500/10 p-2.5 rounded-lg border border-rose-500/30 leading-relaxed">
              ⚠️ <strong>RISK WARNING:</strong> {PARAM_DOCS[activeInfo].warning}
            </div>

            <div className="flex justify-end pt-1">
              <button
                onClick={() => setActiveInfo(null)}
                className="px-4 py-1.5 bg-[#1e293b] hover:bg-[#334155] text-white text-xs font-bold rounded-lg border border-[#334155] transition-colors cursor-pointer"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
