import React from 'react';
import {
  TrendingUp,
  Cpu,
  Brain,
  Crown,
  Crosshair,
  Zap,
  Activity,
} from 'lucide-react';
import { BotProfile } from './BabyBotProfiles';
import {
  DualONNXTelemetry,
  MacroDominionTelemetry,
} from '../../types';

export interface BabyBotTelemetryDeckProps {
  isMacroDominion: boolean;
  activeProfile: BotProfile;
  macroAction: string;
  macroLimitPrice: number;
  macroCalibratedConf: number;
  macroRawConf: number;
  macroEv: number;
  botParams: Record<string, any>;
  macroRegimesAgree: boolean;
  macroSpotTrend: string;
  macroHmmRegime: string;
  quolasSignal: string;
  quolasConfidence: number;
  kalshiSignal: string;
  kalshiConfidence: number;
  macroBrier: string;
  macroPrunedDeciles: number[];
  macroTotalCycles: number;
  macroMistakes: number;
  macroAccuracy: string;
  macroDominionTelemetry?: MacroDominionTelemetry;
  dualRationale: string;
  dualRegime: string;
  dualOnnxTelemetry?: DualONNXTelemetry;
  onnxProbLong: number;
  onnxProbShort: number;
  onnxProbWait: number;
}

export const BabyBotTelemetryDeck: React.FC<BabyBotTelemetryDeckProps> = ({
  isMacroDominion,
  activeProfile,
  macroAction,
  macroLimitPrice,
  macroCalibratedConf,
  macroRawConf,
  macroEv,
  botParams,
  macroRegimesAgree,
  macroSpotTrend,
  macroHmmRegime,
  quolasSignal,
  quolasConfidence,
  kalshiSignal,
  kalshiConfidence,
  macroBrier,
  macroPrunedDeciles,
  macroTotalCycles,
  macroMistakes,
  macroAccuracy,
  macroDominionTelemetry,
  dualRationale,
  dualRegime,
  dualOnnxTelemetry,
  onnxProbLong,
  onnxProbShort,
  onnxProbWait,
}) => {
  return (
    <>
      {/* 5. STRATEGY-SPECIFIC TELEMETRY DECK */}
      {isMacroDominion ? (
        // --- Bot 3: Macro Trend Dominion 15M Triple-Brain & Mistake-Learning Deck ---
        <div className="p-3.5 bg-[#0a0f14] border-b border-[#262d35] space-y-3 font-mono">
          {/* Header Bar */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-bold text-white uppercase tracking-wider">
                Macro Trend Dominion
              </span>
              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                15M 3-BRAIN
              </span>
            </div>
            <span
              className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                macroAction === 'YES'
                  ? 'text-emerald-400 bg-emerald-500/15 border-emerald-500/30'
                  : macroAction === 'NO'
                  ? 'text-rose-400 bg-rose-500/15 border-rose-500/30'
                  : 'text-amber-400 bg-amber-500/15 border-amber-500/30'
              }`}
            >
              {macroAction === 'YES' && '🎯 CALL: BUY YES'}
              {macroAction === 'NO' && '🎯 CALL: BUY NO'}
              {macroAction === 'DONT' && '⏸️ CALL: DONT (HOLD)'}
            </span>
          </div>

          {/* Centerpiece 15M Decision Hero */}
          <div className={`p-3 rounded-xl border flex flex-col gap-2 ${
            macroAction === 'YES'
              ? 'bg-emerald-950/25 border-emerald-500/40 shadow-lg shadow-emerald-500/10 ring-1 ring-emerald-500/30'
              : macroAction === 'NO'
              ? 'bg-rose-950/25 border-rose-500/40 shadow-lg shadow-rose-500/10 ring-1 ring-rose-500/30'
              : 'bg-slate-900/60 border-slate-700/60'
          }`}>
            <div className="flex items-center justify-between border-b border-[#1f2833] pb-2">
              <div className="flex items-center gap-2">
                <span className={`text-xl font-black tracking-tight ${
                  macroAction === 'YES' ? 'text-emerald-400' : macroAction === 'NO' ? 'text-rose-400' : 'text-slate-300'
                }`}>
                  {macroAction === 'DONT' ? 'DONT (NO TRADE)' : `BUY ${macroAction}`}
                </span>
                <span className="text-[10px] text-slate-400">@ 15M Cycle</span>
              </div>
              <div className="text-right">
                <div className="text-sm font-black font-mono text-cyan-300">
                  {macroLimitPrice}¢ Limit
                </div>
                <div className="text-[9px] text-emerald-400/80 font-bold">
                  $0 Maker Fee · +{macroLimitPrice > 0 ? (((100 - macroLimitPrice) / macroLimitPrice) * 100).toFixed(0) : '0'}% ROI
                </div>
              </div>
            </div>

            {/* Metrics Triad: Calibrated Win %, Net EV, Consensus Agreement */}
            <div className="grid grid-cols-3 gap-2 pt-1 text-center">
              <div className="bg-[#0b1017] p-1.5 rounded border border-[#1e2530]">
                <div className="text-[8px] uppercase text-slate-400">Win Probability</div>
                <div className="text-xs font-black text-cyan-300 mt-0.5">
                  {macroCalibratedConf}%
                </div>
                <div className="text-[8px] text-slate-500">
                  Raw: {macroRawConf}% (Brier Cal)
                </div>
              </div>
              <div className="bg-[#0b1017] p-1.5 rounded border border-[#1e2530]">
                <div className="text-[8px] uppercase text-slate-400">Net EV / Ct</div>
                <div className={`text-xs font-black mt-0.5 ${macroEv >= 0.02 ? 'text-emerald-400' : 'text-slate-300'}`}>
                  {macroEv >= 0 ? '+' : ''}${macroEv.toFixed(2)}
                </div>
                <div className="text-[8px] text-slate-500">
                  Hurdle: &ge; ${(botParams.min_ev_dollars ?? 0.03).toFixed(2)}
                </div>
              </div>
              <div className="bg-[#0b1017] p-1.5 rounded border border-[#1e2530]">
                <div className="text-[8px] uppercase text-slate-400">Macro Agreement</div>
                <div className={`text-xs font-black mt-0.5 ${macroRegimesAgree ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {macroRegimesAgree ? 'AGREED' : 'DIVERGENT'}
                </div>
                <div className="text-[8px] text-slate-500 truncate">
                  {macroSpotTrend} vs {macroHmmRegime.replace('_TREND', '')}
                </div>
              </div>
            </div>
          </div>

          {/* Triple-Brain Consensus Grid */}
          <div className="grid grid-cols-3 gap-1.5 text-[9px]">
            {/* Brain 1: QuoLas Spot */}
            <div className="p-2 rounded bg-[#10151c] border border-cyan-500/30 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-cyan-400 font-bold">1. SPOT ONNX</span>
                <span className={`px-1 py-0.2 rounded font-bold ${quolasSignal === 'UP' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                  {quolasSignal}
                </span>
              </div>
              <div className="text-white font-bold">{quolasConfidence}% Conf</div>
              <div className="text-[8px] text-slate-500">CME 5Hz BRTI</div>
            </div>

            {/* Brain 2: Kalshi CLOB ONNX */}
            <div className="p-2 rounded bg-[#10151c] border border-purple-500/30 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-purple-400 font-bold">2. CLOB ONNX</span>
                <span className={`px-1 py-0.2 rounded font-bold ${kalshiSignal === 'UP' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                  {kalshiSignal}
                </span>
              </div>
              <div className="text-white font-bold">{kalshiConfidence}% Conf</div>
              <div className="text-[8px] text-slate-500">28-D Microstructure</div>
            </div>

            {/* Brain 3: 5m HMM Markov */}
            <div className="p-2 rounded bg-[#10151c] border border-amber-500/30 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-amber-400 font-bold">3. 5M HMM</span>
                <span className={`px-1 py-0.2 rounded font-bold ${macroHmmRegime.includes('BULL') ? 'bg-emerald-500/20 text-emerald-400' : macroHmmRegime.includes('BEAR') ? 'bg-rose-500/20 text-rose-400' : 'bg-amber-500/20 text-amber-300'}`}>
                  {macroHmmRegime.replace('_TREND', '')}
                </span>
              </div>
              <div className="text-white font-bold truncate">{macroSpotTrend} 1H</div>
              <div className="text-[8px] text-slate-500">Markov Anchor</div>
            </div>
          </div>

          {/* Mistake-Learning & Adaptation Engine Bar */}
          <div className="p-2.5 rounded-lg bg-[#0d1218] border border-[#1e2530] text-[10px] space-y-1.5">
            <div className="flex items-center justify-between text-slate-400">
              <span className="font-bold uppercase tracking-wider text-cyan-300 flex items-center gap-1">
                <Brain className="w-3.5 h-3.5 text-cyan-400" />
                <span>Dual Paper/Live Mistake-Learning Engine</span>
              </span>
              <span className="text-[9px] font-mono text-emerald-400 font-semibold">
                ONLINE TRACKING
              </span>
            </div>

            <div className="grid grid-cols-3 gap-1.5 text-center text-[9px] pt-0.5">
              <div className="bg-[#121820] p-1.5 rounded border border-[#212a36]">
                <div className="text-slate-400">Brier Score</div>
                <div className="text-white font-bold font-mono">{macroBrier}</div>
                <div className="text-[8px] text-emerald-400">Calibration OK</div>
              </div>
              <div className="bg-[#121820] p-1.5 rounded border border-[#212a36]">
                <div className="text-slate-400">Pruned Deciles</div>
                <div className="text-amber-300 font-bold font-mono">
                  {macroPrunedDeciles.length > 0 ? macroPrunedDeciles.map(d => `${d}¢`).join(', ') : 'None'}
                </div>
                <div className="text-[8px] text-slate-500">-EV Filter</div>
              </div>
              <div className="bg-[#121820] p-1.5 rounded border border-[#212a36]">
                <div className="text-slate-400">Cycles / Mistakes</div>
                <div className="text-white font-bold font-mono">
                  {macroTotalCycles}c / {macroMistakes}m
                </div>
                <div className="text-[8px] text-cyan-400">{macroAccuracy}% Accuracy</div>
              </div>
            </div>
          </div>

          {/* Rationale Banner */}
          <div className="p-2 rounded bg-[#10141a] border border-[#1e2530] text-[10px] text-slate-300">
            <span className="text-cyan-400 font-bold mr-1">Rationale:</span>
            <span>{macroDominionTelemetry?.rationale || dualRationale}</span>
          </div>
        </div>
      ) : activeProfile.telemetryType === 'onnx' ? (
        // --- ONNX Macro Net v2: Dual-Brain Neural Telemetry Deck ---
        <div className="p-3.5 bg-[#0e1117] border-b border-[#262d35] space-y-3 font-mono">
          {/* Header with Dual-Brain Mode & Status */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-purple-400" />
              <span className="text-xs font-bold text-white uppercase tracking-wider">
                {activeProfile.name}
              </span>
            </div>
            <span
              className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                dualRegime === 'MOMENTUM_SCALP'
                  ? 'text-emerald-400 bg-emerald-500/15 border-emerald-500/30'
                  : dualRegime === 'CONTRADICTION_ARBITRAGE'
                  ? 'text-cyan-400 bg-cyan-500/15 border-cyan-500/30 ring-1 ring-cyan-500/30 animate-pulse'
                  : dualRegime === 'TOXIC_VETO'
                  ? 'text-rose-400 bg-rose-500/15 border-rose-500/30'
                  : 'text-amber-400 bg-amber-500/15 border-amber-500/30'
              }`}
            >
              {dualRegime === 'MOMENTUM_SCALP' && '⚡ MOMENTUM SCALP'}
              {dualRegime === 'CONTRADICTION_ARBITRAGE' && '💎 CONTRADICTION ARB'}
              {dualRegime === 'TOXIC_VETO' && '🛡️ TOXIC VETO'}
              {dualRegime === 'CHOP_WAIT' && '⏸️ CHOP WAIT'}
            </span>
          </div>

          {/* Central Glowing Arbitrage Badge (Pillar 1) */}
          <div className="text-center py-0.5">
            <div className={`w-full py-1.5 px-2.5 rounded-xl font-mono text-[11px] font-extrabold uppercase border shadow-md flex items-center justify-center gap-2 transition-all ${
              dualRegime === 'CONTRADICTION_ARBITRAGE'
                ? 'bg-cyan-500/15 text-cyan-300 border-cyan-400/50 shadow-cyan-500/20 ring-1 ring-cyan-400/40 animate-pulse'
                : dualRegime === 'MOMENTUM_SCALP'
                ? 'bg-emerald-500/15 text-emerald-300 border-emerald-400/50 shadow-emerald-500/20 ring-1 ring-emerald-400/40 animate-pulse'
                : dualRegime === 'TOXIC_VETO'
                ? 'bg-rose-500/15 text-rose-300 border-rose-400/50 shadow-rose-500/20'
                : 'bg-[#151921] text-gray-400 border-gray-700'
            }`}>
              {dualRegime === 'CONTRADICTION_ARBITRAGE' && (
                <>
                  <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                  <span>💎 ASYMMETRIC DISCOUNT (BUY {(dualOnnxTelemetry?.side || (quolasSignal === 'UP' ? 'YES' : 'NO')).toUpperCase()} @ {((dualOnnxTelemetry?.recommended_limit_price ?? botParams.discount_limit_price ?? 0.48) * 100).toFixed(0)}¢)</span>
                </>
              )}
              {dualRegime === 'MOMENTUM_SCALP' && (
                <>
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                  <span>⚡ MOMENTUM VELOCITY SCALP (BUY {(dualOnnxTelemetry?.side || (quolasSignal === 'UP' ? 'YES' : 'NO')).toUpperCase()})</span>
                </>
              )}
              {dualRegime === 'TOXIC_VETO' && (
                <>
                  <span className="w-2 h-2 rounded-full bg-rose-400" />
                  <span>🔴 TOXIC VETO (SPOT DUMP / HIGH VPIN)</span>
                </>
              )}
              {dualRegime === 'CHOP_WAIT' && (
                <>
                  <span className="w-2 h-2 rounded-full bg-gray-500" />
                  <span>⏸️ CAPITAL PRESERVATION (CHOP WAIT)</span>
                </>
              )}
            </div>
          </div>

          {/* Dual-Brain Twin Cards: QuoLas (Spot) vs Kalshi (Binary CLOB) */}
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            {/* Brain A: QuoLas Nano Microscope (Spot Order Flow) */}
            <div className="p-2.5 rounded bg-[#13171c] border border-cyan-500/20 space-y-1.5 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-12 h-12 bg-cyan-500/5 rounded-full blur-xl pointer-events-none" />
              <div className="flex items-center justify-between">
                <span className="text-[9px] font-bold uppercase text-cyan-400 flex items-center gap-1">
                  <Activity className="w-3 h-3" />
                  QuoLas Spot
                </span>
                <span
                  className={`px-1.5 py-0.2 rounded font-bold text-[9px] ${
                    quolasSignal === 'UP'
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      : quolasSignal === 'DOWN'
                      ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                      : 'bg-slate-700 text-slate-300'
                  }`}
                >
                  {quolasSignal}
                </span>
              </div>
              <div className="flex items-baseline justify-between pt-0.5">
                <span className="text-[#8c9ba5] text-[9px]">Confidence:</span>
                <span className="text-white font-bold text-xs">{quolasConfidence}%</span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-[#1e252e] overflow-hidden">
                <div
                  className="h-full bg-cyan-400 transition-all duration-300"
                  style={{ width: `${quolasConfidence}%` }}
                />
              </div>
              <div className="text-[8px] text-[#6e7d8b] pt-0.5 flex justify-between">
                <span>Feed: CME BRTI (5Hz)</span>
                <span className="text-cyan-300/80">L2 Imbalance</span>
              </div>
            </div>

            {/* Brain B: Built-in Kalshi CLOB Brain (Binary Microstructure) */}
            <div className="p-2.5 rounded bg-[#13171c] border border-purple-500/20 space-y-1.5 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-12 h-12 bg-purple-500/5 rounded-full blur-xl pointer-events-none" />
              <div className="flex items-center justify-between">
                <span className="text-[9px] font-bold uppercase text-purple-400 flex items-center gap-1">
                  <Cpu className="w-3 h-3" />
                  Kalshi CLOB
                </span>
                <span
                  className={`px-1.5 py-0.2 rounded font-bold text-[9px] ${
                    kalshiSignal === 'UP'
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      : kalshiSignal === 'DOWN'
                      ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                      : 'bg-slate-700 text-slate-300'
                  }`}
                >
                  {kalshiSignal}
                </span>
              </div>
              <div className="flex items-baseline justify-between pt-0.5">
                <span className="text-[#8c9ba5] text-[9px]">Confidence:</span>
                <span className="text-white font-bold text-xs">{kalshiConfidence}%</span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-[#1e252e] overflow-hidden">
                <div
                  className="h-full bg-purple-400 transition-all duration-300"
                  style={{ width: `${kalshiConfidence}%` }}
                />
              </div>
              <div className="text-[8px] text-[#6e7d8b] pt-0.5 flex justify-between">
                <span>28-D Tensor</span>
                <span className="text-emerald-400">0.38ms (CPU)</span>
              </div>
            </div>
          </div>

          {/* Contradiction / Momentum Lead-Lag Rationale Banner */}
          <div className="p-2.5 rounded bg-[#12161f] border border-[#232b35] text-[10px] space-y-1">
            <div className="flex items-center justify-between text-[#8c9ba5]">
              <span className="font-bold uppercase tracking-wider text-[#a5b4fc] flex items-center gap-1">
                <span>🎯 Execution Rationale:</span>
              </span>
              <span className="text-[9px] text-[#34d399] font-semibold">
                Maker Limit: ≤ ${botParams.discount_limit_price?.toFixed(2) || '0.52'}
              </span>
            </div>
            <p className="text-white text-[11px] leading-tight">
              {dualRationale}
            </p>
          </div>

          {/* Softmax Probability Distribution Bar */}
          <div className="space-y-1 pt-0.5">
            <div className="flex justify-between text-[10px] text-[#8c9ba5]">
              <span>Softmax Distribution:</span>
              <span className="text-white font-bold">
                YES {onnxProbLong}% · NO {onnxProbShort}% · WAIT {onnxProbWait}%
              </span>
            </div>
            <div className="w-full h-2 rounded bg-[#171c22] overflow-hidden flex">
              <div className="bg-purple-500 transition-all duration-300" style={{ width: `${onnxProbLong}%` }} title={`YES ${onnxProbLong}%`} />
              <div className="bg-rose-500 transition-all duration-300" style={{ width: `${onnxProbShort}%` }} title={`NO ${onnxProbShort}%`} />
              <div className="bg-slate-600 transition-all duration-300" style={{ width: `${onnxProbWait}%` }} title={`WAIT ${onnxProbWait}%`} />
            </div>
          </div>
        </div>
      ) : activeProfile.telemetryType === 'antipin' ? (
        // --- Dominion 2 Anti-Pin Scalper Telemetry ---
        <div className="p-3.5 bg-[#0e1117] border-b border-[#262d35] space-y-2.5 font-mono">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Crown className="w-4 h-4 text-[#d9a752]" />
              <span className="text-xs font-bold text-white uppercase tracking-wider">Anti-Pin Zone Defense</span>
            </div>
            <span className="text-[10px] text-amber-400 font-bold px-1.5 py-0.5 rounded bg-amber-500/15 border border-amber-500/30">
              ENTRY CEILING: ≤ ${botParams.discount_limit_price?.toFixed(2) || '0.42'}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <div className="p-2 rounded bg-[#13171c] border border-[#1f262d]">
              <span className="text-[#8c9ba5]">PIN RISK RANGE:</span>
              <div className="text-sm font-bold text-white mt-0.5">|Diff| &lt; $25 (T &lt; 180s)</div>
            </div>
            <div className="p-2 rounded bg-[#13171c] border border-[#1f262d]">
              <span className="text-[#8c9ba5]">DISCOUNT VALUE:</span>
              <div className="text-sm font-bold text-[#34d399] mt-0.5">$0.25 - $0.42 Range</div>
            </div>
          </div>
        </div>
      ) : activeProfile.telemetryType === 'scalper' ? (
        // --- OFI Sprint Scalper Telemetry ---
        <div className="p-3.5 bg-[#0e1117] border-b border-[#262d35] space-y-2.5 font-mono">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Crosshair className="w-4 h-4 text-[#00bda5]" />
              <span className="text-xs font-bold text-white uppercase tracking-wider">OFI Sprint Momentum</span>
            </div>
            <span className="text-[10px] text-teal-400 font-bold px-1.5 py-0.5 rounded bg-teal-500/15 border border-teal-500/30">
              5M SPRINT DYNAMICS
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <div className="p-2 rounded bg-[#13171c] border border-[#1f262d]">
              <span className="text-[#8c9ba5]">ORDER FLOW IMBALANCE:</span>
              <div className="text-sm font-bold text-emerald-400 mt-0.5">+4.2 cts/sec (Bullish)</div>
            </div>
            <div className="p-2 rounded bg-[#13171c] border border-[#1f262d]">
              <span className="text-[#8c9ba5]">SETTLEMENT FREEZE:</span>
              <div className="text-sm font-bold text-amber-300 mt-0.5">T-60s Hard Sweep</div>
            </div>
          </div>
        </div>
      ) : activeProfile.id === 'bot1_v4_domination' ? (
        // --- Bot 1 V4: Multi-Turnover Domination Engine Deck ---
        <div className="p-3.5 bg-[#0b1017] border-b border-[#262d35] space-y-3 font-mono">
          {/* Header Bar */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-bold text-white uppercase tracking-wider">
                Bot 1 V4 Multi-Turnover Engine
              </span>
              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40">
                15M V4.0
              </span>
            </div>
            <span className="text-[10px] text-amber-400 font-bold px-2 py-0.5 rounded bg-amber-500/15 border border-amber-500/30">
              MAKER LIMIT: ≤ ${botParams.discount_limit_price?.toFixed(2) || '0.59'}
            </span>
          </div>

          {/* Turnover Progress Gauge & EV Coupling Bar */}
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            {/* Gauge A: Turnover Counter */}
            <div className="p-2.5 rounded bg-[#13171c] border border-amber-500/30 space-y-1 relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-[#8c9ba5] text-[9px] uppercase font-bold">Turnover Cap:</span>
                <span className="text-amber-400 font-bold text-xs">
                  {botParams.turnovers_completed ?? 0} / {botParams.max_turnover_per_event ?? 4}
                </span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-[#1e252e] overflow-hidden">
                <div
                  className="h-full bg-amber-400 transition-all duration-300"
                  style={{ width: `${Math.min(100, ((botParams.turnovers_completed ?? 0) / (botParams.max_turnover_per_event ?? 4)) * 100)}%` }}
                />
              </div>
              <div className="text-[8px] text-[#6e7d8b] flex justify-between pt-0.5">
                <span>Micro-Bankroll: 1 Lot Cap</span>
                <span className="text-amber-300">Sequential</span>
              </div>
            </div>

            {/* Gauge B: EV Math Coupling */}
            <div className="p-2.5 rounded bg-[#13171c] border border-emerald-500/30 space-y-1 relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-[#8c9ba5] text-[9px] uppercase font-bold">EV Math Coupling:</span>
                <span className="text-emerald-400 font-bold text-xs">
                  +${(botParams.min_ev_hurdle_dollars ?? 0.02).toFixed(2)} EV
                </span>
              </div>
              <div className="text-[9px] text-white font-bold flex justify-between pt-0.5">
                <span>P_win Req:</span>
                <span className="text-emerald-300 font-extrabold">
                  {(((botParams.discount_limit_price ?? 0.59) + (botParams.min_ev_hurdle_dollars ?? 0.02)) * 100).toFixed(1)}%
                </span>
              </div>
              <div className="text-[8px] text-[#6e7d8b] flex justify-between">
                <span>P_entry: {((botParams.discount_limit_price ?? 0.59) * 100).toFixed(0)}¢</span>
                <span className="text-emerald-400">$0.00 Fee</span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        // --- 3-Step Dominion Playbook Telemetry ---
        <div className="p-3.5 bg-[#0e1117] border-b border-[#262d35] space-y-2 font-mono">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-bold text-white uppercase tracking-wider">3-Step Dominion v3.2</span>
            </div>
            <span className="text-[10px] text-emerald-400 font-bold px-1.5 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/30">
              MAKER CEILING: ${botParams.discount_limit_price?.toFixed(2) || '0.51'}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-1.5 text-[9px] text-center">
            <div className="p-1.5 rounded bg-[#13171c] border border-[#1f262d] text-[#8c9ba5]">
              <div>STAGE 1 (0-5m)</div>
              <div className="font-bold text-white mt-0.5">Breakout</div>
            </div>
            <div className="p-1.5 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-300">
              <div>STAGE 2 (5-11m)</div>
              <div className="font-bold text-white mt-0.5">★ OFI Drift</div>
            </div>
            <div className="p-1.5 rounded bg-[#13171c] border border-[#1f262d] text-[#8c9ba5]">
              <div>STAGE 3 (11-14m)</div>
              <div className="font-bold text-white mt-0.5">Gamma Snub</div>
            </div>
          </div>
        </div>
      )}

    </>
  );
};
