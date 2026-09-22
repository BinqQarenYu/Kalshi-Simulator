import React from 'react';
import {
  Cpu,
  Layers,
  Activity,
  Award,
  Crown,
  ShieldCheck,
  TrendingUp,
  AlertTriangle,
  Zap,
  Sliders,
  DollarSign,
  Play,
  RotateCcw,
} from 'lucide-react';
import {
  AISignals,
  MacroDominionTelemetry,
  HMMMacroRegimeTelemetry,
  MarketState,
} from '../types';
import { soundFX } from '../utils/audioFX';

interface GoldOnnxCardProps {
  market: MarketState;
  signals?: AISignals;
  macroDominionTelemetry?: MacroDominionTelemetry;
  hmmMacroRegime?: HMMMacroRegimeTelemetry;
  onSelectStrategy?: (strategyId: string) => Promise<any>;
  onTestBot?: () => Promise<any>;
  onOpenReports?: () => void;
}

export const GoldOnnxCard: React.FC<GoldOnnxCardProps> = React.memo(({
  market,
  signals,
  macroDominionTelemetry,
  hmmMacroRegime,
  onSelectStrategy,
  onTestBot,
  onOpenReports,
}) => {
  const telemetry = macroDominionTelemetry;
  const decision = telemetry?.call ?? (signals?.recommended_side ? signals.recommended_side.toUpperCase() : 'WAIT');
  const confidence = telemetry?.confidence_pct ?? (signals?.onnx_confidence ? signals.onnx_confidence * 100 : 50);

  const isBull = decision === 'YES';
  const isBear = decision === 'NO';
  const isWait = !isBull && !isBear;

  const spotScore = telemetry?.spot_confidence ?? (signals?.onnx_prob_long ?? 0.50);
  const kalshiScore = telemetry?.kalshi_confidence ?? (signals?.kalshi_confidence ?? 0.50);
  const hmmState = hmmMacroRegime?.regime_label ?? telemetry?.hmm_regime ?? 'STABLE_RANGE';
  const mistakeShrinkage = telemetry?.brier_shrinkage_factor ? (1 - telemetry.brier_shrinkage_factor) * 100 : 0.0;

  return (
    <div className="bg-[#0f141c] border border-amber-500/30 rounded-2xl p-4 sm:p-5 flex flex-col gap-4 shadow-2xl relative overflow-hidden">
      {/* Background Gold Ambient Glow */}
      <div className="absolute top-0 right-0 w-72 h-72 bg-amber-500/5 rounded-full blur-3xl pointer-events-none" />

      {/* Header Banner */}
      <div className="flex items-center justify-between border-b border-[#212836] pb-3 z-10">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-xl bg-amber-500/20 border border-amber-500/50 flex items-center justify-center shadow-lg shadow-amber-500/10">
            <Crown className="h-4 w-4 text-amber-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-black text-white tracking-wide uppercase">
                Gold ONNX Bot (Triple-Brain Dominion)
              </h2>
              <span className="px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider bg-amber-500/20 text-amber-300 border border-amber-500/40">
                SEAL OF EXCELLENCE
              </span>
            </div>
            <p className="text-[11px] text-gray-400 font-mono">
              Lane 1 Live · Binance Spot ONNX + Kalshi Micro ONNX + 5M HMM Consensus
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-2 py-1 rounded-lg text-[10px] font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            LIVE AUTHORIZED
          </span>
        </div>
      </div>

      {/* Hero Consensus Decision Box */}
      <div
        className={`p-4 rounded-xl border flex flex-col sm:flex-row items-center justify-between gap-4 transition-all ${
          isBull
            ? 'bg-emerald-950/20 border-emerald-500/40 shadow-lg shadow-emerald-950/20'
            : isBear
            ? 'bg-rose-950/20 border-rose-500/40 shadow-lg shadow-rose-950/20'
            : 'bg-[#141923] border-[#252d3d]'
        }`}
      >
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <div
            className={`px-3 py-2 rounded-xl font-mono font-black text-base uppercase tracking-wider border shadow-md ${
              isBull
                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50'
                : isBear
                ? 'bg-rose-500/20 text-rose-400 border-rose-500/50'
                : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
            }`}
          >
            {decision === 'YES' ? 'BUY YES' : decision === 'NO' ? 'BUY NO' : 'WAIT (CHOP)'}
          </div>
          <div>
            <div className="text-xs font-bold text-white flex items-center gap-2">
              <span>{telemetry?.rationale ?? 'Triple-Brain Consensus Synchronizing'}</span>
            </div>
            <div className="text-[11px] font-mono text-gray-400">
              Confidence:{' '}
              <span className="text-white font-bold">{confidence.toFixed(1)}%</span> · Moneyness:{' '}
              <span className="text-amber-300 font-bold">{market?.diff_str ?? '$0.00'}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
          <div className="text-right font-mono pr-2 border-r border-[#2a3447]">
            <div className="text-[9px] uppercase tracking-wider text-gray-400">Target Strike</div>
            <div className="text-xs font-bold text-white">{market?.target_strike_str ?? '$0.00'}</div>
          </div>
          <div className="text-right font-mono pl-1">
            <div className="text-[9px] uppercase tracking-wider text-gray-400">CF Spot (5Hz)</div>
            <div className="text-xs font-bold text-emerald-400">{market?.current_btc_price_str ?? '$0.00'}</div>
          </div>
        </div>
      </div>

      {/* The 3-Brain Consensus Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* Brain 1: Spot ONNX */}
        <div className="bg-[#141a24] border border-[#232b3a] border-t-2 border-t-cyan-500 rounded-xl p-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-[10px] font-mono font-bold text-gray-400 mb-1">
              <span className="flex items-center gap-1 text-cyan-400">
                <Cpu className="h-3 w-3" /> BRAIN 1: SPOT ONNX
              </span>
              <span className="text-white">{(spotScore * 100).toFixed(1)}%</span>
            </div>
            <div className="text-xs font-bold text-white mb-2">
              {spotScore >= 0.55 ? 'Bullish Spot Flow' : spotScore <= 0.45 ? 'Bearish Spot Flow' : 'Neutral / Absorption'}
            </div>
          </div>
          <div className="w-full bg-[#0a0d14] h-1.5 rounded-full overflow-hidden">
            <div
              className="bg-cyan-400 h-full transition-all duration-300"
              style={{ width: `${Math.min(100, Math.max(0, spotScore * 100))}%` }}
            />
          </div>
        </div>

        {/* Brain 2: Kalshi Binary CLOB ONNX */}
        <div className="bg-[#141a24] border border-[#232b3a] border-t-2 border-t-purple-500 rounded-xl p-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-[10px] font-mono font-bold text-gray-400 mb-1">
              <span className="flex items-center gap-1 text-purple-400">
                <Layers className="h-3 w-3" /> BRAIN 2: KALSHI CLOB
              </span>
              <span className="text-white">{(kalshiScore * 100).toFixed(1)}%</span>
            </div>
            <div className="text-xs font-bold text-white mb-2">
              {kalshiScore >= 0.55 ? 'OFI Bid Pressure' : kalshiScore <= 0.45 ? 'OFI Ask Pressure' : 'Balanced Book'}
            </div>
          </div>
          <div className="w-full bg-[#0a0d14] h-1.5 rounded-full overflow-hidden">
            <div
              className="bg-purple-400 h-full transition-all duration-300"
              style={{ width: `${Math.min(100, Math.max(0, kalshiScore * 100))}%` }}
            />
          </div>
        </div>

        {/* Brain 3: 5M HMM Regime */}
        <div className="bg-[#141a24] border border-[#232b3a] border-t-2 border-t-emerald-500 rounded-xl p-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-[10px] font-mono font-bold text-gray-400 mb-1">
              <span className="flex items-center gap-1 text-emerald-400">
                <TrendingUp className="h-3 w-3" /> BRAIN 3: 5M HMM
              </span>
              <span className="text-emerald-300">REGIME</span>
            </div>
            <div className="text-xs font-bold text-white truncate mb-2">
              {hmmState}
            </div>
          </div>
          <div className="text-[10px] font-mono text-gray-400">
            Volatility Moat: <span className="text-emerald-400 font-bold">1.36x ($47.60)</span>
          </div>
        </div>
      </div>

      {/* Online Mistake-Learning & Execution Guardrails */}
      <div className="bg-[#121722] border border-[#1e2533] rounded-xl p-3 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs font-mono">
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <div className="h-7 w-7 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center">
            <Sliders className="h-3.5 w-3.5 text-amber-400" />
          </div>
          <div>
            <div className="text-[11px] font-bold text-white">Online Mistake-Learning Shrinkage</div>
            <div className="text-[10px] text-gray-400">
              Loss Penalty Decile: <span className="text-amber-400">{mistakeShrinkage.toFixed(1)}%</span> · Auto-Pruning
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {onOpenReports && (
            <button
              onClick={() => {
                soundFX.playClickSound();
                onOpenReports();
              }}
              className="px-2.5 py-1 bg-[#1a212f] hover:bg-[#232c3d] text-gray-300 hover:text-white rounded-lg border border-[#2b364a] text-[10px] font-bold transition-all"
            >
              Audits & Reports
            </button>
          )}
          {onTestBot && (
            <button
              onClick={() => {
                soundFX.playClickSound();
                onTestBot();
              }}
              className="px-2.5 py-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 rounded-lg border border-amber-500/40 text-[10px] font-bold flex items-center gap-1 transition-all"
            >
              <Zap className="h-3 w-3" /> Test Inference
            </button>
          )}
        </div>
      </div>
    </div>
  );
});

GoldOnnxCard.displayName = 'GoldOnnxCard';
