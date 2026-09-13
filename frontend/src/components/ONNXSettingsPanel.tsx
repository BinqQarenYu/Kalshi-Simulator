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
  Coins,
  Globe,
  Sparkles,
  ExternalLink,
  ChevronRight,
  Database,
} from 'lucide-react';
import { NeuralEngineSpec } from '../types';

const NEURAL_ENGINES: NeuralEngineSpec[] = [
  {
    id: 'brain_1_spot_macro',
    name: 'Brain 1: Spot Macro Anchor',
    filename: 'nano_microscope_overhauled.onnx',
    version: 'v2.4.1',
    dimension: 28,
    features_description: '28-D Spot Microstructure (Binance 5Hz L2 Depth + aggTrade, CVD, VPIN)',
    target_assets: ['BTC', 'ETH', 'SOL'],
    supported_venues: ['Kalshi', 'Binance'],
    role: 'Global Macro Trajectory & Lead-Lag Momentum Anchor',
    status: 'ACTIVE_LANE_1',
    architecture: 'QuoLasMicroscopeNet (28 -> 64 -> 32 -> 3 Softmax)',
    input_shape: '(B, 28) float32 [features_28d]',
    output_shape: '(B, 3) float32 [P(UP), P(DOWN), P(WAIT)]',
    latency_budget_ms: 1.8,
    physics_features: [
      'OFI L1/5/15 Order Flow Imbalance',
      '5-Minute Cumulative Volume Delta (CVD)',
      'Volume-Synchronized Toxicity (VPIN)',
      '10-Level Spatial Exponential Book Decay'
    ],
    adapters: ['Kalshi CME CF BRTI 5Hz', 'Binance Spot L2 Feed']
  },
  {
    id: 'brain_2_kalshi_sniper',
    name: 'Brain 2: Micro Scalp Sniper',
    filename: 'kalshi_onnx.onnx',
    version: 'v1.8.0',
    dimension: 28,
    features_description: '28-D Kalshi Binary CLOB Depth & Inside Touch Momentum (15–30s horizon)',
    target_assets: ['KXBTC15M', 'KXETH15M'],
    supported_venues: ['Kalshi'],
    role: 'Local CLOB Spread Compression & Fast Execution Sniper',
    status: 'ACTIVE_LANE_1',
    architecture: 'KalshiMicroscopeNet (28 -> 64 -> 32 -> 3 Softmax)',
    input_shape: '(B, 28) float32 [features_28d]',
    output_shape: '(B, 3) float32 [P(UP), P(DOWN), P(WAIT)]',
    latency_budget_ms: 1.2,
    physics_features: [
      'Kalshi 15-Level Binary Depth Decay',
      'Inside Touch Velocity & Spread BPS',
      'Resting Order Absorption Index',
      'Adverse Selection Price Drift Guard'
    ],
    adapters: ['Kalshi WebSocket CLOB Feed']
  },
  {
    id: 'brain_3_gold_spacetime',
    name: 'Brain 3: Gold Spacetime & Tri-Venue Engine',
    filename: 'gold.onnx',
    version: 'v3.0.0-PRO',
    dimension: 32,
    features_description: '32-D Gold Orderflow + Spatial Book Convexity + Spacetime Option Physics',
    target_assets: ['XAU', 'PAXG', 'GOLD'],
    supported_venues: ['Kalshi', 'Polymarket', 'Binance'],
    role: 'Multi-Venue Gold Binary Options & Prediction Microstructure Engine',
    status: 'STANDALONE_LAB',
    architecture: 'QuoLasGoldMicroscopeNet (32 -> LayerNorm -> ResNet 64 -> 32 -> 3 Softmax)',
    input_shape: '(B, 32) float32 [features_32d]',
    output_shape: '(B, 3) float32 [P(UP), P(DOWN), P(WAIT)]',
    latency_budget_ms: 1.5,
    physics_features: [
      'Standardized Moneyness: z_t = (S_t - K) / (σ * sqrt(τ/60))',
      'Time-to-Expiry Normalized: τ_norm = τ / 900.0',
      'OFI Acceleration: ΔOFI_L5 = OFI_t - OFI_{t-3}',
      'Settlement TWAP Delta: (S_t - TWAP_60s) / σ',
      '15-Level Spatial Exponential Book Decay (α=0.425)',
      '13-D Toxic Microstructure (VPIN, CVD, Trade Entropy, Whales, Spoofing)'
    ],
    adapters: [
      'KalshiAdapter (60s Trailing TWAP Parity + CFTC Quadratic Taker Cap)',
      'PolymarketAdapter (Point-in-Time Oracle Pyth/Chainlink + USDC CLOB)',
      'BinanceAdapter (Composite Mark Index + Basis-Point Tiered Fees)'
    ]
  }
];

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
  const [selectedEngine, setSelectedEngine] = useState<NeuralEngineSpec | null>(null);
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

      {/* Neural Engine Fleet & Multi-Brain Architecture Matrix */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4 space-y-3">
        <div className="flex items-center justify-between border-b border-[#21262d] pb-2.5">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-cyan-400" />
            <span className="font-bold text-white uppercase text-[11px] tracking-wider">
              Neural Engine Fleet &amp; Multi-Brain Architecture Matrix
            </span>
          </div>
          <span className="text-[10px] text-gray-400 font-mono">
            3 ONNX Engines • 1 Standalone Multilateral Brain
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          {NEURAL_ENGINES.map((eng) => {
            const isGold = eng.id === 'brain_3_gold_spacetime';
            return (
              <div
                key={eng.id}
                className={`p-3.5 rounded-xl border flex flex-col justify-between transition-all ${
                  isGold
                    ? 'bg-amber-950/20 border-amber-500/40 hover:border-amber-400 shadow-sm'
                    : 'bg-[#0d1117] border-[#262d35] hover:border-cyan-500/40 shadow-sm'
                }`}
              >
                <div className="space-y-2.5">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      {isGold ? (
                        <div className="h-7 w-7 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center shrink-0">
                          <Coins className="w-4 h-4 text-amber-400" />
                        </div>
                      ) : (
                        <div className="h-7 w-7 rounded-lg bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center shrink-0">
                          <Layers className="w-4 h-4 text-cyan-400" />
                        </div>
                      )}
                      <div>
                        <div className="font-bold text-white text-xs flex items-center gap-1.5">
                          <span>{eng.name}</span>
                          {isGold && (
                            <span className="px-1.5 py-0.2 text-[8px] font-mono bg-amber-500/30 text-amber-200 border border-amber-500/50 rounded-full font-bold">
                              NEW
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] font-mono text-gray-400">{eng.filename}</div>
                      </div>
                    </div>
                    <span
                      className={`px-2 py-0.5 text-[9px] font-mono font-bold rounded-full border shrink-0 ${
                        eng.status === 'ACTIVE_LANE_1'
                          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                          : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                      }`}
                    >
                      {eng.status === 'ACTIVE_LANE_1' ? 'LANE 1 LIVE' : 'STANDALONE LAB'}
                    </span>
                  </div>

                  <p className="text-[10px] text-slate-300 leading-snug">
                    {eng.features_description}
                  </p>

                  <div className="grid grid-cols-2 gap-1.5 pt-0.5 text-[10px] font-mono">
                    <div className="bg-[#090c14] p-1.5 rounded border border-white/5">
                      <span className="text-gray-500 block text-[8px] uppercase">Tensor Dimension</span>
                      <span className="font-bold text-cyan-300">{eng.dimension}-D Vector</span>
                    </div>
                    <div className="bg-[#090c14] p-1.5 rounded border border-white/5">
                      <span className="text-gray-500 block text-[8px] uppercase">Latency Budget</span>
                      <span className="font-bold text-emerald-300">&lt; {eng.latency_budget_ms}ms</span>
                    </div>
                  </div>

                  {/* Venues & Target Assets Badges */}
                  <div className="space-y-1 pt-1">
                    <div className="text-[9px] text-gray-400 font-semibold uppercase flex items-center gap-1">
                      <Globe className="w-2.5 h-2.5 text-blue-400" />
                      <span>Supported Venues &amp; Adapters</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-1">
                      {eng.supported_venues.map((venue) => (
                        <span
                          key={venue}
                          className="px-1.5 py-0.5 bg-blue-500/15 border border-blue-500/30 text-blue-300 text-[9px] font-mono rounded"
                        >
                          {venue}
                        </span>
                      ))}
                      {eng.target_assets.map((asset) => (
                        <span
                          key={asset}
                          className="px-1.5 py-0.5 bg-purple-500/15 border border-purple-500/30 text-purple-300 text-[9px] font-mono rounded"
                        >
                          {asset}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="pt-3 border-t border-white/5 mt-3 flex items-center justify-between">
                  <span className="text-[9px] font-mono text-gray-500">
                    {eng.version}
                  </span>
                  <button
                    type="button"
                    onClick={() => setSelectedEngine(eng)}
                    className="flex items-center gap-1 text-[10px] font-bold text-cyan-400 hover:text-cyan-300 transition-colors cursor-pointer px-2 py-1 rounded hover:bg-cyan-500/10 border border-transparent hover:border-cyan-500/30"
                  >
                    <span>Inspect Specs</span>
                    <ChevronRight className="w-3 h-3" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

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

      {/* Deep Neural Engine Specification Modal */}
      {selectedEngine && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in"
          onClick={() => setSelectedEngine(null)}
        >
          <div
            className="bg-[#0f131d] border border-[#28324a] rounded-2xl max-w-2xl w-full p-6 space-y-4 shadow-2xl overflow-y-auto max-h-[90vh]"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-[#262d35] pb-3">
              <div className="flex items-center gap-3">
                <div className={`h-9 w-9 rounded-xl flex items-center justify-center shrink-0 border ${
                  selectedEngine.id === 'brain_3_gold_spacetime'
                    ? 'bg-amber-500/20 border-amber-500/40'
                    : 'bg-cyan-500/20 border-cyan-500/40'
                }`}>
                  {selectedEngine.id === 'brain_3_gold_spacetime' ? (
                    <Coins className="w-5 h-5 text-amber-400" />
                  ) : (
                    <Cpu className="w-5 h-5 text-cyan-400" />
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-white text-sm">{selectedEngine.name}</h3>
                    <span className={`px-2 py-0.5 text-[9px] font-mono font-bold rounded-full border ${
                      selectedEngine.status === 'ACTIVE_LANE_1'
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                        : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                    }`}>
                      {selectedEngine.status === 'ACTIVE_LANE_1' ? 'LANE 1 LIVE' : 'STANDALONE LAB ENGINE'}
                    </span>
                  </div>
                  <div className="text-xs font-mono text-gray-400 mt-0.5">
                    Model Binary: <span className="text-cyan-300">{selectedEngine.filename}</span> • {selectedEngine.version}
                  </div>
                </div>
              </div>
              <button
                onClick={() => setSelectedEngine(null)}
                className="text-gray-400 hover:text-white p-1.5 rounded-lg hover:bg-white/5 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Top Specs Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
              <div className="bg-[#090c14] p-2.5 rounded-xl border border-white/5">
                <span className="text-gray-500 text-[9px] block uppercase">Vector Dim</span>
                <span className="font-bold text-cyan-300 text-sm">{selectedEngine.dimension}-D</span>
              </div>
              <div className="bg-[#090c14] p-2.5 rounded-xl border border-white/5">
                <span className="text-gray-500 text-[9px] block uppercase">Inference Speed</span>
                <span className="font-bold text-emerald-300 text-sm">&lt; {selectedEngine.latency_budget_ms}ms</span>
              </div>
              <div className="bg-[#090c14] p-2.5 rounded-xl border border-white/5">
                <span className="text-gray-500 text-[9px] block uppercase">Input Shape</span>
                <span className="font-bold text-purple-300 text-[11px] truncate block">{selectedEngine.input_shape}</span>
              </div>
              <div className="bg-[#090c14] p-2.5 rounded-xl border border-white/5">
                <span className="text-gray-500 text-[9px] block uppercase">Output Shape</span>
                <span className="font-bold text-amber-300 text-[11px] truncate block">{selectedEngine.output_shape}</span>
              </div>
            </div>

            {/* Neural Graph Architecture */}
            <div className="space-y-1.5">
              <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-cyan-400" />
                <span>Neural Architecture Topology</span>
              </div>
              <div className="bg-[#090c14] p-3 rounded-xl border border-white/5 font-mono text-xs text-slate-200">
                {selectedEngine.architecture}
              </div>
            </div>

            {/* Mathematical & Physical Feature Breakdown */}
            {selectedEngine.physics_features && (
              <div className="space-y-1.5">
                <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Feature Formulation &amp; Physics Dimensions</span>
                </div>
                <div className="bg-[#090c14] p-3 rounded-xl border border-white/5 space-y-1.5">
                  {selectedEngine.physics_features.map((feat, idx) => (
                    <div key={idx} className="flex items-start gap-2 text-xs font-mono text-slate-300">
                      <span className="text-cyan-400 font-bold shrink-0">#{idx + 1}</span>
                      <span>{feat}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tri-Venue Adapter Protocol */}
            {selectedEngine.adapters && (
              <div className="space-y-1.5">
                <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Globe className="w-3.5 h-3.5 text-blue-400" />
                  <span>Tri-Venue Adapter Protocol &amp; Settlement Routing</span>
                </div>
                <div className="bg-[#090c14] p-3 rounded-xl border border-white/5 space-y-2">
                  {selectedEngine.adapters.map((adapter, idx) => (
                    <div key={idx} className="flex items-center justify-between text-xs font-mono bg-[#12161f] p-2 rounded-lg border border-white/5">
                      <div className="flex items-center gap-2">
                        <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        <span className="text-white">{adapter}</span>
                      </div>
                      <span className="text-[9px] text-emerald-300 bg-emerald-500/15 px-2 py-0.5 rounded border border-emerald-500/30">
                        VERIFIED
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Invariant Guarantees Strip */}
            <div className="p-3 rounded-xl bg-cyan-950/20 border border-cyan-500/30 text-xs text-cyan-200 space-y-1">
              <div className="font-bold flex items-center gap-1.5 uppercase text-[10px]">
                <Shield className="w-3.5 h-3.5 text-cyan-400" />
                <span>Microstructure Safety &amp; Decoupled Invariant</span>
              </div>
              <p className="text-[11px] text-slate-300">
                This ONNX engine operates strictly with <strong>zero IEEE-754 floating-point drift</strong> (Python <code>Decimal</code> throughout settlement logic) and enforces micro-bankroll armor (1 contract hard-cap).
              </p>
            </div>

            {/* Close Action */}
            <div className="flex justify-end pt-1">
              <button
                onClick={() => setSelectedEngine(null)}
                className="px-5 py-2 bg-[#1e293b] hover:bg-[#334155] text-white text-xs font-bold rounded-xl border border-[#334155] transition-colors cursor-pointer"
              >
                Close Engine Specs
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

