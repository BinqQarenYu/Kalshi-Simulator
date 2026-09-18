import { NeuralEngineSpec } from '../../types';

export const NEURAL_ENGINES: NeuralEngineSpec[] = [
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

export interface StrategyParameters {
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

export interface ParamDoc {
  title: string;
  symbol: string;
  formula: string;
  mechanism: string;
  recommendation: string;
  warning: string;
}

export const PARAM_DOCS: Record<string, ParamDoc> = {
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
