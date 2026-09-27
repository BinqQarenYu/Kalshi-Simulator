/**
 * @file PerpetualBotPanel.tsx
 * @description Docked bottom panel beneath the perpetual chart for real-time bot configuration.
 * Features:
 * 1. Active Bot status badge & ARM/DISARM master switch
 * 2. Real-time Conviction Gauge and Strategy Rationale feed
 * 3. Interactive parameter tuning sliders:
 *    - Model Conviction Gate (50% to 95%)
 *    - Take-Profit Harvest Target (% ROI)
 *    - Protective Trailing Stop (% Drawdown buffer)
 *    - Dynamic Volatility Moat ($ Dollars)
 *    - VPIN Adverse Selection Toxicity Cap
 */

import React from 'react';
import { usePerpetualTrading } from '../../context/PerpetualTradingContext';
import { Bot, Sliders, Shield, Zap, CheckCircle2, AlertTriangle, Play, Pause } from 'lucide-react';
import { soundFX } from '../../utils/audioFX';

export const PerpetualBotPanel: React.FC = () => {
  const { activeBotId, botConfigs, updateBotParam, toggleArmBot } = usePerpetualTrading();

  const bot = botConfigs[activeBotId];
  if (!bot) return null;

  const handleToggleArm = () => {
    soundFX.playClickSound();
    toggleArmBot(activeBotId);
  };

  return (
    <div className="bg-[#12161a] border border-[#1f2937] rounded-xl p-4 flex flex-col gap-3 text-xs font-mono shadow-xl">
      {/* Bot Header Ribbon */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
            <Bot className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-white text-sm">{bot.name}</span>
              <span className="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-[#1a2128] text-slate-300 border border-slate-800">
                {bot.strategyType}
              </span>
            </div>
            <span className="text-[11px] text-slate-400">
              Continuous live neural inference & risk guardrails
            </span>
          </div>
        </div>

        {/* Master Arming Switch */}
        <div className="flex items-center gap-3">
          <div className="text-right">
            <span className="text-[10px] text-slate-400 block">SYSTEM STATUS</span>
            <span
              className={`text-xs font-bold ${
                bot.isArmed ? 'text-emerald-400' : 'text-amber-400'
              }`}
            >
              {bot.isArmed ? '● ARMED & EXECUTING' : '○ STANDBY MODE'}
            </span>
          </div>

          <button
            onClick={handleToggleArm}
            className={`px-4 py-2 rounded-lg font-bold flex items-center gap-1.5 transition-all shadow-md ${
              bot.isArmed
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/50 hover:bg-emerald-500/30'
                : 'bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700'
            }`}
          >
            {bot.isArmed ? (
              <>
                <Pause className="w-3.5 h-3.5 text-emerald-400" />
                <span>ARMED</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 text-amber-400" />
                <span>ARM BOT</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Real-time Signals Bar */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="bg-[#1a2128] p-2.5 rounded-lg border border-slate-800 flex items-center justify-between">
          <span className="text-slate-400 text-[11px]">Directional Lean:</span>
          <span
            className={`font-bold uppercase px-2 py-0.5 rounded text-[11px] ${
              bot.signals.recommendedSide === 'long'
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                : bot.signals.recommendedSide === 'short'
                ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                : 'bg-slate-800 text-slate-400'
            }`}
          >
            {bot.signals.recommendedSide}
          </span>
        </div>

        <div className="bg-[#1a2128] p-2.5 rounded-lg border border-slate-800 flex items-center justify-between">
          <span className="text-slate-400 text-[11px]">Model Conviction:</span>
          <span className="text-cyan-400 font-bold">{bot.signals.conviction.toFixed(1)}%</span>
        </div>

        <div className="bg-[#1a2128] p-2.5 rounded-lg border border-slate-800 flex items-center justify-between">
          <span className="text-slate-400 text-[11px]">VPIN Toxicity:</span>
          <span className="text-emerald-400 font-bold">{bot.signals.vpin.toFixed(2)}</span>
        </div>

        <div className="bg-[#1a2128] p-2.5 rounded-lg border border-slate-800 flex items-center justify-between">
          <span className="text-slate-400 text-[11px]">Dynamic Moat:</span>
          <span className="text-amber-400 font-bold">${bot.dynamicMoat.toFixed(2)}</span>
        </div>
      </div>

      {/* Dynamic Tuning Sliders Deck */}
      <div className="bg-[#1a2128]/40 p-3 rounded-lg border border-slate-800 grid grid-cols-1 md:grid-cols-4 gap-4 pt-3">
        {/* Slider 1: Min Confidence Gate */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-[11px]">
            <span className="text-slate-400">Min Conviction</span>
            <span className="text-cyan-400 font-bold">{bot.minConfidence}%</span>
          </div>
          <input
            type="range"
            min="50"
            max="95"
            step="1"
            value={bot.minConfidence}
            onChange={(e) => updateBotParam(activeBotId, 'minConfidence', parseFloat(e.target.value))}
            className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
          />
        </div>

        {/* Slider 2: Take Profit Target */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-[11px]">
            <span className="text-slate-400">Take Profit (% ROI)</span>
            <span className="text-emerald-400 font-bold">+{bot.takeProfitPct}%</span>
          </div>
          <input
            type="range"
            min="1.0"
            max="15.0"
            step="0.5"
            value={bot.takeProfitPct}
            onChange={(e) => updateBotParam(activeBotId, 'takeProfitPct', parseFloat(e.target.value))}
            className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-emerald-400"
          />
        </div>

        {/* Slider 3: Trailing Stop Pullback */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-[11px]">
            <span className="text-slate-400">Trailing Ratchet</span>
            <span className="text-amber-400 font-bold">{bot.trailingStopPct}%</span>
          </div>
          <input
            type="range"
            min="0.2"
            max="3.0"
            step="0.1"
            value={bot.trailingStopPct}
            onChange={(e) => updateBotParam(activeBotId, 'trailingStopPct', parseFloat(e.target.value))}
            className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
          />
        </div>

        {/* Slider 4: Dynamic Moat Dollars */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-[11px]">
            <span className="text-slate-400">Safety Moat ($)</span>
            <span className="text-white font-bold">${bot.dynamicMoat}</span>
          </div>
          <input
            type="range"
            min="5.0"
            max="100.0"
            step="5.0"
            value={bot.dynamicMoat}
            onChange={(e) => updateBotParam(activeBotId, 'dynamicMoat', parseFloat(e.target.value))}
            className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-slate-400"
          />
        </div>
      </div>
    </div>
  );
};
