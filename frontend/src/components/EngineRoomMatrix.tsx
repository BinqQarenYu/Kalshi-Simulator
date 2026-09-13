import React, { useState } from 'react';
import {
  Cpu,
  Zap,
  Activity,
  Shield,
  Radio,
  AlertTriangle,
  CheckCircle2,
  Sliders,
  ArrowRight,
  TrendingUp,
  Layers,
  Database,
  Gauge,
  HelpCircle,
  Sparkles,
  RefreshCw,
  Power,
} from 'lucide-react';
import { soundFX } from '../utils/audioFX';

export type EngineViewTab = 'matrix' | 'cylinder1' | 'cylinder2' | 'cylinder3' | 'wiring';

interface EngineRoomMatrixProps {
  activeTab?: EngineViewTab;
  onTabChange?: (tab: EngineViewTab) => void;
}

interface CylinderDef {
  id: string;
  name: string;
  shortName: string;
  cylinderNum: number;
  icon: any;
  color: string;
  badgeBg: string;
  badgeBorder: string;
  cadence: string;
  rawInputs: { name: string; source: string; freq: string; desc: string }[];
  tuningDials: { param: string; defaultVal: string; range: string; desc: string }[];
  namedOutputs: { variable: string; type: string; unit: string; desc: string }[];
  liveStrengths: string[];
  liveWeaknesses: string[];
  botSuitability: { bot: string; recommendation: 'MUST USE' | 'OPTIONAL' | 'DISCONNECT' | 'OPTIONAL (AS VETO)'; reason: string }[];
}

const CYLINDERS: CylinderDef[] = [
  {
    id: 'cylinder1',
    name: 'Spot Microstructure & Orderflow Scanner',
    shortName: 'Spot Orderflow ONNX',
    cylinderNum: 1,
    icon: Zap,
    color: '#f59e0b',
    badgeBg: 'rgba(245, 158, 11, 0.1)',
    badgeBorder: 'rgba(245, 158, 11, 0.3)',
    cadence: '100ms Ticks (High-Frequency)',
    rawInputs: [
      {
        name: 'Binance L2 Depth (20 Levels)',
        source: 'Binance WebSocket (depth20@100ms)',
        freq: '100ms',
        desc: 'Top 20 bids and asks with cumulative volume across price steps.',
      },
      {
        name: 'Aggregated Trades (aggTrade)',
        source: 'Binance Trade WebSocket',
        freq: 'Event-driven (10–50/s)',
        desc: 'Buyer/seller taker aggression and instantaneous execution volume.',
      },
      {
        name: 'Spot Tick Velocity (ΔSpot / Δt)',
        source: 'CME CF BRTI 5Hz / Binance Feed',
        freq: '200ms',
        desc: 'Directional price movement speed in $/sec to detect institutional sweeps.',
      },
      {
        name: 'Bid/Ask Micro-Imbalance',
        source: 'Normalized L2 Depth Feature Transformer',
        freq: '100ms',
        desc: 'Ratio of near-touch liquidity (BidVol - AskVol) / (BidVol + AskVol).',
      },
    ],
    tuningDials: [
      {
        param: 'min_spot_velocity',
        defaultVal: '$15.00/s',
        range: '$5 – $50',
        desc: 'Minimum spot velocity required to trigger directional acceleration signals.',
      },
      {
        param: 'depth_imbalance_ratio',
        defaultVal: '0.35 (+35%)',
        range: '0.10 – 0.70',
        desc: 'Threshold where bid/ask imbalance confirms institutional order flow stacking.',
      },
      {
        param: 'onnx_confidence_threshold',
        defaultVal: '80.0%',
        range: '60% – 95%',
        desc: 'Minimum neural network probability required to issue a momentum recommendation.',
      },
      {
        param: 'lookback_ticks',
        defaultVal: '30 ticks',
        range: '10 – 100',
        desc: 'Rolling sliding window length for micro-feature tensor normalization.',
      },
    ],
    namedOutputs: [
      {
        variable: 'spot_direction',
        type: 'string',
        unit: 'UP | DOWN | FLAT',
        desc: 'Directional bias derived from neural forward pass on orderflow tensor.',
      },
      {
        variable: 'spot_confidence',
        type: 'float',
        unit: '0.00 – 1.00 (0–100%)',
        desc: 'Sigmoid confidence score of the neural classifier.',
      },
      {
        variable: 'micro_velocity_score',
        type: 'float',
        unit: '$/sec momentum',
        desc: 'Rolling rate of spot change over the last 1.5 seconds.',
      },
      {
        variable: 'flow_toxicity (VPIN)',
        type: 'float',
        unit: '0.00 – 1.00',
        desc: 'Volume-Synchronized Probability of Toxicity measuring informed trader dumping.',
      },
    ],
    liveStrengths: [
      '⚡ Sub-second front-running: Spots aggressive spot buying on Binance 200–500ms before Kalshi makers react.',
      '🎯 Momentum sniper: Perfect for entering immediately upon an institutional liquidity sweep.',
      '🛡️ Flash-crash veto: Detects informed selling bursts instantly and halts buy orders before Kalshi catches down.',
    ],
    liveWeaknesses: [
      '⚠️ Brownian noise traps: In tight consolidation (<$25 range), it triggers false-positive buy/sell churn.',
      '⚠️ Spoofing vulnerability: Large resting limit bids on Binance that get cancelled before fill can fake the model.',
      '⚠️ Fee drag if unconstrained: Generating 10 trades in 5 minutes will bleed capital in taker fees.',
    ],
    botSuitability: [
      {
        bot: 'Bot 1 (Dominion Sniper)',
        recommendation: 'DISCONNECT',
        reason: 'Bot 1 trades maker discount limits; sub-second spot velocity causes overtrading and fee drag.',
      },
      {
        bot: 'Bot 2 (ONNX Scalper)',
        recommendation: 'MUST USE',
        reason: 'Bot 2 exists specifically to monetize the sub-second speed differential between Binance and Kalshi.',
      },
      {
        bot: 'Bot 3 (Macro Trend)',
        recommendation: 'OPTIONAL',
        reason: 'Used only as a secondary confirmation gate; macro bot must not execute on raw 100ms micro-noise.',
      },
      {
        bot: 'Bot X (New Custom Bot)',
        recommendation: 'OPTIONAL',
        reason: 'Plug in if Bot X is an ultra-short-term momentum sniper; disconnect if Bot X is a patient swing bot.',
      },
    ],
  },
  {
    id: 'cylinder2',
    name: 'Kalshi CLOB Dynamics & Maker Edge Scanner',
    shortName: 'Kalshi CLOB ONNX',
    cylinderNum: 2,
    icon: Layers,
    color: '#00bda5',
    badgeBg: 'rgba(0, 189, 165, 0.1)',
    badgeBorder: 'rgba(0, 189, 165, 0.3)',
    cadence: '200ms Sequence-Continuous L2 Feed',
    rawInputs: [
      {
        name: 'Kalshi Binary L2 Orderbook',
        source: 'Authenticated Kalshi WebSocket',
        freq: '200ms',
        desc: 'Live resting bids and asks for YES and NO contracts at each cent level ($0.01–$0.99).',
      },
      {
        name: 'Inside Touch Quotes & Spread',
        source: 'CLOB Best Bid / Best Ask Ingestion',
        freq: 'Continuous',
        desc: 'Best YES bid, best YES ask, and spread width: (YES Ask - YES Bid).',
      },
      {
        name: 'Order-to-Trade Ratio (OTR)',
        source: 'CLOB Order Flow Telemetry',
        freq: '1s interval',
        desc: 'Ratio of order placements/cancellations to executed trades to monitor book liquidity depth.',
      },
      {
        name: 'Discount Maker Queue Depth',
        source: 'CLOB Level-2 Depth Accumulator',
        freq: '200ms',
        desc: 'Number of resting contracts ahead in line at key discount levels ($0.48, $0.50, $0.52).',
      },
    ],
    tuningDials: [
      {
        param: 'discount_limit_price',
        defaultVal: '$0.48 – $0.52',
        range: '$0.40 – $0.58',
        desc: 'Maximum limit price the bot will post resting orders at to guarantee positive risk/reward asymmetry.',
      },
      {
        param: 'min_edge_pct',
        defaultVal: '8.0%',
        range: '2.0% – 25.0%',
        desc: 'Minimum theoretical edge over the implied market probability before placing resting orders.',
      },
      {
        param: 'vpin_toxic_threshold',
        defaultVal: '0.60',
        range: '0.40 – 0.85',
        desc: 'Threshold above which adverse selection is too high, vetoing resting bids.',
      },
      {
        param: 'max_spread_cents',
        defaultVal: '3.0¢',
        range: '1.0¢ – 10.0¢',
        desc: 'Maximum bid/ask spread permitted. Wider spreads flag illiquid markets and cancel orders.',
      },
    ],
    namedOutputs: [
      {
        variable: 'clob_direction',
        type: 'string',
        unit: 'YES | NO | FLAT',
        desc: 'Optimal contract side offering mispriced edge relative to fair value.',
      },
      {
        variable: 'maker_ev_dollars',
        type: 'Decimal',
        unit: '$/contract',
        desc: 'Expected net profit per contract after subtracting maker fees ($0.00) and probability payout.',
      },
      {
        variable: 'spread_efficiency_score',
        type: 'float',
        unit: '0.00 – 1.00',
        desc: 'Liquidity score indicating tightness of the inside touch spread.',
      },
      {
        variable: 'queue_fill_probability',
        type: 'float',
        unit: '0–100%',
        desc: 'Estimated probability of resting order getting filled based on queue position and cancel rate.',
      },
    ],
    liveStrengths: [
      '🛡️ $0.00 Maker fee architecture: Exploits maker rebates and zero taker fees to avoid fee drag.',
      '💰 Asymmetric payoff: Buying at 48¢–50¢ provides a >1:1 risk-to-reward ratio on binary settlement.',
      '⚖️ Uncrossed book invariant: Continuous sequence tracking ensures the engine never trades on stale books.',
    ],
    liveWeaknesses: [
      '⚠️ Latent spot disconnect: The Kalshi book is slow. If spot drops violently, resting bids get picked off.',
      '⚠️ Low-fill frustration: In strong trending markets, resting discount maker limit orders at 48¢ never fill.',
      '⚠️ Adverse selection trap: The only time your 48¢ limit order gets filled might be when the trade has gone bad.',
    ],
    botSuitability: [
      {
        bot: 'Bot 1 (Dominion Sniper)',
        recommendation: 'MUST USE',
        reason: 'Cylinder 2 is the core foundation of Bot 1; it enforces discount pricing and zero taker fees.',
      },
      {
        bot: 'Bot 2 (ONNX Scalper)',
        recommendation: 'MUST USE',
        reason: 'Needed to measure Kalshi repricing latency against Cylinder 1 spot signals.',
      },
      {
        bot: 'Bot 3 (Macro Trend)',
        recommendation: 'MUST USE',
        reason: 'Ensures the macro bot does not overpay above 52¢ even when trend conviction is high.',
      },
      {
        bot: 'Bot X (New Custom Bot)',
        recommendation: 'MUST USE',
        reason: 'Non-negotiable for all Kalshi bots to maintain strict mathematical positive EV.',
      },
    ],
  },
  {
    id: 'cylinder3',
    name: 'HMM Macro Regime & Calibration Radar',
    shortName: 'HMM Macro Regime',
    cylinderNum: 3,
    icon: Activity,
    color: '#38bdf8',
    badgeBg: 'rgba(56, 189, 248, 0.1)',
    badgeBorder: 'rgba(56, 189, 248, 0.3)',
    cadence: '1m / 5m Candle Closes',
    rawInputs: [
      {
        name: '1-Minute & 5-Minute OHLCV Candles',
        source: 'Real-time CandleBuilder Aggregator',
        freq: '1m / 5m boundary',
        desc: 'High, low, open, close, and volume across multi-timeframe candle boundaries.',
      },
      {
        name: 'Realized ATR Volatility (14-period)',
        source: 'Mathematical Volatility Transform',
        freq: '1m close',
        desc: 'Actual rolling dollar volatility (e.g. $14–$45) compared to baseline expectation.',
      },
      {
        name: 'Wick Rejection & Exhaustion Ratios',
        source: 'Price Action Kinematics',
        freq: '1m close',
        desc: 'Upper and lower shadow wick length relative to real body to spot false breakouts.',
      },
      {
        name: 'Prediction Feedback (Brier Error Score)',
        source: 'Mistake-Learning Database',
        freq: 'Settlement cycle',
        desc: 'Calibration accuracy tracking: (Forecasted Prob - Actual Outcome)^2 across past 50 trades.',
      },
    ],
    tuningDials: [
      {
        param: 'hmm_states',
        defaultVal: '3 States',
        range: '2 – 5 States',
        desc: 'Discrete hidden Markov regimes: State 0 (Quiet Chop), State 1 (Trending), State 2 (Turbulent Shock).',
      },
      {
        param: 'regime_lookback_candles',
        defaultVal: '30 candles (30m)',
        range: '10 – 100',
        desc: 'Number of historical candles fed into the Baum-Welch / Viterbi transition matrix.',
      },
      {
        param: 'min_regime_stability_pct',
        defaultVal: '75.0%',
        range: '60% – 90%',
        desc: 'Posterior probability certainty required before declaring an official regime shift.',
      },
      {
        param: 'brier_decay_rate',
        defaultVal: '0.95',
        range: '0.80 – 0.99',
        desc: 'Exponential weighting decay for penalizing model confidence after recent streak losses.',
      },
    ],
    namedOutputs: [
      {
        variable: 'market_regime',
        type: 'string',
        unit: 'QUIET | TRENDING | TURBULENT',
        desc: 'Current structural state of the market estimated by the hidden Markov transition matrix.',
      },
      {
        variable: 'regime_conviction',
        type: 'float',
        unit: '0.00 – 1.00 (0–100%)',
        desc: 'Mathematical certainty of the current state assignment.',
      },
      {
        variable: 'volatility_forecast (ATR)',
        type: 'float',
        unit: '$ / minute',
        desc: 'Estimated 1-minute expected price dispersion for dynamic strike moat calculations.',
      },
      {
        variable: 'mistake_learning_penalty',
        type: 'float',
        unit: '0.00 – 0.50 multiplier',
        desc: 'Shrinkage factor applied to position sizing when recent predictions deviate from reality.',
      },
    ],
    liveStrengths: [
      '🛡️ Regime radar: Vetoes trades during TURBULENT states (e.g. CPI/FOMC news shocks) before capital is lost.',
      '🧠 Mistake-learning engine: Automatically lowers position sizing if market conditions deviate from training.',
      '📈 Trend conviction: Locks in high-probability continuation trades when market enters pure TRENDING mode.',
    ],
    liveWeaknesses: [
      '⚠️ Multi-minute lag: Because it waits for candle closes, it cannot react to a sudden 1-second spike.',
      '⚠️ Regime shift whipsaws: In choppy transitions, the model can lag by 1 to 2 candles while regimes alternate.',
      '⚠️ Ineffective for ultra-fast scalping: If your trade duration is <90s, Cylinder 3 is too slow to provide alpha.',
    ],
    botSuitability: [
      {
        bot: 'Bot 1 (Dominion Sniper)',
        recommendation: 'OPTIONAL (AS VETO)',
        reason: 'Useful as a blackout veto during TURBULENT states, but not needed for the entry trigger.',
      },
      {
        bot: 'Bot 2 (ONNX Scalper)',
        recommendation: 'DISCONNECT',
        reason: 'Bot 2 operates in the sub-second domain; waiting for 5-minute HMM updates destroys HFT alpha.',
      },
      {
        bot: 'Bot 3 (Macro Trend)',
        recommendation: 'MUST USE',
        reason: 'Cylinder 3 is the primary driver of Bot 3; it ensures trades only fire when regime is TRENDING.',
      },
      {
        bot: 'Bot X (New Custom Bot)',
        recommendation: 'OPTIONAL',
        reason: 'Connect if Bot X is a trend-follower or swing trader; disconnect if Bot X is a sub-minute scalper.',
      },
    ],
  },
];

export const EngineRoomMatrix: React.FC<EngineRoomMatrixProps> = ({
  activeTab = 'matrix',
  onTabChange,
}) => {
  const [currentTab, setCurrentTab] = useState<EngineViewTab>(activeTab);
  const [botXWiring, setBotXWiring] = useState<{
    cyl1: boolean;
    cyl2: boolean;
    cyl3: boolean;
    role: string;
  }>({
    cyl1: true,
    cyl2: true,
    cyl3: false,
    role: 'Flash Momentum Sniper (Sub-90s)',
  });

  const handleTabClick = (tab: EngineViewTab) => {
    soundFX.playClickSound();
    setCurrentTab(tab);
    if (onTabChange) onTabChange(tab);
  };

  const toggleBotX = (cyl: 'cyl1' | 'cyl2' | 'cyl3') => {
    soundFX.playClickSound();
    setBotXWiring((prev) => {
      const updated = { ...prev, [cyl]: !prev[cyl] };
      let role = 'Custom Hybrid Strategy';
      if (updated.cyl1 && updated.cyl2 && !updated.cyl3) role = 'Sub-90s High-Frequency Arbitrage (Speed)';
      else if (!updated.cyl1 && updated.cyl2 && updated.cyl3) role = 'Macro Trend & Maker Edge Sniper (Patience)';
      else if (updated.cyl1 && updated.cyl2 && updated.cyl3) role = 'Triple-Brain Unanimous Consensus (Full Armor)';
      else if (!updated.cyl1 && updated.cyl2 && !updated.cyl3) role = 'Pure Maker Discount Limit Harvester (Bot 1 Style)';
      else if (updated.cyl1 && !updated.cyl2 && !updated.cyl3) role = 'Raw Spot Velocity Chaser (High Risk)';
      else if (!updated.cyl1 && !updated.cyl2 && updated.cyl3) role = 'Regime Transition Predictor';
      return { ...updated, role };
    });
  };

  return (
    <div className="space-y-6">
      {/* 1. Header Banner & Diagnostics Bench */}
      <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[#38bdf8]/10 border border-[#38bdf8]/30 flex items-center justify-center text-[#38bdf8]">
              <Cpu className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold uppercase tracking-wider text-white">
                  Engine Room: The 3-Cylinder Powertrain
                </h1>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#38bdf8]/15 border border-[#38bdf8]/40 text-[#38bdf8]">
                  CORE SPECIFICATION MATRIX
                </span>
              </div>
              <p className="text-xs text-[#8c9ba5] mt-0.5">
                Educational teardown of the 3 predictive brains: Raw Market Inputs ➔ Tuning Dials ➔ Refined Named Outputs ➔ Real Live Strengths & Failure Modes.
              </p>
            </div>
          </div>

          {/* Quick Stats Pill */}
          <div className="flex items-center gap-2 font-mono text-xs bg-[#171c22] border border-[#262d35] rounded-lg p-2 self-start md:self-auto">
            <div className="flex items-center gap-1.5 px-2 py-1 bg-[#12161a] rounded border border-[#262d35]">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-white text-[11px]">ECU: 5Hz BRTI Synchronized</span>
            </div>
            <div className="flex items-center gap-1.5 px-2 py-1 bg-[#12161a] rounded border border-[#262d35] text-[#8c9ba5] text-[11px]">
              <span>Skew:</span>
              <span className="text-emerald-400 font-bold">18ms</span>
            </div>
          </div>
        </div>

        {/* View Mode Switcher Tabs */}
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[#262d35]/60">
          <button
            onClick={() => handleTabClick('matrix')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
              currentTab === 'matrix'
                ? 'bg-[#00bda5]/15 text-[#00bda5] border border-[#00bda5]/40 font-bold'
                : 'text-[#8c9ba5] hover:text-white bg-[#171c22] border border-transparent'
            }`}
          >
            <Gauge className="w-3.5 h-3.5" />
            <span>Master Visual Matrix (All 3)</span>
          </button>

          <button
            onClick={() => handleTabClick('cylinder1')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
              currentTab === 'cylinder1'
                ? 'bg-[#f59e0b]/15 text-[#f59e0b] border border-[#f59e0b]/40 font-bold'
                : 'text-[#8c9ba5] hover:text-white bg-[#171c22] border border-transparent'
            }`}
          >
            <Zap className="w-3.5 h-3.5 text-[#f59e0b]" />
            <span>Cylinder 1: Spot Orderflow</span>
          </button>

          <button
            onClick={() => handleTabClick('cylinder2')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
              currentTab === 'cylinder2'
                ? 'bg-[#00bda5]/15 text-[#00bda5] border border-[#00bda5]/40 font-bold'
                : 'text-[#8c9ba5] hover:text-white bg-[#171c22] border border-transparent'
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-[#00bda5]" />
            <span>Cylinder 2: Kalshi CLOB</span>
          </button>

          <button
            onClick={() => handleTabClick('cylinder3')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
              currentTab === 'cylinder3'
                ? 'bg-[#38bdf8]/15 text-[#38bdf8] border border-[#38bdf8]/40 font-bold'
                : 'text-[#8c9ba5] hover:text-white bg-[#171c22] border border-transparent'
            }`}
          >
            <Activity className="w-3.5 h-3.5 text-[#38bdf8]" />
            <span>Cylinder 3: HMM Macro Regime</span>
          </button>

          <button
            onClick={() => handleTabClick('wiring')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ml-auto ${
              currentTab === 'wiring'
                ? 'bg-purple-500/15 text-purple-400 border border-purple-500/40 font-bold'
                : 'text-[#8c9ba5] hover:text-white bg-[#171c22] border border-transparent'
            }`}
          >
            <Sliders className="w-3.5 h-3.5 text-purple-400" />
            <span>Bot Harness & Wiring Board</span>
          </button>
        </div>
      </div>

      {/* 2. TAB: Master Visual Matrix (Side-by-Side 3-Cylinder Overview) */}
      {(currentTab === 'matrix' || currentTab === 'wiring') && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {CYLINDERS.map((cyl) => {
            const Icon = cyl.icon;
            return (
              <div
                key={cyl.id}
                className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 flex flex-col justify-between space-y-4 hover:border-[#38bdf8]/40 transition-all"
              >
                <div>
                  {/* Cylinder Badge */}
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span
                        className="px-2 py-0.5 rounded text-[10px] font-mono font-bold"
                        style={{ background: cyl.badgeBg, border: `1px solid ${cyl.badgeBorder}`, color: cyl.color }}
                      >
                        CYLINDER {cyl.cylinderNum}
                      </span>
                      <span className="text-[11px] font-mono text-[#8c9ba5]">{cyl.cadence}</span>
                    </div>
                    <Icon className="w-5 h-5" style={{ color: cyl.color }} />
                  </div>

                  <h3 className="text-sm font-bold text-white mb-1">{cyl.name}</h3>
                  <p className="text-xs text-[#8c9ba5] mb-4">
                    Refines raw high-speed market feeds into mathematically verified directional edge.
                  </p>

                  {/* Section A: What We Fetch (Inputs) */}
                  <div className="space-y-2 mb-4">
                    <div className="text-[11px] font-mono uppercase font-bold text-[#8c9ba5] flex items-center gap-1.5">
                      <Database className="w-3.5 h-3.5 text-amber-400" />
                      <span>1. What We Fetch (Fuel):</span>
                    </div>
                    <div className="bg-[#171c22] rounded-lg p-2.5 border border-[#262d35] space-y-1.5">
                      {cyl.rawInputs.map((inp, idx) => (
                        <div key={idx} className="flex items-center justify-between text-xs">
                          <span className="text-slate-300 font-medium">• {inp.name}</span>
                          <span className="text-[10px] font-mono text-amber-400/80">{inp.freq}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Section B: What The Refined Output Is Called */}
                  <div className="space-y-2 mb-4">
                    <div className="text-[11px] font-mono uppercase font-bold text-[#8c9ba5] flex items-center gap-1.5">
                      <Radio className="w-3.5 h-3.5 text-emerald-400" />
                      <span>2. Named Refined Outputs:</span>
                    </div>
                    <div className="bg-[#171c22] rounded-lg p-2.5 border border-[#262d35] space-y-1.5">
                      {cyl.namedOutputs.map((out, idx) => (
                        <div key={idx} className="flex items-center justify-between text-xs font-mono">
                          <span className="text-emerald-400 font-bold">{out.variable}</span>
                          <span className="text-[10px] text-[#8c9ba5]">{out.unit}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Section C: Live Trading Superpower */}
                  <div className="space-y-1.5 mb-3">
                    <div className="text-[11px] font-mono uppercase font-bold text-emerald-400 flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>3. Superpower (When Strong):</span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed bg-emerald-500/5 border border-emerald-500/20 rounded-lg p-2.5">
                      {cyl.liveStrengths[0]}
                    </p>
                  </div>

                  {/* Section D: Live Trading Kryptonite (Weakness) */}
                  <div className="space-y-1.5">
                    <div className="text-[11px] font-mono uppercase font-bold text-rose-400 flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      <span>4. Kryptonite (Live Failure Mode):</span>
                    </div>
                    <p className="text-xs text-rose-200/90 leading-relaxed bg-rose-500/5 border border-rose-500/20 rounded-lg p-2.5">
                      {cyl.liveWeaknesses[0]}
                    </p>
                  </div>
                </div>

                {/* Card Footer Button */}
                <button
                  onClick={() => handleTabClick(cyl.id as EngineViewTab)}
                  className="w-full mt-4 py-2 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 transition-all bg-[#171c22] hover:bg-[#262d35] text-white border border-[#262d35]"
                >
                  <span>Inspect Full Specification</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* 3. TAB: Individual Cylinder Deep-Dives */}
      {currentTab !== 'matrix' && currentTab !== 'wiring' && (
        <div>
          {CYLINDERS.filter((c) => c.id === currentTab).map((cyl) => {
            const Icon = cyl.icon;
            return (
              <div key={cyl.id} className="space-y-6">
                {/* Cylinder Header Card */}
                <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-6">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-12 h-12 rounded-xl flex items-center justify-center"
                        style={{ background: cyl.badgeBg, border: `1px solid ${cyl.badgeBorder}`, color: cyl.color }}
                      >
                        <Icon className="w-7 h-7" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span
                            className="px-2 py-0.5 rounded text-[10px] font-mono font-bold"
                            style={{ background: cyl.badgeBg, border: `1px solid ${cyl.badgeBorder}`, color: cyl.color }}
                          >
                            CYLINDER {cyl.cylinderNum} SPECIFICATION
                          </span>
                          <span className="text-xs font-mono text-[#8c9ba5]">Stream Cadence: {cyl.cadence}</span>
                        </div>
                        <h2 className="text-lg font-bold text-white mt-1">{cyl.name}</h2>
                      </div>
                    </div>

                    <button
                      onClick={() => handleTabClick('matrix')}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#171c22] hover:bg-[#262d35] text-[#8c9ba5] hover:text-white border border-[#262d35] self-start md:self-auto"
                    >
                      ← Back to All 3 Cylinders
                    </button>
                  </div>

                  {/* 4-Column Teardown Matrix */}
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
                    {/* Fuel Box */}
                    <div className="bg-[#171c22] border border-[#262d35] rounded-lg p-4 space-y-2">
                      <div className="flex items-center gap-2 text-xs font-mono font-bold text-amber-400 uppercase">
                        <Database className="w-4 h-4" />
                        <span>1. Raw Market Fuel</span>
                      </div>
                      <p className="text-[11px] text-[#8c9ba5]">Incoming raw ticks fetched continuously before tensor transformation:</p>
                      <ul className="space-y-2 text-xs text-slate-300">
                        {cyl.rawInputs.map((item, idx) => (
                          <li key={idx} className="border-t border-[#262d35]/60 pt-1.5">
                            <span className="font-bold text-white">{item.name}</span>
                            <div className="text-[10px] text-[#8c9ba5] font-mono">{item.source} ({item.freq})</div>
                            <div className="text-[10px] text-slate-400 mt-0.5">{item.desc}</div>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Dials Box */}
                    <div className="bg-[#171c22] border border-[#262d35] rounded-lg p-4 space-y-2">
                      <div className="flex items-center gap-2 text-xs font-mono font-bold text-[#38bdf8] uppercase">
                        <Sliders className="w-4 h-4" />
                        <span>2. Internal Tuning Dials</span>
                      </div>
                      <p className="text-[11px] text-[#8c9ba5]">Parameters inside the cylinder you adjust to tighten or loosen risk:</p>
                      <ul className="space-y-2 text-xs text-slate-300">
                        {cyl.tuningDials.map((item, idx) => (
                          <li key={idx} className="border-t border-[#262d35]/60 pt-1.5">
                            <div className="flex items-center justify-between">
                              <span className="font-mono font-bold text-[#38bdf8]">{item.param}</span>
                              <span className="text-[10px] font-mono text-white bg-[#12161a] px-1.5 py-0.5 rounded border border-[#262d35]">
                                {item.defaultVal}
                              </span>
                            </div>
                            <div className="text-[10px] text-slate-400 mt-0.5">{item.desc}</div>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Outputs Box */}
                    <div className="bg-[#171c22] border border-[#262d35] rounded-lg p-4 space-y-2">
                      <div className="flex items-center gap-2 text-xs font-mono font-bold text-emerald-400 uppercase">
                        <Radio className="w-4 h-4" />
                        <span>3. Refined Output Variables</span>
                      </div>
                      <p className="text-[11px] text-[#8c9ba5]">What the refined telemetry is called when passed to the bots:</p>
                      <ul className="space-y-2 text-xs text-slate-300">
                        {cyl.namedOutputs.map((item, idx) => (
                          <li key={idx} className="border-t border-[#262d35]/60 pt-1.5">
                            <div className="flex items-center justify-between font-mono">
                              <span className="font-bold text-emerald-400">{item.variable}</span>
                              <span className="text-[10px] text-[#8c9ba5]">{item.unit}</span>
                            </div>
                            <div className="text-[10px] text-slate-400 mt-0.5">{item.desc}</div>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Strengths & Kryptonite Box */}
                    <div className="bg-[#171c22] border border-[#262d35] rounded-lg p-4 space-y-3">
                      <div className="space-y-1.5">
                        <div className="flex items-center gap-2 text-xs font-mono font-bold text-emerald-400 uppercase">
                          <CheckCircle2 className="w-4 h-4" />
                          <span>Real Live Superpower:</span>
                        </div>
                        <ul className="space-y-1 text-xs text-slate-300">
                          {cyl.liveStrengths.map((str, idx) => (
                            <li key={idx} className="text-[11px] leading-relaxed text-emerald-300/90">
                              {str}
                            </li>
                          ))}
                        </ul>
                      </div>

                      <div className="border-t border-[#262d35] pt-3 space-y-1.5">
                        <div className="flex items-center gap-2 text-xs font-mono font-bold text-rose-400 uppercase">
                          <AlertTriangle className="w-4 h-4" />
                          <span>Real Live Kryptonite (Weakness):</span>
                        </div>
                        <ul className="space-y-1 text-xs text-slate-300">
                          {cyl.liveWeaknesses.map((wk, idx) => (
                            <li key={idx} className="text-[11px] leading-relaxed text-rose-300/90">
                              {wk}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Bot Suitability Guide */}
                <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-3">
                  <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-purple-400" />
                    <span>How to Wire Cylinder {cyl.cylinderNum} into Active & Future Bots</span>
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                    {cyl.botSuitability.map((suit, idx) => {
                      const isMust = suit.recommendation === 'MUST USE';
                      const isOpt = suit.recommendation === 'OPTIONAL';
                      const isDisc = suit.recommendation === 'DISCONNECT';
                      return (
                        <div key={idx} className="bg-[#171c22] border border-[#262d35] rounded-lg p-3 space-y-1.5">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-xs text-white">{suit.bot}</span>
                            <span
                              className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${
                                isMust
                                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                                  : isOpt
                                  ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                                  : 'bg-rose-500/20 text-rose-400 border border-rose-500/40'
                              }`}
                            >
                              {suit.recommendation}
                            </span>
                          </div>
                          <p className="text-[10px] text-[#8c9ba5] leading-relaxed">{suit.reason}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 4. TAB: Bot Wiring Harness & Customizable "Bot X" Plugboard */}
      <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-6 space-y-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-400">
              <Sliders className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                The Bot Wiring Harness: Know-The-Engine Plugboard
              </h2>
              <p className="text-xs text-[#8c9ba5]">
                See which bots are connected to which cylinders, or wire up a custom <strong>Bot X</strong> to test modular combinations.
              </p>
            </div>
          </div>

          <span className="text-[11px] font-mono text-purple-400 bg-purple-500/10 border border-purple-500/30 px-2.5 py-1 rounded-md self-start md:self-auto">
            Zero Code Drift • Modular Socket Architecture
          </span>
        </div>

        {/* The Comparative Matrix Table */}
        <div className="overflow-x-auto border border-[#262d35] rounded-lg">
          <table className="w-full text-left text-xs font-mono border-collapse">
            <thead>
              <tr className="bg-[#171c22] border-b border-[#262d35] text-[#8c9ba5] uppercase text-[10px]">
                <th className="p-3">Bot Entity</th>
                <th className="p-3">Cylinder 1: Spot Orderflow</th>
                <th className="p-3">Cylinder 2: Kalshi CLOB</th>
                <th className="p-3">Cylinder 3: HMM Macro</th>
                <th className="p-3">Execution Role & Philosophy</th>
                <th className="p-3 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#262d35]/60">
              {/* Bot 1 */}
              <tr className="hover:bg-[#171c22]/40 transition-colors">
                <td className="p-3 font-bold text-white flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-400" />
                  <span>Bot 1 (Dominion)</span>
                </td>
                <td className="p-3 text-rose-400 font-bold">❌ DISCONNECTED</td>
                <td className="p-3 text-emerald-400 font-bold">🔌 CONNECTED (100%)</td>
                <td className="p-3 text-amber-400 font-bold">🛡️ VETO ONLY (Blackout)</td>
                <td className="p-3 text-slate-300 font-sans text-xs">
                  Micro-bankroll ($22) sniper. Trades 48¢–52¢ maker limits with $0.00 fee. Never overtrades.
                </td>
                <td className="p-3 text-right">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 border border-emerald-500/40 text-emerald-400">
                    LIVE ARMED (Port 8001)
                  </span>
                </td>
              </tr>

              {/* Bot 2 */}
              <tr className="hover:bg-[#171c22]/40 transition-colors">
                <td className="p-3 font-bold text-white flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-amber-400" />
                  <span>Bot 2 (ONNX Scalper)</span>
                </td>
                <td className="p-3 text-emerald-400 font-bold">🔌 CONNECTED (100%)</td>
                <td className="p-3 text-emerald-400 font-bold">🔌 CONNECTED (100%)</td>
                <td className="p-3 text-rose-400 font-bold">❌ DISCONNECTED</td>
                <td className="p-3 text-slate-300 font-sans text-xs">
                  Sub-90s HFT scalper. Exploits sub-second latency mismatch between Binance and Kalshi.
                </td>
                <td className="p-3 text-right">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/15 border border-amber-500/40 text-amber-400">
                    INCUBATOR (Port 8002)
                  </span>
                </td>
              </tr>

              {/* Bot 3 */}
              <tr className="hover:bg-[#171c22]/40 transition-colors">
                <td className="p-3 font-bold text-white flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#38bdf8]" />
                  <span>Bot 3 (Macro Trend)</span>
                </td>
                <td className="p-3 text-[#38bdf8] font-bold">🔍 CONFIRMATION ONLY</td>
                <td className="p-3 text-emerald-400 font-bold">🔌 CONNECTED (52¢ Cap)</td>
                <td className="p-3 text-emerald-400 font-bold">👑 MASTER DRIVER (HMM)</td>
                <td className="p-3 text-slate-300 font-sans text-xs">
                  Mid-cycle trend rider. Waits for 1m/5m HMM regime confirmation, then snipes 52¢ contracts.
                </td>
                <td className="p-3 text-right">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/15 border border-blue-500/40 text-blue-400">
                    PAPER RUN (Port 8003)
                  </span>
                </td>
              </tr>

              {/* Bot X Interactive Row */}
              <tr className="bg-purple-950/20 border-t-2 border-purple-500/30">
                <td className="p-3 font-bold text-purple-300 flex items-center gap-2">
                  <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                  <span>Bot X (Custom Wire)</span>
                </td>
                <td className="p-3">
                  <button
                    onClick={() => toggleBotX('cyl1')}
                    className={`px-2.5 py-1 rounded text-[11px] font-bold transition-all flex items-center gap-1.5 ${
                      botXWiring.cyl1
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                        : 'bg-[#171c22] text-[#8c9ba5] border border-[#262d35]'
                    }`}
                  >
                    <Power className="w-3 h-3" />
                    <span>{botXWiring.cyl1 ? 'PLUGGED IN' : 'DETACHED'}</span>
                  </button>
                </td>
                <td className="p-3">
                  <button
                    onClick={() => toggleBotX('cyl2')}
                    className={`px-2.5 py-1 rounded text-[11px] font-bold transition-all flex items-center gap-1.5 ${
                      botXWiring.cyl2
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                        : 'bg-[#171c22] text-[#8c9ba5] border border-[#262d35]'
                    }`}
                  >
                    <Power className="w-3 h-3" />
                    <span>{botXWiring.cyl2 ? 'PLUGGED IN' : 'DETACHED'}</span>
                  </button>
                </td>
                <td className="p-3">
                  <button
                    onClick={() => toggleBotX('cyl3')}
                    className={`px-2.5 py-1 rounded text-[11px] font-bold transition-all flex items-center gap-1.5 ${
                      botXWiring.cyl3
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                        : 'bg-[#171c22] text-[#8c9ba5] border border-[#262d35]'
                    }`}
                  >
                    <Power className="w-3 h-3" />
                    <span>{botXWiring.cyl3 ? 'PLUGGED IN' : 'DETACHED'}</span>
                  </button>
                </td>
                <td className="p-3 text-purple-200 font-sans text-xs">
                  <strong>Synthesized Role:</strong> {botXWiring.role}
                </td>
                <td className="p-3 text-right">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/15 border border-purple-500/40 text-purple-300">
                    INTERACTIVE BENCH
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Educational Takeaway Callout */}
        <div className="bg-[#171c22] border border-[#262d35] rounded-lg p-4 flex items-start gap-3 text-xs">
          <div className="p-1.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 mt-0.5">
            <HelpCircle className="w-4 h-4" />
          </div>
          <div className="space-y-1">
            <h4 className="font-bold text-white">The Golden Rule of the Engine:</h4>
            <p className="text-[#8c9ba5] leading-relaxed">
              Every cylinder has an unavoidable kryptonite. When engineering a new bot, do not blindly connect all 3 brains. Connect the cylinders whose strengths match your cycle timeframe, and disconnect the cylinders whose blindspots would sabotage your trade.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
